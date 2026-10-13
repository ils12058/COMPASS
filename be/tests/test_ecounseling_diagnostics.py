"""Fault injection against real local PostgreSQL and fake-only provider/storage IO."""

import json
import logging
import pickle
import uuid
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import psycopg
import pytest
from django.db import DatabaseError, connection
from django.utils import timezone

from compass.audit import actions
from compass.common.json_logging import JsonFormatter
from compass.ecounseling.artifacts import enqueue_artifact, ingest_artifact
from compass.ecounseling.diagnostics import (
    ArtifactStage,
    ArtifactTaskError,
    log_artifact_diagnostic,
)
from compass.ecounseling.models import ECounselingMediaArtifact
from compass.ecounseling.tasks import ingest_media_artifact, recover_media_artifacts
from compass.integrations.daily import DailyHTTPError
from compass.integrations.media_download import stream_daily_media
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_media_v2 import ArtifactDaily, fake_download, ready_artifact
from tests.test_privacy_governance import auth_client

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def synthetic_dispatch(monkeypatch, caplog):
    monkeypatch.setattr(ingest_media_artifact, "delay", lambda *_args: None)
    caplog.set_level(logging.INFO, logger="compass.ecounseling.diagnostics")


def diagnostics(caplog):
    return [
        json.loads(JsonFormatter().format(record))
        for record in caplog.records
        if record.name == "compass.ecounseling.diagnostics"
    ]


def private_failure(*_args, **_kwargs):
    raise RuntimeError(PRIVATE_TEXT)


