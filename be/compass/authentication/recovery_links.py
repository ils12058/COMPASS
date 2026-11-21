"""Hash-only, single-use links for assisted recovery and password access."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.audit.context import AuditContext
from compass.audit.services import record_event
from compass.authentication.abuse import (
    check_auth_rate_limit,
    request_ip,
    verify_turnstile,
)
from compass.authentication.actions import AUTH_PASSWORD_INITIAL_SET, AUTH_PASSWORD_RESET
from compass.authentication.models import (
    AccountRecoveryLink,
    AuthSession,
    EmailChangeRequest,
    EmailOTPPurpose,
    IdentityCheckBasis,
)
from compass.authentication.password_access import validate_new_password
from compass.authentication.security import invalidate_reusable_auth_state
from compass.authentication.security_email import render_recovery_link_email
from compass.authentication.sessions import (
    digest_opaque_token,
    generate_opaque_token,
    require_recent_mfa,
)
from compass.integrations.mail import Mailer
from compass.notifications.email_links import validated_portal_origin

User = get_user_model()
logger = logging.getLogger("compass.authentication.recovery_links")
LINK_INVALID_MESSAGE = "This link is unavailable. Ask the ITSO for a new link."
LINK_REQUEST_MESSAGE = "If the account is eligible, a password link will be sent to its email."
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}", re.ASCII)


class RecoveryLinkInvalid(RuntimeError):
    pass


class RecoveryLinkInputInvalid(RuntimeError):
    pass


class RecoveryLinkConflict(RuntimeError):
    pass


class RecoveryLinkPermissionDenied(RuntimeError):
    pass


class RecoveryLinkSelfTarget(RuntimeError):
    pass


class RecoveryLinkUnavailable(RuntimeError):
    pass


class RecoveryLinkVerificationFailed(RuntimeError):
    pass


def _email(value: str) -> str:
    try:
        return User.objects.clean_email(value)
    except (TypeError, ValueError):
        raise RecoveryLinkInputInvalid("Enter a valid email address.") from None


def _origin() -> str:
    origin = validated_portal_origin(settings.COMPASS_PORTAL_ORIGIN, app_env=settings.APP_ENV)
    if origin is None:
        raise RecoveryLinkUnavailable("The email link destination is not configured.")
    return origin


def _issue_controls(*, email, request, limiter, turnstile_token) -> None:
    # Preserve the existing forgot-password request limits and Turnstile action.
    check_auth_rate_limit(
        "email_otp_issue", ip_address=request_ip(request), identifier=email, limiter=limiter
    )
    if not verify_turnstile(request, turnstile_token, flow="email_otp"):
        raise RecoveryLinkVerificationFailed


def _dispatch(link_id: str, token: str, origin: str, *, required: bool) -> None:
    """Render and send in memory after commit; never publish a secret to Celery/logs.

    The raw token cannot be recovered for retries. A failed initial delivery requires a
    newly issued link. Completion notices have a separate durable, secret-free task.
    """
    try:
        link = AccountRecoveryLink.objects.select_related("user").get(pk=link_id)
        if not _usable(link, link.user, timezone.now()):
            if required:
                raise RecoveryLinkUnavailable
            return
        message = render_recovery_link_email(
            url=f"{origin}/account-recovery#{token}",
            expires_at=link.expires_at,
            email_change=link.email_change,
        )
        sent = Mailer().send(
            subject=message.subject,
            body=message.text_body,
            html_body=message.html_body,
            recipients=link.destination_email,
        )
        if sent != 1:
            raise RecoveryLinkUnavailable
    except Exception:
        # Exception details may include a message body, so log only this fixed event.
        logger.warning("account link delivery failed", extra={"event": "account_link_send_failed"})
        if required:
            raise RecoveryLinkUnavailable from None


def _issue_locked(
    *, user, actor, destination, email_change, basis, reason, current, origin, request
):
    AccountRecoveryLink.objects.filter(
        user=user, consumed_at__isnull=True, invalidated_at__isnull=True
    ).update(invalidated_at=current)
    ttl = (
        settings.AUTH_ACCOUNT_RECOVERY_LINK_TTL_SECONDS
        if email_change
        else settings.AUTH_PASSWORD_RESET_LINK_TTL_SECONDS
    )
    token = generate_opaque_token()
    link = AccountRecoveryLink.objects.create(
        user=user,
        requested_by=actor,
        token_digest=digest_opaque_token(token),
        current_email_snapshot=user.email,
        password_snapshot_digest=digest_opaque_token(user.password),
        destination_email=destination,
        email_change=email_change,
        identity_check_basis=basis,
        identity_check_reason=reason,
        created_at=current,
        expires_at=current + timedelta(seconds=ttl),
    )
    # Free-text identity details stay on the staff check record, outside audit metadata.
    record_event(
        context=AuditContext.from_request(request, actor=actor)
        if request
        else AuditContext.user(actor),
        action="auth.account.link.issued",
        outcome="SUCCESS",
        target_type="accounts.user",
        target_id=user.pk,
        metadata={
            "method": "expiring_link",
            "initiator": "administrator" if email_change else "self",
            "identity_check_basis": basis,
            "identity_check_record_id": str(link.pk),
        },
    )
    transaction.on_commit(lambda: _dispatch(str(link.pk), token, origin, required=email_change))
    return link


def request_assisted_recovery(
    *,
    actor,
    actor_session,
    target_id,
    new_email: str,
    identity_check_basis: str,
    identity_check_reason: str = "",
    expected_updated_at: datetime,
    request=None,
    limiter=None,
    turnstile_token=None,
    now=None,
):
    current = now or timezone.now()
    destination = _email(new_email)
    reason = identity_check_reason.strip()
    if (
        identity_check_basis not in IdentityCheckBasis.values
        or (identity_check_basis == IdentityCheckBasis.OTHER and not reason)
        or len(reason) > 240
        or any(ord(char) < 32 for char in reason)
    ):
        raise RecoveryLinkInputInvalid("Record how the person's identity was checked.")
    if identity_check_basis != IdentityCheckBasis.OTHER and reason:
        raise RecoveryLinkInputInvalid("Use Other to record a different identity check.")
    origin = _origin()
    with transaction.atomic():
        users = {
            item.pk: item
            for item in User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk__in=sorted({actor.pk, target_id}, key=str))
            .order_by("id")
        }
        locked_actor = users.get(actor.pk)
        if (
            not locked_actor
            or not locked_actor.is_active
            or not locked_actor.has_capability("accounts.manage")
        ):
            raise RecoveryLinkPermissionDenied
        session = (
            AuthSession.objects.select_for_update()
            .filter(
                pk=getattr(actor_session, "pk", None),
                user=locked_actor,
                revoked_at__isnull=True,
                expires_at__gt=current,
            )
            .first()
        )
        if session is None:
            raise RecoveryLinkPermissionDenied
        require_recent_mfa(session, now=current)
        if target_id == actor.pk:
            raise RecoveryLinkSelfTarget
        target = users.get(target_id)
        if target is None or not target.is_active:
            raise RecoveryLinkInvalid(LINK_INVALID_MESSAGE)
        if target.updated_at != expected_updated_at:
            raise RecoveryLinkConflict("This account changed. Review its latest details.")
        if destination == target.email:
            raise RecoveryLinkInputInvalid("Choose a different email address.")
        if User.objects.filter(email__iexact=destination).exclude(pk=target.pk).exists():
            raise RecoveryLinkConflict("This email belongs to another account.")
        _issue_controls(
            email=destination, request=request, limiter=limiter, turnstile_token=turnstile_token
        )
        return _issue_locked(
            user=target,
            actor=locked_actor,
            destination=destination,
            email_change=True,
            basis=identity_check_basis,
            reason=reason,
            current=current,
            origin=origin,
            request=request,
        )


def request_password_reset_link(
    *, email, request=None, limiter=None, turnstile_token=None, now=None
):
    normalized = _email(email)
    _issue_controls(
        email=normalized, request=request, limiter=limiter, turnstile_token=turnstile_token
    )
    origin = _origin()  # Configuration failure is identical for known and unknown accounts.
    current = now or timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(email=normalized, is_active=True).first()
        if user is not None:
            _issue_locked(
                user=user,
                actor=user,
                destination=user.email,
                email_change=False,
                basis="",
                reason="",
                current=current,
                origin=origin,
                request=request,
            )
    return LINK_REQUEST_MESSAGE


def _lookup(token, *, operation, request, limiter):
    # Even malformed/unknown tokens consume both the IP and digest-subject budgets.
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    check_auth_rate_limit(
        operation, ip_address=request_ip(request), identifier=digest, limiter=limiter
    )
    if not _TOKEN_RE.fullmatch(token):
        raise RecoveryLinkInvalid(LINK_INVALID_MESSAGE)
    return AccountRecoveryLink.objects.filter(token_digest=digest).first()


def _usable(link, user, current):
    return bool(
        link is not None
        and user is not None
        and user.is_active
        and link.consumed_at is None
        and link.invalidated_at is None
        and link.expires_at > current
        and user.email == link.current_email_snapshot
        and digest_opaque_token(user.password) == link.password_snapshot_digest
        and (not link.email_change or link.requested_by_id is not None)
        and not User.objects.filter(email__iexact=link.destination_email)
        .exclude(pk=user.pk)
        .exists()
    )


def verify_recovery_link(*, token, request=None, limiter=None, now=None):
    link = _lookup(token, operation="account_link_verify", request=request, limiter=limiter)
    user = User.objects.filter(pk=link.user_id).first() if link else None
    if not _usable(link, user, now or timezone.now()):
        raise RecoveryLinkInvalid(LINK_INVALID_MESSAGE)
    local, domain = link.destination_email.split("@", 1)
    return {
        "valid": True,
        "masked_email": f"{local[:1]}***@{domain}",
        "email_change": link.email_change,
    }


def _enqueue_receipts(link_id):
    try:
        from compass.authentication.recovery_tasks import deliver_recovery_completion

        deliver_recovery_completion.delay(link_id)
    except Exception:
        logger.warning(
            "account link receipts enqueue failed",
            extra={"event": "account_link_receipts_enqueue_failed"},
        )


def confirm_recovery_link(*, token, new_password, request=None, limiter=None, now=None):
    existing = _lookup(token, operation="account_link_submit", request=request, limiter=limiter)
    if existing is None:
        raise RecoveryLinkInvalid(LINK_INVALID_MESSAGE)
    current = now or timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=existing.user_id).first()
        link = (
            AccountRecoveryLink.objects.select_for_update(of=("self",))
            .select_related("requested_by")
            .get(pk=existing.pk)
        )
        current = now or timezone.now()
        if not _usable(link, user, current):
            raise RecoveryLinkInvalid(LINK_INVALID_MESSAGE)
        # Validate against the identity that will be committed, including the new mailbox.
        user.email = link.destination_email
        validate_new_password(user=user, new_password=new_password)
        initial_password = not user.has_usable_password()
        user.set_password(new_password)
        user.email_verified_at = current
        try:
            with transaction.atomic():
                user.save(update_fields=["password", "email", "email_verified_at", "updated_at"])
        except IntegrityError:
            raise RecoveryLinkInvalid(LINK_INVALID_MESSAGE) from None
        actor = link.requested_by if link.email_change else user
        context = (
            AuditContext.from_request(request, actor=actor) if request else AuditContext.user(actor)
        )
        link.consumed_at = current
        link.save(update_fields=["consumed_at"])
        AccountRecoveryLink.objects.filter(
            user=user, consumed_at__isnull=True, invalidated_at__isnull=True
        ).update(invalidated_at=current)
        invalidate_reusable_auth_state(
            user_id=user.pk,
            context=context,
            reason="account_link_completed",
            now=current,
            email_challenge_purposes=EmailOTPPurpose.values,
        )
        EmailChangeRequest.objects.filter(
            user=user, confirmed_at__isnull=True, cancelled_at__isnull=True
        ).update(cancelled_at=current)
        metadata = {
            "method": "expiring_link",
            "initiator": "administrator" if link.email_change else "self",
            "identity_check_basis": link.identity_check_basis,
            "identity_check_record_id": str(link.pk),
        }
        record_event(
            context=context,
            action=AUTH_PASSWORD_INITIAL_SET if initial_password else AUTH_PASSWORD_RESET,
            outcome="SUCCESS",
            target_type="accounts.user",
            target_id=user.pk,
            metadata=metadata,
        )
        if link.email_change:
            record_event(
                context=context,
                action="auth.email.changed",
                outcome="SUCCESS",
                target_type="accounts.user",
                target_id=user.pk,
                metadata=metadata,
            )
        transaction.on_commit(lambda: _enqueue_receipts(str(link.pk)))
    return {"password_set": True}
