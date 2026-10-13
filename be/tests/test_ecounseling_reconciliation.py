"""Verified Daily metadata fixtures and deterministic PostgreSQL recovery races."""

import json
import logging
import pickle
import runpy
from copy import deepcopy
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, transaction
from django.test import override_settings
from django.utils import timezone

from compass.common.json_logging import JsonFormatter
from compass.ecounseling.diagnostics import (
    CaptureReconciliationTaskError,
    CaptureStage,
    log_capture_reconciliation,
)
from compass.ecounseling.media import get_media_projection, withdraw_my_consent
from compass.ecounseling.models import (
    ECounselingCaptureReconciliation as Recovery,
)
from compass.ecounseling.models import (
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
)
from compass.ecounseling.reconciliation import (
    discover_captures,
    reconcile_captures,
)
from compass.ecounseling.tasks import reconcile_media_captures, recover_media_artifacts
from compass.integrations.daily import (
    DailyHTTPError,
    DailyInvalidResponse,
    DailyTimeout,
    DailyUnavailable,
)
from compass.service_catalog.models import Service
from tests import test_ecounseling_media as media_fixtures
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_media import context
from tests.test_ecounseling_state_correctness import begin, deliver

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_only_boundaries(monkeypatch, caplog):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Reconciliation tests permit only synthetic metadata clients.", pytrace=False)

    for path in (
        "compass.integrations.daily.DailyClient.from_settings",
        "compass.integrations.daily.urlopen",
        "compass.ecounseling.artifacts.ObjectStorage",
        "compass.ecounseling.artifacts.stream_daily_media",
    ):
        monkeypatch.setattr(path, forbidden)
    monkeypatch.setattr("compass.ecounseling.artifacts.enqueue_artifact", lambda *_: None)
    caplog.set_level(logging.INFO, logger="compass.ecounseling.diagnostics")
    with override_settings(DAILY_ENABLED=True, ECOUNSELING_CAPTURE_RECONCILIATION_ENABLED=True):
        yield


def pending_capture(
    *,
    kind="TRANSCRIPTION",
    state="STOP_REQUESTED",
    bound=True,
    storage=False,
    stop_intent=None,
    version=2,
):
    # The existing helper assumes an otherwise empty DB. Use distinct synthetic sessions for
    # batch/concurrency cases, including unique artifact identities from the documented contract.
    factory = media_fixtures.make_user
    service_factory = media_fixtures.create_counseling_service
    suffix = uuid4().hex
    with (
        patch.object(
            media_fixtures,
            "make_user",
            lambda email, role: factory(email.replace("@", f"+{suffix}@"), role),
        ),
        patch.object(
            media_fixtures,
            "create_counseling_service",
            lambda admin: (
                Service.objects.filter(code="COUNSELING").first() or service_factory(admin)
            ),
        ),
    ):
        student, counselor, appointment, original_client, capture = begin(
            kind=kind, storage=storage, version=version
        )
    if bound:
        deliver(
            capture, "started", **{"recording_id" if kind == "RECORDING" else "id": str(uuid4())}
        )
        capture.provider_session_id = str(uuid4())
        # Synthetic provider media time, independent of webhook dispatch. Transcript started
        # has no documented media-start timestamp after Slice 1C.3 removes the old fallback.
        capture.started_at = capture.started_at or timezone.now() - timedelta(seconds=120)
    capture.status = state
    capture.media_authorized_at = timezone.now() - timedelta(seconds=120)
    if stop_intent is True or (stop_intent is None and state == "STOP_REQUESTED"):
        capture.stop_requested_at = timezone.now() - timedelta(seconds=120)
    if state == "ERROR":
        capture.failed_at = timezone.now() - timedelta(seconds=120)
    capture.error_code = (
        "STOP_PROVIDER_NO_ACTIVE_RECORDING"
        if capture.stop_requested_at
        else "START_PROVIDER_TIMEOUT"
    )
    capture.save()
    return student, counselor, appointment, original_client, capture


