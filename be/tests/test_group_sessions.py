"""Tests for Group Sessions, Facilitators, Registration, Capacity, Attendance, and Metrics."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.actions import (
    GROUP_SESSION_ATTENDANCE_CORRECTED,
    GROUP_SESSION_CREATED,
    GROUP_SESSION_PUBLISHED,
    GROUP_SESSION_WITHDRAWN,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.group_sessions.models import (
    GroupSessionAttendance,
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.group_sessions.services import (
    cancel_group_session,
    cancel_student_registration,
    complete_group_session,
    create_group_session,
    export_roster_csv,
    get_group_session_metrics,
    publish_group_session,
    record_attendance,
    register_student,
    sanitize_csv_cell,
    update_group_session,
    withdraw_group_session,
)
from compass.notifications.models import Notification
from compass.organization.models import StaffSupervision
from compass.service_catalog.models import (
    BookingPathwayCode,
    DeliveryMode,
    Service,
)
from compass.service_catalog.services import create_service, set_service_active


def make_user(email: str, role: str) -> User:
    call_command("sync_identity_policy", verbosity=0)
    return User.objects.create_user(
        email=email,
        password="a-test-password-15chars",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
        is_active=True,
    )


@pytest.fixture
def counselor(db) -> User:
    return make_user("counselor_gs@example.test", "COUNSELOR")


@pytest.fixture
def other_counselor(db) -> User:
    return make_user("counselor_other@example.test", "COUNSELOR")


@pytest.fixture
def student(db) -> User:
    return make_user("student_gs@example.test", "STUDENT")


@pytest.fixture
def student2(db) -> User:
    return make_user("student2_gs@example.test", "STUDENT")


@pytest.fixture
def group_service(db, counselor) -> Service:
    svc = create_service(
        code="CAREER_WORKSHOP",
        name="Career Development Workshop",
        description="Interactive career planning group events.",
        delivery_modes=["IN_PERSON", "ONLINE"],
        booking_pathways=[BookingPathwayCode.GROUP_SESSION],
        provider_coverage="ALL_COUNSELORS",
        context=AuditContext.user(counselor),
    )
    return set_service_active(
        service_id=svc.pk, is_active=True, context=AuditContext.user(counselor)
    )


@pytest.mark.django_db
def test_create_group_session_success(group_service, counselor):
    now = timezone.now()
    starts_at = now + timedelta(days=5, hours=9)
    ends_at = starts_at + timedelta(hours=2)

    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Resume & Interview Workshop",
        description="Comprehensive workshop for graduating students.",
        delivery_mode=DeliveryMode.IN_PERSON,
        venue_or_meeting_url="Auditorium Hall B",
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=30,
        facilitator_ids=[counselor.id],
        lead_facilitator_id=counselor.id,
    )

    assert session.status == GroupSessionStatus.DRAFT
    assert session.title == "Resume & Interview Workshop"
    assert session.capacity == 30
    assert session.facilitators.count() == 1
    assert session.facilitators.first().internal_user == counselor
    assert session.facilitators.first().is_lead is True

    audit = AuditEvent.objects.filter(
        action=GROUP_SESSION_CREATED, target_id=str(session.id)
    ).first()
    assert audit is not None
    assert audit.target_type == "service.group.session"


@pytest.mark.django_db
def test_external_facilitator_is_a_guest_identity_with_non_destructive_history(
    group_service, counselor
):
    before_users = User.objects.count()
    starts_at = timezone.now() + timedelta(days=9)
    session = create_group_session(
        service_id=group_service.pk,
        organizer=counselor,
        title="Community Seminar",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        capacity=40,
        facilitators=[
            {
                "kind": "EXTERNAL",
                "internal_user_id": None,
                "external_display_name": "Dr. A. Guest",
                "is_lead": True,
            }
        ],
    )
    guest = session.facilitators.get()
    assert User.objects.count() == before_users
    assert guest.kind == "EXTERNAL"
    assert guest.internal_user_id is None
    assert guest.external_display_name == "Dr. A. Guest"
    assert guest.display_name_snapshot == "Dr. A. Guest"
    assert guest.is_lead

    update_group_session(
        session_id=session.pk,
        actor=counselor,
        facilitators=[
            {
                "kind": "EXTERNAL",
                "internal_user_id": None,
                "external_display_name": "Dr. B. Guest",
                "is_lead": True,
            }
        ],
    )
    guest.refresh_from_db()
    assert guest.removed_at is not None
    assert guest.display_name_snapshot == "Dr. A. Guest"
    current_guest = session.facilitators.get(removed_at__isnull=True)
    assert current_guest.external_display_name == "Dr. B. Guest"
    assert current_guest.internal_user_id is None

    with pytest.raises(ValidationError, match="cannot be linked to a COMPASS account"):
        update_group_session(
            session_id=session.pk,
            actor=counselor,
            facilitators=[
                {
                    "kind": "EXTERNAL",
                    "internal_user_id": counselor.pk,
                    "external_display_name": "Dr. C. Guest",
                    "is_lead": True,
                }
            ],
        )


@pytest.mark.django_db
def test_gss_facilitator_candidates_are_scoped_without_services_manage(counselor):
    gss = make_user("event-candidates-gss@example.test", "GUIDANCE_SERVICES_STAFF")
    out_of_scope_gss = make_user("outside-event-gss@example.test", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    assert gss.has_capability("appointments.manage")
    assert not gss.has_capability("services.manage")

    client = auth_client(gss)
    response = client.get("/api/v1/group-sessions/facilitator-candidates")
    assert response.status_code == 200, response.content
    candidate_ids = {row["id"] for row in response.json()}
    assert str(gss.pk) in candidate_ids
    assert str(counselor.pk) in candidate_ids
    assert str(out_of_scope_gss.pk) not in candidate_ids


@pytest.mark.django_db
def test_create_group_session_rejects_missing_pathway(counselor):
    # Service without GROUP_SESSION pathway
    plain_svc = create_service(
        code="INDIVIDUAL_COUNSELING",
        name="Individual Counseling",
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=60,
        delivery_modes=["IN_PERSON"],
        booking_pathways=[BookingPathwayCode.FLEXIBLE_APPOINTMENT],
        provider_coverage="ALL_COUNSELORS",
        context=AuditContext.user(counselor),
    )
    set_service_active(
        service_id=plain_svc.pk, is_active=True, context=AuditContext.user(counselor)
    )

    now = timezone.now()
    with pytest.raises(ValidationError, match="Group Sessions pathway"):
        create_group_session(
            service_id=plain_svc.id,
            organizer=counselor,
            title="Invalid Event",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=1),
            capacity=20,
            facilitator_ids=[counselor.id],
        )


@pytest.mark.django_db
def test_create_group_session_rejects_invalid_times_or_capacity(group_service, counselor):
    now = timezone.now()
    # starts >= ends
    with pytest.raises(ValidationError, match="start time must be before end time"):
        create_group_session(
            service_id=group_service.id,
            organizer=counselor,
            title="Invalid Times",
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=2),
            capacity=10,
        )

    # capacity < 1
    with pytest.raises(ValidationError, match="Capacity must be at least 1"):
        create_group_session(
            service_id=group_service.id,
            organizer=counselor,
            title="Zero Capacity",
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=2, hours=1),
            capacity=0,
        )

    with pytest.raises(ValidationError, match="Registration times must include a time zone"):
        create_group_session(
            service_id=group_service.pk,
            organizer=counselor,
            title="Naive registration time",
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=2, hours=1),
            capacity=10,
            reg_opens_at=(now + timedelta(days=1)).replace(tzinfo=None),
        )


@pytest.mark.django_db
def test_publish_and_update_lifecycle(group_service, counselor, other_counselor):
    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Leadership Lab",
        starts_at=now + timedelta(days=3),
        ends_at=now + timedelta(days=3, hours=1),
        capacity=15,
        facilitator_ids=[counselor.id],
    )

    # Update in DRAFT
    updated = update_group_session(
        session_id=session.id,
        actor=counselor,
        title="Advanced Leadership Lab",
        capacity=20,
        facilitator_ids=[counselor.id, other_counselor.id],
        lead_facilitator_id=counselor.id,
    )
    assert updated.title == "Advanced Leadership Lab"
    assert updated.capacity == 20
    assert updated.facilitators.count() == 2

    # Publish
    published = publish_group_session(session_id=session.id, actor=counselor)
    assert published.status == GroupSessionStatus.PUBLISHED

    audit_pub = AuditEvent.objects.filter(
        action=GROUP_SESSION_PUBLISHED, target_id=str(session.id)
    ).first()
    assert audit_pub is not None

    # Complete
    with pytest.raises(ValidationError, match="before it has ended"):
        complete_group_session(session_id=session.id, actor=counselor)
    completed = complete_group_session(
        session_id=session.id,
        actor=counselor,
        now=session.ends_at + timedelta(seconds=1),
    )
    assert completed.status == GroupSessionStatus.COMPLETED
    with pytest.raises(ProtectedError):
        completed.delete()


@pytest.mark.django_db
def test_student_registration_and_capacity_enforcement(group_service, counselor, student, student2):
    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Micro Workshop",
        starts_at=now + timedelta(days=4),
        ends_at=now + timedelta(days=4, hours=1),
        capacity=1,  # Capacity 1
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    # Student 1 registers
    reg1 = register_student(session_id=session.id, student=student)
    assert reg1.status == RegistrationStatus.REGISTERED
    assert reg1.student == student

    # Student 1 receives in-app notification
    notif = Notification.objects.filter(
        recipient=student, event_code="group_session.registered"
    ).first()
    assert notif is not None
    assert "Registration Confirmed" in notif.title

    # Duplicate registration rejected
    with pytest.raises(ValidationError, match="already registered"):
        register_student(session_id=session.id, student=student)

    # Capacity full: student2 cannot register
    with pytest.raises(ValidationError, match="[Mm]aximum participant capacity"):
        register_student(session_id=session.id, student=student2)

    # Student 1 cancels
    cancel_student_registration(session_id=session.id, student=student, reason="Schedule conflict")
    reg1.refresh_from_db()
    assert reg1.status == RegistrationStatus.CANCELLED

    # Cancellation notification emitted
    notif_cancel = Notification.objects.filter(
        recipient=student, event_code="group_session.registration_cancelled"
    ).first()
    assert notif_cancel is not None

    # Now student 2 can register
    reg2 = register_student(session_id=session.id, student=student2)
    assert reg2.status == RegistrationStatus.REGISTERED


@pytest.mark.django_db
def test_session_cancellation_cascades_to_registrations(
    group_service, counselor, student, student2
):
    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Peer Mentoring",
        starts_at=now + timedelta(days=5),
        ends_at=now + timedelta(days=5, hours=2),
        capacity=20,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    reg1 = register_student(session_id=session.id, student=student)
    reg2 = register_student(session_id=session.id, student=student2)

    # Staff cancels the session
    cancelled_session = cancel_group_session(
        session_id=session.id,
        actor=counselor,
        reason="Facilitator illness",
    )
    assert cancelled_session.status == GroupSessionStatus.CANCELLED
    assert cancelled_session.cancellation_reason == "Facilitator illness"

    # Both student registrations are cancelled
    reg1.refresh_from_db()
    reg2.refresh_from_db()
    assert reg1.status == RegistrationStatus.CANCELLED
    assert "Facilitator illness" in reg1.cancellation_reason
    assert reg2.status == RegistrationStatus.CANCELLED
    assert GroupSessionRegistration.objects.filter(group_session=session).count() == 2

    # Notifications delivered to both students
    notifs = Notification.objects.filter(event_code="group_session.cancelled", target_id=session.id)
    assert notifs.count() == 2


@pytest.mark.django_db
def test_record_attendance_and_roster_csv(group_service, counselor, student, student2):
    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Mindfulness Circle",
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    reg1 = register_student(session_id=session.id, student=student)
    reg2 = register_student(session_id=session.id, student=student2)

    # Record attendance
    records = [
        {"registration_id": reg1.id, "attended": True, "notes": "Active participant"},
        {"registration_id": reg2.id, "attended": False, "notes": "Unexcused absence"},
    ]
    attendances = record_attendance(session_id=session.id, actor=counselor, records=records)
    assert len(attendances) == 2

    att1 = GroupSessionAttendance.objects.get(registration=reg1)
    att2 = GroupSessionAttendance.objects.get(registration=reg2)
    assert att1.attended is True
    assert att2.attended is False

    # Correction
    corrected_records = [
        {"registration_id": reg2.id, "attended": True, "notes": "Arrived late with excuse"},
    ]
    record_attendance(session_id=session.id, actor=counselor, records=corrected_records)
    att2.refresh_from_db()
    assert att2.attended is True

    audit_corr = AuditEvent.objects.filter(
        action=GROUP_SESSION_ATTENDANCE_CORRECTED, target_id=str(session.id)
    ).first()
    assert audit_corr is not None

    # CSV Roster Export with formula injection check
    csv_content = export_roster_csv(session_id=session.id, actor=counselor)
    assert "Student Name,Institutional ID,Email" in csv_content
    assert student.last_name in csv_content
    assert student2.last_name in csv_content
    assert "Present" in csv_content


def test_sanitize_csv_cell():
    assert sanitize_csv_cell("Normal Text") == "Normal Text"
    assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_csv_cell("+123456789") == "'+123456789"
    assert sanitize_csv_cell("-CMD") == "'-CMD"
    assert sanitize_csv_cell("@EVAL") == "'@EVAL"
    assert sanitize_csv_cell(None) == ""


@pytest.mark.django_db
def test_group_session_operational_metrics(group_service, counselor, student):
    now = timezone.now()
    session1 = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Session 1",
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session1.id, actor=counselor)

    reg = register_student(session_id=session1.id, student=student)
    record_attendance(
        session_id=session1.id,
        actor=counselor,
        records=[{"registration_id": reg.id, "attended": True}],
    )

    metrics = get_group_session_metrics(actor=counselor, service_id=group_service.id)
    assert metrics["total_sessions"] >= 1
    assert metrics["published_sessions"] >= 1
    assert metrics["total_registrations"] >= 1
    assert metrics["attended_count"] >= 1
    assert metrics["attendance_rate_percent"] == 100.0


def auth_client(user: User, *, recent_mfa: bool = False):
    from django.test import Client

    from compass.authentication.sessions import create_auth_session

    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


@pytest.mark.django_db
def test_group_session_api_auth_mfa_and_role_capability_boundaries(
    group_service, counselor, student
):
    import json

    from django.test import Client

    it_admin = make_user("itadmin_gs@example.test", "IT_ADMIN")
    officer = make_user("officer_gs@example.test", "INSTITUTIONAL_OFFICER")

    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Auth Boundary Session",
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    # 1. Unauthenticated requests rejected with 401
    anon = Client()
    for path in (
        "/api/v1/group-sessions/discover",
        "/api/v1/group-sessions/me/registrations",
        f"/api/v1/group-sessions/{session.id}",
        "/api/v1/group-sessions",
    ):
        res = anon.get(path)
        assert res.status_code == 401, f"Expected 401 for {path}, got {res.status_code}"

    # 2. IT_ADMIN, INSTITUTIONAL_OFFICER, and STUDENT rejected with 403 on staff endpoints
    for non_staff in (it_admin, officer, student):
        c = auth_client(non_staff, recent_mfa=True)
        assert c.get("/api/v1/group-sessions").status_code == 403
        assert (
            c.post(
                f"/api/v1/group-sessions/create/{group_service.id}",
                data=json.dumps(
                    {
                        "title": "Blocked",
                        "starts_at": (now + timedelta(days=3)).isoformat(),
                        "ends_at": (now + timedelta(days=3, hours=1)).isoformat(),
                        "capacity": 5,
                    }
                ),
                content_type="application/json",
                **csrf(c),
            ).status_code
            == 403
        )

    # 3. Counselor without recent MFA rejected with 403 on staff mutation
    no_mfa_staff = auth_client(counselor, recent_mfa=False)
    mfa_res = no_mfa_staff.post(
        f"/api/v1/group-sessions/create/{group_service.id}",
        data=json.dumps(
            {
                "title": "Needs MFA",
                "starts_at": (now + timedelta(days=3)).isoformat(),
                "ends_at": (now + timedelta(days=3, hours=1)).isoformat(),
                "capacity": 5,
            }
        ),
        content_type="application/json",
        **csrf(no_mfa_staff),
    )
    assert mfa_res.status_code == 403
    assert mfa_res.json()["error"]["code"] in ("mfa_setup_required", "mfa_step_up_required")

    # 4. Staff rejected with 403 on student-only endpoints (/discover, /me/registrations, /register)
    mfa_staff = auth_client(counselor, recent_mfa=True)
    assert mfa_staff.get("/api/v1/group-sessions/discover").status_code == 403
    assert mfa_staff.get("/api/v1/group-sessions/me/registrations").status_code == 403
    assert (
        mfa_staff.post(
            f"/api/v1/group-sessions/{session.id}/register",
            **csrf(mfa_staff),
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_group_session_api_privacy_redaction_and_reschedule_notification(
    group_service, counselor, student
):
    import json

    now = timezone.now()
    starts_at = now + timedelta(days=3, hours=2)
    ends_at = starts_at + timedelta(hours=1)
    secret_url = "https://meet.example.edu/secret-group-room-99"

    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Online Career Seminar",
        delivery_mode=DeliveryMode.ONLINE,
        venue_or_meeting_url=secret_url,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=15,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    student_client = auth_client(student)
    staff_client = auth_client(counselor, recent_mfa=True)
    staff_detail = staff_client.get(f"/api/v1/group-sessions/{session.id}")
    assert staff_detail.status_code == 200
    assert staff_detail.json()["can_complete"] is False
    from unittest.mock import patch

    with patch(
        "compass.group_sessions.api.timezone.now",
        return_value=ends_at + timedelta(seconds=1),
    ):
        ended_detail = staff_client.get(f"/api/v1/group-sessions/{session.id}")
    assert ended_detail.json()["can_complete"] is True

    # 1. Unregistered student does NOT see online meeting URL in /discover or /{id}
    disc_res = student_client.get("/api/v1/group-sessions/discover")
    assert disc_res.status_code == 200
    disc_item = next(s for s in disc_res.json() if s["id"] == str(session.id))
    assert disc_item["venue_or_meeting_url"] == ""
    assert disc_item["can_register"] is True

    detail_res = student_client.get(f"/api/v1/group-sessions/{session.id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["venue_or_meeting_url"] == ""

    # 2. Student registers -> now sees online meeting URL
    reg_res = student_client.post(
        f"/api/v1/group-sessions/{session.id}/register",
        **csrf(student_client),
    )
    assert reg_res.status_code == 201, reg_res.content
    registration_id = reg_res.json()["id"]
    student2 = make_user("student2-privacy-gs@example.test", "STUDENT")
    registration2 = register_student(session_id=session.id, student=student2)

    disc_after = student_client.get("/api/v1/group-sessions/discover")
    disc_item_after = next(s for s in disc_after.json() if s["id"] == str(session.id))
    assert disc_item_after["venue_or_meeting_url"] == secret_url
    assert disc_item_after["is_registered_by_me"] is True
    assert disc_item_after["can_register"] is False

    detail_after = student_client.get(f"/api/v1/group-sessions/{session.id}")
    assert detail_after.json()["venue_or_meeting_url"] == secret_url

    # 3. Staff records attendance with internal facilitator notes
    att_res = staff_client.post(
        f"/api/v1/group-sessions/{session.id}/attendance",
        data=json.dumps(
            {
                "records": [
                    {
                        "registration_id": registration_id,
                        "attended": True,
                        "notes": "Internal facilitator note: follow up on internship anxiety",
                    }
                ]
            }
        ),
        content_type="application/json",
        **csrf(staff_client),
    )
    assert att_res.status_code == 200, att_res.content

    # Staff sees attendance_notes; student does NOT see attendance_notes
    staff_regs = staff_client.get(f"/api/v1/group-sessions/{session.id}/registrations")
    assert staff_regs.status_code == 200
    assert (
        staff_regs.json()[0]["attendance_notes"]
        == "Internal facilitator note: follow up on internship anxiety"
    )

    my_regs = student_client.get("/api/v1/group-sessions/me/registrations")
    assert my_regs.status_code == 200
    my_reg = next(r for r in my_regs.json() if r["id"] == registration_id)
    assert len(my_regs.json()) == 1
    assert my_regs.json()[0]["student_id"] == str(student.id)
    assert registration2.id != registration_id
    assert my_reg["attended"] is True
    assert my_reg["attendance_notes"] is None
    assert my_reg["service_id"] == str(group_service.pk)
    starts_at_from_api = datetime.fromisoformat(my_reg["starts_at"].replace("Z", "+00:00"))
    ends_at_from_api = datetime.fromisoformat(my_reg["ends_at"].replace("Z", "+00:00"))
    assert starts_at_from_api == starts_at.replace(
        microsecond=(starts_at.microsecond // 1000) * 1000
    )
    assert ends_at_from_api == ends_at.replace(microsecond=(ends_at.microsecond // 1000) * 1000)

    # 4. Staff reschedules published session -> student receives group_session.rescheduled
    new_starts = starts_at + timedelta(hours=3)
    new_ends = new_starts + timedelta(hours=1)
    patch_res = staff_client.patch(
        f"/api/v1/group-sessions/{session.id}",
        data=json.dumps(
            {
                "starts_at": new_starts.isoformat(),
                "ends_at": new_ends.isoformat(),
            }
        ),
        content_type="application/json",
        **csrf(staff_client),
    )
    assert patch_res.status_code == 200, patch_res.content

    resched_notif = Notification.objects.filter(
        recipient=student,
        event_code="group_session.rescheduled",
        target_id=session.id,
    ).first()
    assert resched_notif is not None
    assert resched_notif.source_type == "group_session_schedule_v2"
    from compass.notifications.delivery import claim_email_delivery
    from compass.notifications.models import EmailDelivery, EmailDeliveryStatus

    stale_email = EmailDelivery.objects.get(notification=resched_notif)

    # A later reschedule invalidates the earlier queued and displayed notice.
    later_starts = new_starts + timedelta(hours=3)
    later_ends = later_starts + timedelta(hours=1)
    second_patch = staff_client.patch(
        f"/api/v1/group-sessions/{session.id}",
        data=json.dumps(
            {
                "starts_at": later_starts.isoformat(),
                "ends_at": later_ends.isoformat(),
            }
        ),
        content_type="application/json",
        **csrf(staff_client),
    )
    assert second_patch.status_code == 200, second_patch.content
    resched_notif.refresh_from_db()
    from compass.notifications.current import notification_is_current

    assert notification_is_current(resched_notif) is False
    assert claim_email_delivery(stale_email.pk) is None
    stale_email.refresh_from_db()
    assert stale_email.status == EmailDeliveryStatus.CANCELLED
    assert stale_email.failure_code == "source_ineligible"
    notifications = student_client.get("/api/v1/notifications").json()["items"]
    stale_view = next(item for item in notifications if item["id"] == str(resched_notif.id))
    assert stale_view["is_current"] is False
    assert stale_view["title"] == "Group Session schedule updated again"
    assert "current details" in stale_view["message"]

    # Replaced facilitators stay visible in a registrant's history. A cancelled
    # registration retains the event reason but no longer exposes the online URL.
    update_group_session(
        session_id=session.id,
        actor=counselor,
        facilitators=[
            {
                "kind": "EXTERNAL",
                "internal_user_id": None,
                "external_display_name": "Community Speaker",
                "is_lead": True,
            }
        ],
    )
    cancel_group_session(
        session_id=session.id,
        actor=counselor,
        reason="The event organizer cancelled this seminar.",
    )
    historical_detail = student_client.get(f"/api/v1/group-sessions/{session.id}")
    assert historical_detail.status_code == 200
    history_data = historical_detail.json()
    assert history_data["status"] == GroupSessionStatus.CANCELLED
    assert history_data["cancellation_reason"] == "The event organizer cancelled this seminar."
    assert history_data["venue_or_meeting_url"] == ""
    facilitator_history = {
        item["display_name"]: item["is_current"] for item in history_data["facilitators"]
    }
    assert facilitator_history[counselor.get_full_name().strip()] is False
    assert facilitator_history["Community Speaker"] is True


@pytest.mark.django_db
def test_group_session_student_eligibility_and_cancelled_attendance_guard(
    group_service, counselor, student
):
    from compass.accounts.models import StudentLifecycleStatus

    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Eligibility & Attendance Guard Session",
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    # Non-current student cannot register
    alumni = make_user("alumni_gs@example.test", "STUDENT")
    alumni.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    alumni.save(update_fields=["student_lifecycle_status"])

    with pytest.raises(ValidationError, match="Current Student lifecycle is required"):
        register_student(session_id=session.id, student=alumni)

    # Current student registers then cancels -> attendance rejected on cancelled registration
    reg = register_student(session_id=session.id, student=student)
    cancel_student_registration(session_id=session.id, student=student, reason="Cannot attend")

    with pytest.raises(ValidationError, match="Active registration not found for this session"):
        record_attendance(
            session_id=session.id,
            actor=counselor,
            records=[{"registration_id": reg.id, "attended": True}],
        )


@pytest.mark.django_db(transaction=True)
def test_group_session_concurrent_registration_capacity_enforcement():
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connections

    counselor = make_user("concurrent_counselor_gs@example.test", "COUNSELOR")
    s1 = make_user("concurrent_s1_gs@example.test", "STUDENT")
    s2 = make_user("concurrent_s2_gs@example.test", "STUDENT")

    svc = create_service(
        code="CONCURRENT_GS_WORKSHOP",
        name="Concurrent Capacity Workshop",
        description="Concurrency test workshop.",
        delivery_modes=["IN_PERSON"],
        booking_pathways=[BookingPathwayCode.GROUP_SESSION],
        provider_coverage="ALL_COUNSELORS",
        context=AuditContext.user(counselor),
    )
    svc = set_service_active(
        service_id=svc.pk, is_active=True, context=AuditContext.user(counselor)
    )

    now = timezone.now()
    session = create_group_session(
        service_id=svc.id,
        organizer=counselor,
        title="Single Seat Workshop",
        starts_at=now + timedelta(days=4),
        ends_at=now + timedelta(days=4, hours=1),
        capacity=1,
        facilitator_ids=[counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)

    def attempt_register(student_user: User) -> str:
        try:
            register_student(session_id=session.id, student=student_user)
            return "registered"
        except ValidationError:
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(attempt_register, [s1, s2]))

    assert outcomes == ["conflict", "registered"]
    assert (
        GroupSessionRegistration.objects.filter(
            group_session=session, status=RegistrationStatus.REGISTERED
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_group_session_draft_withdrawal_preserves_record_and_audit(group_service, counselor):
    import json

    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Draft to Withdraw",
        starts_at=now + timedelta(days=5),
        ends_at=now + timedelta(days=5, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )

    client = auth_client(counselor, recent_mfa=True)
    legacy_delete = client.delete(
        f"/api/v1/group-sessions/{session.id}",
        **csrf(client),
    )
    assert legacy_delete.status_code in (404, 405)
    assert session.__class__.objects.filter(pk=session.pk).exists()

    response = client.post(
        f"/api/v1/group-sessions/{session.id}/withdraw",
        data=json.dumps({"reason": "Planning changed"}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 200, response.content
    withdrawn = session.__class__.objects.get(pk=session.pk)

    assert withdrawn.pk == session.pk
    assert withdrawn.status == GroupSessionStatus.CANCELLED
    assert withdrawn.cancelled_at is not None
    assert withdrawn.cancellation_reason == "Planning changed"
    assert withdrawn.facilitators.count() == 1
    with pytest.raises(ProtectedError):
        withdrawn.delete()
    assert (
        AuditEvent.objects.filter(
            action=GROUP_SESSION_WITHDRAWN,
            target_id=str(session.id),
        ).count()
        == 1
    )
    with pytest.raises(ValidationError):
        withdraw_group_session(session_id=session.id, actor=counselor)
    assert (
        AuditEvent.objects.filter(
            action=GROUP_SESSION_WITHDRAWN,
            target_id=str(session.id),
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_group_session_concurrent_withdrawal_records_one_transition(group_service, counselor):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connections

    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Concurrent Draft Withdrawal",
        starts_at=timezone.now() + timedelta(days=6),
        ends_at=timezone.now() + timedelta(days=6, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )

    def withdraw() -> str:
        try:
            withdraw_group_session(session_id=session.id, actor=counselor)
            return "withdrawn"
        except ValidationError:
            return "already_transitioned"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: withdraw(), range(2)))

    assert outcomes == ["already_transitioned", "withdrawn"]
    assert session.__class__.objects.get(pk=session.pk).status == GroupSessionStatus.CANCELLED
    assert (
        AuditEvent.objects.filter(
            action=GROUP_SESSION_WITHDRAWN,
            target_id=str(session.id),
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_postgresql_prevents_physical_deletion_of_group_session(group_service, counselor):
    from django.db import DatabaseError, connection, transaction

    if connection.vendor != "postgresql":
        pytest.skip("The direct-delete guard is PostgreSQL-specific.")

    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Protected Draft",
        starts_at=timezone.now() + timedelta(days=7),
        ends_at=timezone.now() + timedelta(days=7, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )
    from compass.group_sessions.models import GroupSession

    table = connection.ops.quote_name(GroupSession._meta.db_table)
    primary_key = connection.ops.quote_name(GroupSession._meta.pk.column)

    with pytest.raises(DatabaseError, match="operational records and cannot be deleted"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE {primary_key} = %s", [session.pk])

    assert GroupSession.objects.filter(pk=session.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_postgresql_preserves_removed_facilitator_identity_on_direct_delete(
    group_service, counselor
):
    from django.db import connection

    from compass.group_sessions.models import GroupSessionFacilitator

    if connection.vendor != "postgresql":
        pytest.skip("The facilitator history trigger is PostgreSQL-specific.")

    session = create_group_session(
        service_id=group_service.pk,
        organizer=counselor,
        title="Retain Facilitator History",
        starts_at=timezone.now() + timedelta(days=7),
        ends_at=timezone.now() + timedelta(days=7, hours=1),
        capacity=10,
        facilitator_ids=[counselor.pk],
    )
    facilitator = session.facilitators.get()
    table = connection.ops.quote_name(GroupSessionFacilitator._meta.db_table)
    primary_key = connection.ops.quote_name(GroupSessionFacilitator._meta.pk.column)

    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE {primary_key} = %s", [facilitator.pk])

    facilitator.refresh_from_db()
    assert facilitator.removed_at is not None
    assert facilitator.display_name_snapshot == counselor.get_full_name().strip()


@pytest.mark.django_db
def test_group_session_lifecycle_migration_refuses_rollback_while_history_exists(
    group_service, counselor
):
    from importlib import import_module

    from django.apps import apps
    from django.db import connection

    create_group_session(
        service_id=group_service.pk,
        organizer=counselor,
        title="Retain Group Session Lifecycle",
        starts_at=timezone.now() + timedelta(days=9),
        ends_at=timezone.now() + timedelta(days=9, hours=1),
        capacity=5,
        facilitator_ids=[counselor.pk],
    )
    migration = import_module(
        "compass.group_sessions.migrations.0002_alter_groupsessionfacilitator_group_session"
    )

    with connection.schema_editor() as schema_editor:
        with pytest.raises(RuntimeError, match="Group Session history exists"):
            migration.allow_group_session_deletion_migration_reverse(apps, schema_editor)


@pytest.mark.django_db
def test_group_session_staff_scope_and_facilitator_participant_privacy(
    group_service, counselor, other_counselor, student
):
    import json

    from compass.accounts.models import Designation
    from compass.group_sessions.models import GroupSessionAttendance

    stranger = make_user("stranger-gs@example.test", "COUNSELOR")
    head = make_user("head-stranger-gs@example.test", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Scoped Workshop",
        starts_at=now + timedelta(days=6),
        ends_at=now + timedelta(days=6, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id, other_counselor.id],
    )
    publish_group_session(session_id=session.id, actor=counselor)
    registration = register_student(session_id=session.id, student=student)
    record_attendance(
        session_id=session.id,
        actor=counselor,
        records=[
            {
                "registration_id": registration.id,
                "attended": True,
                "notes": "Restricted staff note",
            }
        ],
    )

    facilitator_client = auth_client(other_counselor, recent_mfa=True)
    outsider_client = auth_client(stranger, recent_mfa=True)
    head_client = auth_client(head, recent_mfa=True)

    facilitator_detail = facilitator_client.get(f"/api/v1/group-sessions/{session.id}")
    assert facilitator_detail.status_code == 200
    assert facilitator_detail.json()["can_view"] is True
    assert facilitator_detail.json()["can_manage"] is False
    assert facilitator_detail.json()["can_record_attendance"] is True
    assert facilitator_detail.json()["can_export_roster"] is False

    facilitator_roster = facilitator_client.get(
        f"/api/v1/group-sessions/{session.id}/registrations"
    )
    assert facilitator_roster.status_code == 200
    participant = facilitator_roster.json()[0]
    assert participant["student_name"] == student.get_full_name()
    assert participant["student_id"] is None
    assert participant["student_email"] is None
    assert participant["registered_at"] is None
    assert participant["attendance_notes"] is None

    denied_export = facilitator_client.get(f"/api/v1/group-sessions/{session.id}/roster/export")
    assert denied_export.status_code == 404

    denied_notes = facilitator_client.post(
        f"/api/v1/group-sessions/{session.id}/attendance",
        data=json.dumps(
            {
                "records": [
                    {
                        "registration_id": str(registration.id),
                        "attended": False,
                        "notes": "Attempted unauthorized note edit",
                    }
                ]
            }
        ),
        content_type="application/json",
        **csrf(facilitator_client),
    )
    assert denied_notes.status_code == 422
    attendance = GroupSessionAttendance.objects.get(registration=registration)
    assert attendance.notes == "Restricted staff note"
    assert attendance.attended is True

    outsider_detail = outsider_client.get(f"/api/v1/group-sessions/{session.id}")
    head_detail = head_client.get(f"/api/v1/group-sessions/{session.id}")
    assert outsider_detail.status_code == 404
    assert head_detail.status_code == 404
    assert str(session.id) not in {
        item["id"] for item in outsider_client.get("/api/v1/group-sessions").json()
    }
    assert (
        outsider_client.get(f"/api/v1/group-sessions/{session.id}/registrations").status_code == 404
    )
    assert (
        outsider_client.get(f"/api/v1/group-sessions/{session.id}/roster/export").status_code == 404
    )
    assert (
        outsider_client.patch(
            f"/api/v1/group-sessions/{session.id}",
            data=json.dumps({"title": "Unauthorized edit"}),
            content_type="application/json",
            **csrf(outsider_client),
        ).status_code
        == 404
    )
    assert (
        outsider_client.post(
            f"/api/v1/group-sessions/{session.id}/attendance",
            data=json.dumps(
                {"records": [{"registration_id": str(registration.id), "attended": False}]}
            ),
            content_type="application/json",
            **csrf(outsider_client),
        ).status_code
        == 404
    )

    metrics = get_group_session_metrics(actor=other_counselor, service_id=group_service.id)
    assert metrics["total_sessions"] == 0
    assert metrics["total_registrations"] == 0


@pytest.mark.django_db
def test_group_session_gss_and_supervisor_are_limited_to_direct_responsibility(
    group_service, counselor, other_counselor
):
    gss = make_user("events-gss@example.test", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=gss,
        title="GSS Organized Workshop",
        starts_at=now + timedelta(days=7),
        ends_at=now + timedelta(days=7, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )

    published = publish_group_session(session_id=session.id, actor=counselor)
    assert published.status == GroupSessionStatus.PUBLISHED
    assert get_group_session_metrics(actor=counselor)["total_sessions"] == 1
    assert get_group_session_metrics(actor=other_counselor)["total_sessions"] == 0
    with pytest.raises(ValidationError, match="Group session not found"):
        complete_group_session(session_id=session.id, actor=other_counselor)


@pytest.mark.django_db
def test_group_session_current_account_and_capability_are_rechecked(group_service, counselor):
    from compass.accounts.models import UserCapabilityOverride
    from compass.accounts.services import set_user_capability_override

    now = timezone.now()
    session = create_group_session(
        service_id=group_service.id,
        organizer=counselor,
        title="Authority Recheck",
        starts_at=now + timedelta(days=8),
        ends_at=now + timedelta(days=8, hours=1),
        capacity=10,
        facilitator_ids=[counselor.id],
    )

    set_user_capability_override(
        user=counselor,
        capability="appointments.manage",
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Regression test capability revocation",
    )
    client = auth_client(counselor, recent_mfa=True)
    assert client.get("/api/v1/group-sessions").status_code == 403
    assert client.get(f"/api/v1/group-sessions/{session.id}").status_code == 403
