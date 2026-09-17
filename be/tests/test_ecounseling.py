from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling.models import CounselingEncounter
from compass.ecounseling.models import DailyWebhookReceipt, ECounselingRoom
from compass.ecounseling.services import (
    ECounselingAppointmentNotEligible,
    ECounselingNotPermitted,
    ECounselingProviderUnavailable,
    create_join_credential,
    get_counselor_workspace,
    get_student_workspace,
    process_daily_webhook,
)
from compass.integrations.daily import DailyUnavailable
from compass.service_catalog.services import create_service, set_service_active


class FakeDailyClient:
    def __init__(self) -> None:
        self.created_rooms: list[tuple[str, int]] = []
        self.tokens: list[tuple[str, str, str, int]] = []

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


class FailingDailyClient(FakeDailyClient):
    def create_room(self, *, room_name: str, expires_at_epoch: int):
        raise DailyUnavailable("provider unavailable")


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


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


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


def make_appointment(
    *,
    student: User,
    counselor: User,
    service,
    mode: str = "ONLINE",
    active_window: bool = True,
) -> Appointment:
    now = timezone.now()
    start = now - timedelta(minutes=5) if active_window else now + timedelta(days=1)
    return Appointment.objects.create(
        reference_code=f"APT-2026-{Appointment.objects.count() + 1:06d}",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode=mode,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status=AppointmentStatus.SCHEDULED,
        cancellation_cutoff_minutes=30,
        created_by=student,
    )


def _webhook_signature(secret: bytes, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


@pytest.mark.django_db
def test_capabilities_are_explicit_and_do_not_grant_gss_it_or_head_blanket_access():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert student.has_capability("ecounseling.view_self")
    assert student.has_capability("ecounseling.join_self")
    assert counselor.has_capability("ecounseling.view_assigned")
    assert counselor.has_capability("ecounseling.join_assigned")
    assert not gss.has_capability("ecounseling.view_assigned")
    assert not admin.has_capability("ecounseling.view_assigned")
    assert head.has_capability("ecounseling.view_assigned")


@pytest.mark.django_db
def test_workspace_is_read_only_relationship_scoped_and_does_not_provision_room():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    unrelated = make_user("unrelated@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)

    with override_settings(DAILY_ENABLED=False):
        student_view = get_student_workspace(student=student, appointment_id=appointment.pk)
        counselor_view = get_counselor_workspace(counselor=counselor, appointment_id=appointment.pk)

    assert student_view["provider_readiness"] == {
        "daily_enabled": False,
        "room_provisioned": False,
        "join_allowed": False,
    }
    assert student_view["routine_interview"] is None
    assert "student" not in student_view
    assert "counseling_encounter" not in student_view
    assert counselor_view["routine_interview"] is None
    assert counselor_view["counseling_encounter"] is None
    assert ECounselingRoom.objects.count() == 0

    with pytest.raises(ECounselingNotPermitted):
        get_counselor_workspace(counselor=unrelated, appointment_id=appointment.pk)


@pytest.mark.django_db
def test_join_reuses_one_opaque_room_mints_fresh_tokens_and_never_checks_inventory():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    fake = FakeDailyClient()

    with override_settings(
        DAILY_ENABLED=True,
        DAILY_MEETING_TOKEN_TTL_SECONDS=300,
        ECOUNSELING_JOIN_EARLY_SECONDS=0,
        ECOUNSELING_REJOIN_GRACE_SECONDS=0,
    ):
        first = create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
        second = create_join_credential(
            actor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=fake,
        )

    assert first.room.pk == second.room.pk
    assert first.room.daily_room_name.startswith("ec-")
    assert appointment.reference_code not in first.room.daily_room_name
    assert student.email not in first.room.daily_room_name
    assert len(fake.created_rooms) == 1
    assert first.meeting_token == "token-1"
    assert second.meeting_token == "token-2"
    assert ECounselingRoom.objects.count() == 1
    assert AuditEvent.objects.filter(action="ecounseling.room_provisioned").count() == 1
    assert AuditEvent.objects.filter(action="ecounseling.join_authorized").count() == 2
    serialized_audit = json.dumps(list(AuditEvent.objects.values("action", "metadata")))
    assert "token-1" not in serialized_audit
    assert first.room_url not in serialized_audit


@pytest.mark.django_db
def test_join_rejects_non_online_cancelled_wrong_relationship_and_provider_failure_preserves_truth():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    unrelated = make_user("unrelated@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    in_person = make_appointment(
        student=student, counselor=counselor, service=service, mode="IN_PERSON"
    )
    with pytest.raises(ECounselingAppointmentNotEligible):
        get_student_workspace(student=student, appointment_id=in_person.pk)

    online = make_appointment(student=student, counselor=counselor, service=service)
    with override_settings(DAILY_ENABLED=True):
        with pytest.raises(ECounselingNotPermitted):
            create_join_credential(
                actor=unrelated,
                appointment_id=online.pk,
                context=context(unrelated),
                daily_client=FakeDailyClient(),
            )
        with pytest.raises(ECounselingProviderUnavailable):
            create_join_credential(
                actor=student,
                appointment_id=online.pk,
                context=context(student),
                daily_client=FailingDailyClient(),
            )
    online.refresh_from_db()
    assert online.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=online).exists()


@pytest.mark.django_db
def test_cancellation_denies_new_tokens_but_preserves_existing_provider_binding():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    fake = FakeDailyClient()

    with override_settings(DAILY_ENABLED=True):
        credential = create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = timezone.now()
    appointment.cancelled_by = student
    appointment.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])

    with override_settings(DAILY_ENABLED=True):
        with pytest.raises(ECounselingAppointmentNotEligible):
            create_join_credential(
                actor=student,
                appointment_id=appointment.pk,
                context=context(student),
                daily_client=fake,
            )
    assert ECounselingRoom.objects.filter(pk=credential.room.pk).exists()
    assert len(fake.tokens) == 1


