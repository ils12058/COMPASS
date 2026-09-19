from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.models import AuditEvent
from compass.authentication.crypto import encrypt_totp_secret
from compass.authentication.models import (
    AuthSession,
    EmailChangeRequest,
    EmailOTPChallenge,
    LoginChallenge,
    TOTPFactor,
    TrustedSession,
)
from compass.authentication.sessions import (
    create_auth_session,
    create_login_challenge,
    create_trusted_session,
)
from compass.authentication.tasks import deliver_email_change_security_alert
from compass.common.rate_limit import RateLimitResult


class AllowLimiter:
    def consume_with_failure_policy(self, policy, subject):
        return RateLimitResult(
            allowed=True,
            count=1,
            limit=policy.limit,
            remaining=policy.limit - 1,
            retry_after_seconds=1,
        )


@pytest.fixture(autouse=True)
def configure_security(settings, monkeypatch):
    settings.AUTH_TOTP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.AUTH_TURNSTILE_EMAIL_OTP_REQUIRED = False
    monkeypatch.setattr(
        "compass.authentication.abuse.RedisRateLimiter.from_settings",
        lambda: AllowLimiter(),
    )
    monkeypatch.setattr(
        "compass.authentication.email_otp._new_code",
        lambda: "123456",
    )
    monkeypatch.setattr(
        "compass.authentication.tasks.deliver_email_otp.delay",
        lambda *args, **kwargs: None,
    )


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    verified: bool = True,
    institutional_id: str | None = None,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Email",
        last_name="Change",
        institutional_id=institutional_id,
    )
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
    return user


def auth_client(user: User, *, recent_mfa: bool = False) -> tuple[Client, AuthSession]:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client, issued.session


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def post(client: Client, path: str, payload: dict[str, object]):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_non_totp_email_change_requires_current_mailbox_then_new_mailbox_and_revokes_auth_state():
    sync_policy()
    user = make_user(
        "old-address@example.edu",
        institutional_id="UCN-EMAIL-001",
    )
    client, current_session = auth_client(user)
    other_session = create_auth_session(user).session
    trusted = create_trusted_session(user).session
    login_challenge = create_login_challenge(
        user,
        allowed_methods=["totp"],
        trust_browser=False,
    ).challenge

    skipped = post(
        client,
        "/api/v1/auth/email-change/request",
        {"new_email": "new-address@example.edu"},
    )
    assert skipped.status_code == 422
    user.refresh_from_db()
    assert user.email == "old-address@example.edu"

    current_proof = post(
        client,
        "/api/v1/auth/email-change/security-challenge",
        {},
    )
    assert current_proof.status_code == 200
    current_challenge_id = current_proof.json()["challenge_id"]

    requested = post(
        client,
        "/api/v1/auth/email-change/request",
        {
            "new_email": " NEW-ADDRESS@example.edu ",
            "current_email_challenge_id": current_challenge_id,
            "current_email_code": "123456",
        },
    )
    assert requested.status_code == 200
    body = requested.json()
    pending = EmailChangeRequest.objects.get(pk=body["request_id"])
    new_challenge = EmailOTPChallenge.objects.get(pk=body["challenge_id"])
    assert pending.new_email == "new-address@example.edu"
    assert pending.current_email_snapshot == "old-address@example.edu"
    assert pending.current_email_authorized_at is not None
    assert new_challenge.email == "new-address@example.edu"
    assert new_challenge.code_hash != "123456"
    user.refresh_from_db()
    assert user.email == "old-address@example.edu"

    with patch(
        "compass.authentication.email_change._safe_enqueue_old_email_alert"
    ) as enqueue_alert:
        confirmed = post(
            client,
            "/api/v1/auth/email-change/confirm",
            {"code": "123456"},
        )
    assert confirmed.status_code == 200
    assert confirmed.json() == {
        "changed": True,
        "reauthentication_required": True,
    }
    enqueue_alert.assert_called_once_with(str(pending.pk))

    user.refresh_from_db()
    assert user.email == "new-address@example.edu"
    assert user.email_verified_at is not None

    for model, pk, field in (
        (AuthSession, current_session.pk, "revoked_at"),
        (AuthSession, other_session.pk, "revoked_at"),
        (TrustedSession, trusted.pk, "revoked_at"),
        (LoginChallenge, login_challenge.pk, "consumed_at"),
    ):
        record = model.objects.get(pk=pk)
        assert getattr(record, field) is not None

    assert (
        "compass_session" not in confirmed.cookies or not confirmed.cookies["compass_session"].value
    )
    changed_event = AuditEvent.objects.get(action="auth.email.changed", actor_user=user)
    serialized = str(changed_event.metadata)
    assert "old-address@example.edu" not in serialized
    assert "new-address@example.edu" not in serialized


