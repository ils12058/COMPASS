"""EC-FIX-1: Daily contract corrections observed on live staging (2026-10-17).

Response shapes below follow the live structure; every value is synthetic. Fake-only: no Daily call,
no object storage, no media content.
"""

import hashlib
import time
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit
from urllib.request import Request

import pytest
from django.test import override_settings
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.ecounseling.artifacts import (
    access_artifact,
    daily_owned_transcript_storage,
    ingest_artifact,
)
from compass.ecounseling.media import (
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
    ECounselingProviderUnavailable,
)
from compass.integrations.daily import DailyHTTPError
from compass.integrations.media_download import (
    MediaDownloadError,
    NoRedirect,
    stream_daily_media,
    validate_daily_link,
)
from tests.test_ecounseling_media import context
from tests.test_ecounseling_media_v2 import (
    ArtifactDaily,
    approved_session,
    ready_artifact,
)

pytestmark = pytest.mark.django_db

DAILY_OUT_PARAMS = {
    "bucket": "daily-co-transcription",
    "key": "synthetic-domain/synthetic-transcript.vtt",
    "region": "us-west-2",
}
RECORDING_BYTES = b"\x00\x00\x00\x18ftypisom" + b"synthetic-recording" * 4
TRANSCRIPT_BYTES = b"WEBVTT\n\n00:00.000 --> 00:01.000\nsynthetic\n"


@pytest.fixture(autouse=True)
def fake_dispatch():
    with patch("compass.ecounseling.artifacts.enqueue_artifact"):
        yield


def signed(path="opaque"):
    return f"https://c.daily.co/{path}?Expires=1&Signature=synthetic&Key-Pair-Id=synthetic"


def recording_link(**overrides):
    payload = {
        "download_link": signed(),
        "expires": int(time.time()) + 899,
        "s3_bucket": "synthetic-bucket",
        "s3_key": "synthetic/key.mp4",
        "s3_region": "us-west-2",
        "data_outputs": {},
    }
    return {**payload, **overrides}


def transcript_link(artifact_id="synthetic-transcript", **overrides):
    payload = {
        "transcriptId": artifact_id,
        "link": signed("opaque.vtt"),
        "outParams": DAILY_OUT_PARAMS,
        "status": "t_finished",
        "isVttAvailable": True,
    }
    return {**payload, **overrides}


class ObservedDaily(ArtifactDaily):
    """The live response structure: c.daily.co links and Daily-owned transcript outParams."""

    def __init__(self, capture, *, out_params=DAILY_OUT_PARAMS, deleted_out_params=None, **kwargs):
        super().__init__(capture, **kwargs)
        self.out_params = out_params
        self.deleted_out_params = out_params if deleted_out_params is None else deleted_out_params
        self.status_at_delete = None

    def get_recording(self, *, artifact_id):
        item = super().get_recording(artifact_id=artifact_id)
        item.update(
            mtgSessionId="synthetic-session",
            s3key="synthetic/key",
            share_token="synthetic",
            start_ts=int(time.time()) - 60,
            duration=60,
            max_participants=2,
            tracks=[],
            data_outputs=[],
        )
        return item

    def get_transcript(self, *, artifact_id):
        item = super().get_transcript(artifact_id=artifact_id)
        item.update(
            outParams=self.out_params,
            mtgSessionId="synthetic-session",
            domainId="synthetic-domain",
            roomName=self.capture.room.daily_room_name,
            duration=53,
            participantMinutes=2,
            created_at="2026-10-17T09:10:43.000Z",
            updated_at="2026-10-17T09:11:37.000Z",
        )
        return item

    def recording_access_link(self, *, artifact_id):
        self.calls.append("LINK")
        return recording_link()

    def transcript_access_link(self, *, artifact_id):
        self.calls.append("LINK")
        return transcript_link(artifact_id, outParams=self.out_params)

    def _custody_at_delete(self):
        self.status_at_delete = ECounselingMediaArtifact.objects.get(capture=self.capture).status

    def delete_recording(self, *, artifact_id):
        self._custody_at_delete()
        return super().delete_recording(artifact_id=artifact_id)

    def delete_transcript(self, *, artifact_id):
        self._custody_at_delete()
        result = super().delete_transcript(artifact_id=artifact_id)
        result["outParams"] = self.deleted_out_params
        return result


