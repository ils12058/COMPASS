"""Synthetic capture evidence and real PostgreSQL consent-ordering regressions."""

from datetime import timedelta
from threading import Event, Thread
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import OperationalError, close_old_connections, connection, transaction
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.ecounseling.artifacts import ingest_artifact, provider_metadata
from compass.ecounseling.media import (
    ECounselingConsentNotApproved,
    ECounselingMediaConflict,
    get_media_projection,
    process_media_webhook_event,
    start_recording,
    start_transcription,
    stop_media_capture,
    withdraw_my_consent,
)
from compass.ecounseling.models import (
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
)
from compass.ecounseling.services import (
    ECounselingInvalidProviderResponse,
    ECounselingNotPermitted,
    ECounselingProviderUnavailable,
    create_join_credential,
)
from compass.integrations.daily import DailyHTTPError, DailyTimeout
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_media import (
    FakeMediaDailyClient,
    approve_scope,
    context,
    make_user,
    setup_session,
)
from tests.test_ecounseling_media_v2 import (
    ArtifactDaily,
    FakeStorage,
    fake_download,
    ready_artifact,
)

pytestmark = pytest.mark.django_db


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


def authorized_session(*, kind="TRANSCRIPTION", storage=False, storage_consent=False, version=2):
    _, student, counselor, appointment = setup_session(media_policy_version=version)
    scope = (
        "SESSION_MEDIA_CAPTURE"
        if version == 2
        else "AUDIO_VIDEO_RECORDING"
        if kind == "RECORDING"
        else "LIVE_TRANSCRIPTION"
    )
    approve_scope(student=student, counselor=counselor, appointment=appointment, scope=scope)
    if storage or storage_consent:
        approve_scope(
            student=student,
            counselor=counselor,
            appointment=appointment,
            scope="TRANSCRIPT_STORAGE",
        )
    client = FakeMediaDailyClient()
    create_join_credential(
        actor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    return student, counselor, appointment, client


def begin(*, kind="TRANSCRIPTION", storage=False, storage_consent=False, version=2):
    student, counselor, appointment, client = authorized_session(
        kind=kind, storage=storage, storage_consent=storage_consent, version=version
    )
    args = dict(counselor=counselor, appointment_id=appointment.pk, context=context(counselor))
    capture = (
        start_recording(**args, daily_client=client)
        if kind == "RECORDING"
        else start_transcription(**args, store_transcript=storage, daily_client=client)
    )
    return student, counselor, appointment, client, capture


def deliver(capture, observation, *, event_id=None, **overrides):
    recording = capture.kind == "RECORDING"
    payload = {
        "room_name": capture.room.daily_room_name,
        "duration": 5,
        "recording_id" if recording else "id": capture.provider_artifact_id or "synthetic-artifact",
    }
    if recording:
        payload.update(
            instance_id=capture.provider_instance_id, start_ts=timezone.now().timestamp()
        )
    else:
        payload.update(
            info={"instanceId": capture.provider_instance_id},
            mtg_session_id=capture.provider_session_id or "synthetic-meeting",
            room_id=capture.room.daily_room_id,
            status="t_finished" if observation == "ready-to-download" else "t_in_progress",
        )
    payload.update(overrides)
    result = process_media_webhook_event(
        event_type=f"{'recording' if recording else 'transcript'}.{observation}",
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
    subject = "recording" if capture.kind == "RECORDING" else "transcription"
    return AuditEvent.objects.filter(
        action=f"ecounseling.{subject}_stop_requested", target_id=str(capture.pk)
    )


def test_transcription_stop_ack_retains_intent_identity_error_and_no_end_time():
    _, counselor, appointment, client, capture = begin()
    deliver(capture, "started")
    capture.error_code = "STOP_PROVIDER_TIMEOUT"
    capture.save(update_fields=["error_code"])
    instance = capture.provider_instance_id
    first = stop(capture, counselor, appointment, client)
    requested = first.stop_requested_at
    second = stop(first, counselor, appointment, client)
    assert second.status == "STOP_REQUESTED" and second.stop_requested_at == requested
    assert second.provider_instance_id == instance and second.ended_at is None
    assert second.error_code == "STOP_PROVIDER_TIMEOUT" and second.ready_at is None
    assert len(client.transcription_stops) == 2  # Two explicit requests; no automatic replay.
    assert {item[1] for item in client.transcription_stops} == {instance}
    assert stop_audits(capture).count() == 1
    assert stop_audits(capture).get().actor_user_id == counselor.pk


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("failure", ["invalid_ack", "timeout", "http400"])
def test_stop_failure_never_establishes_terminal_evidence(kind, failure, monkeypatch):
    _, counselor, appointment, client, capture = begin(kind=kind)
    deliver(capture, "started")
    original = client.stop_recording if kind == "RECORDING" else client.stop_transcription

    def reject(**kwargs):
        original(**kwargs)
        if failure == "invalid_ack":
            return {}
        if failure == "timeout":
            raise DailyTimeout("Synthetic timeout.")
        raise DailyHTTPError(400)

    monkeypatch.setattr(
        client, "stop_recording" if kind == "RECORDING" else "stop_transcription", reject
    )
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


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("version", [1, 2])
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
def test_transition_policy_preserves_stop_intent_and_terminal_evidence(kind, version, scenario):
    _, counselor, appointment, client, capture = begin(kind=kind, version=version)
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
            if kind == "RECORDING":
                start_recording(
                    counselor=counselor,
                    appointment_id=appointment.pk,
                    context=context(counselor),
                    daily_client=client,
                )
            else:
                start_transcription(
                    counselor=counselor,
                    appointment_id=appointment.pk,
                    context=context(counselor),
                    store_transcript=False,
                    daily_client=client,
                )
        assert (
            len(client.recording_starts if kind == "RECORDING" else client.transcription_starts)
            == 1
        )


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
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


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
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


@pytest.mark.parametrize("storage,storage_consent", [(False, False), (False, True), (True, True)])
@pytest.mark.parametrize("version", [1, 2])
def test_finished_job_preserves_selected_storage_mode_and_does_not_claim_custody(
    storage, storage_consent, version
):
    _, counselor, appointment, client, capture = begin(
        storage=storage, storage_consent=storage_consent, version=version
    )
    deliver(capture, "started")
    capture = stop(capture, counselor, appointment, client)
    calls = list(client.room_updates)
    deliver(capture, "ready-to-download")  # No isVttAvailable, no file inspection.
    assert capture.status == "READY" and capture.ended_at is None
    assert capture.transcript_storage_enabled is storage
    assert capture.transcript_storage_authorized is storage
    assert client.room_updates == calls
    assert not get_media_projection(capture.room)["transcription"]["artifact_available"]
    assert ECounselingMediaArtifact.objects.filter(capture=capture).count() == (
        storage and version == 2
    )


@pytest.mark.parametrize("storage", [False, True])
@pytest.mark.parametrize("scope", ["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"])
def test_withdrawal_and_delayed_events_do_not_restore_storage_or_live_consent(
    storage, scope, monkeypatch
):
    student, _, appointment, client, capture = begin(storage=storage, storage_consent=True)
    monkeypatch.setattr("compass.ecounseling.media.DailyClient.from_settings", lambda: client)
    deliver(capture, "started")
    consent = ECounselingConsent.objects.get(room=capture.room, scope=scope)
    withdraw_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=consent.pk,
        context=context(student),
        daily_client=client,
    )
    capture.refresh_from_db()
    requested = capture.stop_requested_at
    deliver(capture, "started")
    assert capture.stop_requested_at == requested
    assert capture.transcript_storage_enabled is False
    deliver(capture, "ready-to-download")
    assert capture.status == "READY" and capture.transcript_storage_enabled is False
    assert capture.transcript_storage_authorized is storage  # Existing historical authorization.
    consent.refresh_from_db()
    assert consent.withdrawn_at and not consent.is_effectively_approved
    if not storage:
        assert not ECounselingMediaArtifact.objects.filter(capture=capture).exists()


def test_finished_stored_transcription_without_vtt_metadata_cannot_reach_custody():
    _, _, _, _, capture = begin(storage=True)
    deliver(capture, "started")
    deliver(capture, "ready-to-download")
    artifact = ECounselingMediaArtifact.objects.get(capture=capture)
    client = ArtifactDaily(capture)
    metadata = client.get_transcript(artifact_id=capture.provider_artifact_id)
    metadata["mtgSessionId"] = capture.provider_session_id
    client.get_transcript = lambda **_: metadata
    assert provider_metadata(capture, client)["isVttAvailable"] is True
    metadata.pop("isVttAvailable")
    storage = FakeStorage()
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    assert capture.status == "READY" and artifact.status == "FAILED"
    assert artifact.error_code == "PROVIDER_IDENTITY_UNVERIFIED"
    assert not storage.objects and "LINK" not in client.calls and "DELETE" not in client.calls


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
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


@pytest.mark.parametrize("storage", [False, True])
@pytest.mark.parametrize("failure", ["timeout", "http400"])
def test_reserved_mode_and_attributable_audit_survive_provider_start_failure(
    storage, failure, monkeypatch
):
    _, counselor, appointment, client = authorized_session(storage=storage)
    original = client.start_transcription

    def reject(**kwargs):
        original(**kwargs)
        raise DailyTimeout("Synthetic timeout.") if failure == "timeout" else DailyHTTPError(400)

    monkeypatch.setattr(client, "start_transcription", reject)
    with pytest.raises(ECounselingProviderUnavailable):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=storage,
            context=context(counselor),
            daily_client=client,
        )
    capture = ECounselingMediaCapture.objects.get(
        room__appointment=appointment, kind="TRANSCRIPTION"
    )
    assert capture.status == ("START_REQUESTED" if failure == "timeout" else "ERROR")
    assert (
        capture.transcript_storage_authorized is storage
        and capture.transcript_storage_enabled is storage
    )
    assert capture.media_authorized_at and capture.provider_instance_id and capture.ended_at is None
    audit = AuditEvent.objects.get(action="ecounseling.transcription_start_requested")
    assert audit.actor_user_id == counselor.pk and audit.metadata["storage_selected"] is storage
    with pytest.raises(ECounselingMediaConflict):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=storage,
            context=context(counselor),
            daily_client=client,
        )
    assert len(client.transcription_starts) == 1


