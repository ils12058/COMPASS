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
GRADUATE_TRACER_TARGET_TYPE = "reports.graduatetracer"
GOOD_MORAL_TARGET_TYPE = "goodmoral.request"
REFERRAL_TARGET_TYPE = "referrals.referral"
CALL_SLIP_TARGET_TYPE = "callslips.callslip"


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


def record_graduate_tracer_release(
    *,
    context: AuditContext,
    release_context: Mapping[str, object],
) -> None:
    schema_version = release_context.get("instrument_schema_version")
    if schema_version != 1:
        raise ValueError("unsupported Graduate Tracer schema version")
    _record_release(
        context=context,
        action=REPORT_EXPORT_RELEASED,
        target_type=GRADUATE_TRACER_TARGET_TYPE,
        target_id=schema_version,
        metadata={
            "report_type": "graduate_tracer",
            "format": "XLSX",
            "instrument_schema_version": schema_version,
            "submitted_from": release_context.get("submitted_from"),
            "submitted_to": release_context.get("submitted_to"),
        },
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


def record_referral_release(
    *,
    context: AuditContext,
    referral_id,
    form_revision_id,
    official_code: str | None,
    official_revision: str | None,
) -> None:
    _record_release(
        context=context,
        action=DOCUMENT_DOWNLOAD_RELEASED,
        target_type=REFERRAL_TARGET_TYPE,
        target_id=referral_id,
        metadata={
            "document_type": "referral_slip",
            "access_mode": "GCO",
            "form_revision_id": str(form_revision_id),
            "official_code": official_code,
            "official_revision": official_revision,
        },
    )


def record_call_slip_release(
    *,
    context: AuditContext,
    call_slip_id,
    access_mode: str,
    form_revision_id,
    official_code: str | None,
    official_revision: str | None,
) -> None:
    normalized_access = str(access_mode).strip().upper()
    if normalized_access not in {"SELF", "GCO"}:
        raise ValueError("unsupported Call Slip release access mode")
    _record_release(
        context=context,
        action=DOCUMENT_DOWNLOAD_RELEASED,
        target_type=CALL_SLIP_TARGET_TYPE,
        target_id=call_slip_id,
        metadata={
            "document_type": "call_slip",
            "access_mode": normalized_access,
            "form_revision_id": str(form_revision_id),
            "official_code": official_code,
            "official_revision": official_revision,
        },
    )


__all__ = [
    "CALL_SLIP_TARGET_TYPE",
    "GOOD_MORAL_TARGET_TYPE",
    "GRADUATE_TRACER_TARGET_TYPE",
    "REFERRAL_TARGET_TYPE",
    "ReleaseAuditUnavailable",
    "STUDENT_PROFILING_TARGET_TYPE",
    "record_call_slip_release",
    "record_good_moral_release",
    "record_graduate_tracer_release",
    "record_referral_release",
    "record_student_profiling_release",
]
