"""Thin Django Ninja API for Organization structure and default responsibility configuration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import StrEnum
from typing import Annotated, NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict, Field, StrictBool, StrictInt

from compass.accounts.api_codes import RoleCode
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired
from compass.authentication.step_up import require_recent_mfa_for_request, step_up_api_error
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.organization import catalog_services as catalog
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StaffSupervision,
)
from compass.organization.program_policy import (
    AcademicClassification,
    YearLevelPolicyStatus,
    get_program_policy,
)
from compass.organization.services import (
    DEFAULT_PAGE_SIZE,
    InvalidOrganizationInput,
    OrganizationConflict,
    OrganizationError,
    OrganizationNotFound,
    get_campus,
    get_college,
    get_program,
    list_campuses,
    list_colleges,
    list_people,
    list_programs,
    list_student_affiliations,
    remove_counselor_responsibility,
    remove_staff_supervisor,
    remove_student_affiliation,
    set_counselor_responsibility,
    set_staff_supervisor,
    set_student_affiliation,
)

router = Router(tags=["organization"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CampusSummary(StrictSchema):
    id: UUID
    code: str
    name: str
    is_active: bool
    resource_version: int


class CampusListResponse(StrictSchema):
    items: list[CampusSummary]


class CollegeSummary(StrictSchema):
    id: UUID
    code: str
    name: str
    campus: CampusSummary
    is_active: bool
    resource_version: int


class CollegeListResponse(StrictSchema):
    items: list[CollegeSummary]


class ProgramSummary(StrictSchema):
    id: UUID
    code: str
    name: str
    college: CollegeSummary
    is_active: bool
    resource_version: int
    academic_classification: AcademicClassification | None
    year_level_policy_status: YearLevelPolicyStatus
    applicable_year_levels: list[int] | None


class ProgramListResponse(StrictSchema):
    items: list[ProgramSummary]


class OrganizationResponsibilityScope(StrEnum):
    ASSIGNED_AND_FALLBACK_COLLEGES = "ASSIGNED_AND_FALLBACK_COLLEGES"
    ASSIGNED_COLLEGES = "ASSIGNED_COLLEGES"


class OrganizationPersonSummary(StrictSchema):
    id: UUID
    institutional_id: str | None
    full_name: str
    email: str
    role: RoleCode
    is_active: bool
    responsibility_scope: OrganizationResponsibilityScope | None


class PersonListResponse(StrictSchema):
    items: list[OrganizationPersonSummary]
    page: int
    page_size: int
    has_next: bool


class CounselorAssignmentRequest(StrictSchema):
    counselor_id: UUID


class StaffSupervisorRequest(StrictSchema):
    supervisor_id: UUID


class StudentAffiliationRequest(StrictSchema):
    college_id: UUID


class CounselorResponsibilityResponse(StrictSchema):
    college: CollegeSummary
    counselor: OrganizationPersonSummary


class CounselorResponsibilityListResponse(StrictSchema):
    items: list[CounselorResponsibilityResponse]


class StaffSupervisionResponse(StrictSchema):
    staff: OrganizationPersonSummary
    supervisor: OrganizationPersonSummary


class StaffSupervisionListResponse(StrictSchema):
    items: list[StaffSupervisionResponse]


class StudentAffiliationResponse(StrictSchema):
    student: OrganizationPersonSummary
    college: CollegeSummary


class StudentAffiliationListResponse(StrictSchema):
    items: list[StudentAffiliationResponse]
    page: int
    page_size: int
    has_next: bool


class RemovedResponse(StrictSchema):
    removed: bool


class OrganizationRole(StrEnum):
    COUNSELOR = "COUNSELOR"
    GUIDANCE_SERVICES_STAFF = "GUIDANCE_SERVICES_STAFF"
    STUDENT = "STUDENT"


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    if not request.auth_user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        require_recent_mfa_for_request(request)


def _raise(exc: OrganizationError) -> NoReturn:
    if isinstance(exc, OrganizationNotFound):
        raise APIError(404, "organization_not_found", str(exc)) from exc
    if isinstance(exc, OrganizationConflict):
        raise APIError(409, "organization_conflict", str(exc)) from exc
    if isinstance(exc, InvalidOrganizationInput):
        raise APIError(422, "invalid_organization_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The organization operation could not be completed."
    ) from exc


def _campus(campus) -> dict[str, object]:
    return {
        "id": campus.pk,
        "code": campus.code,
        "name": campus.name,
        "is_active": campus.is_active,
        "resource_version": campus.resource_version,
    }


def _college(college) -> dict[str, object]:
    return {
        "id": college.pk,
        "code": college.code,
        "name": college.name,
        "campus": _campus(college.campus),
        "is_active": college.is_active,
        "resource_version": college.resource_version,
    }


def _program(program) -> dict[str, object]:
    metadata = get_program_policy(program)
    return {
        "id": program.pk,
        "code": program.code,
        "name": program.name,
        "college": _college(program.college),
        "is_active": program.is_active,
        "resource_version": program.resource_version,
        "academic_classification": (metadata.academic_classification),
        "year_level_policy_status": (metadata.year_level_policy_status),
        "applicable_year_levels": (
            list(metadata.applicable_year_levels)
            if metadata.applicable_year_levels is not None
            else None
        ),
    }


def _person(user) -> dict[str, object]:
    responsibility_scope = None
    if user.role.code == "COUNSELOR":
        responsibility_scope = (
            OrganizationResponsibilityScope.ASSIGNED_AND_FALLBACK_COLLEGES
            if any(
                designation.code == "HEAD_GUIDANCE_COUNSELOR"
                for designation in user.designations.all()
            )
            else OrganizationResponsibilityScope.ASSIGNED_COLLEGES
        )
    return {
        "id": user.pk,
        "institutional_id": user.institutional_id,
        "full_name": user.get_full_name(),
        "email": user.email,
        "role": user.role.code,
        "is_active": user.is_active,
        "responsibility_scope": responsibility_scope,
    }


@router.get(
    "/campuses",
    response=response_with_errors(CampusListResponse, 401, 403),
    auth=session_auth,
    operation_id="organizationListCampuses",
)
def campuses(request, is_active: bool | None = None, search: str | None = None):
    _require(request, "organization.structure.view")
    return {"items": [_campus(item) for item in list_campuses(is_active=is_active, search=search)]}


@router.get(
    "/campuses/{campus_id}",
    response=response_with_errors(CampusSummary, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="organizationGetCampus",
)
def campus_get(request, campus_id: UUID):
    _require(request, "organization.structure.view")
    try:
        return _campus(get_campus(campus_id))
    except OrganizationError as exc:
        _raise(exc)


@router.get(
    "/colleges",
    response=response_with_errors(CollegeListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="organizationListColleges",
)
def colleges(
    request, campus_id: UUID | None = None, is_active: bool | None = None, search: str | None = None
):
    _require(request, "organization.structure.view")
    return {
        "items": [
            _college(item)
            for item in list_colleges(campus_id=campus_id, is_active=is_active, search=search)
        ]
    }


@router.get(
    "/colleges/{college_id}",
    response=response_with_errors(CollegeSummary, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="organizationGetCollege",
)
def college_get(request, college_id: UUID):
    _require(request, "organization.structure.view")
    try:
        return _college(get_college(college_id))
    except OrganizationError as exc:
        _raise(exc)


@router.get(
    "/programs",
    response=response_with_errors(ProgramListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="organizationListPrograms",
)
def programs(
    request,
    college_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
):
    _require(request, "organization.structure.view")
    return {
        "items": [
            _program(item)
            for item in list_programs(
                college_id=college_id,
                is_active=is_active,
                search=search,
            )
        ]
    }


@router.get(
    "/programs/{program_id}",
    response=response_with_errors(ProgramSummary, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="organizationGetProgram",
)
def program_get(request, program_id: UUID):
    _require(request, "organization.structure.view")
    try:
        return _program(get_program(program_id))
    except OrganizationError as exc:
        _raise(exc)


@router.get(
    "/counselor-responsibilities",
    response=response_with_errors(CounselorResponsibilityListResponse, 401, 403),
    auth=session_auth,
    operation_id="organizationListCounselorResponsibilities",
)
def counselor_responsibilities(
    request,
    counselor_id: UUID | None = None,
    college_id: UUID | None = None,
    campus_id: UUID | None = None,
):
    _require(request, "organization.manage")
    qs = (
        CounselorResponsibility.objects.select_related("college__campus", "counselor__role")
        .prefetch_related("counselor__designations")
        .order_by("college__campus__code", "college__code")
    )
    if counselor_id is not None:
        qs = qs.filter(counselor_id=counselor_id)
    if college_id is not None:
        qs = qs.filter(college_id=college_id)
    if campus_id is not None:
        qs = qs.filter(college__campus_id=campus_id)
    return {
        "items": [
            {"college": _college(item.college), "counselor": _person(item.counselor)} for item in qs
        ]
    }


@router.put(
    "/colleges/{college_id}/counselor",
    response=response_with_errors(CounselorResponsibilityResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="organizationSetCollegeCounselor",
)
def college_counselor_set(request, college_id: UUID, payload: CounselorAssignmentRequest):
    _require(request, "organization.manage", recent_mfa=True)
    try:
        item = set_counselor_responsibility(
            college_id=college_id,
            counselor_id=payload.counselor_id,
            context=_context(request),
        )
    except OrganizationError as exc:
        _raise(exc)
    return {"college": _college(item.college), "counselor": _person(item.counselor)}


@router.delete(
    "/colleges/{college_id}/counselor",
    response=response_with_errors(RemovedResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="organizationRemoveCollegeCounselor",
)
def college_counselor_remove(request, college_id: UUID):
    _require(request, "organization.manage", recent_mfa=True)
    try:
        removed = remove_counselor_responsibility(college_id=college_id, context=_context(request))
    except OrganizationError as exc:
        _raise(exc)
    return {"removed": removed}


@router.get(
    "/staff-supervisions",
    response=response_with_errors(StaffSupervisionListResponse, 401, 403),
    auth=session_auth,
    operation_id="organizationListStaffSupervisions",
)
def staff_supervisions(request):
    _require(request, "organization.manage")
    qs = (
        StaffSupervision.objects.select_related("staff__role", "supervisor__role")
        .prefetch_related("supervisor__designations")
        .order_by("staff__last_name", "staff__id")
    )
    return {
        "items": [
            {"staff": _person(item.staff), "supervisor": _person(item.supervisor)} for item in qs
        ]
    }


@router.put(
    "/staff/{staff_id}/supervisor",
    response=response_with_errors(StaffSupervisionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="organizationSetStaffSupervisor",
)
def staff_supervisor_set(request, staff_id: UUID, payload: StaffSupervisorRequest):
    _require(request, "organization.manage", recent_mfa=True)
    try:
        item = set_staff_supervisor(
            staff_id=staff_id,
            supervisor_id=payload.supervisor_id,
            context=_context(request),
        )
    except OrganizationError as exc:
        _raise(exc)
    return {"staff": _person(item.staff), "supervisor": _person(item.supervisor)}


@router.delete(
    "/staff/{staff_id}/supervisor",
    response=response_with_errors(RemovedResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="organizationRemoveStaffSupervisor",
)
def staff_supervisor_remove(request, staff_id: UUID):
    _require(request, "organization.manage", recent_mfa=True)
    try:
        removed = remove_staff_supervisor(staff_id=staff_id, context=_context(request))
    except OrganizationError as exc:
        _raise(exc)
    return {"removed": removed}


@router.get(
    "/student-affiliations",
    response=response_with_errors(StudentAffiliationListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="organizationListStudentAffiliations",
)
def student_affiliations(
    request,
    student_id: UUID | None = None,
    college_id: UUID | None = None,
    campus_id: UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "organization.manage")
    try:
        result = list_student_affiliations(
            student_id=student_id,
            college_id=college_id,
            campus_id=campus_id,
            search=search,
            page=page,
            page_size=page_size,
        )
    except OrganizationError as exc:
        _raise(exc)
    return {
        "items": [
            {"student": _person(item.student), "college": _college(item.college)}
            for item in result.items
        ],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.put(
    "/students/{student_id}/affiliation",
    response=response_with_errors(StudentAffiliationResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="organizationSetStudentAffiliation",
)
def student_affiliation_set(request, student_id: UUID, payload: StudentAffiliationRequest):
    _require(request, "organization.manage", recent_mfa=True)
    try:
        item = set_student_affiliation(
            student_id=student_id,
            college_id=payload.college_id,
            context=_context(request),
        )
    except OrganizationError as exc:
        _raise(exc)
    return {"student": _person(item.student), "college": _college(item.college)}


@router.delete(
    "/students/{student_id}/affiliation",
    response=response_with_errors(RemovedResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="organizationRemoveStudentAffiliation",
)
def student_affiliation_remove(request, student_id: UUID):
    _require(request, "organization.manage", recent_mfa=True)
    try:
        removed = remove_student_affiliation(student_id=student_id, context=_context(request))
    except OrganizationError as exc:
        _raise(exc)
    return {"removed": removed}


@router.get(
    "/people",
    response=response_with_errors(PersonListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="organizationListEligiblePeople",
)
def people(
    request,
    role: OrganizationRole,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "organization.manage")
    try:
        result = list_people(role=role.value, search=search, page=page, page_size=page_size)
    except OrganizationError as exc:
        _raise(exc)
    return {
        "items": [_person(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


PositiveVersion = Annotated[StrictInt, Field(ge=1)]
CatalogText = Annotated[str, Field(min_length=1, max_length=160)]


class CatalogCreateCampusRequest(StrictSchema):
    code: Annotated[str, Field(min_length=1, max_length=32)]
    name: CatalogText
    is_active: StrictBool
    basis: CatalogText


class CatalogCreateCollegeRequest(CatalogCreateCampusRequest):
    campus_id: UUID


class CatalogPolicyFields(StrictSchema):
    academic_classification: AcademicClassification | None
    year_level_policy_status: YearLevelPolicyStatus
    applicable_year_levels: list[StrictInt] | None


class CatalogCreateProgramRequest(CatalogCreateCampusRequest, CatalogPolicyFields):
    college_id: UUID


class CatalogRenameRequest(StrictSchema):
    expected_resource_version: PositiveVersion
    name: CatalogText
    basis: CatalogText


class CatalogStatusRequest(StrictSchema):
    expected_resource_version: PositiveVersion
    is_active: StrictBool
    basis: CatalogText


class CatalogPolicyRequest(CatalogPolicyFields):
    expected_resource_version: PositiveVersion
    basis: CatalogText


class CatalogIssueCode(StrEnum):
    ACTIVE_CHILD_COLLEGES = "active_child_colleges"
    ACTIVE_CHILD_PROGRAMS = "active_child_programs"
    ACTIVE_STUDENT_AFFILIATIONS = "active_student_affiliations"
    COUNSELOR_RESPONSIBILITIES = "counselor_responsibilities"
    OPEN_OFFICE_THREADS = "open_office_threads"
    PENDING_OPERATIONAL_FOLLOWUPS = "pending_operational_followups"
    INACTIVE_ACCOUNT_AFFILIATIONS = "inactive_account_affiliations"
    DRAFT_INVENTORIES = "draft_inventories"
    PENDING_GOOD_MORAL = "pending_good_moral"


class CatalogIssueSummary(StrictSchema):
    code: CatalogIssueCode
    count: int


class CatalogDependentCounts(StrictSchema):
    child_colleges: int
    active_child_colleges: int
    child_programs: int
    active_child_programs: int
    student_affiliations: int
    active_student_affiliations: int
    inactive_account_affiliations: int
    counselor_responsibilities: int
    draft_inventories: int
    submitted_inventories: int
    graduate_tracer_references: int
    open_office_threads: int
    resolved_threads: int
    pending_good_moral: int
    pending_f4: int
    issued_good_moral: int
    pending_operational_followups: int


class CatalogImpactResponse(StrictSchema):
    target_id: UUID
    resource_version: int
    observed_at: datetime
    can_deactivate: bool
    blockers: list[CatalogIssueSummary]
    warnings: list[CatalogIssueSummary]
    counts: CatalogDependentCounts
    preserved_categories: list[str]


class CatalogHistoryValues(StrictSchema):
    name: str | None = None
    is_active: bool | None = None
    academic_classification: AcademicClassification | None = None
    year_level_policy_status: YearLevelPolicyStatus | None = None
    applicable_year_levels: list[int] | None = None


class CatalogHistoryItem(StrictSchema):
    id: UUID
    occurred_at: datetime
    actor_id: UUID
    action: str
    code: str
    parent_id: UUID | None
    changed_fields: list[str]
    resource_version_before: int | None
    resource_version_after: int
    before: CatalogHistoryValues
    after: CatalogHistoryValues
    basis: str


class CatalogHistoryResponse(StrictSchema):
    items: list[CatalogHistoryItem]
    page: int
    page_size: int
    has_next: bool


def _catalog_require(request, *, mutation=False):
    try:
        catalog.require_catalog_manager(actor=request.auth_user)
    except catalog.CatalogError as exc:
        raise APIError(exc.status, exc.code, str(exc), details=exc.details) from exc
    if mutation:
        require_recent_mfa_for_request(request)


def _catalog_call(request, function, *, mutation=False, **kwargs):
    _catalog_require(request, mutation=mutation)
    try:
        if mutation:
            return function(
                actor=request.auth_user,
                actor_session=request.auth_session,
                context=_context(request),
                **kwargs,
            )
        return function(actor=request.auth_user, **kwargs)
    except catalog.CatalogError as exc:
        raise APIError(exc.status, exc.code, str(exc), details=exc.details) from exc
    except RecentMFARequired as exc:
        raise step_up_api_error(exc) from exc


@router.post(
    "/campuses",
    auth=session_auth,
    response=response_with_errors(CampusSummary, 401, 403, 404, 409, 422),
    operation_id="organizationCreateCampus",
)
def catalog_create_campus(request, payload: CatalogCreateCampusRequest):
    item = _catalog_call(request, catalog.create_campus, mutation=True, **payload.model_dump())
    return _campus(item)


@router.put(
    "/campuses/{target_id}/name",
    auth=session_auth,
    response=response_with_errors(CampusSummary, 401, 403, 404, 409, 422),
    operation_id="organizationRenameCampus",
)
def catalog_rename_campus(request, target_id: UUID, payload: CatalogRenameRequest):
    item = _catalog_call(
        request, catalog.rename_campus, mutation=True, target_id=target_id, **payload.model_dump()
    )
    return _campus(item)


@router.put(
    "/campuses/{target_id}/active",
    auth=session_auth,
    response=response_with_errors(CampusSummary, 401, 403, 404, 409, 422),
    operation_id="organizationSetCampusActive",
)
def catalog_status_campus(request, target_id: UUID, payload: CatalogStatusRequest):
    item = _catalog_call(
        request,
        catalog.set_campus_active,
        mutation=True,
        target_id=target_id,
        **payload.model_dump(),
    )
    return _campus(item)


@router.get(
    "/campuses/{target_id}/impact",
    auth=session_auth,
    response=response_with_errors(CatalogImpactResponse, 401, 403, 404, 422),
    operation_id="organizationGetCampusImpact",
)
def catalog_impact_campus(request, target_id: UUID):
    return asdict(
        _catalog_call(request, catalog.get_catalog_impact, model=Campus, target_id=target_id)
    )


@router.get(
    "/campuses/{target_id}/history",
    auth=session_auth,
    response=response_with_errors(CatalogHistoryResponse, 401, 403, 404, 422),
    operation_id="organizationGetCampusHistory",
)
def catalog_history_campus(request, target_id: UUID, page: int = 1, page_size: int = 20):
    return _catalog_call(
        request,
        catalog.get_catalog_history,
        model=Campus,
        target_id=target_id,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/colleges",
    auth=session_auth,
    response=response_with_errors(CollegeSummary, 401, 403, 404, 409, 422),
    operation_id="organizationCreateCollege",
)
def catalog_create_college(request, payload: CatalogCreateCollegeRequest):
    item = _catalog_call(request, catalog.create_college, mutation=True, **payload.model_dump())
    return _college(item)


@router.put(
    "/colleges/{target_id}/name",
    auth=session_auth,
    response=response_with_errors(CollegeSummary, 401, 403, 404, 409, 422),
    operation_id="organizationRenameCollege",
)
def catalog_rename_college(request, target_id: UUID, payload: CatalogRenameRequest):
    item = _catalog_call(
        request, catalog.rename_college, mutation=True, target_id=target_id, **payload.model_dump()
    )
    return _college(item)


@router.put(
    "/colleges/{target_id}/active",
    auth=session_auth,
    response=response_with_errors(CollegeSummary, 401, 403, 404, 409, 422),
    operation_id="organizationSetCollegeActive",
)
def catalog_status_college(request, target_id: UUID, payload: CatalogStatusRequest):
    item = _catalog_call(
        request,
        catalog.set_college_active,
        mutation=True,
        target_id=target_id,
        **payload.model_dump(),
    )
    return _college(item)


@router.get(
    "/colleges/{target_id}/impact",
    auth=session_auth,
    response=response_with_errors(CatalogImpactResponse, 401, 403, 404, 422),
    operation_id="organizationGetCollegeImpact",
)
def catalog_impact_college(request, target_id: UUID):
    return asdict(
        _catalog_call(request, catalog.get_catalog_impact, model=College, target_id=target_id)
    )


@router.get(
    "/colleges/{target_id}/history",
    auth=session_auth,
    response=response_with_errors(CatalogHistoryResponse, 401, 403, 404, 422),
    operation_id="organizationGetCollegeHistory",
)
def catalog_history_college(request, target_id: UUID, page: int = 1, page_size: int = 20):
    return _catalog_call(
        request,
        catalog.get_catalog_history,
        model=College,
        target_id=target_id,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/programs",
    auth=session_auth,
    response=response_with_errors(ProgramSummary, 401, 403, 404, 409, 422),
    operation_id="organizationCreateProgram",
)
def catalog_create_program(request, payload: CatalogCreateProgramRequest):
    item = _catalog_call(request, catalog.create_program, mutation=True, **payload.model_dump())
    return _program(item)


@router.put(
    "/programs/{target_id}/name",
    auth=session_auth,
    response=response_with_errors(ProgramSummary, 401, 403, 404, 409, 422),
    operation_id="organizationRenameProgram",
)
def catalog_rename_program(request, target_id: UUID, payload: CatalogRenameRequest):
    item = _catalog_call(
        request, catalog.rename_program, mutation=True, target_id=target_id, **payload.model_dump()
    )
    return _program(item)


@router.put(
    "/programs/{target_id}/active",
    auth=session_auth,
    response=response_with_errors(ProgramSummary, 401, 403, 404, 409, 422),
    operation_id="organizationSetProgramActive",
)
def catalog_status_program(request, target_id: UUID, payload: CatalogStatusRequest):
    item = _catalog_call(
        request,
        catalog.set_program_active,
        mutation=True,
        target_id=target_id,
        **payload.model_dump(),
    )
    return _program(item)


@router.get(
    "/programs/{target_id}/impact",
    auth=session_auth,
    response=response_with_errors(CatalogImpactResponse, 401, 403, 404, 422),
    operation_id="organizationGetProgramImpact",
)
def catalog_impact_program(request, target_id: UUID):
    return asdict(
        _catalog_call(request, catalog.get_catalog_impact, model=Program, target_id=target_id)
    )


@router.get(
    "/programs/{target_id}/history",
    auth=session_auth,
    response=response_with_errors(CatalogHistoryResponse, 401, 403, 404, 422),
    operation_id="organizationGetProgramHistory",
)
def catalog_history_program(request, target_id: UUID, page: int = 1, page_size: int = 20):
    return _catalog_call(
        request,
        catalog.get_catalog_history,
        model=Program,
        target_id=target_id,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/programs/{target_id}/policy",
    auth=session_auth,
    response=response_with_errors(ProgramSummary, 401, 403, 404, 409, 422),
    operation_id="organizationUpdateProgramPolicy",
)
def catalog_program_policy(request, target_id: UUID, payload: CatalogPolicyRequest):
    item = _catalog_call(
        request,
        catalog.update_program_policy,
        mutation=True,
        target_id=target_id,
        **payload.model_dump(),
    )
    return _program(item)
