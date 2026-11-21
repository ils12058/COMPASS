"""Urgent intake, staff scope, source slip, concurrency, queue and content-free notices."""

from uuid import uuid4

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.notifications.current import notification_is_current
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import EmailDelivery, Notification, NotificationPreference
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import list_my_notifications, unread_count_for
from compass.referrals import faculty_services, services
from compass.referrals.faculty_rules import AdministrativeReferralError
from compass.referrals.models import Referral, ReferralUrgencyChange
from compass.referrals.notification_contract import create_urgent_notices
from compass.referrals.urgency import change_urgency, urgency_facts
from compass.work_queue.services import list_work
from tests.faculty_referral_helpers import confirm, submit
from tests.referral_administration_helpers import make_world, transition

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    return make_world(monkeypatch)


def change(world, pk, urgent, version, **kwargs):
    args = dict(
        actor=world.counselor,
        actor_session=world.counselor_issued.session,
        referral_id=pk,
        is_urgent=urgent,
        expected_version=version,
        context=AuditContext.user(world.counselor),
    )
    args.update(kwargs)
    return change_urgency(**args)


def paper(world, **kwargs):
    args = dict(
        actor=world.counselor,
        student_id=world.student.pk,
        course_year_block="Synthetic course",
        reason="Synthetic confidential reason",
        referrer_name="Synthetic referrer",
        referred_on=timezone.localdate(),
        received_at=None,
        idempotency_key=str(uuid4()),
        request_fingerprint="a" * 64,
        context=AuditContext.user(world.counselor),
    )
    args.update(kwargs)
    return services.create_referral(**args)


def test_faculty_urgent_intake_replay_own_scope_and_slip(world):
    ticket = confirm(world)["confirmation"]
    value, created = submit(world, ticket, is_urgent=True)
    assert created and value["is_urgent"] is True
    row = Referral.objects.get(pk=value["id"])
    before = services.build_referral_render_context(row)
    assert not {"is_urgent", "urgency", "priority"}.intersection(before)
    change(world, row.pk, False, 1)
    row.refresh_from_db()
    assert services.build_referral_render_context(row) == before
    replay, created = submit(world, ticket, is_urgent=True)
    assert not created and replay["is_urgent"] is False
    assert row.urgency_changes.count() == 2
    with pytest.raises(services.ReferralCreationConflict):
        submit(world, ticket, is_urgent=False)
    with pytest.raises(services.ReferralNotFound):
        faculty_services.get_own_submission(
            actor=world.other_faculty, actor_session=world.other_issued.session, referral_id=row.pk
        )
    assert "reason" not in replay and "urgency_changed_by" not in replay
    events = AuditEvent.objects.filter(target_id=str(row.pk), action__startswith="referral.urgency")
    assert set(events.values_list("actor_user_id", flat=True)) == {
        world.faculty.pk,
        world.counselor.pk,
    }
    assert all(set(event.metadata) == {"is_urgent", "version"} for event in events)


def test_staff_encode_mark_clear_versions_filter_and_append_only(world):
    row = paper(world, is_urgent=True)
    assert urgency_facts(row)["is_urgent"]
    assert services.list_referrals(actor=world.counselor, is_urgent=True).items[0].pk == row.pk
    cleared = change(world, row.pk, False, 1)
    assert (
        cleared["urgency_version"] == 2
        and cleared["urgency_changed_by"]["id"] == world.counselor.pk
    )
    assert cleared["urgency_changed_at"] is not None
    assert not services.list_referrals(actor=world.counselor, is_urgent=True).items
    with pytest.raises(AdministrativeReferralError):
        change(world, row.pk, True, 1)
    assert change(world, row.pk, True, 2)["urgency_version"] == 3
    assert change(world, row.pk, True, 3)["urgency_version"] == 3
    latest = row.urgency_changes.first()
    for operation in (
        lambda: latest.save(),
        lambda: latest.delete(),
        lambda: ReferralUrgencyChange.objects.filter(pk=latest.pk).update(is_urgent=False),
        lambda: ReferralUrgencyChange.objects.filter(pk=latest.pk).delete(),
    ):
        with pytest.raises(ValidationError):
            operation()


@pytest.mark.parametrize("actor_name", ["faculty", "student", "admin", "other_counselor"])
def test_urgency_mutation_denies_unauthorized_and_out_of_scope_staff(world, actor_name):
    row = paper(world)
    actor = getattr(world, actor_name)
    issued = create_auth_session(actor)
    with pytest.raises((AdministrativeReferralError, services.ReferralNotFound)):
        change(world, row.pk, True, 0, actor=actor, actor_session=issued.session)
    assert not row.urgency_changes.exists()


