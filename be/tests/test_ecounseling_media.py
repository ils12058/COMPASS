from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.counseling.models import CounselingEncounter
from compass.ecounseling.media import (
    ECounselingConsentConflict,
    ECounselingConsentNotApproved,
    ECounselingMediaConflict,
    decide_my_consent,
    process_media_webhook_event,
    request_consents,
    start_recording,
    start_transcription,
    withdraw_my_consent,
)
from compass.ecounseling.models import (
    ConsentDecision,
    ConsentScope,
    ECounselingConsent,
    ECounselingMediaCapture,
    ECounselingRoom,
    MediaCaptureKind,
    MediaCaptureStatus,
)
from compass.ecounseling.services import (
    ECounselingNotPermitted,
    ECounselingProviderUnavailable,
    create_join_credential,
)
from compass.integrations.daily import DailyUnavailable
from compass.service_catalog.services import create_service, set_service_active


class FakeMediaDailyClient:
    def __init__(self, *, fail_stop: bool = False) -> None:
        self.fail_stop = fail_stop
        self.created_rooms: list[tuple[str, int]] = []
        self.tokens: list[tuple[str, str, str, int]] = []
        self.room_updates: list[tuple[str, dict[str, object]]] = []
        self.recording_starts: list[tuple[str, str]] = []
        self.recording_stops: list[str] = []
        self.transcription_starts: list[tuple[str, str]] = []
        self.transcription_stops: list[tuple[str, str]] = []

    def create_room(self, *, room_name: str, expires_at_epoch: int):
        self.created_rooms.append((room_name, expires_at_epoch))
        return {
            "id": "daily-room-id",
            "name": room_name,
            "url": f"https://example.daily.co/{room_name}",
            "privacy": "private",
            "api_created": True,
            "config": {
                "exp": expires_at_epoch,
                "eject_at_room_exp": False,
                "max_participants": 2,
                "enable_chat": False,
                "enable_screenshare": False,
                "enable_live_captions_ui": False,
                "enable_transcription_storage": False,
                "enforce_unique_user_ids": True,
            },
        }

    def get_room(self, *, room_name: str):
        assert self.created_rooms
        return self.create_room(
            room_name=room_name,
            expires_at_epoch=self.created_rooms[-1][1],
        )

    def create_meeting_token(
        self,
        *,
        room_name: str,
        user_id: str,
        user_name: str,
        expires_at_epoch: int,
    ) -> str:
        self.tokens.append((room_name, user_id, user_name, expires_at_epoch))
        return f"token-{len(self.tokens)}"

    def update_room(self, *, room_name: str, properties: dict[str, object]):
        self.room_updates.append((room_name, properties))
        return {"name": room_name, "config": properties}

    def start_recording(self, *, room_name: str, instance_id: str):
        self.recording_starts.append((room_name, instance_id))
        return {"status": "sent"}

    def stop_recording(self, *, room_name: str):
        self.recording_stops.append(room_name)
        if self.fail_stop:
            raise DailyUnavailable("provider unavailable")
        return {"status": "sent"}

    def start_transcription(self, *, room_name: str, instance_id: str):
        self.transcription_starts.append((room_name, instance_id))
        return {"sent": "true"}

    def stop_transcription(self, *, room_name: str, instance_id: str):
        self.transcription_stops.append((room_name, instance_id))
        if self.fail_stop:
            raise DailyUnavailable("provider unavailable")
        return {"sent": "true"}


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
    )


def context(user: User) -> AuditContext:
    return AuditContext.user(user)


def create_counseling_service(admin: User):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON", "ONLINE"],
        provider_roles=["COUNSELOR"],
        context=context(admin),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(admin))


def make_appointment(*, student: User, counselor: User, service) -> Appointment:
    start = timezone.now() - timedelta(minutes=5)
    return Appointment.objects.create(
        reference_code=f"APT-2026-{Appointment.objects.count() + 1:06d}",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="ONLINE",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status=AppointmentStatus.SCHEDULED,
        cancellation_cutoff_minutes=30,
        created_by=student,
    )


def setup_session():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    return admin, student, counselor, appointment


def approve_scope(
    *,
    student: User,
    counselor: User,
    appointment: Appointment,
    scope: str,
):
    requested = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[scope],
        context=context(counselor),
    )[0]
    return decide_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=requested["id"],
        decision=ConsentDecision.APPROVED,
        context=context(student),
    )


