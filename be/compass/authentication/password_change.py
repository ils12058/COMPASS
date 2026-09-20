"""Authenticated self-service password change with explicit strong-auth boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from compass.audit.context import AuditContext
from compass.audit.services import record_event
from compass.authentication.abuse import check_auth_rate_limit, request_ip
from compass.authentication.actions import AUTH_PASSWORD_CHANGED
from compass.authentication.mfa import has_active_totp_factor, mfa_required_for_user
from compass.authentication.models import EmailOTPPurpose
from compass.authentication.password_access import validate_new_password
from compass.authentication.security import AuthStateInvalidation, invalidate_reusable_auth_state
from compass.authentication.sessions import require_recent_mfa
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event

User = get_user_model()


class PasswordChangeError(RuntimeError):
    """Base class for expected authenticated password-change failures."""


class PasswordChangeAuthenticationFailed(PasswordChangeError):
    """The authenticated user did not satisfy the required primary proof."""


class PasswordChangeStrongAuthRequired(PasswordChangeError):
    """The account requires TOTP-backed recent MFA but cannot currently satisfy it."""


@dataclass(frozen=True, slots=True)
class PasswordChangeResult:
    changed: bool
    method: str
    invalidation: AuthStateInvalidation


def change_password(
    *,
    user,
    session,
    current_password: str | None,
    new_password: str,
    context: AuditContext,
    request=None,
    limiter=None,
    now: datetime | None = None,
) -> PasswordChangeResult:
    """Change an authenticated account password without creating a recovery flow."""

    current = now or timezone.now()

    with transaction.atomic():
        locked_user = User.objects.select_for_update().select_related("role").filter(pk=user.pk).first()
        if (
            locked_user is None
            or not locked_user.is_active
            or getattr(session, "user_id", None) != locked_user.pk
        ):
            raise PasswordChangeAuthenticationFailed(
                "the authenticated account could not be verified"
            )

        if mfa_required_for_user(locked_user):
            if not has_active_totp_factor(locked_user.pk):
                raise PasswordChangeStrongAuthRequired(
                    "TOTP must be configured before changing this account password"
                )
            require_recent_mfa(session, now=current)
            method = "recent_mfa"
        else:
            check_auth_rate_limit(
                "password_change",
                ip_address=request_ip(request),
                user_id=locked_user.pk,
                limiter=limiter,
            )
            if (
                not isinstance(current_password, str)
                or not current_password
                or not locked_user.check_password(current_password)
            ):
                raise PasswordChangeAuthenticationFailed(
                    "the current password could not be verified"
                )
            method = "current_password"

        validate_new_password(user=locked_user, new_password=new_password)
        locked_user.set_password(new_password)
        locked_user.save(update_fields=["password", "updated_at"])

        invalidation = invalidate_reusable_auth_state(
            user_id=locked_user.pk,
            context=context,
            reason="password_changed",
            now=current,
            email_challenge_purposes=(
                EmailOTPPurpose.RECOVERY,
                EmailOTPPurpose.EMAIL_VERIFICATION,
            ),
            email_challenge_email=locked_user.email,
            exclude_auth_session_id=session.pk,
        )
        audit_event = record_event(
            context=context,
            action=AUTH_PASSWORD_CHANGED,
            outcome="SUCCESS",
            target_type="accounts.user",
            target_id=locked_user.pk,
            metadata={"method": method},
        )
        create_notification_for_event(
            recipient=locked_user,
            event=NotificationEvent.SECURITY_PASSWORD_CHANGED,
            source_type="audit_event",
            source_id=audit_event.pk,
            target_type="ACCOUNT_SECURITY",
            target_id=locked_user.pk,
        )

    return PasswordChangeResult(
        changed=True,
        method=method,
        invalidation=invalidation,
    )


__all__ = [
    "PasswordChangeAuthenticationFailed",
    "PasswordChangeError",
    "PasswordChangeResult",
    "PasswordChangeStrongAuthRequired",
    "change_password",
]
