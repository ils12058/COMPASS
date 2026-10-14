"""RT-1B: committed public transitions, current authority and real socket/HTTP proof."""

import asyncio
import json
from threading import Barrier, Event, Thread
from uuid import uuid4

import pytest
import redis
from django.db import connection, connections, transaction
from django.utils import timezone

from compass.accounts.models import Capability, Role, UserCapabilityOverride
from compass.ecounseling import artifacts, media, media_realtime
from compass.ecounseling.models import (
    DailyWebhookReceipt,
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
)
from compass.ecounseling.reconciliation import (
    apply_observation,
    claim_capture,
    discover_captures,
    observe_metadata,
)
from compass.ecounseling.services import ECounselingProviderUnavailable, create_join_credential
from compass.integrations.daily import DailyHTTPError, DailyTimeout
from compass.notifications import services as notifications
from compass.privacy_governance import retention
from compass.privacy_governance.tasks import execute_disposition
from compass.realtime import connection as realtime_connection
from compass.realtime import publish
from realtime_service import protocol
from tests.test_ecounseling_media import FakeMediaDailyClient, context, make_user, setup_session
from tests.test_ecounseling_media_v2 import (
    ArtifactDaily,
    FakeStorage,
    fake_download,
    ready_artifact,
    v2_case,
)
from tests.test_ecounseling_reconciliation import metadata, pending_capture
from tests.test_ecounseling_state_correctness import authorized_session
from tests.test_ecounseling_webhook_security import body_for, signed
from tests.test_notifications import auth_client
from tests.test_operational_retention import (
    CapturingDispositionDaily,
    active_rule,
    approve,
    discovered_case,
    media_source,
)
from tests.test_privacy_governance import make_dpo
from tests.test_realtime_service import Socket, run
from tests.test_realtime_tickets import issue

pytestmark = pytest.mark.django_db(transaction=True)
EVENT = "ecounseling.media.changed"
ORIGINAL_PUBLISH = publish._publish


