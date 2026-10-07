"""Synthetic, fake-only end-to-end tests for consent, custody, access and approved disposition."""

import hashlib
import time
from contextlib import contextmanager
from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.db import connection
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.common.errors import APIError
from compass.ecounseling.artifacts import access_artifact, ensure_pending_artifact, ingest_artifact
from compass.ecounseling.media import (
    ECounselingConsentConflict,
    ECounselingConsentNotApproved,
    ECounselingConsentScopeIncompatible,
    get_media_projection,
    process_media_webhook_event,
    request_consents,
    start_recording,
    start_transcription,
    withdraw_my_consent,
)
from compass.ecounseling.models import (
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    ECounselingRoom,
)
from compass.ecounseling.services import (
    ECounselingNotPermitted,
    ECounselingProviderUnavailable,
    create_join_credential,
)
from compass.ecounseling.tasks import recover_media_artifacts
from compass.integrations.daily import DailyUnavailable
from compass.integrations.media_download import (
    MediaDownloadError,
    stream_daily_media,
    validate_daily_link,
)
from compass.privacy_governance import retention
from compass.privacy_governance.retention_models import DispositionCase
from compass.privacy_governance.tasks import execute_disposition
from tests.test_ecounseling_media import (
    FakeMediaDailyClient,
    approve_scope,
    context,
    make_user,
    setup_session,
)
from tests.test_operational_retention import rule_values
from tests.test_privacy_governance import auth_client, make_dpo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_dispatch():
    with (
        patch("compass.ecounseling.artifacts.enqueue_artifact"),
        patch("compass.privacy_governance.retention.enqueue"),
    ):
        yield


def session():
    return setup_session(media_policy_version=2)


def approved_session(storage=False):
    _, student, counselor, appointment = session()
    approve_scope(
        student=student, counselor=counselor, appointment=appointment, scope="SESSION_MEDIA_CAPTURE"
    )
    if storage:
        approve_scope(
            student=student,
            counselor=counselor,
            appointment=appointment,
            scope="TRANSCRIPT_STORAGE",
        )
    client = FakeMediaDailyClient()
    with patch("compass.ecounseling.services.settings.DAILY_ENABLED", True):
        create_join_credential(
            actor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
    return student, counselor, appointment, client


def test_new_room_combines_permission_without_starting_media_and_preserves_terminal_choices():
    _, student, counselor, appointment = session()
    rows = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"],
        context=context(counselor),
    )
    room = ECounselingRoom.objects.get(appointment=appointment)
    assert room.media_policy_version == 2 and room.provisioned_at is None
    assert not room.media_captures.exists()
    assert len(rows) == 2
    media = room.consents.get(scope="SESSION_MEDIA_CAPTURE")
    media.decision, media.decided_at = "DENIED", timezone.now()
    media.save()
    with pytest.raises(ECounselingConsentConflict):
        request_consents(
            counselor=counselor,
            appointment_id=appointment.pk,
            scopes=["SESSION_MEDIA_CAPTURE"],
            context=context(counselor),
        )
    assert appointment.status == "SCHEDULED"


@pytest.mark.parametrize(
    "version,scope",
    [(1, "SESSION_MEDIA_CAPTURE"), (2, "AUDIO_VIDEO_RECORDING"), (2, "LIVE_TRANSCRIPTION")],
)
def test_scope_contract_is_enforced_in_services_and_api(version, scope):
    _, _, counselor, appointment = session()
    ECounselingRoom.objects.create(
        appointment=appointment, daily_room_name="scope-room", media_policy_version=version
    )
    with pytest.raises(ECounselingConsentScopeIncompatible):
        request_consents(
            counselor=counselor,
            appointment_id=appointment.pk,
            scopes=[scope],
            context=context(counselor),
        )
    response = auth_client(counselor).post(
        f"/api/v1/e-counseling/appointments/{appointment.pk}/consents",
        data='{"scopes":["' + scope + '"]}',
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ecounseling_consent_scope_incompatible"
    assert not ECounselingConsent.objects.exists()


def test_both_v2_capture_types_use_combined_permission_but_storage_needs_its_own():
    student, counselor, appointment, client = approved_session()
    with patch("compass.ecounseling.media.settings.DAILY_ENABLED", True):
        with pytest.raises(ECounselingConsentNotApproved):
            start_transcription(
                counselor=counselor,
                appointment_id=appointment.pk,
                store_transcript=True,
                context=context(counselor),
                daily_client=client,
            )
        recording = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
        transcription = start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=False,
            context=context(counselor),
            daily_client=client,
        )
    assert recording.pk != transcription.pk
    assert len(client.recording_starts) == len(client.transcription_starts) == 1
    assert not transcription.transcript_storage_authorized