@pytest.mark.parametrize("storage", [False, True])
def test_storage_configuration_timeout_preserves_selection_without_claiming_enablement(
    storage, monkeypatch
):
    _, counselor, appointment, client = authorized_session(storage=storage)

    def configuration_unknown(**_kwargs):
        raise DailyTimeout("Synthetic room update timeout.")

    monkeypatch.setattr(client, "update_room", configuration_unknown)
    with pytest.raises(ECounselingProviderUnavailable):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=storage,
            context=context(counselor),
            daily_client=client,
        )
    capture = ECounselingMediaCapture.objects.get(kind="TRANSCRIPTION")
    assert capture.status == "START_REQUESTED" and capture.error_code == "START_PROVIDER_TIMEOUT"
    assert capture.transcript_storage_authorized is storage
    assert capture.transcript_storage_enabled is False and not client.transcription_starts
    assert (
        AuditEvent.objects.get(action="ecounseling.transcription_start_requested").metadata[
            "storage_selected"
        ]
        is storage
    )


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
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
    assert capture.status == "READY" and not capture.transcript_storage_enabled
    assert not capture.transcript_storage_authorized and client.room_updates == updates
    assert not ECounselingMediaArtifact.objects.filter(capture=capture).exists()
    assert_private_absent(str(capture.__dict__))
    for event in AuditEvent.objects.all():
        assert_private_absent(str(event.metadata))
    assert_private_absent(caplog.text)


