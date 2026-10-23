"""Synthetic NOTIF-03 source, policy and transport-boundary regressions."""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from django.core import mail
from django.db import close_old_connections, transaction
from django.utils import timezone

from compass.accounts.models import Capability, Role, User, UserCapabilityOverride
from compass.call_slips.models import CallSlip
from compass.good_moral.models import GoodMoralRequest
from compass.group_sessions.models import GroupSession, GroupSessionRegistration
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import EmailDelivery, Notification
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from tests.test_appointments import active_service, sync_policy

POLICY = "operational_v1"
EVENTS = (
    NotificationEvent.GROUP_SESSION_REGISTERED,
    NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED,
    NotificationEvent.GROUP_SESSION_CANCELLED,
    NotificationEvent.GROUP_SESSION_RESCHEDULED,
    NotificationEvent.GOOD_MORAL_REQUEST_INITIATED,
    NotificationEvent.GOOD_MORAL_ISSUED,
    NotificationEvent.CALL_SLIP_ISSUED,
    NotificationEvent.CALL_SLIP_VOIDED,
)


@pytest.fixture(autouse=True)
def synthetic_transport(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "minimal"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


@pytest.fixture
def world(db):
    sync_policy()
    users = {}
    for name, role in (("student", "STUDENT"), ("other", "STUDENT"), ("staff", "COUNSELOR")):
        users[name] = User.objects.create_user(
            email=f"notif03-{name}@example.test",
            password=None,
            role=Role.objects.get(code=role),
            first_name="PRIVATE_PERSON",
            last_name=name,
        )
    users["service"] = active_service(users["staff"])
    return users


def form(key, code):
    family, _ = FormFamily.objects.get_or_create(key=key, defaults={"title": "Synthetic form"})
    active = FormRevision.objects.filter(family=family, status="ACTIVE").first()
    if active is not None:
        return active
    revision, _ = FormRevision.objects.get_or_create(
        family=family,
        official_code=code,
        official_revision="2",
        defaults={"internal_schema_version": 1, "status": "ACTIVE"},
    )
    return revision


def intent(world, event, *, recipient=None):
    student, staff = world["student"], world["staff"]
    at = timezone.now()
    if event.value.startswith("group_session."):
        session = GroupSession.objects.create(
            service=world["service"],
            organizer=staff,
            title="PRIVATE_SENSITIVE_TITLE <script>",
            description="PRIVATE_DESCRIPTION",
            capacity=20,
            status="PUBLISHED",
            delivery_mode="ONLINE",
            venue_or_meeting_url="https://meeting.invalid/PRIVATE_TOKEN",
            starts_at=datetime(2099, 10, 23, 1, tzinfo=UTC),
            ends_at=datetime(2099, 10, 23, 2, tzinfo=UTC),
        )
        reg = GroupSessionRegistration.objects.create(
            group_session=session, student=student, registered_at=at - timedelta(hours=1)
        )
        source_type, source_id = "group_session_registration", reg.pk
        if event == NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED:
            reg.status, reg.cancelled_at = "CANCELLED", at
            reg.save()
        elif event == NotificationEvent.GROUP_SESSION_CANCELLED:
            session.status, session.cancelled_at = "CANCELLED", at
            session.save()
            reg.status, reg.cancelled_at = "CANCELLED", at
            reg.save()
            source_type, source_id = "group_session", session.pk
        elif event == NotificationEvent.GROUP_SESSION_RESCHEDULED:
            session.schedule_revision = 2
            session.save()
            source_type, source_id = "group_session_schedule_v2", session.pk
        item, target_type = session, "GROUP_SESSION"
    elif event.value.startswith("good_moral."):
        item = GoodMoralRequest.objects.create(
            student=student,
            variant="GRADUATE",
            initiation_origin="GCO_ASSISTED",
            initiated_by=staff,
            official_receipt_number="PRIVATE_OR_NUMBER",
            official_receipt_amount="999.99",
            official_receipt_date=at.date(),
            applicant_name_snapshot="PRIVATE_APPLICANT",
            degree_snapshot="PRIVATE_ACADEMIC",
        )
        if event == NotificationEvent.GOOD_MORAL_ISSUED:
            item.status, item.issued_at, item.issued_by = "ISSUED", at, staff
            item.issued_by_name_snapshot = "PRIVATE_ISSUER"
            item.form_revision = form("good_moral_graduate", "UCN-OP-GCO-01F6")
            item.document_template_key, item.document_template_version = "good_moral_graduate", 1
            item.save()
        source_type, source_id, target_type = "good_moral_request", item.pk, "GOOD_MORAL"
    else:
        item = CallSlip.objects.create(
            student=student,
            issued_by=staff,
            student_name_snapshot="PRIVATE_STUDENT",
            course_year_snapshot="PRIVATE_COURSE",
            issued_by_name_snapshot="PRIVATE_ISSUER",
            destination_type="OTHER",
            other_destination="PRIVATE_DESTINATION",
            report_at=at + timedelta(days=2),
            issuance_mode="LIVE",
            form_revision=form("call_slip", "UCN-OP-GCO-01F2"),
        )
        if event == NotificationEvent.CALL_SLIP_VOIDED:
            item.voided_at, item.void_reason = at, "PRIVATE_VOID_REASON"
            item.save()
        source_type, source_id, target_type = "call_slip", item.pk, "CALL_SLIP"
    notification = create_notification_for_event(
        recipient=recipient or student,
        event=event,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=item.pk,
    )
    return notification, item


def resolve_render(notification):
    plan = resolve_notification_email_presentation(notification)
    return plan, render_notification_email(notification.event_code, presentation=plan)


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("policy", ["minimal", POLICY])
def test_all_operational_events_use_source_owned_safe_links(world, settings, event, policy):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = policy
    notification, item = intent(world, event)
    plan, message = resolve_render(notification)
    route = {
        "GROUP_SESSION": "group-sessions",
        "GOOD_MORAL": "good-moral",
        "CALL_SLIP": "call-slips",
    }[notification.target_type]
    url = f"https://portal.example/portal/{route}/{item.pk}"
    assert plan.reason == ("rich_available" if policy == POLICY else "link_available")
    assert url in message.text_body and url in message.html_body
    assert "PRIVATE" not in message.text_body + message.html_body + repr(plan)
    assert ("Status:" in message.text_body) is (policy == POLICY)


def test_real_settings_default_is_centralized_and_obsolete_name_absent():
    environment = dict(os.environ)
    for key in (
        "COMPASS_EMAIL_DISCLOSURE_POLICY",
        "COMPASS_EMAIL_DISCLOSURE_POLICY_FILE",
        "APPOINTMENT_EMAIL_DISCLOSURE_POLICY",
        "APPOINTMENT_EMAIL_DISCLOSURE_POLICY_FILE",
    ):
        environment.pop(key, None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tests.settings as s; "
            "assert s.COMPASS_EMAIL_DISCLOSURE_POLICY == 'minimal'; "
            "assert not hasattr(s, 'APPOINTMENT_EMAIL_DISCLOSURE_POLICY')",
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "key", ["APPOINTMENT_EMAIL_DISCLOSURE_POLICY", "APPOINTMENT_EMAIL_DISCLOSURE_POLICY_FILE"]
)
@pytest.mark.parametrize("value", ["", "operational_v1"])
def test_obsolete_environment_is_rejected_even_if_empty(key, value):
    environment = dict(os.environ)
    environment[key] = value
    result = subprocess.run(
        [sys.executable, "-c", "import tests.settings"],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "replace" in result.stderr and "COMPASS_EMAIL_DISCLOSURE_POLICY" in result.stderr


@pytest.mark.parametrize("event", EVENTS)
def test_unrelated_student_gets_no_details_or_action(world, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event, recipient=world["other"])
    plan, message = resolve_render(notification)
    assert plan.reason == "recipient_denied"
    assert "https://" not in message.text_body
    assert "PRIVATE" not in message.text_body + message.html_body


@pytest.mark.parametrize("event", EVENTS)
def test_wrong_target_never_gains_link_or_fields(world, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    notification.target_id = uuid4()
    notification.save(update_fields=["target_id"])
    plan, message = resolve_render(notification)
    assert plan.reason == "invalid_source"
    assert "https://" not in message.text_body and "PRIVATE" not in message.text_body


@pytest.mark.parametrize("event", EVENTS)
def test_transport_success_and_duplicate_task_do_not_reissue_intents(world, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    delivery = EmailDelivery.objects.get(notification=notification)
    before = Notification.objects.count()
    assert deliver_email_delivery(delivery.pk) == "SENT"
    assert deliver_email_delivery(delivery.pk) == "skipped"
    assert len(mail.outbox) == 1 and Notification.objects.count() == before


def capability_for(event):
    if event.value.startswith("group_session."):
        return "appointments.view_self"
    if event.value.startswith("good_moral."):
        return "good_moral.view_self"
    return "call_slips.view_self"


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("change", ["inactive", "role", "capability"])
def test_current_self_authority_required_for_both_disclosure_and_links(
    world, settings, event, change
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    if change == "inactive":
        User.objects.filter(pk=world["student"].pk).update(is_active=False)
    elif change == "role":
        User.objects.filter(pk=world["student"].pk).update(role=Role.objects.get(code="IT_ADMIN"))
    else:
        UserCapabilityOverride.objects.create(
            user=world["student"],
            capability=Capability.objects.get(code=capability_for(event)),
            effect="REVOKE",
            reason="Synthetic revocation",
        )
    plan, message = resolve_render(notification)
    assert plan.reason == "recipient_denied"
    assert "https://" not in message.text_body and "PRIVATE" not in message.text_body


@pytest.mark.parametrize("event", EVENTS)
def test_missing_legacy_sources_have_generic_projection_without_data_or_links(
    world, settings, event
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    notification.source_id = uuid4()
    if notification.source_type != "group_session_registration":
        notification.target_id = notification.source_id
    notification.save(update_fields=["source_id", "target_id"])
    plan, message = resolve_render(notification)
    assert plan.reason == "source_missing"
    assert message == render_notification_email(event)


@pytest.mark.parametrize("event", EVENTS)
def test_wrong_source_type_is_never_a_domain_reader(world, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    notification.source_type = "student_session_summary"
    plan, message = resolve_render(notification)
    assert plan.reason == "invalid_source"
    assert "https://" not in message.text_body and "PRIVATE" not in message.text_body


@pytest.mark.parametrize(
    "policy", [None, True, "OPERATIONAL_V1", "operational_v2", " operational_v1"]
)
@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[5], EVENTS[6]])
def test_unrecognized_central_values_only_allow_minimal_links(world, settings, event, policy):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = policy
    notification, _ = intent(world, event)
    plan, message = resolve_render(notification)
    assert plan.reason == "link_available" and plan.disclosure_policy == "minimal"
    assert "Status:" not in message.text_body


@pytest.mark.parametrize("origin", ["", "https://portal.example/bad", "javascript:PRIVATE_TOKEN"])
@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[5], EVENTS[6]])
def test_new_domain_details_require_validated_portal_origin(world, settings, event, origin):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    settings.COMPASS_PORTAL_ORIGIN = origin
    notification, _ = intent(world, event)
    plan, message = resolve_render(notification)
    assert plan.reason in {"origin_missing", "origin_invalid"}
    assert message == render_notification_email(event)


@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[2], EVENTS[3]])
def test_group_details_never_fetch_or_render_free_text_title_or_meeting_context(
    world, settings, event
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, event)
    baseline, message = resolve_render(notification)
    for title in ("<img src=x onerror=PRIVATE_TOKEN>", ("PRIVATE_Counseling " * 15)[:255], ""):
        GroupSession.objects.filter(pk=item.pk).update(title=title, venue_or_meeting_url="")
        plan, current = resolve_render(notification)
        assert plan == baseline and current == message
    assert "PRIVATE" not in message.subject + message.text_body + message.html_body


def test_group_cancellation_requires_proven_participant_at_exact_cancellation(world, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[2])
    GroupSessionRegistration.objects.filter(group_session=item).update(
        cancelled_at=item.cancelled_at - timedelta(minutes=1)
    )
    plan, message = resolve_render(notification)
    assert plan.reason == "recipient_denied" and "https://" not in message.text_body


def test_group_cancelled_registration_is_not_current_after_reregistration(world, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[1])
    GroupSessionRegistration.objects.create(group_session=item, student=world["student"])
    plan = resolve_notification_email_presentation(notification)
    assert plan.reason == "source_superseded" and plan.suppress


@pytest.mark.parametrize("legacy", [False, True])
def test_group_schedule_revision_and_legacy_general_version_have_distinct_rich_proof(
    world, settings, legacy
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[3])
    if legacy:
        notification.source_type = f"group_session_v{item.version}"
        notification.save(update_fields=["source_type"])
    plan, message = resolve_render(notification)
    assert plan.reason == ("link_available" if legacy else "rich_available")
    assert ("Updated date:" in message.text_body) is not legacy
    assert "Previous date:" not in message.text_body
    GroupSession.objects.filter(pk=item.pk).update(schedule_revision=3, version=item.version + 1)
    obsolete = resolve_notification_email_presentation(notification)
    assert obsolete.reason == "source_superseded" and obsolete.suppress


@pytest.mark.parametrize("state", ["CANCELLED", "COMPLETED", "DRAFT", "PAST"])
@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[3]])
def test_group_upcoming_messages_do_not_survive_obsolete_session_state(
    world, settings, event, state
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, event)
    changes = (
        {"status": state}
        if state != "PAST"
        else {
            "starts_at": timezone.now() - timedelta(hours=2),
            "ends_at": timezone.now() - timedelta(hours=1),
        }
    )
    GroupSession.objects.filter(pk=item.pk).update(**changes)
    plan = resolve_notification_email_presentation(notification)
    assert plan.reason == "source_stale" and plan.suppress


