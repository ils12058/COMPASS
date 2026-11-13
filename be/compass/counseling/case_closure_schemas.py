"""Canonical closure review and deliberate lifecycle requests."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from compass.guidance_followups.api import Category, SourceKind

from .case_closure_models import CaseClosureOutcome, CaseClosureReason, CaseReopenReason


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CaseClosureBlockerKind(StrEnum):
    TRANSFER = "TRANSFER"
    COVERAGE = "COVERAGE"
    DELEGATED_TASK = "DELEGATED_TASK"
    APPOINTMENT = "APPOINTMENT"
    TASK = "TASK"


class CaseClosurePerson(StrictSchema):
    id: UUID
    display_name: str


class CaseClosureResponse(StrictSchema):
    id: UUID
    closed_at: datetime
    closed_by: CaseClosurePerson
    reason: CaseClosureReason
    outcome: CaseClosureOutcome
    # Confidential, only in the current owner's protected detail; absent from list/history.
    note: str | None
    reopened_at: datetime | None
    reopened_by: CaseClosurePerson | None
    reopen_reason: CaseReopenReason | None


class CaseClosureArrangement(StrictSchema):
    id: UUID
    reference_code: str
    state: str


class CaseClosureAppointment(StrictSchema):
    id: UUID
    reference_code: str
    starts_at: datetime
    ends_at: datetime


class CaseClosureTask(StrictSchema):
    id: UUID
    student_id: UUID
    category: Category
    source_kind: SourceKind | None
    source_id: UUID | None
    title: str | None
    assigned_to_id: UUID
    assigned_to_name: str
    due_at: datetime
    version: int
    post_closure_designated_at: datetime | None
    can_designate: bool


class CaseClosureContextResponse(StrictSchema):
    case_id: UUID
    version: int
    blockers: list[CaseClosureBlockerKind]
    transfers: list[CaseClosureArrangement]
    coverages: list[CaseClosureArrangement]
    delegated_task_ids: list[UUID]
    appointments: list[CaseClosureAppointment]
    tasks: list[CaseClosureTask]
    can_close: bool


class CaseCloseRequest(StrictSchema):
    expected_version: int = Field(ge=1)
    reason: CaseClosureReason
    outcome: CaseClosureOutcome
    note: str | None = Field(default=None, max_length=4000)


class CaseReopenRequest(StrictSchema):
    expected_version: int = Field(ge=1)
    reason: CaseReopenReason


class CasePostClosureTaskRequest(StrictSchema):
    expected_version: int = Field(ge=1)
    expected_task_version: int = Field(ge=1)
    administrative_action: Literal[True]
    assigned_to_id: UUID
    due_at: datetime