def provider_transfer(kind):
    """The real bounded downloader, reading a synthetic c.daily.co response."""
    content = TRANSCRIPT_BYTES if kind == "TRANSCRIPTION" else RECORDING_BYTES
    response = MagicMock()
    response.status = 200
    response.headers = {
        "Content-Type": "text/vtt" if kind == "TRANSCRIPTION" else "video/mp4",
        "Content-Length": str(len(content)),
    }
    response.read.side_effect = [content, b""]
    response.__enter__.return_value = response
    requests = []
    opener = MagicMock()

    def open_request(request, timeout):
        requests.append((request, timeout))
        return response

    opener.open.side_effect = open_request
    return opener, requests, content


# F1: recording Stop targets the started instance.


def started_recording():
    student, counselor, appointment, client = approved_session()
    with override_settings(DAILY_ENABLED=True):
        capture = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
    started = process_media_webhook_event(
        event_type="recording.started",
        event_id="ec-fix-rec-start",
        event_ts=timezone.now().timestamp(),
        payload={
            "recording_id": "synthetic-recording",
            "instance_id": capture.provider_instance_id,
            "start_ts": int(timezone.now().timestamp()),
        },
    )
    assert started.accepted
    capture.refresh_from_db()
    assert capture.status == "ACTIVE" and capture.provider_binding_verified_at
    return student, counselor, appointment, client, capture


def stop_recording_as(counselor, appointment, client):
    with override_settings(DAILY_ENABLED=True):
        return stop_media_capture(
            counselor=counselor,
            appointment_id=appointment.pk,
            kind="RECORDING",
            context=context(counselor),
            daily_client=client,
        )


def test_recording_stop_targets_started_instance_and_only_completion_makes_it_ready():
    _, counselor, appointment, client, capture = started_recording()
    stop_recording_as(counselor, appointment, client)

    assert client.recording_stops == [(capture.room.daily_room_name, capture.provider_instance_id)]
    assert client.recording_starts == client.recording_stops
    capture.refresh_from_db()
    # The provider acknowledgment is a command receipt, never completion evidence.
    assert capture.status == "STOP_REQUESTED" and capture.stop_requested_at
    assert capture.ready_at is None and capture.ended_at is None and capture.error_code is None
    assert not ECounselingMediaArtifact.objects.exists()

    ready = process_media_webhook_event(
        event_type="recording.ready-to-download",
        event_id="ec-fix-rec-ready",
        event_ts=timezone.now().timestamp(),
        payload={
            "recording_id": "synthetic-recording",
            "room_name": capture.room.daily_room_name,
            "start_ts": int(timezone.now().timestamp()) - 60,
            "duration": 60,
        },
    )
    assert ready.accepted
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.ready_at
    assert ECounselingMediaArtifact.objects.get(capture=capture).status == "PENDING"


def test_recording_stop_without_a_persisted_instance_fails_closed_without_a_provider_call():
    _, counselor, appointment, client, capture = started_recording()
    ECounselingMediaCapture.objects.filter(pk=capture.pk).update(provider_instance_id=None)

    with pytest.raises(ECounselingInvalidProviderResponse):
        stop_recording_as(counselor, appointment, client)

    assert client.recording_stops == []
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED"
    assert capture.error_code == "STOP_PROVIDER_INVALID_RESPONSE"
    assert capture.ready_at is None


def test_rejected_recording_stop_keeps_intent_is_not_repeated_and_retry_targets_same_instance():
    _, counselor, appointment, client, capture = started_recording()
    sent = []
    original = client.stop_recording

    def reject(**kwargs):
        sent.append(kwargs)
        raise DailyHTTPError(400)

    client.stop_recording = reject
    with pytest.raises(ECounselingProviderUnavailable):
        stop_recording_as(counselor, appointment, client)
    capture.refresh_from_db()
    assert sent == [
        {"room_name": capture.room.daily_room_name, "instance_id": capture.provider_instance_id}
    ]
    assert capture.status == "STOP_REQUESTED"
    assert capture.error_code == "STOP_PROVIDER_INVALID_REQUEST"
    assert capture.ready_at is None and capture.ended_at is None

    client.stop_recording = original
    stop_recording_as(counselor, appointment, client)
    assert client.recording_stops == [(capture.room.daily_room_name, capture.provider_instance_id)]
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and capture.ready_at is None


