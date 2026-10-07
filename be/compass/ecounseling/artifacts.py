"""Durable V2 custody and assigned access. Locations and provider links stay internal."""

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
from compass.integrations.daily import DailyClient
from compass.integrations.media_download import stream_daily_media, validate_daily_link
from compass.integrations.storage import ObjectStorage

from .media import _load_session_appointment
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
        and capture.media_authorized_at is not None
        and (capture.kind == "RECORDING" or capture.transcript_storage_authorized)
    )


def ensure_pending_artifact(capture):
    if not artifact_eligible(capture):
        return None
    artifact, _ = ECounselingMediaArtifact.objects.get_or_create(
        capture=capture,
        defaults={"next_attempt_at": timezone.now()},
    )
    if artifact.status != MediaArtifactStatus.DISPOSED:
        transaction.on_commit(lambda: enqueue_artifact(artifact.pk))
    return artifact


def enqueue_artifact(artifact_id):
    from .tasks import ingest_media_artifact

    try:
        ingest_media_artifact.delay(str(artifact_id))
    except Exception:
        # The row is the outbox. Beat finds it even when Redis dispatch failed.
        pass


def custody_audit(action, artifact):
    record_event(
        context=AuditContext.system(),
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="ecounseling.mediaartifact",
        target_id=artifact.pk,
        metadata={"media_kind": artifact.capture.kind, "state": artifact.status},
    )


def provider_metadata(source, client, *, allow_deleted=False):
    """Exact artifact/room/session identity; reject customer-managed transcript storage."""
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
            and not item.get("outParams")
            and (item.get("status") == "t_deleted" or item.get("isVttAvailable") is True)
        )
    if source.provider_session_id:
        valid = valid and item.get("mtgSessionId") == source.provider_session_id
    if not valid:
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
            or result.get("outParams")
        ):
            raise ArtifactVerificationError("Provider deletion could not be verified.")


def _retry(artifact_id, token, code):
    with transaction.atomic():
        artifact = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact_id)
        if artifact.claim_token != token or artifact.status == MediaArtifactStatus.DISPOSED:
            return
        if artifact.status != MediaArtifactStatus.STORED:
            artifact.status = MediaArtifactStatus.FAILED
        artifact.claim_token, artifact.claimed_at = None, None
        artifact.error_code = code
        artifact.next_attempt_at = timezone.now() + timedelta(
            seconds=min(3600, 60 * 2 ** min(artifact.attempts, 6))
        )
        artifact.save()