def metadata(capture, *, active=False, vtt=True):
    if capture.kind == "RECORDING":
        return {
            "id": capture.provider_artifact_id,
            "room_name": capture.room.daily_room_name,
            "mtgSessionId": capture.provider_session_id,
            "status": "in-progress" if active else "finished",
            "start_ts": int((timezone.now() - timedelta(seconds=90)).timestamp()),
            **({} if active else {"duration": 30}),
        }
    return {
        "transcriptId": capture.provider_artifact_id,
        "roomId": capture.room.daily_room_id,
        "mtgSessionId": capture.provider_session_id,
        "status": "t_in_progress" if active else "t_finished",
        "created_at": (timezone.now() - timedelta(seconds=90)).isoformat(),
        "updated_at": timezone.now().isoformat(),
        "duration": 30,
        **({} if vtt is None else {"isVttAvailable": vtt}),
    }


class MetadataOnlyDaily:
    def __init__(self, item=None, *, error=None, callback=None):
        self.item, self.error, self.callback = item, error, callback
        self.calls = []

    def get_capture_metadata(self, **kwargs):
        self.calls.append(kwargs)
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return deepcopy(self.item)

    def __getattr__(self, _name):
        pytest.fail("A forbidden provider operation was attempted.", pytrace=False)


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    ("state", "stop_intent"),
    [("START_REQUESTED", False), ("STOP_REQUESTED", True), ("ERROR", True), ("ERROR", False)],
)
@pytest.mark.parametrize("active", [False, True])
def test_bound_metadata_is_monotonic_and_preserves_historical_evidence(
    kind, state, stop_intent, active
):
    *_, capture = pending_capture(kind=kind, state=state, stop_intent=stop_intent)
    prior = {
        k: getattr(capture, k)
        for k in (
            "provider_instance_id",
            "provider_artifact_id",
            "provider_session_id",
            "stop_requested_at",
            "error_code",
            "started_at",
            "ready_at",
            "ended_at",
            "transcript_storage_enabled",
            "transcript_storage_authorized",
        )
    }
    client = MetadataOnlyDaily(metadata(capture, active=active))
    result = reconcile_captures(client=client)
    capture.refresh_from_db()
    recovery = Recovery.objects.get(capture=capture)
    assert result["metadata_checks"] == 1 and recovery.attempts == 1
    assert capture.status == (
        "STOP_REQUESTED" if active and stop_intent else "ACTIVE" if active else "READY"
    )
    assert all(getattr(capture, k) == value for k, value in prior.items())
    assert recovery.provider_evidence == ("ACTIVE" if active else "COMPLETED")
    assert recovery.outcome_code == (
        "PROVIDER_ACTIVE_CONFIRMED" if active else "PROVIDER_COMPLETION_CONFIRMED"
    )
    assert recovery.state == ("PENDING" if active and stop_intent else "RESOLVED")
    assert (recovery.completion_confirmed_at is not None) is (not active)
    assert ECounselingMediaArtifact.objects.filter(capture=capture).count() == (
        1 if not active and kind == "RECORDING" else 0
    )
    assert reconcile_captures(client=client)["metadata_checks"] == 0
    assert len(client.calls) == 1


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("state", ["START_REQUESTED", "STOP_REQUESTED", "ERROR"])
def test_unknown_artifact_never_lists_adopts_replays_or_proves_absence(kind, state):
    *_, capture = pending_capture(kind=kind, state=state, bound=False)
    instance = capture.provider_instance_id
    client = MetadataOnlyDaily({"id": "foreign", "status": "finished"})
    assert reconcile_captures(client=client)["metadata_checks"] == 0
    capture.refresh_from_db()
    recovery = Recovery.objects.get(capture=capture)
    assert recovery.outcome_code == "PROVIDER_IDENTITY_INSUFFICIENT" and recovery.state == "PENDING"
    assert capture.status == state and capture.provider_artifact_id is None
    assert (
        capture.provider_instance_id == instance
        and capture.ready_at is None
        and capture.ended_at is None
    )
    assert not client.calls and not ECounselingMediaArtifact.objects.exists()


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    "conflict",
    [
        "artifact",
        "room",
        "session",
        "missing_artifact",
        "missing_room",
        "missing_session",
        "instance",
        "nested_instance",
        "kind",
    ],
)
def test_metadata_identity_conflicts_or_missing_required_binding_preserve_uncertainty(
    kind, conflict
):
    *_, capture = pending_capture(kind=kind)
    item = metadata(capture)
    field = {
        "artifact": "id" if kind == "RECORDING" else "transcriptId",
        "room": "room_name" if kind == "RECORDING" else "roomId",
        "session": "mtgSessionId",
    }
    if conflict.startswith("missing_"):
        del item[field[conflict.removeprefix("missing_")]]
    elif conflict in field:
        item[field[conflict]] = "foreign"
    elif conflict == "nested_instance":
        item["info"] = {"instanceId": "foreign"}
    else:
        item["instanceId" if conflict == "instance" else "kind"] = "foreign"
    reconcile_captures(client=MetadataOnlyDaily(item))
    capture.refresh_from_db()
    assert (
        capture.status == "STOP_REQUESTED" and capture.ready_at is None and capture.ended_at is None
    )
    assert Recovery.objects.get(capture=capture).outcome_code == "PROVIDER_IDENTITY_INSUFFICIENT"
    assert not ECounselingMediaArtifact.objects.exists()


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("RECORDING", "canceled"),
        ("TRANSCRIPTION", "t_error"),
        ("TRANSCRIPTION", "t_deleted"),
        ("RECORDING", None),
        ("TRANSCRIPTION", "unsupported-malformed-status"),
    ],
)
def test_noncompletion_or_malformed_status_does_not_establish_cessation(kind, status):
    *_, capture = pending_capture(kind=kind)
    item = metadata(capture)
    item["status"] = status
    reconcile_captures(client=MetadataOnlyDaily(item))
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and capture.ended_at is None
    assert Recovery.objects.get(capture=capture).outcome_code == "PROVIDER_OUTCOME_UNKNOWN"


