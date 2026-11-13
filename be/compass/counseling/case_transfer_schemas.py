"""Canonical, audience-bounded case continuity contract."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from .case_handoff_models import CaseHandoffState, CaseHandoffUnavailableReason
from .case_models import CounselingCaseStatus
from .case_transfer_models import (
    CaseAppointmentDisposition,
    CaseAppointmentRetentionReason,
    CaseArrangementDecisionReason,
    CaseAuthorizationRoute,
    CaseCommunicationDeferral,
    CaseContinuityReason,
    CaseOfficePreparationReason,
    CaseStudentCommunication,
    CaseTaskDisposition,
)


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CaseArrangementStatus(StrEnum):
    PREPARED = "PREPARED"
    AUTHORIZED = "AUTHORIZED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class CaseContinuityPerson(StrictSchema):
    id: UUID
    display_name: str


class CaseContinuityIdentity(StrictSchema):
    id: UUID
    reference_code: str
    student: CaseContinuityPerson
    primary_counselor: CaseContinuityPerson
    status: CounselingCaseStatus
    version: int


class CaseTransferReceiverOption(StrictSchema):
    person: CaseContinuityPerson
    authorization_route: CaseAuthorizationRoute | None
    blocked_reason: str | None


class CaseTransferTaskContext(StrictSchema):
    task_id: UUID
    version: int
    category: str
    source_kind: str | None
    due_at: datetime
    assignee: CaseContinuityPerson
    title: str | None
    allowed_dispositions: list[CaseTaskDisposition]
    record_accessible: bool


class CaseTransferAppointmentContext(StrictSchema):
    link_id: UUID
    appointment_id: UUID
    reference_code: str
    starts_at: datetime
    ends_at: datetime
    status: str
    provider: CaseContinuityPerson
    record_accessible: bool


class CaseTransferContextResponse(StrictSchema):
    case: CaseContinuityIdentity
    office_prepared: bool
    receiver_options: list[CaseTransferReceiverOption]
    tasks: list[CaseTransferTaskContext]
    appointments: list[CaseTransferAppointmentContext]


class CaseTransferTaskPlanInput(StrictSchema):
    task_id: UUID
    expected_version: int = Field(ge=1)
    disposition: CaseTaskDisposition
    successor_title: str | None = Field(default=None, min_length=1, max_length=120)
    successor_due_at: datetime | None = None


class CaseTransferAppointmentPlanInput(StrictSchema):
    link_id: UUID
    disposition: CaseAppointmentDisposition
    retention_reason: CaseAppointmentRetentionReason | None = None


class CaseHandoffSections(StrictSchema):
    context_and_purpose: str = Field(max_length=12000)
    support_and_progress: str = Field(max_length=12000)
    continuing_considerations: str = Field(max_length=12000)
    receiver_next_steps: str = Field(max_length=12000)


class CaseHandoffMetadata(StrictSchema):
    id: UUID
    version: int
    state: CaseHandoffState
    author: CaseContinuityPerson
    submitted_at: datetime | None
    received_at: datetime | None


class CaseHandoffExceptionMetadata(StrictSchema):
    reason: CaseHandoffUnavailableReason
    recorded_by: CaseContinuityPerson
    recorded_at: datetime


class CaseTransferPrepareRequest(StrictSchema):
    expected_case_version: int = Field(ge=1)
    receiving_counselor_id: UUID
    reason: CaseContinuityReason
    office_preparation_reason: CaseOfficePreparationReason | None = None
    tasks: list[CaseTransferTaskPlanInput] = Field(default_factory=list, max_length=2000)
    appointments: list[CaseTransferAppointmentPlanInput] = Field(
        default_factory=list, max_length=2000
    )
    student_communication: CaseStudentCommunication = CaseStudentCommunication.NO
    student_informed_at: datetime | None = None
    communication_deferral_reason: CaseCommunicationDeferral | None = None
    communication_next_action: str | None = Field(default=None, min_length=1, max_length=120)
    communication_due_at: datetime | None = None
    handoff_sections: CaseHandoffSections | None = None


class CaseTransferUpdateRequest(CaseTransferPrepareRequest):
    expected_version: int = Field(ge=1)


class CaseTransferVersionRequest(StrictSchema):
    expected_version: int = Field(ge=1)


class CaseTransferDecisionRequest(CaseTransferVersionRequest):
    reason: CaseArrangementDecisionReason


class CaseTransferTaskPlanResponse(StrictSchema):
    task_id: UUID
    category: str
    source_kind: str | None
    due_at: datetime
    assignee: CaseContinuityPerson
    disposition: CaseTaskDisposition
    successor_due_at: datetime | None
    successor_title: str | None
    title: str | None
    record_accessible: bool


class CaseTransferAppointmentPlanResponse(CaseTransferAppointmentContext):
    disposition: CaseAppointmentDisposition
    retention_reason: CaseAppointmentRetentionReason | None


class CaseTransferSummary(StrictSchema):
    id: UUID
    reference_code: str
    state: CaseArrangementStatus
    version: int
    receiving_counselor: CaseContinuityPerson
    waiting_for: str | None
    review_expires_at: datetime | None
    independent_authorization: bool
    authorization_route: CaseAuthorizationRoute | None
    needs_new_arrangement: bool


class CaseTransferHistoryResponse(StrictSchema):
    id: UUID
    transfer_id: UUID
    reference_code: str
    kind: str
    version: int
    actor: CaseContinuityPerson
    occurred_at: datetime
    independent_authorization: bool
    authorization_route: CaseAuthorizationRoute | None


class CaseResponsibilityResponse(StrictSchema):
    counselor: CaseContinuityPerson
    started_at: datetime
    ended_at: datetime | None
    transfer_id: UUID | None
    derived_opening: bool


class CaseContinuityPanelResponse(StrictSchema):
    transfers: list[CaseTransferSummary]
    responsibility: list[CaseResponsibilityResponse]
    history: list[CaseTransferHistoryResponse]
    can_transfer: bool


class CaseTransferDetailResponse(CaseTransferSummary):
    handoff: CaseHandoffMetadata | None
    handoff_exception: CaseHandoffExceptionMetadata | None
    handoff_ready: bool
    handoff_required: bool
    can_write_handoff: bool
    can_read_handoff: bool
    can_record_handoff_exception: bool
    case: CaseContinuityIdentity
    outgoing_counselor: CaseContinuityPerson
    prepared_by: CaseContinuityPerson
    office_prepared: bool
    reason: CaseContinuityReason
    office_preparation_reason: CaseOfficePreparationReason | None
    authorized_by: CaseContinuityPerson | None
    authorized_at: datetime | None
    decided_by: CaseContinuityPerson | None
    decided_at: datetime | None
    decision_reason: CaseArrangementDecisionReason | None
    student_communication: CaseStudentCommunication
    student_informed_at: datetime | None
    communication_recorded_by: CaseContinuityPerson
    communication_deferral_reason: CaseCommunicationDeferral | None
    communication_task_id: UUID | None
    communication_responsible: CaseContinuityPerson | None
    tasks: list[CaseTransferTaskPlanResponse]
    appointments: list[CaseTransferAppointmentPlanResponse]
    history: list[CaseTransferHistoryResponse]
    review_accessible: bool
    can_edit: bool
    can_submit: bool
    can_authorize: bool
    can_accept: bool
    can_decline: bool
    can_cancel: bool
    can_open_case: bool


class CaseContinuityLookupPage(StrictSchema):
    items: list[CaseContinuityIdentity]
    page: int
    page_size: int
    has_next: bool
