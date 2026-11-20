"""Targeted HTTP, atomicity, delivery, and abuse checks for expiring links."""

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.models import AuditEvent
from compass.authentication.crypto import encrypt_totp_secret
from compass.authentication.models import (
    AccountRecoveryLink,
    AuthSession,
    EmailChangeRequest,
    EmailOTPChallenge,
    EmailOTPPurpose,
    LoginChallenge,
    RecoveryCode,
    TOTPFactor,
    TrustedSession,
)
from compass.authentication.recovery_links import (
    LINK_INVALID_MESSAGE,
    RecoveryLinkInvalid,
    RecoveryLinkPermissionDenied,
    confirm_recovery_link,
    request_assisted_recovery,
    request_password_reset_link,
)
from compass.authentication.recovery_tasks import (
    deliver_recovery_completion,
    recover_recovery_completion_notices,
)
from compass.authentication.sessions import (
    create_auth_session,
    create_login_challenge,
    create_trusted_session,
)
from compass.common.rate_limit import RateLimitResult

pytestmark = pytest.mark.django_db(transaction=True)
CURRENT_PASSWORD = "quiet gardens beside the campus library"
NEW_PASSWORD = "river lanterns across the moonlit campus"


class Limiter:
    def __init__(self):
        self.calls = []
        self.blocked = False

    def consume_with_failure_policy(self, policy, subject):
        self.calls.append((policy, subject))
        return RateLimitResult(
            allowed=not self.blocked,
            count=1,
            limit=policy.limit,
            remaining=policy.limit - 1,
            retry_after_seconds=23,
        )


@pytest.fixture(autouse=True)
def setup(settings, monkeypatch):
    settings.AUTH_TOTP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.COMPASS_PORTAL_ORIGIN = "https://compass.example.edu"
    settings.TURNSTILE_ENABLED = False
    call_command("sync_identity_policy", verbosity=0)
    limiter = Limiter()
    monkeypatch.setattr(
        "compass.authentication.abuse.RedisRateLimiter.from_settings", lambda: limiter
    )
    messages = []

    def send(_self, *, subject, body, recipients, html_body):
        messages.append({"subject": subject, "body": body, "to": recipients, "html": html_body})
        return 1

    monkeypatch.setattr("compass.integrations.mail.Mailer.send", send)
    queued = []
    monkeypatch.setattr(
        "compass.authentication.recovery_tasks.deliver_recovery_completion.delay", queued.append
    )
    return limiter, messages, queued


def user(email="student@example.edu", *, role="STUDENT", password=CURRENT_PASSWORD):
    return User.objects.create_user(
        email=email,
        password=password,
        role=Role.objects.get(code=role),
        first_name="Link",
        last_name="Test",
    )


def client_for(person, *, recent=True):
    issued = create_auth_session(person, mfa_verified_at=timezone.now() if recent else None)
    client = Client(enforce_csrf_checks=True)
    client.cookies["compass_session"] = issued.token
    return client, issued.session


def post(client, path, payload, *, csrf=True):
    headers = {}
    if csrf:
        headers["HTTP_X_CSRFTOKEN"] = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client.post(path, json.dumps(payload), content_type="application/json", **headers)


def assisted(*, target=None, actor=None, client=None, **overrides):
    target = target or user()
    actor = actor or user("admin@example.edu", role="IT_ADMIN")
    if client is None:
        client, _session = client_for(actor)
    payload = {
        "new_email": "new@example.edu",
        "identity_check_basis": "in_person_id",
        "expected_updated_at": target.updated_at.isoformat(),
        **overrides,
    }
    return post(client, f"/api/v1/accounts/{target.pk}/recovery-link", payload), target, actor


def token_from(messages):
    return re.search(r"/account-recovery#([A-Za-z0-9_-]+)", messages[-1]["body"]).group(1)


def issue(setup):
    response, target, actor = assisted()
    assert response.status_code == 202, response.json()
    return target, actor, token_from(setup[1])


def confirm(token, password=NEW_PASSWORD):
    return post(
        Client(enforce_csrf_checks=True),
        "/api/v1/auth/account-recovery/confirm",
        {"token": token, "new_password": password},
    )


def verify(token):
    return post(
        Client(enforce_csrf_checks=True), "/api/v1/auth/account-recovery/verify", {"token": token}
    )


