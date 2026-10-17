"""Durable V2 custody and assigned access. Locations and provider links stay internal."""

import time
import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.core.files import File
from django.db import connection, transaction
from django.utils import timezone

from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.errors import APIError
from compass.common.institutional_time import institution_date
from compass.integrations.daily import DailyClient
from compass.integrations.media_download import (
    MediaDownloadError,
    MediaDownloadFailure,
    stream_daily_media,
    validate_daily_link,
)
from compass.integrations.storage import ObjectStorage

from .diagnostics import ArtifactStage, ArtifactTaskError, log_artifact_diagnostic
from .media import _load_session_appointment
from .media_realtime import media_changed_on_commit
from .models import (
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    MediaArtifactStatus,
    MediaCaptureStatus,
    MediaPolicyVersion,
)
from .services import _require_counselor_relationship


class ArtifactVerificationError(RuntimeError):
    pass


@contextmanager
def artifact_guard(artifact_id):
    """Session advisory lock fences duplicate workers during network IO, with no DB transaction."""
    key = uuid.UUID(str(artifact_id)).int % (2**63)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [key])


def artifact_eligible(capture):
    return (
        capture.room.media_policy_version == MediaPolicyVersion.V2
        and capture.status == MediaCaptureStatus.READY
        and not capture.artifact_disposed_at
        and not capture.provider_binding_quarantined_at
        and capture.provider_binding_verified_at is not None
        and capture.media_authorized_at is not None
        and (capture.kind == "RECORDING" or capture.transcript_storage_authorized)
    )


def ensure_pending_artifact(capture, *, publish_hint=True):
    if not artifact_eligible(capture):
        return None
    artifact, created = ECounselingMediaArtifact.objects.get_or_create(
        capture=capture,
        defaults={"next_attempt_at": timezone.now()},
    )
    if created and publish_hint:
        media_changed_on_commit(capture.room.appointment_id)
    if artifact.status != MediaArtifactStatus.DISPOSED:
        transaction.on_commit(lambda: enqueue_artifact(artifact.pk))
    return artifact


def enqueue_artifact(artifact_id):
    from .tasks import ingest_media_artifact

    try:
        ingest_media_artifact.delay(str(artifact_id))
    except Exception:
        # The row is the outbox. Beat finds it even when Redis dispatch failed.
        log_artifact_diagnostic(stage=ArtifactStage.DISPATCH)
    else:
        # Dispatch acceptance is not proof that a worker started or a provider operation ran.
        log_artifact_diagnostic(stage=ArtifactStage.DISPATCH, outcome_code="DISPATCHED")


def custody_audit(action, artifact):
    record_event(
        context=AuditContext.system(),
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="ecounseling.mediaartifact",
        target_id=artifact.pk,
        metadata={"media_kind": artifact.capture.kind, "state": artifact.status},
    )


# Daily reports its own transcript storage in outParams too (live staging, 2026-10-17, with no
# custom transcription_bucket on the domain). Only this exact Daily-owned bucket is accepted.
DAILY_TRANSCRIPT_BUCKETS = frozenset({"daily-co-transcription"})


def daily_owned_transcript_storage(out_params):
    """Absent outParams or Daily's own bucket; any other location is customer-managed storage."""
    if not out_params:
        return True
    if not isinstance(out_params, dict):
        return False
    bucket = out_params.get("bucket")
    return (
        isinstance(bucket, str)
        and bucket in DAILY_TRANSCRIPT_BUCKETS
        and out_params.get("storage_provider") in (None, "aws")
    )


def provider_metadata(source, client, *, allow_deleted=False):
    """Exact artifact/room/session identity; reject customer-managed transcript storage."""
    if (
        not source.provider_binding_verified_at
        or source.provider_binding_quarantined_at
        or ECounselingMediaCapture.objects.filter(
            pk=source.pk, provider_binding_quarantined_at__isnull=False
        ).exists()
    ):
        raise ArtifactVerificationError("Provider media binding requires protected review.")
    artifact_id = source.provider_artifact_id
    if source.kind == "RECORDING":
        item = client.get_recording(artifact_id=artifact_id)
        valid = (
            item.get("id") == artifact_id
            and item.get("status") == "finished"
            and item.get("room_name") == source.room.daily_room_name
            and item.get("storage_provider") in (None, "aws")
        )
    else:
        item = client.get_transcript(artifact_id=artifact_id)
        terminal = {"t_finished", "t_deleted"} if allow_deleted else {"t_finished"}
        valid = (
            item.get("transcriptId") == artifact_id
            and item.get("status") in terminal
            and source.room.daily_room_id
            and item.get("roomId") == source.room.daily_room_id
            and daily_owned_transcript_storage(item.get("outParams"))
            and (item.get("status") == "t_deleted" or item.get("isVttAvailable") is True)
        )
    if source.provider_session_id:
        valid = valid and item.get("mtgSessionId") == source.provider_session_id
    if (
        not valid
        or ECounselingMediaCapture.objects.filter(
            pk=source.pk, provider_binding_quarantined_at__isnull=False
        ).exists()
    ):
        raise ArtifactVerificationError("Provider media identity could not be verified.")
    return item