def test_group_cross_date_uses_updated_schedule_in_philippine_time(world, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[3])
    GroupSession.objects.filter(pk=item.pk).update(
        starts_at=datetime(2099, 10, 23, 15, 30, tzinfo=UTC),
        ends_at=datetime(2099, 10, 23, 17, tzinfo=UTC),
    )
    _, message = resolve_render(notification)
    assert "October 23, 2099" in message.text_body and "October 24, 2099" in message.text_body
    assert "11:30 PM–1:00 AM (Philippine Time)" in message.text_body


@pytest.mark.parametrize("state", ["REQUESTED", "READY_FOR_ISSUANCE", "CANCELLED", "ISSUED"])
def test_assisted_request_message_tracks_current_status_without_guessing_issuance(
    world, settings, state
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[4] if state != "ISSUED" else EVENTS[5])
    notification.event_code = EVENTS[4]
    if state == "READY_FOR_ISSUANCE":
        item.status, item.prepared_at, item.prepared_by = state, timezone.now(), world["staff"]
        item.save()
    elif state == "CANCELLED":
        item.status, item.cancelled_at, item.cancellation_reason = (
            state,
            timezone.now(),
            "PRIVATE_REASON",
        )
        item.save()
    plan = resolve_notification_email_presentation(notification)
    if state in {"ISSUED", "CANCELLED"}:
        assert plan.suppress
    else:
        message = render_notification_email(notification.event_code, presentation=plan)
        assert (
            "Ready for issuance" if state == "READY_FOR_ISSUANCE" else "Requested"
        ) in message.text_body
        assert "Certificate issued" not in message.text_body and "PRIVATE" not in message.text_body


