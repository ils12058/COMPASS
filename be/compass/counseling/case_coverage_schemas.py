"""Case coverage review carries selected task metadata, never another source's body."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .case_coverage_models import CaseCoverageReturnPlan
from .case_transfer_models import (
    CaseArrangementDecisionReason,
    CaseCommunicationDeferral,
    CaseContinuityReason,
    CaseOfficePreparationReason,
    CaseStudentCommunication,
)
from .case_transfer_schemas import (
    CaseContinuityIdentity,
    CaseContinuityPerson,
    CaseCoverageHistoryResponse,
    CaseCoverageSummary,
    CaseTransferReceiverOption,
    StrictSchema,
)


class CaseCoverageTaskContext(StrictSchema):
    task_id: UUID
    version: int
    category: str
    source_kind: str | None
    due_at: datetime
    assignee: CaseContinuityPerson
    title: str | None
    record_accessible: bool
    can_delegate: bool
    blocked_reason: str | None


class CaseCoverageContextResponse(StrictSchema):
    case: CaseContinuityIdentity
    office_prepared: bool
    receiver_options: list[CaseTransferReceiverOption]
    tasks: list[CaseCoverageTaskContext]


class CaseCoverageTaskInput(StrictSchema):
    task_id: UUID
    expected_version: int = Field(ge=1)
    return_plan: CaseCoverageReturnPlan


class CaseCoveragePrepareRequest(StrictSchema):
    expected_case_version: int = Field(ge=1)
    receiving_counselor_id: UUID
    reason: CaseContinuityReason
    office_preparation_reason: CaseOfficePreparationReason | None = None
    starts_at: datetime
    expires_at: datetime
    tasks: list[CaseCoverageTaskInput] = Field(default_factory=list, max_length=2000)
    student_communication: CaseStudentCommunication = CaseStudentCommunication.NO
    student_informed_at: datetime | None = None
    communication_deferral_reason: CaseCommunicationDeferral | None = None
    communication_next_action: str | None = Field(default=None, min_length=1, max_length=120)
    communication_due_at: datetime | None = None


class CaseCoverageUpdateRequest(CaseCoveragePrepareRequest):
    expected_version: int = Field(ge=1)


class CaseCoverageVersionRequest(StrictSchema):
    expected_version: int = Field(ge=1)


class CaseCoverageDecisionRequest(CaseCoverageVersionRequest):
    reason: CaseArrangementDecisionReason


class CaseCoverageTaskResponse(StrictSchema):
    task_id: UUID
    category: str
    source_kind: str | None
    due_at: datetime
    assigned_counselor: CaseContinuityPerson
    return_plan: CaseCoverageReturnPlan
    title: str | None
    record_accessible: bool
    returned_at: datetime | None
    returned_by: CaseContinuityPerson | None
    recovery_required: bool


class CaseCoverageDetailResponse(CaseCoverageSummary):
    case: CaseContinuityIdentity
    primary_counselor: CaseContinuityPerson
    prepared_by: CaseContinuityPerson
    office_prepared: bool
    reason: CaseContinuityReason
    office_preparation_reason: CaseOfficePreparationReason | None
    authorized_by: CaseContinuityPerson | None
    authorized_at: datetime | None
    decided_by: CaseContinuityPerson | None
    decided_at: datetime | None
    decision_reason: CaseArrangementDecisionReason | None
    revoked_by: CaseContinuityPerson | None
    revoked_at: datetime | None
    revocation_reason: CaseArrangementDecisionReason | None
    student_communication: CaseStudentCommunication
    student_informed_at: datetime | None
    communication_recorded_by: CaseContinuityPerson
    communication_deferral_reason: CaseCommunicationDeferral | None
    communication_task_id: UUID | None
    communication_responsible: CaseContinuityPerson | None
    tasks: list[CaseCoverageTaskResponse]
    history: list[CaseCoverageHistoryResponse]
    review_accessible: bool
    can_edit: bool
    can_submit: bool
    can_authorize: bool
    can_accept: bool
    can_decline: bool
    can_cancel: bool
    can_revoke: bool
    can_open_case: bool
    can_arrange_transfer: bool
