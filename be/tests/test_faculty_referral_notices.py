"""Faculty receipt/closure producers, source currentness and trusted email links."""

from uuid import uuid4

import pytest
from django.core import mail
from django.db import transaction

from compass.accounts.models import Capability, Role, User, UserCapabilityOverride
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.notifications.current import notification_is_current
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_links import (
    NotificationEmailTarget,
    build_notification_email_link,
)
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import (
    EmailDelivery,
    Notification,
    NotificationPreference,
    PushDelivery,
)
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.notifications.services import list_my_notifications, unread_count_for
from compass.organization.models import FacultyAffiliation
from compass.referrals import faculty_rules as rules
from compass.referrals import services
from compass.referrals.notification_contract import create_faculty_notice, prepare_candidate_intent
from tests.faculty_referral_helpers import submit
from tests.referral_administration_helpers import make_world, transition

pytestmark = pytest.mark.django_db
EVENTS = ("RECEIVED_BY_GCO", "ADMINISTRATIVELY_CLOSED")


@pytest.fixture
def world(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)
    return make_world(monkeypatch)


def noticed(world, event):
    pk = submit(world)[0]["id"]
    transition(world, pk)
    if event == "ADMINISTRATIVELY_CLOSED":
        transition(world, pk, close=True)
    return Notification.objects.get(
        target_id=pk,
        event_code=(
            NotificationEvent.FACULTY_REFERRAL_RECEIVED
            if event == "RECEIVED_BY_GCO"
            else NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED
        ),
    )


@pytest.mark.parametrize("event", EVENTS)
def test_transition_creates_one_owner_only_notice_and_email_with_exact_link(world, event):
    notice = noticed(world, event)
    assert notice.recipient_id == world.faculty.pk
    assert notice.target_type == NotificationTargetType.FACULTY_REFERRAL
    assert notice.source_id == notice.target_id
    plan = resolve_notification_email_presentation(notice)
    rendered = render_notification_email(notice.event_code, presentation=plan)
    url = f"https://portal.example/portal/faculty/referrals/{notice.target_id}"
    assert url in rendered.text_body and f'href="{url}"' in rendered.html_body
    body = (
        notice.title + notice.message + rendered.subject + rendered.text_body + rendered.html_body
    )
    for private in (
        world.student.get_full_name(),
        world.student.email,
        world.student.institutional_id,
        world.counselor.get_full_name(),
        "Synthetic confidential reason",
        "SYNTHETIC-NOT-INSTITUTIONAL",
    ):
        assert private not in body
    for _ in range(2):
        assert create_faculty_notice(referral_id=notice.target_id, event=event).pk == notice.pk
    assert Notification.objects.filter(event_code=notice.event_code).count() == 1
    assert EmailDelivery.objects.filter(notification=notice).count() == 1
    assert not PushDelivery.objects.exists()
    for actor in (world.student, world.other_faculty, world.counselor, world.staff, world.admin):
        assert not list_my_notifications(actor=actor).items
        assert unread_count_for(actor=actor) == 0
    delivery = EmailDelivery.objects.get(notification=notice)
    assert deliver_email_delivery(delivery.pk) == "SENT"
    assert deliver_email_delivery(delivery.pk) == "skipped"
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [world.faculty.email]


@pytest.mark.parametrize("event", EVENTS)
def test_email_preference_retains_in_app_notice_without_external_delivery(world, event):
    NotificationPreference.objects.create(user=world.faculty, optional_email_enabled=False)
    notice = noticed(world, event)
    assert [row.pk for row in list_my_notifications(actor=world.faculty).items] == [notice.pk]
    assert unread_count_for(actor=world.faculty) == 1
    assert not EmailDelivery.objects.filter(notification=notice).exists()
    assert not PushDelivery.objects.exists()


@pytest.mark.parametrize("event", EVENTS)
def test_pending_email_honors_preference_disabled_after_enqueue(world, event):
    notice = noticed(world, event)
    NotificationPreference.objects.create(user=world.faculty, optional_email_enabled=False)
    delivery = EmailDelivery.objects.get(notification=notice)
    assert deliver_email_delivery(delivery.pk) == "CANCELLED"
    assert not mail.outbox
    assert [row.pk for row in list_my_notifications(actor=world.faculty).items] == [notice.pk]


def test_received_notice_is_superseded_by_closure_and_void_hides_both(world):
    received = noticed(world, "RECEIVED_BY_GCO")
    transition(world, received.target_id, close=True)
    closed = Notification.objects.get(
        event_code=NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED
    )
    assert not notification_is_current(received) and notification_is_current(closed)
    assert [row.pk for row in list_my_notifications(actor=world.faculty).items] == [closed.pk]
    assert unread_count_for(actor=world.faculty) == 1
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=received).pk) == "skipped"
    services.void_referral(
        actor=world.counselor,
        referral_id=closed.target_id,
        reason="Synthetic void",
        context=AuditContext.user(world.counselor),
    )
    for event in EVENTS:
        assert create_faculty_notice(referral_id=closed.target_id, event=event) is None
    assert not notification_is_current(closed)
    assert not list_my_notifications(actor=world.faculty).items
    assert unread_count_for(actor=world.faculty) == 0
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=closed).pk) == "skipped"
    assert not mail.outbox


