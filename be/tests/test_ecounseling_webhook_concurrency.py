"""Separate PostgreSQL sessions and event barriers; provider I/O never holds SQL locks."""

import base64
import hashlib
import hmac
import json
import time
from copy import deepcopy
from threading import Barrier, Event
from unittest.mock import patch

import pytest
from django.db import OperationalError, connection, transaction
from django.test import override_settings
from django.utils import timezone

from compass.ecounseling.artifacts import ingest_artifact
from compass.ecounseling.media import withdraw_my_consent
from compass.ecounseling.models import DailyWebhookReceipt as Receipt
from compass.ecounseling.models import (
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
)
from compass.ecounseling.services import ECounselingProviderUnavailable, process_daily_webhook
from compass.ecounseling.webhooks import replay_receipt
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_media import FakeMediaDailyClient, context
from tests.test_ecounseling_media_v2 import ArtifactDaily, FakeStorage, fake_download
from tests.test_ecounseling_reconciliation import MetadataOnlyDaily, metadata
from tests.test_ecounseling_reconciliation import fake_only_boundaries as fake_only_boundaries
from tests.test_ecounseling_state_correctness import run_thread
from tests.test_ecounseling_webhook_security import SECRET, body_for, fenced_artifact, reservation

pytestmark = pytest.mark.django_db(transaction=True)


class ScopedArtifactDaily(ArtifactDaily):
    def get_recording(self, **kwargs):
        return {**super().get_recording(**kwargs), "mtgSessionId": self.capture.provider_session_id}

    def get_transcript(self, **kwargs):
        return {
            **super().get_transcript(**kwargs),
            "mtgSessionId": self.capture.provider_session_id,
        }


@pytest.fixture(autouse=True)
def isolated_signature_settings():
    with override_settings(DAILY_WEBHOOK_HMAC=base64.b64encode(SECRET).decode()):
        yield


def emit(event):
    raw = json.dumps(event, separators=(",", ":")).encode()
    now = time.time()
    timestamp = str(now)
    signature = base64.b64encode(
        hmac.new(SECRET, timestamp.encode() + b"." + raw, hashlib.sha256).digest()
    ).decode()
    return process_daily_webhook(
        raw_body=raw, signature=signature, timestamp=timestamp, now_epoch=now
    )


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("conflict", [False, True])
def test_concurrent_identical_or_conflicting_event_ids_have_one_original_binding(kind, conflict):
    _, capture = reservation(kind)
    first = body_for(capture, artifact_id="original-artifact")
    second = deepcopy(first)
    if conflict:
        second["payload"]["recording_id" if kind == "RECORDING" else "id"] = "second-artifact"
    start = Barrier(3)
    errors = []
    results = []

    def deliver(event):
        start.wait(20)
        results.append(emit(event))

    threads = [
        run_thread(lambda: deliver(first), errors),
        run_thread(lambda: deliver(second), errors),
    ]
    start.wait(20)
    for thread in threads:
        thread.join(20)
        assert not thread.is_alive()
    assert not errors and len(results) == 2 and sum(r.duplicate for r in results) == 1
    row = Receipt.objects.get(provider_event_id=first["id"])
    capture.refresh_from_db()
    assert row.provider_artifact_id == capture.provider_artifact_id
    assert bool(capture.provider_binding_quarantined_at) == conflict
    assert (
        row.event_id_conflict == conflict
        and Receipt.objects.filter(provider_event_id=first["id"]).count() == 1
    )


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    "race", ["withdrawal", "capture_disposition", "artifact_disposition", "cleanup", "stored"]
)
def test_domain_change_committed_during_webhook_validation_wins_safe_apply(kind, race, monkeypatch):
    people, capture = reservation(kind, bound=True, storage=kind == "TRANSCRIPTION")
    event = body_for(capture, "ready-to-download")
    from compass.ecounseling import webhooks

    original = webhooks._apply
    entered, release = Event(), Event()
    errors = []

    def paused(receipt, validated):
        entered.set()
        assert release.wait(20)
        return original(receipt, validated)

    monkeypatch.setattr(webhooks, "_apply", paused)
    thread = run_thread(lambda: emit(event), errors)
    assert entered.wait(20)
    try:
        if race == "withdrawal":
            consent = ECounselingConsent.objects.get(
                room=capture.room, scope="SESSION_MEDIA_CAPTURE"
            )
            withdraw_my_consent(
                student=people[0],
                appointment_id=people[2].pk,
                consent_id=consent.pk,
                context=context(people[0]),
                daily_client=people[3],
            )
        elif race == "capture_disposition":
            with transaction.atomic():
                ECounselingMediaCapture.objects.filter(pk=capture.pk).update(
                    artifact_disposed_at=timezone.now(), provider_artifact_id=None
                )
        else:
            fenced_artifact(
                capture,
                {"artifact_disposition": "artifact", "stored": "stored", "cleanup": "cleanup"}[
                    race
                ],
            )
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    capture.refresh_from_db()
    row = Receipt.objects.get(provider_event_id=event["id"])
    if race == "withdrawal":
        consent.refresh_from_db()
        assert consent.withdrawn_at and not consent.is_effectively_approved
        assert capture.status == "READY" and capture.stop_requested_at
        assert not capture.transcript_storage_enabled
    else:
        assert (
            row.processing_outcome == "DISPOSITION_BLOCKED" and capture.status == "START_REQUESTED"
        )


