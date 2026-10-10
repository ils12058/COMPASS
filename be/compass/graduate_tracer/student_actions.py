"""Available surveys are voluntary; only an existing personal draft contributes."""

from .models import GraduateTracerResponse, GraduateTracerStatus
from .services import (
    GTS_SCHEMA_VERSION,
    GraduateTracerDisposed,
    GraduateTracerGraduatedStudentRequired,
    GraduateTracerNotPermitted,
    _require_personal_response_available,
    _validate_graduated_student_access,
)


def personal_draft(*, student):
    try:
        _validate_graduated_student_access(student, "graduate_tracer.manage_self")
        _require_personal_response_available(student)
    except (
        GraduateTracerNotPermitted,
        GraduateTracerGraduatedStudentRequired,
        GraduateTracerDisposed,
    ):
        return None
    return (
        GraduateTracerResponse.objects.filter(
            student_id=student.pk,
            instrument_schema_version=GTS_SCHEMA_VERSION,
            status=GraduateTracerStatus.DRAFT,
            anonymized_at__isnull=True,
        )
        .only("id", "created_at")
        .first()
    )