def test_withdrawal_before_start_blocks_reservation_configuration_and_command():
    student, counselor, appointment, client = authorized_session(storage=True)
    consent = ECounselingConsent.objects.get(scope="SESSION_MEDIA_CAPTURE")
    withdraw_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=consent.pk,
        context=context(student),
        daily_client=client,
    )
    with pytest.raises(ECounselingConsentNotApproved):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    assert not ECounselingMediaCapture.objects.exists()
    assert not client.room_updates and not client.transcription_starts
    consent.refresh_from_db()
    assert consent.withdrawn_at and not consent.is_effectively_approved


def test_start_intent_audit_failure_prevents_all_provider_side_effects(monkeypatch):
    _, counselor, appointment, client = authorized_session(storage=True)

    def audit_failure(**_kwargs):
        raise OperationalError("Synthetic intent persistence failure.")

    monkeypatch.setattr("compass.ecounseling.media.record_event", audit_failure)
    with pytest.raises(OperationalError):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    assert not ECounselingMediaCapture.objects.exists()
    assert not client.room_updates and not client.transcription_starts


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("storage", [False, True])
@pytest.mark.parametrize("commit_happened", [False, True])
def test_start_ack_then_database_failure_preserves_committed_mode_and_audit(
    storage, commit_happened, monkeypatch
):
    _, counselor, appointment, client = authorized_session(storage=storage)
    original_commit = connection.commit
    fired = False

    def fail_after_start():
        nonlocal fired
        if client.transcription_starts and not fired:
            fired = True
            if commit_happened:
                original_commit()
            raise OperationalError("Synthetic final transaction failure.")
        original_commit()

    monkeypatch.setattr(connection, "commit", fail_after_start)
    with pytest.raises(OperationalError):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=storage,
            context=context(counselor),
            daily_client=client,
        )
    assert fired and len(client.transcription_starts) == 1
    capture = ECounselingMediaCapture.objects.get(
        room__appointment=appointment, kind="TRANSCRIPTION"
    )
    assert capture.status == "START_REQUESTED" and capture.media_authorized_at
    assert (
        capture.transcript_storage_authorized is storage
        and capture.transcript_storage_enabled is storage
    )
    assert capture.provider_instance_id == client.transcription_starts[0][1]
    assert capture.ended_at is None and capture.ready_at is None
    assert (
        AuditEvent.objects.get(action="ecounseling.transcription_start_requested").metadata[
            "storage_selected"
        ]
        is storage
    )


