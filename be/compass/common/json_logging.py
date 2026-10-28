"""Structured JSON logs with safe request/task context."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from compass.common.correlation import get_current_request_id

_CONTEXT_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "task_name",
    "task_id",
)

# Reviewed operational context that callers pass through ``extra``. Add a name only when every
# caller supplies an identifier, closed code, count, or class name. Never add fields for
# credentials, tokens, OTP or recovery codes, keys, signed URLs, storage keys, request, response,
# or email bodies, confidential content, exception messages, or metadata mappings.
_DIAGNOSTIC_FIELDS = (
    # Notification email and Web Push delivery.
    "notification_id",
    "notification_event_code",
    "email_delivery_id",
    "delivery_id",
    "attempt_number",
    "delivery_status",
    "failure_code",
    "presentation_reason",
    # PostgreSQL rejection mapped by the API error handlers.
    "sqlstate",
    # Authentication email recovery and audit fallbacks.
    "challenge_id",
    "email_change_request_id",
    "action",
    "target_type",
    "target_id",
    # Domain and provider operations.
    "resource_id",
    "cleanup",
    "routine_interview_id",
    "section",
    "reason",
    "media_kind",
    "operation",
    "version",
    "check_code",
    # E-Counseling's closed stage/outcome codes and numeric/boolean attempt metadata.
    "pipeline_stage",
    "outcome_code",
    "retry_scheduled",
    "next_attempt_in_seconds",
    "custody_committed",
    "provider_failure_code",
    # Capture reconciliation emits only a closed evidence category and two booleans.
    "provider_evidence",
    "terminal_evidence_confirmed",
    "escalation_required",
    # Signed media webhook diagnostics supply only closed mitigation and verified-identity flags.
    "mitigation_state",
    "identity_verified",
    "truncated_field_count",
    # Exception class names only; messages are never logged.
    "error_type",
    "exception_class",
)

# Diagnostic strings must look like an identifier or code. Prose, exception messages, URLs, and
# serialized structures fail this check and are dropped even under an approved field name.
_DIAGNOSTIC_TEXT = re.compile(r"[A-Za-z0-9_.-]{1,128}")


def _diagnostic_value(value: object) -> str | int | float | None:
    if isinstance(value, int | float):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str) and _DIAGNOSTIC_TEXT.fullmatch(value):
        return value
    return None


class JsonFormatter(logging.Formatter):
    """Emit controlled fields and never serialize request bodies or query strings."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        request_id = getattr(record, "request_id", None) or get_current_request_id()
        if request_id:
            payload["request_id"] = request_id

        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        for field in _DIAGNOSTIC_FIELDS:
            value = _diagnostic_value(getattr(record, field, None))
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__

        return json.dumps(payload, separators=(",", ":"), default=str)
