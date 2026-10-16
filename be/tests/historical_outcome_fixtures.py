"""Synthetic historical outcomes that the retired ADR-072 engine once committed. Test-only.

The canonical schema has no disposition ledger (ADR-114, CANON-1C) and COMPASS never creates these
outcomes. Graduate Tracer and E-Counseling still carry the resulting markers (an anonymous
contribution, disposed media), so these helpers write those rows directly to prove the surviving
readers, reports and fences keep honouring them. Nothing here exercises a destructive path.
"""

from datetime import timedelta

from django.utils import timezone

from compass.common.institutional_time import (
    institution_date,
    institution_day_start,
    institution_today,
)
from compass.graduate_tracer.disposition import ANALYTICAL_FIELDS
from compass.graduate_tracer.models import (
    GTS_SCHEMA_VERSION,
    GraduateTracerResponse,
    GraduateTracerStatus,
)
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation


def historical_anonymized_contribution(source):
    """The committed outcome of the retired anonymization executor, written directly."""
    submitted_day = institution_day_start(institution_date(source.submitted_at))
    operation_day = institution_day_start(institution_today())
    retained = GraduateTracerResponse.objects.create(
        student=None,
        confidential_content_ciphertext=None,
        instrument_schema_version=GTS_SCHEMA_VERSION,
        status=GraduateTracerStatus.SUBMITTED,
        submitted_at=submitted_day,
        anonymized_at=operation_day,
        **{field: getattr(source, field) for field in ANALYTICAL_FIELDS},
    )
    GraduateTracerResponse.objects.filter(pk=retained.pk).update(
        created_at=submitted_day, updated_at=operation_day
    )
    GraduateTracerDisposedParticipation.objects.get_or_create(
        student_id=source.student_id,
        instrument_schema_version=GTS_SCHEMA_VERSION,
        defaults={"disposed_on": institution_today()},
    )
    source.delete()
    retained.refresh_from_db()
    return retained


def historically_disposed_media(capture, artifact=None, storage=None):
    """The committed outcome of the retired media executors, written directly."""
    now = timezone.now()
    if artifact is not None:
        if storage is not None:
            storage.objects.pop(artifact.object_key, None)
        artifact.status, artifact.disposed_at = "DISPOSED", now
        artifact.object_key = artifact.sha256 = artifact.storage_binding = None
        artifact.content_type = artifact.size = None
        artifact.claim_token = artifact.claimed_at = artifact.next_attempt_at = None
        artifact.provider_deleted_at = artifact.provider_deleted_at or now
        artifact.save()
    capture.provider_artifact_id, capture.artifact_disposed_at = None, now
    capture.save(update_fields=["provider_artifact_id", "artifact_disposed_at", "updated_at"])
    return capture


def legacy_media_source(kind):
    """A version-one READY capture whose artifact stays provider-held (no COMPASS custody)."""
    from compass.ecounseling.models import (
        ECounselingConsent,
        ECounselingMediaCapture,
        ECounselingRoom,
    )
    from tests.test_ecounseling_media import setup_session

    _, student, counselor, appointment = setup_session(media_policy_version=2)
    room = ECounselingRoom.objects.create(
        appointment=appointment,
        daily_room_name="safe-opaque-room",
        media_policy_version=1,
        room_expires_at=timezone.now() - timedelta(days=31),
    )
    consent = ECounselingConsent.objects.create(
        room=room,
        scope="AUDIO_VIDEO_RECORDING" if kind == "RECORDING" else "TRANSCRIPT_STORAGE",
        requested_by=counselor,
        decision="APPROVED",
        decided_at=timezone.now() - timedelta(days=32),
        withdrawn_at=timezone.now() - timedelta(days=31),
    )
    source = ECounselingMediaCapture.objects.create(
        room=room,
        kind=kind,
        status="READY",
        provider_artifact_id="artifact-opaque",
        provider_instance_id="instance-opaque",
        ready_at=timezone.now() - timedelta(days=31),
    )
    return source, consent