def delete_v2_provider(source, client):
    item = provider_metadata(source, client, allow_deleted=True)
    artifact_id = source.provider_artifact_id
    if source.kind == "RECORDING":
        result = client.delete_recording(artifact_id=artifact_id)
        if (
            result.get("deleted") is not True
            or result.get("id") != artifact_id
            or result.get("storage_provider")
        ):
            raise ArtifactVerificationError("Provider deletion could not be verified.")
    elif item.get("status") != "t_deleted":
        result = client.delete_transcript(artifact_id=artifact_id)
        if (
            result.get("transcriptId") != artifact_id
            or result.get("status") != "t_deleted"
            or not daily_owned_transcript_storage(result.get("outParams"))
        ):
            raise ArtifactVerificationError("Provider deletion could not be verified.")


def _retry(artifact_id, token, code):
    with transaction.atomic():
        artifact = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact_id)
        if artifact.claim_token != token or artifact.status == MediaArtifactStatus.DISPOSED:
            return
        previous_status = artifact.status
        if artifact.status != MediaArtifactStatus.STORED:
            artifact.status = MediaArtifactStatus.FAILED
        artifact.claim_token, artifact.claimed_at = None, None
        artifact.error_code = code
        delay = min(3600, 60 * 2 ** min(artifact.attempts, 6))
        artifact.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        artifact.save()
        if previous_status != artifact.status:
            media_changed_on_commit(artifact.capture.room.appointment_id)
        return {
            "attempt_number": artifact.attempts,
            "retry_scheduled": True,
            "next_attempt_in_seconds": delay,
            "custody_committed": artifact.status == MediaArtifactStatus.STORED,
        }


