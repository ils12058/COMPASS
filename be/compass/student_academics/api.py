"""Django Ninja API for canonical Student academic records."""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn
from uuid import UUID

from ninja import File, Form, Router
from ninja.files import UploadedFile

from compass.accounts.models import StudentLifecycleStatus
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.organization.academic_years_api import AcademicYearResponse
from compass.organization.api import (
    CollegeSummary,
    OrganizationPersonSummary,
    RemovedResponse,
    StrictSchema,
    _college,
    _context,
    _person,
    _require,
)
from compass.student_academics.batch_import import (
    BatchImportConfirmationMismatch,
    BatchImportPreviewRequired,
    BatchImportStale,
    import_student_academic_periods,
    import_student_graduations,
)
from compass.student_academics.models import AcademicTerm, EnrollmentStatus
from compass.student_academics.roster_import import (
    MAX_CSV_BYTES,
    RosterImportConflict,
    RosterImportDuplicateIdentity,
    RosterImportInvalidRows,
    RosterImportMalformed,
    RosterImportTooLarge,
    RosterImportUnsupportedHeaders,
    import_student_academic_roster,
)
from compass.student_academics.services import (
    DEFAULT_PAGE_SIZE,
    InvalidStudentAcademicInput,
    StudentAcademicConflict,
    StudentAcademicError,
    StudentAcademicNotFound,
    clear_current_placement,
    get_student_academic_record,
    list_current_placements,
    record_academic_period,
    record_graduation,
    set_current_placement,
)

router = Router(tags=["student-academics"])


class PlacementRequest(StrictSchema):
    college_id: UUID


class PlacementResponse(StrictSchema):
    student: OrganizationPersonSummary
    college: CollegeSummary


class PlacementListResponse(StrictSchema):
    items: list[PlacementResponse]
    page: int
    page_size: int
    has_next: bool


class AcademicPeriodRecordRequest(StrictSchema):
    academic_year_id: UUID
    term: AcademicTerm
    college_id: UUID
    year_level: int | None = None
    enrollment_status: EnrollmentStatus = EnrollmentStatus.UNKNOWN


class AcademicPeriodRecordResponse(StrictSchema):
    id: UUID
    academic_year: AcademicYearResponse
    term: AcademicTerm
    college: CollegeSummary
    year_level: int | None
    enrollment_status: EnrollmentStatus
    created_at: datetime
    updated_at: datetime


class GraduationRecordRequest(StrictSchema):
    graduated_college_id: UUID
    graduation_date: date
    verification_source: str


class GraduationRecordResponse(StrictSchema):
    id: UUID
    graduated_college: CollegeSummary
    graduation_date: date
    verification_source: str
    verified_by: OrganizationPersonSummary | None
    verified_at: datetime
    created_at: datetime
    updated_at: datetime


class StudentAcademicRecordResponse(StrictSchema):
    student: OrganizationPersonSummary
    lifecycle_status: StudentLifecycleStatus | None
    placement: PlacementResponse | None
    periods: list[AcademicPeriodRecordResponse]
    graduation: GraduationRecordResponse | None


class RosterImportRowResponse(StrictSchema):
    row_number: int
    institutional_id: str
    student_id: UUID | None
    student_name: str
    current_college_code: str | None
    campus_code: str
    college_code: str
    action: str
    message: str


class RosterImportResponse(StrictSchema):
    valid: bool
    committed: bool
    total_rows: int
    set_count: int
    noop_count: int
    conflict_count: int
    invalid_count: int
    rows: list[RosterImportRowResponse]


class PeriodImportRowResponse(StrictSchema):
    row_number: int
    institutional_id: str
    student_id: UUID | None
    student_name: str
    campus_code: str
    college_code: str
    year_level: int | None
    enrollment_status: str
    current_college_code: str | None
    current_year_level: int | None
    current_enrollment_status: str | None
    action: str
    message: str


