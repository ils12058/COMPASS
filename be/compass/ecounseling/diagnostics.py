"""Closed operational diagnostics: no resource IDs, locations, payloads or exception prose."""

import logging
from enum import StrEnum

from compass.integrations.daily import DailyError, safe_daily_failure_code

INGEST_TASK = "compass.ecounseling.ingest_media_artifact"
RECOVERY_TASK = "compass.ecounseling.recover_media_artifacts"
logger = logging.getLogger("compass.ecounseling.diagnostics")


class ArtifactStage(StrEnum):
    UNKNOWN = "INTERNAL_UNVERIFIED"
    CLAIM = "CLAIM_COMMIT_UNVERIFIED"
    STORAGE_POLICY = "STORAGE_POLICY_UNVERIFIED"
    BINDING = "STORAGE_BINDING_UNVERIFIED"
    PROVIDER_METADATA = "PROVIDER_METADATA_FAILED"
    PROVIDER_IDENTITY = "PROVIDER_IDENTITY_UNVERIFIED"
    ACCESS_LINK = "ACCESS_LINK_FAILED"
    LINK_VALIDATION = "ACCESS_LINK_UNVERIFIED"
    TRANSFER = "MEDIA_TRANSFER_FAILED"
    DOWNLOAD_VALIDATION = "DOWNLOAD_UNVERIFIED"
    PRECOMMIT = "PRE_CUSTODY_COMMIT_UNVERIFIED"
    UPLOAD = "CANONICAL_UPLOAD_UNVERIFIED"
    INTEGRITY = "CANONICAL_INTEGRITY_UNVERIFIED"
    CUSTODY_COMMIT = "CUSTODY_COMMIT_UNVERIFIED"
    PROVIDER_CLEANUP = "PROVIDER_CLEANUP_UNVERIFIED"
    CLEANUP_COMMIT = "CLEANUP_COMMIT_UNVERIFIED"
    RETRY_COMMIT = "RETRY_COMMIT_UNVERIFIED"
    DISPATCH = "TASK_DISPATCH_FAILED"
    RECOVERY = "RECOVERY_UNVERIFIED"


class ArtifactTaskError(RuntimeError):
    """Only a closed stage code is passed to Celery failure/result handling."""

    def __init__(self, stage=ArtifactStage.UNKNOWN):
        # Celery/exception pickling reconstructs from args. Accept only our exact closed message
        # forms as well as stage values, so reconstruction preserves the code without prose.
        if isinstance(stage, str) and stage.startswith("Media task failed: "):
            stage = stage.removeprefix("Media task failed: ")
        try:
            self.diagnostic_stage = ArtifactStage(stage)
        except (ValueError, TypeError):
            self.diagnostic_stage = ArtifactStage.UNKNOWN
        super().__init__(f"Media task failed: {self.diagnostic_stage.value}")


_SUCCESS_OUTCOMES = frozenset(
    {
        "PROCESSING",
        "STALE_CLAIM_RECLAIMED",
        "LOCK_BUSY",
        "INELIGIBLE",
        "RETRY_NOT_DUE",
        "ALREADY_CLEANED",
        "SUPERSEDED",
        "PROVIDER_CLEANED",
        "DISPATCHED",
        "RECOVERY_SCAN_COMPLETE",
    }
)
_OUTCOMES = _SUCCESS_OUTCOMES | frozenset(ArtifactStage)


def _count(value):
    return value if type(value) is int and value >= 0 else None


def log_artifact_diagnostic(
    *,
    stage=ArtifactStage.UNKNOWN,
    outcome_code=None,
    task_name=INGEST_TASK,
    attempt_number=None,
    retry_scheduled=None,
    next_attempt_in_seconds=None,
    duration_ms=None,
    custody_committed=None,
    provider_error=None,
):
    stage = stage if isinstance(stage, ArtifactStage) else ArtifactStage.UNKNOWN
    outcome = (
        outcome_code if isinstance(outcome_code, str) and outcome_code in _OUTCOMES else stage.value
    )
    logger.log(
        logging.INFO if outcome in _SUCCESS_OUTCOMES else logging.WARNING,
        "E-Counseling media diagnostic",
        extra={
            "event": "ecounseling_media_diagnostic",
            "task_name": (
                task_name
                if isinstance(task_name, str) and task_name in {INGEST_TASK, RECOVERY_TASK}
                else INGEST_TASK
            ),
            "pipeline_stage": stage.name,
            "outcome_code": outcome,
            "attempt_number": _count(attempt_number),
            "retry_scheduled": retry_scheduled if type(retry_scheduled) is bool else None,
            "next_attempt_in_seconds": _count(next_attempt_in_seconds),
            "duration_ms": _count(duration_ms),
            "custody_committed": custody_committed if type(custody_committed) is bool else None,
            "provider_failure_code": (
                safe_daily_failure_code(provider_error).value
                if isinstance(provider_error, DailyError)
                else None
            ),
        },
    )