@pytest.mark.parametrize("fail_recording", [False, True])
def test_combined_withdrawal_commits_before_both_stops_and_independent_storage_disable(
    fail_recording,
):
    student, counselor, appointment, client = approved_session(storage=True)
    with patch("compass.ecounseling.media.settings.DAILY_ENABLED", True):
        start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
        start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
    consent = ECounselingConsent.objects.get(scope="SESSION_MEDIA_CAPTURE")
    original = client.stop_recording

    def stop(**kwargs):
        assert (
            not connection.in_atomic_block
            or consent.__class__.objects.get(pk=consent.pk).withdrawn_at
        )
        assert consent.__class__.objects.get(pk=consent.pk).withdrawn_at
        original(**kwargs)
        if fail_recording:
            raise DailyUnavailable("sanitized")
        return {"status": "sent"}

    client.stop_recording = stop
    with patch("compass.ecounseling.media.settings.DAILY_ENABLED", True):
        if fail_recording:
            with pytest.raises(ECounselingProviderUnavailable):
                withdraw_my_consent(
                    student=student,
                    appointment_id=appointment.pk,
                    consent_id=consent.pk,
                    context=context(student),
                    daily_client=client,
                )
        else:
            withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=consent.pk,
                context=context(student),
                daily_client=client,
            )
    consent.refresh_from_db()
    assert consent.withdrawn_at and not consent.is_effectively_approved
    assert len(client.recording_stops) == len(client.transcription_stops) == 1
    assert client.room_updates[-1][1] == {"enable_transcription_storage": False}
    transcription = ECounselingMediaCapture.objects.get(kind="TRANSCRIPTION")
    assert (
        not transcription.transcript_storage_enabled and transcription.transcript_storage_authorized
    )
    with pytest.raises(ECounselingConsentConflict):
        request_consents(
            counselor=counselor,
            appointment_id=appointment.pk,
            scopes=["SESSION_MEDIA_CAPTURE"],
            context=context(counselor),
        )


class FakeStorage:
    namespace = "f" * 64

    def binding_identity(self):
        return self.namespace

    def __init__(self, *, fail_save=False, fail_verify=False, fail_delete=False):
        self.objects = {}
        self.calls = []
        self.fail_save, self.fail_verify, self.fail_delete = fail_save, fail_verify, fail_delete

    def validate_sensitive_policy(self):
        self.calls.append("POLICY")

    def exists(self, name):
        self.calls.append("EXISTS")
        return name in self.objects

    def save(self, name, file):
        self.calls.append("SAVE")
        if self.fail_save:
            raise OSError("never exposed")
        self.objects[name] = file.read()
        return name

    def verify(self, name, *, size, sha256):
        self.calls.append("VERIFY")
        content = self.objects.get(name, b"")
        return (
            not self.fail_verify
            and len(content) == size
            and hashlib.sha256(content).hexdigest() == sha256
        )

    def delete(self, name):
        self.calls.append("DELETE")
        if self.fail_delete:
            raise OSError("never exposed")
        self.objects.pop(name, None)

    def private_url(self, key, **kwargs):
        self.calls.append(("URL", kwargs))
        return "https://private.example.test/file?signed=secret"