@pytest.mark.django_db
def test_media_capabilities_are_narrow_and_head_designation_does_not_bypass_assignment():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    head = make_user("head@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert student.has_capability("ecounseling.consent_self")
    assert counselor.has_capability("ecounseling.manage_media_assigned")
    assert head.has_capability("ecounseling.manage_media_assigned")
    assert not gss.has_capability("ecounseling.manage_media_assigned")
    assert not admin.has_capability("ecounseling.manage_media_assigned")


@pytest.mark.django_db
def test_consent_request_creates_only_local_room_binding_and_is_idempotent():
    _, student, counselor, appointment = setup_session()
    first = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.AUDIO_VIDEO_RECORDING],
        context=context(counselor),
    )
    second = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.AUDIO_VIDEO_RECORDING],
        context=context(counselor),
    )

    room = ECounselingRoom.objects.get(appointment=appointment)
    assert room.provisioned_at is None
    assert room.daily_room_url is None
    assert first == second
    assert first[0]["decision"] == ConsentDecision.PENDING
    assert ECounselingConsent.objects.count() == 1
    assert AuditEvent.objects.filter(action="ecounseling.consent_requested").count() == 1
    assert student.has_capability("ecounseling.consent_self")


@pytest.mark.django_db
def test_consent_request_rejects_duplicates_terminal_rerequest_and_storage_without_live_request():
    _, student, counselor, appointment = setup_session()
    with pytest.raises(ECounselingConsentConflict, match="Duplicate"):
        request_consents(
            counselor=counselor,
            appointment_id=appointment.pk,
            scopes=[ConsentScope.LIVE_TRANSCRIPTION, ConsentScope.LIVE_TRANSCRIPTION],
            context=context(counselor),
        )
    with pytest.raises(ECounselingConsentConflict, match="requires"):
        request_consents(
            counselor=counselor,
            appointment_id=appointment.pk,
            scopes=[ConsentScope.TRANSCRIPT_STORAGE],
            context=context(counselor),
        )

    item = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.AUDIO_VIDEO_RECORDING],
        context=context(counselor),
    )[0]
    decide_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=item["id"],
        decision=ConsentDecision.DENIED,
        context=context(student),
    )
    with pytest.raises(ECounselingConsentConflict, match="cannot be reopened"):
        request_consents(
            counselor=counselor,
            appointment_id=appointment.pk,
            scopes=[ConsentScope.AUDIO_VIDEO_RECORDING],
            context=context(counselor),
        )


@pytest.mark.django_db
def test_only_student_owner_decides_and_denial_does_not_cancel_counseling():
    _, student, counselor, appointment = setup_session()
    other_student = make_user("other@example.edu", "STUDENT")
    item = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.AUDIO_VIDEO_RECORDING],
        context=context(counselor),
    )[0]

    with pytest.raises(ECounselingNotPermitted):
        decide_my_consent(
            student=other_student,
            appointment_id=appointment.pk,
            consent_id=item["id"],
            decision=ConsentDecision.APPROVED,
            context=context(other_student),
        )

    decided = decide_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=item["id"],
        decision=ConsentDecision.DENIED,
        context=context(student),
    )
    assert decided["decision"] == ConsentDecision.DENIED
    with pytest.raises(ECounselingConsentConflict, match="already been decided"):
        decide_my_consent(
            student=student,
            appointment_id=appointment.pk,
            consent_id=item["id"],
            decision=ConsentDecision.APPROVED,
            context=context(student),
        )
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()


@pytest.mark.django_db
def test_recording_requires_effective_consent_and_uses_deterministic_instance_id():
    _, student, counselor, appointment = setup_session()
    fake = FakeMediaDailyClient()
    with override_settings(DAILY_ENABLED=True):
        create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        with pytest.raises(ECounselingConsentNotApproved):
            start_recording(
                counselor=counselor,
                appointment_id=appointment.pk,
                context=context(counselor),
                daily_client=fake,
            )
        approve_scope(
            student=student,
            counselor=counselor,
            appointment=appointment,
            scope=ConsentScope.AUDIO_VIDEO_RECORDING,
        )
        capture = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=fake,
        )

    assert capture.status == MediaCaptureStatus.START_REQUESTED
    assert capture.provider_instance_id
    assert fake.room_updates[-1][1] == {"enable_recording": "cloud"}
    assert fake.recording_starts == [(capture.room.daily_room_name, capture.provider_instance_id)]
    assert AuditEvent.objects.filter(action="ecounseling.recording_start_requested").count() == 1
    with override_settings(DAILY_ENABLED=True):
        with pytest.raises(ECounselingMediaConflict):
            start_recording(
                counselor=counselor,
                appointment_id=appointment.pk,
                context=context(counselor),
                daily_client=fake,
            )