@pytest.mark.django_db
def test_invalid_or_replayed_new_email_otp_never_commits():
    sync_policy()
    user = make_user("otp-old@example.edu", institutional_id="UCN-EMAIL-002")
    client, _session = auth_client(user)

    proof = post(client, "/api/v1/auth/email-change/security-challenge", {})
    requested = post(
        client,
        "/api/v1/auth/email-change/request",
        {
            "new_email": "otp-new@example.edu",
            "current_email_challenge_id": proof.json()["challenge_id"],
            "current_email_code": "123456",
        },
    )
    challenge = EmailOTPChallenge.objects.get(pk=requested.json()["challenge_id"])

    wrong = post(
        client,
        "/api/v1/auth/email-change/confirm",
        {"code": "000000"},
    )
    assert wrong.status_code == 422
    user.refresh_from_db()
    challenge.refresh_from_db()
    assert user.email == "otp-old@example.edu"
    assert challenge.failed_attempt_count == 1
    assert challenge.consumed_at is None

    with patch("compass.authentication.email_change._safe_enqueue_old_email_alert"):
        success = post(client, "/api/v1/auth/email-change/confirm", {"code": "123456"})
    assert success.status_code == 200

    replacement_client, _replacement_session = auth_client(user)
    replay = post(
        replacement_client,
        "/api/v1/auth/email-change/confirm",
        {
            "request_id": requested.json()["request_id"],
            "challenge_id": requested.json()["challenge_id"],
            "code": "123456",
        },
    )
    assert replay.status_code in {404, 422}


@pytest.mark.django_db
def test_totp_accounts_require_recent_mfa_and_email_otp_cannot_substitute(settings):
    sync_policy()
    user = make_user("totp-old@example.edu", institutional_id="UCN-TOTP-001")
    TOTPFactor.objects.create(
        user=user,
        encrypted_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
        confirmed_at=timezone.now(),
    )

    stale_client, _stale = auth_client(user, recent_mfa=False)
    current_email_fallback = post(
        stale_client,
        "/api/v1/auth/email-change/security-challenge",
        {},
    )
    assert current_email_fallback.status_code == 403
    assert current_email_fallback.json()["error"]["code"] == "totp_step_up_required"

    stale_request = post(
        stale_client,
        "/api/v1/auth/email-change/request",
        {"new_email": "totp-new@example.edu"},
    )
    assert stale_request.status_code == 403
    assert stale_request.json()["error"]["code"] == "recent_mfa_required"

    recent_client, _recent = auth_client(user, recent_mfa=True)
    allowed = post(
        recent_client,
        "/api/v1/auth/email-change/request",
        {"new_email": "totp-new@example.edu"},
    )
    assert allowed.status_code == 200
    user.refresh_from_db()
    assert user.email == "totp-old@example.edu"

    settings.AUTH_MFA_REQUIRED_ROLE_CODES = {"STUDENT"}
    factor = TOTPFactor.objects.get(user=user)
    factor.disabled_at = timezone.now()
    factor.save(update_fields=["disabled_at"])

    required_client, _required = auth_client(user, recent_mfa=True)
    cannot_substitute = post(
        required_client,
        "/api/v1/auth/email-change/request",
        {
            "new_email": "cannot-substitute@example.edu",
        },
    )
    assert cannot_substitute.status_code == 403
    assert cannot_substitute.json()["error"]["code"] == "totp_step_up_required"