class ArtifactDaily:
    def __init__(self, capture, *, fail_delete=False):
        self.capture, self.calls, self.fail_delete = capture, [], fail_delete

    def get_recording(self, *, artifact_id):
        self.calls.append("GET")
        return {
            "id": artifact_id,
            "status": "finished",
            "room_name": self.capture.room.daily_room_name,
        }

    def get_transcript(self, *, artifact_id):
        self.calls.append("GET")
        return {
            "transcriptId": artifact_id,
            "status": "t_finished",
            "roomId": self.capture.room.daily_room_id,
            "isVttAvailable": True,
        }

    def recording_access_link(self, *, artifact_id):
        self.calls.append("LINK")
        return {
            "download_link": "https://daily-meeting-recordings.s3.us-west-2.amazonaws.com/opaque?secret=provider",
            "expires": int(time.time()) + 900,
        }

    def transcript_access_link(self, *, artifact_id):
        self.calls.append("LINK")
        return {
            "transcriptId": artifact_id,
            "link": "https://daily-meeting-transcripts.s3.us-west-2.amazonaws.com/opaque?secret=provider",
        }

    def delete_recording(self, *, artifact_id):
        self.calls.append("DELETE")
        if self.fail_delete:
            raise DailyUnavailable("sanitized")
        return {"deleted": True, "id": artifact_id}

    def delete_transcript(self, *, artifact_id):
        self.calls.append("DELETE")
        if self.fail_delete:
            raise DailyUnavailable("sanitized")
        return {"transcriptId": artifact_id, "status": "t_deleted"}


@contextmanager
def fake_download(url, *, kind):
    content = (
        b"WEBVTT\n\n00:00.000 --> 00:01.000\nsynthetic\n"
        if kind == "TRANSCRIPTION"
        else b"\x00\x00\x00\x18ftypisomsynthetic-media"
    )
    yield (
        BytesIO(content),
        "text/vtt" if kind == "TRANSCRIPTION" else "video/mp4",
        len(content),
        hashlib.sha256(content).hexdigest(),
    )


def ready_artifact(kind="RECORDING", *, pending=True):
    _, student, counselor, appointment = session()
    room = ECounselingRoom.objects.create(
        appointment=appointment,
        daily_room_name="opaque-room",
        daily_room_id="opaque-provider-room",
        media_policy_version=2,
        room_expires_at=timezone.now() - timedelta(days=31),
    )
    capture = ECounselingMediaCapture.objects.create(
        room=room,
        kind=kind,
        status="READY",
        provider_artifact_id="opaque-artifact",
        ready_at=timezone.now() - timedelta(days=31),
        media_authorized_at=timezone.now() - timedelta(days=32),
        transcript_storage_authorized=kind == "TRANSCRIPTION",
    )
    artifact = ensure_pending_artifact(capture)
    if not pending:
        storage = FakeStorage()
        ingest_artifact(
            artifact.pk, storage=storage, client=ArtifactDaily(capture), download=fake_download
        )
        artifact.refresh_from_db()
        capture.refresh_from_db()
        return student, counselor, appointment, capture, artifact, storage
    return student, counselor, appointment, capture, artifact, FakeStorage()


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_ingestion_stores_verified_opaque_copy_then_cleans_provider_and_projects_availability(kind):
    _, counselor, appointment, capture, artifact, storage = ready_artifact(kind)
    client = ArtifactDaily(capture)
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "STORED" and artifact.provider_deleted_at
    assert capture.provider_artifact_id is None and capture.artifact_disposed_at is None
    assert artifact.object_key == f"{capture.room_id}/{capture.pk}/{artifact.pk}"
    assert client.calls == ["GET", "LINK", "GET", "DELETE"]
    assert storage.calls.index("SAVE") < storage.calls.index("VERIFY")
    assert get_media_projection(capture.room)[
        "recording" if kind == "RECORDING" else "transcription"
    ]["artifact_available"]
    with patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage):
        access = access_artifact(
            counselor=counselor,
            appointment_id=appointment.pk,
            kind=kind,
            context=context(counselor),
        )
    assert "signed=secret" in access["url"]
    metadata = str(list(AuditEvent.objects.values_list("metadata", flat=True)))
    assert all(
        secret not in metadata
        for secret in ("signed=", "secret=provider", artifact.object_key, "synthetic-media")
    )


@pytest.mark.parametrize("failure", ["save", "verify", "cleanup"])
def test_ingestion_failure_is_durable_and_preserves_provider_until_verified_custody(failure):
    _, _, _, capture, artifact, storage = ready_artifact()
    storage.fail_save = failure == "save"
    storage.fail_verify = failure == "verify"
    client = ArtifactDaily(capture, fail_delete=failure == "cleanup")
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == ("STORED" if failure == "cleanup" else "FAILED")
    assert capture.provider_artifact_id and artifact.next_attempt_at
    assert ("DELETE" in client.calls) == (failure == "cleanup")
    storage.fail_save = storage.fail_verify = client.fail_delete = False
    artifact.next_attempt_at = timezone.now()
    artifact.save()
    ingest_artifact(artifact.pk, storage=storage, client=client, download=fake_download)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "STORED" and capture.provider_artifact_id is None
    assert len(storage.objects) == 1


