"""Student self-service and Guidance operational API for Good Moral certificates."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Header, Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import request_fingerprint
from compass.documents.filenames import institutional_pdf_content_disposition
from compass.institutional_forms.filter_options import (
    CollectionFilterOptions,
    project_filter_options,
)
from compass.organization.canonical import CANONICAL_CAMPUSES, AcademicClassification
from compass.privacy_governance.releases import (
    ReleaseAuditUnavailable,
    record_good_moral_release,
)

from .models import GoodMoralInitiationOrigin, GoodMoralStatus, GoodMoralVariant
from .services import (
    DEFAULT_PAGE_SIZE,
    GoodMoralAffiliationRequired,
    GoodMoralCertificateDateInFuture,
    GoodMoralConfigurationConflict,
    GoodMoralConflict,
    GoodMoralCreationConflict,
    GoodMoralCurrentStudentRequired,
    GoodMoralDocumentUnavailable,
    GoodMoralError,
    GoodMoralExitInterviewRequired,
    GoodMoralF4AcademicEligibilityRequired,
    GoodMoralInventoryRequired,
    GoodMoralNotFound,
    GoodMoralNotPermitted,
    GoodMoralNotReady,
    GoodMoralOrdering,
    GoodMoralPreparationChanged,
    InvalidGoodMoralInput,
    cancel_request,
    correction_fields,
    create_assisted_request,
    create_my_current_student,
    create_my_graduate,
    get_f4_academic_context,
    get_mine,
    get_request,
    issue_request,
    list_eligible_students,
    list_mine,
    list_requests,
    prepare_request,
    render_certificate_pdf,
    update_request,
)

router = Router(tags=["good-moral"])

CURRENT_STUDENT_CREATE_ROUTE = "/api/v1/good-moral/me/requests/current-student"
GRADUATE_CREATE_ROUTE = "/api/v1/good-moral/me/requests/graduate"

PDF_SUCCESS_OPENAPI = {
    "responses": {
        200: {
            "content": {
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"},
                }
            }
        }
    }
}


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class GoodMoralVariantValue(StrEnum):
    CURRENT_STUDENT = GoodMoralVariant.CURRENT_STUDENT
    GRADUATE = GoodMoralVariant.GRADUATE


class GoodMoralStatusValue(StrEnum):
    REQUESTED = GoodMoralStatus.REQUESTED
    READY_FOR_ISSUANCE = GoodMoralStatus.READY_FOR_ISSUANCE
    ISSUED = GoodMoralStatus.ISSUED
    CANCELLED = GoodMoralStatus.CANCELLED


class CurrentStudentRequestPayload(StrictSchema):
    year_level: str | None = None
    semester: str


class GraduateRequestPayload(StrictSchema):
    degree: str
    major: str = ""
    graduation_date: date


class AssistedCurrentStudentRequestPayload(CurrentStudentRequestPayload):
    student_id: UUID


class AssistedGraduateRequestPayload(GraduateRequestPayload):
    student_id: UUID


class GoodMoralStudentCollegeResponse(StrictSchema):
    id: UUID
    code: str
    name: str


class GoodMoralF4EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_CURRENT = "NOT_CURRENT"
    INVENTORY_REQUIRED = "INVENTORY_REQUIRED"
    UNCLASSIFIED_PROGRAM = "UNCLASSIFIED_PROGRAM"
    POSTGRADUATE_PROGRAM = "POSTGRADUATE_PROGRAM"
    UNSUPPORTED_YEAR_LEVEL = "UNSUPPORTED_YEAR_LEVEL"


class GoodMoralF4AcademicContextResponse(StrictSchema):
    status: GoodMoralF4EligibilityStatus
    academic_classification: AcademicClassification | None = None
    year_level: int | None = None


class GoodMoralDegreeOptionsResponse(StrictSchema):
    items: list[str]


class GoodMoralStudentOptionResponse(StrictSchema):
    id: UUID
    display_name: str
    institutional_id: str | None
    college: GoodMoralStudentCollegeResponse | None
    variant: GoodMoralVariantValue
    f4_eligibility: GoodMoralF4AcademicContextResponse | None = None


class GoodMoralStudentOptionPage(StrictSchema):
    items: list[GoodMoralStudentOptionResponse]
    page: int
    page_size: int
    has_next: bool


class GoodMoralCancellationPayload(StrictSchema):
    reason: str


class GoodMoralPreparationPayload(StrictSchema):
    expected_resource_version: str


class GoodMoralIssuePayload(StrictSchema):
    expected_preparation_version: str
    expected_resource_version: str | None = None
    expected_receipt_revision: UUID | None = None
    expected_receipt_verification: UUID | None = None


class GoodMoralReceiptVerificationPayload(StrictSchema):
    expected_resource_version: str
    assignment_id: UUID
    operation_id: UUID
    method: Literal["PHYSICAL_OR_INSPECTION"]


class GoodMoralCorrectionPayload(StrictSchema):
    applicant_name: str | None = None
    year_level: str | None = None
    college: str | None = None
    course: str | None = None
    major: str | None = None
    semester: str | None = None
    degree: str | None = None
    graduation_date: date | None = None
    expected_resource_version: str | None = None
    expected_receipt_revision: UUID | None = None
    receipt_operation_id: UUID | None = None
    official_receipt_number: str | None = None
    official_receipt_date: date | None = None
    official_receipt_amount: Decimal | None = None


class PersonSummary(StrictSchema):
    id: UUID
    display_name: str


class AcademicYearSummary(StrictSchema):
    id: UUID
    label: str


class FormRevisionSummary(StrictSchema):
    id: UUID
    family_key: str
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class GoodMoralInitiationOriginValue(StrEnum):
    STUDENT_SELF = GoodMoralInitiationOrigin.STUDENT_SELF
    GCO_ASSISTED = GoodMoralInitiationOrigin.GCO_ASSISTED
    LEGACY_UNSPECIFIED = GoodMoralInitiationOrigin.LEGACY_UNSPECIFIED


class GoodMoralSummaryResponse(StrictSchema):
    initiation_origin: GoodMoralInitiationOriginValue
    id: UUID
    variant: GoodMoralVariantValue
    status: GoodMoralStatusValue
    applicant_name: str
    issued_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoodMoralOperationalSummaryResponse(GoodMoralSummaryResponse):
    student_institutional_id: str | None
    official_receipt_number: str
    academic_year: AcademicYearSummary | None
    prepared_at: datetime | None


class GoodMoralDetailResponse(GoodMoralSummaryResponse):
    student: PersonSummary
    graduation_opportunity_id: UUID | None
    exit_interview_id: UUID | None
    exit_interview_submitted_at: datetime | None
    inventory_id: UUID | None
    academic_year: AcademicYearSummary | None
    major: str
    year_level: str
    college: str
    course: str
    semester: str
    degree: str
    graduation_date: date | None
    official_receipt_number: str
    official_receipt_date: date | None
    official_receipt_amount: Decimal | None
    form_revision: FormRevisionSummary | None
    document_template_key: str | None
    document_template_version: int | None
    issued_by: PersonSummary | None
    issued_by_name_snapshot: str


class GoodMoralCancellationSummary(StrictSchema):
    cancelled_by: PersonSummary | None
    reason: str


class GoodMoralActionsResponse(StrictSchema):
    request_version: str
    preparation_version: str | None
    can_prepare: bool
    can_correct: bool
    can_issue: bool
    can_cancel: bool
    can_download: bool
    correction_fields: list[str]


class GoodMoralReceiptHistoryItem(StrictSchema):
    id: UUID
    sequence: int
    change_kind: str
    origin: str
    recorded_at: datetime
    recorded_by_id: UUID | None
    is_current: bool
    closed_at: datetime | None


class GoodMoralReceiptStateResponse(StrictSchema):
    ledger_mode: Literal["DORMANT", "FENCED", "ACTIVE"]
    revision_id: UUID | None
    identity_state: Literal[
        "DORMANT", "ABSENT", "BOUND", "LEGACY_AMBIGUOUS", "DISPUTED", "QUARANTINED"
    ]
    history: list[GoodMoralReceiptHistoryItem]


class GoodMoralReceiptMutationResponse(StrictSchema):
    operation_id: UUID
    result_revision_id: UUID | None
    result_request_version: str


class GoodMoralReceiptInspectionResponse(StrictSchema):
    status: Literal[
        "MISSING",
        "INCOMPLETE",
        "NEEDS_VERIFICATION",
        "VERIFIED",
        "LEGACY_UNKNOWN",
        "LEGACY_CONFLICT",
        "DISPUTED",
        "POLICY_UNAVAILABLE",
    ]
    blocker: str | None
    can_verify: bool
    verification_id: UUID | None
    verified_by_id: UUID | None
    verified_at: datetime | None
    method: Literal["PHYSICAL_OR_INSPECTION"] | None
    expected_amount: Decimal | None
    currency: Literal["PHP"] | None


class GoodMoralReceiptVerificationResult(StrictSchema):
    operation_id: UUID
    verification_id: UUID
    assignment_id: UUID
    invalidated_at: datetime | None


class GoodMoralOperationalDetailResponse(GoodMoralDetailResponse):
    initiated_by: PersonSummary | None
    student_institutional_id: str | None
    cancellation: GoodMoralCancellationSummary | None
    prepared_by: PersonSummary | None
    prepared_at: datetime | None
    actions: GoodMoralActionsResponse
    receipt_identity: GoodMoralReceiptStateResponse | None = None
    receipt_mutation_result: GoodMoralReceiptMutationResponse | None = None
    receipt_inspection: GoodMoralReceiptInspectionResponse | None = None
    receipt_verification_result: GoodMoralReceiptVerificationResult | None = None


class GoodMoralHistoryResponse(StrictSchema):
    items: list[GoodMoralSummaryResponse]


class GoodMoralPageResponse(StrictSchema):
    items: list[GoodMoralOperationalSummaryResponse]
    page: int
    page_size: int
    has_next: bool
    # The ordering applied: the requested one, or the default for the selected status.
    ordering: GoodMoralOrdering
    filter_options: CollectionFilterOptions


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT" or not user.has_capability(capability):
        raise APIError(403, "permission_denied", "Student Good Moral access is required.")


def _require_counselor(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "COUNSELOR" or not user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")


def _require_operational(request, capability: str) -> None:
    user = request.auth_user
    if (
        not user.is_active
        or user.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not user.has_capability(capability)
    ):
        raise APIError(403, "permission_denied", "Guidance Good Moral access is required.")


def _raise(exc: GoodMoralError) -> NoReturn:
    from .receipt_verification import ReceiptBlocked

    if isinstance(exc, ReceiptBlocked):
        raise APIError(409, exc.code, str(exc)) from exc
    from .receipt_identity import (
        ReceiptChanged,
        ReceiptConflict,
        ReceiptCutoverRequired,
        ReceiptOperationConflict,
    )

    for cls, code in (
        (ReceiptConflict, "good_moral_receipt_conflict"),
        (ReceiptChanged, "good_moral_receipt_changed"),
        (ReceiptCutoverRequired, "good_moral_receipt_cutover_required"),
        (ReceiptOperationConflict, "idempotency_key_conflict"),
    ):
        if isinstance(exc, cls):
            raise APIError(409, code, str(exc)) from exc
    if isinstance(exc, GoodMoralNotFound):
        raise APIError(404, "good_moral_not_found", str(exc)) from exc
    if isinstance(exc, GoodMoralNotPermitted):
        raise APIError(403, "permission_denied", str(exc)) from exc
    if isinstance(exc, GoodMoralCurrentStudentRequired):
        raise APIError(409, "current_student_required", str(exc)) from exc
    if isinstance(exc, GoodMoralF4AcademicEligibilityRequired):
        raise APIError(409, "good_moral_f4_academic_eligibility_required", str(exc)) from exc
    if isinstance(exc, GoodMoralExitInterviewRequired):
        raise APIError(409, "good_moral_exit_interview_required", str(exc)) from exc
    if isinstance(exc, GoodMoralInventoryRequired):
        raise APIError(409, "good_moral_inventory_required", str(exc)) from exc
    if isinstance(exc, GoodMoralAffiliationRequired):
        raise APIError(409, "good_moral_affiliation_required", str(exc)) from exc
    if isinstance(exc, GoodMoralConfigurationConflict):
        raise APIError(409, "good_moral_configuration_conflict", str(exc)) from exc
    if isinstance(exc, GoodMoralCreationConflict):
        # Same stable code as the other idempotent creation routes.
        raise APIError(409, "idempotency_key_conflict", str(exc)) from exc
    if isinstance(exc, GoodMoralNotReady):
        raise APIError(409, "good_moral_not_ready", str(exc)) from exc
    if isinstance(exc, GoodMoralPreparationChanged):
        raise APIError(409, "good_moral_preparation_changed", str(exc)) from exc
    if isinstance(exc, GoodMoralCertificateDateInFuture):
        raise APIError(409, "good_moral_certificate_date_in_future", str(exc)) from exc
    if isinstance(exc, GoodMoralConflict):
        raise APIError(409, "good_moral_conflict", str(exc)) from exc
    if isinstance(exc, GoodMoralDocumentUnavailable):
        raise APIError(503, "good_moral_document_unavailable", str(exc)) from exc
    if isinstance(exc, InvalidGoodMoralInput):
        raise APIError(422, "invalid_good_moral_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Good Moral operation could not be completed."
    ) from exc


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "initiation_origin": item.initiation_origin,
        "variant": item.variant,
        "status": item.status,
        "applicant_name": item.applicant_name_snapshot,
        "issued_at": item.issued_at,
        "cancelled_at": item.cancelled_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _operational_summary(item) -> dict[str, object]:
    return {
        **_summary(item),
        "student_institutional_id": item.student.institutional_id,
        "official_receipt_number": item.official_receipt_number,
        "academic_year": {"id": item.academic_year_id, "label": item.academic_year.label}
        if item.academic_year_id
        else None,
        "prepared_at": item.prepared_at,
    }


def _operational_detail(item, actor) -> dict[str, object]:
    from .receipt_identity import operational_receipt_state
    from .receipt_verification import operational_status

    verification = getattr(item, "receipt_verification_result", None)
    operation = getattr(item, "receipt_mutation_result", None)
    cancellation = None
    if item.cancelled_at is not None:
        cancellation = {
            "cancelled_by": _person(item.cancelled_by) if item.cancelled_by_id else None,
            "reason": item.cancellation_reason,
        }
    return {
        **_detail(item),
        "initiated_by": _person(item.initiated_by) if item.initiated_by_id else None,
        "student_institutional_id": item.student.institutional_id,
        "cancellation": cancellation,
        "prepared_by": _person(item.prepared_by) if item.prepared_by_id else None,
        "prepared_at": item.prepared_at,
        "actions": _actions(item, actor),
        "receipt_identity": operational_receipt_state(item),
        "receipt_inspection": operational_status(item, actor),
        "receipt_verification_result": {
            "operation_id": verification.operation_id,
            "verification_id": verification.pk,
            "assignment_id": verification.assignment_id,
            "invalidated_at": verification.invalidated_at,
        }
        if verification
        else None,
        "receipt_mutation_result": {
            "operation_id": operation.pk,
            "result_revision_id": operation.result_revision_id,
            "result_request_version": operation.result_request_version,
        }
        if operation
        else None,
    }


def _actions(item, actor):
    from .receipt_identity import ReceiptCutoverRequired
    from .receipt_verification import ReceiptBlocked, active_mode, gate

    receipt_ready = True
    try:
        if active_mode():
            gate(item)
            receipt_ready = True
    except (ReceiptBlocked, ReceiptCutoverRequired):
        receipt_ready = False
    preparable = item.status in {GoodMoralStatus.REQUESTED, GoodMoralStatus.READY_FOR_ISSUANCE}
    prepare = actor.has_capability("good_moral.prepare")
    counselor = actor.role.code == "COUNSELOR"
    mapping = {
        "applicant_name_snapshot": "applicant_name",
        "year_level_snapshot": "year_level",
        "college_snapshot": "college",
        "course_snapshot": "course",
        "major_snapshot": "major",
        "semester_snapshot": "semester",
        "degree_snapshot": "degree",
    }
    return {
        "request_version": item.updated_at.isoformat(),
        "preparation_version": item.prepared_at.isoformat() if item.prepared_at else None,
        "can_prepare": prepare and receipt_ready and item.status == GoodMoralStatus.REQUESTED,
        "can_correct": prepare and preparable,
        "can_issue": receipt_ready
        and (not active_mode() or item.prepared_receipt_verification_id is not None)
        and counselor
        and actor.has_capability("good_moral.issue")
        and item.status == GoodMoralStatus.READY_FOR_ISSUANCE,
        "can_cancel": counselor and actor.has_capability("good_moral.manage") and preparable,
        "can_download": item.status == GoodMoralStatus.ISSUED,
        "correction_fields": sorted(
            mapping.get(name, name) for name in correction_fields(actor, item)
        )
        if prepare and preparable
        else [],
    }


def _detail(item) -> dict[str, object]:
    revision = item.form_revision
    return {
        **_summary(item),
        "student": _person(item.student),
        "graduation_opportunity_id": item.graduation_opportunity_id,
        "exit_interview_id": item.exit_interview_id,
        "exit_interview_submitted_at": item.exit_interview_submitted_at,
        "inventory_id": item.inventory_id,
        "academic_year": (
            {"id": item.academic_year_id, "label": item.academic_year.label}
            if item.academic_year_id
            else None
        ),
        "major": item.major_snapshot,
        "year_level": item.year_level_snapshot,
        "college": item.college_snapshot,
        "course": item.course_snapshot,
        "semester": item.semester_snapshot,
        "degree": item.degree_snapshot,
        "graduation_date": item.graduation_date,
        "official_receipt_number": item.official_receipt_number,
        "official_receipt_date": item.official_receipt_date,
        "official_receipt_amount": item.official_receipt_amount,
        "form_revision": (
            {
                "id": revision.pk,
                "family_key": revision.family.key,
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "internal_schema_version": revision.internal_schema_version,
            }
            if revision is not None
            else None
        ),
        "document_template_key": item.document_template_key,
        "document_template_version": item.document_template_version,
        "issued_by": _person(item.issued_by) if item.issued_by_id else None,
        "issued_by_name_snapshot": item.issued_by_name_snapshot,
    }


def _correction_values(payload: GoodMoralCorrectionPayload) -> dict[str, object]:
    values = payload.model_dump(
        exclude_unset=True,
        exclude={"expected_resource_version", "expected_receipt_revision", "receipt_operation_id"},
    )
    mapping = {
        "applicant_name": "applicant_name_snapshot",
        "year_level": "year_level_snapshot",
        "college": "college_snapshot",
        "course": "course_snapshot",
        "major": "major_snapshot",
        "semester": "semester_snapshot",
        "degree": "degree_snapshot",
    }
    return {mapping.get(name, name): value for name, value in values.items()}


def _pdf_response(
    item,
    *,
    context: AuditContext,
    access_mode: str,
) -> HttpResponse:
    try:
        pdf_bytes = render_certificate_pdf(item)
    except GoodMoralError as exc:
        _raise(exc)
    try:
        record_good_moral_release(
            context=context,
            request_id=item.pk,
            variant=item.variant,
            access_mode=access_mode,
        )
    except ReleaseAuditUnavailable as exc:
        raise APIError(
            503,
            "release_audit_unavailable",
            (
                "The certificate could not be released because its required privacy audit "
                "is unavailable."
            ),
        ) from exc
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = institutional_pdf_content_disposition("good_moral", item.pk)
    return response


def _f4_academic_context_response(student) -> dict[str, object]:
    context = get_f4_academic_context(student)
    return {
        "status": context.status,
        "academic_classification": context.academic_classification,
        "year_level": context.year_level,
    }


def _require_degree_options_access(request) -> None:
    user = request.auth_user
    if (
        user.is_active
        and user.role.code == "STUDENT"
        and user.has_capability("good_moral.request_self")
    ):
        return
    if (
        user.is_active
        and user.role.code in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        and (
            user.has_capability("good_moral.initiate") or user.has_capability("good_moral.prepare")
        )
    ):
        return
    raise APIError(403, "permission_denied", "Good Moral degree suggestions are unavailable.")


# Static operational routes precede UUID detail routes.
@router.get(
    "/degree-options",
    response=response_with_errors(GoodMoralDegreeOptionsResponse, 401, 403),
    auth=session_auth,
    operation_id="goodMoralListDegreeOptions",
)
def good_moral_degree_options(request):
    _require_degree_options_access(request)
    items = sorted(
        {
            program.name
            for campus in CANONICAL_CAMPUSES
            for college in campus.colleges
            for program in college.programs
            if program.active
            and program.academic_classification == AcademicClassification.BACHELORS
        }
    )
    return {"items": items}


@router.get(
    "/student-options",
    response=response_with_errors(GoodMoralStudentOptionPage, 401, 403, 422),
    auth=session_auth,
    operation_id="goodMoralListEligibleStudents",
)
def good_moral_student_options(
    request, search: str | None = None, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
):
    _require_operational(request, "good_moral.initiate")
    try:
        rows, has_next = list_eligible_students(
            actor=request.auth_user,
            search=search,
            page=page,
            page_size=page_size,
        )
    except GoodMoralError as exc:
        _raise(exc)
    items = []
    for student in rows:
        affiliation = getattr(student, "organization_student_affiliation", None)
        college = affiliation.college if affiliation else None
        items.append(
            {
                "id": student.pk,
                "display_name": student.get_full_name(),
                "institutional_id": student.institutional_id,
                "college": {"id": college.pk, "code": college.code, "name": college.name}
                if college and college.is_active and college.campus.is_active
                else None,
                "variant": GoodMoralVariant.CURRENT_STUDENT
                if student.student_lifecycle_status == "CURRENT"
                else GoodMoralVariant.GRADUATE,
                "f4_eligibility": (
                    _f4_academic_context_response(student)
                    if student.student_lifecycle_status == "CURRENT"
                    else None
                ),
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "has_next": has_next}


def _assisted_create(request, payload, variant, route, key):
    _require_operational(request, "good_moral.initiate")
    values = payload.model_dump()
    student_id = values.pop("student_id")
    try:
        item = create_assisted_request(
            actor=request.auth_user,
            student_id=student_id,
            variant=variant,
            details=values,
            idempotency_key=key,
            request_fingerprint=request_fingerprint(
                method="POST",
                route=route,
                query_string=request.META.get("QUERY_STRING", ""),
                body=request.body,
            ),
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return Status(201, _operational_detail(item, request.auth_user))


@router.post(
    "/requests/current-student",
    auth=session_auth,
    response=response_with_errors(
        GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    operation_id="goodMoralCreateAssistedCurrentStudentRequest",
)
def good_moral_create_assisted_current(
    request,
    payload: AssistedCurrentStudentRequestPayload,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    return _assisted_create(
        request,
        payload,
        GoodMoralVariant.CURRENT_STUDENT,
        "/api/v1/good-moral/requests/current-student",
        idempotency_key,
    )


@router.post(
    "/requests/graduate",
    auth=session_auth,
    response=response_with_errors(
        GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422, success_status=201
    ),
    operation_id="goodMoralCreateAssistedGraduateRequest",
)
def good_moral_create_assisted_graduate(
    request,
    payload: AssistedGraduateRequestPayload,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    return _assisted_create(
        request,
        payload,
        GoodMoralVariant.GRADUATE,
        "/api/v1/good-moral/requests/graduate",
        idempotency_key,
    )


# Static self-service routes are registered before UUID routes.


@router.post(
    "/me/requests/current-student",
    response=response_with_errors(
        GoodMoralDetailResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="goodMoralCreateMyCurrentStudentRequest",
)
def good_moral_create_my_current_student(
    request,
    payload: CurrentStudentRequestPayload,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_student(request, "good_moral.request_self")
    fingerprint = request_fingerprint(
        method="POST",
        route=CURRENT_STUDENT_CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_my_current_student(
            student=request.auth_user,
            year_level=payload.year_level,
            semester=payload.semester,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return Status(201, _detail(item))


@router.get(
    "/me/academic-context",
    response=response_with_errors(GoodMoralF4AcademicContextResponse, 401, 403),
    auth=session_auth,
    operation_id="goodMoralGetMyF4AcademicContext",
)
def good_moral_my_academic_context(request):
    _require_student(request, "good_moral.request_self")
    return _f4_academic_context_response(request.auth_user)


@router.post(
    "/me/requests/graduate",
    response=response_with_errors(
        GoodMoralDetailResponse,
        401,
        403,
        409,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="goodMoralCreateMyGraduateRequest",
)
def good_moral_create_my_graduate(
    request,
    payload: GraduateRequestPayload,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_student(request, "good_moral.request_self")
    fingerprint = request_fingerprint(
        method="POST",
        route=GRADUATE_CREATE_ROUTE,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        item = create_my_graduate(
            student=request.auth_user,
            degree=payload.degree,
            major=payload.major,
            graduation_date=payload.graduation_date,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return Status(201, _detail(item))


@router.get(
    "/me",
    response=response_with_errors(GoodMoralHistoryResponse, 401, 403),
    auth=session_auth,
    operation_id="goodMoralListMyRequests",
)
def good_moral_list_my(request):
    _require_student(request, "good_moral.view_self")
    try:
        items = list_mine(request.auth_user)
    except GoodMoralError as exc:
        _raise(exc)
    return {"items": [_summary(item) for item in items]}


@router.post(
    "/me/{request_id}/cancel",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralCancelMyRequest",
)
def good_moral_cancel_my(
    request,
    request_id: UUID,
    payload: GoodMoralCancellationPayload,
):
    _require_student(request, "good_moral.request_self")
    try:
        item = cancel_request(
            actor=request.auth_user,
            request_id=request_id,
            reason=payload.reason,
            self_service=True,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/me/{request_id}/pdf",
    response=response_with_errors(None, 401, 403, 404, 409, 503),
    auth=session_auth,
    operation_id="goodMoralDownloadMyCertificate",
    openapi_extra=PDF_SUCCESS_OPENAPI,
)
def good_moral_download_my(request, request_id: UUID):
    _require_student(request, "good_moral.view_self")
    try:
        item = get_mine(student=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _pdf_response(item, context=_context(request), access_mode="SELF")


@router.get(
    "/me/{request_id}",
    response=response_with_errors(GoodMoralDetailResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="goodMoralGetMyRequest",
)
def good_moral_get_my(request, request_id: UUID):
    _require_student(request, "good_moral.view_self")
    try:
        item = get_mine(student=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/requests",
    response=response_with_errors(GoodMoralPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="goodMoralListRequests",
)
def good_moral_list_requests(
    request,
    variant: GoodMoralVariantValue | None = None,
    status: GoodMoralStatusValue | None = None,
    student_id: UUID | None = None,
    search: str | None = None,
    form_revision_id: UUID | None = None,
    academic_year_id: UUID | None = None,
    ordering: GoodMoralOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_operational(request, "good_moral.view")
    try:
        result = list_requests(
            actor=request.auth_user,
            variant=variant.value if variant is not None else None,
            status=status.value if status is not None else None,
            student_id=student_id,
            search=search,
            form_revision_id=form_revision_id,
            academic_year_id=academic_year_id,
            ordering=ordering,
            page=page,
            page_size=page_size,
        )
    except GoodMoralError as exc:
        _raise(exc)
    return {
        "items": [_operational_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
        "ordering": result.ordering,
        "filter_options": project_filter_options(result.form_revisions),
    }


@router.get(
    "/requests/{request_id}/pdf",
    response=response_with_errors(None, 401, 403, 404, 409, 503),
    auth=session_auth,
    operation_id="goodMoralDownloadCertificate",
    openapi_extra=PDF_SUCCESS_OPENAPI,
)
def good_moral_download(request, request_id: UUID):
    _require_operational(request, "good_moral.view")
    try:
        item = get_request(actor=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _pdf_response(item, context=_context(request), access_mode="GCO")


@router.post(
    "/requests/{request_id}/cancel",
    response=response_with_errors(GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralCancelRequest",
)
def good_moral_cancel_request(
    request,
    request_id: UUID,
    payload: GoodMoralCancellationPayload,
):
    _require_counselor(request, "good_moral.manage")
    try:
        item = cancel_request(
            actor=request.auth_user,
            request_id=request_id,
            reason=payload.reason,
            self_service=False,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _operational_detail(item, request.auth_user)


@router.post(
    "/requests/{request_id}/issue",
    response=response_with_errors(GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralIssueRequest",
)
def good_moral_issue(request, request_id: UUID, payload: GoodMoralIssuePayload):
    _require_counselor(request, "good_moral.issue")
    try:
        item = issue_request(
            expected_preparation_version=payload.expected_preparation_version,
            expected_resource_version=payload.expected_resource_version,
            expected_receipt_revision=payload.expected_receipt_revision,
            expected_receipt_verification=payload.expected_receipt_verification,
            actor=request.auth_user,
            request_id=request_id,
            context=_context(request),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _operational_detail(item, request.auth_user)


@router.get(
    "/requests/{request_id}",
    response=response_with_errors(GoodMoralOperationalDetailResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="goodMoralGetRequest",
)
def good_moral_get(request, request_id: UUID):
    _require_operational(request, "good_moral.view")
    try:
        item = get_request(actor=request.auth_user, request_id=request_id)
    except GoodMoralError as exc:
        _raise(exc)
    return _operational_detail(item, request.auth_user)


@router.patch(
    "/requests/{request_id}",
    response=response_with_errors(GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralUpdateRequest",
)
def good_moral_update(request, request_id: UUID, payload: GoodMoralCorrectionPayload):
    _require_operational(request, "good_moral.prepare")
    try:
        item = update_request(
            actor=request.auth_user,
            request_id=request_id,
            changes=_correction_values(payload),
            context=_context(request),
            expected_resource_version=payload.expected_resource_version,
            expected_receipt_revision=(
                payload.expected_receipt_revision
                if "expected_receipt_revision" in payload.model_fields_set
                else ...
            ),
            operation_id=payload.receipt_operation_id,
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _operational_detail(item, request.auth_user)


@router.post(
    "/requests/{request_id}/prepare",
    response=response_with_errors(GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralPrepareRequest",
)
def good_moral_prepare(request, request_id: UUID, payload: GoodMoralPreparationPayload):
    _require_operational(request, "good_moral.prepare")
    try:
        item = prepare_request(
            actor=request.auth_user,
            request_id=request_id,
            context=_context(request),
            expected_resource_version=payload.expected_resource_version,
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _operational_detail(item, request.auth_user)


@router.post(
    "/requests/{request_id}/receipt/verify",
    response=response_with_errors(GoodMoralOperationalDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="goodMoralVerifyReceipt",
)
def good_moral_verify_receipt(
    request, request_id: UUID, payload: GoodMoralReceiptVerificationPayload
):
    from .receipt_verification import verify_receipt

    _require_operational(request, "good_moral.verify_receipt")
    try:
        item = verify_receipt(
            actor=request.auth_user,
            request_id=request_id,
            context=_context(request),
            **payload.model_dump(),
        )
    except GoodMoralError as exc:
        _raise(exc)
    return _operational_detail(item, request.auth_user)