@pytest.mark.django_db
def test_transcription_storage_requires_both_consents_and_room_config_matches_choice():
    _, student, counselor, appointment = setup_session()
    fake = FakeMediaDailyClient()
    with override_settings(DAILY_ENABLED=True):
        create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        approve_scope(
            student=student,
            counselor=counselor,
            appointment=appointment,
            scope=ConsentScope.LIVE_TRANSCRIPTION,
        )
        with pytest.raises(ECounselingConsentNotApproved):
            start_transcription(
                counselor=counselor,
                appointment_id=appointment.pk,
                store_transcript=True,
                context=context(counselor),
                daily_client=fake,
            )
        capture = start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=False,
            context=context(counselor),
            daily_client=fake,
        )

    assert capture.status == MediaCaptureStatus.START_REQUESTED
    assert capture.transcript_storage_enabled is False
    assert fake.room_updates[-1][1] == {"enable_transcription_storage": False}
    assert fake.transcription_starts[-1][1] == capture.provider_instance_id


@pytest.mark.django_db
def test_transcription_with_storage_approved_enables_provider_storage():
    _, student, counselor, appointment = setup_session()
    fake = FakeMediaDailyClient()
    requested = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.LIVE_TRANSCRIPTION, ConsentScope.TRANSCRIPT_STORAGE],
        context=context(counselor),
    )
    for item in requested:
        decide_my_consent(
            student=student,
            appointment_id=appointment.pk,
            consent_id=item["id"],
            decision=ConsentDecision.APPROVED,
            context=context(student),
        )
    with override_settings(DAILY_ENABLED=True):
        create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        capture = start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=fake,
        )
    assert capture.transcript_storage_enabled is True
    assert fake.room_updates[-1][1] == {"enable_transcription_storage": True}


@pytest.mark.django_db
def test_withdrawal_persists_when_recording_stop_fails():
    _, student, counselor, appointment = setup_session()
    fake = FakeMediaDailyClient(fail_stop=True)
    approved = approve_scope(
        student=student,
        counselor=counselor,
        appointment=appointment,
        scope=ConsentScope.AUDIO_VIDEO_RECORDING,
    )
    with override_settings(DAILY_ENABLED=True):
        create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        capture = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=fake,
        )
    capture.status = MediaCaptureStatus.ACTIVE
    capture.save(update_fields=["status", "updated_at"])

    with override_settings(DAILY_ENABLED=True):
        with pytest.raises(ECounselingProviderUnavailable):
            withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=approved["id"],
                context=context(student),
                daily_client=fake,
            )

    consent = ECounselingConsent.objects.get(pk=approved["id"])
    capture.refresh_from_db()
    assert consent.withdrawn_at is not None
    assert not consent.is_effectively_approved
    assert capture.status == MediaCaptureStatus.STOP_REQUESTED
    assert capture.error_code == "STOP_PROVIDER_FAILED"
    assert AuditEvent.objects.filter(action="ecounseling.consent_withdrawn").count() == 1
    assert AuditEvent.objects.filter(action="ecounseling.recording_stop_requested").count() == 1


@pytest.mark.django_db
def test_transcript_storage_withdrawal_disables_storage_even_when_stop_fails():
    _, student, counselor, appointment = setup_session()
    fake = FakeMediaDailyClient(fail_stop=True)
    requested = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.LIVE_TRANSCRIPTION, ConsentScope.TRANSCRIPT_STORAGE],
        context=context(counselor),
    )
    approved = {}
    for item in requested:
        decided = decide_my_consent(
            student=student,
            appointment_id=appointment.pk,
            consent_id=item["id"],
            decision=ConsentDecision.APPROVED,
            context=context(student),
        )
        approved[decided["scope"]] = decided

    with override_settings(DAILY_ENABLED=True):
        create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        capture = start_transcription(
            counselor=counselor,
            appointment_id=appointment.pk,
            store_transcript=True,
            context=context(counselor),
            daily_client=fake,
        )
    capture.status = MediaCaptureStatus.ACTIVE
    capture.save(update_fields=["status", "updated_at"])

    with override_settings(DAILY_ENABLED=True):
        with pytest.raises(ECounselingProviderUnavailable):
            withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=approved[ConsentScope.TRANSCRIPT_STORAGE]["id"],
                context=context(student),
                daily_client=fake,
            )

    consent = ECounselingConsent.objects.get(pk=approved[ConsentScope.TRANSCRIPT_STORAGE]["id"])
    capture.refresh_from_db()
    assert consent.withdrawn_at is not None
    assert not consent.is_effectively_approved
    assert capture.status == MediaCaptureStatus.STOP_REQUESTED
    assert capture.error_code == "STOP_PROVIDER_FAILED"
    assert capture.transcript_storage_enabled is False
    assert fake.transcription_stops
    assert fake.room_updates[-1][1] == {"enable_transcription_storage": False}


