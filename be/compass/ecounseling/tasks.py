"""The same worker/Beat deployment owns ingestion and custody-transfer recovery."""

from datetime import timedelta
from time import monotonic

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from compass.tasks import CorrelationTask

from .artifacts import enqueue_artifact, ingest_artifact
from .diagnostics import RECOVERY_TASK, ArtifactStage, ArtifactTaskError, log_artifact_diagnostic
from .models import ECounselingMediaArtifact


@shared_task(
    name="compass.ecounseling.ingest_media_artifact",
    base=CorrelationTask,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=30 * 60,
    time_limit=35 * 60,
)
def ingest_media_artifact(artifact_id):
    try:
        ingest_artifact(artifact_id)
    except ArtifactTaskError as error:
        raise ArtifactTaskError(error.diagnostic_stage) from None
    except Exception:
        # Failures outside the classified pipeline (including claim/lock finalizers) have no
        # verified stage. Do not let DB/adapter prose reach Celery failure logs/results.
        log_artifact_diagnostic(stage=ArtifactStage.UNKNOWN)
        raise ArtifactTaskError(ArtifactStage.UNKNOWN) from None


@shared_task(name="compass.ecounseling.recover_media_artifacts", base=CorrelationTask)
def recover_media_artifacts():
    try:
        now = timezone.now()
        ids = list(
            ECounselingMediaArtifact.objects.filter(
                Q(status__in=("PENDING", "FAILED"), next_attempt_at__lte=now)
                | Q(status="PROCESSING", claimed_at__lt=now - timedelta(minutes=30))
                | Q(status="STORED", provider_deleted_at__isnull=True, next_attempt_at__lte=now)
            )
            .order_by("next_attempt_at", "id")
            .values_list("id", flat=True)[:100]
        )
        for artifact_id in ids:
            enqueue_artifact(artifact_id)
        log_artifact_diagnostic(
            stage=ArtifactStage.RECOVERY,
            outcome_code="RECOVERY_SCAN_COMPLETE",
            task_name=RECOVERY_TASK,
        )
        return len(ids)
    except Exception:
        log_artifact_diagnostic(stage=ArtifactStage.RECOVERY, task_name=RECOVERY_TASK)
        raise ArtifactTaskError(ArtifactStage.RECOVERY) from None


@shared_task(
    name="compass.ecounseling.reconcile_media_captures",
    base=CorrelationTask,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=150,
)
def reconcile_media_captures():
    from .diagnostics import (
        CaptureReconciliationTaskError,
        CaptureStage,
        log_capture_reconciliation,
    )
    from .reconciliation import reconcile_captures

    started = monotonic()
    try:
        counts = reconcile_captures()
    except Exception:
        log_capture_reconciliation(stage=CaptureStage.UNKNOWN)
        raise CaptureReconciliationTaskError() from None
    log_capture_reconciliation(
        stage=CaptureStage.SCAN,
        duration_ms=max(0, int((monotonic() - started) * 1000)),
    )
    return counts