@pytest.mark.parametrize("cleanup", [False, True])
def test_binding_quarantine_during_ingester_metadata_prevents_transfer_or_provider_delete(cleanup):
    _, capture = reservation("RECORDING", bound=True)
    completed = body_for(capture, "ready-to-download")
    emit(completed)
    capture.refresh_from_db()
    artifact = ECounselingMediaArtifact.objects.get(capture=capture)
    storage = FakeStorage()
    if cleanup:
        ingest_artifact(
            artifact.pk,
            storage=storage,
            client=ScopedArtifactDaily(capture, fail_delete=True),
            download=fake_download,
        )
        artifact.refresh_from_db()
        assert artifact.status == "STORED"
        artifact.next_attempt_at = None
        artifact.save(update_fields=["next_attempt_at"])
    client = ScopedArtifactDaily(capture)
    original = client.get_recording
    entered, release = Event(), Event()
    errors = []

    def blocked(**kwargs):
        assert not connection.in_atomic_block
        entered.set()
        assert release.wait(20)
        return original(**kwargs)

    client.get_recording = blocked
    thread = run_thread(
        lambda: ingest_artifact(
            artifact.pk, storage=storage, client=client, download=fake_download
        ),
        errors,
    )
    assert entered.wait(20)
    try:
        conflicting = deepcopy(completed)
        conflicting["payload"]["recording_id"] = "foreign-artifact"
        emit(conflicting)
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    capture.refresh_from_db()
    artifact.refresh_from_db()
    assert capture.provider_binding_quarantined_at and capture.provider_artifact_id
    assert (
        "DELETE" not in client.calls
        and "LINK" not in client.calls
        and artifact.provider_deleted_at is None
    )
    assert artifact.status == ("STORED" if cleanup else "FAILED")


def test_real_policy_stop_runs_after_receipt_and_stop_intent_commit_once():
    _, capture = reservation("TRANSCRIPTION")
    ECounselingConsent.objects.filter(room=capture.room).update(withdrawn_at=timezone.now())
    client = FakeMediaDailyClient()
    original = client.stop_transcription

    def checked(**kwargs):
        assert not connection.in_atomic_block
        assert Receipt.objects.filter(capture=capture, mitigation_state="ATTEMPT_RESERVED").exists()
        assert ECounselingMediaCapture.objects.get(pk=capture.pk).stop_requested_at
        return original(**kwargs)

    client.stop_transcription = checked
    with patch("compass.integrations.daily.DailyClient.from_settings", return_value=client):
        event = body_for(capture)
        emit(event)
        emit(event)
    assert len(client.transcription_stops) == 1


