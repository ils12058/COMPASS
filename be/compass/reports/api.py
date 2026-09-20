"""Restricted read-only API for Student Profiling aggregate reports."""

from __future__ import annotations

from datetime import date
from typing import NoReturn
from uuid import UUID

from django.http import HttpResponse
from ninja import Router

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.privacy_governance.releases import (
    ReleaseAuditUnavailable,
    record_graduate_tracer_release,
    record_student_profiling_release,
)

from .graduate_tracer import (
    GraduateTracerReportError,
    InvalidGraduateTracerReportFilter,
    build_graduate_tracer_report,
)
from .graduate_tracer_schemas import GraduateTracerReportResponse
from .graduate_tracer_xlsx import (
    GraduateTracerWorkbookUnavailable,
    render_graduate_tracer_xlsx,
)
from .pdf import (
    StudentProfilingDocumentUnavailable,
    render_student_profiling_pdf,
)
from .schemas import StudentProfilingReportResponse
from .services import (
    InvalidReportFilter,
    ReportAccessDenied,
    ReportAccessScope,
    ReportConfigurationConflict,
    ReportError,
    ReportNotFound,
    build_student_profiling_report,
    resolve_report_access_scope,
)
from .xlsx import (
    XLSX_CONTENT_TYPE,
    StudentProfilingWorkbookUnavailable,
    render_student_profiling_xlsx,
)

router = Router(tags=["reports"])

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
XLSX_SUCCESS_OPENAPI = {
    "responses": {
        200: {
            "content": {
                XLSX_CONTENT_TYPE: {
                    "schema": {"type": "string", "format": "binary"},
                }
            }
        }
    }
}


def _require_viewer(request) -> ReportAccessScope:
    try:
        return resolve_report_access_scope(request.auth_user)
    except ReportAccessDenied as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc


def _require_global_viewer(request) -> None:
    access_scope = _require_viewer(request)
    if not access_scope.is_global:
        raise APIError(
            403,
            "permission_denied",
            "Institution-wide aggregate report access is required.",
        )


def _raise(exc: ReportError) -> NoReturn:
    if isinstance(exc, ReportAccessDenied):
        raise APIError(403, "permission_denied", str(exc)) from exc
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
    if isinstance(exc, StudentProfilingWorkbookUnavailable):
        raise APIError(
            503,
            "report_workbook_unavailable",
            "The Student Profiling report XLSX is temporarily unavailable.",
        ) from exc
    raise APIError(
        500,
        "internal_error",
        "The Student Profiling report could not be generated.",
    ) from exc


def _raise_graduate_tracer(exc: GraduateTracerReportError) -> NoReturn:
    if isinstance(exc, InvalidGraduateTracerReportFilter):
        raise APIError(422, "invalid_report_filter", str(exc)) from exc
    if isinstance(exc, GraduateTracerWorkbookUnavailable):
        raise APIError(
            503,
            "report_workbook_unavailable",
            "The Graduate Tracer report XLSX is temporarily unavailable.",
        ) from exc
    raise APIError(
        500,
        "internal_error",
        "The Graduate Tracer report could not be generated.",
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
    access_scope = _require_viewer(request)
    try:
        return build_student_profiling_report(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            college_id=college_id,
            program_id=program_id,
            year_level=year_level,
            access_scope=access_scope,
        )
    except ReportError as exc:
        _raise(exc)


@router.get(
    "/student-profile/pdf",
    response=response_with_errors(None, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="reportsDownloadStudentProfilePdf",
    openapi_extra=PDF_SUCCESS_OPENAPI,
)
def student_profile_pdf(
    request,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
):
    access_scope = _require_viewer(request)
    try:
        result = render_student_profiling_pdf(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            college_id=college_id,
            program_id=program_id,
            year_level=year_level,
            access_scope=access_scope,
        )
    except ReportError as exc:
        _raise(exc)

    try:
        record_student_profiling_release(
            context=AuditContext.from_request(request, actor=request.auth_user),
            artifact_format="PDF",
            release_context=result.release_context,
        )
    except ReleaseAuditUnavailable as exc:
        raise APIError(
            503,
            "release_audit_unavailable",
            "The report could not be released because its required privacy audit is unavailable.",
        ) from exc

    response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
    return response


@router.get(
    "/student-profile/xlsx",
    response=response_with_errors(None, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="reportsDownloadStudentProfileXlsx",
    openapi_extra=XLSX_SUCCESS_OPENAPI,
)
def student_profile_xlsx(
    request,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
):
    access_scope = _require_viewer(request)
    try:
        result = render_student_profiling_xlsx(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            college_id=college_id,
            program_id=program_id,
            year_level=year_level,
            access_scope=access_scope,
        )
    except ReportError as exc:
        _raise(exc)

    try:
        record_student_profiling_release(
            context=AuditContext.from_request(request, actor=request.auth_user),
            artifact_format="XLSX",
            release_context=result.release_context,
        )
    except ReleaseAuditUnavailable as exc:
        raise APIError(
            503,
            "release_audit_unavailable",
            "The report could not be released because its required privacy audit is unavailable.",
        ) from exc

    response = HttpResponse(result.xlsx_bytes, content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
    return response


@router.get(
    "/graduate-tracer",
    response=response_with_errors(GraduateTracerReportResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="reportsGetGraduateTracer",
)
def graduate_tracer(
    request,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
):
    _require_global_viewer(request)
    try:
        return build_graduate_tracer_report(
            submitted_from=submitted_from,
            submitted_to=submitted_to,
        )
    except GraduateTracerReportError as exc:
        _raise_graduate_tracer(exc)


@router.get(
    "/graduate-tracer/xlsx",
    response=response_with_errors(None, 401, 403, 422, 503),
    auth=session_auth,
    operation_id="reportsDownloadGraduateTracerXlsx",
    openapi_extra=XLSX_SUCCESS_OPENAPI,
)
def graduate_tracer_xlsx(
    request,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
):
    _require_global_viewer(request)
    try:
        result = render_graduate_tracer_xlsx(
            submitted_from=submitted_from,
            submitted_to=submitted_to,
        )
    except GraduateTracerReportError as exc:
        _raise_graduate_tracer(exc)

    try:
        record_graduate_tracer_release(
            context=AuditContext.from_request(request, actor=request.auth_user),
            release_context=result.release_context,
        )
    except ReleaseAuditUnavailable as exc:
        raise APIError(
            503,
            "release_audit_unavailable",
            "The report could not be released because its required privacy audit is unavailable.",
        ) from exc

    response = HttpResponse(result.xlsx_bytes, content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
    return response
