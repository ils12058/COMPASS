"""Public recovery API; credentials travel only in POST bodies."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import Field

from compass.authentication.abuse import AuthenticationRateLimited
from compass.authentication.api import (
    PasswordAccessConfirmResponse,
    PasswordAccessRequest,
    StrictSchema,
    _raise_password_policy,
    _raise_rate_limited,
    _raise_security_unavailable,
    _require_csrf,
)
from compass.authentication.password_access import PasswordPolicyRejected
from compass.authentication.recovery_links import (
    LINK_INVALID_MESSAGE,
    RecoveryLinkConflict,
    RecoveryLinkInputInvalid,
    RecoveryLinkInvalid,
    RecoveryLinkPermissionDenied,
    RecoveryLinkSelfTarget,
    RecoveryLinkVerificationFailed,
    confirm_recovery_link,
    request_password_reset_link,
    verify_recovery_link,
)
from compass.authentication.sessions import RecentMFARequired
from compass.authentication.step_up import step_up_api_error
from compass.common.api import response_with_errors
from compass.common.errors import APIError

router = Router(tags=["auth"])


class IdentityCheckCode(StrEnum):
    IN_PERSON_ID = "in_person_id"
    OTHER = "other"


class AssistedRecoveryRequest(StrictSchema):
    new_email: str
    identity_check_basis: IdentityCheckCode
    identity_check_reason: str = Field(default="", max_length=240)
    expected_updated_at: datetime
    turnstile_token: str | None = None


class AssistedRecoveryResponse(Schema):
    request_id: UUID
    expires_at: datetime


class PasswordLinkRequestResponse(Schema):
    message: str


class RecoveryLinkVerifyRequest(StrictSchema):
    token: str = Field(max_length=256, repr=False)


class RecoveryLinkConfirmRequest(RecoveryLinkVerifyRequest):
    new_password: str = Field(repr=False)


class RecoveryLinkVerifyResponse(Schema):
    valid: bool
    masked_email: str
    email_change: bool


def raise_recovery_link_error(exc):
    if isinstance(exc, RecentMFARequired):
        raise step_up_api_error(exc) from exc
    if isinstance(exc, AuthenticationRateLimited):
        _raise_rate_limited(exc)
    if isinstance(exc, PasswordPolicyRejected):
        _raise_password_policy(exc)
    if isinstance(exc, RecoveryLinkInvalid):
        raise APIError(400, "account_recovery_invalid", LINK_INVALID_MESSAGE) from None
    if isinstance(exc, RecoveryLinkInputInvalid):
        raise APIError(422, "invalid_account_recovery_request", str(exc)) from None
    if isinstance(exc, RecoveryLinkConflict):
        raise APIError(409, "account_recovery_conflict", str(exc)) from None
    if isinstance(exc, RecoveryLinkSelfTarget):
        raise APIError(
            403, "self_target_forbidden", "You cannot recover your own account here."
        ) from None
    if isinstance(exc, RecoveryLinkPermissionDenied):
        raise APIError(
            403, "permission_denied", "You don't have permission to manage accounts."
        ) from None
    if isinstance(exc, RecoveryLinkVerificationFailed):
        raise APIError(
            403,
            "security_verification_failed",
            "Couldn't complete the security verification. Try again.",
        ) from None
    # Do not include unexpected exception details: they may hold the submitted secret.
    _raise_security_unavailable(exc)


@router.post(
    "/password-link/request",
    response=response_with_errors(
        PasswordLinkRequestResponse, 400, 403, 422, 429, 503, success_status=202
    ),
    operation_id="authRequestPasswordLink",
    summary="Request an expiring password link",
    description=(
        "Same response for active, disabled, and unknown accounts. Keeps "
        "email-request limits and Turnstile."
    ),
)
def password_link_request(request, payload: PasswordAccessRequest):
    _require_csrf(request)
    try:
        message = request_password_reset_link(
            email=payload.email, request=request, turnstile_token=payload.turnstile_token
        )
    except Exception as exc:
        raise_recovery_link_error(exc)
    return Status(202, {"message": message})


@router.post(
    "/account-recovery/verify",
    response=response_with_errors(RecoveryLinkVerifyResponse, 400, 403, 422, 429, 503),
    operation_id="authVerifyRecoveryLink",
    summary="Check an account recovery link",
    description=(
        "Does not consume the link. Invalid, expired, used, and changed-account links "
        "share one error."
    ),
)
def recovery_link_verify(request, payload: RecoveryLinkVerifyRequest):
    _require_csrf(request)
    try:
        return verify_recovery_link(token=payload.token, request=request)
    except Exception as exc:
        raise_recovery_link_error(exc)


@router.post(
    "/account-recovery/confirm",
    response=response_with_errors(PasswordAccessConfirmResponse, 400, 403, 422, 429, 503),
    operation_id="authConfirmRecoveryLink",
    summary="Set a password using a recovery link",
    description=(
        "Atomically consumes the link, verifies the destination email, and revokes "
        "all reusable sign-ins. Existing authenticators are preserved. No sign-in "
        "session is created."
    ),
)
def recovery_link_confirm(request, payload: RecoveryLinkConfirmRequest):
    _require_csrf(request)
    try:
        return confirm_recovery_link(
            token=payload.token, new_password=payload.new_password, request=request
        )
    except Exception as exc:
        raise_recovery_link_error(exc)