class PeriodImportResponse(StrictSchema):
    valid: bool
    committed: bool
    total_rows: int
    create_count: int
    update_count: int
    noop_count: int
    conflict_count: int
    invalid_count: int
    preview_fingerprint: str
    rows: list[PeriodImportRowResponse]


class GraduationImportRowResponse(StrictSchema):
    row_number: int
    institutional_id: str
    student_id: UUID | None
    student_name: str
    campus_code: str
    college_code: str
    graduation_date: str
    lifecycle_status: str | None
    current_placement_college_code: str | None
    previous_college_code: str | None
    previous_graduation_date: str | None
    action: str
    message: str


class GraduationImportResponse(StrictSchema):
    valid: bool
    committed: bool
    total_rows: int
    graduate_count: int
    update_count: int
    noop_count: int
    conflict_count: int
    invalid_count: int
    write_count: int
    placement_cleared_count: int
    preview_fingerprint: str
    rows: list[GraduationImportRowResponse]


def _raise(exc: StudentAcademicError) -> NoReturn:
    if isinstance(exc, StudentAcademicNotFound):
        raise APIError(404, "student_academic_not_found", str(exc)) from exc
    if isinstance(exc, StudentAcademicConflict):
        raise APIError(409, "student_academic_conflict", str(exc)) from exc
    if isinstance(exc, InvalidStudentAcademicInput):
        raise APIError(422, "invalid_student_academic_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "Couldn't complete the Student Academic Record change. Try again."
    ) from exc


def _placement(profile) -> dict[str, object]:
    return {
        "student": _person(profile.student),
        "college": _college(profile.current_college),
    }


def _academic_year(academic_year) -> dict[str, object]:
    return {
        "id": academic_year.pk,
        "label": academic_year.label,
        "is_current": academic_year.is_current,
    }