def test_staff_urgency_api_session_capability_and_strict_version(world):
    row = paper(world)
    client = Client()
    url = f"/api/v1/referrals/{row.pk}/urgency"
    payload = {"expected_version": 0, "is_urgent": True}
    assert client.post(url, payload, content_type="application/json").status_code == 401
    client.cookies["compass_session"] = world.staff_issued.token
    assert client.post(url, payload, content_type="application/json").status_code == 200
    assert client.post(url, payload, content_type="application/json").status_code == 409
    assert (
        client.post(
            url, {**payload, "is_urgent": "true"}, content_type="application/json"
        ).status_code
        == 422
    )
    UserCapabilityOverride.objects.create(
        user=world.staff,
        capability=Capability.objects.get(code="referrals.manage"),
        effect="REVOKE",
    )
    assert client.post(url, payload, content_type="application/json").status_code == 403


def test_queue_priority_scope_and_drop_on_acknowledgment_or_action(world):
    value, _ = submit(world, is_urgent=True)
    row = Referral.objects.get(pk=value["id"])
    from compass.good_moral.models import GoodMoralRequest

    routine = GoodMoralRequest.objects.create(
        student=world.student,
        initiation_origin="STUDENT_SELF",
        initiated_by=world.student,
        variant="GRADUATE",
    )
    for actor in (world.counselor, world.staff):
        result = list_work(actor=actor, page_size=1)
        assert result.items[0].source_id == row.pk
        assert result.items[0].priority == "TIME_SENSITIVE"
        assert result.has_next
        assert list_work(actor=actor, page=2, page_size=1).items[0].source_id == routine.pk
    assert all(
        item.kind != "URGENT_REFERRAL" for item in list_work(actor=world.other_counselor).items
    )
    # Even deadline-bearing work must follow the immediate referral at the global merge.
    from compass.work_queue.schemas import WorkItem, WorkKind, WorkPriority, WorkStudent
    from compass.work_queue.services import _rank

    due = WorkItem(
        id="due",
        kind=WorkKind.CALL_SLIP_DUE,
        priority=WorkPriority.TIME_SENSITIVE,
        source_id=uuid4(),
        student=WorkStudent(id=world.student.pk, display_name="Synthetic"),
        conversation_kind=None,
        due_at=timezone.now(),
        waiting_since=None,
    )
    assert (
        sorted([due, list_work(actor=world.counselor).items[0]], key=_rank)[0].source_id == row.pk
    )
    transition(world, row.pk)
    assert all(item.kind != "URGENT_REFERRAL" for item in list_work(actor=world.counselor).items)
    assert urgency_facts(row)["is_urgent"]  # history retains the original urgency
    encoded = paper(world, is_urgent=True)
    services.record_action(
        actor=world.counselor,
        referral_id=encoded.pk,
        action_type="CALL_PARENT_GUARDIAN",
        occurred_at=timezone.now(),
        remarks="",
        context=AuditContext.user(world.counselor),
    )
    assert all(item.kind != "URGENT_REFERRAL" for item in list_work(actor=world.counselor).items)


def test_immediate_notices_only_responsible_staff_content_free_and_rechecked(world):
    NotificationPreference.objects.create(user=world.staff, optional_email_enabled=False)
    value, _ = submit(world, is_urgent=True)
    notices = Notification.objects.filter(event_code=NotificationEvent.REFERRAL_URGENT)
    assert set(notices.values_list("recipient_id", flat=True)) == {
        world.counselor.pk,
        world.staff.pk,
    }
    assert EmailDelivery.objects.filter(notification__in=notices).count() == 2
    create_urgent_notices(referral_id=value["id"])
    assert notices.count() == 2
    for notice in notices:
        assert notification_is_current(notice)
        assert unread_count_for(actor=notice.recipient) == 1
        plan = resolve_notification_email_presentation(notice)
        rendered = render_notification_email(notice.event_code, presentation=plan)
        assert f"https://portal.example/portal/referrals/{value['id']}" in rendered.text_body
        body = (
            rendered.text_body
            + rendered.html_body
            + rendered.subject
            + notice.title
            + notice.message
        )
        for secret in (
            world.student.get_full_name(),
            world.student.email,
            world.student.institutional_id,
            "Synthetic confidential reason",
            "Faculty supplied",
        ):
            assert secret not in body
        assert deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk) == "SENT"
    assert len(mail.outbox) == 2
    change(world, value["id"], False, 1)
    for actor in (world.counselor, world.staff):
        assert not list_my_notifications(actor=actor).items
        assert unread_count_for(actor=actor) == 0
    change(world, value["id"], True, 2)
    assert notices.all().count() == 4  # a new urgent intention, one notice per recipient
    UserCapabilityOverride.objects.create(
        user=world.staff, capability=Capability.objects.get(code="referrals.view"), effect="REVOKE"
    )
    assert not list_my_notifications(actor=world.staff).items
    for notice in notices.filter(recipient=world.staff):
        assert not notification_is_current(notice)