@pytest.mark.django_db
def test_recording_webhooks_reconcile_without_persisting_temporary_access_values():
    _, student, counselor, appointment = setup_session()
    fake = FakeMediaDailyClient()
    approve_scope(
        student=student,
        counselor=counselor,
        appointment=appointment,
        scope=ConsentScope.AUDIO_VIDEO_RECORDING,
    )
    with override_settings(DAILY_ENABLED=True):
        create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        capture = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=fake,
        )

    started = process_media_webhook_event(
        event_type="recording.started",
        event_id="rec-start-1",
        event_ts=timezone.now().timestamp(),
        payload={
            "recording_id": "recording-1",
            "instance_id": capture.provider_instance_id,
            "start_ts": timezone.now().timestamp(),
        },
    )
    assert started.accepted and started.supported
    capture.refresh_from_db()
    assert capture.status == MediaCaptureStatus.ACTIVE

    ready = process_media_webhook_event(
        event_type="recording.ready-to-download",
        event_id="rec-ready-1",
        event_ts=timezone.now().timestamp(),
        payload={
            "recording_id": "recording-1",
            "room_name": capture.room.daily_room_name,
            "start_ts": timezone.now().timestamp() - 5,
            "duration": 5,
            "share_token": "must-not-persist",
            "s3_key": "must/not/persist",
        },
    )
    assert ready.accepted and ready.supported
    duplicate = process_media_webhook_event(
        event_type="recording.ready-to-download",
        event_id="rec-ready-1",
        event_ts=timezone.now().timestamp(),
        payload={
            "recording_id": "recording-1",
            "room_name": capture.room.daily_room_name,
        },
    )
    assert duplicate.duplicate

    capture.refresh_from_db()
    assert capture.status == MediaCaptureStatus.READY
    assert capture.provider_artifact_id == "recording-1"
    assert not hasattr(capture, "share_token")
    assert not hasattr(capture, "s3_key")
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()


@pytest.mark.django_db
def test_unexpected_transcription_without_consent_is_marked_stop_required_and_best_effort_stopped():
    _, student, _, appointment = setup_session()
    fake = FakeMediaDailyClient()
    with override_settings(DAILY_ENABLED=True):
        credential = create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        with patch("compass.ecounseling.media.DailyClient.from_settings", return_value=fake):
            result = process_media_webhook_event(
                event_type="transcript.started",
                event_id="tra-start-unexpected",
                event_ts=timezone.now().timestamp(),
                payload={
                    "id": "transcript-1",
                    "info": {"instanceId": "transcription-instance-1"},
                    "room_name": credential.room.daily_room_name,
                    "mtg_session_id": "meeting-1",
                    "duration": 0,
                },
            )
    assert result.accepted and result.supported
    capture = ECounselingMediaCapture.objects.get(
        room=credential.room,
        kind=MediaCaptureKind.TRANSCRIPTION,
    )
    assert capture.status == MediaCaptureStatus.STOP_REQUESTED
    assert capture.error_code == "CONSENT_NOT_EFFECTIVE"
    assert fake.transcription_stops == [
        (credential.room.daily_room_name, "transcription-instance-1")
    ]


@pytest.mark.django_db
def test_consent_audit_contains_state_not_counseling_content():
    _, student, counselor, appointment = setup_session()
    item = request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=[ConsentScope.LIVE_TRANSCRIPTION],
        context=context(counselor),
    )[0]
    decide_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=item["id"],
        decision=ConsentDecision.APPROVED,
        context=context(student),
    )
    serialized = str(list(AuditEvent.objects.values("action", "metadata")))
    assert "LIVE_TRANSCRIPTION" in serialized
    assert "APPROVED" in serialized
    assert "transcript text" not in serialized.lower()
    assert "recording_url" not in serialized.lower()
