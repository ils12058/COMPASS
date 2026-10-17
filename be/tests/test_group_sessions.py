"""Comprehensive tests for Group Sessions, Facilitators, Registration, Capacity, Attendance, and Metrics."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    GROUP_SESSION_ATTENDANCE_CORRECTED,
    GROUP_SESSION_ATTENDANCE_RECORDED,
    GROUP_SESSION_CANCELLED,
    GROUP_SESSION_COMPLETED,
    GROUP_SESSION_CREATED,
    GROUP_SESSION_PUBLISHED,
    GROUP_SESSION_REGISTERED,
    GROUP_SESSION_REGISTRATION_CANCELLED,
    GROUP_SESSION_UPDATED,
)
from compass.audit.models import AuditEvent
from compass.group_sessions.models import (
    GroupSession,
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
    ServiceBookingPathway,
    ServiceProviderCoverage,
)


from django.core.management import call_command
from compass.accounts.models import Role, User


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


from compass.audit.context import AuditContext
from compass.service_catalog.services import create_service, set_service_active


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
    cancel_student_registration(
        session_id=session.id, student=student, reason="Schedule conflict"
    )
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
def test_session_cancellation_cascades_to_registrations(group_service, counselor, student, student2):
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
    notifs = Notification.objects.filter(
        event_code="group_session.cancelled", target_id=session.id
    )
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
    attendances = record_attendance(
        session_id=session.id, actor=counselor, records=records
    )
    assert len(attendances) == 2

    att1 = GroupSessionAttendance.objects.get(registration=reg1)
    att2 = GroupSessionAttendance.objects.get(registration=reg2)
    assert att1.attended is True
    assert att2.attended is False

    # Correction
    corrected_records = [
        {"registration_id": reg2.id, "attended": True, "notes": "Arrived late with excuse"},
    ]
    record_attendance(
        session_id=session.id, actor=counselor, records=corrected_records
    )
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