def test_worker_adopts_upload_after_crash_without_a_second_provider_download():
    _, _, _, capture, artifact, storage = ready_artifact()
    with fake_download("never-persisted", kind="RECORDING") as (file, mime, size, digest):
        artifact.object_key = f"{capture.room_id}/{capture.pk}/{artifact.pk}"
        artifact.content_type, artifact.size, artifact.sha256 = mime, size, digest
        artifact.storage_binding = storage.binding_identity()
        artifact.status = "PROCESSING"
        artifact.claimed_at = timezone.now() - timedelta(hours=1)
        artifact.save()
        storage.objects[artifact.object_key] = file.read()
    client = ArtifactDaily(capture)
    ingest_artifact(
        artifact.pk, storage=storage, client=client, download=lambda *_: pytest.fail("must adopt")
    )
    artifact.refresh_from_db()
    assert artifact.status == "STORED" and client.calls == ["GET", "DELETE"]


def test_duplicate_ready_webhooks_create_one_artifact_and_broker_failure_is_recovered():
    _, _, _, capture, artifact, _ = ready_artifact()
    for index in range(2):
        process_media_webhook_event(
            event_type="recording.ready-to-download",
            event_id=f"event-{index}",
            event_ts=time.time(),
            payload={
                "recording_id": capture.provider_artifact_id,
                "room_name": capture.room.daily_room_name,
            },
        )
    assert ECounselingMediaArtifact.objects.count() == 1
    with patch("compass.ecounseling.tasks.enqueue_artifact") as enqueue:
        assert recover_media_artifacts() == 1
        enqueue.assert_called_once_with(artifact.pk)


@pytest.mark.parametrize(
    "role", ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER", "STUDENT"]
)
def test_artifact_access_requires_assigned_active_counselor_even_with_explicit_capability(role):
    _, _, appointment, _, _, storage = ready_artifact(pending=False)
    other = make_user("other@example.edu", role)
    UserCapabilityOverride.objects.create(
        user=other,
        capability=Capability.objects.get(code="ecounseling.access_media_assigned"),
        effect="GRANT",
        reason="synthetic",
    )
    with (
        patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage),
        pytest.raises(ECounselingNotPermitted),
    ):
        access_artifact(
            counselor=other, appointment_id=appointment.pk, kind="RECORDING", context=context(other)
        )


@pytest.mark.parametrize("state", ["PENDING", "PROCESSING", "FAILED", "DISPOSED"])
def test_only_stored_artifact_can_be_accessed(state):
    _, counselor, appointment, capture, artifact, storage = ready_artifact()
    artifact.status = state
    if state == "DISPOSED":
        artifact.disposed_at = timezone.now()
    artifact.save()
    with (
        patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage),
        pytest.raises(APIError) as error,
    ):
        access_artifact(
            counselor=counselor,
            appointment_id=appointment.pk,
            kind="RECORDING",
            context=context(counselor),
        )
    assert error.value.status_code == (410 if state == "DISPOSED" else 409)


def test_access_has_no_store_bounded_ttl_and_survives_completed_appointment_service_changes():
    _, counselor, appointment, capture, artifact, storage = ready_artifact(pending=False)
    appointment.status = "COMPLETED"
    appointment.completed_at = timezone.now()
    appointment.save()
    appointment.service.is_active = False
    appointment.service.save()
    with patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage):
        result = auth_client(counselor).get(
            f"/api/v1/e-counseling/appointments/{appointment.pk}/media/RECORDING/access"
        )
    assert result.status_code == 200, result.content
    assert result["Cache-Control"] == "no-store, private" and result["Pragma"] == "no-cache"
    url_call = [call for call in storage.calls if isinstance(call, tuple)][0][1]
    assert url_call["expires_seconds"] == 300
    assert url_call["filename"].startswith("e-counseling-recording-")
    assert not {"object_key", "provider_artifact_id"} & result.json().keys()


