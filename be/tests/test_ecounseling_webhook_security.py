"""Synthetic signed deliveries: provenance, durable outcomes and private custody fences."""

import base64
import hashlib
import hmac
import json
import pickle
import time
from copy import deepcopy
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client, override_settings
from django.utils import timezone

from compass.ecounseling.diagnostics import WebhookReplayTaskError
from compass.ecounseling.models import DailyWebhookReceipt as Receipt
from compass.ecounseling.models import (
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
)
from compass.ecounseling.reconciliation import (
    apply_observation,
    claim_capture,
    discover_captures,
    observe_metadata,
    reconcile_captures,
)
from compass.ecounseling.services import (
    ECounselingInvalidWebhook,
    ECounselingProviderUnavailable,
    process_daily_webhook,
)
from compass.ecounseling.tasks import replay_media_webhooks
from compass.ecounseling.webhooks import replay_due_events, replay_receipt
from compass.integrations.daily import DailyTimeout, DailyWebhookSignatureInvalid
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_reconciliation import MetadataOnlyDaily, metadata, pending_capture
from tests.test_ecounseling_reconciliation import fake_only_boundaries as fake_only_boundaries
from tests.test_ecounseling_state_correctness import authorized_session

pytestmark = pytest.mark.django_db
SECRET = b"slice1c3-synthetic-webhook-secret"


def body_for(capture, phase="started", *, event_id=None, artifact_id=None):
    recording = capture.kind == "RECORDING"
    payload = {
        "recording_id" if recording else "id": artifact_id
        or capture.provider_artifact_id
        or "synthetic-artifact",
        "room_name": capture.room.daily_room_name,
        "mtg_session_id": capture.provider_session_id or "synthetic-session",
        "room_id": capture.room.daily_room_id,
    }
    if recording:
        payload.update(instance_id=capture.provider_instance_id, start_ts=int(time.time()) - 10)
        if phase == "ready-to-download":
            payload.update(status="finished", duration=5)
        if phase == "error":
            payload["timestamp"] = int(time.time())
    else:
        payload.update(
            info={"instanceId": capture.provider_instance_id},
            status={
                "started": "t_in_progress",
                "ready-to-download": "t_finished",
                "error": "t_error",
            }[phase],
            duration=0 if phase == "started" else 5.5,
        )
    return {
        "version": "1.1.0",
        "type": f"{'recording' if recording else 'transcript'}.{phase}",
        "id": event_id or str(uuid4()),
        "event_ts": time.time(),
        "payload": payload,
    }


def signed(event=None, *, raw=None, signature=None, header_age=0, http=False):
    raw = json.dumps(event, separators=(",", ":")).encode() if raw is None else raw
    now = time.time()
    timestamp = str(now - header_age)
    signature = (
        signature
        or base64.b64encode(
            hmac.new(SECRET, timestamp.encode() + b"." + raw, hashlib.sha256).digest()
        ).decode()
    )
    with override_settings(
        DAILY_ENABLED=True, DAILY_WEBHOOK_HMAC=base64.b64encode(SECRET).decode()
    ):
        if http:
            return Client().post(
                "/api/v1/integrations/daily/webhook",
                data=raw,
                content_type="application/json",
                HTTP_X_WEBHOOK_SIGNATURE=signature,
                HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
            )
        return process_daily_webhook(
            raw_body=raw, signature=signature, timestamp=timestamp, now_epoch=now
        )


def reservation(kind="TRANSCRIPTION", *, bound=False, storage=False, state="START_REQUESTED"):
    *people, capture = pending_capture(
        kind=kind, state=state, bound=bound, storage=storage, stop_intent=False
    )
    return people, capture


