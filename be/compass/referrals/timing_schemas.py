"""Canonical scheduling supplement contracts, separate from the institutional form."""

from datetime import date as CivilDate
from datetime import datetime, time
from enum import StrEnum
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from .models import ReferralSubmissionChannel
from .timing_models import (
    ReferralTimingAnswer,
    ReferralTimingSource,
    ReferralTimingVerificationAnswer,
)
from .timing_rules import (
    ReferralTimingInformationType,
    ReferralTimingPattern,
    ReferralTimingWeekday,
)


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ReferralTimingStatus(StrEnum):
    NOT_PROVIDED = "NOT_PROVIDED"
    UNKNOWN = "UNKNOWN"
    KNOWN = "KNOWN"


class ReferralTimingWindowRequest(StrictSchema):
    information_type: ReferralTimingInformationType
    pattern: ReferralTimingPattern
    date: CivilDate | None = None
    weekday: ReferralTimingWeekday | None = None
    valid_until: CivilDate | None = None
    start_time: time
    end_time: time


class ReferralSchedulingStatementRequest(StrictSchema):
    answer_kind: ReferralTimingAnswer
    windows: list[ReferralTimingWindowRequest] = Field(default_factory=list, max_length=5)
    note: str = Field(default="", max_length=500)


class ReferralTimingWindowResponse(ReferralTimingWindowRequest):
    expired: bool


class ReferralSchedulingStatementResponse(StrictSchema):
    id: UUID
    answer_kind: ReferralTimingAnswer
    windows: list[ReferralTimingWindowResponse]
    note: str
    submission_channel: ReferralSubmissionChannel
    author_id: UUID
    author_name: str
    created_at: datetime


class ReferralTimingVerificationRequest(StrictSchema):
    expected_latest_verification_id: UUID | None
    expected_referral_updated_at: datetime
    answer_kind: ReferralTimingVerificationAnswer
    confirmation_source: ReferralTimingSource
    windows: list[ReferralTimingWindowRequest] = Field(default_factory=list, max_length=5)
    note: str = Field(default="", max_length=500)


class ReferralSchedulingVerificationResponse(StrictSchema):
    id: UUID
    answer_kind: ReferralTimingVerificationAnswer
    confirmation_source: ReferralTimingSource
    windows: list[ReferralTimingWindowResponse]
    note: str
    author_id: UUID
    author_name: str
    created_at: datetime


class ReferralTimingResponse(StrictSchema):
    referral_id: UUID
    timing_status: ReferralTimingStatus
    reported: ReferralSchedulingStatementResponse | None
    verifications: list[ReferralSchedulingVerificationResponse]
    latest_verification_id: UUID | None
    referral_updated_at: str = Field(
        description=(
            "Exact ISO-8601 Referral version timestamp, including microseconds. "
            "Return this value unchanged as expected_referral_updated_at when verifying."
        )
    )
    referral_closed: bool
    can_verify: bool