def v2_case(capture):
    dpo = make_dpo()
    values = rule_values(
        "ECOUNSELING_RECORDING" if capture.kind == "RECORDING" else "ECOUNSELING_TRANSCRIPT"
    )
    values.update(contract_version=2, action="DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE")
    rule = retention.create_rule(actor=dpo, values=values, context=context(dpo))
    retention.transition_rule(
        actor=dpo,
        rule_id=rule.pk,
        expected_revision=rule.revision,
        activate=True,
        context=context(dpo),
    )
    retention.discover_eligibility()
    case = DispositionCase.objects.get(source_id=capture.pk)
    return dpo, case


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("provider_residue", [False, True])
def test_v2_disposition_deletes_verified_live_copies_and_late_events_cannot_resurrect(
    kind, provider_residue
):
    _, counselor, appointment, capture, artifact, storage = ready_artifact(kind, pending=False)
    if provider_residue:
        capture.provider_artifact_id = "opaque-artifact"
        capture.save()
        artifact.provider_deleted_at = None
        artifact.save()
    dpo, case = v2_case(capture)
    retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=context(dpo)
    )
    provider = ArtifactDaily(capture)
    with (
        patch("compass.privacy_governance.media_disposition.ObjectStorage", return_value=storage),
        patch(
            "compass.privacy_governance.media_disposition.DailyClient.from_settings",
            return_value=provider,
        ),
    ):
        execute_disposition(case.pk)
    case.refresh_from_db()
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert case.state == "COMPLETED" and artifact.status == "DISPOSED"
    assert not storage.objects and not artifact.object_key and not artifact.sha256
    assert capture.artifact_disposed_at and capture.provider_artifact_id is None
    assert ("DELETE" in provider.calls) == provider_residue
    ingest_artifact(artifact.pk, storage=storage, client=provider, download=fake_download)
    process_media_webhook_event(
        event_type="recording.ready-to-download"
        if kind == "RECORDING"
        else "transcript.ready-to-download",
        event_id="late-event",
        event_ts=time.time(),
        payload={
            "room_name": capture.room.daily_room_name,
            "recording_id": "late-provider",
            "id": "late-provider",
        },
    )
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert (
        not storage.objects
        and artifact.status == "DISPOSED"
        and capture.provider_artifact_id is None
    )


@pytest.mark.parametrize("failure", ["delete", "absence", "provider"])
def test_uncertain_v2_disposition_never_completes_and_keeps_locations_for_reconciliation(failure):
    _, _, _, capture, artifact, storage = ready_artifact(pending=False)
    capture.provider_artifact_id = "residue"
    capture.save()
    if failure == "delete":
        storage.fail_delete = True
    if failure == "absence":
        storage.delete = lambda key: None
    provider = ArtifactDaily(capture, fail_delete=failure == "provider")
    dpo, case = v2_case(capture)
    retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=context(dpo)
    )
    with (
        patch("compass.privacy_governance.media_disposition.ObjectStorage", return_value=storage),
        patch(
            "compass.privacy_governance.media_disposition.DailyClient.from_settings",
            return_value=provider,
        ),
    ):
        execute_disposition(case.pk)
    case.refresh_from_db()
    artifact.refresh_from_db()
    assert case.state == "RECONCILIATION_REQUIRED" and artifact.object_key
    assert artifact.status == "STORED"
    assert ("DELETE" in provider.calls) == (failure == "provider")


def test_hold_revokes_queued_approval_and_keeps_canonical_object():
    _, _, _, capture, artifact, storage = ready_artifact(pending=False)
    dpo, case = v2_case(capture)
    case = retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=context(dpo)
    )
    retention.change_hold(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        reason="synthetic hold",
        release=False,
        context=context(dpo),
    )
    with patch("compass.privacy_governance.media_disposition.ObjectStorage", return_value=storage):
        execute_disposition(case.pk)
    case.refresh_from_db()
    assert case.state == "ON_HOLD" and case.approved_at is None and storage.objects
    case = retention.change_hold(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        reason=None,
        release=True,
        context=context(dpo),
    )
    assert case.state == "READY" and case.approved_at is None


def test_unresolved_ingestion_blocks_retention_without_provider_or_storage_calls():
    _, _, _, capture, artifact, _ = ready_artifact()
    _, case = v2_case(capture)
    assert case.state == "BLOCKED" and case.blocker == "INGESTION_INCOMPLETE"


