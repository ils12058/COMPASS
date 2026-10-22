"""Synthetic HTTP/transport joins for NOTIF-04; no SMTP or live actors."""

import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from django.core import mail
from django.utils import timezone

from compass.accounts.models import Capability, Designation, UserCapabilityOverride, UserDesignation
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.email_disclosure import APPROVED_EMAIL_EVENTS
from compass.notifications.email_links import NotificationEmailTarget, notification_email_route
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus
from compass.notifications.policy import NotificationEvent
from compass.notifications.push_policy import push_body_for
from tests.test_appointment_email_presentation import case, notice  # noqa: F401
from tests.test_appointments import make_user
from tests.test_notifications import auth_client
from tests.test_operational_email_presentation import intent, world  # noqa: F401


@pytest.fixture(autouse=True)
def local_transport(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "minimal"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


def event_notice(request, event):
    if event.value.startswith("appointment."):
        return notice(request.getfixturevalue("case"), event)
    return intent(request.getfixturevalue("world"), event)[0]


@pytest.mark.django_db
@pytest.mark.parametrize("event", sorted(APPROVED_EMAIL_EVENTS))
@pytest.mark.parametrize("policy", ["minimal", "operational_v1"])
def test_fifteen_events_join_email_http_read_and_push(request, settings, event, policy):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = policy
    notification = event_notice(request, event)
    owner = auth_client(notification.recipient)
    listed = owner.get("/api/v1/notifications").json()["items"]
    assert [item["id"] for item in listed] == [str(notification.pk)]
    row = listed[0]
    assert row["event_code"] == event
    assert row["target_id"] == str(notification.target_id)
    assert owner.get("/api/v1/notifications/unread-count").json()["unread_count"] == 1
    plan = resolve_notification_email_presentation(notification)
    rendered = render_notification_email(event, presentation=plan)
    route = notification_email_route(
        NotificationEmailTarget(notification.target_type, notification.target_id)
    )
    if plan.target:
        assert f"https://portal.example{route}" in rendered.text_body
        assert f"https://portal.example{route}" in rendered.html_body
    assert "PRIVATE" not in row["message"] + row["title"]
    assert str(notification.target_id) not in (push_body_for(event) or "")
    assert "PRIVATE" not in (push_body_for(event) or "")
    delivery = EmailDelivery.objects.get(notification=notification)
    assert deliver_email_delivery(delivery.pk) == EmailDeliveryStatus.SENT
    assert len(mail.outbox) == 1
    # Transport handoff never marks an in-app message read.
    assert owner.get("/api/v1/notifications/unread-count").json()["unread_count"] == 1
    marked = owner.patch(f"/api/v1/notifications/{notification.pk}/read")
    assert marked.status_code == 200 and marked.json()["is_read"] is True
    assert owner.get("/api/v1/notifications/unread-count").json()["unread_count"] == 0
    assert owner.get("/api/v1/notifications").json()["items"][0]["target_id"] == row["target_id"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "actor_kind",
    ["student", "assigned", "former", "head", "gss", "it", "unrelated", "inactive", "revoked"],
)
def test_actual_appointment_endpoint_rechecks_roles_despite_notification_ownership(
    request, settings, actor_kind
):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "operational_v1"
    appointment_case = request.getfixturevalue("case")
    student, provider, previous, appointment = appointment_case
    role = {"gss": "GUIDANCE_SERVICES_STAFF", "it": "IT_ADMIN"}.get(actor_kind, "COUNSELOR")
    actors = {"student": student, "assigned": provider, "former": previous}
    actor = actors.get(actor_kind) or make_user(f"cross-{actor_kind}@example.test", role)
    if actor_kind == "head":
        UserDesignation.objects.create(
            user=actor, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
        )
    if actor_kind == "revoked":
        actor = provider
        for code in ("appointments.view_self", "appointments.manage"):
            UserCapabilityOverride.objects.create(
                user=actor, capability=Capability.objects.get(code=code), effect="REVOKE"
            )
    client = auth_client(actor)
    # Even a synthetic notice owned by this actor is not an access grant.
    notification = notice(
        appointment_case, NotificationEvent.APPOINTMENT_REASSIGNED, recipient=actor
    )
    if actor_kind == "inactive":
        type(actor).objects.filter(pk=actor.pk).update(is_active=False)
    response = client.get(f"/api/v1/appointments/{appointment.pk}")
    if actor_kind in {"student", "assigned"}:
        assert response.status_code == 200
        assert response.json()["id"] == str(appointment.pk)
    else:
        assert response.status_code in {401, 403, 404}
        assert appointment.reference_code not in response.content.decode()
        plan = resolve_notification_email_presentation(notification)
        assert plan.target is None and plan.appointment_facts is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event,path",
    [
        (NotificationEvent.GOOD_MORAL_ISSUED, "/api/v1/good-moral/me/{id}"),
        (NotificationEvent.CALL_SLIP_VOIDED, "/api/v1/call-slips/me/{id}"),
    ],
)
def test_other_student_cannot_read_notice_or_record(request, event, path):
    operational_world = request.getfixturevalue("world")
    notification, item = intent(operational_world, event)
    owner, other = (
        auth_client(operational_world["student"]),
        auth_client(operational_world["other"]),
    )
    assert owner.get(path.format(id=item.pk)).status_code == 200
    assert other.get(path.format(id=item.pk)).status_code == 404
    assert other.get("/api/v1/notifications").json()["items"] == []
    assert other.get("/api/v1/notifications/unread-count").json()["unread_count"] == 0
    assert other.patch(f"/api/v1/notifications/{notification.pk}/read").status_code == 404
    notification.refresh_from_db()
    assert notification.read_at is None