@pytest.fixture(autouse=True)
def synthetic_boundaries(settings, monkeypatch):
    settings.REALTIME_ENABLED = settings.DAILY_ENABLED = True
    settings.ECOUNSELING_CAPTURE_RECONCILIATION_ENABLED = True
    monkeypatch.setattr(notifications, "_safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr(notifications, "_safe_kick_push_delivery", lambda _: None)
    monkeypatch.setattr(artifacts, "enqueue_artifact", lambda _: None)
    monkeypatch.setattr(retention, "enqueue", lambda _: None)

    def forbidden(*args, **kwargs):
        pytest.fail("Only synthetic provider/storage boundaries are permitted", pytrace=False)

    monkeypatch.setattr("compass.integrations.daily.DailyClient.from_settings", forbidden)
    monkeypatch.setattr("compass.integrations.daily.urlopen", forbidden)
    monkeypatch.setattr(artifacts, "ObjectStorage", forbidden)
    monkeypatch.setattr(artifacts, "stream_daily_media", forbidden)


@pytest.fixture
def frames(monkeypatch):
    observed = []

    def send(channel, frame):
        assert not connection.in_atomic_block, "Redis IO must follow the SQL commit"
        observed.append((channel, json.loads(frame)))
        return True

    monkeypatch.setattr(publish, "_publish", send)
    return observed


def media_frames(frames):
    return [(channel, frame) for channel, frame in frames if frame["type"] == EVENT]


def assert_hints(frames, appointment, participants, *, transitions=1):
    hints = media_frames(frames)
    assert len(hints) == len(participants) * transitions
    for participant in participants:
        assert (
            sum(channel == protocol.user_channel(participant.pk) for channel, _ in hints)
            == transitions
        )
    assert all(
        frame == {"v": 1, "type": EVENT, "appointment_id": str(appointment.pk)}
        for _, frame in hints
    )


def start(kind, counselor, appointment, client, *, storage=False):
    kwargs = dict(
        counselor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    return (
        media.start_recording(**kwargs)
        if kind == "RECORDING"
        else media.start_transcription(**kwargs, store_transcript=storage)
    )


def claim(capture):
    discover_captures(limit=10)
    return claim_capture(capture.pk)


class BoundArtifactDaily(ArtifactDaily):
    def get_recording(self, **kwargs):
        return {**super().get_recording(**kwargs), "mtgSessionId": self.capture.provider_session_id}

    def get_transcript(self, **kwargs):
        return {
            **super().get_transcript(**kwargs),
            "mtgSessionId": self.capture.provider_session_id,
        }


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_start_intent_is_durable_before_provider_and_ack_does_not_mean_active(frames, kind):
    student, counselor, appointment, client = authorized_session(kind=kind)
    frames.clear()
    original = client.update_room

    def update(**kwargs):
        assert (
            ECounselingMediaCapture.objects.get(room__appointment=appointment, kind=kind).status
            == "START_REQUESTED"
        )
        assert_hints(frames, appointment, [student, counselor])
        return original(**kwargs)

    client.update_room = update
    capture = start(kind, counselor, appointment, client)
    assert capture.status == "START_REQUESTED" and capture.started_at is None
    assert_hints(frames, appointment, [student, counselor])


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("known", [False, True])
def test_start_failure_publishes_only_a_changed_public_status(frames, kind, known):
    student, counselor, appointment, client = authorized_session(kind=kind)
    frames.clear()

    def fail(**kwargs):
        raise DailyHTTPError(403) if known else DailyTimeout("synthetic uncertainty")

    client.update_room = fail
    with pytest.raises(ECounselingProviderUnavailable):
        start(kind, counselor, appointment, client)
    capture = ECounselingMediaCapture.objects.get(room__appointment=appointment, kind=kind)
    assert capture.status == ("ERROR" if known else "START_REQUESTED")
    assert_hints(frames, appointment, [student, counselor], transitions=2 if known else 1)


def test_transcription_storage_configuration_and_cleanup_are_separate_visible_commits(frames):
    student, counselor, appointment, client = authorized_session(storage=True)
    frames.clear()
    capture = start("TRANSCRIPTION", counselor, appointment, client, storage=True)
    assert capture.transcript_storage_enabled and capture.status == "START_REQUESTED"
    assert_hints(frames, appointment, [student, counselor], transitions=2)
    consent = ECounselingConsent.objects.get(room=capture.room, scope="TRANSCRIPT_STORAGE")
    frames.clear()
    media.withdraw_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=consent.pk,
        context=context(student),
        daily_client=client,
    )
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and not capture.transcript_storage_enabled
    assert_hints(frames, appointment, [student, counselor], transitions=2)


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("failure", [False, True])
def test_stop_intent_survives_failure_and_repeated_stop_does_not_publish(frames, kind, failure):
    student, counselor, appointment, _, capture = pending_capture(
        kind=kind, state="ACTIVE", stop_intent=False
    )
    frames.clear()
    client = FakeMediaDailyClient(fail_stop=failure)
    kwargs = dict(
        counselor=counselor,
        appointment_id=appointment.pk,
        kind=kind,
        context=context(counselor),
        daily_client=client,
    )
    if failure:
        with pytest.raises(ECounselingProviderUnavailable):
            media.stop_media_capture(**kwargs)
    else:
        media.stop_media_capture(**kwargs)
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and capture.ended_at is None
    assert_hints(frames, appointment, [student, counselor])
    frames.clear()
    if failure:
        with pytest.raises(ECounselingProviderUnavailable):
            media.stop_media_capture(**kwargs)
    else:
        media.stop_media_capture(**kwargs)
    assert media_frames(frames) == []


def test_combined_withdrawal_publishes_one_media_transition_before_failed_mitigation(frames):
    student, counselor, appointment, client = authorized_session()
    recording = start("RECORDING", counselor, appointment, client)
    start("TRANSCRIPTION", counselor, appointment, client)
    consent = ECounselingConsent.objects.get(room=recording.room, scope="SESSION_MEDIA_CAPTURE")
    frames.clear()

    def failed_stop(**kwargs):
        consent.refresh_from_db()
        assert consent.withdrawn_at
        assert_hints(frames, appointment, [student, counselor])
        assert sum(frame["type"] == "ecounseling.consent.changed" for _, frame in frames) == 2
        raise DailyTimeout("synthetic Stop uncertainty")

    client.stop_recording = failed_stop
    with pytest.raises(ECounselingProviderUnavailable):
        media.withdraw_my_consent(
            student=student,
            appointment_id=appointment.pk,
            consent_id=consent.pk,
            context=context(student),
            daily_client=client,
        )
    assert set(
        ECounselingMediaCapture.objects.filter(room=recording.room).values_list("status", flat=True)
    ) == {"STOP_REQUESTED"}
    assert_hints(frames, appointment, [student, counselor])


@pytest.mark.parametrize("nested", [False, True])
def test_outer_and_savepoint_rollback_discard_publication(frames, nested):
    student, counselor, appointment, _, capture = pending_capture(state="ACTIVE", stop_intent=False)
    frames.clear()
    with transaction.atomic():
        try:
            with transaction.atomic():
                media.stop_media_capture(
                    counselor=counselor,
                    appointment_id=appointment.pk,
                    kind=capture.kind,
                    context=context(counselor),
                    daily_client=FakeMediaDailyClient(),
                )
                assert frames == []
                raise ValueError("rollback")
        except ValueError:
            if not nested:
                transaction.set_rollback(True)
    capture.refresh_from_db()
    assert capture.status == "ACTIVE" and media_frames(frames) == []


@pytest.mark.parametrize("participant", ["student", "counselor"])
@pytest.mark.parametrize("loss", ["inactive", "role", "view"])
def test_current_workspace_authority_is_checked_after_commit(frames, participant, loss):
    student, counselor, appointment, _ = authorized_session()
    actor = student if participant == "student" else counselor
    frames.clear()
    with transaction.atomic():
        media_realtime.media_changed_on_commit(appointment.pk)
        if loss == "inactive":
            actor.is_active = False
            actor.save(update_fields=["is_active"])
        elif loss == "role":
            actor.role = Role.objects.get(code="IT_ADMIN")
            actor.save(update_fields=["role"])
        else:
            UserCapabilityOverride.objects.create(
                user=actor,
                capability=Capability.objects.get(
                    code="ecounseling.view_self"
                    if participant == "student"
                    else "ecounseling.view_assigned"
                ),
                effect="REVOKE",
                reason="Synthetic",
            )
        assert frames == []
    assert_hints(frames, appointment, [counselor if participant == "student" else student])


def test_media_viewers_do_not_need_consent_management_or_download_capabilities(frames):
    student, counselor, appointment, _ = authorized_session()
    for actor, code in [
        (student, "ecounseling.consent_self"),
        (counselor, "ecounseling.manage_media_assigned"),
        (counselor, "ecounseling.access_media_assigned"),
    ]:
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code=code),
            effect="REVOKE",
            reason="Synthetic",
        )
    frames.clear()
    media_realtime.media_changed_on_commit(appointment.pk)
    assert_hints(frames, appointment, [student, counselor])
    for actor, path in [(student, "me/appointments"), (counselor, "appointments")]:
        assert (
            auth_client(actor).get(f"/api/v1/e-counseling/{path}/{appointment.pk}").status_code
            == 200
        )