def _period(record) -> dict[str, object]:
    return {
        "id": record.pk,
        "academic_year": _academic_year(record.academic_year),
        "term": record.term,
        "college": _college(record.college),
        "year_level": record.year_level,
        "enrollment_status": record.enrollment_status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _graduation(record) -> dict[str, object]:
    return {
        "id": record.pk,
        "graduated_college": _college(record.graduated_college),
        "graduation_date": record.graduation_date,
        "verification_source": record.verification_source,
        "verified_by": _person(record.verified_by) if record.verified_by is not None else None,
        "verified_at": record.verified_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _record_payload(record) -> dict[str, object]:
    return {
        "student": _person(record.student),
        "lifecycle_status": record.lifecycle_status,
        "placement": _placement(record.placement) if record.placement is not None else None,
        "periods": [_period(item) for item in record.periods],
        "graduation": _graduation(record.graduation) if record.graduation is not None else None,
    }


def _roster_report_payload(report) -> dict[str, object]:
    return {
        "valid": report.valid,
        "committed": report.committed,
        "total_rows": report.total_rows,
        "set_count": report.set_count,
        "noop_count": report.noop_count,
        "conflict_count": report.conflict_count,
        "invalid_count": report.invalid_count,
        "rows": [
            {
                "row_number": row.row_number,
                "institutional_id": row.institutional_id,
                "student_id": row.student_id,
                "student_name": row.student_name,
                "current_college_code": row.current_college_code,
                "campus_code": row.campus_code,
                "college_code": row.college_code,
                "action": row.action,
                "message": row.message,
            }
            for row in report.rows
        ],
    }


def _roster_issue_details(issues) -> list[dict[str, object]]:
    return [
        {
            "row_number": issue.row_number,
            "institutional_id": issue.institutional_id,
            "message": issue.message,
        }
        for issue in issues
    ]


@router.get(
    "/placements",
    response=response_with_errors(PlacementListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="studentAcademicsListPlacements",
)
def placements(
    request,
    student_id: UUID | None = None,
    college_id: UUID | None = None,
    campus_id: UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "student_academics.view")
    try:
        result = list_current_placements(
            student_id=student_id,
            college_id=college_id,
            campus_id=campus_id,
            search=search,
            page=page,
            page_size=page_size,
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return {
        "items": [_placement(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/me/record",
    response=response_with_errors(StudentAcademicRecordResponse, 401, 403),
    auth=session_auth,
    operation_id="studentAcademicsGetMyRecord",
)
def my_record(request):
    _require(request, "student_academics.view_self")
    if request.auth_user.role.code != "STUDENT":
        raise APIError(
            403,
            "permission_denied",
            "Academic record self-view is available only to Student accounts.",
        )
    try:
        record = get_student_academic_record(student_id=request.auth_user.pk)
    except StudentAcademicError as exc:
        _raise(exc)
    return _record_payload(record)


@router.put(
    "/students/{student_id}/placement",
    response=response_with_errors(PlacementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsSetPlacement",
)
def placement_set(request, student_id: UUID, payload: PlacementRequest):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        item = set_current_placement(
            student_id=student_id,
            college_id=payload.college_id,
            context=_context(request),
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return _placement(item)


@router.delete(
    "/students/{student_id}/placement",
    response=response_with_errors(RemovedResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsClearPlacement",
)
def placement_clear(request, student_id: UUID):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        removed = clear_current_placement(student_id=student_id, context=_context(request))
    except StudentAcademicError as exc:
        _raise(exc)
    return {"removed": removed}


@router.get(
    "/students/{student_id}/record",
    response=response_with_errors(StudentAcademicRecordResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="studentAcademicsGetStudentRecord",
)
def student_record(request, student_id: UUID):
    _require(request, "student_academics.view")
    try:
        record = get_student_academic_record(student_id=student_id)
    except StudentAcademicError as exc:
        _raise(exc)
    return _record_payload(record)


@router.put(
    "/students/{student_id}/periods",
    response=response_with_errors(AcademicPeriodRecordResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsRecordPeriod",
)
def period_record(request, student_id: UUID, payload: AcademicPeriodRecordRequest):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        item = record_academic_period(
            student_id=student_id,
            academic_year_id=payload.academic_year_id,
            term=payload.term,
            college_id=payload.college_id,
            year_level=payload.year_level,
            enrollment_status=payload.enrollment_status,
            context=_context(request),
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return _period(item)


@router.put(
    "/students/{student_id}/graduation",
    response=response_with_errors(GraduationRecordResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsRecordGraduation",
)
def graduation_record(request, student_id: UUID, payload: GraduationRecordRequest):
    _require(request, "student_academics.manage", recent_mfa=True)
    try:
        item = record_graduation(
            student_id=student_id,
            graduated_college_id=payload.graduated_college_id,
            graduation_date=payload.graduation_date,
            verification_source=payload.verification_source,
            context=_context(request),
        )
    except StudentAcademicError as exc:
        _raise(exc)
    return _graduation(item)


@router.post(
    "/imports/csv",
    response=response_with_errors(RosterImportResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsImportRosterCsv",
    summary="Validate or commit an approved Student academic roster CSV",
)
def roster_csv_import(
    request,
    file: File[UploadedFile],
    dry_run: bool = True,
):
    _require(request, "student_academics.import", recent_mfa=True)
    data = file.read(MAX_CSV_BYTES + 1)
    try:
        report = import_student_academic_roster(
            context=_context(request),
            data=data,
            dry_run=dry_run,
        )
    except RosterImportTooLarge as exc:
        raise APIError(422, "csv_import_too_large", str(exc)) from exc
    except RosterImportUnsupportedHeaders as exc:
        raise APIError(422, "csv_import_unsupported_headers", str(exc)) from exc
    except RosterImportMalformed as exc:
        raise APIError(422, "csv_import_malformed", str(exc)) from exc
    except RosterImportDuplicateIdentity as exc:
        raise APIError(
            422,
            "csv_import_duplicate_identity",
            str(exc),
            details=_roster_issue_details(exc.issues),
        ) from exc
    except RosterImportInvalidRows as exc:
        raise APIError(
            422,
            "csv_import_invalid_rows",
            str(exc),
            details=_roster_issue_details(exc.issues),
        ) from exc
    except RosterImportConflict as exc:
        raise APIError(
            409,
            "csv_import_conflict",
            str(exc),
            details=[
                {
                    "row_number": row.row_number,
                    "institutional_id": row.institutional_id,
                    "message": row.message,
                }
                for row in exc.rows
            ],
        ) from exc
    return _roster_report_payload(report)


def _batch_report(report) -> dict[str, object]:
    payload = {
        name: getattr(report, name) for name in report.__dataclass_fields__ if name != "rows"
    }
    payload["rows"] = [
        {name: getattr(row, name) for name in row.__dataclass_fields__} for row in report.rows
    ]
    return payload


def _run_batch_import(run):
    """Map the shared CSV import failures onto the roster import's stable error codes."""

    try:
        return _batch_report(run())
    except StudentAcademicError as exc:
        _raise(exc)
    except RosterImportTooLarge as exc:
        raise APIError(422, "csv_import_too_large", str(exc)) from exc
    except RosterImportUnsupportedHeaders as exc:
        raise APIError(422, "csv_import_unsupported_headers", str(exc)) from exc
    except RosterImportMalformed as exc:
        raise APIError(422, "csv_import_malformed", str(exc)) from exc
    except RosterImportDuplicateIdentity as exc:
        raise APIError(
            422,
            "csv_import_duplicate_identity",
            str(exc),
            details=_roster_issue_details(exc.issues),
        ) from exc
    except RosterImportInvalidRows as exc:
        raise APIError(
            422, "csv_import_invalid_rows", str(exc), details=_roster_issue_details(exc.issues)
        ) from exc
    except BatchImportPreviewRequired as exc:
        raise APIError(422, "csv_import_preview_required", str(exc)) from exc
    except BatchImportConfirmationMismatch as exc:
        raise APIError(422, "csv_import_confirmation_mismatch", str(exc)) from exc
    except BatchImportStale as exc:
        raise APIError(409, "csv_import_stale", str(exc)) from exc
    except RosterImportConflict as exc:
        raise APIError(
            409,
            "csv_import_conflict",
            str(exc),
            details=[
                {
                    "row_number": row.row_number,
                    "institutional_id": row.institutional_id,
                    "message": row.message,
                }
                for row in exc.rows
            ],
        ) from exc


@router.post(
    "/imports/periods/csv",
    response=response_with_errors(PeriodImportResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsImportPeriodsCsv",
    summary="Validate or commit a CSV of term records for one academic year and term",
)
def periods_csv_import(
    request,
    file: File[UploadedFile],
    academic_year_id: Form[UUID],
    term: Form[AcademicTerm],
    preview_fingerprint: Form[str | None] = None,
    dry_run: bool = True,
):
    _require(request, "student_academics.import", recent_mfa=True)
    data = file.read(MAX_CSV_BYTES + 1)
    return _run_batch_import(
        lambda: import_student_academic_periods(
            context=_context(request),
            data=data,
            academic_year_id=academic_year_id,
            term=term,
            dry_run=dry_run,
            preview_fingerprint=preview_fingerprint,
        )
    )


@router.post(
    "/imports/graduations/csv",
    response=response_with_errors(GraduationImportResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="studentAcademicsImportGraduationsCsv",
    summary="Validate or commit a CSV of graduation records",
)
def graduations_csv_import(
    request,
    file: File[UploadedFile],
    verification_source: Form[str],
    preview_fingerprint: Form[str | None] = None,
    confirmed_count: Form[int | None] = None,
    dry_run: bool = True,
):
    _require(request, "student_academics.import", recent_mfa=True)
    data = file.read(MAX_CSV_BYTES + 1)
    return _run_batch_import(
        lambda: import_student_graduations(
            context=_context(request),
            data=data,
            verification_source=verification_source,
            dry_run=dry_run,
            preview_fingerprint=preview_fingerprint,
            confirmed_count=confirmed_count,
        )
    )