def test_self_service_request_cannot_be_reinterpreted_as_office_assisted(world, settings):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[4])
    GoodMoralRequest.objects.filter(pk=item.pk).update(
        initiation_origin="STUDENT_SELF", initiated_by=world["student"]
    )
    assert resolve_notification_email_presentation(notification).suppress


@pytest.mark.parametrize("state", ["REQUESTED", "READY_FOR_ISSUANCE", "CANCELLED"])
def test_request_or_preparation_is_not_certificate_issuance(world, settings, state):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[4])
    notification.event_code = EVENTS[5]
    if state == "READY_FOR_ISSUANCE":
        item.status, item.prepared_at, item.prepared_by = state, timezone.now(), world["staff"]
    elif state == "CANCELLED":
        item.status, item.cancelled_at, item.cancellation_reason = (
            state,
            timezone.now(),
            "PRIVATE_REASON",
        )
    item.save()
    assert resolve_notification_email_presentation(notification).suppress


@pytest.mark.parametrize("mode", ["LIVE", "HISTORICAL", "LEGACY_UNKNOWN"])
@pytest.mark.parametrize("event", [EVENTS[6], EVENTS[7]])
def test_call_slip_original_issuance_intent_and_legacy_void_contract(world, settings, event, mode):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, event)
    CallSlip.objects.filter(pk=item.pk).update(issuance_mode=mode)
    plan = resolve_notification_email_presentation(notification)
    if mode == "HISTORICAL" or (mode == "LEGACY_UNKNOWN" and event == EVENTS[6]):
        assert plan.suppress
    else:
        message = render_notification_email(event, presentation=plan)
        assert plan.reason == ("rich_available" if mode == "LIVE" else "link_available")
        assert "PRIVATE" not in message.text_body
        assert ("Status:" in message.text_body) is (mode == "LIVE")