@pytest.mark.parametrize("role", ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN"])
def test_unrelated_or_designated_accounts_never_receive_the_hint(frames, role):
    student, counselor, appointment, _ = authorized_session()
    other = make_user(f"unrelated-{role}@example.edu", role)
    for code in ["ecounseling.view_self", "ecounseling.view_assigned"]:
        UserCapabilityOverride.objects.create(
            user=other,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic",
        )
    frames.clear()
    media_realtime.media_changed_on_commit(appointment.pk)
    assert_hints(frames, appointment, [student, counselor])


@pytest.mark.parametrize("during_first_publish", [False, True])
def test_reassignment_resolves_current_provider_before_each_publication(
    frames, monkeypatch, during_first_publish
):
    student, _, appointment, _ = authorized_session()
    replacement = make_user("new-provider@example.edu", "COUNSELOR")
    frames.clear()
    original = media_realtime.publish_to_user_on_commit

    def send(user_id, event_type, fields):
        original(user_id, event_type, fields)
        if user_id == student.pk:
            type(appointment).objects.filter(pk=appointment.pk).update(provider=replacement)

    if during_first_publish:
        monkeypatch.setattr(media_realtime, "publish_to_user_on_commit", send)
    with transaction.atomic():
        media_realtime.media_changed_on_commit(appointment.pk)
        if not during_first_publish:
            type(appointment).objects.filter(pk=appointment.pk).update(provider=replacement)
    assert_hints(frames, appointment, [student, replacement])


@pytest.mark.parametrize("transport", ["disabled", "redis-refused", "resolver-error"])
def test_transport_and_lookup_failures_never_undo_capture_intent(
    frames, settings, monkeypatch, caplog, transport
):
    student, counselor, appointment, client = authorized_session()
    frames.clear()
    if transport == "disabled":
        settings.REALTIME_ENABLED = False
    elif transport == "redis-refused":
        refused = redis.Redis(
            host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1
        )
        monkeypatch.setattr(publish, "_publish", ORIGINAL_PUBLISH)
        monkeypatch.setattr(publish, "realtime_redis", lambda: refused)
    else:

        def fail(*args, **kwargs):
            raise RuntimeError("PRIVATE_PROVIDER_LOCATION")

        monkeypatch.setattr(media_realtime, "workspace_participant_id", fail)
    capture = start("RECORDING", counselor, appointment, client)
    assert capture.status == "START_REQUESTED" and media_frames(frames) == []
    assert "PRIVATE_PROVIDER_LOCATION" not in caplog.text


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("phase", ["started", "ready-to-download", "error"])
def test_verified_signed_webhook_publishes_only_a_changed_projection(frames, kind, phase):
    student, counselor, appointment, _, capture = pending_capture(
        kind=kind,
        state="START_REQUESTED",
        bound=phase != "started",
        storage=kind == "TRANSCRIPTION",
        stop_intent=False,
    )
    frames.clear()
    event = body_for(capture, phase)
    signed(event)
    capture.refresh_from_db()
    assert (
        capture.status
        == {"started": "ACTIVE", "ready-to-download": "READY", "error": "ERROR"}[phase]
    )
    assert_hints(frames, appointment, [student, counselor])
    frames.clear()
    assert signed(event).duplicate
    assert media_frames(frames) == []
    signed(body_for(capture, phase))
    assert media_frames(frames) == [], (
        "New receipt ID with unchanged public state is bookkeeping only"
    )


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    "invalid", ["room", "instance", "session", "artifact", "malformed", "quarantined", "disposed"]
)
def test_untrusted_or_protected_webhook_never_publishes(frames, kind, invalid):
    _, _, _, _, capture = pending_capture(
        kind=kind, state="START_REQUESTED", storage=kind == "TRANSCRIPTION", stop_intent=False
    )
    event = body_for(capture)
    if invalid == "room":
        event["payload"]["room_name"] = "foreign-room"
    elif invalid == "instance":
        if kind == "RECORDING":
            event["payload"]["instance_id"] = "foreign-instance"
        else:
            event["payload"]["info"]["instanceId"] = "foreign-instance"
    elif invalid == "session":
        event["payload"]["mtg_session_id"] = "foreign-session"
    elif invalid == "artifact":
        event["payload"]["recording_id" if kind == "RECORDING" else "id"] = "foreign-artifact"
    elif invalid == "malformed":
        event["payload"] = {"raw": "untrusted"}
    else:
        setattr(
            capture,
            "provider_binding_quarantined_at"
            if invalid == "quarantined"
            else "artifact_disposed_at",
            timezone.now(),
        )
        capture.save()
    frames.clear()
    assert signed(event).accepted
    assert media_frames(frames) == []


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_early_completion_replay_publishes_active_then_ready_once(frames, kind):
    student, counselor, appointment, _, capture = pending_capture(
        kind=kind,
        state="START_REQUESTED",
        bound=False,
        storage=kind == "TRANSCRIPTION",
        stop_intent=False,
    )
    frames.clear()
    early = body_for(capture, "ready-to-download", artifact_id="early-artifact")
    signed(early)
    assert media_frames(frames) == []
    signed(body_for(capture, artifact_id="early-artifact"))
    capture.refresh_from_db()
    assert (
        capture.status == "READY"
        and DailyWebhookReceipt.objects.get(provider_event_id=early["id"]).applied_at
    )
    assert_hints(frames, appointment, [student, counselor], transitions=2)
    frames.clear()
    signed(early)
    assert media_frames(frames) == []


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("active", [False, True])
def test_reconciliation_publishes_changed_capture_and_artifact_not_claim_metadata(
    frames, kind, active
):
    student, counselor, appointment, _, capture = pending_capture(
        kind=kind,
        state="START_REQUESTED" if active else "STOP_REQUESTED",
        storage=kind == "TRANSCRIPTION",
        stop_intent=not active,
    )
    frames.clear()
    claimed = claim(capture)
    assert claimed and media_frames(frames) == []
    observation = observe_metadata(claimed, metadata(capture, active=active))
    apply_observation(claimed, observation)
    capture.refresh_from_db()
    assert capture.status == ("ACTIVE" if active else "READY")
    assert_hints(frames, appointment, [student, counselor])
    frames.clear()
    apply_observation(claimed, observation)
    assert media_frames(frames) == []