def test_versioned_rules_coexist_and_do_not_discover_sources_from_the_other_version():
    _, _, _, capture, artifact, storage = ready_artifact(pending=False)
    dpo, case = v2_case(capture)
    values = rule_values("ECOUNSELING_RECORDING")
    values["code"] = "LEGACY-SYNTHETIC"
    legacy = retention.create_rule(actor=dpo, values=values, context=context(dpo))
    retention.transition_rule(
        actor=dpo,
        rule_id=legacy.pk,
        expected_revision=legacy.revision,
        activate=True,
        context=context(dpo),
    )
    retention.discover_eligibility()
    case.refresh_from_db()
    assert case.contract_version == 2 and case.rule_id != legacy.pk
    assert not retention.source_queryset("ECOUNSELING_RECORDING", 1).filter(pk=capture.pk).exists()
    assert retention.source_queryset("ECOUNSELING_RECORDING", 2).filter(pk=capture.pk).exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://daily-meeting-recordings.s3.amazonaws.com/file",
        "https://127.0.0.1/file",
        "https://evil.test/file",
        "https://daily-meeting-recordings.s3.amazonaws.com.evil.test/file",
        "https://user:secret@daily-meeting-recordings.s3.amazonaws.com/file",
        "https://daily-meeting-recordings.s3.amazonaws.com:8443/file",
    ],
)
def test_untrusted_provider_download_destination_is_rejected(url):
    with pytest.raises(MediaDownloadError):
        validate_daily_link(
            {"download_link": url, "expires": int(time.time()) + 900},
            kind="RECORDING",
            artifact_id="synthetic",
        )


def test_recording_download_uses_bounded_reads_and_disk_spooling_and_validates_content():
    response = MagicMock()
    response.status = 200
    response.headers = {"Content-Type": "video/mp4", "Content-Length": "24"}
    response.read.side_effect = [b"\x00\x00\x00\x18ftypisom" + b"0" * 12, b""]
    response.__enter__.return_value = response
    opener = MagicMock()
    opener.open.return_value = response
    with patch("compass.integrations.media_download.build_opener", return_value=opener):
        with stream_daily_media("https://not-logged.test/?secret=never-log", kind="RECORDING") as (
            file,
            mime,
            size,
            digest,
        ):
            assert file.fileno() >= 0 and mime == "video/mp4" and size == 24
    assert response.read.call_args_list == [((65536,), {}), ((65536,), {})]
    request = opener.open.call_args.args[0]
    assert "Authorization" not in request.headers


def test_recording_start_rechecks_combined_consent_after_provider_room_enablement(settings):
    settings.DAILY_ENABLED = True
    student, counselor, appointment, client = approved_session()
    consent = ECounselingConsent.objects.get(
        room__appointment=appointment, scope="SESSION_MEDIA_CAPTURE"
    )
    original = client.update_room

    def racing_update(**kwargs):
        result = original(**kwargs)
        if kwargs["properties"].get("enable_recording"):
            withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=consent.pk,
                context=context(student),
                daily_client=client,
            )
        return result

    client.update_room = racing_update
    with pytest.raises(ECounselingConsentNotApproved):
        start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
    assert not client.recording_starts
    assert (
        ECounselingMediaCapture.objects.get(room__appointment=appointment, kind="RECORDING").status
        == "STOP_REQUESTED"
    )


def test_delayed_ready_events_preserve_v2_identity_and_original_retention_anchor():
    _, _, _, capture, artifact, _ = ready_artifact()
    before = capture.ready_at
    for artifact_id in (capture.provider_artifact_id, "conflicting-late-artifact"):
        process_media_webhook_event(
            event_type="recording.ready-to-download",
            event_id=artifact_id,
            event_ts=time.time(),
            payload={"room_name": capture.room.daily_room_name, "recording_id": artifact_id},
        )
    capture.refresh_from_db()
    assert capture.provider_artifact_id == "opaque-artifact" and capture.ready_at == before
    assert ECounselingMediaArtifact.objects.filter(capture=capture).count() == 1


def test_completed_workspace_keeps_historical_files_with_join_closed():
    from compass.ecounseling.services import get_counselor_workspace

    _, counselor, appointment, _, artifact, _ = ready_artifact(pending=False)
    appointment.status = "COMPLETED"
    appointment.completed_at = timezone.now()
    appointment.save()
    appointment.service.is_active = False
    appointment.service.save()
    data = get_counselor_workspace(counselor=counselor, appointment_id=appointment.pk)
    assert data["media"]["recording"]["artifact_available"]
    assert not data["provider_readiness"]["join_allowed"]
    assert data["provider_readiness"]["join_state"] == "CLOSED"