@pytest.mark.parametrize("change", ["voided", "completed"])
def test_pending_call_slip_issuance_cancels_after_obsolete_instruction(world, settings, change):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[6])
    updates = (
        {"voided_at": timezone.now(), "void_reason": "PRIVATE_REASON"}
        if change == "voided"
        else {"interview_ended_at": timezone.now()}
    )
    CallSlip.objects.filter(pk=item.pk).update(**updates)
    assert (
        deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk)
        == "CANCELLED"
    )
    assert not mail.outbox


def mutate_source(item):
    if isinstance(item, GroupSession):
        GroupSession.objects.filter(pk=item.pk).update(schedule_revision=item.schedule_revision + 1)
    elif isinstance(item, GoodMoralRequest):
        GoodMoralRequest.objects.filter(pk=item.pk).update(
            issued_at=item.issued_at + timedelta(days=1)
        )
    else:
        CallSlip.objects.filter(pk=item.pk).update(
            voided_at=timezone.now(), void_reason="PRIVATE_REASON"
        )


@pytest.mark.parametrize("event", [EVENTS[3], EVENTS[5], EVENTS[6]])
@pytest.mark.parametrize("change", ["policy", "origin", "email", "capability", "role", "source"])
def test_post_render_changes_cancel_old_transport(world, settings, monkeypatch, event, change):
    from compass.notifications import delivery as worker

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, event)
    original = worker.render_notification_email

    def rendered_then_change(*args, **kwargs):
        message = original(*args, **kwargs)
        if change == "policy":
            settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "minimal"
        elif change == "origin":
            settings.COMPASS_PORTAL_ORIGIN = "https://changed.example"
        elif change == "email":
            User.objects.filter(pk=world["student"].pk).update(email="changed@example.test")
        elif change == "capability":
            UserCapabilityOverride.objects.create(
                user=world["student"],
                capability=Capability.objects.get(code=capability_for(event)),
                effect="REVOKE",
                reason="Synthetic revocation",
            )
        elif change == "role":
            User.objects.filter(pk=world["student"].pk).update(
                role=Role.objects.get(code="IT_ADMIN")
            )
        else:
            mutate_source(item)
        return message

    monkeypatch.setattr(worker, "render_notification_email", rendered_then_change)
    delivery = EmailDelivery.objects.get(notification=notification)
    assert deliver_email_delivery(delivery.pk) == "CANCELLED"
    delivery.refresh_from_db()
    assert delivery.failure_code == "source_or_recipient_changed"
    assert not mail.outbox


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("event", [EVENTS[3], EVENTS[5], EVENTS[6]])
def test_committed_source_changes_are_seen_by_worker_before_smtp(
    world, settings, monkeypatch, event
):
    from compass.integrations.mail import Mailer
    from compass.notifications import delivery as worker

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, event)
    delivery = EmailDelivery.objects.get(notification=notification)
    rendered, release = threading.Event(), threading.Event()
    original = worker.render_notification_email
    sends = []

    def barrier(*args, **kwargs):
        message = original(*args, **kwargs)
        rendered.set()
        assert release.wait(15)
        return message

    def run():
        close_old_connections()
        try:
            return deliver_email_delivery(delivery.pk)
        finally:
            close_old_connections()

    monkeypatch.setattr(worker, "render_notification_email", barrier)
    monkeypatch.setattr(Mailer, "send", lambda *args, **kwargs: sends.append(kwargs) or 1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(run)
        try:
            assert rendered.wait(15)
            with transaction.atomic():
                mutate_source(item)
        finally:
            release.set()
        assert task.result(15) == "CANCELLED"
    assert not sends


@pytest.mark.parametrize("event", [EVENTS[2], EVENTS[5], EVENTS[7]])
def test_linked_history_uses_actual_student_detail_endpoint_authorization(world, event):
    from tests.test_good_moral import auth_client

    notification, item = intent(world, event)
    api_path = {
        "GROUP_SESSION": f"/api/v1/group-sessions/{item.pk}",
        "GOOD_MORAL": f"/api/v1/good-moral/me/{item.pk}",
        "CALL_SLIP": f"/api/v1/call-slips/me/{item.pk}",
    }[notification.target_type]
    assert auth_client(world["student"]).get(api_path).status_code == 200
    assert auth_client(world["other"]).get(api_path).status_code == 404


@pytest.mark.parametrize(
    "variant,lifecycle", [("CURRENT_STUDENT", "CURRENT"), ("GRADUATE", "GRADUATED")]
)
def test_f4_f6_issuance_projection_preserves_variant_and_omits_private_snapshots(
    world, settings, variant, lifecycle
):
    from tests.test_good_moral import make_academic_year, make_inventory

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[5])
    User.objects.filter(pk=world["student"].pk).update(student_lifecycle_status=lifecycle)
    if variant == "CURRENT_STUDENT":
        year = make_academic_year()
        inventory = make_inventory(world["student"], year)
        GoodMoralRequest.objects.filter(pk=item.pk).update(
            variant=variant,
            inventory=inventory,
            academic_year=year,
            degree_snapshot="",
            form_revision=form("good_moral_current_student", "UCN-OP-GCO-01F4"),
            document_template_key="good_moral_current_student",
            document_template_version=2,
        )
    plan, message = resolve_render(notification)
    assert plan.good_moral_facts.variant == variant
    assert "Certificate issued" in message.text_body
    for forbidden in ("PRIVATE", "999.99", "Receipt", "dry seal", "payment verified"):
        assert forbidden not in message.subject + message.text_body + message.html_body