def test_uncertain_metadata_and_retry_bookkeeping_do_not_publish(frames):
    *_, capture = pending_capture()
    frames.clear()
    claimed = claim(capture)
    apply_observation(claimed, observe_metadata(claimed, {}))
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and media_frames(frames) == []


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize("failure", [None, "integrity", "cleanup"])
def test_custody_hints_follow_verified_public_stages_and_ignore_cleanup_bookkeeping(
    frames, kind, failure
):
    student, counselor, appointment, capture, artifact, storage = ready_artifact(kind)
    assert_hints(frames, appointment, [student, counselor])
    frames.clear()
    storage.fail_verify = failure == "integrity"
    artifacts.ingest_artifact(
        artifact.pk,
        storage=storage,
        client=BoundArtifactDaily(capture, fail_delete=failure == "cleanup"),
        download=fake_download,
    )
    artifact.refresh_from_db()
    assert artifact.status == ("FAILED" if failure == "integrity" else "STORED")
    assert_hints(frames, appointment, [student, counselor], transitions=2)
    assert media.get_media_projection(capture.room)[kind.lower()]["artifact_available"] == (
        failure != "integrity"
    )
    frames.clear()
    if failure:
        ECounselingMediaArtifact.objects.filter(pk=artifact.pk).update(
            next_attempt_at=timezone.now()
        )
        storage.fail_verify = False
    artifacts.ingest_artifact(
        artifact.pk, storage=storage, client=BoundArtifactDaily(capture), download=fake_download
    )
    if failure == "integrity":
        assert_hints(frames, appointment, [student, counselor], transitions=2)
    else:
        assert media_frames(frames) == []


