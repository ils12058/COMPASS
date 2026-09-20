from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.models import AuditEvent
from compass.authentication.crypto import encrypt_totp_secret
from compass.authentication.models import (
    AuthSession,
    EmailOTPChallenge,
    EmailOTPPurpose,
    LoginChallenge,
    RecoveryCode,
    TOTPFactor,
    TrustedSession,
)
from compass.authentication.sessions import (
    create_auth_session,
    create_login_challenge,
    create_trusted_session,
)
from compass.notifications.models import Notification


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, *, role: str = "STUDENT", password: str = "old-test-password") -> User:
    return User.objects.create_user(
        email=email,
        password=password,
        role=Role.objects.get(code=role),
        first_name="Password",
        last_name="User",
    )


def auth_client(user: User, *, recent_mfa: bool = False):
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


def change(client: Client, payload: dict[str, object]):
    return client.post(
        "/api/v1/auth/password/change",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


def login(email: str, password: str):
    client = Client()
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps(
            {
                "email": email,
                "password": password,
                "trust_browser": False,
            }
        ),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_password_change_requires_authentication_and_active_account():
    sync_policy()
    anonymous = Client()
    denied = change(
        anonymous,
        {"current_password": "old-test-password", "new_password": "A-new-password-2026!"},
    )
    assert denied.status_code == 401

    user = make_user("inactive-change@example.edu")
    client, _session = auth_client(user)
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])

    inactive = change(
        client,
        {"current_password": "old-test-password", "new_password": "A-new-password-2026!"},
    )
    assert inactive.status_code == 401


@pytest.mark.django_db
def test_non_totp_password_change_requires_current_password_and_preserves_only_current_session(
    monkeypatch,
):
    sync_policy()
    user = make_user("password-change@example.edu")
    client, current_session = auth_client(user)
    other_session = create_auth_session(user).session
    trusted = create_trusted_session(user).session
    login_challenge = create_login_challenge(
        user,
        allowed_methods=["totp"],
        trust_browser=False,
    ).challenge
    now = timezone.now()
    recovery_otp = EmailOTPChallenge.objects.create(
        user=user,
        email=user.email,
        purpose=EmailOTPPurpose.RECOVERY,
        code_hash=make_password("123456"),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        last_sent_at=now,
    )
    verification_otp = EmailOTPChallenge.objects.create(
        user=user,
        email=user.email,
        purpose=EmailOTPPurpose.EMAIL_VERIFICATION,
        code_hash=make_password("654321"),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        last_sent_at=now,
    )

    rate_limit_calls: list[tuple[str, object]] = []

    def record_rate_limit(operation, **kwargs):
        rate_limit_calls.append((operation, kwargs.get("user_id")))

    monkeypatch.setattr(
        "compass.authentication.password_change.check_auth_rate_limit",
        record_rate_limit,
    )

    missing = change(client, {"new_password": "A-new-password-2026!"})
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "password_change_authentication_failed"

    wrong = change(
        client,
        {"current_password": "wrong-password", "new_password": "A-new-password-2026!"},
    )
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "password_change_authentication_failed"
    user.refresh_from_db()
    assert user.check_password("old-test-password")
    assert rate_limit_calls == [
        ("password_change", user.pk),
        ("password_change", user.pk),
    ]

    same = change(
        client,
        {"current_password": "old-test-password", "new_password": "old-test-password"},
    )
    assert same.status_code == 422
    assert same.json()["error"]["code"] == "password_policy_failed"

    changed = change(
        client,
        {"current_password": "old-test-password", "new_password": "A-new-password-2026!"},
    )
    assert changed.status_code == 200
    assert changed.json() == {"changed": True}

    user.refresh_from_db()
    assert not user.check_password("old-test-password")
    assert user.check_password("A-new-password-2026!")

    assert client.get("/api/v1/auth/session").status_code == 200
    current_session.refresh_from_db()
    other_session.refresh_from_db()
    trusted.refresh_from_db()
    login_challenge.refresh_from_db()
    recovery_otp.refresh_from_db()
    verification_otp.refresh_from_db()
    assert current_session.revoked_at is None
    assert other_session.revoked_at is not None
    assert trusted.revoked_at is not None
    assert login_challenge.consumed_at is not None
    assert recovery_otp.consumed_at is not None
    assert verification_otp.consumed_at is not None

    event = AuditEvent.objects.get(action="auth.password.changed", actor_user=user)
    assert event.metadata == {"method": "current_password"}
    serialized = str(event.metadata)
    assert "old-test-password" not in serialized
    assert "A-new-password-2026!" not in serialized
    notification = Notification.objects.get(
        recipient=user,
        event_code="security.password.changed",
        source_type="audit_event",
        source_id=event.pk,
    )
    assert notification.policy == "MANDATORY_SECURITY"

    assert login(user.email, "old-test-password").status_code == 401
    assert login(user.email, "A-new-password-2026!").status_code == 200


@pytest.mark.django_db
def test_totp_password_change_requires_recent_mfa_and_preserves_mfa_state():
    sync_policy()
    user = make_user("totp-change@example.edu")
    now = timezone.now()
    factor = TOTPFactor.objects.create(
        user=user,
        encrypted_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
        confirmed_at=now,
    )
    recovery = RecoveryCode.objects.create(
        user=user,
        code_hash=make_password("ABCDEFGHJKLM"),
    )

    stale_client, stale_session = auth_client(user, recent_mfa=False)
    stale = change(
        stale_client,
        {"current_password": "old-test-password", "new_password": "A-new-password-2026!"},
    )
    assert stale.status_code == 403
    assert stale.json()["error"]["code"] == "recent_mfa_required"

    stale_session.refresh_from_db()
    assert stale_session.revoked_at is None

    recent_client, recent_session = auth_client(user, recent_mfa=True)
    other_session = create_auth_session(user).session
    changed = change(
        recent_client,
        {
            "current_password": "intentionally-not-used",
            "new_password": "A-new-password-2026!",
        },
    )
    assert changed.status_code == 200

    recent_session.refresh_from_db()
    other_session.refresh_from_db()
    factor.refresh_from_db()
    recovery.refresh_from_db()
    assert recent_session.revoked_at is None
    assert other_session.revoked_at is not None
    assert factor.disabled_at is None
    assert factor.confirmed_at is not None
    assert recovery.used_at is None
    assert recovery.invalidated_at is None
    assert AuditEvent.objects.get(
        action="auth.password.changed",
        actor_user=user,
    ).metadata == {"method": "recent_mfa"}


@pytest.mark.django_db
@override_settings(AUTH_MFA_REQUIRED_ROLE_CODES=["STUDENT"])
def test_role_required_mfa_without_totp_fails_closed():
    sync_policy()
    user = make_user("required-mfa-change@example.edu")
    client, _session = auth_client(user, recent_mfa=True)

    response = change(
        client,
        {"current_password": "old-test-password", "new_password": "A-new-password-2026!"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "mfa_setup_required"
    user.refresh_from_db()
    assert user.check_password("old-test-password")
    assert not AuditEvent.objects.filter(action="auth.password.changed", actor_user=user).exists()