def test_student_self_service_creation_does_not_add_assisted_notification(world):
    from datetime import date

    from compass.audit.context import AuditContext
    from compass.good_moral.services import create_my_graduate

    student = world["student"]
    student.student_lifecycle_status = "GRADUATED"
    student.save(update_fields=["student_lifecycle_status"])
    item = create_my_graduate(
        student=student,
        degree="Synthetic degree",
        major="",
        idempotency_key="synthetic-notif03-self-service",
        request_fingerprint="a" * 64,
        graduation_date=date(2020, 6, 1),
        context=AuditContext.user(student),
    )
    assert item.initiation_origin == "STUDENT_SELF"
    assert not Notification.objects.filter(source_id=item.pk).exists()


@pytest.mark.parametrize("event", [EVENTS[3], EVENTS[5], EVENTS[6]])
@pytest.mark.parametrize(
    "defect",
    ["mapping", "duplicate", "wrong_recipient", "wrong_event", "wrong_target", "unapproved_policy"],
)
def test_renderer_rejects_forged_domain_rows_and_binding(world, settings, event, defect):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    plan = resolve_notification_email_presentation(notification)
    attribute = {
        "GROUP_SESSION": "group_session_facts",
        "GOOD_MORAL": "good_moral_facts",
        "CALL_SLIP": "call_slip_facts",
    }[notification.target_type]
    facts = getattr(plan, attribute)
    if defect == "mapping":
        facts = replace(facts, rows=({"field": "Status", "value": "PRIVATE"},))
    elif defect == "duplicate":
        facts = replace(facts, rows=(facts.rows[0], facts.rows[0]))
    elif defect == "wrong_recipient":
        facts = replace(facts, recipient_class="unrelated")
    elif defect == "wrong_event":
        facts = replace(facts, event_code="security.password.changed")
    elif defect == "wrong_target":
        plan = replace(plan, target=replace(plan.target, target_id=uuid4()))
    else:
        plan = replace(plan, disclosure_policy="unapproved")
    plan = replace(plan, **{attribute: facts})
    with pytest.raises(ValueError) as exc:
        render_notification_email(event, presentation=plan)
    assert "PRIVATE" not in str(exc.value)