@pytest.mark.parametrize("outcome", ["success", "hold", "storage-failure"])
def test_disposition_publishes_only_verified_final_availability_loss(frames, monkeypatch, outcome):
    student, counselor, appointment, capture, artifact, storage = ready_artifact(pending=False)
    dpo, case = v2_case(capture)
    case = retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=context(dpo)
    )
    if outcome == "hold":
        retention.change_hold(
            actor=dpo,
            case_id=case.pk,
            expected_revision=case.revision,
            reason="Synthetic hold",
            release=False,
            context=context(dpo),
        )
    storage.fail_delete = outcome == "storage-failure"
    monkeypatch.setattr(
        "compass.privacy_governance.media_disposition.ObjectStorage", lambda **kwargs: storage
    )
    frames.clear()
    execute_disposition(case.pk)
    artifact.refresh_from_db()
    assert artifact.status == ("DISPOSED" if outcome == "success" else "STORED")
    if outcome == "success":
        assert_hints(frames, appointment, [student, counselor])
        assert not media.get_media_projection(capture.room)["recording"]["artifact_available"]
        assert (
            auth_client(counselor)
            .get(f"/api/v1/e-counseling/appointments/{appointment.pk}/media/RECORDING/access")
            .status_code
            == 410
        )
    else:
        assert media_frames(frames) == []


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_legacy_verified_disposition_also_notifies_saved_workspace_viewers(
    frames, monkeypatch, kind
):
    capture, _ = media_source(kind)
    appointment = capture.room.appointment
    dpo = make_dpo()
    active_rule(dpo, "ECOUNSELING_RECORDING" if kind == "RECORDING" else "ECOUNSELING_TRANSCRIPT")
    case = approve(dpo, discovered_case(capture))
    monkeypatch.setattr(
        "compass.privacy_governance.tasks.DailyClient.from_settings",
        lambda: CapturingDispositionDaily("success", transcript=kind == "TRANSCRIPTION"),
    )
    frames.clear()
    execute_disposition(case.pk)
    capture.refresh_from_db()
    assert capture.artifact_disposed_at
    assert_hints(frames, appointment, [appointment.student, appointment.provider])