@pytest.mark.parametrize(
    "revoke", ["ecounseling.access_media_assigned", "ecounseling.view_assigned"]
)
def test_assigned_access_requires_capability_and_its_view_dependency(revoke):
    _, counselor, appointment, _, _, storage = ready_artifact(pending=False)
    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code=revoke),
        effect="REVOKE",
        reason="Synthetic test",
    )
    with (
        patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage),
        pytest.raises(ECounselingNotPermitted),
    ):
        access_artifact(
            counselor=counselor,
            appointment_id=appointment.pk,
            kind="RECORDING",
            context=context(counselor),
        )


def test_broker_failure_preserves_pending_outbox_for_recovery(django_capture_on_commit_callbacks):
    from compass.ecounseling.artifacts import enqueue_artifact as dispatch

    _, _, _, _, artifact, _ = ready_artifact()
    with patch(
        "compass.ecounseling.tasks.ingest_media_artifact.delay",
        side_effect=RuntimeError("synthetic broker offline"),
    ):
        dispatch(artifact.pk)
    artifact.refresh_from_db()
    assert artifact.status == "PENDING" and artifact.next_attempt_at
    with patch("compass.ecounseling.tasks.enqueue_artifact") as retried:
        recover_media_artifacts()
    retried.assert_called_once_with(artifact.pk)


@pytest.mark.django_db(transaction=True)
def test_duplicate_jobs_on_separate_database_sessions_upload_only_once():
    from threading import Event, Thread

    from django.db import close_old_connections

    _, _, _, capture, artifact, storage = ready_artifact()
    entered, release = Event(), Event()
    provider = ArtifactDaily(capture)
    errors = []

    @contextmanager
    def paused_download(url, *, kind):
        entered.set()
        assert release.wait(10)
        with fake_download(url, kind=kind) as content:
            yield content

    def first_job():
        close_old_connections()
        try:
            ingest_artifact(artifact.pk, storage=storage, client=provider, download=paused_download)
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            close_old_connections()

    thread = Thread(target=first_job)
    thread.start()
    try:
        assert entered.wait(10)
        ingest_artifact(artifact.pk, storage=storage, client=provider, download=fake_download)
        artifact.refresh_from_db()
        assert artifact.attempts == 1 and artifact.status == "PROCESSING"
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and not errors
    artifact.refresh_from_db()
    assert artifact.status == "STORED" and len(storage.objects) == 1
    assert provider.calls.count("LINK") == 1 and provider.calls.count("DELETE") == 1


@pytest.mark.parametrize(
    "designation,role", [("HEAD_GUIDANCE_COUNSELOR", "COUNSELOR"), ("DPO", "INSTITUTIONAL_OFFICER")]
)
def test_unrelated_designated_staff_cannot_bypass_saved_relationship(designation, role):
    from compass.accounts.models import Designation, UserDesignation

    _, _, appointment, _, _, storage = ready_artifact(pending=False)
    other = make_user("designated@example.edu", role)
    UserDesignation.objects.create(
        user=other, designation=Designation.objects.get(code=designation)
    )
    for code in ("ecounseling.view_assigned", "ecounseling.access_media_assigned"):
        UserCapabilityOverride.objects.create(
            user=other,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic exception",
        )
    with (
        patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage),
        pytest.raises(ECounselingNotPermitted),
    ):
        access_artifact(
            counselor=other, appointment_id=appointment.pk, kind="RECORDING", context=context(other)
        )


def test_inactive_assigned_counselor_is_denied_access():
    _, counselor, appointment, _, _, storage = ready_artifact(pending=False)
    counselor.is_active = False
    counselor.save()
    with (
        patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage),
        pytest.raises(ECounselingNotPermitted),
    ):
        access_artifact(
            counselor=counselor,
            appointment_id=appointment.pk,
            kind="RECORDING",
            context=context(counselor),
        )