def test_group_cancellation_field_policy_rejects_active_schedule_rows(world, settings):
    from compass.group_sessions.email_presentation import (
        GroupSessionEmailDetail,
        GroupSessionEmailField,
    )

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, EVENTS[2])
    plan = resolve_notification_email_presentation(notification)
    facts = replace(
        plan.group_session_facts,
        rows=(GroupSessionEmailDetail(GroupSessionEmailField.CURRENT_DATE, "PRIVATE"),),
    )
    with pytest.raises(ValueError, match="unapproved operational"):
        render_notification_email(
            notification.event_code, presentation=replace(plan, group_session_facts=facts)
        )


def test_typed_detail_html_escaping_and_plain_text_parity(world, settings):
    from compass.group_sessions.email_presentation import (
        GroupSessionEmailDetail,
        GroupSessionEmailField,
    )

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, EVENTS[0])
    plan = resolve_notification_email_presentation(notification)
    value = "Synthetic <em>label</em> & sample"
    facts = replace(
        plan.group_session_facts,
        rows=(GroupSessionEmailDetail(GroupSessionEmailField.SESSION, value),),
    )
    message = render_notification_email(
        notification.event_code, presentation=replace(plan, group_session_facts=facts)
    )
    assert value in message.text_body
    assert "&lt;em&gt;label&lt;/em&gt; &amp; sample" in message.html_body
    assert "<em>label</em>" not in message.html_body


@pytest.mark.parametrize("defect", ["family", "template", "version", "future_date"])
def test_good_moral_issuance_requires_consistent_persisted_provenance(world, settings, defect):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[5])
    if defect == "family":
        item.form_revision = form("call_slip", "UCN-OP-GCO-01F2")
    elif defect == "template":
        item.document_template_key = "PRIVATE_WRONG_TEMPLATE"
    elif defect == "version":
        item.document_template_version = 999
    else:
        item.issued_at = timezone.now() + timedelta(days=1)
    item.save()
    plan, message = resolve_render(notification)
    assert plan.reason == "provenance_unavailable"
    assert "Status:" not in message.text_body and "https://" not in message.text_body