def test_withdrawal_stops_recording_with_its_instance_and_transcription_stop_is_unchanged():
    student, counselor, appointment, client = approved_session(storage=True)
    with override_settings(DAILY_ENABLED=True):
        recording = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
        transcription = start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=client,
        )
        consent = ECounselingConsent.objects.get(scope="SESSION_MEDIA_CAPTURE")
        withdraw_my_consent(
            student=student,
            appointment_id=appointment.pk,
            consent_id=consent.pk,
            context=context(student),
            daily_client=client,
        )
    room_name = recording.room.daily_room_name
    assert client.recording_stops == [(room_name, recording.provider_instance_id)]
    assert client.transcription_stops == [(room_name, transcription.provider_instance_id)]
    assert recording.provider_instance_id != transcription.provider_instance_id
    for capture in (recording, transcription):
        capture.refresh_from_db()
        assert capture.status == "STOP_REQUESTED" and capture.ready_at is None


# F2: the observed signed-link host, and nothing broader.


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("RECORDING", recording_link()),
        ("TRANSCRIPTION", transcript_link()),
        ("RECORDING", recording_link(download_link=signed().replace("c.daily.co", "C.DAILY.CO"))),
    ],
    ids=["recording", "transcript", "host-case"],
)
def test_observed_daily_signed_links_are_accepted(kind, payload):
    url = validate_daily_link(payload, kind=kind, artifact_id="synthetic-transcript")
    assert urlsplit(url).hostname == "c.daily.co"


@pytest.mark.parametrize(
    "url",
    [
        "http://c.daily.co/opaque?Signature=synthetic",
        "https://c.daily.co.evil.test/opaque",
        "https://evil.c.daily.co/opaque",
        "https://c.daily.co./opaque",
        "https://b.daily.co/opaque",
        "https://daily.co/opaque",
        "https://api.daily.co/v1/opaque",
        "https://cdaily.co/opaque",
        "https://user:secret@c.daily.co/opaque",
        "https://c.daily.co:8443/opaque",
        "https://c.daily.co/opaque#fragment",
        "https://c.daily.co:not-a-port/opaque",
    ],
)
@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_signed_link_host_trust_is_exact(url, kind):
    payload = (
        recording_link(download_link=url) if kind == "RECORDING" else transcript_link(link=url)
    )
    with pytest.raises(MediaDownloadError):
        validate_daily_link(payload, kind=kind, artifact_id="synthetic-transcript")


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("RECORDING", recording_link(expires=int(time.time()) - 1)),
        ("RECORDING", recording_link(expires=str(int(time.time()) + 900))),
        ("RECORDING", {k: v for k, v in recording_link().items() if k != "expires"}),
        ("RECORDING", recording_link(link=signed("other"))),
        ("RECORDING", recording_link(download_link=None)),
        ("TRANSCRIPTION", transcript_link(transcriptId="another-transcript")),
        ("TRANSCRIPTION", transcript_link(download_link=signed("conflict"))),
        ("TRANSCRIPTION", {k: v for k, v in transcript_link().items() if k != "link"}),
        ("TRANSCRIPTION", ["not", "a", "mapping"]),
    ],
    ids=[
        "expired",
        "expires-not-int",
        "expires-missing",
        "conflicting-fields",
        "non-string-link",
        "transcript-identity",
        "transcript-conflict",
        "missing-link",
        "invalid-shape",
    ],
)
def test_signed_link_metadata_still_fails_closed(kind, payload):
    with pytest.raises(MediaDownloadError):
        validate_daily_link(payload, kind=kind, artifact_id="synthetic-transcript")


def test_signed_link_redirects_are_never_followed():
    with pytest.raises(MediaDownloadError):
        NoRedirect().redirect_request(
            Request(signed()), None, 302, "Found", {}, "https://elsewhere.test/opaque"
        )
    opener = MagicMock()
    opener.open.side_effect = MediaDownloadError("Provider media redirects are unsupported.")
    with (
        patch("compass.integrations.media_download.build_opener", return_value=opener) as build,
        pytest.raises(MediaDownloadError),
        stream_daily_media(signed(), kind="RECORDING"),
    ):
        pytest.fail("A redirected download must not yield media.")
    assert isinstance(build.call_args.args[0], NoRedirect)


# F3: Daily-owned transcript storage, distinct from customer-managed storage.