def fenced_artifact(capture, fence):
    fields = dict(
        capture=capture,
        status="DISPOSED" if fence == "artifact" else "STORED" if fence == "stored" else "PENDING",
    )
    if fence == "artifact":
        fields["disposed_at"] = timezone.now()
    elif fence == "cleanup":
        fields["provider_deleted_at"] = timezone.now()
    elif fence == "stored":
        fields.update(
            object_key="synthetic-private-object",
            storage_binding="a" * 64,
            content_type="video/mp4",
            size=5,
            sha256="b" * 64,
            stored_at=timezone.now(),
        )
    return ECounselingMediaArtifact.objects.create(**fields)


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("phase", ["started", "ready-to-download", "error"])
def test_signed_supported_event_mutates_only_exact_verified_capture(kind, phase):
    _, capture = reservation(kind, bound=phase != "started")
    prior_start = capture.started_at
    event = body_for(capture, phase)
    assert signed(event).accepted
    capture.refresh_from_db()
    receipt = Receipt.objects.get(provider_event_id=event["id"])
    assert receipt.processing_outcome == "APPLIED" and receipt.identity_verified
    assert (
        capture.status
        == {"started": "ACTIVE", "ready-to-download": "READY", "error": "ERROR"}[phase]
    )
    assert capture.provider_instance_id == event["payload"].get(
        "instance_id", event["payload"].get("info", {}).get("instanceId")
    )
    if kind == "TRANSCRIPTION":
        assert capture.started_at == prior_start and capture.ended_at is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    "change,code",
    [
        ("instance", "INSTANCE_MISMATCH"),
        ("artifact", "ARTIFACT_MISMATCH"),
        ("session", "SESSION_MISMATCH"),
        ("room", "ROOM_MISMATCH"),
        ("room_id", "ROOM_MISMATCH"),
    ],
)
def test_same_room_or_instance_does_not_authorize_conflicting_identity(kind, change, code):
    _, capture = reservation(kind, bound=True)
    original = (
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.provider_session_id,
        capture.status,
    )
    event = body_for(capture)
    if change == "instance":
        event["payload"]["instance_id"] = (
            "foreign-instance" if kind == "RECORDING" else capture.provider_instance_id
        )
        if kind == "TRANSCRIPTION":
            event["payload"].pop("instance_id")
            event["payload"]["info"]["instanceId"] = "foreign-instance"
    else:
        key = {
            "artifact": "recording_id" if kind == "RECORDING" else "id",
            "session": "mtg_session_id",
            "room": "room_name",
            "room_id": "room_id",
        }[change]
        event["payload"][key] = "foreign-identity"
    signed(event)
    capture.refresh_from_db()
    receipt = Receipt.objects.get(provider_event_id=event["id"])
    assert receipt.processing_outcome == "IDENTITY_CONFLICT" and receipt.anomaly_code == code
    assert receipt.operator_review_required and not receipt.identity_verified
    assert original == (
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.provider_session_id,
        capture.status,
    )
    assert bool(capture.provider_binding_quarantined_at) == (change == "artifact")
    assert not ECounselingMediaArtifact.objects.exists()


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_early_completion_replays_after_exact_start_binding_without_media_io(kind):
    _, capture = reservation(kind, storage=kind == "TRANSCRIPTION")
    early = body_for(capture, "ready-to-download", artifact_id="early-artifact")
    signed(early)
    receipt = Receipt.objects.get(provider_event_id=early["id"])
    assert receipt.processing_outcome == "UNRESOLVED_IDENTITY" and receipt.next_attempt_at
    assert not ECounselingMediaArtifact.objects.exists()
    signed(body_for(capture, artifact_id="early-artifact"))
    capture.refresh_from_db()
    receipt.refresh_from_db()
    assert capture.status == "READY" and capture.provider_artifact_id == "early-artifact"
    assert receipt.processing_outcome == "APPLIED" and receipt.processing_attempts == 2
    assert ECounselingMediaArtifact.objects.filter(capture=capture).count() == 1
    assert signed(early).duplicate
    receipt.refresh_from_db()
    assert receipt.processing_attempts == 2


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_unbound_foreign_completion_is_not_adopted_by_later_other_start(kind):
    _, capture = reservation(kind)
    early = body_for(capture, "ready-to-download", artifact_id="foreign-artifact")
    signed(early)
    signed(body_for(capture, artifact_id="real-artifact"))
    receipt = Receipt.objects.get(provider_event_id=early["id"])
    capture.refresh_from_db()
    assert capture.status == "ACTIVE" and capture.provider_artifact_id == "real-artifact"
    receipt.next_attempt_at = timezone.now() - timedelta(seconds=1)
    receipt.save(update_fields=["next_attempt_at"])
    replay_receipt(receipt.pk)
    receipt.refresh_from_db()
    assert (
        receipt.anomaly_code == "ARTIFACT_MISMATCH"
        and receipt.processing_outcome == "IDENTITY_CONFLICT"
    )
    assert not ECounselingMediaArtifact.objects.exists()


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_no_reservation_never_adopts_foreign_artifact_or_issues_stop(kind):
    _, _, appointment, _ = authorized_session(kind=kind)
    room = appointment.ecounseling_room
    event = {
        "type": f"{'recording' if kind == 'RECORDING' else 'transcript'}.started",
        "id": "unreserved-event",
        "event_ts": time.time(),
        "payload": {
            "room_name": room.daily_room_name,
            "room_id": room.daily_room_id,
            "mtg_session_id": "unreserved-session",
            "recording_id": "foreign-artifact",
            "id": "foreign-artifact",
            "instance_id": "foreign-instance",
            "info": {"instanceId": "foreign-instance"},
        },
    }
    signed(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert row.anomaly_code == "RESERVATION_MISSING" and row.severity == "PRIVACY"
    assert (
        not ECounselingMediaCapture.objects.exists()
        and not ECounselingMediaArtifact.objects.exists()
    )
    assert row.mitigation_state == "REVIEW_REQUIRED" and row.mitigation_attempted_at is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_conflicting_reused_applied_event_id_quarantines_binding_and_fences_metadata_and_custody(
    kind,
):
    _, capture = reservation(kind)
    event = body_for(capture)
    signed(event)
    capture.refresh_from_db()
    capture.status = "STOP_REQUESTED"
    capture.stop_requested_at = timezone.now() - timedelta(seconds=120)
    capture.save(update_fields=["status", "stop_requested_at"])
    discover_captures(limit=20)
    conflicting = deepcopy(event)
    conflicting["payload"]["recording_id" if kind == "RECORDING" else "id"] = "foreign-artifact"
    signed(conflicting)
    capture.refresh_from_db()
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert (
        row.event_id_conflict
        and row.anomaly_code == "EVENT_ID_CONFLICT"
        and capture.provider_binding_quarantined_at
    )
    assert (
        row.provider_artifact_id
        == event["payload"]["recording_id" if kind == "RECORDING" else "id"]
    )
    assert claim_capture(capture.pk) is None
    signed(body_for(capture, "ready-to-download"))
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and not ECounselingMediaArtifact.objects.exists()


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_terminal_webhook_supersedes_reconciliation_claim_without_resetting_attempts(kind):
    _, capture = reservation(kind, bound=True, state="STOP_REQUESTED")
    discover_captures(limit=20)
    claim = claim_capture(capture.pk)
    observed = observe_metadata(claim, metadata(capture, active=True))
    signed(body_for(capture, "ready-to-download"))
    apply_observation(claim, observed)
    capture.refresh_from_db()
    recovery = capture.reconciliation
    assert capture.status == "READY" and recovery.state == "SUPERSEDED" and recovery.attempts == 1
    assert recovery.claim_token is None and recovery.next_attempt_at is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("status", ["STOP_REQUESTED", "READY"])
def test_late_started_and_error_preserve_stop_intent_and_terminal_evidence(kind, status):
    _, capture = reservation(kind, bound=True, state=status)
    capture.stop_requested_at = timezone.now() - timedelta(minutes=1)
    capture.save(update_fields=["stop_requested_at"])
    original = capture.stop_requested_at
    signed(body_for(capture))
    signed(body_for(capture, "error"))
    capture.refresh_from_db()
    assert capture.status == status and capture.stop_requested_at == original


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("fence", ["capture", "artifact", "cleanup", "stored"])
def test_delayed_valid_events_cannot_resurrect_protected_media(kind, fence):
    _, capture = reservation(kind, bound=True)
    if fence == "capture":
        capture.artifact_disposed_at = timezone.now()
        capture.save(update_fields=["artifact_disposed_at"])
    else:
        fenced_artifact(capture, fence)
    before = capture.status
    signed(body_for(capture, "ready-to-download"))
    capture.refresh_from_db()
    assert capture.status == before and capture.ready_at is None
    assert Receipt.objects.latest("received_at").processing_outcome == "DISPOSITION_BLOCKED"


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("failure", [None, "timeout"])
def test_verified_policy_stop_reserves_one_attempt_and_ack_never_proves_cessation(kind, failure):
    _, capture = reservation(kind)
    ECounselingConsent.objects.filter(room=capture.room).update(withdrawn_at=timezone.now())
    from tests.test_ecounseling_media import FakeMediaDailyClient

    client = FakeMediaDailyClient()
    if failure:
        setattr(
            client,
            "stop_recording" if kind == "RECORDING" else "stop_transcription",
            lambda **_: (_ for _ in ()).throw(DailyTimeout(PRIVATE_TEXT)),
        )
    with patch("compass.integrations.daily.DailyClient.from_settings", return_value=client):
        event = body_for(capture)
        signed(event)
        signed(event)
    capture.refresh_from_db()
    row = Receipt.objects.get(provider_event_id=event["id"])
    if kind == "RECORDING":
        assert row.mitigation_attempted_at is None and row.mitigation_state == "REVIEW_REQUIRED"
        assert client.recording_stops == []
    else:
        assert row.mitigation_attempted_at and row.mitigation_state == (
            "FAILED_UNVERIFIED" if failure else "ACK_UNVERIFIED"
        )
    assert capture.status == "STOP_REQUESTED" and capture.ended_at is None
    if not failure and kind == "TRANSCRIPTION":
        assert (
            len(client.recording_stops if kind == "RECORDING" else client.transcription_stops) == 1
        )
    assert_private_absent(str(list(Receipt.objects.values())))


def test_lost_policy_callback_remains_durably_unverified_and_never_retries_stop():
    _, capture = reservation("TRANSCRIPTION")
    ECounselingConsent.objects.filter(room=capture.room).update(withdrawn_at=timezone.now())
    event = body_for(capture)
    with patch("compass.ecounseling.webhooks._after_commit"):
        signed(event)
    assert signed(event).duplicate
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert row.mitigation_state == "ATTEMPT_RESERVED" and row.operator_review_required


@pytest.mark.parametrize(
    "bad", [None, True, "5", float("nan"), float("inf"), -float("inf"), -1, 10**1000]
)
def test_signed_malformed_duration_is_durable_quarantine_with_generic_http_ack(bad):
    _, capture = reservation("TRANSCRIPTION", bound=True)
    event = body_for(capture, "ready-to-download")
    event["payload"]["duration"] = bad
    result = signed(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    capture.refresh_from_db()
    assert result.accepted and row.processing_outcome == "REJECTED_MALFORMED"
    assert row.duration_seconds is None and capture.status == "START_REQUESTED"


@pytest.mark.parametrize(
    "mode", ["signature", "stale", "json", "array", "duplicate_keys", "oversized"]
)
def test_authenticity_envelope_and_size_rejections_never_create_receipts(mode):
    event = {
        "type": "recording.started",
        "id": "bad-envelope",
        "event_ts": time.time(),
        "payload": {},
    }
    kwargs = (
        {"signature": "invalid"}
        if mode == "signature"
        else {"header_age": 901}
        if mode == "stale"
        else {
            "raw": {
                "json": b"{",
                "array": b"[]",
                "duplicate_keys": b'{"type":"recording.started","type":"transcript.started"}',
                "oversized": b" " * 65537,
            }[mode]
        }
    )
    with pytest.raises(
        DailyWebhookSignatureInvalid
        if mode in ("signature", "stale")
        else ECounselingInvalidWebhook
    ):
        signed(event, **kwargs)
    assert not Receipt.objects.exists()


def test_replay_is_delayed_finite_age_bounded_and_disabled_by_default():
    _, capture = reservation("RECORDING")
    event = body_for(capture, "ready-to-download")
    signed(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert signed(event).duplicate
    row.refresh_from_db()
    assert row.processing_attempts == 1
    assert not replay_receipt(row.pk)
    with override_settings(ECOUNSELING_WEBHOOK_REPLAY_ENABLED=False):
        assert replay_due_events() == 0
    for _ in range(6):
        row.next_attempt_at = timezone.now() - timedelta(seconds=1)
        row.save(update_fields=["next_attempt_at"])
        replay_receipt(row.pk)
        row.refresh_from_db()
    assert (
        row.processing_attempts == 6
        and row.next_attempt_at is None
        and row.operator_review_required
    )


def test_receipt_commit_failure_rolls_back_capture_and_exposes_only_safe_error():
    _, capture = reservation("RECORDING")
    event = body_for(capture)
    with patch.object(Receipt, "save", side_effect=OperationalError(PRIVATE_TEXT)):
        with pytest.raises(ECounselingProviderUnavailable) as error:
            signed(event)
    assert_private_absent(str(error.value))
    capture.refresh_from_db()
    assert capture.provider_artifact_id is None and capture.status == "START_REQUESTED"
    assert not Receipt.objects.filter(provider_event_id=event["id"]).exists()


def test_operator_readout_distinguishes_current_risk_from_historical_privacy_escalation():
    _, capture = reservation("TRANSCRIPTION")
    ECounselingConsent.objects.filter(room=capture.room).update(withdrawn_at=timezone.now())
    with patch("compass.ecounseling.webhooks._after_commit"):
        signed(body_for(capture))
    capture.refresh_from_db()
    signed(body_for(capture, "ready-to-download"))
    out = StringIO()
    call_command("ecounseling_capture_reconciliation_status", stdout=out)
    data = json.loads(out.getvalue())
    row = data["webhook_anomalies"][0]
    assert (
        row["historical_escalation"]
        and not row["current_review_required"]
        and row["terminal_evidence_confirmed"]
        and not row["physical_cutoff_verified"]
    )
    assert (
        capture.provider_instance_id not in out.getvalue()
        and capture.room.daily_room_name not in out.getvalue()
    )


def test_replay_task_exception_and_result_are_closed_and_pickle_safe():
    with patch(
        "compass.ecounseling.webhooks.replay_due_events", side_effect=RuntimeError(PRIVATE_TEXT)
    ):
        with pytest.raises(WebhookReplayTaskError) as error:
            replay_media_webhooks.run()
    assert_private_absent(str(error.value))
    assert str(pickle.loads(pickle.dumps(error.value))) == str(error.value)


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_unknown_room_has_durable_closed_evidence_without_provider_action(kind):
    _, capture = reservation(kind)
    event = body_for(capture)
    event["payload"]["room_name"] = "unknown-room"
    if kind == "RECORDING":
        event["payload"]["instance_id"] = "unknown-instance"
    else:
        event["payload"]["info"]["instanceId"] = "unknown-instance"
    signed(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert row.anomaly_code == "UNKNOWN_ROOM" and row.capture_id is None
    assert row.operator_review_required and row.mitigation_attempted_at is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_expired_room_start_is_historical_uncertainty_without_new_stop(kind):
    _, capture = reservation(kind)
    capture.room.room_expires_at = timezone.now() - timedelta(minutes=1)
    capture.room.save(update_fields=["room_expires_at"])
    event = body_for(capture)
    signed(event)
    capture.refresh_from_db()
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert row.anomaly_code == "EXPIRED_ROOM_START" and row.operator_review_required
    assert capture.provider_artifact_id is None and capture.status == "START_REQUESTED"
    assert row.mitigation_attempted_at is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_webhook_after_metadata_completion_fills_only_absent_readiness_anchor(kind):
    _, capture = reservation(kind, bound=True, state="STOP_REQUESTED")
    discover_captures(limit=20)
    claim = claim_capture(capture.pk)
    apply_observation(claim, observe_metadata(claim, metadata(capture)))
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.ready_at is None
    start = capture.started_at
    signed(body_for(capture, "ready-to-download"))
    capture.refresh_from_db()
    assert capture.ready_at is not None and capture.started_at == start
    assert capture.reconciliation.attempts == 1


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_same_applied_id_with_other_supported_type_preserves_original_and_quarantines(kind):
    _, capture = reservation(kind)
    event = body_for(capture)
    signed(event)
    capture.refresh_from_db()
    error = body_for(capture, "error", event_id=event["id"])
    signed(error)
    row = Receipt.objects.get(provider_event_id=event["id"])
    capture.refresh_from_db()
    assert row.event_type == event["type"] and row.applied_at and row.event_id_conflict
    assert capture.provider_binding_quarantined_at and capture.status == "ACTIVE"


def test_malformed_redelivery_does_not_rewrite_valid_identity_or_quarantine_binding():
    _, capture = reservation("RECORDING", bound=True)
    event = body_for(capture, "ready-to-download")
    signed(event)
    bad = deepcopy(event)
    bad["payload"]["duration"] = float("nan")
    signed(bad)
    row = Receipt.objects.get(provider_event_id=event["id"])
    capture.refresh_from_db()
    assert row.processing_outcome == "REJECTED_MALFORMED" and row.applied_at
    assert row.duration_seconds == 5 and not row.event_id_conflict
    assert capture.status == "READY" and capture.provider_binding_quarantined_at is None


def test_http_quarantine_duplicate_and_database_failure_have_safe_existing_response_shape():
    _, capture = reservation("TRANSCRIPTION")
    event = body_for(capture)
    event["payload"]["info"] = []
    first = signed(event, http=True)
    duplicate = signed(event, http=True)
    assert first.status_code == duplicate.status_code == 200
    assert first.json() == {"accepted": True, "duplicate": False}
    assert duplicate.json() == {"accepted": True, "duplicate": True}
    event = body_for(capture)
    with patch.object(Receipt, "save", side_effect=OperationalError(PRIVATE_TEXT)):
        failed = signed(event, http=True)
    assert (
        failed.status_code == 503
        and failed.json()["error"]["code"] == "ecounseling_provider_unavailable"
    )
    assert_private_absent(failed.content.decode())


def test_valid_supported_event_cannot_bypass_validation_with_handshake_marker():
    _, capture = reservation("RECORDING")
    event = body_for(capture)
    event["test"] = "test"
    signed(event)
    assert Receipt.objects.get(provider_event_id=event["id"]).processing_outcome == "APPLIED"


def test_unsupported_valid_event_and_real_handshake_are_acknowledged_without_payload_persistence():
    assert not signed(
        {"type": "participant.joined", "payload": {"private": PRIVATE_TEXT}}
    ).supported
    assert signed({"test": "test"}).accepted
    assert not Receipt.objects.exists()


def test_replay_maximum_age_clears_schedule_without_fabricating_terminal_state():
    _, capture = reservation("RECORDING")
    event = body_for(capture, "ready-to-download")
    signed(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    Receipt.objects.filter(pk=row.pk).update(
        received_at=timezone.now() - timedelta(hours=2), next_attempt_at=timezone.now()
    )
    replay_receipt(row.pk)
    row.refresh_from_db()
    capture.refresh_from_db()
    assert (
        row.next_attempt_at is None
        and row.processing_attempts == 1
        and row.operator_review_required
    )
    assert capture.status == "START_REQUESTED"


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_historical_unverified_binding_cannot_be_certified_by_metadata_or_custody(kind):
    from compass.ecounseling.artifacts import ensure_pending_artifact

    _, capture = reservation(
        kind, bound=True, state="STOP_REQUESTED", storage=kind == "TRANSCRIPTION"
    )
    capture.provider_binding_verified_at = None
    capture.save(update_fields=["provider_binding_verified_at"])
    client = MetadataOnlyDaily(metadata(capture))
    result = reconcile_captures(client=client)
    capture.refresh_from_db()
    assert result["metadata_checks"] == 0 and not client.calls
    assert (
        capture.status == "STOP_REQUESTED"
        and capture.reconciliation.outcome_code == "PROVIDER_IDENTITY_INSUFFICIENT"
    )
    event = body_for(capture, "ready-to-download")
    signed(event)
    row = Receipt.objects.get(provider_event_id=event["id"])
    assert row.processing_outcome == "UNRESOLVED_IDENTITY" and not row.identity_verified
    assert ensure_pending_artifact(capture) is None
    signed(body_for(capture))
    capture.refresh_from_db()
    row.refresh_from_db()
    assert capture.provider_binding_verified_at and capture.status == "READY"
    assert row.processing_outcome == "APPLIED" and capture.reconciliation.attempts == 1


def test_old_receipt_stays_historically_unverified_without_inferred_processing():
    _, capture = reservation("RECORDING")
    event = body_for(capture)
    row = Receipt.objects.create(provider_event_id=event["id"], event_type=event["type"])
    assert signed(event).duplicate
    row.refresh_from_db()
    capture.refresh_from_db()
    assert row.processing_outcome == "HISTORICAL_UNVERIFIED" and not row.identity_verified
    assert capture.provider_binding_verified_at is None and capture.provider_artifact_id is None