@pytest.mark.parametrize("operation", ["stop", "withdraw"])
def test_concurrent_start_superseded_by_stop_or_withdrawal_has_only_committed_hints(
    frames, operation
):
    student, counselor, appointment, client = authorized_session()
    entered, release = Event(), Event()
    original = client.update_room

    def delayed_update(**kwargs):
        value = original(**kwargs)
        entered.set()
        assert release.wait(10)
        return value

    client.update_room = delayed_update
    failures = []

    def starting():
        try:
            start("RECORDING", counselor, appointment, client)
        except Exception as exc:
            failures.append(exc)
        finally:
            connections.close_all()

    frames.clear()
    thread = Thread(target=starting)
    thread.start()
    try:
        assert entered.wait(10)
        if operation == "stop":
            media.stop_recording(
                counselor=counselor,
                appointment_id=appointment.pk,
                context=context(counselor),
                daily_client=FakeMediaDailyClient(),
            )
        else:
            consent = ECounselingConsent.objects.get(
                room__appointment=appointment, scope="SESSION_MEDIA_CAPTURE"
            )
            media.withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=consent.pk,
                context=context(student),
                daily_client=FakeMediaDailyClient(),
            )
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and len(failures) == 1
    assert isinstance(
        failures[0], (media.ECounselingMediaConflict, media.ECounselingConsentNotApproved)
    )
    assert not client.recording_starts
    assert_hints(frames, appointment, [student, counselor], transitions=2)


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "room_id",
        "instance_id",
        "session_id",
        "artifact_id",
        "url",
        "object_key",
        "consent",
        "error",
        "duration",
    ],
)
def test_media_public_contract_rejects_every_additional_field(field):
    with pytest.raises(ValueError):
        protocol.encode_event(EVENT, {"appointment_id": uuid4(), field: "PRIVATE"})