@pytest.mark.django_db
def test_webhooks_are_hmac_verified_deduplicated_and_telemetry_only():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    fake = FakeDailyClient()
    secret = b"daily-webhook-secret"
    secret_b64 = base64.b64encode(secret).decode("ascii")

    with override_settings(DAILY_ENABLED=True):
        credential = create_join_credential(
            actor=student,
            appointment_id=appointment.pk,
            context=context(student),
            daily_client=fake,
        )

    event_time = timezone.now().timestamp()
    event = {
        "version": "1.0.0",
        "type": "meeting.ended",
        "id": "met-end-test-1",
        "payload": {
            "start_ts": event_time - 120,
            "end_ts": event_time,
            "meeting_id": "meeting-session-1",
            "room": credential.room.daily_room_name,
        },
        "event_ts": event_time,
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(event_time)
    signature = _webhook_signature(secret, timestamp, body)

    with override_settings(
        DAILY_ENABLED=True,
        DAILY_WEBHOOK_HMAC=secret_b64,
        DAILY_WEBHOOK_MAX_AGE_SECONDS=300,
    ):
        first = process_daily_webhook(
            raw_body=body,
            signature=signature,
            timestamp=timestamp,
            now_epoch=event_time,
        )
        duplicate = process_daily_webhook(
            raw_body=body,
            signature=signature,
            timestamp=timestamp,
            now_epoch=event_time,
        )

    assert first.accepted and first.supported and not first.duplicate
    assert duplicate.accepted and duplicate.duplicate
    assert DailyWebhookReceipt.objects.filter(provider_event_id="met-end-test-1").count() == 1
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED


@pytest.mark.django_db
def test_join_api_is_no_store_and_returns_token_separately_from_room_url():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    client = auth_client(student)

    # Provider HTTP is deliberately not exercised by this API smoke test; disabled mode proves
    # session/CSRF routing and controlled provider gating without any network dependency.
    with override_settings(DAILY_ENABLED=False):
        response = client.post(
            f"/api/v1/e-counseling/appointments/{appointment.pk}/join",
            data=json.dumps({}),
            content_type="application/json",
            **csrf(client),
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ecounseling_provider_disabled"
