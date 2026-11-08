"""Synthetic capture evidence and real PostgreSQL consent-ordering regressions."""

from datetime import timedelta
from threading import Thread
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import close_old_connections
from django.test import override_settings
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.ecounseling.media import (
    ECounselingMediaConflict,
    process_media_webhook_event,
    start_recording,
    stop_media_capture,
)
from compass.ecounseling.models import (
    ECounselingMediaArtifact,
)
from compass.ecounseling.services import (
    ECounselingInvalidProviderResponse,
    ECounselingProviderUnavailable,
    create_join_credential,
)
from compass.integrations.daily import DailyHTTPError, DailyTimeout
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_media import (
    FakeMediaDailyClient,
    approve_scope,
    context,
    setup_session,
)
from tests.test_ecounseling_media_v2 import (
    ready_artifact,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def kind():
    """E-Counseling is recording-only, so capture-generic checks run for recordings."""
    return "RECORDING"


@pytest.fixture(autouse=True)
def synthetic_boundaries(monkeypatch):
    def no_real_client():
        pytest.fail("This suite requires a synthetic Daily client.", pytrace=False)

    monkeypatch.setattr("compass.ecounseling.media.DailyClient.from_settings", no_real_client)
    with (
        override_settings(DAILY_ENABLED=True),
        patch("compass.ecounseling.artifacts.enqueue_artifact"),
    ):
        yield


def authorized_session(*, kind="RECORDING"):
    assert kind == "RECORDING"
    _, student, counselor, appointment = setup_session(precreate_room=False)
    approve_scope(
        student=student, counselor=counselor, appointment=appointment, scope="AUDIO_VIDEO_RECORDING"
    )
    client = FakeMediaDailyClient()
    create_join_credential(
        actor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    return student, counselor, appointment, client


def begin(*, kind="RECORDING"):
    student, counselor, appointment, client = authorized_session(kind=kind)
    capture = start_recording(
        counselor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    return student, counselor, appointment, client, capture


def deliver(capture, observation, *, event_id=None, **overrides):
    payload = {
        "room_name": capture.room.daily_room_name,
        "duration": 5,
        "recording_id": capture.provider_artifact_id or "synthetic-artifact",
        "instance_id": capture.provider_instance_id,
        "start_ts": int(timezone.now().timestamp()),
    }
    payload.update(overrides)
    result = process_media_webhook_event(
        event_type=f"recording.{observation}",
        event_id=event_id or str(uuid4()),
        event_ts=timezone.now().timestamp(),
        payload=payload,
    )
    capture.refresh_from_db()
    return result


def stop(capture, counselor, appointment, client):
    return stop_media_capture(
        counselor=counselor,
        appointment_id=appointment.pk,
        kind=capture.kind,
        context=context(counselor),
        daily_client=client,
    )


def stop_audits(capture):
    return AuditEvent.objects.filter(
        action="ecounseling.recording_stop_requested", target_id=str(capture.pk)
    )


@pytest.mark.parametrize("failure", ["invalid_ack", "timeout", "http400"])
def test_stop_failure_never_establishes_terminal_evidence(kind, failure, monkeypatch):
    _, counselor, appointment, client, capture = begin(kind=kind)
    deliver(capture, "started")
    original = client.stop_recording

    def reject(**kwargs):
        original(**kwargs)
        if failure == "invalid_ack":
            return {}
        if failure == "timeout":
            raise DailyTimeout("Synthetic timeout.")
        raise DailyHTTPError(400)

    monkeypatch.setattr(client, "stop_recording", reject)
    expected_error = (
        ECounselingInvalidProviderResponse
        if failure == "invalid_ack"
        else ECounselingProviderUnavailable
    )
    with pytest.raises(expected_error):
        stop(capture, counselor, appointment, client)
    capture.refresh_from_db()
    code = {
        "invalid_ack": "INVALID_ACKNOWLEDGMENT",
        "timeout": "TIMEOUT",
        "http400": "INVALID_REQUEST",
    }[failure]
    assert capture.status == "STOP_REQUESTED" and capture.stop_requested_at
    assert capture.error_code == f"STOP_PROVIDER_{code}"
    assert capture.ended_at is None and capture.ready_at is None
    deliver(capture, "ready-to-download")
    assert capture.status == "READY"  # Independent, correlated positive completion.


@pytest.mark.parametrize(
    "scenario",
    [
        "stopping_started",
        "stopping_error",
        "stopping_error_started",
        "old_error_started",
        "stopped_started",
        "stopped_error",
        "ready_started",
        "ready_error",
        "ready_error_started",
    ],
)
def test_transition_policy_preserves_stop_intent_and_terminal_evidence(kind, scenario):
    _, counselor, appointment, client, capture = begin(kind=kind)
    deliver(capture, "started")
    if scenario.startswith(("stopping", "old_error")):
        capture = stop(capture, counselor, appointment, client)
        expected = "STOP_REQUESTED"
    elif scenario.startswith("stopped"):
        capture.status = "STOPPED"  # Legacy row; no automatic rewrite.
        capture.ended_at = timezone.now() - timedelta(minutes=1)
        capture.save(update_fields=["status", "ended_at"])
        expected = "STOPPED"
    else:
        deliver(capture, "ready-to-download")
        expected = "READY"
    before = (
        capture.stop_requested_at,
        capture.ended_at,
        capture.ready_at,
        capture.started_at,
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.provider_session_id,
    )
    if scenario.startswith("old_error"):
        capture.status = "ERROR"
        capture.error_code = "PROVIDER_ERROR"
        capture.save(update_fields=["status", "error_code"])
    elif "error" in scenario:
        deliver(capture, "error")
    if scenario.endswith("started"):
        deliver(capture, "started")
    assert capture.status == expected
    after = (
        capture.stop_requested_at,
        capture.ended_at,
        capture.ready_at,
        capture.started_at,
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.provider_session_id,
    )
    assert after == before
    if expected == "STOP_REQUESTED":
        assert stop_audits(capture).count() == 1
        with pytest.raises(ECounselingMediaConflict):
            start_recording(
                counselor=counselor,
                appointment_id=appointment.pk,
                context=context(counselor),
                daily_client=client,
            )
        assert len(client.recording_starts) == 1


def test_duplicate_deliveries_and_repeated_completion_preserve_original_evidence(kind):
    _, counselor, appointment, client, capture = begin(kind=kind)
    first = deliver(capture, "started", event_id="same-start")
    started = capture.started_at
    duplicate = deliver(capture, "started", event_id="same-start")
    assert first.accepted and duplicate.duplicate and capture.started_at == started
    capture = stop(capture, counselor, appointment, client)
    requested = capture.stop_requested_at
    deliver(capture, "ready-to-download", event_id="same-ready")
    before = (capture.ready_at, capture.ended_at, capture.duration_seconds)
    assert deliver(capture, "ready-to-download", event_id="same-ready").duplicate
    deliver(capture, "ready-to-download", duration=999)
    assert (capture.ready_at, capture.ended_at, capture.duration_seconds) == before
    assert capture.status == "READY" and capture.stop_requested_at == requested
    assert ECounselingMediaArtifact.objects.filter(capture=capture).count() == (kind == "RECORDING")


def test_recording_completion_uses_provider_start_without_malformed_dispatch_fallback():
    _, _, _, _, capture = begin(kind="RECORDING")
    actual_start = timezone.now().replace(microsecond=0) - timedelta(minutes=2)
    deliver(capture, "started", start_ts=None)
    assert capture.started_at is None and capture.provider_artifact_id is None
    process_media_webhook_event(
        event_type="recording.started",
        event_id=str(uuid4()),
        event_ts=timezone.now().timestamp(),
        payload={"instance_id": capture.provider_instance_id, "recording_id": "synthetic-artifact"},
    )
    capture.refresh_from_db()
    assert capture.started_at is None and capture.status == "ACTIVE"
    deliver(capture, "ready-to-download", start_ts=int(actual_start.timestamp()), duration=5)
    assert capture.status == "READY" and capture.started_at == actual_start
    assert capture.ended_at == actual_start + timedelta(seconds=5)
    deliver(capture, "started", start_ts=int((actual_start + timedelta(minutes=1)).timestamp()))
    assert capture.started_at == actual_start and capture.ended_at == actual_start + timedelta(
        seconds=5
    )


@pytest.mark.parametrize("mismatch", ["unbound", "artifact", "session", "room", "nonterminal"])
def test_uncorrelated_or_contradictory_completion_is_not_stop_proof(kind, mismatch):
    _, counselor, appointment, client, capture = begin(kind=kind)
    deliver(capture, "started")
    capture.provider_session_id = "synthetic-meeting"
    capture.save(update_fields=["provider_session_id"])
    capture = stop(capture, counselor, appointment, client)
    changes = {}
    if mismatch == "unbound":
        capture.provider_artifact_id = None
        capture.save(update_fields=["provider_artifact_id"])
    elif mismatch == "artifact":
        changes["recording_id" if kind == "RECORDING" else "id"] = "different-artifact"
    elif mismatch == "session":
        changes["mtg_session_id"] = "different-meeting"
    elif mismatch == "room":
        changes["room_id"] = "different-room"
    else:
        changes["status"] = "in_progress" if kind == "RECORDING" else "t_in_progress"
    # Supply the known session even for recording's synthetic extended envelope.
    changes.setdefault("mtg_session_id", capture.provider_session_id)
    before = capture.stop_requested_at
    deliver(capture, "ready-to-download", **changes)
    assert capture.status == "STOP_REQUESTED" and capture.stop_requested_at == before
    assert capture.ready_at is None and capture.ended_at is None
    assert not ECounselingMediaArtifact.objects.filter(capture=capture).exists()


@pytest.mark.parametrize("fence", ["capture_disposed", "artifact_disposed", "provider_cleaned"])
def test_late_events_cannot_resurrect_disposition_or_provider_cleanup(kind, fence):
    _, _, _, capture, artifact, _ = ready_artifact(kind)
    capture.provider_instance_id = "synthetic-instance"
    if fence == "capture_disposed":
        capture.artifact_disposed_at = timezone.now()
    elif fence == "artifact_disposed":
        artifact.status = "DISPOSED"
        artifact.disposed_at = timezone.now()
        artifact.save()
    else:
        artifact.provider_deleted_at = timezone.now()
        artifact.save()
        capture.provider_artifact_id = None
    capture.save()
    before = (
        capture.status,
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.ready_at,
    )
    for observation in ("started", "error", "ready-to-download"):
        deliver(capture, observation)
        assert (
            capture.status,
            capture.provider_instance_id,
            capture.provider_artifact_id,
            capture.ready_at,
        ) == before
    artifact.refresh_from_db()
    assert artifact.status == ("DISPOSED" if fence == "artifact_disposed" else "PENDING")


@pytest.mark.parametrize("observation", ["started", "error"])
def test_conflicting_instance_cannot_replace_canonical_capture_or_stop_intent(kind, observation):
    _, counselor, appointment, client, capture = begin(kind=kind)
    deliver(capture, "started")
    capture = stop(capture, counselor, appointment, client)
    before = (capture.provider_instance_id, capture.provider_artifact_id, capture.stop_requested_at)
    overrides = (
        {"instance_id": "foreign-instance"}
        if kind == "RECORDING"
        else {"info": {"instanceId": "foreign-instance"}}
    )
    deliver(capture, observation, **overrides)
    assert capture.status == "STOP_REQUESTED"
    assert (
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.stop_requested_at,
    ) == before


def test_ready_payload_private_material_is_absent_from_capture_audit_and_logs(caplog):
    _, _, _, client, capture = begin()
    deliver(
        capture,
        "started",
        info={"instanceId": capture.provider_instance_id, "private": PRIVATE_TEXT},
    )
    updates = list(client.room_updates)
    deliver(
        capture,
        "ready-to-download",
        out_params={"private": PRIVATE_TEXT},
        share_token=PRIVATE_TEXT,
        s3_key=PRIVATE_TEXT,
        download_link=PRIVATE_TEXT,
    )
    assert capture.status == "READY" and client.room_updates == updates
    # A ready recording queues custody; nothing private from the payload reaches its row.
    artifact = ECounselingMediaArtifact.objects.get(capture=capture)
    assert artifact.status == "PENDING" and artifact.object_key is None
    assert_private_absent(str(capture.__dict__))
    assert_private_absent(str(artifact.__dict__))
    for event in AuditEvent.objects.all():
        assert_private_absent(str(event.metadata))
    assert_private_absent(caplog.text)


def run_thread(function, errors):
    def execute():
        close_old_connections()
        try:
            function()
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            close_old_connections()

    thread = Thread(target=execute)
    thread.start()
    return thread
