"""Recent-MFA (step-up) policy: which actions keep it, and what an account without TOTP is told.

* No active TOTP factor: a retained action reports ``mfa_setup_required``; no code challenge exists.
* Active TOTP, stale verification: ``recent_mfa_required``; the account can verify and retry.
* Active TOTP, recent verification: the action proceeds.
* Routine operational work does not need step-up at all.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.authentication.crypto import encrypt_totp_secret
from compass.authentication.models import TOTPFactor
from compass.authentication.sessions import (
    MFASetupRequired,
    RecentMFARequired,
    create_auth_session,
    require_recent_mfa,
)


@pytest.fixture(autouse=True)
def totp_key(settings):
    settings.AUTH_TOTP_ENCRYPTION_KEY = Fernet.generate_key().decode()


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str = "IT_ADMIN") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name="Step",
        last_name="Up",
    )


def make_dpo(email: str) -> User:
    user = make_user(email, "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(user=user, designation=Designation.objects.get(code="DPO"))
    return user


def enable_totp(user: User, *, confirmed: bool = True, disabled: bool = False) -> TOTPFactor:
    now = timezone.now()
    return TOTPFactor.objects.create(
        user=user,
        encrypted_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
        created_at=now,
        confirmed_at=now if confirmed else None,
        disabled_at=now if disabled else None,
    )


def client_for(user: User, *, recent: bool) -> Client:
    now = timezone.now()
    issued = create_auth_session(user, now=now, mfa_verified_at=now if recent else None)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def send(client: Client, method: str, path: str, payload: dict[str, object] | None = None):
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return getattr(client, method)(
        path,
        data=json.dumps(payload or {}, default=str),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )


def error_code(response) -> str:
    return response.json()["error"]["code"]


# Shared helper semantics


@pytest.mark.django_db
def test_require_recent_mfa_distinguishes_missing_authenticator_from_stale_verification():
    sync_policy()
    without_totp = make_user("no-totp@example.edu")
    with_totp = make_user("with-totp@example.edu")
    enable_totp(with_totp)
    now = timezone.now()

    with pytest.raises(MFASetupRequired):
        require_recent_mfa(create_auth_session(without_totp, now=now).session, now=now)

    stale = create_auth_session(with_totp, now=now).session
    with pytest.raises(RecentMFARequired) as raised:
        require_recent_mfa(stale, now=now)
    assert not isinstance(raised.value, MFASetupRequired)

    recent = create_auth_session(with_totp, now=now, mfa_verified_at=now).session
    require_recent_mfa(recent, now=now)

    # The recent window is unchanged: a verification older than it is stale again.
    later = now + timedelta(minutes=11)
    with pytest.raises(RecentMFARequired) as expired:
        require_recent_mfa(recent, now=later)
    assert not isinstance(expired.value, MFASetupRequired)


@pytest.mark.django_db
def test_pending_or_disabled_factors_do_not_count_as_an_authenticator():
    sync_policy()
    pending = make_user("pending-totp@example.edu")
    enable_totp(pending, confirmed=False)
    disabled = make_user("disabled-totp@example.edu")
    enable_totp(disabled, disabled=True)
    now = timezone.now()

    for user in (pending, disabled):
        with pytest.raises(MFASetupRequired):
            require_recent_mfa(create_auth_session(user, now=now).session, now=now)


# Retained boundaries report the account's real state


@pytest.mark.django_db
def test_retained_account_action_reports_setup_required_then_stale_then_proceeds():
    sync_policy()
    admin = make_user("retained-admin@example.edu")
    target = make_user("retained-target@example.edu", "STUDENT")
    path = f"/api/v1/accounts/{target.pk}/disable"

    no_authenticator = send(client_for(admin, recent=False), "post", path)
    assert no_authenticator.status_code == 403
    assert error_code(no_authenticator) == "mfa_setup_required"

    enable_totp(admin)
    stale = send(client_for(admin, recent=False), "post", path)
    assert stale.status_code == 403
    assert error_code(stale) == "recent_mfa_required"

    recent = send(client_for(admin, recent=True), "post", path)
    assert recent.status_code == 200
    target.refresh_from_db()
    assert target.is_active is False


@pytest.mark.django_db
def test_role_capability_and_mfa_reset_keep_step_up():
    sync_policy()
    admin = make_user("authority-admin@example.edu")
    enable_totp(admin)
    target = make_user("authority-target@example.edu", "COUNSELOR")
    stale = client_for(admin, recent=False)

    for method, path, payload in (
        ("put", f"/api/v1/accounts/{target.pk}/role", {"role": "GUIDANCE_SERVICES_STAFF"}),
        (
            "put",
            f"/api/v1/accounts/{target.pk}/capability-overrides/reports.view",
            {"effect": "GRANT", "reason": "Temporary reporting help"},
        ),
        ("post", f"/api/v1/accounts/{target.pk}/security/reset-mfa", {}),
        ("post", f"/api/v1/accounts/{target.pk}/security/revoke-sessions", {}),
    ):
        response = send(stale, method, path, payload)
        assert response.status_code == 403, path
        assert error_code(response) == "recent_mfa_required", path


@pytest.mark.django_db
def test_platform_maintenance_keeps_step_up_but_email_retry_does_not_need_it():
    sync_policy()
    admin = make_user("platform-admin@example.edu")
    enable_totp(admin)
    stale = client_for(admin, recent=False)

    enabled = send(stale, "post", "/api/v1/platform/maintenance/enable", {"message": "Planned"})
    assert enabled.status_code == 403
    assert error_code(enabled) == "recent_mfa_required"

    # An unknown delivery is refused for what it is, not for a missing step-up.
    retry = send(
        stale,
        "post",
        "/api/v1/platform/email-deliveries/00000000-0000-4000-8000-000000000000/retry",
    )
    assert retry.status_code == 404


@pytest.mark.django_db
def test_privacy_drafts_need_no_step_up_but_publication_and_retirement_keep_it():
    from tests.test_privacy_governance_expansion import notice_payload

    sync_policy()
    dpo = make_dpo("draft-dpo@example.edu")
    enable_totp(dpo)
    stale = client_for(dpo, recent=False)

    created = send(stale, "post", "/api/v1/privacy/notices", notice_payload())
    assert created.status_code == 201
    notice_id = created.json()["id"]
    revision_id = created.json()["draft_revision"]["id"]

    renamed = send(stale, "patch", f"/api/v1/privacy/notices/{notice_id}", {"name": "Renamed"})
    assert renamed.status_code == 200
    edited = send(
        stale, "patch", f"/api/v1/privacy/notice-revisions/{revision_id}", {"title": "Edited"}
    )
    assert edited.status_code == 200

    published = send(stale, "post", f"/api/v1/privacy/notice-revisions/{revision_id}/publish")
    assert published.status_code == 403
    assert error_code(published) == "recent_mfa_required"
    retired = send(stale, "post", f"/api/v1/privacy/notices/{notice_id}/retire")
    assert retired.status_code == 403
    assert error_code(retired) == "recent_mfa_required"


@pytest.mark.django_db
def test_identity_corrections_need_no_step_up_but_sign_in_email_changes_keep_it():
    sync_policy()
    admin = make_user("identity-admin@example.edu")
    target = make_user("identity-target@example.edu", "STUDENT")
    stale = client_for(admin, recent=False)

    corrected = send(
        stale, "patch", f"/api/v1/accounts/{target.pk}/identity", {"first_name": "Corrected"}
    )
    assert corrected.status_code == 200
    assert corrected.json()["first_name"] == "Corrected"

    email = send(
        stale,
        "post",
        f"/api/v1/accounts/{target.pk}/email-change",
        {"new_email": "new-address@example.edu"},
    )
    assert email.status_code == 403
    assert error_code(email) == "mfa_setup_required"


@pytest.mark.django_db
def test_disabling_a_missing_authenticator_is_not_a_step_up_challenge():
    sync_policy()
    user = make_user("no-factor@example.edu", "STUDENT")

    response = send(client_for(user, recent=False), "post", "/api/v1/auth/mfa/totp/disable")

    assert response.status_code == 400
    assert error_code(response) == "mfa_not_configured"