@pytest.mark.parametrize(
    "error",
    [
        DailyTimeout(PRIVATE_TEXT),
        DailyHTTPError(429),
        DailyHTTPError(500),
        DailyHTTPError(503),
        DailyHTTPError(404),
        DailyHTTPError(400),
        DailyUnavailable(PRIVATE_TEXT),
        DailyInvalidResponse(PRIVATE_TEXT),
        RuntimeError(PRIVATE_TEXT),
    ],
)
def test_provider_failures_preserve_uncertainty_and_schedule_safe_bounded_retry(error, caplog):
    *_, capture = pending_capture()
    prior = capture.error_code
    reconcile_captures(client=MetadataOnlyDaily(error=error))
    capture.refresh_from_db()
    recovery = Recovery.objects.get(capture=capture)
    assert capture.status == "STOP_REQUESTED" and capture.error_code == prior
    assert (
        capture.ended_at is None
        and recovery.state == "PENDING"
        and recovery.next_attempt_at > timezone.now()
    )
    assert recovery.outcome_code == "PROVIDER_METADATA_UNAVAILABLE"
    assert recovery.provider_failure_code == (
        error.diagnostic_code if hasattr(error, "diagnostic_code") else None
    )
    assert_private_absent(json.dumps(list(Recovery.objects.values()), default=str))
    for record in caplog.records:
        assert_private_absent(JsonFormatter().format(record))