def ingest_artifact(artifact_id, *, storage=None, client=None, download=None):
    """At-least-once delivery converges on one precommitted UUID key; no network under atomic()."""
    with artifact_guard(artifact_id) as acquired:
        if not acquired:
            return
        token = uuid.uuid4()
        with transaction.atomic():
            initial = ECounselingMediaArtifact.objects.select_related("capture__room").get(
                pk=artifact_id
            )
            source = ECounselingMediaCapture.objects.select_for_update().get(pk=initial.capture_id)
            source.room = initial.capture.room
            artifact = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact_id)
            from compass.privacy_governance.retention_models import DispositionCase

            if DispositionCase.objects.filter(source_id=source.pk, state="PROCESSING").exists():
                return
            if not artifact_eligible(source) or artifact.status == MediaArtifactStatus.DISPOSED:
                return
            if artifact.next_attempt_at and artifact.next_attempt_at > timezone.now():
                return
            if artifact.status == MediaArtifactStatus.STORED and not source.provider_artifact_id:
                return
            # A PROCESSING row whose old session lock vanished is safely reclaimable. Its stable
            # key and precommitted digest allow adoption after upload/DB acknowledgement loss.
            artifact.claim_token, artifact.claimed_at = token, timezone.now()
            artifact.attempts += 1
            if artifact.status != MediaArtifactStatus.STORED:
                artifact.status = MediaArtifactStatus.PROCESSING
                artifact.object_key = (
                    artifact.object_key or f"{source.room_id}/{source.pk}/{artifact.pk}"
                )
            artifact.save()
            provider_id = source.provider_artifact_id

        try:
            storage = storage or ObjectStorage(alias="ecounseling_media")
            storage.validate_sensitive_policy()
            if artifact.status != MediaArtifactStatus.STORED:
                if artifact.size and artifact.sha256 and storage.exists(artifact.object_key):
                    if not storage.verify(
                        artifact.object_key, size=artifact.size, sha256=artifact.sha256
                    ):
                        raise ArtifactVerificationError("Stored media integrity is unverified.")
                else:
                    client = client or DailyClient.from_settings()
                    provider_metadata(source, client)
                    link_payload = (
                        client.recording_access_link(artifact_id=provider_id)
                        if source.kind == "RECORDING"
                        else client.transcript_access_link(artifact_id=provider_id)
                    )
                    url = validate_daily_link(
                        link_payload, kind=source.kind, artifact_id=provider_id
                    )
                    downloader = download or stream_daily_media
                    with downloader(url, kind=source.kind) as (spool, content_type, size, digest):
                        del url, link_payload
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
                        file = File(spool)
                        file.content_type = content_type
                        saved_key = storage.save(artifact.object_key, file)
                        if saved_key != artifact.object_key:
                            # This backend violates deterministic custody; minimize its stray copy.
                            storage.delete(saved_key)
                            raise ArtifactVerificationError("Storage identity is unverified.")
                        if not storage.verify(saved_key, size=size, sha256=digest):
                            raise ArtifactVerificationError("Stored media integrity is unverified.")
                with transaction.atomic():
                    capture = ECounselingMediaCapture.objects.select_for_update().get(pk=source.pk)
                    current = ECounselingMediaArtifact.objects.select_for_update().get(
                        pk=artifact_id
                    )
                    if (
                        current.claim_token != token
                        or capture.artifact_disposed_at
                        or capture.provider_artifact_id != provider_id
                    ):
                        raise ArtifactVerificationError("Media custody changed during preparation.")
                    current.status, current.stored_at = MediaArtifactStatus.STORED, timezone.now()
                    current.error_code = None
                    current.save()
                    custody_audit(actions.ECOUNSELING_MEDIA_ARTIFACT_STORED, current)
                    artifact = current
            # Canonical custody committed and reverified before provider cleanup, including retries.
            if not storage.verify(artifact.object_key, size=artifact.size, sha256=artifact.sha256):
                raise ArtifactVerificationError("Stored media integrity is unverified.")
            if provider_id:
                delete_v2_provider(source, client or DailyClient.from_settings())
            with transaction.atomic():
                capture = ECounselingMediaCapture.objects.select_for_update().get(pk=source.pk)
                current = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact_id)
                if (
                    current.claim_token != token
                    or current.status != MediaArtifactStatus.STORED
                    or capture.provider_artifact_id != provider_id
                ):
                    raise ArtifactVerificationError("Media custody changed during cleanup.")
                capture.provider_artifact_id = None
                capture.save(update_fields=["provider_artifact_id", "updated_at"])
                current.provider_deleted_at = timezone.now()
                current.claim_token, current.claimed_at = None, None
                current.next_attempt_at, current.error_code = None, None
                current.save()
                custody_audit(actions.ECOUNSELING_MEDIA_PROVIDER_CLEANED, current)
        except Exception:
            # Never include upstream exceptions or signed locations in logs/Celery results.
            _retry(artifact_id, token, "CUSTODY_OR_CLEANUP_UNVERIFIED")


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
        if not storage.exists(artifact.object_key):
            raise ValueError()
        extensions = {"video/mp4": "mp4", "video/webm": "webm", "text/vtt": "vtt"}
        date = timezone.localtime(appointment.starts_at).date().isoformat()
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