def test_hash_only_random_token_and_branded_multipart_expiry(setup):
    target, actor, token = issue(setup)
    link = AccountRecoveryLink.objects.get(user=target)
    assert len(token) == 43 and link.token_digest == hashlib.sha256(token.encode()).hexdigest()
    assert link.requested_by_id == actor.pk and link.destination_email == "new@example.edu"
    assert link.current_email_snapshot == target.email
    assert link.expires_at - link.created_at == timedelta(hours=1)
    assert token not in json.dumps(list(AccountRecoveryLink.objects.values()), default=str)
    message = setup[1][-1]
    assert message["to"] == "new@example.edu" and "Asia/Manila" in message["body"]
    assert "ignore" in message["body"] and "COMPASS" in message["html"]
    assert f"/account-recovery#{token}" in message["html"]
    target.refresh_from_db()
    assert target.email == "student@example.edu"
    response = verify(token)
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "masked_email": "n***@example.edu",
        "email_change": True,
    }
    assert response.headers["Cache-Control"] == "no-store"


def test_single_use_no_sign_in_created_and_password_email_verified(setup):
    target, _actor, token = issue(setup)
    assert confirm(token).status_code == 200
    target.refresh_from_db()
    assert target.email == "new@example.edu" and target.check_password(NEW_PASSWORD)
    assert target.email_verified_at is not None
    assert AccountRecoveryLink.objects.get(user=target).consumed_at is not None
    assert not AuthSession.objects.filter(user=target, revoked_at__isnull=True).exists()
    assert verify(token).status_code == confirm(token).status_code == 400
    assert verify(token).json()["error"]["message"] == LINK_INVALID_MESSAGE


@pytest.mark.parametrize("change", ["expired", "email", "password", "disabled", "claimed_email"])
def test_expiry_and_account_snapshots_checked_at_verify_and_submit(setup, change):
    target, _actor, token = issue(setup)
    if change == "expired":
        link = AccountRecoveryLink.objects.get(user=target)
        # Keep the additive database TTL constraint valid while advancing test time.
        link.created_at = timezone.now() - timedelta(hours=2)
        link.expires_at = timezone.now() - timedelta(hours=1)
        link.save()
    elif change == "claimed_email":
        user("new@example.edu")
    else:
        if change == "email":
            target.email = "changed@example.edu"
        if change == "password":
            target.set_password("another password beside the quiet river")
        if change == "disabled":
            target.is_active = False
        target.save()
    for response in [verify(token), confirm(token)]:
        assert response.status_code == 400
        assert response.json()["error"]["message"] == LINK_INVALID_MESSAGE
        assert response.headers["Cache-Control"] == "no-store"


def test_newer_link_invalidates_earlier_link(setup):
    target, actor, old = issue(setup)
    response, *_ = assisted(target=target, actor=actor, new_email="second@example.edu")
    assert response.status_code == 202
    new = token_from(setup[1])
    assert verify(old).status_code == confirm(old).status_code == 400
    assert verify(new).status_code == 200
    assert (
        AccountRecoveryLink.objects.filter(user=target, invalidated_at__isnull=False).count() == 1
    )


@pytest.mark.parametrize(
    "case,expected",
    [
        ("inactive", 400),
        ("duplicate", 409),
        ("self", 403),
        ("no_mfa", 403),
        ("no_capability", 403),
        ("stale", 409),
        ("missing_basis", 422),
        ("other_no_reason", 422),
    ],
)
def test_assisted_request_refusals(setup, case, expected):
    target = user()
    actor = user("admin@example.edu", role="IT_ADMIN")
    overrides = {}
    if case == "inactive":
        target.is_active = False
        target.save()
    if case == "duplicate":
        user("new@example.edu")
    if case == "self":
        target = actor
    if case == "no_capability":
        actor = user("other@example.edu")
    client, _session = client_for(actor, recent=case != "no_mfa")
    if case == "stale":
        overrides["expected_updated_at"] = (target.updated_at - timedelta(seconds=1)).isoformat()
    if case == "missing_basis":
        overrides["identity_check_basis"] = ""
    if case == "other_no_reason":
        overrides["identity_check_basis"] = "other"
    response, *_ = assisted(target=target, actor=actor, client=client, **overrides)
    assert response.status_code == expected, response.json()
    assert response.headers["Cache-Control"] == "no-store"
    assert not AccountRecoveryLink.objects.exists() and not setup[1]


def test_direct_service_rechecks_revoked_actor_session(setup):
    actor = user("admin@example.edu", role="IT_ADMIN")
    target = user()
    _client, session = client_for(actor)
    AuthSession.objects.filter(pk=session.pk).update(revoked_at=timezone.now())
    with pytest.raises(RecoveryLinkPermissionDenied):
        request_assisted_recovery(
            actor=actor,
            actor_session=session,
            target_id=target.pk,
            new_email="new@example.edu",
            identity_check_basis="in_person_id",
            expected_updated_at=target.updated_at,
        )