def test_start_refuses_enclosing_application_transaction_before_provider_side_effects():
    _, counselor, appointment, client = authorized_session(storage=True)
    with transaction.atomic(), pytest.raises(RuntimeError, match="durable atomic block"):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    assert not client.transcription_starts and not client.room_updates
    assert not ECounselingMediaCapture.objects.exists()


@pytest.mark.parametrize("denial", ["capability", "relationship", "storage_consent"])
def test_start_authorization_fails_before_intent_or_provider_changes(denial):
    _, counselor, appointment, client = authorized_session()
    if denial == "capability":
        UserCapabilityOverride.objects.create(
            user=counselor,
            capability=Capability.objects.get(code="ecounseling.manage_media_assigned"),
            effect="REVOKE",
            reason="Synthetic policy.",
        )
    elif denial == "relationship":
        counselor = make_user("unassigned@example.edu", "COUNSELOR")
    expected = (
        ECounselingConsentNotApproved if denial == "storage_consent" else ECounselingNotPermitted
    )
    with pytest.raises(expected):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    assert not client.transcription_starts and not client.room_updates
    assert not ECounselingMediaCapture.objects.exists()


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


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("storage", [False, True])
def test_committed_withdrawal_during_room_configuration_prevents_start(storage, monkeypatch):
    student, counselor, appointment, client = authorized_session(storage=storage)
    configured, release = Event(), Event()
    errors = []
    original = client.update_room

    def pause_configuration(**kwargs):
        result = original(**kwargs)
        if (
            kwargs["properties"].get("enable_transcription_storage") is storage
            and not configured.is_set()
        ):
            configured.set()
            assert release.wait(15)
        return result

    monkeypatch.setattr(client, "update_room", pause_configuration)

    def start():
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=storage,
            context=context(counselor),
            daily_client=client,
        )

    thread = run_thread(start, errors)
    try:
        assert configured.wait(15)
        consent = ECounselingConsent.objects.get(scope="SESSION_MEDIA_CAPTURE")
        withdraw_my_consent(
            student=student,
            appointment_id=appointment.pk,
            consent_id=consent.pk,
            context=context(student),
            daily_client=client,
        )
    finally:
        release.set()
        thread.join(15)
    assert not thread.is_alive() and errors == ["ECounselingConsentNotApproved"]
    capture = ECounselingMediaCapture.objects.get(kind="TRANSCRIPTION")
    assert not client.transcription_starts and capture.status == "STOP_REQUESTED"
    assert (
        capture.transcript_storage_enabled is False
        and capture.transcript_storage_authorized is storage
    )
    consent.refresh_from_db()
    assert consent.withdrawn_at and not consent.is_effectively_approved


@pytest.mark.django_db(transaction=True)
def test_withdrawal_in_committed_storage_flag_gap_prevents_provider_start(monkeypatch):
    student, counselor, appointment, client = authorized_session(storage=True)
    consent = ECounselingConsent.objects.get(scope="TRANSCRIPT_STORAGE")
    original_save = ECounselingMediaCapture.save
    scheduled = False

    def withdraw_after_storage_commit(capture, *args, **kwargs):
        nonlocal scheduled
        original_save(capture, *args, **kwargs)
        if capture.transcript_storage_enabled and not scheduled:
            scheduled = True
            transaction.on_commit(
                lambda: withdraw_my_consent(
                    student=student,
                    appointment_id=appointment.pk,
                    consent_id=consent.pk,
                    context=context(student),
                    daily_client=client,
                )
            )

    monkeypatch.setattr(ECounselingMediaCapture, "save", withdraw_after_storage_commit)
    with pytest.raises(ECounselingConsentNotApproved):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    capture = ECounselingMediaCapture.objects.get(kind="TRANSCRIPTION")
    assert scheduled and not client.transcription_starts
    assert capture.transcript_storage_authorized and not capture.transcript_storage_enabled
    assert capture.status == "STOP_REQUESTED"
    consent.refresh_from_db()
    assert consent.withdrawn_at and not consent.is_effectively_approved