def test_encoded_paper_receipt_is_history_not_digital_acknowledgment(world):
    row = paper(world, is_urgent=True, received_at=timezone.now())
    assert list_work(actor=world.counselor).items[0].source_id == row.pk
    assert (
        Notification.objects.filter(
            target_id=row.pk, event_code=NotificationEvent.REFERRAL_URGENT
        ).count()
        == 2
    )


def test_faculty_submit_api_carries_urgency_and_rejects_coercion(world):
    client = Client()
    client.cookies["compass_session"] = world.issued.token
    payload = dict(
        confirmation=confirm(world)["confirmation"],
        course_year_block="Synthetic",
        reason="Synthetic",
        is_urgent=True,
    )
    response = client.post(
        "/api/v1/faculty/referrals",
        payload,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="urgent-api",
    )
    assert response.status_code == 201 and response.json()["is_urgent"] is True
    assert (
        client.get(f"/api/v1/faculty/referrals/{response.json()['id']}").json()["is_urgent"] is True
    )
    invalid = client.post(
        "/api/v1/faculty/referrals",
        {**payload, "is_urgent": "true"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="urgent-api-2",
    )
    assert invalid.status_code == 422


def test_urgency_audit_failure_rolls_back_state_and_notice(world, monkeypatch):
    row = paper(world)

    def fail(**kwargs):
        raise RuntimeError("Synthetic audit unavailable")

    monkeypatch.setattr("compass.referrals.urgency.record_event", fail)
    with pytest.raises(RuntimeError):
        change(world, row.pk, True, 0)
    assert not row.urgency_changes.exists()
    assert not Notification.objects.filter(event_code=NotificationEvent.REFERRAL_URGENT).exists()


def test_revoked_session_cannot_change_urgency(world):
    from compass.referrals.timing_services import ReferralTimingSessionUnavailable

    row = paper(world)
    world.counselor_issued.session.revoked_at = timezone.now()
    world.counselor_issued.session.save(update_fields=["revoked_at"])
    with pytest.raises(ReferralTimingSessionUnavailable):
        change(world, row.pk, True, 0)
    assert not row.urgency_changes.exists()


def test_head_work_and_notice_follow_responsibility_not_oversight(world):
    from compass.accounts.models import Designation, UserDesignation
    from compass.organization.models import CounselorResponsibility

    UserDesignation.objects.create(
        user=world.other_counselor,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    value, _ = submit(world, is_urgent=True)
    assert not list_work(actor=world.other_counselor).items
    assert not Notification.objects.filter(
        recipient=world.other_counselor, event_code=NotificationEvent.REFERRAL_URGENT
    ).exists()
    # The existing unique-Head fallback owns Colleges without an active Counselor assignment.
    CounselorResponsibility.objects.filter(college=world.ccms).delete()
    assert list_work(actor=world.other_counselor).items[0].source_id == value["id"]
    assert not list_work(actor=world.counselor).items
    assert not list_work(actor=world.staff).items
    assert not list_my_notifications(actor=world.counselor).items


@pytest.mark.parametrize("change_kind", ["supervision", "student", "college"])
def test_current_responsibility_loss_hides_urgent_work_and_pending_email(world, change_kind):
    from compass.organization.models import StaffSupervision

    value, _ = submit(world, is_urgent=True)
    notice = Notification.objects.get(
        recipient=world.staff, event_code=NotificationEvent.REFERRAL_URGENT
    )
    if change_kind == "supervision":
        StaffSupervision.objects.filter(staff=world.staff).delete()
    elif change_kind == "student":
        world.student.is_active = False
        world.student.save(update_fields=["is_active"])
    else:
        world.ccms.is_active = False
        world.ccms.save(update_fields=["is_active"])
    assert not list_work(actor=world.staff).items
    assert not notification_is_current(notice)
    assert not list_my_notifications(actor=world.staff).items
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk) == "skipped"
    assert not mail.outbox
    assert Referral.objects.get(pk=value["id"]).urgency_changes.exists()