def test_capture_save_failure_after_receipt_creation_rolls_back_both():
    _, capture = reservation("RECORDING")
    event = body_for(capture)
    with patch.object(ECounselingMediaCapture, "save", side_effect=OperationalError(PRIVATE_TEXT)):
        with pytest.raises(ECounselingProviderUnavailable) as error:
            emit(event)
    assert_private_absent(str(error.value))
    assert not Receipt.objects.filter(provider_event_id=event["id"]).exists()
    capture.refresh_from_db()
    assert capture.provider_artifact_id is None


def test_replay_process_loss_rolls_back_budget_and_fresh_delivery_converges():
    _, capture = reservation("RECORDING")
    event = body_for(capture, "ready-to-download")
    emit(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    row.next_attempt_at = timezone.now()
    row.save(update_fields=["next_attempt_at"])
    with patch("compass.ecounseling.webhooks._apply", side_effect=OperationalError(PRIVATE_TEXT)):
        with pytest.raises(ECounselingProviderUnavailable):
            replay_receipt(row.pk)
    row.refresh_from_db()
    assert row.processing_attempts == 1 and row.next_attempt_at
    emit(body_for(capture))
    row.refresh_from_db()
    capture.refresh_from_db()
    assert (
        row.processing_attempts == 2
        and row.processing_outcome == "APPLIED"
        and capture.status == "READY"
    )


def test_application_transaction_defers_policy_io_and_rollback_discards_attempt():
    _, capture = reservation("TRANSCRIPTION")
    ECounselingConsent.objects.filter(room=capture.room).update(withdrawn_at=timezone.now())
    with patch("compass.ecounseling.webhooks._run_policy_stop") as stop:
        with pytest.raises(OperationalError):
            with transaction.atomic():
                emit(body_for(capture))
                stop.assert_not_called()
                raise OperationalError("synthetic rollback")
        stop.assert_not_called()
    capture.refresh_from_db()
    assert capture.stop_requested_at is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_signed_completion_committed_during_metadata_io_supersedes_old_claim(kind):
    from compass.ecounseling.reconciliation import reconcile_captures

    _, capture = reservation(kind, bound=True, state="STOP_REQUESTED")
    entered, release = Event(), Event()
    errors = []

    def blocked():
        assert not connection.in_atomic_block
        entered.set()
        assert release.wait(20)

    client = MetadataOnlyDaily(metadata(capture, active=True), callback=blocked)
    thread = run_thread(lambda: reconcile_captures(client=client), errors)
    assert entered.wait(20)
    try:
        emit(body_for(capture, "ready-to-download"))
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    capture.refresh_from_db()
    recovery = capture.reconciliation
    assert capture.status == "READY" and recovery.state == "SUPERSEDED"
    assert recovery.attempts == 1 and recovery.claim_token is None


@pytest.mark.parametrize("commit_succeeded", [False, True])
def test_receipt_commit_failure_or_lost_ack_preserves_truth_without_duplicate_effects(
    commit_succeeded,
):
    _, capture = reservation("RECORDING")
    event = body_for(capture)
    original_commit = connection.commit
    failed = False

    def commit():
        nonlocal failed
        if not failed:
            failed = True
            if commit_succeeded:
                original_commit()
            raise OperationalError(PRIVATE_TEXT)
        return original_commit()

    with patch.object(connection, "commit", side_effect=commit):
        with pytest.raises(ECounselingProviderUnavailable) as error:
            emit(event)
    assert_private_absent(str(error.value))
    capture.refresh_from_db()
    assert Receipt.objects.filter(provider_event_id=event["id"]).exists() == commit_succeeded
    assert bool(capture.provider_artifact_id) == commit_succeeded
    assert emit(event).duplicate == commit_succeeded
    assert Receipt.objects.filter(provider_event_id=event["id"]).count() == 1
