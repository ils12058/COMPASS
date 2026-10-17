"""Tests for Group Sessions, Facilitators, Registration, Capacity, Attendance, and Metrics."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.actions import (
    GROUP_SESSION_ATTENDANCE_CORRECTED,
    GROUP_SESSION_CREATED,
    GROUP_SESSION_PUBLISHED,
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
)
from compass.notifications.models import Notification
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
    assert session.facilitators.first().counselor == counselor
    assert session.facilitators.first().is_lead is True

    audit = AuditEvent.objects.filter(
        action=GROUP_SESSION_CREATED, target_id=str(session.id)
    ).first()
    assert audit is not None
    assert audit.target_type == "service.group.session"


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
    completed = complete_group_session(session_id=session.id, actor=counselor)
    assert completed.status == GroupSessionStatus.COMPLETED


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

    metrics = get_group_session_metrics(service_id=group_service.id)
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

    # 1. Unregistered student does NOT see online meeting URL in /discover or /{id}
    disc_res = student_client.get("/api/v1/group-sessions/discover")
    assert disc_res.status_code == 200
    disc_item = next(s for s in disc_res.json() if s["id"] == str(session.id))
    assert disc_item["venue_or_meeting_url"] == ""

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

    disc_after = student_client.get("/api/v1/group-sessions/discover")
    disc_item_after = next(s for s in disc_after.json() if s["id"] == str(session.id))
    assert disc_item_after["venue_or_meeting_url"] == secret_url

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
    assert my_reg["attended"] is True
    assert my_reg["attendance_notes"] is None

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

    with pytest.raises(ValidationError, match="Active registration .* not found in this session"):
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