@pytest.mark.parametrize("vtt", [None, False, True])
@pytest.mark.parametrize("stored", [False, True])
def test_finished_transcript_does_not_invent_vtt_storage_flags_or_institutional_custody(
    vtt, stored
):
    *_, capture = pending_capture(storage=stored)
    reconcile_captures(client=MetadataOnlyDaily(metadata(capture, vtt=vtt)))
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.ready_at is None and capture.ended_at is None
    assert (
        capture.transcript_storage_authorized is stored
        and capture.transcript_storage_enabled is stored
    )
    artifact = ECounselingMediaArtifact.objects.filter(capture=capture).first()
    assert (artifact is not None) is stored
    if artifact:
        assert (
            artifact.status == "PENDING" and artifact.stored_at is None and artifact.attempts == 0
        )
        assert artifact.provider_deleted_at is None and artifact.object_key is None


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_documented_start_metadata_can_fill_an_absent_time_without_inventing_end_or_ready(kind):
    *_, capture = pending_capture(kind=kind)
    capture.started_at = None
    capture.save(update_fields=["started_at"])
    item = metadata(capture)
    reconcile_captures(client=MetadataOnlyDaily(item))
    capture.refresh_from_db()
    assert capture.started_at is not None and capture.started_at < timezone.now()
    assert capture.status == "READY" and capture.ready_at is None and capture.ended_at is None
    assert Recovery.objects.get(capture=capture).completion_confirmed_at > capture.started_at


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    "optional", ["missing", "bad_time", "bad_duration", "nan_duration", "infinite_duration"]
)
def test_malformed_optional_times_or_duration_do_not_fabricate_media_evidence(kind, optional):
    *_, capture = pending_capture(kind=kind)
    capture.started_at = None
    capture.save(update_fields=["started_at"])
    item = metadata(capture)
    if optional == "missing":
        item.pop("start_ts" if kind == "RECORDING" else "created_at")
        item.pop("duration", None)
    elif optional == "bad_time":
        item["start_ts" if kind == "RECORDING" else "created_at"] = PRIVATE_TEXT
    else:
        item["duration"] = {
            "bad_duration": PRIVATE_TEXT,
            "nan_duration": float("nan"),
            "infinite_duration": float("inf"),
        }[optional]
    reconcile_captures(client=MetadataOnlyDaily(item))
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.ended_at is None and capture.ready_at is None
    if optional in ("missing", "bad_time"):
        assert capture.started_at is None
    if optional in ("missing", "bad_duration", "nan_duration", "infinite_duration"):
        assert capture.duration_seconds is None


def test_missing_local_transcript_room_binding_cannot_fall_back_to_room_name():
    *_, capture = pending_capture()
    item = metadata(capture)
    item["room_name"] = capture.room.daily_room_name
    capture.room.daily_room_id = None
    capture.room.save(update_fields=["daily_room_id"])
    reconcile_captures(client=MetadataOnlyDaily(item))
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED"
    assert Recovery.objects.get(capture=capture).outcome_code == "PROVIDER_IDENTITY_INSUFFICIENT"


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_unknown_session_is_never_assigned_from_a_provider_snapshot(kind):
    *_, capture = pending_capture(kind=kind)
    capture.provider_session_id = None
    capture.save(update_fields=["provider_session_id"])
    item = metadata(capture)
    item["mtgSessionId"] = "provider-session-never-adopted"
    reconcile_captures(client=MetadataOnlyDaily(item))
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.provider_session_id is None


@pytest.mark.parametrize("bound", [False, True])
def test_finite_backoff_survives_redelivery_and_ends_in_durable_operator_review(bound, monkeypatch):
    *_, capture = pending_capture(bound=bound)
    clock = [timezone.now()]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    client = MetadataOnlyDaily(error=DailyHTTPError(404))
    delays = []
    for attempt in range(1, settings.ECOUNSELING_CAPTURE_RECONCILIATION_MAX_ATTEMPTS + 1):
        result = reconcile_captures(client=client)
        assert result["claimed"] == 1
        row = Recovery.objects.get(capture=capture)
        assert row.attempts == attempt
        # A redelivery/browser-independent fresh invocation cannot bypass the committed deadline.
        assert reconcile_captures(client=client)["claimed"] == 0
        if row.next_attempt_at:
            delays.append(int((row.next_attempt_at - clock[0]).total_seconds()))
            clock[0] = row.next_attempt_at + timedelta(seconds=1)
    assert delays == [60, 120, 240, 480, 900]
    row.refresh_from_db()
    assert row.state == "ESCALATED" and row.escalation_code == "RECONCILIATION_EXHAUSTED"
    assert row.next_attempt_at is None and row.escalated_at is not None
    assert len(client.calls) == (6 if bound else 0)
    clock[0] += timedelta(days=10)
    assert reconcile_captures(client=client)["claimed"] == 0
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and capture.ended_at is None
    output = StringIO()
    call_command("ecounseling_capture_reconciliation_status", stdout=output)
    data = json.loads(output.getvalue())
    assert data["escalations"][0]["capture_id"] == str(capture.pk)
    assert data["escalations"][0]["attempts"] == 6