@pytest.mark.parametrize("failure", ["identity", "provider_shape", "link", "download"])
def test_unverified_provider_source_cannot_delete_the_only_copy(failure):
    _, _, _, capture, artifact, storage = ready_artifact()
    provider = ArtifactDaily(capture)
    if failure in ("identity", "provider_shape"):
        original = provider.get_recording
        provider.get_recording = lambda **kwargs: (
            {**original(**kwargs), "id": "wrong"}
            if failure == "identity"
            else {**original(**kwargs), "storage_provider": "oci"}
        )
    if failure == "link":
        provider.recording_access_link = lambda **kwargs: {
            "download_link": "https://127.0.0.1/private",
            "expires": int(time.time()) + 900,
        }

    @contextmanager
    def unavailable_download(*args, **kwargs):
        raise MediaDownloadError("sanitized")
        yield

    ingest_artifact(
        artifact.pk,
        storage=storage,
        client=provider,
        download=unavailable_download if failure == "download" else fake_download,
    )
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "FAILED" and capture.provider_artifact_id
    assert "DELETE" not in provider.calls and not storage.objects


@pytest.mark.parametrize("failure", ["oversize", "truncated", "mime", "signature"])
def test_stream_validation_rejects_unbounded_or_unverified_content(failure, settings):
    response = MagicMock()
    content = b"\x00\x00\x00\x18ftypisom" + b"0" * 12
    response.status = 200
    response.headers = {
        "Content-Type": "text/html" if failure == "mime" else "video/mp4",
        "Content-Length": "25" if failure == "truncated" else "24",
    }
    response.read.side_effect = [b"invalid" if failure == "signature" else content, b""]
    if failure == "oversize":
        settings.ECOUNSELING_MEDIA_MAX_BYTES = 1
    response.__enter__.return_value = response
    opener = MagicMock()
    opener.open.return_value = response
    with (
        patch("compass.integrations.media_download.build_opener", return_value=opener),
        pytest.raises(MediaDownloadError),
    ):
        with stream_daily_media("https://synthetic/?signed=never-log", kind="RECORDING"):
            pytest.fail("Unverified bytes must not reach storage")


def test_storage_namespace_change_blocks_access_and_disposition_of_original_copy():
    _, counselor, appointment, capture, artifact, storage = ready_artifact(pending=False)
    original_binding = artifact.storage_binding
    storage.namespace = "0" * 64
    with patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage):
        response = auth_client(counselor).get(
            f"/api/v1/e-counseling/appointments/{appointment.pk}/media/RECORDING/access"
        )
    assert response.status_code == 503 and response["Cache-Control"] == "no-store, private"
    dpo, case = v2_case(capture)
    retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=context(dpo)
    )
    with patch("compass.privacy_governance.media_disposition.ObjectStorage", return_value=storage):
        execute_disposition(case.pk)
    case.refresh_from_db()
    artifact.refresh_from_db()
    assert case.state == "RECONCILIATION_REQUIRED" and case.blocker == "OBJECT_STORAGE_UNVERIFIED"
    assert storage.objects and artifact.storage_binding == original_binding
    assert artifact.object_key and artifact.status == "STORED"


def test_ingestion_cannot_adopt_or_delete_using_a_different_storage_namespace():
    _, _, _, capture, artifact, storage = ready_artifact()
    provider = ArtifactDaily(capture)
    storage.fail_verify = True
    ingest_artifact(artifact.pk, storage=storage, client=provider, download=fake_download)
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.storage_binding == storage.namespace
    count = storage.calls.count("SAVE")
    storage.namespace = "0" * 64
    storage.fail_verify = False
    artifact.next_attempt_at = timezone.now()
    artifact.save()
    ingest_artifact(artifact.pk, storage=storage, client=provider, download=fake_download)
    capture.refresh_from_db()
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and capture.provider_artifact_id
    assert "DELETE" not in provider.calls and storage.calls.count("SAVE") == count


def test_missing_provider_locator_requires_verified_cleanup_evidence_before_disposition():
    _, _, _, capture, artifact, storage = ready_artifact(pending=False)
    assert capture.provider_artifact_id is None and artifact.provider_deleted_at is not None
    dpo, case = v2_case(capture)
    retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=context(dpo)
    )
    artifact.provider_deleted_at = None
    artifact.save()
    with patch("compass.privacy_governance.media_disposition.ObjectStorage", return_value=storage):
        execute_disposition(case.pk)
    case.refresh_from_db()
    artifact.refresh_from_db()
    assert case.state != "COMPLETED" and case.blocker == "PROVIDER_CLEANUP_UNVERIFIED"
    assert storage.objects and artifact.object_key and artifact.status == "STORED"
