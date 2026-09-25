"""Strict API schemas for the Portal Overview summary."""

from __future__ import annotations

from datetime import datetime

from ninja import Schema
from pydantic import ConfigDict


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class OverviewStudentSummary(StrictSchema):
    upcoming_appointments_count: int | None
    routine_intake_draft_count: int | None
    good_moral_requested_count: int | None
    active_call_slip_count: int | None


class OverviewGuidanceSummary(StrictSchema):
    upcoming_self_appointments_count: int | None
    upcoming_managed_appointments_count: int | None
    routine_evaluation_pending_count: int | None
    good_moral_requested_count: int | None
    active_call_slip_count: int | None


class OverviewPlatformSummary(StrictSchema):
    email_pending_count: int | None
    email_due_pending_count: int | None
    email_failed_count: int | None
    email_sent_today_count: int | None


class OverviewPrivacySummary(StrictSchema):
    open_review_count: int | None
    active_incident_count: int | None


class OverviewSummaryResponse(StrictSchema):
    generated_at: datetime
    student: OverviewStudentSummary | None
    guidance: OverviewGuidanceSummary | None
    platform: OverviewPlatformSummary | None
    privacy: OverviewPrivacySummary | None