def test_old_uncertainty_escalates_without_polling_or_rewriting_capture_history():
    *_, capture = pending_capture()
    capture.stop_requested_at = timezone.now() - timedelta(hours=2)
    capture.save(update_fields=["stop_requested_at"])
    prior = ECounselingMediaCapture.objects.values().get(pk=capture.pk)
    client = MetadataOnlyDaily(metadata(capture))
    reconcile_captures(client=client)
    row = Recovery.objects.get(capture=capture)
    assert row.state == "ESCALATED" and row.attempts == 0 and row.last_checked_at is None
    assert row.escalation_code == "RECONCILIATION_EXHAUSTED" and not client.calls
    assert ECounselingMediaCapture.objects.values().get(pk=capture.pk) == prior


def test_initial_grace_is_durable_and_does_not_charge_an_attempt():
    *_, capture = pending_capture()
    capture.stop_requested_at = timezone.now()
    capture.save(update_fields=["stop_requested_at"])
    client = MetadataOnlyDaily(metadata(capture))
    assert reconcile_captures(client=client)["claimed"] == 0
    row = Recovery.objects.get(capture=capture)
    assert row.attempts == 0 and row.next_attempt_at == capture.stop_requested_at + timedelta(
        seconds=60
    )
    assert not client.calls


def test_batch_limit_and_future_deadlines_allow_other_captures_to_progress():
    captures = [pending_capture()[-1] for _ in range(5)]
    client = MetadataOnlyDaily(error=DailyHTTPError(429))
    with override_settings(ECOUNSELING_CAPTURE_RECONCILIATION_BATCH_SIZE=2):
        counts = [reconcile_captures(client=client) for _ in range(3)]
    assert [count["metadata_checks"] for count in counts] == [2, 2, 1]
    assert len(client.calls) == 5
    assert set(call["artifact_id"] for call in client.calls) == {
        capture.provider_artifact_id for capture in captures
    }
    assert Recovery.objects.filter(attempts=1).count() == 5


@pytest.mark.parametrize(
    "fence",
    ["ready", "stopped", "disposed_capture", "disposed_artifact", "provider_cleaned", "stored"],
)
def test_terminal_disposition_cleanup_and_custody_are_excluded_without_any_get(fence):
    *_, capture = pending_capture()
    if fence in ("ready", "stopped"):
        capture.status = fence.upper()
        capture.save(update_fields=["status"])
    elif fence == "disposed_capture":
        capture.artifact_disposed_at = timezone.now()
        capture.save(update_fields=["artifact_disposed_at"])
    elif fence == "disposed_artifact":
        ECounselingMediaArtifact.objects.create(
            capture=capture, status="DISPOSED", disposed_at=timezone.now()
        )
    elif fence == "provider_cleaned":
        ECounselingMediaArtifact.objects.create(capture=capture, provider_deleted_at=timezone.now())
    else:
        ECounselingMediaArtifact.objects.create(
            capture=capture,
            status="STORED",
            object_key="synthetic-key",
            storage_binding="a" * 64,
            sha256="b" * 64,
            content_type="text/vtt",
            size=10,
            stored_at=timezone.now(),
        )
    prior = ECounselingMediaCapture.objects.values().get(pk=capture.pk)
    client = MetadataOnlyDaily(metadata(capture))
    assert reconcile_captures(client=client)["claimed"] == 0
    assert not Recovery.objects.exists() and not client.calls
    assert ECounselingMediaCapture.objects.values().get(pk=capture.pk) == prior


def test_capture_attempts_do_not_overwrite_the_existing_artifact_retry_or_custody_record():
    *_, capture = pending_capture(storage=True)
    artifact = ECounselingMediaArtifact.objects.create(
        capture=capture,
        status="FAILED",
        attempts=5,
        error_code="PROVIDER_METADATA_FAILED",
        next_attempt_at=timezone.now() + timedelta(minutes=10),
    )
    prior = ECounselingMediaArtifact.objects.values().get(pk=artifact.pk)
    reconcile_captures(client=MetadataOnlyDaily(metadata(capture)))
    assert Recovery.objects.get(capture=capture).attempts == 1
    assert ECounselingMediaArtifact.objects.values().get(pk=artifact.pk) == prior