class DownloadResponse:
    status = 200

    def __init__(self, body, mime, *, length=None):
        self.body = BytesIO(body)
        self.headers = {
            "Content-Type": mime,
            "Content-Length": str(len(body) if length is None else length),
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.body.read(size)


def install_stream(monkeypatch, *, kind="RECORDING", failure=None, webm=False):
    body = (
        b"WEBVTT\n\n00:00.000 --> 00:01.000\nsynthetic\n"
        if kind == "TRANSCRIPTION"
        else b"\x00\x00\x00\x18ftypisomsynthetic"
    )
    mime = "text/vtt" if kind == "TRANSCRIPTION" else "video/mp4"
    if webm:
        body, mime = b"\x1a\x45\xdf\xa3synthetic", "video/webm"
    if failure == "content_type":
        mime = "text/html"
    if failure == "signature":
        body = b"wrong synthetic signature"

    class Opener:
        def open(self, *_args, **_kwargs):
            if failure == "timeout":
                raise TimeoutError(PRIVATE_TEXT)
            return DownloadResponse(body, mime, length=len(body) + 1 if failure == "size" else None)

    monkeypatch.setattr("compass.integrations.media_download.build_opener", lambda *_: Opener())
    return stream_daily_media


@pytest.mark.parametrize(
    ("failure", "code", "stored"),
    [
        ("policy", "STORAGE_POLICY_UNVERIFIED", False),
        ("binding", "STORAGE_BINDING_UNVERIFIED", False),
        ("metadata", "PROVIDER_METADATA_FAILED", False),
        ("identity", "PROVIDER_IDENTITY_UNVERIFIED", False),
        ("link_request", "ACCESS_LINK_FAILED", False),
        ("link_host", "ACCESS_LINK_UNVERIFIED", False),
        ("timeout", "MEDIA_TRANSFER_FAILED", False),
        ("content_type", "DOWNLOAD_UNVERIFIED", False),
        ("signature", "DOWNLOAD_UNVERIFIED", False),
        ("size", "DOWNLOAD_UNVERIFIED", False),
        ("precommit", "PRE_CUSTODY_COMMIT_UNVERIFIED", False),
        ("upload", "CANONICAL_UPLOAD_UNVERIFIED", False),
        ("integrity", "CANONICAL_INTEGRITY_UNVERIFIED", False),
        ("custody_commit", "CUSTODY_COMMIT_UNVERIFIED", False),
        ("cleanup", "PROVIDER_CLEANUP_UNVERIFIED", True),
        ("cleanup_commit", "CLEANUP_COMMIT_UNVERIFIED", True),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_each_failure_boundary_preserves_custody_retry_and_privacy(
    failure, code, stored, monkeypatch, caplog
):
    _, counselor, appointment, capture, artifact, storage = ready_artifact()
    client = ArtifactDaily(capture)
    downloader = fake_download
    if failure == "policy":
        monkeypatch.setattr(storage, "validate_sensitive_policy", private_failure)
    elif failure == "binding":
        artifact.storage_binding = "a" * 64
        artifact.save()
    elif failure == "metadata":

        def fail_metadata(**_kwargs):
            raise DailyHTTPError(429)

        monkeypatch.setattr(client, "get_recording", fail_metadata)
    elif failure == "identity":
        monkeypatch.setattr(
            client,
            "get_recording",
            lambda **_kwargs: {"id": "different", "room_name": PRIVATE_TEXT},
        )
    elif failure == "link_request":
        monkeypatch.setattr(client, "recording_access_link", private_failure)
    elif failure == "link_host":
        monkeypatch.setattr(
            client,
            "recording_access_link",
            lambda **_kwargs: {
                "download_link": "https://untrusted.invalid/private",
                "expires": 2_000_000_000,
            },
        )
    elif failure in {"timeout", "content_type", "signature", "size"}:
        downloader = install_stream(monkeypatch, failure=failure)
    elif failure == "precommit":
        original = ECounselingMediaArtifact.save

        def fail_precommit(self, *args, **kwargs):
            if self.status == "PROCESSING" and self.size:
                raise DatabaseError(PRIVATE_TEXT)
            return original(self, *args, **kwargs)

        monkeypatch.setattr(ECounselingMediaArtifact, "save", fail_precommit)
    elif failure == "upload":
        monkeypatch.setattr(storage, "save", private_failure)
    elif failure == "integrity":
        storage.fail_verify = True
    elif failure in {"custody_commit", "cleanup_commit"}:
        original_audit = __import__(
            "compass.ecounseling.artifacts", fromlist=["custody_audit"]
        ).custody_audit
        target = (
            actions.ECOUNSELING_MEDIA_ARTIFACT_STORED
            if failure == "custody_commit"
            else actions.ECOUNSELING_MEDIA_PROVIDER_CLEANED
        )

        def fail_commit(action, current):
            if action == target:
                raise DatabaseError(PRIVATE_TEXT)
            return original_audit(action, current)

        monkeypatch.setattr("compass.ecounseling.artifacts.custody_audit", fail_commit)
    elif failure == "cleanup":
        monkeypatch.setattr(client, "delete_recording", private_failure)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=downloader)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.error_code == code
    assert artifact.status == ("STORED" if stored else "FAILED")
    assert artifact.attempts == 1 and artifact.next_attempt_at > timezone.now()
    assert artifact.claim_token is None and artifact.claimed_at is None
    assert capture.provider_artifact_id and artifact.provider_deleted_at is None
    if stored:
        assert artifact.stored_at and artifact.size > 0 and len(artifact.sha256) == 64
        assert storage.verify(artifact.object_key, size=artifact.size, sha256=artifact.sha256)
    else:
        assert artifact.stored_at is None
        assert "DELETE" not in client.calls
    event = diagnostics(caplog)[-1]
    assert event["outcome_code"] == code and event["custody_committed"] is stored
    assert event["retry_scheduled"] is True and event["next_attempt_in_seconds"] == 120
    assert event["attempt_number"] == 1 and event["duration_ms"] >= 0
    if failure == "metadata":
        assert event["provider_failure_code"] == "RATE_LIMITED"
    assert_private_absent(json.dumps(diagnostics(caplog)))
    assert_private_absent(
        json.dumps(diagnostics(caplog)),
        (capture.provider_artifact_id, capture.room.daily_room_name, artifact.object_key),
    )
    with patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage):
        response = auth_client(counselor).get(
            f"/api/v1/e-counseling/appointments/{appointment.pk}/media/RECORDING/access"
        )
    assert response.status_code == (200 if stored else 409)
    if not stored:
        assert_private_absent(response.content.decode())
        assert code not in response.content.decode()


@pytest.mark.parametrize(
    ("kind", "webm"),
    [("RECORDING", False), ("RECORDING", True), ("TRANSCRIPTION", False)],
    ids=["mp4", "webm", "webvtt"],
)
def test_real_bounded_stream_validation_and_successful_cleanup_still_work(
    kind, webm, monkeypatch, caplog
):
    _, _, _, capture, artifact, storage = ready_artifact(kind)
    ingest_artifact(
        artifact.pk,
        storage=storage,
        client=ArtifactDaily(capture),
        download=install_stream(monkeypatch, kind=kind, webm=webm),
    )
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "STORED" and artifact.provider_deleted_at
    assert capture.provider_artifact_id is None
    assert artifact.error_code is None and artifact.next_attempt_at is None
    assert diagnostics(caplog)[-1]["retry_scheduled"] is False


@pytest.mark.parametrize("prior_attempts", [0, 1, 5, 6, 8])
def test_retry_backoff_is_unchanged_and_history_is_retained_while_processing(
    prior_attempts, monkeypatch, caplog
):
    _, _, _, capture, artifact, storage = ready_artifact()
    artifact.attempts = prior_attempts
    artifact.error_code = "CUSTODY_OR_CLEANUP_UNVERIFIED"
    artifact.save()
    now = timezone.now()
    monkeypatch.setattr("compass.ecounseling.artifacts.timezone.now", lambda: now)

    def fail_policy():
        current = ECounselingMediaArtifact.objects.get(pk=artifact.pk)
        assert current.status == "PROCESSING"
        assert current.error_code == "CUSTODY_OR_CLEANUP_UNVERIFIED"
        raise RuntimeError(PRIVATE_TEXT)

    monkeypatch.setattr(storage, "validate_sensitive_policy", fail_policy)
    ingest_artifact(
        artifact.pk, storage=storage, client=ArtifactDaily(capture), download=fake_download
    )
    artifact.refresh_from_db()
    delay = min(3600, 60 * 2 ** min(prior_attempts + 1, 6))
    assert artifact.next_attempt_at == now + timedelta(seconds=delay)
    assert diagnostics(caplog)[-1]["next_attempt_in_seconds"] == delay


def test_scheduled_wait_and_stale_claim_are_distinct_and_do_not_add_attempts(caplog):
    _, _, _, capture, artifact, storage = ready_artifact()
    artifact.next_attempt_at = timezone.now() + timedelta(minutes=10)
    artifact.save()
    client = ArtifactDaily(capture)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    assert artifact.attempts == 0 and client.calls == []
    assert diagnostics(caplog)[-1]["outcome_code"] == "RETRY_NOT_DUE"
    artifact.status, artifact.claim_token = "PROCESSING", uuid.uuid4()
    artifact.claimed_at = timezone.now() - timedelta(minutes=31)
    artifact.next_attempt_at = timezone.now()
    artifact.save()
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    assert any(event["outcome_code"] == "STALE_CLAIM_RECLAIMED" for event in diagnostics(caplog))


def test_real_postgres_advisory_lock_blocks_duplicate_worker_without_side_effects(caplog):
    _, _, _, capture, artifact, storage = ready_artifact()
    config = connection.settings_dict
    with psycopg.connect(
        dbname=config["NAME"],
        user=config["USER"],
        password=config["PASSWORD"],
        host=config["HOST"],
        port=config["PORT"],
        autocommit=True,
    ) as other:
        other.execute("SELECT pg_advisory_lock(%s)", [artifact.pk.int % (2**63)])
        client = ArtifactDaily(capture)
        ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    assert artifact.attempts == 0 and client.calls == [] and storage.calls == []
    assert diagnostics(caplog)[-1]["outcome_code"] == "LOCK_BUSY"


def test_missing_capture_authorization_blocks_ingestion_and_duplicate_success_is_idempotent(caplog):
    _, _, _, capture, artifact, storage = ready_artifact()
    authorized_at = capture.media_authorized_at
    capture.media_authorized_at = None
    capture.save()
    client = ArtifactDaily(capture)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    assert client.calls == [] and storage.calls == []
    assert diagnostics(caplog)[-1]["outcome_code"] == "INELIGIBLE"
    capture.media_authorized_at = authorized_at
    capture.save()
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    calls = list(client.calls)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    assert artifact.status == "STORED" and artifact.attempts == 1
    assert client.calls == calls and len(storage.objects) == 1
    assert diagnostics(caplog)[-1]["outcome_code"] == "ALREADY_CLEANED"


@pytest.mark.django_db(transaction=True)
def test_custody_commit_acknowledgment_loss_preserves_actual_stored_row_and_safe_adoption(
    monkeypatch, caplog
):
    _, _, _, capture, artifact, storage = ready_artifact()
    client = ArtifactDaily(capture)
    original_commit = connection.commit
    injected = False

    def lost_ack():
        nonlocal injected
        stored = ECounselingMediaArtifact.objects.filter(pk=artifact.pk, status="STORED").exists()
        original_commit()
        if stored and not injected:
            injected = True
            raise DatabaseError(PRIVATE_TEXT)

    monkeypatch.setattr(connection, "commit", lost_ack)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    assert artifact.status == "STORED" and artifact.error_code == "CUSTODY_COMMIT_UNVERIFIED"
    assert artifact.provider_deleted_at is None and "DELETE" not in client.calls
    assert diagnostics(caplog)[-1]["custody_committed"] is True
    artifact.next_attempt_at = timezone.now()
    artifact.save()
    ingest_artifact(
        artifact.pk,
        storage=storage,
        client=client,
        download=lambda *_args, **_kwargs: pytest.fail("Must adopt verified custody"),
    )
    artifact.refresh_from_db()
    assert artifact.provider_deleted_at and artifact.error_code is None
    assert client.calls.count("LINK") == 1 and len(storage.objects) == 1


def test_dispatch_failure_is_sanitized_and_preserves_durable_outbox(monkeypatch, caplog):
    _, _, _, _, artifact, _ = ready_artifact()
    monkeypatch.setattr(ingest_media_artifact, "delay", private_failure)
    enqueue_artifact(artifact.pk)
    artifact.refresh_from_db()
    assert artifact.status == "PENDING" and artifact.attempts == 0 and artifact.next_attempt_at
    assert diagnostics(caplog)[-1]["outcome_code"] == "TASK_DISPATCH_FAILED"
    assert_private_absent(json.dumps(diagnostics(caplog)))


def test_unexpected_task_and_recovery_failures_have_safe_celery_results(monkeypatch, caplog):
    monkeypatch.setattr("compass.ecounseling.tasks.ingest_artifact", private_failure)
    result = ingest_media_artifact.apply(args=[str(uuid.uuid4())], throw=False)
    assert result.failed() and isinstance(result.result, ArtifactTaskError)
    assert "INTERNAL_UNVERIFIED" in str(result.result)
    assert_private_absent(
        str(result.result)
        + result.traceback
        + "".join(JsonFormatter().format(record) for record in caplog.records)
    )
    monkeypatch.setattr(ECounselingMediaArtifact.objects, "filter", private_failure)
    result = recover_media_artifacts.apply(throw=False)
    assert result.failed() and "RECOVERY_UNVERIFIED" in str(result.result)
    assert_private_absent(
        str(result.result)
        + result.traceback
        + "".join(JsonFormatter().format(record) for record in caplog.records)
    )


def test_retry_persistence_failure_does_not_claim_a_committed_schedule(monkeypatch, caplog):
    _, _, _, capture, artifact, storage = ready_artifact()
    monkeypatch.setattr(storage, "save", private_failure)
    monkeypatch.setattr("compass.ecounseling.artifacts._retry", private_failure)
    with pytest.raises(ArtifactTaskError, match="RETRY_COMMIT_UNVERIFIED"):
        ingest_artifact(
            artifact.pk, storage=storage, client=ArtifactDaily(capture), download=fake_download
        )
    event = diagnostics(caplog)[-1]
    assert event["outcome_code"] == "RETRY_COMMIT_UNVERIFIED"
    assert "retry_scheduled" not in event and "custody_committed" not in event
    assert_private_absent(json.dumps(diagnostics(caplog)))


def test_diagnostic_logger_rejects_free_text_and_non_numeric_context(caplog):
    log_artifact_diagnostic(
        stage=PRIVATE_TEXT,
        outcome_code=PRIVATE_TEXT,
        task_name=PRIVATE_TEXT,
        attempt_number=PRIVATE_TEXT,
        duration_ms=PRIVATE_TEXT,
        retry_scheduled=PRIVATE_TEXT,
        custody_committed=PRIVATE_TEXT,
    )
    event = diagnostics(caplog)[-1]
    assert event["pipeline_stage"] == "UNKNOWN" and event["outcome_code"] == "INTERNAL_UNVERIFIED"
    assert "attempt_number" not in event and "retry_scheduled" not in event
    assert_private_absent(json.dumps(event))


def test_task_error_constructor_and_celery_reconstruction_only_preserve_closed_codes():
    for stage in (ArtifactStage.RETRY_COMMIT, ArtifactStage.RECOVERY, ArtifactStage.UNKNOWN):
        error = ArtifactTaskError(stage)
        assert str(type(error)(*error.args)) == str(error)
        assert str(pickle.loads(pickle.dumps(error))) == str(error)
    error = ArtifactTaskError(PRIVATE_TEXT)
    assert error.diagnostic_stage == ArtifactStage.UNKNOWN
    assert_private_absent(str(error) + repr(error.args))


def test_recovery_iteration_failure_has_safe_celery_failure_output(monkeypatch, caplog):
    ready_artifact()
    monkeypatch.setattr("compass.ecounseling.tasks.enqueue_artifact", private_failure)
    result = recover_media_artifacts.apply(throw=False)
    assert result.failed() and "RECOVERY_UNVERIFIED" in str(result.result)
    assert_private_absent(
        str(result.result)
        + result.traceback
        + "".join(JsonFormatter().format(record) for record in caplog.records)
    )


def test_provider_cleanup_404_is_not_deletion_evidence(monkeypatch, caplog):
    _, _, _, capture, artifact, storage = ready_artifact()
    client = ArtifactDaily(capture)
    original = client.get_recording

    def metadata(**kwargs):
        if ECounselingMediaArtifact.objects.get(pk=artifact.pk).status == "STORED":
            raise DailyHTTPError(404)
        return original(**kwargs)

    monkeypatch.setattr(client, "get_recording", metadata)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "STORED" and artifact.provider_deleted_at is None
    assert artifact.error_code == "PROVIDER_CLEANUP_UNVERIFIED"
    assert capture.provider_artifact_id and "DELETE" not in client.calls
    assert diagnostics(caplog)[-1]["provider_failure_code"] == "UNCLASSIFIED"


@pytest.mark.parametrize("invalid_field", ["transcriptId", "roomId", "isVttAvailable", "outParams"])
def test_transcript_provenance_and_storage_validation_remain_fail_closed(
    invalid_field, monkeypatch
):
    _, _, _, capture, artifact, storage = ready_artifact("TRANSCRIPTION")
    client = ArtifactDaily(capture)
    original = client.get_transcript

    def metadata(**kwargs):
        item = original(**kwargs)
        item[invalid_field] = False if invalid_field == "isVttAvailable" else PRIVATE_TEXT
        return item

    monkeypatch.setattr(client, "get_transcript", metadata)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.error_code == "PROVIDER_IDENTITY_UNVERIFIED"
    assert artifact.stored_at is None and "DELETE" not in client.calls
