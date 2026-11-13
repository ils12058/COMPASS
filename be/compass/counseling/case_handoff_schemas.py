"""Structured narrative and read-only work; incoming clients cannot write the work snapshot."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .case_handoff_models import CaseHandoffState, CaseHandoffUnavailableReason
from .case_transfer_schemas import (
    CaseAppointmentDisposition,
    CaseContinuityPerson,
    CaseHandoffSections,
    CaseTaskDisposition,
    StrictSchema,
)


class CaseHandoffSaveRequest(StrictSchema):
    expected_transfer_version: int = Field(ge=1)
    expected_handoff_version: int | None = Field(default=None, ge=1)
    sections: CaseHandoffSections


class CaseHandoffSubmitRequest(StrictSchema):
    expected_transfer_version: int = Field(ge=1)
    expected_handoff_version: int = Field(ge=1)


class CaseHandoffAddendumRequest(StrictSchema):
    expected_transfer_version: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=12000)


class CaseHandoffExceptionRequest(StrictSchema):
    expected_transfer_version: int = Field(ge=1)
    reason: CaseHandoffUnavailableReason


class CaseHandoffActionWork(StrictSchema):
    task_id: UUID
    category: str
    source_kind: str | None
    disposition: CaseTaskDisposition
    due_at: datetime
    responsible: CaseContinuityPerson


class CaseHandoffAppointmentWork(StrictSchema):
    appointment_id: UUID
    reference_code: str
    starts_at: datetime
    ends_at: datetime
    disposition: CaseAppointmentDisposition
    responsible: CaseContinuityPerson


class CaseHandoffWork(StrictSchema):
    tasks: list[CaseHandoffActionWork] = Field(max_length=2000)
    appointments: list[CaseHandoffAppointmentWork] = Field(max_length=2000)


class CaseHandoffAddendumResponse(StrictSchema):
    id: UUID
    author: CaseContinuityPerson
    created_at: datetime
    content: str


class CaseHandoffBodyResponse(StrictSchema):
    id: UUID
    version: int
    state: CaseHandoffState
    author: CaseContinuityPerson
    submitted_at: datetime | None
    transfer_version: int
    sections: CaseHandoffSections
    work: CaseHandoffWork
    addenda: list[CaseHandoffAddendumResponse]
    addenda_page: int
    addenda_has_next: bool
    can_edit: bool
    can_addendum: bool