@pytest.mark.parametrize("active", [False, True])
def test_withdrawal_preserves_authorization_and_stop_and_active_metadata_escalates_urgently(
    active, caplog
):
    student, _, appointment, original, capture = pending_capture(storage=True)
    original_stop = capture.stop_requested_at
    withdraw_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=ECounselingConsent.objects.get(
            room=capture.room, scope="SESSION_MEDIA_CAPTURE"
        ).pk,
        context=context(student),
        daily_client=original,
    )
    commands = deepcopy(original.transcription_stops)
    reconcile_captures(client=MetadataOnlyDaily(metadata(capture, active=active)))
    capture.refresh_from_db()
    row = Recovery.objects.get(capture=capture)
    assert capture.stop_requested_at == original_stop and capture.transcript_storage_authorized
    assert not capture.transcript_storage_enabled and original.transcription_stops == commands
    assert (
        ECounselingConsent.objects.get(
            room=capture.room, scope="SESSION_MEDIA_CAPTURE"
        ).withdrawn_at
        is not None
    )
    if active:
        assert not ECounselingMediaArtifact.objects.exists()
        assert capture.status == "STOP_REQUESTED" and row.state == "ESCALATED"
        assert (
            row.escalation_code == "PRIVACY_REVIEW_REQUIRED" and row.provider_evidence == "ACTIVE"
        )
        assert any(
            r.levelno == logging.ERROR
            and getattr(r, "outcome_code", None) == "PRIVACY_REVIEW_REQUIRED"
            for r in caplog.records
        )
    else:
        assert capture.status == "READY" and row.state == "RESOLVED"
        artifact = ECounselingMediaArtifact.objects.get(capture=capture)
        assert (
            artifact.status == "PENDING" and artifact.stored_at is None and artifact.attempts == 0
        )


def test_unselected_transcript_storage_is_not_authorized_by_approved_storage_consent():
    student, counselor, appointment, _, capture = pending_capture(storage=False)
    from tests.test_ecounseling_media import approve_scope

    approve_scope(
        student=student, counselor=counselor, appointment=appointment, scope="TRANSCRIPT_STORAGE"
    )
    before = get_media_projection(capture.room)
    reconcile_captures(client=MetadataOnlyDaily(metadata(capture)))
    after = get_media_projection(capture.room)
    capture.refresh_from_db()
    assert set(before) == set(after)
    assert not capture.transcript_storage_authorized and not capture.transcript_storage_enabled
    assert not ECounselingMediaArtifact.objects.exists()
    assert "reconciliation" not in json.dumps(after)


def test_private_provider_metadata_and_exception_prose_never_enter_recovery_or_logs(caplog):
    *_, capture = pending_capture()
    item = metadata(capture)
    for key in ("error", "outParams", "recordingUrl", "signedLink", "studentName", "transcript"):
        item[key] = PRIVATE_TEXT
    reconcile_captures(client=MetadataOnlyDaily(item))
    assert_private_absent(json.dumps(list(Recovery.objects.values()), default=str))
    assert_private_absent(json.dumps(list(ECounselingMediaCapture.objects.values()), default=str))
    for record in caplog.records:
        assert_private_absent(JsonFormatter().format(record))


def test_closed_logging_and_exception_serialization_reject_arbitrary_values(caplog):
    log_capture_reconciliation(
        stage=PRIVATE_TEXT,
        kind=PRIVATE_TEXT,
        outcome=PRIVATE_TEXT,
        attempts=PRIVATE_TEXT,
        evidence=PRIVATE_TEXT,
        retry_scheduled=PRIVATE_TEXT,
        delay_seconds=PRIVATE_TEXT,
        terminal_confirmed=PRIVATE_TEXT,
        escalation_required=PRIVATE_TEXT,
    )
    record = caplog.records[-1]
    formatted = json.loads(JsonFormatter().format(record))
    assert formatted["outcome_code"] == "PROVIDER_OUTCOME_UNKNOWN"
    assert formatted["pipeline_stage"] == "INTERNAL_UNVERIFIED"
    assert "media_kind" not in formatted and "attempt_number" not in formatted
    assert_private_absent(json.dumps(formatted))
    for stage in (PRIVATE_TEXT, CaptureStage.APPLY):
        error = CaptureReconciliationTaskError(stage)
        assert str(pickle.loads(pickle.dumps(error))) == str(error)
        assert_private_absent(str(error))