@pytest.mark.django_db
def test_admin_can_only_stage_email_change_and_target_new_mailbox_must_confirm():
    sync_policy()
    admin = make_user(
        "email-admin@example.edu",
        role="IT_ADMIN",
        institutional_id="EMP-EMAIL-001",
    )
    target = make_user(
        "managed-old@example.edu",
        institutional_id="UCN-MANAGED-001",
    )
    admin_client, _admin_session = auth_client(admin, recent_mfa=True)

    staged = post(
        admin_client,
        f"/api/v1/accounts/{target.pk}/email-change",
        {"new_email": "managed-new@example.edu"},
    )
    assert staged.status_code == 200
    target.refresh_from_db()
    assert target.email == "managed-old@example.edu"

    target_client, _target_session = auth_client(target)
    with patch("compass.authentication.email_change._safe_enqueue_old_email_alert"):
        confirmed = post(
            target_client,
            "/api/v1/auth/email-change/confirm",
            {"code": "123456"},
        )
    assert confirmed.status_code == 200
    target.refresh_from_db()
    assert target.email == "managed-new@example.edu"


@pytest.mark.django_db
def test_old_email_security_alert_uses_previous_destination_snapshot():
    sync_policy()
    user = make_user("alert-old@example.edu", institutional_id="UCN-ALERT-001")
    client, _session = auth_client(user)
    proof = post(client, "/api/v1/auth/email-change/security-challenge", {})
    requested = post(
        client,
        "/api/v1/auth/email-change/request",
        {
            "new_email": "alert-new@example.edu",
            "current_email_challenge_id": proof.json()["challenge_id"],
            "current_email_code": "123456",
        },
    )
    with patch("compass.authentication.email_change._safe_enqueue_old_email_alert"):
        confirmed = post(client, "/api/v1/auth/email-change/confirm", {"code": "123456"})
    assert confirmed.status_code == 200

    pending = EmailChangeRequest.objects.get(pk=requested.json()["request_id"])
    with patch(
        "compass.authentication.tasks.Mailer.send",
        return_value=1,
    ) as send:
        delivered = deliver_email_change_security_alert.run(str(pending.pk))
    assert delivered == 1
    assert send.call_args.kwargs["recipients"] == "alert-old@example.edu"
    assert "alert-new@example.edu" not in send.call_args.kwargs["body"]
    pending.refresh_from_db()
    assert pending.old_email_alert_sent_at is not None
    assert pending.old_email_alert_attempt_count == 1


@pytest.mark.django_db
def test_same_and_duplicate_new_email_are_rejected_without_mutation():
    sync_policy()
    user = make_user("same@example.edu", institutional_id="UCN-SAME-001")
    make_user("occupied@example.edu", institutional_id="UCN-SAME-002")
    client, _session = auth_client(user)

    proof = post(client, "/api/v1/auth/email-change/security-challenge", {})
    same = post(
        client,
        "/api/v1/auth/email-change/request",
        {
            "new_email": "SAME@example.edu",
            "current_email_challenge_id": proof.json()["challenge_id"],
            "current_email_code": "123456",
        },
    )
    assert same.status_code == 422

    proof = post(client, "/api/v1/auth/email-change/security-challenge", {})
    occupied = post(
        client,
        "/api/v1/auth/email-change/request",
        {
            "new_email": "occupied@example.edu",
            "current_email_challenge_id": proof.json()["challenge_id"],
            "current_email_code": "123456",
        },
    )
    assert occupied.status_code == 409
    user.refresh_from_db()
    assert user.email == "same@example.edu"