def test_password_policy_does_not_consume_valid_link(setup):
    target, _actor, token = issue(setup)
    response = confirm(token, "123")
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "password_policy_failed"
    )
    assert response.json()["error"]["details"] and verify(token).status_code == 200
    assert AccountRecoveryLink.objects.get(user=target).consumed_at is None
    assert confirm(token, CURRENT_PASSWORD).status_code == 422


def test_sessions_challenges_revoked_authenticator_and_backup_codes_preserved(setup):
    target, _actor, token = issue(setup)
    create_auth_session(target)
    create_auth_session(target)
    create_trusted_session(target)
    create_login_challenge(target, allowed_methods=["totp"], trust_browser=False)
    factor = TOTPFactor.objects.create(
        user=target,
        encrypted_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
        confirmed_at=timezone.now(),
    )
    backup = RecoveryCode.objects.create(user=target, code_hash="test-hash")
    for purpose in EmailOTPPurpose.values:
        EmailOTPChallenge.objects.create(
            user=target,
            email="pending@example.edu",
            purpose=purpose,
            code_hash="test-hash",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
    challenge = EmailOTPChallenge.objects.get(user=target, purpose=EmailOTPPurpose.EMAIL_CHANGE)
    pending = EmailChangeRequest.objects.create(
        user=target,
        requested_by=target,
        current_email_snapshot=target.email,
        new_email="pending@example.edu",
        email_otp_challenge=challenge,
        expires_at=challenge.expires_at,
    )
    assert confirm(token).status_code == 200
    assert not AuthSession.objects.filter(user=target, revoked_at__isnull=True).exists()
    assert not TrustedSession.objects.filter(user=target, revoked_at__isnull=True).exists()
    assert not LoginChallenge.objects.filter(user=target, consumed_at__isnull=True).exists()
    assert not EmailOTPChallenge.objects.filter(user=target, consumed_at__isnull=True).exists()
    pending.refresh_from_db()
    assert pending.cancelled_at is not None
    factor.refresh_from_db()
    assert factor.disabled_at is None
    backup.refresh_from_db()
    assert backup.used_at is None and backup.invalidated_at is None


def test_receipts_after_commit_sent_once_to_old_and_new_addresses(setup):
    target, _actor, token = issue(setup)
    assert confirm(token).status_code == 200
    assert setup[2] == [str(AccountRecoveryLink.objects.get(user=target).pk)]
    setup[1].clear()
    assert deliver_recovery_completion.run(setup[2][0]) == 2
    assert [message["to"] for message in setup[1]] == ["student@example.edu", "new@example.edu"]
    assert deliver_recovery_completion.run(setup[2][0]) == 0
    assert recover_recovery_completion_notices.run() == 0


def test_audit_failure_rolls_back_password_email_token_sessions_and_receipts(setup):
    target, _actor, token = issue(setup)
    session = create_auth_session(target).session
    with patch("compass.authentication.recovery_links.record_event", side_effect=RuntimeError):
        response = confirm(token)
    assert response.status_code == 503
    target.refresh_from_db()
    session.refresh_from_db()
    assert target.email == "student@example.edu" and target.check_password(CURRENT_PASSWORD)
    assert session.revoked_at is None and not setup[2]
    assert AccountRecoveryLink.objects.get(user=target).consumed_at is None


def test_other_identity_record_and_staff_audit_have_no_token_password_or_email(setup):
    response, target, actor = assisted(
        identity_check_basis="other", identity_check_reason="Registrar checked ID in person"
    )
    assert response.status_code == 202
    token = token_from(setup[1])
    assert confirm(token).status_code == 200
    link = AccountRecoveryLink.objects.get(user=target)
    assert link.identity_check_reason == "Registrar checked ID in person"
    event = AuditEvent.objects.get(action="auth.password.reset", target_id=str(target.pk))
    assert event.actor_user_id == actor.pk and event.metadata["identity_check_basis"] == "other"
    assert event.metadata["identity_check_record_id"] == str(link.pk)
    serialized = json.dumps(list(AuditEvent.objects.values()), default=str)
    assert (
        token not in serialized
        and NEW_PASSWORD not in serialized
        and "new@example.edu" not in serialized
    )


def test_forgot_password_identical_response_active_unknown_inactive_and_30_minute_ttl(setup):
    active = user()
    inactive = user("inactive@example.edu")
    inactive.is_active = False
    inactive.save()
    results = [
        post(Client(), "/api/v1/auth/password-link/request", {"email": email})
        for email in [active.email, "unknown@example.edu", inactive.email]
    ]
    assert [result.status_code for result in results] == [202, 202, 202]
    assert results[0].json() == results[1].json() == results[2].json()
    assert all(result.headers["Cache-Control"] == "no-store" for result in results)
    assert len(setup[1]) == AccountRecoveryLink.objects.count() == 1
    link = AccountRecoveryLink.objects.get()
    assert link.expires_at - link.created_at == timedelta(minutes=30)
    token = token_from(setup[1])
    assert verify(token).json()["email_change"] is False
    assert confirm(token).status_code == 200
    active.refresh_from_db()
    assert active.email == "student@example.edu" and active.check_password(NEW_PASSWORD)
    setup[1].clear()
    assert deliver_recovery_completion.run(setup[2][0]) == 1
    assert setup[1][0]["to"] == active.email


def test_initial_password_setup_by_link(setup):
    target = user(password=None)
    request_password_reset_link(email=target.email)
    assert confirm(token_from(setup[1])).status_code == 200
    assert AuditEvent.objects.filter(
        action="auth.password.initial_set", target_id=str(target.pk)
    ).exists()


@pytest.mark.parametrize("operation", ["verify", "confirm", "request"])
def test_rate_limit_hit_and_retry_after(setup, operation):
    _target, _actor, token = issue(setup)
    setup[0].blocked = True
    if operation == "verify":
        response = verify(token)
    elif operation == "confirm":
        response = confirm(token)
    else:
        response = post(
            Client(), "/api/v1/auth/password-link/request", {"email": "unknown@example.edu"}
        )
    assert response.status_code == 429 and response.headers["Retry-After"] == "23"
    assert response.headers["Cache-Control"] == "no-store"


def test_ip_and_token_budgets_on_verification_and_submission(setup):
    _target, _actor, token = issue(setup)
    setup[0].calls.clear()
    assert verify(token).status_code == confirm(token).status_code == 200
    assert [policy.name for policy, _ in setup[0].calls] == [
        "auth.account_link.verify.ip",
        "auth.account_link.verify.identifier",
        "auth.account_link.submit.ip",
        "auth.account_link.submit.identifier",
    ]
    assert all(token not in subject for _, subject in setup[0].calls)


@pytest.mark.parametrize(
    "path,payload",
    [("verify", {"token": "bad"}), ("confirm", {"token": "bad", "new_password": "example"})],
)
def test_csrf_failure_no_store(setup, path, payload):
    response = post(
        Client(enforce_csrf_checks=True),
        f"/api/v1/auth/account-recovery/{path}",
        payload,
        csrf=False,
    )
    assert response.status_code == 403 and response.headers["Cache-Control"] == "no-store"


def test_unknown_empty_token_generic_and_rate_limited(setup):
    for token in ["", "bad", "a" * 43]:
        response = verify(token)
        assert (
            response.status_code == 400
            and response.json()["error"]["message"] == LINK_INVALID_MESSAGE
        )
    assert len(setup[0].calls) == 6


def test_turnstile_enforced_unknown_and_active_email(setup, settings):
    settings.TURNSTILE_ENABLED = True
    target = user()
    for email in [target.email, "unknown@example.edu"]:
        response = post(Client(), "/api/v1/auth/password-link/request", {"email": email})
        assert (
            response.status_code == 403
            and response.json()["error"]["code"] == "security_verification_failed"
        )
    assert not setup[1] and not AccountRecoveryLink.objects.exists()


def test_untrusted_or_missing_origin_fails_for_unknown_email_too(setup, settings):
    for origin in ["", "https://compass.example.edu/evil", "https://user@evil.example"]:
        settings.COMPASS_PORTAL_ORIGIN = origin
        response = post(
            Client(), "/api/v1/auth/password-link/request", {"email": "unknown@example.edu"}
        )
        assert response.status_code == 503
    assert not setup[1]


def test_completion_enqueue_failure_recovered(setup, monkeypatch):
    target, _actor, token = issue(setup)

    def fail(_id):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        "compass.authentication.recovery_tasks.deliver_recovery_completion.delay", fail
    )
    assert confirm(token).status_code == 200
    monkeypatch.setattr(
        "compass.authentication.recovery_tasks.deliver_recovery_completion.delay", setup[2].append
    )
    assert recover_recovery_completion_notices.run() == 1
    assert setup[2] == [str(AccountRecoveryLink.objects.get(user=target).pk)]


def test_two_concurrent_submissions_consume_link_only_once(setup):
    if connection.vendor != "postgresql":
        pytest.skip("requires PostgreSQL row locks")
    target, _actor, token = issue(setup)

    def complete():
        close_old_connections()
        try:
            confirm_recovery_link(token=token, new_password=NEW_PASSWORD)
            return "completed"
        except RecoveryLinkInvalid:
            return "unavailable"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: complete(), range(2)))
    assert sorted(outcomes) == ["completed", "unavailable"]
    assert (
        AuditEvent.objects.filter(action="auth.password.reset", target_id=str(target.pk)).count()
        == 1
    )
    assert len(setup[2]) == 1