def ingest_artifact(artifact_id, *, storage=None, client=None, download=None):
    """At-least-once delivery converges on one precommitted UUID key; no network under atomic()."""
    started = time.monotonic()
    with artifact_guard(artifact_id) as acquired:
        if not acquired:
            log_artifact_diagnostic(stage=ArtifactStage.CLAIM, outcome_code="LOCK_BUSY")
            return
        token = uuid.uuid4()
        with transaction.atomic():
            initial = ECounselingMediaArtifact.objects.select_related("capture__room").get(
                pk=artifact_id
            )
            source = ECounselingMediaCapture.objects.select_for_update().get(pk=initial.capture_id)
            source.room = initial.capture.room
            artifact = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact_id)
            if not artifact_eligible(source) or artifact.status == MediaArtifactStatus.DISPOSED:
                log_artifact_diagnostic(stage=ArtifactStage.CLAIM, outcome_code="INELIGIBLE")
                return
            if artifact.next_attempt_at and artifact.next_attempt_at > timezone.now():
                log_artifact_diagnostic(
                    stage=ArtifactStage.CLAIM,
                    outcome_code="RETRY_NOT_DUE",
                    attempt_number=artifact.attempts,
                    retry_scheduled=True,
                    next_attempt_in_seconds=max(
                        0, int((artifact.next_attempt_at - timezone.now()).total_seconds())
                    ),
                    custody_committed=artifact.status == MediaArtifactStatus.STORED,
                )
                return
            if artifact.status == MediaArtifactStatus.STORED and not source.provider_artifact_id:
                log_artifact_diagnostic(
                    stage=ArtifactStage.CLAIM,
                    outcome_code="ALREADY_CLEANED",
                    custody_committed=True,
                )
                return
            # A PROCESSING row whose old session lock vanished is safely reclaimable. Its stable
            # key and precommitted digest allow adoption after upload/DB acknowledgement loss.
            stale_claim = (
                artifact.status == MediaArtifactStatus.PROCESSING
                and artifact.claimed_at
                and artifact.claimed_at < timezone.now() - timedelta(minutes=30)
            )
            artifact.claim_token, artifact.claimed_at = token, timezone.now()
            artifact.attempts += 1
            previous_status = artifact.status
            if artifact.status != MediaArtifactStatus.STORED:
                artifact.status = MediaArtifactStatus.PROCESSING
                artifact.object_key = (
                    artifact.object_key or f"{source.room_id}/{source.pk}/{artifact.pk}"
                )
            artifact.save()
            if previous_status != artifact.status:
                media_changed_on_commit(source.room.appointment_id)
            provider_id = source.provider_artifact_id

        log_artifact_diagnostic(
            stage=ArtifactStage.CLAIM,
            outcome_code="STALE_CLAIM_RECLAIMED" if stale_claim else "PROCESSING",
            attempt_number=artifact.attempts,
            retry_scheduled=False,
            custody_committed=artifact.status == MediaArtifactStatus.STORED,
        )
        stage = ArtifactStage.STORAGE_POLICY
        try:
            storage = storage or ObjectStorage(alias="ecounseling_media")
            storage.validate_sensitive_policy()
            stage = ArtifactStage.BINDING
            binding = storage.binding_identity()
            if artifact.storage_binding and artifact.storage_binding != binding:
                raise ArtifactVerificationError("Media storage namespace changed.")
            if artifact.storage_binding is None:
                with transaction.atomic():
                    current = ECounselingMediaArtifact.objects.select_for_update().get(
                        pk=artifact_id
                    )
                    if current.claim_token != token:
                        return
                    current.storage_binding = binding
                    current.save(update_fields=["storage_binding", "updated_at"])
                    artifact = current
            if artifact.status != MediaArtifactStatus.STORED:
                stage = ArtifactStage.INTEGRITY
                if artifact.size and artifact.sha256 and storage.exists(artifact.object_key):
                    if not storage.verify(
                        artifact.object_key, size=artifact.size, sha256=artifact.sha256
                    ):
                        raise ArtifactVerificationError("Stored media integrity is unverified.")
                else:
                    stage = ArtifactStage.PROVIDER_METADATA
                    client = client or DailyClient.from_settings()
                    provider_metadata(source, client)
                    stage = ArtifactStage.ACCESS_LINK
                    link_payload = (
                        client.recording_access_link(artifact_id=provider_id)
                        if source.kind == "RECORDING"
                        else client.transcript_access_link(artifact_id=provider_id)
                    )
                    stage = ArtifactStage.LINK_VALIDATION
                    url = validate_daily_link(
                        link_payload, kind=source.kind, artifact_id=provider_id
                    )
                    downloader = download or stream_daily_media
                    stage = ArtifactStage.TRANSFER
                    with downloader(url, kind=source.kind) as (spool, content_type, size, digest):
                        del url, link_payload
                        stage = ArtifactStage.PRECOMMIT
                        with transaction.atomic():
                            current = ECounselingMediaArtifact.objects.select_for_update().get(
                                pk=artifact_id
                            )
                            if (
                                current.claim_token != token
                                or current.status != MediaArtifactStatus.PROCESSING
                            ):
                                return
                            current.content_type, current.size, current.sha256 = (
                                content_type,
                                size,
                                digest,
                            )
                            current.save()
                        stage = ArtifactStage.UPLOAD
                        file = File(spool)
                        file.content_type = content_type
                        saved_key = storage.save(artifact.object_key, file)
                        if saved_key != artifact.object_key:
                            # This backend violates deterministic custody; minimize its stray copy.
                            storage.delete(saved_key)
                            raise ArtifactVerificationError("Storage identity is unverified.")
                        stage = ArtifactStage.INTEGRITY
                        if not storage.verify(saved_key, size=size, sha256=digest):
                            raise ArtifactVerificationError("Stored media integrity is unverified.")
                        # Finalizing the protected download/spool context is its own IO boundary.
                        stage = ArtifactStage.TRANSFER
                stage = ArtifactStage.CUSTODY_COMMIT
                with transaction.atomic():
                    capture = ECounselingMediaCapture.objects.select_for_update().get(pk=source.pk)
                    current = ECounselingMediaArtifact.objects.select_for_update().get(
                        pk=artifact_id
                    )
                    if (
                        current.claim_token != token
                        or capture.artifact_disposed_at
                        or capture.provider_binding_quarantined_at
                        or capture.provider_artifact_id != provider_id
                    ):
                        raise ArtifactVerificationError("Media custody changed during preparation.")
                    previous_status = current.status
                    current.status, current.stored_at = MediaArtifactStatus.STORED, timezone.now()
                    current.error_code = None
                    current.save()
                    custody_audit(actions.ECOUNSELING_MEDIA_ARTIFACT_STORED, current)
                    if previous_status != current.status:
                        media_changed_on_commit(source.room.appointment_id)
                    artifact = current
            # Canonical custody committed and reverified before provider cleanup, including retries.
            stage = ArtifactStage.INTEGRITY
            if not storage.verify(artifact.object_key, size=artifact.size, sha256=artifact.sha256):
                raise ArtifactVerificationError("Stored media integrity is unverified.")
            if provider_id:
                stage = ArtifactStage.PROVIDER_CLEANUP
                delete_v2_provider(source, client or DailyClient.from_settings())
            stage = ArtifactStage.CLEANUP_COMMIT
            with transaction.atomic():
                capture = ECounselingMediaCapture.objects.select_for_update().get(pk=source.pk)
                current = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact_id)
                if (
                    current.claim_token != token
                    or current.status != MediaArtifactStatus.STORED
                    or capture.provider_artifact_id != provider_id
                    or capture.provider_binding_quarantined_at
                ):
                    raise ArtifactVerificationError("Media custody changed during cleanup.")
                capture.provider_artifact_id = None
                capture.save(update_fields=["provider_artifact_id", "updated_at"])
                current.provider_deleted_at = timezone.now()
                current.claim_token, current.claimed_at = None, None
                current.next_attempt_at, current.error_code = None, None
                current.save()
                custody_audit(actions.ECOUNSELING_MEDIA_PROVIDER_CLEANED, current)
            log_artifact_diagnostic(
                stage=stage,
                outcome_code="PROVIDER_CLEANED",
                attempt_number=artifact.attempts,
                retry_scheduled=False,
                duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                custody_committed=True,
            )
        except Exception as error:
            # Never include upstream exceptions or signed locations in logs/Celery results.
            if stage == ArtifactStage.PROVIDER_METADATA and isinstance(
                error, ArtifactVerificationError
            ):
                stage = ArtifactStage.PROVIDER_IDENTITY
            elif (
                stage == ArtifactStage.TRANSFER
                and isinstance(error, MediaDownloadError)
                and error.failure == MediaDownloadFailure.VALIDATION
            ):
                stage = ArtifactStage.DOWNLOAD_VALIDATION
            try:
                retry = _retry(artifact_id, token, stage.value)
            except Exception:
                # A failed retry-state transaction cannot truthfully promise its schedule/custody.
                log_artifact_diagnostic(
                    stage=ArtifactStage.RETRY_COMMIT,
                    attempt_number=artifact.attempts,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                )
                raise ArtifactTaskError(ArtifactStage.RETRY_COMMIT) from None
            log_artifact_diagnostic(
                stage=stage,
                outcome_code=stage.value if retry else "SUPERSEDED",
                duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                provider_error=error,
                **(retry or {}),
            )


