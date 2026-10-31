"""Protected GCO-only metadata/transition contracts over canonical Referral facts."""

from datetime import datetime
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict, Field, field_validator

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.referrals.administration import get_administration, transition
from compass.referrals.administrative_policy import AdministrativeReferralError
from compass.referrals.administrative_state import FacultyReferralSubmissionState
from compass.referrals.api import _raise, _require
from compass.referrals.errors import ReferralError

router = Router(tags=["referrals"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ReferralAdministrativeActor(StrictSchema):
    id: UUID
    display_name: str


class ReferralAdministrationResponse(StrictSchema):
    referral_id: UUID
    version: int
    state: FacultyReferralSubmissionState | None
    submitted_at: datetime
    submitted_by: ReferralAdministrativeActor
    faculty_home_college: str
    student_college_at_submission: str
    received_at: datetime | None
    acknowledged_by: ReferralAdministrativeActor | None
    closed_at: datetime | None
    closed_by: ReferralAdministrativeActor | None
    can_acknowledge: bool
    can_close: bool
    valid_until: datetime | None


class ReferralAcknowledgmentRequest(StrictSchema):
    expected_version: int = Field(ge=1, strict=True)


class ReferralAdministrativeClosureRequest(ReferralAcknowledgmentRequest):
    obligations_reviewed: bool = Field(strict=True)

    @field_validator("obligations_reviewed")
    @classmethod
    def review_required(cls, value):
        if value is not True:
            raise ValueError("Administrative obligations must be reviewed.")
        return value


def _error(exc):
    if isinstance(exc, AdministrativeReferralError):
        raise APIError(exc.status, exc.code, str(exc)) from exc
    _raise(exc)


@router.get(
    "/{referral_id}/administration",
    auth=session_auth,
    response=response_with_errors(ReferralAdministrationResponse, 401, 403, 404, 422),
    operation_id="referralsGetAdministration",
)
def referrals_get_administration(request, referral_id: UUID):
    _require(request, "referrals.view")
    try:
        return get_administration(
            actor=request.auth_user, actor_session=request.auth_session, referral_id=referral_id
        )
    except ReferralError as exc:
        _error(exc)


def _transition(request, referral_id, expected_version, kind, obligations_reviewed=False):
    _require(request, "referrals.manage")
    try:
        return transition(
            actor=request.auth_user,
            actor_session=request.auth_session,
            referral_id=referral_id,
            expected_version=expected_version,
            kind=kind,
            obligations_reviewed=obligations_reviewed,
            context=AuditContext.from_request(request, actor=request.auth_user),
        )
    except ReferralError as exc:
        _error(exc)


@router.post(
    "/{referral_id}/acknowledgment",
    auth=session_auth,
    response=response_with_errors(ReferralAdministrationResponse, 401, 403, 404, 409, 422),
    operation_id="referralsAcknowledge",
)
def referrals_acknowledge(request, referral_id: UUID, payload: ReferralAcknowledgmentRequest):
    return _transition(request, referral_id, payload.expected_version, "ACKNOWLEDGMENT")


@router.post(
    "/{referral_id}/administrative-closure",
    auth=session_auth,
    response=response_with_errors(ReferralAdministrationResponse, 401, 403, 404, 409, 422),
    operation_id="referralsCloseAdministratively",
)
def referrals_close_administratively(
    request, referral_id: UUID, payload: ReferralAdministrativeClosureRequest
):
    return _transition(
        request, referral_id, payload.expected_version, "CLOSURE", payload.obligations_reviewed
    )