@pytest.mark.parametrize("family", ["group", "good_moral", "call_slip"])
@pytest.mark.parametrize("value", ["bad\nvalue", "https://secret.invalid/token", "x" * 601])
def test_domain_detail_values_are_bounded_and_errors_content_free(family, value):
    from compass.call_slips.email_presentation import CallSlipEmailDetail, CallSlipEmailField
    from compass.good_moral.email_presentation import GoodMoralEmailDetail, GoodMoralEmailField
    from compass.group_sessions.email_presentation import (
        GroupSessionEmailDetail,
        GroupSessionEmailField,
    )

    detail, field = {
        "group": (GroupSessionEmailDetail, GroupSessionEmailField.STATUS),
        "good_moral": (GoodMoralEmailDetail, GoodMoralEmailField.STATUS),
        "call_slip": (CallSlipEmailDetail, CallSlipEmailField.STATUS),
    }[family]
    with pytest.raises(ValueError) as exc:
        detail(field, value)
    assert value not in str(exc.value)


@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[5], EVENTS[6]])
def test_renderer_requires_available_origin_snapshot_for_new_domain_facts(world, settings, event):
    from compass.notifications.email_links import build_notification_email_link

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    plan = resolve_notification_email_presentation(notification)
    settings.COMPASS_PORTAL_ORIGIN = ""
    invalid = replace(plan, validated_link=build_notification_email_link(plan.target))
    with pytest.raises(ValueError, match="unapproved operational"):
        render_notification_email(event, presentation=invalid)


def test_one_central_declaration_and_no_legacy_runtime_alias():
    import ast

    source = Path("config/settings.py").read_text()
    module = ast.parse(source)
    declared = {
        target.id
        for node in ast.walk(module)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.endswith("EMAIL_DISCLOSURE_POLICY")
    }
    assert declared == {"COMPASS_EMAIL_DISCLOSURE_POLICY"}


@pytest.mark.parametrize("event", [EVENTS[5], EVENTS[6]])
def test_undisclosed_source_changes_do_not_change_email_projection(world, settings, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, event)
    before = resolve_notification_email_presentation(notification)
    if isinstance(item, GoodMoralRequest):
        GoodMoralRequest.objects.filter(pk=item.pk).update(
            official_receipt_number="ANOTHER_PRIVATE_OR",
            official_receipt_amount="123.45",
            applicant_name_snapshot="ANOTHER_PRIVATE_NAME",
        )
    else:
        CallSlip.objects.filter(pk=item.pk).update(
            other_destination="ANOTHER_PRIVATE_DESTINATION",
            student_name_snapshot="ANOTHER_PRIVATE_NAME",
            report_at=item.report_at + timedelta(hours=1),
        )
    assert resolve_notification_email_presentation(notification) == before


def test_registered_notice_labels_current_schedule_instead_of_inventing_initial_snapshot(
    world, settings
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[0])
    GroupSession.objects.filter(pk=item.pk).update(
        schedule_revision=3,
        starts_at=item.starts_at + timedelta(hours=1),
        ends_at=item.ends_at + timedelta(hours=1),
    )
    _, message = resolve_render(notification)
    assert "Current time: 10:00 AM–11:00 AM (Philippine Time)" in message.text_body
    assert "Previous" not in message.text_body and "Original" not in message.text_body


@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[5], EVENTS[6]])
def test_minimal_link_plan_still_detects_profile_change_before_smtp(
    world, settings, monkeypatch, event
):
    from compass.notifications import delivery as worker

    notification, _ = intent(world, event)
    original = worker.render_notification_email

    def change(*args, **kwargs):
        message = original(*args, **kwargs)
        settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
        return message

    monkeypatch.setattr(worker, "render_notification_email", change)
    assert (
        deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk)
        == "CANCELLED"
    )
    assert not mail.outbox