@pytest.mark.django_db
@pytest.mark.parametrize("family", ["appointment", "call_slip", "group"])
def test_suppressed_external_notice_keeps_truthful_in_app_history(request, settings, family):
    settings.COMPASS_EMAIL_DISCLOSURE_POLICY = "operational_v1"
    event = {
        "appointment": NotificationEvent.APPOINTMENT_SCHEDULED,
        "call_slip": NotificationEvent.CALL_SLIP_ISSUED,
        "group": NotificationEvent.GROUP_SESSION_RESCHEDULED,
    }[family]
    notification = event_notice(request, event)
    if family == "appointment":
        item = request.getfixturevalue("case")[3]
        item.status, item.cancelled_at = "CANCELLED", timezone.now()
    elif family == "call_slip":
        from compass.call_slips.models import CallSlip

        item = CallSlip.objects.get(pk=notification.target_id)
        item.voided_at, item.void_reason = timezone.now(), "PRIVATE"
    else:
        from compass.group_sessions.models import GroupSession

        item = GroupSession.objects.get(pk=notification.target_id)
        item.schedule_revision += 1
    item.save()
    delivery = EmailDelivery.objects.get(notification=notification)
    outcome = deliver_email_delivery(delivery.pk)
    assert outcome in {EmailDeliveryStatus.CANCELLED, "skipped"}
    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.CANCELLED
    row = auth_client(notification.recipient).get("/api/v1/notifications").json()["items"][0]
    assert row["id"] == str(notification.pk)
    if family == "group":
        assert row["is_current"] is False
        assert "changed since" in row["message"]
    assert mail.outbox == []


def test_catalog_has_thirty_events_and_only_fifteen_rich_candidates():
    assert len(NotificationEvent) == 30
    assert len(APPROVED_EMAIL_EVENTS) == 15
    assert push_body_for("unrecognized.event") is None
    assert notification_email_route(NotificationEmailTarget("APPOINTMENT", str(uuid4())))


def test_closed_email_routes_match_shared_frontend_contract():
    path = Path(__file__).resolve().parents[2] / "fe/tests/support/notification-route-contract.json"
    rows = json.loads(path.read_text())
    assert len(rows) == 22
    for row in rows:
        assert (
            notification_email_route(NotificationEmailTarget(row["target_type"], row["target_id"]))
            == row["route"]
        )


@pytest.mark.django_db
def test_group_registration_ownership_and_roster_are_independent_of_notice(request):
    operational_world = request.getfixturevalue("world")
    notification, item = intent(operational_world, NotificationEvent.GROUP_SESSION_REGISTERED)
    owner = auth_client(operational_world["student"])
    other = auth_client(operational_world["other"])
    own_registrations = owner.get("/api/v1/group-sessions/me/registrations")
    assert own_registrations.status_code == 200
    assert str(item.pk) in own_registrations.content.decode()
    assert other.get("/api/v1/group-sessions/me/registrations").json() == []
    denied = other.get(f"/api/v1/group-sessions/{item.pk}/registrations")
    assert denied.status_code in {403, 404}
    assert str(notification.recipient_id) not in denied.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["verify", "required_setup"])
def test_expired_mfa_challenge_never_creates_record_access(request, settings, monkeypatch, kind):
    from cryptography.fernet import Fernet
    from django.test import Client

    from compass.authentication.crypto import encrypt_totp_secret
    from compass.authentication.models import AuthSession, LoginChallenge, TOTPFactor
    from tests.test_authentication import AllowLimiter, csrf_headers, login, post_json

    settings.AUTH_TOTP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.AUTH_MFA_REQUIRED_ROLE_CODES = ["COUNSELOR"]
    monkeypatch.setattr(
        "compass.authentication.abuse.RedisRateLimiter.from_settings", lambda: AllowLimiter()
    )
    appointment_case = request.getfixturevalue("case")
    actor = appointment_case[0] if kind == "verify" else appointment_case[1]
    if kind == "verify":
        TOTPFactor.objects.create(
            user=actor,
            encrypted_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            confirmed_at=timezone.now(),
        )
    client = Client()
    challenged = login(client, email=actor.email, password="a-test-password")
    assert challenged.status_code == (200 if kind == "verify" else 403)
    assert not AuthSession.objects.filter(user=actor).exists()
    now = timezone.now()
    LoginChallenge.objects.filter(user=actor).update(
        created_at=now - timedelta(hours=1), expires_at=now - timedelta(minutes=1)
    )
    endpoint = (
        "/api/v1/auth/mfa/verify" if kind == "verify" else "/api/v1/auth/mfa/totp/bootstrap/setup"
    )
    response = post_json(
        client,
        endpoint,
        {"method": "totp", "code": "123456"} if kind == "verify" else {},
        headers=csrf_headers(client),
    )
    assert response.status_code == (400 if kind == "verify" else 403)
    assert response.json()["error"]["code"] == (
        "mfa_failed" if kind == "verify" else "mfa_enrollment_challenge_invalid"
    )
    assert not AuthSession.objects.filter(user=actor).exists()
    denied = client.get(f"/api/v1/appointments/{appointment_case[3].pk}")
    assert denied.status_code == 401
    assert appointment_case[3].reference_code not in denied.content.decode()