@pytest.mark.parametrize("mutation", ["inactive", "role", "capability", "affiliation", "campus"])
@pytest.mark.parametrize("event", EVENTS)
def test_current_owner_authority_loss_suppresses_notice_and_pending_email(
    world, event, mutation, monkeypatch
):
    notice = noticed(world, event)
    if mutation == "inactive":
        User.objects.filter(pk=world.faculty.pk).update(is_active=False)
    elif mutation == "role":
        User.objects.filter(pk=world.faculty.pk).update(role=Role.objects.get(code="IT_ADMIN"))
    elif mutation == "capability":
        UserCapabilityOverride.objects.create(
            user=world.faculty,
            capability=Capability.objects.get(code="referrals.view_submitted_self"),
            effect="REVOKE",
        )
    elif mutation == "affiliation":
        FacultyAffiliation.objects.filter(faculty=world.faculty).delete()
    elif mutation == "campus":
        campus = world.cas.campus
        campus.is_active = False
        campus.save(update_fields=["is_active"])
    assert not notification_is_current(notice)
    assert not list_my_notifications(actor=world.faculty).items
    assert unread_count_for(actor=world.faculty) == 0
    assert create_faculty_notice(referral_id=notice.target_id, event=event) is None
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk) == "skipped"
    assert not mail.outbox


def test_invalid_or_void_transitions_never_produce_notices(world):
    pk = submit(world)[0]["id"]
    for event in (*EVENTS, "VOIDED", "UNKNOWN"):
        assert create_faculty_notice(referral_id=pk, event=event) is None
    with pytest.raises(rules.AdministrativeReferralError):
        transition(world, pk, close=True, expected_version=1)
    with pytest.raises(rules.AdministrativeReferralError):
        transition(world, pk, expected_version=0)
    services.void_referral(
        actor=world.counselor,
        referral_id=pk,
        reason="Synthetic",
        context=AuditContext.user(world.counselor),
    )
    with pytest.raises(rules.AdministrativeReferralError):
        transition(world, pk)
    assert not Notification.objects.exists() and not EmailDelivery.objects.exists()


def test_transition_rollback_removes_notice_delivery_and_audit(world):
    pk = submit(world)[0]["id"]
    with pytest.raises(RuntimeError), transaction.atomic():
        transition(world, pk)
        assert Notification.objects.count() == 1 and EmailDelivery.objects.count() == 1
        raise RuntimeError("Synthetic rollback")
    assert not Notification.objects.exists() and not EmailDelivery.objects.exists()
    assert not AuditEvent.objects.filter(action="referral.acknowledged").exists()
    assert create_faculty_notice(referral_id=pk, event="RECEIVED_BY_GCO") is None


@pytest.mark.parametrize("defect", ["source", "target", "recipient", "event"])
def test_forged_notice_cannot_gain_source_access_or_email_link(world, defect):
    notice = noticed(world, "RECEIVED_BY_GCO")
    if defect == "source":
        notice.source_id = uuid4()
    elif defect == "target":
        notice.target_type = NotificationTargetType.APPOINTMENT
    elif defect == "recipient":
        notice.recipient = world.other_faculty
    else:
        notice.event_code = NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED
    assert not notification_is_current(notice)
    assert resolve_notification_email_presentation(notice).suppress


@pytest.mark.parametrize("change", ["origin", "email", "preference", "inactive", "closure"])
def test_final_revalidation_cancels_when_notice_authority_changes_after_render(
    world, settings, monkeypatch, change
):
    from compass.notifications import delivery as worker

    notice = noticed(world, "RECEIVED_BY_GCO")
    original = worker.render_notification_email

    def rendered_then_changed(*args, **kwargs):
        rendered = original(*args, **kwargs)
        if change == "origin":
            settings.COMPASS_PORTAL_ORIGIN = "https://changed.example"
        elif change == "email":
            User.objects.filter(pk=world.faculty.pk).update(email="changed@example.test")
        elif change == "preference":
            NotificationPreference.objects.create(user=world.faculty, optional_email_enabled=False)
        elif change == "inactive":
            User.objects.filter(pk=world.faculty.pk).update(is_active=False)
        else:
            transition(world, notice.target_id, close=True)
        return rendered

    monkeypatch.setattr(worker, "render_notification_email", rendered_then_changed)
    assert deliver_email_delivery(EmailDelivery.objects.get(notification=notice).pk) == "CANCELLED"
    assert not mail.outbox


@pytest.mark.parametrize("origin", ["", "https://portal.example/path", "javascript:PRIVATE"])
def test_invalid_origin_keeps_local_generic_notice_without_untrusted_link(world, settings, origin):
    notice = noticed(world, "RECEIVED_BY_GCO")
    settings.COMPASS_PORTAL_ORIGIN = origin
    plan = resolve_notification_email_presentation(notice)
    message = render_notification_email(notice.event_code, presentation=plan)
    assert "href=" not in message.html_body and "PRIVATE" not in message.text_body


def test_closed_target_uses_faculty_page_and_rejects_arbitrary_identifiers(world):
    notice = noticed(world, "RECEIVED_BY_GCO")
    intent = prepare_candidate_intent(referral_id=notice.target_id, event="RECEIVED_BY_GCO")
    assert (
        build_notification_email_link(
            NotificationEmailTarget("FACULTY_REFERRAL", notice.target_id)
        ).url
        == "https://portal.example" + intent.route
    )
    assert (
        build_notification_email_link(
            NotificationEmailTarget("FACULTY_REFERRAL", "//evil.test/path")
        ).url
        is None
    )
    assert (
        build_notification_email_link(NotificationEmailTarget("FACULTY_REFERRAL", None)).url is None
    )
