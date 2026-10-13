"""Closed operational diagnostics: no resource IDs, locations, payloads or exception prose."""

import logging
from enum import StrEnum

from compass.integrations.daily import DailyError, safe_daily_failure_code

from .models import (
    CaptureEvidence,
    CaptureReconciliationOutcome,
    MediaCaptureKind,
    WebhookAnomaly,
    WebhookMitigation,
    WebhookOutcome,
    WebhookSeverity,
)

INGEST_TASK = "compass.ecounseling.ingest_media_artifact"
RECOVERY_TASK = "compass.ecounseling.recover_media_artifacts"
CAPTURE_RECONCILIATION_TASK = "compass.ecounseling.reconcile_media_captures"
logger = logging.getLogger("compass.ecounseling.diagnostics")


class WebhookReplayTaskError(RuntimeError):
    def __init__(self, *_):
        super().__init__("Media webhook replay failed: INTERNAL_UNVERIFIED")


def log_media_webhook(receipt):
    outcome = (
        receipt.processing_outcome
        if receipt.processing_outcome in WebhookOutcome.values
        else WebhookOutcome.MALFORMED
    )
    code = receipt.anomaly_code if receipt.anomaly_code in WebhookAnomaly.values else None
    mitigation = (
        receipt.mitigation_state if receipt.mitigation_state in WebhookMitigation.values else None
    )
    logger.log(
        logging.ERROR
        if receipt.severity == WebhookSeverity.PRIVACY
        else logging.WARNING
        if code
        else logging.INFO,
        "E-Counseling media webhook diagnostic",
        extra={
            "event": "ecounseling_media_webhook",
            "pipeline_stage": "WEBHOOK",
            "outcome_code": code or outcome,
            "mitigation_state": mitigation,
            "attempt_number": _count(receipt.processing_attempts),
            "identity_verified": type(receipt.identity_verified) is bool
            and receipt.identity_verified,
            "retry_scheduled": receipt.next_attempt_at is not None,
            "escalation_required": type(receipt.operator_review_required) is bool
            and receipt.operator_review_required,
        },
    )


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


class CaptureStage(StrEnum):
    UNKNOWN = "INTERNAL_UNVERIFIED"
    SCAN = "SCAN"
    DISCOVERY = "DISCOVERY"
    CLAIM = "CLAIM"
    METADATA = "METADATA"
    APPLY = "APPLY"


class CaptureReconciliationTaskError(RuntimeError):
    def __init__(self, stage=CaptureStage.UNKNOWN):
        if isinstance(stage, str) and stage.startswith("Capture reconciliation failed: "):
            stage = stage.removeprefix("Capture reconciliation failed: ")
        try:
            self.diagnostic_stage = CaptureStage(stage)
        except (ValueError, TypeError):
            self.diagnostic_stage = CaptureStage.UNKNOWN
        super().__init__(f"Capture reconciliation failed: {self.diagnostic_stage.value}")


def log_capture_reconciliation(
    *,
    stage=CaptureStage.UNKNOWN,
    kind=None,
    outcome=CaptureReconciliationOutcome.UNKNOWN,
    attempts=None,
    evidence=CaptureEvidence.UNKNOWN,
    retry_scheduled=None,
    delay_seconds=None,
    duration_ms=None,
    terminal_confirmed=None,
    escalation_required=None,
):
    stage = stage if isinstance(stage, CaptureStage) else CaptureStage.UNKNOWN
    outcome = (
        outcome
        if isinstance(outcome, str) and outcome in CaptureReconciliationOutcome.values
        else CaptureReconciliationOutcome.UNKNOWN
    )
    logger.log(
        logging.ERROR
        if outcome == CaptureReconciliationOutcome.PRIVACY
        else logging.WARNING
        if escalation_required is True or stage == CaptureStage.UNKNOWN
        else logging.INFO,
        "E-Counseling capture reconciliation diagnostic",
        extra={
            "event": "ecounseling_capture_reconciliation",
            "task_name": CAPTURE_RECONCILIATION_TASK,
            "pipeline_stage": stage.value,
            "media_kind": kind
            if isinstance(kind, str) and kind in MediaCaptureKind.values
            else None,
            "outcome_code": outcome,
            "attempt_number": _count(attempts),
            "provider_evidence": (
                evidence
                if isinstance(evidence, str) and evidence in CaptureEvidence.values
                else CaptureEvidence.UNKNOWN
            ),
            "retry_scheduled": retry_scheduled if type(retry_scheduled) is bool else None,
            "next_attempt_in_seconds": _count(delay_seconds),
            "duration_ms": _count(duration_ms),
            "terminal_evidence_confirmed": (
                terminal_confirmed if type(terminal_confirmed) is bool else None
            ),
            "escalation_required": (
                escalation_required if type(escalation_required) is bool else None
            ),
        },
    )


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