@pytest.mark.parametrize(
    "out_params,owned",
    [
        (None, True),
        ({}, True),
        (DAILY_OUT_PARAMS, True),
        ({**DAILY_OUT_PARAMS, "storage_provider": "aws"}, True),
        ({**DAILY_OUT_PARAMS, "storage_provider": "oci"}, False),
        ({**DAILY_OUT_PARAMS, "bucket": "institution-transcripts"}, False),
        ({**DAILY_OUT_PARAMS, "bucket": "daily-co-transcription-copy"}, False),
        ({**DAILY_OUT_PARAMS, "bucket": "daily-meeting-transcripts"}, False),
        ({**DAILY_OUT_PARAMS, "bucket": ["daily-co-transcription"]}, False),
        ({"key": "synthetic", "region": "us-west-2"}, False),
        ("daily-co-transcription", False),
        (["daily-co-transcription"], False),
    ],
)
def test_daily_owned_transcript_storage_is_an_exact_allowlist(out_params, owned):
    assert daily_owned_transcript_storage(out_params) is owned


# End to end through the existing pipeline: metadata, link, bounded transfer, custody, cleanup.


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_observed_daily_media_reaches_verified_custody_then_cleanup_then_authorized_access(kind):
    _, counselor, appointment, capture, artifact, storage = ready_artifact(kind)
    if kind == "TRANSCRIPTION":
        capture.provider_session_id = "synthetic-session"
        capture.save(update_fields=["provider_session_id", "updated_at"])
    client = ObservedDaily(capture)
    opener, requests, content = provider_transfer(kind)

    with patch("compass.integrations.media_download.build_opener", return_value=opener):
        ingest_artifact(artifact.pk, storage=storage, client=client)

    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "STORED" and artifact.error_code is None
    assert artifact.content_type == ("text/vtt" if kind == "TRANSCRIPTION" else "video/mp4")
    assert artifact.size == len(content)
    assert artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert storage.objects[artifact.object_key] == content
    assert storage.calls.index("POLICY") < storage.calls.index("SAVE")
    assert storage.calls.index("SAVE") < storage.calls.index("VERIFY")
    # Exactly one bounded server-side request to the observed host, with no credential forwarding.
    [(request, timeout)] = requests
    assert urlsplit(request.full_url).hostname == "c.daily.co" and timeout == 30
    assert "Authorization" not in request.headers
    # Provider cleanup only after verified, committed custody.
    assert client.calls == ["GET", "LINK", "GET", "DELETE"]
    assert client.status_at_delete == "STORED"
    assert artifact.provider_deleted_at and capture.provider_artifact_id is None
    actions = set(
        AuditEvent.objects.filter(target_id=str(artifact.pk)).values_list("action", flat=True)
    )
    assert {
        "ecounseling.media_artifact.stored",
        "ecounseling.media_artifact.provider_cleaned",
    } <= actions

    key = "recording" if kind == "RECORDING" else "transcription"
    assert get_media_projection(capture.room)[key]["artifact_available"]
    with patch("compass.ecounseling.artifacts.ObjectStorage", return_value=storage):
        access = access_artifact(
            counselor=counselor,
            appointment_id=appointment.pk,
            kind=kind,
            context=context(counselor),
        )
    assert access["url"].startswith("https://private.example.test/")
    metadata = str(list(AuditEvent.objects.values_list("metadata", flat=True)))
    assert "c.daily.co" not in metadata and "Signature" not in metadata


@pytest.mark.parametrize(
    "out_params",
    [
        {**DAILY_OUT_PARAMS, "bucket": "institution-transcripts"},
        {**DAILY_OUT_PARAMS, "storage_provider": "oci"},
        "daily-co-transcription",
    ],
    ids=["customer-bucket", "unsupported-provider", "invalid-shape"],
)
def test_customer_managed_transcript_storage_is_never_taken_into_custody(out_params):
    _, _, _, capture, artifact, storage = ready_artifact("TRANSCRIPTION")
    client = ObservedDaily(capture, out_params=out_params)
    with patch("compass.integrations.media_download.build_opener") as build:
        ingest_artifact(artifact.pk, storage=storage, client=client)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.error_code == "PROVIDER_IDENTITY_UNVERIFIED"
    assert client.calls == ["GET"] and not build.called
    assert "SAVE" not in storage.calls and capture.provider_artifact_id


