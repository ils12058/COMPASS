"""Fail-closed audit helpers for sensitive report/document release."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from compass.audit.actions import DOCUMENT_DOWNLOAD_RELEASED, REPORT_EXPORT_RELEASED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

logger = logging.getLogger("compass.privacy_governance")

STUDENT_PROFILING_TARGET_TYPE = "reports.studentprofiling"
GOOD_MORAL_TARGET_TYPE = "goodmoral.request"


class ReleaseAuditUnavailable(RuntimeError):
    """A required sensitive-release AuditEvent could not be appended."""


def _record_release(
    *,
    context: AuditContext,
    action: str,
    target_type: str,
    target_id,
    metadata: Mapping[str, object],
) -> None:
    try:
        record_event(
            context=context,
            action=action,
            outcome=AuditOutcome.SUCCESS,
            target_type=target_type,
            target_id=target_id,
            metadata=dict(metadata),
        )
    except Exception as exc:
        logger.error(
            "sensitive artifact release audit failed",
            extra={
                "event": "sensitive_release_audit_failed",
                "action": action,
                "target_type": target_type,
                "target_id": str(target_id) if target_id is not None else None,
            },
        )
        raise ReleaseAuditUnavailable(
            "the required privacy release audit could not be recorded"
        ) from exc


def record_student_profiling_release(
    *,
    context: AuditContext,
    artifact_format: str,
    release_context: Mapping[str, object],
) -> None:
    normalized_format = str(artifact_format).strip().upper()
    if normalized_format not in {"PDF", "XLSX"}:
        raise ValueError("unsupported Student Profiling release format")
    metadata = {
        "report_type": "student_profiling",
        "format": normalized_format,
        "academic_year_id": release_context.get("academic_year_id"),
        "academic_year_label": release_context.get("academic_year_label"),
        "campus_id": release_context.get("campus_id"),
        "campus_code": release_context.get("campus_code"),
        "college_id": release_context.get("college_id"),
        "college_code": release_context.get("college_code"),
        "program_id": release_context.get("program_id"),
        "program_code": release_context.get("program_code"),
        "year_level": release_context.get("year_level"),
    }
    _record_release(
        context=context,
        action=REPORT_EXPORT_RELEASED,
        target_type=STUDENT_PROFILING_TARGET_TYPE,
        target_id=release_context.get("academic_year_id"),
        metadata=metadata,
    )


def record_good_moral_release(
    *,
    context: AuditContext,
    request_id,
    variant: str,
    access_mode: str,
) -> None:
    normalized_access = str(access_mode).strip().upper()
    if normalized_access not in {"SELF", "GCO"}:
        raise ValueError("unsupported Good Moral release access mode")
    _record_release(
        context=context,
        action=DOCUMENT_DOWNLOAD_RELEASED,
        target_type=GOOD_MORAL_TARGET_TYPE,
        target_id=request_id,
        metadata={
            "document_type": "good_moral_certificate",
            "variant": str(variant),
            "access_mode": normalized_access,
        },
    )


__all__ = [
    "GOOD_MORAL_TARGET_TYPE",
    "ReleaseAuditUnavailable",
    "STUDENT_PROFILING_TARGET_TYPE",
    "record_good_moral_release",
    "record_student_profiling_release",
]
