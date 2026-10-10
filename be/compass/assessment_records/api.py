"""Structural lists and explicitly authorized confidential detail; no DELETE or self-service."""

from dataclasses import asdict
from functools import wraps
from uuid import UUID

from ninja import Query, Router

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.operational_students import InvalidOperationalStudentQuery

from . import services
from .confidential_content import AssessmentRecordConfidentialContentUnavailable
from .errors import (
    AssessmentRecordAccessDenied,
    AssessmentRecordConflict,
    AssessmentRecordError,
    AssessmentRecordNotFound,
    InvalidAssessmentRecordInput,
)
from .schemas import (
    AssessmentRecordCreate,
    AssessmentRecordDetail,
    AssessmentRecordFilters,
    AssessmentRecordPage,
    AssessmentRecordUpdate,
    AssessmentStudentPage,
    AssessmentTypeCreate,
    AssessmentTypeResponse,
    AssessmentTypeUpdate,
)

router = Router(tags=["assessment-records"], auth=session_auth)


def domain_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (AssessmentRecordError, InvalidOperationalStudentQuery) as exc:
            if isinstance(exc, AssessmentRecordAccessDenied):
                status, code, message = 403, "permission_denied", str(exc)
            elif isinstance(exc, AssessmentRecordNotFound):
                status, code, message = 404, "assessment_record_not_found", str(exc)
            elif isinstance(exc, AssessmentRecordConflict):
                status, code, message = 409, "assessment_record_conflict", str(exc)
            elif isinstance(exc, (InvalidAssessmentRecordInput, InvalidOperationalStudentQuery)):
                status, code, message = 422, "invalid_assessment_record_input", str(exc)
            elif isinstance(exc, AssessmentRecordConfidentialContentUnavailable):
                status, code, message = 500, "assessment_record_content_unavailable", str(exc)
            else:
                status, code, message = 500, "internal_error", "Assessment Records are unavailable."
            raise APIError(status, code, message) from None

    return wrapped


def _person(user):
    return {
        "id": user.pk,
        "institutional_id": user.institutional_id,
        "display_name": user.get_full_name(),
    }


def _summary(item):
    return {
        "id": item.pk,
        "student": _person(item.student),
        "assessment_type": item.assessment_type,
        "administered_on": item.administered_on,
        "recorded_by": _person(item.recorded_by),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _detail(result):
    item, content = result
    return {**_summary(item), **asdict(content)}


@router.get(
    "/types",
    response=response_with_errors(list[AssessmentTypeResponse], 401, 403),
    operation_id="assessmentRecordsListTypes",
)
@domain_errors
def list_types(request, active_only: bool = False):
    return services.list_types(actor=request.auth_user, active_only=active_only)


@router.post(
    "/types",
    response=response_with_errors(AssessmentTypeResponse, 401, 403, 409, 422, success_status=201),
    operation_id="assessmentRecordsCreateType",
)
@domain_errors
def create_type(request, payload: AssessmentTypeCreate):
    return 201, services.create_type(
        actor=request.auth_user,
        values=payload.model_dump(),
        context=AuditContext.from_request(request),
    )


@router.patch(
    "/types/{type_id}",
    response=response_with_errors(AssessmentTypeResponse, 401, 403, 404, 409, 422),
    operation_id="assessmentRecordsUpdateType",
)
@domain_errors
def update_type(request, type_id: UUID, payload: AssessmentTypeUpdate):
    return services.update_type(
        actor=request.auth_user,
        type_id=type_id,
        values=payload.model_dump(exclude_unset=True),
        context=AuditContext.from_request(request),
    )


@router.get(
    "/students",
    response=response_with_errors(AssessmentStudentPage, 401, 403, 422),
    operation_id="assessmentRecordsEligibleStudents",
)
@domain_errors
def eligible_students(request, search: str | None = None, page: int = 1, page_size: int = 20):
    result = services.eligible_students(
        actor=request.auth_user, search=search, page=page, page_size=page_size
    )
    return {
        "items": [
            {
                "id": item.id,
                "institutional_id": item.institutional_id,
                "display_name": item.display_name,
                "college": asdict(item.college) if item.college else None,
            }
            for item in result.items
        ],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "",
    response=response_with_errors(AssessmentRecordPage, 401, 403, 422),
    operation_id="assessmentRecordsList",
)
@domain_errors
def list_records(request, filters: Query[AssessmentRecordFilters]):
    result = services.list_records(actor=request.auth_user, **filters.model_dump())
    return {**result, "items": [_summary(item) for item in result["items"]]}


@router.post(
    "",
    response=response_with_errors(
        AssessmentRecordDetail, 401, 403, 404, 422, 500, success_status=201
    ),
    operation_id="assessmentRecordsCreate",
)
@domain_errors
def create_record(request, payload: AssessmentRecordCreate):
    return 201, _detail(
        services.create_record(
            actor=request.auth_user,
            values=payload.model_dump(),
            context=AuditContext.from_request(request),
        )
    )


@router.get(
    "/{record_id}",
    response=response_with_errors(AssessmentRecordDetail, 401, 403, 404, 500),
    operation_id="assessmentRecordsGet",
)
@domain_errors
def get_record(request, record_id: UUID):
    return _detail(services.get_record(actor=request.auth_user, record_id=record_id))


@router.patch(
    "/{record_id}",
    response=response_with_errors(AssessmentRecordDetail, 401, 403, 404, 422, 500),
    operation_id="assessmentRecordsUpdate",
)
@domain_errors
def update_record(request, record_id: UUID, payload: AssessmentRecordUpdate):
    return _detail(
        services.update_record(
            actor=request.auth_user,
            record_id=record_id,
            values=payload.model_dump(exclude_unset=True),
            context=AuditContext.from_request(request),
        )
    )
