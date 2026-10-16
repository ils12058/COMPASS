"""Synthetic historical evidence left by the retired ADR-072 engine (ADR-114). Test-only.

COMPASS no longer creates rules, cases, anonymous contributions or disposed media. These helpers
write the rows the retired engine would have committed, so tests can prove that historical
evidence stays intact, readable and fenced without exercising any destructive code path.
"""

import uuid
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
from compass.privacy_governance.retention import SUPPORTED_CONTRACTS
from compass.privacy_governance.retention_models import (
    DispositionCase,
    DispositionHold,
    OperationalRetentionRule,
)

MEDIA_CATEGORY = {"RECORDING": "ECOUNSELING_RECORDING", "TRANSCRIPTION": "ECOUNSELING_TRANSCRIPT"}


def legacy_rule(*, actor, category="GRADUATE_TRACER", contract_version=1, status="RETIRED"):
    trigger, action = SUPPORTED_CONTRACTS[(category, contract_version)]
    now = timezone.now()
    return OperationalRetentionRule.objects.create(
        code=f"LEGACY-{category}-V{contract_version}-{status}",
        label="Synthetic legacy rule",
        category=category,
        contract_version=contract_version,
        trigger=trigger,
        duration_days=30,
        action=action,
        policy_reference="TEST FIXTURE ONLY - not institutional policy",
        effective_on=institution_today() - timedelta(days=60),
        status=status,
        revision=3 if status == "RETIRED" else 2,
        created_by=actor,
        updated_by=actor,
        activated_by=actor,
        activated_at=now - timedelta(days=45),
        retired_by=actor if status == "RETIRED" else None,
        retired_at=now - timedelta(days=1) if status == "RETIRED" else None,
    )


def legacy_case(*, rule, source, state, blocker=None, hold_reason=None):
    now = timezone.now()
    approved = state in {
        "APPROVED",
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "RECONCILIATION_REQUIRED",
    }
    case = DispositionCase.objects.create(
        rule=rule,
        rule_revision=rule.revision,
        category=rule.category,
        contract_version=rule.contract_version,
        source_id=source.pk,
        source_updated_at=source.updated_at,
        eligible_at=now - timedelta(days=2),
        state=state,
        blocker=blocker,
        revision=4,
        approved_by=rule.created_by if approved else None,
        approved_at=now - timedelta(hours=2) if approved else None,
        started_at=now - timedelta(hours=1)
        if state in {"PROCESSING", "COMPLETED", "FAILED", "RECONCILIATION_REQUIRED"}
        else None,
        completed_at=now - timedelta(minutes=30) if state == "COMPLETED" else None,
        claim_token=uuid.uuid4() if state == "PROCESSING" else None,
        attempts=1 if approved and state not in {"APPROVED", "QUEUED"} else 0,
        next_attempt_at=now - timedelta(minutes=1) if state == "QUEUED" else None,
    )
    if hold_reason:
        DispositionHold.objects.create(case=case, reason=hold_reason, placed_by=rule.created_by)
    return case


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


def media_category(capture):
    return MEDIA_CATEGORY[capture.kind]


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