@pytest.mark.parametrize(
    "field",
    ["state", "outcome_code", "provider_evidence", "provider_failure_code", "escalation_code"],
)
def test_persistent_diagnostic_vocabulary_rejects_raw_provider_prose(field):
    *_, capture = pending_capture()
    discover_captures(limit=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        # Fits every column: test the closed vocabulary, rather than only its length bound.
        Recovery.objects.filter(capture=capture).update(**{field: "raw private"})


@pytest.mark.parametrize(("enabled", "daily"), [(False, True), (True, False)])
def test_disabled_recovery_does_not_consume_budget_or_contact_daily(enabled, daily):
    *_, capture = pending_capture()
    client = MetadataOnlyDaily(metadata(capture))
    with override_settings(ECOUNSELING_CAPTURE_RECONCILIATION_ENABLED=enabled, DAILY_ENABLED=daily):
        assert reconcile_captures(client=client)["disabled"] == 1
    assert not client.calls and not Recovery.objects.exists()


def test_new_task_is_independent_of_artifact_recovery_and_sanitizes_task_failures(monkeypatch):
    assert reconcile_media_captures.name == "compass.ecounseling.reconcile_media_captures"
    assert recover_media_artifacts.name == "compass.ecounseling.recover_media_artifacts"
    assert reconcile_media_captures.acks_late and reconcile_media_captures.reject_on_worker_lost
    assert (
        reconcile_media_captures.soft_time_limit == 120
        and reconcile_media_captures.time_limit == 150
    )

    def fail():
        raise OperationalError(PRIVATE_TEXT)

    monkeypatch.setattr("compass.ecounseling.reconciliation.reconcile_captures", fail)
    result = reconcile_media_captures.apply(throw=False)
    assert result.failed() and isinstance(result.result, CaptureReconciliationTaskError)
    assert_private_absent(str(result.result))
    assert result.result.__suppress_context__
    assert recover_media_artifacts() == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_beat_registration_is_opted_in_only_after_worker_upgrade(enabled, monkeypatch):
    monkeypatch.setenv("ECOUNSELING_CAPTURE_RECONCILIATION_ENABLED", str(enabled).lower())
    namespace = runpy.run_path("config/settings.py")
    schedule = namespace["CELERY_BEAT_SCHEDULE"]
    assert ("ecounseling-capture-reconciliation" in schedule) is enabled
    if enabled:
        assert schedule["ecounseling-capture-reconciliation"] == {
            "task": reconcile_media_captures.name,
            "schedule": 60,
        }
    assert schedule["ecounseling-artifact-recovery"]["task"] == recover_media_artifacts.name


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("MAX_ATTEMPTS", "0"),
        ("BATCH_SIZE", "21"),
        ("TIMEOUT_SECONDS", "6"),
        ("TIMEOUT_SECONDS", "nan"),
        ("MAX_AGE_SECONDS", "299"),
        ("RETRY_BASE_SECONDS", "0"),
        ("CLAIM_TTL_SECONDS", "0"),
        ("INTERVAL_SECONDS", "0"),
    ],
)
def test_configuration_caps_cannot_allow_unbounded_provider_checks(setting, value, monkeypatch):
    monkeypatch.setenv("ECOUNSELING_CAPTURE_RECONCILIATION_" + setting, value)
    with pytest.raises(ValueError, match="ECOUNSELING_CAPTURE_RECONCILIATION_"):
        runpy.run_path("config/settings.py")


@pytest.mark.parametrize("limit", [0, 101])
def test_operator_evidence_command_is_bounded_and_read_only(limit):
    with pytest.raises(CommandError, match="limit"):
        call_command("ecounseling_capture_reconciliation_status", limit=limit)


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_legacy_pending_capture_uses_its_own_consent_scope_and_does_not_create_v2_custody(kind):
    *_, capture = pending_capture(kind=kind, storage=kind == "TRANSCRIPTION", version=1)
    reconcile_captures(client=MetadataOnlyDaily(metadata(capture)))
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.room.media_policy_version == 1
    assert not ECounselingMediaArtifact.objects.exists()