@pytest.mark.parametrize("event", [EVENTS[0], EVENTS[5], EVENTS[6]])
def test_projection_failure_diagnostics_do_not_log_source_facts(
    world, settings, monkeypatch, caplog, event
):
    from compass.notifications import email_presentation as plans

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)

    def fail(**kwargs):
        raise RuntimeError("PRIVATE_SOURCE https://secret.invalid/token")

    method = {
        "GROUP_SESSION": "resolve_group_session_email_facts",
        "GOOD_MORAL": "resolve_good_moral_email_facts",
        "CALL_SLIP": "resolve_call_slip_email_facts",
    }[notification.target_type]
    monkeypatch.setattr(plans, method, fail)
    with caplog.at_level("INFO", logger="compass.notifications"):
        assert (
            deliver_email_delivery(EmailDelivery.objects.get(notification=notification).pk)
            == "FAILED"
        )
    assert "PRIVATE" not in caplog.text and "secret.invalid" not in caplog.text
    assert not mail.outbox


@pytest.mark.parametrize("event", [EVENTS[3], EVENTS[5], EVENTS[6]])
def test_retry_preserves_source_identity_and_never_adds_notification(
    world, settings, monkeypatch, event
):
    from compass.integrations.mail import Mailer

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, _ = intent(world, event)
    delivery = EmailDelivery.objects.get(notification=notification)
    before = resolve_notification_email_presentation(notification)
    count = Notification.objects.count()

    def fail(**kwargs):
        raise RuntimeError("synthetic transport failure")

    monkeypatch.setattr(Mailer, "send", lambda self, **kwargs: fail(**kwargs))
    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    assert resolve_notification_email_presentation(notification) == before
    EmailDelivery.objects.filter(pk=delivery.pk).update(
        next_attempt_at=timezone.now() - timedelta(seconds=1)
    )
    sent = []
    monkeypatch.setattr(Mailer, "send", lambda self, **kwargs: sent.append(kwargs) or 1)
    assert deliver_email_delivery(delivery.pk) == "SENT"
    notification.refresh_from_db()
    assert Notification.objects.count() == count and len(sent) == 1
    assert resolve_notification_email_presentation(notification) == before


def test_email_supersession_does_not_rewrite_in_app_or_push_currentness(world, settings):
    from compass.notifications.current import notification_is_current

    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = POLICY
    notification, item = intent(world, EVENTS[6])
    mutate_source(item)
    assert notification_is_current(notification)
    assert resolve_notification_email_presentation(notification).suppress
    assert Notification.objects.filter(pk=notification.pk, source_id=item.pk).exists()


EXAMPLES = (
    ("group-registered", EVENTS[0]),
    ("group-registration-cancelled", EVENTS[1]),
    ("group-cancelled", EVENTS[2]),
    ("group-rescheduled", EVENTS[3]),
    ("good-moral-assisted", EVENTS[4]),
    ("good-moral-issued", EVENTS[5]),
    ("call-slip-issued", EVENTS[6]),
    ("call-slip-voided", EVENTS[7]),
    ("minimal-link", EVENTS[0]),
    ("missing-source", EVENTS[5]),
    ("unauthorized-recipient", EVENTS[6]),
    ("superseded-session", EVENTS[3]),
    ("long-sensitive-title-omitted", EVENTS[0]),
    ("legacy-void-minimal", EVENTS[7]),
)


@pytest.mark.parametrize("name,event", EXAMPLES)
def test_synthetic_operational_previews(world, settings, tmp_path, name, event):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "minimal" if name == "minimal-link" else POLICY
    notification, item = intent(
        world, event, recipient=world["other"] if name == "unauthorized-recipient" else None
    )
    if name == "missing-source":
        notification.source_id = uuid4()
        notification.target_id = notification.source_id
    elif name == "superseded-session":
        mutate_source(item)
    elif name == "long-sensitive-title-omitted":
        GroupSession.objects.filter(pk=item.pk).update(
            title=("SENSITIVE_LABEL_" * 17)[:255], venue_or_meeting_url=""
        )
    elif name == "legacy-void-minimal":
        CallSlip.objects.filter(pk=item.pk).update(issuance_mode="LEGACY_UNKNOWN")
    plan = resolve_notification_email_presentation(notification)
    output = Path(os.environ.get("COMPASS_OPERATIONAL_EMAIL_PREVIEW_DIR", str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{name}.json").write_text(
        json.dumps(
            {
                "event": event.value,
                "reason": plan.reason.value,
                "suppressed": plan.suppress,
                "synthetic": True,
                "transport": "not_sent",
            },
            indent=2,
        )
        + "\n"
    )
    if plan.suppress:
        assert name == "superseded-session"
        return
    message = render_notification_email(event, presentation=plan)
    for extension, body in (("html", message.html_body), ("txt", message.text_body)):
        (output / f"{name}.{extension}").write_text(
            "\n".join(line.rstrip() for line in body.splitlines()) + "\n"
        )
    assert "PRIVATE" not in message.subject + message.html_body + message.text_body