@pytest.mark.parametrize("mismatch", ["transcriptId", "mtgSessionId", "roomId"])
def test_daily_owned_storage_does_not_relax_transcript_identity(mismatch, monkeypatch):
    _, _, _, capture, artifact, storage = ready_artifact("TRANSCRIPTION")
    capture.provider_session_id = "synthetic-session"
    capture.save(update_fields=["provider_session_id", "updated_at"])
    client = ObservedDaily(capture)
    original = client.get_transcript

    def metadata(**kwargs):
        item = original(**kwargs)
        item[mismatch] = "synthetic-other"
        return item

    monkeypatch.setattr(client, "get_transcript", metadata)
    ingest_artifact(artifact.pk, storage=storage, client=client)
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.error_code == "PROVIDER_IDENTITY_UNVERIFIED"
    assert "LINK" not in client.calls and "SAVE" not in storage.calls


def test_unavailable_transcript_vtt_still_fails_with_daily_owned_storage(monkeypatch):
    _, _, _, capture, artifact, storage = ready_artifact("TRANSCRIPTION")
    client = ObservedDaily(capture)
    original = client.get_transcript
    monkeypatch.setattr(
        client, "get_transcript", lambda **kwargs: {**original(**kwargs), "isVttAvailable": False}
    )
    ingest_artifact(artifact.pk, storage=storage, client=client)
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.error_code == "PROVIDER_IDENTITY_UNVERIFIED"


@pytest.mark.parametrize(
    "deleted_out_params,cleaned",
    [
        (DAILY_OUT_PARAMS, True),
        ({}, True),
        ({**DAILY_OUT_PARAMS, "bucket": "institution-transcripts"}, False),
    ],
    ids=["daily-owned", "empty", "customer-bucket"],
)
def test_transcript_cleanup_verification_uses_the_same_custody_classification(
    deleted_out_params, cleaned
):
    _, _, _, capture, artifact, storage = ready_artifact("TRANSCRIPTION")
    client = ObservedDaily(capture, deleted_out_params=deleted_out_params)
    opener, _, _ = provider_transfer("TRANSCRIPTION")
    with patch("compass.integrations.media_download.build_opener", return_value=opener):
        ingest_artifact(artifact.pk, storage=storage, client=client)
    artifact.refresh_from_db()
    capture.refresh_from_db()
    # Custody is committed either way; only verified provider deletion releases the provider copy.
    assert artifact.status == "STORED"
    assert bool(artifact.provider_deleted_at) is cleaned
    assert (capture.provider_artifact_id is None) is cleaned
    assert artifact.error_code == (None if cleaned else "PROVIDER_CLEANUP_UNVERIFIED")


def test_lookalike_recording_link_never_downloads():
    _, _, _, capture, artifact, storage = ready_artifact("RECORDING")
    client = ObservedDaily(capture)
    client.recording_access_link = lambda **_: recording_link(
        download_link="https://c.daily.co.evil.test/opaque?Signature=synthetic"
    )
    with patch("compass.integrations.media_download.build_opener") as build:
        ingest_artifact(artifact.pk, storage=storage, client=client)
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.error_code == "ACCESS_LINK_UNVERIFIED"
    assert not build.called and "SAVE" not in storage.calls


def test_failed_live_artifacts_recover_on_their_existing_schedule_without_data_repair():
    _, _, _, capture, artifact, storage = ready_artifact("RECORDING")
    # The live failure: the old allowlist rejected the observed host and scheduled a retry.
    with patch("compass.ecounseling.artifacts.validate_daily_link") as legacy:
        legacy.side_effect = MediaDownloadError("Provider media storage is unsupported.")
        ingest_artifact(artifact.pk, storage=storage, client=ObservedDaily(capture))
    artifact.refresh_from_db()
    assert artifact.status == "FAILED" and artifact.error_code == "ACCESS_LINK_UNVERIFIED"
    assert artifact.next_attempt_at > timezone.now()

    # Once due, the same row is retried as-is and completes.
    ECounselingMediaArtifact.objects.filter(pk=artifact.pk).update(next_attempt_at=timezone.now())
    opener, _, _ = provider_transfer("RECORDING")
    with patch("compass.integrations.media_download.build_opener", return_value=opener):
        ingest_artifact(artifact.pk, storage=storage, client=ObservedDaily(capture))
    artifact.refresh_from_db()
    assert artifact.status == "STORED" and artifact.provider_deleted_at and artifact.attempts == 2