@pytest.mark.parametrize("token_failure", [False, True])
def test_room_provisioning_notifies_once_independently_of_later_token_failure(
    frames, token_failure
):
    _, student, counselor, appointment = setup_session(media_policy_version=2)
    client = FakeMediaDailyClient()
    if token_failure:

        def fail(**kwargs):
            assert_hints(frames, appointment, [student, counselor])
            raise DailyTimeout("synthetic token failure")

        client.create_meeting_token = fail
    if token_failure:
        with pytest.raises(ECounselingProviderUnavailable):
            create_join_credential(
                actor=counselor,
                appointment_id=appointment.pk,
                context=context(counselor),
                daily_client=client,
            )
    else:
        create_join_credential(
            actor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=client,
        )
    assert_hints(frames, appointment, [student, counselor])
    frames.clear()
    client.create_meeting_token = FakeMediaDailyClient().create_meeting_token
    create_join_credential(
        actor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    assert media_frames(frames) == []


def test_artifact_creation_rolls_back_without_hint_or_dispatch(frames):
    *_, capture = pending_capture(kind="RECORDING", state="READY")
    frames.clear()
    with pytest.raises(ValueError):
        with transaction.atomic():
            assert artifacts.ensure_pending_artifact(capture)
            assert media_frames(frames) == []
            raise ValueError("rollback")
    assert not ECounselingMediaArtifact.objects.filter(capture=capture).exists()
    assert media_frames(frames) == []


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_concurrent_verified_webhook_and_reconciliation_converge_on_one_transition(frames, kind):
    student, counselor, appointment, _, capture = pending_capture(
        kind=kind, storage=kind == "TRANSCRIPTION"
    )
    claimed = claim(capture)
    observation = observe_metadata(claimed, metadata(capture))
    event = body_for(capture, "ready-to-download")
    barrier = Barrier(2)
    failures = []

    def perform(action):
        try:
            barrier.wait(timeout=10)
            action()
        except Exception as exc:
            failures.append(exc)
        finally:
            connections.close_all()

    frames.clear()
    threads = [
        Thread(target=perform, args=(lambda: signed(event),)),
        Thread(target=perform, args=(lambda: apply_observation(claimed, observation),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)
    assert not failures and all(not thread.is_alive() for thread in threads)
    capture.refresh_from_db()
    assert capture.status == "READY" and capture.stop_requested_at
    assert_hints(frames, appointment, [student, counselor])
    assert ECounselingMediaArtifact.objects.filter(capture=capture).count() == 1


def test_duplicate_ingestion_worker_during_transfer_adds_no_transition(frames):
    student, counselor, appointment, capture, artifact, storage = ready_artifact()
    entered, release = Event(), Event()
    original = storage.save

    def held_save(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    storage.save = held_save
    failures = []

    def ingest():
        try:
            artifacts.ingest_artifact(
                artifact.pk,
                storage=storage,
                client=BoundArtifactDaily(capture),
                download=fake_download,
            )
        except Exception as exc:
            failures.append(exc)
        finally:
            connections.close_all()

    frames.clear()
    thread = Thread(target=ingest)
    thread.start()
    try:
        assert entered.wait(10)
        assert_hints(frames, appointment, [student, counselor])
        artifacts.ingest_artifact(
            artifact.pk, storage=storage, client=BoundArtifactDaily(capture), download=fake_download
        )
        assert_hints(frames, appointment, [student, counselor])
    finally:
        release.set()
        thread.join(15)
    artifact.refresh_from_db()
    assert not failures and not thread.is_alive() and artifact.status == "STORED"
    assert_hints(frames, appointment, [student, counselor], transitions=2)


@pytest.mark.parametrize("operation", ["webhook", "custody"])
def test_refused_redis_cannot_undo_verified_provider_or_institutional_custody(
    frames, monkeypatch, operation
):
    if operation == "webhook":
        student, counselor, appointment, _, capture = pending_capture(
            kind="RECORDING", state="START_REQUESTED"
        )
    else:
        student, counselor, appointment, capture, artifact, storage = ready_artifact()
    frames.clear()
    refused = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1)
    monkeypatch.setattr(publish, "_publish", ORIGINAL_PUBLISH)
    monkeypatch.setattr(publish, "realtime_redis", lambda: refused)
    if operation == "webhook":
        event = body_for(capture)
        assert signed(event).accepted
        capture.refresh_from_db()
        assert capture.status == "ACTIVE"
        assert (
            DailyWebhookReceipt.objects.get(provider_event_id=event["id"]).processing_outcome
            == "APPLIED"
        )
    else:
        artifacts.ingest_artifact(
            artifact.pk, storage=storage, client=BoundArtifactDaily(capture), download=fake_download
        )
        artifact.refresh_from_db()
        assert (
            artifact.status == "STORED"
            and media.get_media_projection(capture.room)["recording"]["artifact_available"]
        )
    assert media_frames(frames) == []


def test_real_redis_socket_authenticated_http_signed_provider_and_custody_flow(monkeypatch):
    student, counselor, appointment, client = authorized_session(kind="RECORDING")
    other = make_user("media-socket-other@example.edu", "COUNSELOR")
    clients = [auth_client(student), auth_client(counselor), auth_client(other)]
    monkeypatch.setattr("compass.ecounseling.media.DailyClient.from_settings", lambda: client)
    realtime_connection._client.cache_clear()
    frame = {"v": 1, "type": EVENT, "appointment_id": str(appointment.pk)}
    base = f"/api/v1/e-counseling/appointments/{appointment.pk}"
    student_path = f"/api/v1/e-counseling/me/appointments/{appointment.pk}"

    async def database_call(function, *args, **kwargs):
        def call():
            try:
                return function(*args, **kwargs)
            finally:
                connections.close_all()

        return await asyncio.to_thread(call)

    async def receive(socket):
        message = await socket.next()
        assert message["type"] == "websocket.send" and json.loads(message["text"]) == frame

    async def test(app, _redis):
        sockets = []
        try:
            for http in clients:
                ticket = await database_call(issue, http)
                assert ticket.status_code == 200
                socket = Socket(app)
                sockets.append(socket)
                await socket.ready(ticket.json()["ticket"])

            async def notified(transitions=1):
                for _ in range(transitions):
                    await receive(sockets[0])
                    await receive(sockets[1])
                await sockets[2].nothing()

            started = await database_call(
                clients[1].post,
                base + "/recording/start",
                data="{}",
                content_type="application/json",
            )
            assert started.status_code == 200
            await notified()
            state = await database_call(clients[0].get, student_path)
            assert state.json()["media"]["recording"]["capture_status"] == "START_REQUESTED"
            capture = await database_call(
                ECounselingMediaCapture.objects.select_related("room").get,
                room__appointment=appointment,
                kind="RECORDING",
            )
            assert (await database_call(signed, body_for(capture), http=True)).status_code == 200
            await notified()
            capture = await database_call(
                ECounselingMediaCapture.objects.select_related("room").get, pk=capture.pk
            )
            state = await database_call(clients[0].get, student_path)
            assert state.json()["media"]["recording"]["capture_status"] == "ACTIVE"
            assert (
                await database_call(
                    clients[1].post,
                    base + "/recording/stop",
                    data="{}",
                    content_type="application/json",
                )
            ).status_code == 200
            await notified()
            state = await database_call(clients[0].get, student_path)
            assert state.json()["media"]["recording"]["capture_status"] == "STOP_REQUESTED"
            assert (
                await database_call(signed, body_for(capture, "ready-to-download"), http=True)
            ).status_code == 200
            await notified()
            state = await database_call(clients[0].get, student_path)
            assert (
                state.json()["media"]["recording"]["capture_status"] == "READY"
                and not state.json()["media"]["recording"]["artifact_available"]
            )
            artifact = await database_call(ECounselingMediaArtifact.objects.get, capture=capture)
            storage = FakeStorage()
            await database_call(
                artifacts.ingest_artifact,
                artifact.pk,
                storage=storage,
                client=BoundArtifactDaily(capture),
                download=fake_download,
            )
            await notified(2)
            state = await database_call(clients[1].get, base)
            assert (
                state.json()["media"]["recording"]["artifact_status"] == "STORED"
                and state.json()["media"]["recording"]["artifact_available"]
            )
            assert (await database_call(clients[2].get, base)).status_code == 403
            refused = redis.Redis(
                host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1
            )
            monkeypatch.setattr(publish, "realtime_redis", lambda: refused)
            started_transcript = await database_call(
                clients[1].post,
                base + "/transcription/start",
                data='{"store_transcript":false}',
                content_type="application/json",
            )
            assert started_transcript.status_code == 200
            state = await database_call(clients[1].get, base)
            assert state.json()["media"]["transcription"]["capture_status"] == "START_REQUESTED"
            assert state.json()["media"]["recording"]["artifact_available"]
            for socket in sockets:
                await socket.nothing()
        finally:
            for socket in sockets:
                await socket.disconnect()

    try:
        run(test)
    finally:
        realtime_connection._client.cache_clear()
