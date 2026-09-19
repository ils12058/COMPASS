"""Verified-before-commit sign-in email change workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.actions import (
    AUTH_EMAIL_CHANGED,
    AUTH_EMAIL_CHANGE_REQUESTED,
)
from compass.authentication.email_otp import (
    EmailOTPInvalid,
    _consume_email_otp_locked,
    _verify_email_otp_locked,
    consume_email_otp,
    issue_email_otp,
)
from compass.authentication.mfa import has_active_totp_factor, mfa_required_for_user
from compass.authentication.models import (
    EmailChangeRequest,
    EmailOTPChallenge,
    EmailOTPPurpose,
)
from compass.authentication.security import (
    AuthStateInvalidation,
    invalidate_auth_state_after_authority_change,
)
from compass.authentication.sessions import require_recent_mfa

logger = logging.getLogger("compass.authentication.email_change")


class EmailChangeError(RuntimeError):
    """Base class for expected email-change failures."""


class EmailChangeInvalid(EmailChangeError):
    """The request or challenge cannot safely authorize an email transition."""


class EmailChangeConflict(EmailChangeError):
    """The proposed email or account state conflicts with another identity."""


class EmailChangeNotFound(EmailChangeError):
    """The pending request does not belong to the authenticated account."""


class EmailChangePermissionDenied(EmailChangeError):
    """The actor is not authorized for an administrative initiation."""


class EmailChangeStrongAuthRequired(EmailChangeError):
    """The account requires TOTP-backed step-up and cannot use email fallback."""


@dataclass(frozen=True, slots=True)
class EmailChangeChallenge:
    challenge_id: object
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PendingEmailChange:
    request_id: object
    challenge_id: object
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class EmailChangeConfirmation:
    request_id: object
    invalidation: AuthStateInvalidation
    reauthentication_required: bool = True


def _normalize_email(value: str) -> str:
    try:
        return User.objects.clean_email(value)
    except (TypeError, ValueError) as exc:
        raise EmailChangeInvalid("a valid new email address is required") from exc


def _assert_new_email_available(*, user: User, new_email: str) -> None:
    if new_email == user.email:
        raise EmailChangeInvalid("the new email must differ from the current email")
    if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        raise EmailChangeConflict("the proposed email is already assigned to another account")


def _cancel_pending_locked(*, user_id, current: datetime) -> None:
    pending = EmailChangeRequest.objects.select_for_update().filter(
        user_id=user_id,
        confirmed_at__isnull=True,
        cancelled_at__isnull=True,
    )
    for request in pending:
        request.cancelled_at = current
        request.save(update_fields=["cancelled_at"])


def _stage_locked(
    *,
    user: User,
    requested_by: User,
    new_email: str,
    context: AuditContext,
    request,
    turnstile_token: str | None,
    current_email_authorized_at: datetime | None,
    current: datetime,
) -> PendingEmailChange:
    if not user.is_active:
        raise EmailChangeInvalid("the account is unavailable")
    normalized_email = _normalize_email(new_email)
    _assert_new_email_available(user=user, new_email=normalized_email)

    _cancel_pending_locked(user_id=user.pk, current=current)
    issue = issue_email_otp(
        email=normalized_email,
        purpose=EmailOTPPurpose.EMAIL_CHANGE,
        user=user,
        request=request,
        turnstile_token=turnstile_token,
        replace_existing=True,
        now=current,
    )
    pending = EmailChangeRequest.objects.create(
        user=user,
        requested_by=requested_by,
        current_email_snapshot=user.email,
        new_email=normalized_email,
        email_otp_challenge=issue.challenge,
        created_at=current,
        expires_at=issue.challenge.expires_at,
        current_email_authorized_at=current_email_authorized_at,
    )
    record_event(
        context=context,
        action=AUTH_EMAIL_CHANGE_REQUESTED,
        outcome=AuditOutcome.SUCCESS,
        target_type="auth.emailchange",
        target_id=pending.pk,
        metadata={
            "initiator": "self" if requested_by.pk == user.pk else "administrator",
        },
    )
    return PendingEmailChange(
        request_id=pending.pk,
        challenge_id=issue.challenge.pk,
        expires_at=pending.expires_at,
    )


def request_current_email_security_challenge(
    *,
    user: User,
    request,
    turnstile_token: str | None = None,
) -> EmailChangeChallenge:
    """Issue fallback authorization only for accounts not governed by TOTP step-up."""

    with transaction.atomic():
        locked = User.objects.select_for_update().select_related("role").get(pk=user.pk)
        if not locked.is_active:
            raise EmailChangeInvalid("the account is unavailable")
        if mfa_required_for_user(locked):
            raise EmailChangeStrongAuthRequired(
                "TOTP-backed recent MFA is required for this account"
            )
        if locked.email_verified_at is None:
            raise EmailChangeInvalid(
                "the current email must already be verified before email fallback can be used"
            )
        issue = issue_email_otp(
            email=locked.email,
            purpose=EmailOTPPurpose.SECURITY_CHALLENGE,
            user=locked,
            request=request,
            turnstile_token=turnstile_token,
            replace_existing=True,
        )
        return EmailChangeChallenge(
            challenge_id=issue.challenge.pk,
            expires_at=issue.challenge.expires_at,
        )


def request_self_email_change(
    *,
    user: User,
    session,
    new_email: str,
    context: AuditContext,
    request,
    turnstile_token: str | None = None,
    current_email_challenge_id=None,
    current_email_code: str | None = None,
    now: datetime | None = None,
) -> PendingEmailChange:
    current = now or timezone.now()
    authorized_current_email: str | None = None

    # For non-TOTP accounts, consume the current-mailbox proof first. Invalid-attempt
    # accounting must commit independently instead of being rolled back with staging.
    role = getattr(user, "role", None)
    role_code = getattr(role, "code", None)
    required_by_role = role_code in settings.AUTH_MFA_REQUIRED_ROLE_CODES
    has_totp = has_active_totp_factor(user.pk)
    if not has_totp and not required_by_role:
        if current_email_challenge_id is None or current_email_code is None:
            raise EmailChangeInvalid("current email authorization is required")
        challenge = EmailOTPChallenge.objects.filter(pk=current_email_challenge_id).first()
        if (
            challenge is None
            or challenge.user_id != user.pk
            or challenge.purpose != EmailOTPPurpose.SECURITY_CHALLENGE
            or challenge.email != user.email
        ):
            raise EmailChangeInvalid("current email authorization is unavailable")
        try:
            consume_email_otp(
                challenge_id=challenge.pk,
                code=current_email_code,
                request=request,
                now=current,
            )
        except EmailOTPInvalid as exc:
            raise EmailChangeInvalid("current email authorization is unavailable") from exc
        authorized_current_email = challenge.email

    with transaction.atomic():
        locked = User.objects.select_for_update().select_related("role").get(pk=user.pk)
        if not locked.is_active:
            raise EmailChangeInvalid("the account is unavailable")
        if getattr(session, "user_id", None) != locked.pk:
            raise EmailChangeInvalid("the authenticated session is unavailable")

        if mfa_required_for_user(locked):
            if not has_active_totp_factor(locked.pk):
                raise EmailChangeStrongAuthRequired(
                    "TOTP must be configured for this account before changing email"
                )
            require_recent_mfa(session, now=current)
            current_email_authorized_at = None
        else:
            if authorized_current_email is None or locked.email != authorized_current_email:
                raise EmailChangeInvalid("current email authorization is stale")
            current_email_authorized_at = current

        return _stage_locked(
            user=locked,
            requested_by=locked,
            new_email=new_email,
            context=context,
            request=request,
            turnstile_token=turnstile_token,
            current_email_authorized_at=current_email_authorized_at,
            current=current,
        )


def request_administrative_email_change(
    *,
    actor: User,
    actor_session,
    target_id,
    new_email: str,
    context: AuditContext,
    request,
    turnstile_token: str | None = None,
    now: datetime | None = None,
) -> PendingEmailChange:
    """Stage a new mailbox for an account manager without bypassing possession proof."""

    current = now or timezone.now()
    ids = sorted({actor.pk, target_id}, key=str)
    with transaction.atomic():
        locked_users = {
            item.pk: item
            for item in User.objects.select_for_update()
            .select_related("role")
            .filter(pk__in=ids)
            .order_by("id")
        }
        locked_actor = locked_users.get(actor.pk)
        target = locked_users.get(target_id)
        if (
            locked_actor is None
            or not locked_actor.is_active
            or not locked_actor.has_capability("accounts.manage")
        ):
            raise EmailChangePermissionDenied("accounts.manage is required")
        if getattr(actor_session, "user_id", None) != locked_actor.pk:
            raise EmailChangePermissionDenied("the step-up session does not belong to the actor")
        require_recent_mfa(actor_session, now=current)
        if target is None or not target.is_active:
            raise EmailChangeNotFound("the requested account was not found")

        return _stage_locked(
            user=target,
            requested_by=locked_actor,
            new_email=new_email,
            context=context,
            request=request,
            turnstile_token=turnstile_token,
            current_email_authorized_at=None,
            current=current,
        )


def _safe_enqueue_old_email_alert(request_id: str) -> None:
    try:
        from compass.authentication.tasks import deliver_email_change_security_alert

        deliver_email_change_security_alert.delay(request_id)
    except Exception:
        logger.warning(
            "email change security alert enqueue failed; request remains recoverable",
            extra={
                "event": "email_change_security_alert_enqueue_failed",
                "email_change_request_id": request_id,
            },
        )


def confirm_email_change(
    *,
    user: User,
    session,
    request_id,
    challenge_id,
    code: str,
    context: AuditContext,
    request,
    now: datetime | None = None,
) -> EmailChangeConfirmation:
    current = now or timezone.now()
    invalid_code = False
    result: EmailChangeConfirmation | None = None

    with transaction.atomic():
        locked_user = User.objects.select_for_update().select_related("role").get(pk=user.pk)
        pending = (
            EmailChangeRequest.objects.select_for_update()
            .select_related("requested_by", "email_otp_challenge")
            .filter(pk=request_id, user_id=locked_user.pk)
            .first()
        )
        if pending is None:
            raise EmailChangeNotFound("the pending email change was not found")
        if (
            pending.confirmed_at is not None
            or pending.cancelled_at is not None
            or pending.expires_at <= current
            or pending.email_otp_challenge_id != challenge_id
        ):
            raise EmailChangeInvalid("the pending email change is unavailable")
        if not locked_user.is_active:
            raise EmailChangeInvalid("the account is unavailable")
        if getattr(session, "user_id", None) != locked_user.pk:
            raise EmailChangeInvalid("the authenticated session is unavailable")
        if locked_user.email != pending.current_email_snapshot:
            raise EmailChangeConflict("the account email changed after this request was created")
        if User.objects.filter(email__iexact=pending.new_email).exclude(
            pk=locked_user.pk
        ).exists():
            raise EmailChangeConflict("the proposed email is already assigned to another account")

        if mfa_required_for_user(locked_user):
            if not has_active_totp_factor(locked_user.pk):
                raise EmailChangeStrongAuthRequired(
                    "TOTP must be configured for this account before changing email"
                )
            require_recent_mfa(session, now=current)
        elif (
            pending.requested_by_id == locked_user.pk
            and pending.current_email_authorized_at is None
        ):
            raise EmailChangeInvalid("current email authorization is missing")

        challenge = EmailOTPChallenge.objects.select_for_update().get(
            pk=pending.email_otp_challenge_id
        )
        usable_binding = (
            challenge.user_id == locked_user.pk
            and challenge.email == pending.new_email
            and challenge.purpose == EmailOTPPurpose.EMAIL_CHANGE
        )
        valid = usable_binding and _verify_email_otp_locked(
            challenge=challenge,
            code=code,
            request=request,
            current=current,
            expected_purpose=EmailOTPPurpose.EMAIL_CHANGE,
        )
        if not valid:
            invalid_code = True
        else:
            try:
                with transaction.atomic():
                    locked_user.email = pending.new_email
                    locked_user.email_verified_at = current
                    locked_user.save(update_fields=["email", "email_verified_at", "updated_at"])
            except IntegrityError as exc:
                raise EmailChangeConflict(
                    "the proposed email is already assigned to another account"
                ) from exc

            _consume_email_otp_locked(challenge=challenge, request=request, current=current)
            pending.confirmed_at = current
            pending.save(update_fields=["confirmed_at"])
            invalidation = invalidate_auth_state_after_authority_change(
                user_id=locked_user.pk,
                context=context,
                reason="email_changed",
                now=current,
                invalidate_email_security_challenges=True,
                previous_email=pending.current_email_snapshot,
            )
            record_event(
                context=context,
                action=AUTH_EMAIL_CHANGED,
                outcome=AuditOutcome.SUCCESS,
                target_type="accounts.user",
                target_id=locked_user.pk,
                metadata={
                    "initiator": (
                        "self"
                        if pending.requested_by_id == locked_user.pk
                        else "administrator"
                    )
                },
            )
            transaction.on_commit(
                lambda request_id=str(pending.pk): _safe_enqueue_old_email_alert(request_id)
            )
            result = EmailChangeConfirmation(
                request_id=pending.pk,
                invalidation=invalidation,
            )

    if invalid_code:
        raise EmailChangeInvalid("the email verification challenge is unavailable")
    assert result is not None
    return result


__all__ = [
    "EmailChangeChallenge",
    "EmailChangeConflict",
    "EmailChangeError",
    "EmailChangeInvalid",
    "EmailChangeNotFound",
    "EmailChangePermissionDenied",
    "EmailChangeStrongAuthRequired",
    "EmailChangeConfirmation",
    "PendingEmailChange",
    "confirm_email_change",
    "request_administrative_email_change",
    "request_current_email_security_challenge",
    "request_self_email_change",
]
