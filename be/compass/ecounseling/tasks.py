"""The same worker/Beat deployment owns ingestion and custody-transfer recovery."""

from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from compass.tasks import CorrelationTask

from .artifacts import enqueue_artifact, ingest_artifact
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
    ingest_artifact(artifact_id)


@shared_task(name="compass.ecounseling.recover_media_artifacts", base=CorrelationTask)
def recover_media_artifacts():
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
    return len(ids)