def access_artifact(*, counselor, appointment_id, kind, context):
    appointment = _load_session_appointment(appointment_id)
    _require_counselor_relationship(
        actor=counselor,
        appointment=appointment,
        capability="ecounseling.access_media_assigned",
    )
    artifact = (
        ECounselingMediaArtifact.objects.select_related("capture__room")
        .filter(capture__room__appointment=appointment, capture__kind=kind)
        .first()
    )
    if artifact and (artifact.disposed_at or artifact.capture.artifact_disposed_at):
        raise APIError(
            410,
            "ecounseling_artifact_disposed",
            "This file was deleted under an approved retention rule.",
        )
    if artifact is None or artifact.status != MediaArtifactStatus.STORED:
        raise APIError(
            409,
            "ecounseling_artifact_not_ready",
            "The file is still being prepared or was not saved.",
        )
    try:
        storage = ObjectStorage(alias="ecounseling_media")
        storage.validate_sensitive_policy()
        if artifact.storage_binding != storage.binding_identity():
            raise ArtifactVerificationError("Media storage namespace changed.")
        if not storage.exists(artifact.object_key):
            raise ValueError()
        extensions = {"video/mp4": "mp4", "video/webm": "webm", "text/vtt": "vtt"}
        date = institution_date(appointment.starts_at).isoformat()
        subject = "recording" if kind == "RECORDING" else "transcript"
        filename = f"e-counseling-{subject}-{date}.{extensions[artifact.content_type]}"
        ttl = settings.ECOUNSELING_MEDIA_ACCESS_URL_TTL_SECONDS
        url = storage.private_url(
            artifact.object_key,
            expires_seconds=ttl,
            filename=filename,
            content_type=artifact.content_type,
        )
    except Exception:
        raise APIError(
            503,
            "ecounseling_artifact_unavailable",
            "The file isn't available right now. Try again.",
        ) from None
    # A storage check can race disposition. Recheck before issuing bounded access authority.
    if ECounselingMediaArtifact.objects.filter(pk=artifact.pk, status="DISPOSED").exists():
        raise APIError(410, "ecounseling_artifact_disposed", "This file has been deleted.")
    record_event(
        context=context,
        action=actions.ECOUNSELING_MEDIA_ARTIFACT_ACCESS_AUTHORIZED,
        outcome=AuditOutcome.SUCCESS,
        target_type="ecounseling.mediaartifact",
        target_id=artifact.pk,
        metadata={
            "appointment_id": str(appointment.pk),
            "media_kind": kind,
            "access_mode": "DOWNLOAD",
        },
    )
    return {"url": url, "expires_at": timezone.now() + timedelta(seconds=ttl)}