@pytest.mark.django_db(transaction=True)
def test_manual_stop_in_configuration_commit_gap_keeps_confirmed_disablement(monkeypatch):
    _, counselor, appointment, client = authorized_session(storage=True)
    original_save = ECounselingMediaCapture.save
    scheduled = False

    def stop_after_configuration_commit(capture, *args, **kwargs):
        nonlocal scheduled
        original_save(capture, *args, **kwargs)
        if capture.transcript_storage_enabled and not scheduled:
            scheduled = True
            transaction.on_commit(lambda: stop(capture, counselor, appointment, client))

    monkeypatch.setattr(ECounselingMediaCapture, "save", stop_after_configuration_commit)
    with pytest.raises(ECounselingMediaConflict):
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    capture = ECounselingMediaCapture.objects.get(kind="TRANSCRIPTION")
    assert scheduled and not client.transcription_starts and len(client.transcription_stops) == 1
    assert (
        capture.status == "STOP_REQUESTED"
        and capture.stop_requested_at
        and capture.ended_at is None
    )
    assert capture.transcript_storage_authorized and not capture.transcript_storage_enabled
    assert client.room_updates[-1][1] == {"enable_transcription_storage": False}
    assert stop_audits(capture).count() == 1


@pytest.mark.django_db(transaction=True)
def test_start_winning_room_lock_serializes_withdrawal_and_exposes_stop_intent(monkeypatch):
    student, counselor, appointment, client = authorized_session(storage=True)
    entered, release, withdrawal_at_lock = Event(), Event(), Event()
    errors = []
    consent = ECounselingConsent.objects.get(scope="SESSION_MEDIA_CAPTURE")
    original = client.start_transcription

    def locked_start(**kwargs):
        assert connection.in_atomic_block
        assert ECounselingConsent.objects.get(pk=consent.pk).is_effectively_approved
        result = original(**kwargs)
        entered.set()
        assert release.wait(15)
        assert ECounselingConsent.objects.get(pk=consent.pk).is_effectively_approved
        return result

    monkeypatch.setattr(client, "start_transcription", locked_start)

    def start():
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )

    def withdraw():
        def at_lock(execute, sql, params, many, query_context):
            if '"ecounseling_ecounselingroom"' in sql and "FOR UPDATE" in sql:
                withdrawal_at_lock.set()
            return execute(sql, params, many, query_context)

        with connection.execute_wrapper(at_lock):
            withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=consent.pk,
                context=context(student),
                daily_client=client,
            )

    first = run_thread(start, errors)
    second = None
    try:
        assert entered.wait(15)
        second = run_thread(withdraw, errors)
        assert withdrawal_at_lock.wait(15)
    finally:
        release.set()
        first.join(15)
        if second:
            second.join(15)
    assert not first.is_alive() and second and not second.is_alive() and not errors
    consent.refresh_from_db()
    capture = ECounselingMediaCapture.objects.get(kind="TRANSCRIPTION")
    assert consent.withdrawn_at and not consent.is_effectively_approved
    assert (
        capture.status == "STOP_REQUESTED"
        and capture.stop_requested_at
        and capture.ended_at is None
    )
    assert capture.transcript_storage_authorized and not capture.transcript_storage_enabled
    assert len(client.transcription_starts) == len(client.transcription_stops) == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_start_requests_reserve_one_instance_and_send_one_command(monkeypatch):
    _, counselor, appointment, client = authorized_session(storage=True)
    configured, release = Event(), Event()
    errors = []
    original = client.update_room

    def pause_configuration(**kwargs):
        result = original(**kwargs)
        configured.set()
        assert release.wait(15)
        return result

    monkeypatch.setattr(client, "update_room", pause_configuration)

    def start():
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )

    first = run_thread(start, errors)
    second = None
    try:
        assert configured.wait(15)
        second = run_thread(start, errors)
        second.join(15)
        assert not second.is_alive() and errors == ["ECounselingMediaConflict"]
    finally:
        release.set()
        first.join(15)
        if second:
            second.join(15)
    assert not first.is_alive() and len(client.transcription_starts) == 1
    assert len(client.room_updates) == 1 and ECounselingMediaCapture.objects.count() == 1
    assert (
        AuditEvent.objects.filter(action="ecounseling.transcription_start_requested").count() == 1
    )
