"""Restricted read-only API for Student Profiling aggregate reports."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Router

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .pdf import (
    StudentProfilingDocumentUnavailable,
    render_student_profiling_pdf,
)
from .schemas import StudentProfilingReportResponse
from .services import (
    InvalidReportFilter,
    ReportConfigurationConflict,
    ReportError,
    ReportNotFound,
    build_student_profiling_report,
)

router = Router(tags=["reports"])


def _require_viewer(request) -> None:
    actor = request.auth_user
    if not actor.is_active or not actor.has_capability("reports.view"):
        raise APIError(
            403,
            "permission_denied",
            "Head Guidance aggregate-report authority is required.",
        )


def _raise(exc: ReportError) -> NoReturn:
    if isinstance(exc, ReportNotFound):
        raise APIError(404, "report_filter_not_found", str(exc)) from exc
    if isinstance(exc, ReportConfigurationConflict):
        raise APIError(409, "report_configuration_conflict", str(exc)) from exc
    if isinstance(exc, InvalidReportFilter):
        raise APIError(422, "invalid_report_filter", str(exc)) from exc
    if isinstance(exc, StudentProfilingDocumentUnavailable):
        raise APIError(
            503,
            "report_document_unavailable",
            "The Student Profiling report PDF is temporarily unavailable.",
        ) from exc
    raise APIError(
        500,
        "internal_error",
        "The Student Profiling report could not be generated.",
    ) from exc


@router.get(
    "/student-profile",
    response=response_with_errors(StudentProfilingReportResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="reportsGetStudentProfile",
)
def student_profile(
    request,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
):
    _require_viewer(request)
    try:
        return build_student_profiling_report(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            college_id=college_id,
            program_id=program_id,
            year_level=year_level,
        )
    except ReportError as exc:
        _raise(exc)


@router.get(
    "/student-profile/pdf",
    response=response_with_errors(None, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="reportsDownloadStudentProfilePdf",
)
def student_profile_pdf(
    request,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
):
    _require_viewer(request)
    try:
        result = render_student_profiling_pdf(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            college_id=college_id,
            program_id=program_id,
            year_level=year_level,
        )
    except ReportError as exc:
        _raise(exc)

    response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
    return response
