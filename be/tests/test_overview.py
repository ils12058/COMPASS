from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.appointments.models import Appointment, AppointmentStatus
from compass.authentication.sessions import create_auth_session
from compass.call_slips.models import CallSlip, CallSlipDestinationType
from compass.good_moral.models import GoodMoralRequest, GoodMoralStatus, GoodMoralVariant
from compass.institutional_forms.models import FormFamily, FormRevision, FormRevisionStatus
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
from compass.notifications.policy import NotificationPolicy
from compass.organization.models import (
    AcademicYear,
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.privacy_governance.models import (
    PrivacyIncident,
    PrivacyIncidentStatus,
    PrivacyReview,
    PrivacyReviewStatus,
    ProcessingActivity,
)
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import Service


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    role: str,
    *,
    lifecycle: str | None = None,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        last_name="User",
    )
    if lifecycle is not None:
        user.student_lifecycle_status = lifecycle
        user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def make_head(email: str = "overview-head@example.edu") -> User:
    user = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def make_dpo(email: str = "overview-dpo@example.edu") -> User:
    user = make_user(email, "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="DPO"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def make_service(code: str = "OVERVIEW_SERVICE") -> Service:
    return Service.objects.create(
        code=code,
        name=code.replace("_", " ").title(),
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        is_active=True,
    )


def make_revision(key: str) -> FormRevision:
    family = FormFamily.objects.create(key=key, title=key.replace("_", " ").title())
    return FormRevision.objects.create(
        family=family,
        official_code=f"TEST-{key.upper()}",
        official_revision="0",
        internal_schema_version=1,
        status=FormRevisionStatus.ACTIVE,
    )


def make_inventory(student: User, *, suffix: str) -> StudentInventory:
    year, _ = AcademicYear.objects.get_or_create(label="2026-2027", defaults={"is_current": True})
    revision = make_revision(f"overview_inventory_{suffix}")
    return StudentInventory.objects.create(
        student=student,
        academic_year=year,
        form_revision=revision,
        full_name_snapshot=student.get_full_name(),
    )


def make_appointment(
    *,
    code: str,
    student: User,
    provider: User,
    service: Service,
    starts_at,
    status: str = AppointmentStatus.SCHEDULED,
) -> Appointment:
    terminal: dict[str, object] = {}
    if status == AppointmentStatus.CANCELLED:
        terminal = {"cancelled_at": timezone.now(), "cancelled_by": student}
    elif status == AppointmentStatus.COMPLETED:
        terminal = {"completed_at": timezone.now(), "completed_by": provider}
    elif status == AppointmentStatus.NO_SHOW:
        terminal = {"no_show_at": timezone.now(), "no_show_by": provider}
    return Appointment.objects.create(
        reference_code=code,
        student=student,
        provider=provider,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=status,
        cancellation_cutoff_minutes=30,
        created_by=student,
        **terminal,
    )


def make_call_slip(
    *,
    student: User,
    issuer: User,
    revision: FormRevision,
    completed: bool = False,
    voided: bool = False,
) -> CallSlip:
    return CallSlip.objects.create(
        student=student,
        student_name_snapshot=student.get_full_name(),
        course_year_snapshot="BSIS 4",
        destination_type=CallSlipDestinationType.GUIDANCE_OFFICE,
        report_at=timezone.now() + timedelta(days=1),
        issued_by=issuer,
        issued_by_name_snapshot=issuer.get_full_name(),
        form_revision=revision,
        interview_ended_at=timezone.now() if completed else None,
        voided_at=timezone.now() if voided else None,
        voided_by=issuer if voided else None,
        void_reason="Superseded test slip" if voided else "",
    )


def make_good_moral(
    *,
    student: User,
    status: str,
    issuer: User,
    revision: FormRevision,
) -> GoodMoralRequest:
    values: dict[str, object] = {
        "student": student,
        "variant": GoodMoralVariant.GRADUATE,
        "status": status,
        "applicant_name_snapshot": student.get_full_name(),
        "degree_snapshot": "BS Information Systems",
        "graduation_date": date(2026, 6, 30),
    }
    if status == GoodMoralStatus.CANCELLED:
        values.update(
            cancelled_at=timezone.now(),
            cancelled_by=issuer,
            cancellation_reason="Synthetic cancellation",
        )
    elif status == GoodMoralStatus.ISSUED:
        values.update(
            form_revision=revision,
            issued_at=timezone.now(),
            issued_by=issuer,
            issued_by_name_snapshot=issuer.get_full_name(),
            document_template_key="good_moral_graduate",
            document_template_version=1,
        )
    return GoodMoralRequest.objects.create(**values)


@pytest.mark.django_db
def test_overview_requires_authentication_and_preserves_zero_vs_null() -> None:
    sync_policy()
    student = make_user(
        "overview-student-zero@example.edu",
        "STUDENT",
        lifecycle=StudentLifecycleStatus.CURRENT,
    )

    assert Client().get("/api/v1/overview").status_code == 401

    response = auth_client(student).get("/api/v1/overview")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"generated_at", "student", "guidance", "platform", "privacy"}
    assert body["student"] == {
        "upcoming_appointments_count": 0,
        "routine_intake_draft_count": 0,
        "good_moral_requested_count": 0,
        "active_call_slip_count": 0,
    }
    assert body["guidance"] is None
    assert body["platform"] is None
    assert body["privacy"] is None

    student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    lifecycle_body = auth_client(student).get("/api/v1/overview").json()
    assert lifecycle_body["student"]["routine_intake_draft_count"] is None
    assert lifecycle_body["student"]["upcoming_appointments_count"] == 0


@pytest.mark.django_db
def test_student_overview_counts_exact_actionable_records_only() -> None:
    sync_policy()
    student = make_user(
        "overview-student@example.edu",
        "STUDENT",
        lifecycle=StudentLifecycleStatus.CURRENT,
    )
    other = make_user(
        "overview-other-student@example.edu",
        "STUDENT",
        lifecycle=StudentLifecycleStatus.CURRENT,
    )
    counselor = make_user("overview-counselor@example.edu", "COUNSELOR")
    service = make_service()
    now = timezone.now()

    make_appointment(
        code="OV-APT-1",
        student=student,
        provider=counselor,
        service=service,
        starts_at=now + timedelta(days=1),
    )
    make_appointment(
        code="OV-APT-2",
        student=student,
        provider=counselor,
        service=service,
        starts_at=now - timedelta(days=1),
    )
    make_appointment(
        code="OV-APT-3",
        student=student,
        provider=counselor,
        service=service,
        starts_at=now + timedelta(days=2),
        status=AppointmentStatus.CANCELLED,
    )
    make_appointment(
        code="OV-APT-4",
        student=other,
        provider=counselor,
        service=service,
        starts_at=now + timedelta(days=1),
    )

    own_inventory = make_inventory(student, suffix="own")
    other_inventory = make_inventory(other, suffix="other")
    RoutineInterview.objects.create(
        student=student,
        counselor=counselor,
        inventory=own_inventory,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        created_by=counselor,
    )
    RoutineInterview.objects.create(
        student=student,
        counselor=counselor,
        inventory=own_inventory,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=now,
        created_by=counselor,
    )
    RoutineInterview.objects.create(
        student=other,
        counselor=counselor,
        inventory=other_inventory,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        created_by=counselor,
    )

    shared_revision = make_revision("overview_documents")
    make_good_moral(
        student=student,
        status=GoodMoralStatus.REQUESTED,
        issuer=counselor,
        revision=shared_revision,
    )
    make_good_moral(
        student=student,
        status=GoodMoralStatus.CANCELLED,
        issuer=counselor,
        revision=shared_revision,
    )
    make_good_moral(
        student=student,
        status=GoodMoralStatus.ISSUED,
        issuer=counselor,
        revision=shared_revision,
    )
    make_good_moral(
        student=other,
        status=GoodMoralStatus.REQUESTED,
        issuer=counselor,
        revision=shared_revision,
    )

    make_call_slip(student=student, issuer=counselor, revision=shared_revision)
    make_call_slip(
        student=student,
        issuer=counselor,
        revision=shared_revision,
        completed=True,
    )
    make_call_slip(
        student=student,
        issuer=counselor,
        revision=shared_revision,
        voided=True,
    )
    make_call_slip(student=other, issuer=counselor, revision=shared_revision)

    body = auth_client(student).get("/api/v1/overview").json()
    assert body["student"] == {
        "upcoming_appointments_count": 1,
        "routine_intake_draft_count": 1,
        "good_moral_requested_count": 1,
        "active_call_slip_count": 1,
    }


@pytest.mark.django_db
def test_guidance_overview_preserves_counselor_gss_and_head_scope() -> None:
    sync_policy()
    counselor = make_user("overview-counselor-a@example.edu", "COUNSELOR")
    other_counselor = make_user("overview-counselor-b@example.edu", "COUNSELOR")
    head = make_head()
    gss = make_user("overview-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student_a = make_user(
        "overview-guidance-student-a@example.edu",
        "STUDENT",
        lifecycle=StudentLifecycleStatus.CURRENT,
    )
    student_b = make_user(
        "overview-guidance-student-b@example.edu",
        "STUDENT",
        lifecycle=StudentLifecycleStatus.CURRENT,
    )
    campus = Campus.objects.create(code="OV-C", name="Overview Campus")
    college_a = College.objects.create(campus=campus, code="OV-A", name="Overview A")
    college_b = College.objects.create(campus=campus, code="OV-B", name="Overview B")
    CounselorResponsibility.objects.create(college=college_a, counselor=counselor)
    CounselorResponsibility.objects.create(college=college_b, counselor=other_counselor)
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    StudentAffiliation.objects.create(student=student_a, college=college_a)
    StudentAffiliation.objects.create(student=student_b, college=college_b)

    service = make_service("OVERVIEW_GUIDANCE")
    now = timezone.now()
    make_appointment(
        code="OV-G-1",
        student=student_a,
        provider=counselor,
        service=service,
        starts_at=now + timedelta(days=1),
    )
    make_appointment(
        code="OV-G-2",
        student=student_b,
        provider=other_counselor,
        service=service,
        starts_at=now + timedelta(days=1),
    )
    make_appointment(
        code="OV-G-3",
        student=student_a,
        provider=counselor,
        service=service,
        starts_at=now - timedelta(days=1),
    )
    make_appointment(
        code="OV-G-4",
        student=student_a,
        provider=head,
        service=service,
        starts_at=now + timedelta(days=2),
    )

    inventory_a = make_inventory(student_a, suffix="guidance-a")
    inventory_b = make_inventory(student_b, suffix="guidance-b")
    RoutineInterview.objects.create(
        student=student_a,
        counselor=counselor,
        inventory=inventory_a,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=now,
        created_by=counselor,
    )
    RoutineInterview.objects.create(
        student=student_a,
        counselor=counselor,
        inventory=inventory_a,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        created_by=counselor,
    )
    RoutineInterview.objects.create(
        student=student_b,
        counselor=other_counselor,
        inventory=inventory_b,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=now,
        created_by=other_counselor,
    )

    revision = make_revision("overview_guidance_documents")
    make_good_moral(
        student=student_a,
        status=GoodMoralStatus.REQUESTED,
        issuer=counselor,
        revision=revision,
    )
    make_good_moral(
        student=student_b,
        status=GoodMoralStatus.CANCELLED,
        issuer=other_counselor,
        revision=revision,
    )
    make_call_slip(student=student_a, issuer=counselor, revision=revision)
    make_call_slip(student=student_b, issuer=other_counselor, revision=revision)
    make_call_slip(
        student=student_a,
        issuer=counselor,
        revision=revision,
        completed=True,
    )

    counselor_body = auth_client(counselor).get("/api/v1/overview").json()["guidance"]
    assert counselor_body == {
        "upcoming_self_appointments_count": 1,
        "upcoming_managed_appointments_count": None,
        "routine_evaluation_pending_count": 1,
        "good_moral_requested_count": 1,
        "active_call_slip_count": 1,
    }

    gss_body = auth_client(gss).get("/api/v1/overview").json()["guidance"]
    assert gss_body == {
        "upcoming_self_appointments_count": None,
        "upcoming_managed_appointments_count": 1,
        "routine_evaluation_pending_count": None,
        "good_moral_requested_count": None,
        "active_call_slip_count": 1,
    }

    head_body = auth_client(head).get("/api/v1/overview").json()["guidance"]
    assert head_body["upcoming_self_appointments_count"] == 1
    assert head_body["upcoming_managed_appointments_count"] is None
    assert head_body["routine_evaluation_pending_count"] == 0
    assert head_body["active_call_slip_count"] == 2


@pytest.mark.django_db
def test_platform_and_privacy_sections_use_compatible_domain_identity() -> None:
    sync_policy()
    admin = make_user("overview-admin@example.edu", "IT_ADMIN")
    recipient = make_user(
        "overview-recipient@example.edu",
        "STUDENT",
        lifecycle=StudentLifecycleStatus.CURRENT,
    )
    for status in (
        EmailDeliveryStatus.PENDING,
        EmailDeliveryStatus.FAILED,
        EmailDeliveryStatus.SENT,
    ):
        notification = Notification.objects.create(
            recipient=recipient,
            event_code=f"overview.{status.lower()}.{uuid4()}",
            policy=NotificationPolicy.MANDATORY_OPERATIONAL,
            title="Overview test",
            message="Overview test",
            source_type="overview_test",
            source_id=uuid4(),
        )
        delivery = EmailDelivery.objects.create(
            notification=notification,
            status=status,
            next_attempt_at=timezone.now() if status == EmailDeliveryStatus.PENDING else None,
            failure_code="transport_error" if status == EmailDeliveryStatus.FAILED else "",
            sent_at=timezone.now() if status == EmailDeliveryStatus.SENT else None,
        )
        assert delivery.pk is not None

    platform = auth_client(admin).get("/api/v1/overview").json()
    assert platform["student"] is None
    assert platform["guidance"] is None
    assert platform["privacy"] is None
    assert platform["platform"] == {
        "email_pending_count": 1,
        "email_due_pending_count": 1,
        "email_failed_count": 1,
        "email_sent_today_count": 1,
    }

    dpo = make_dpo()
    ordinary_officer = make_user("overview-officer@example.edu", "INSTITUTIONAL_OFFICER")
    processing = ProcessingActivity.objects.create(
        code="OVERVIEW",
        name="Overview Processing",
        purpose="Synthetic test purpose",
        data_subject_categories=["Student"],
        personal_data_categories=["Profile"],
        authorized_access_summary="Synthetic",
        safeguards_summary="Synthetic",
    )
    PrivacyReview.objects.create(
        processing_activity=processing,
        review_type="PRIVACY_REVIEW",
        status=PrivacyReviewStatus.OPEN,
        scope_summary="Synthetic",
        reviewed_by=dpo,
    )
    PrivacyReview.objects.create(
        processing_activity=processing,
        review_type="PRIVACY_REVIEW",
        status=PrivacyReviewStatus.RESOLVED,
        scope_summary="Synthetic",
        reviewed_by=dpo,
        resolved_at=timezone.now(),
    )
    for status in (
        PrivacyIncidentStatus.OPEN,
        PrivacyIncidentStatus.ASSESSING,
        PrivacyIncidentStatus.CONTAINED,
        PrivacyIncidentStatus.RESOLVED,
    ):
        PrivacyIncident.objects.create(
            reference_code=f"OV-{status}",
            title=f"{status} incident",
            summary="Synthetic",
            affected_area="Synthetic",
            personal_data_categories=["Profile"],
            status=status,
            discovered_at=timezone.now(),
            resolved_at=timezone.now() if status == PrivacyIncidentStatus.RESOLVED else None,
        )

    privacy = auth_client(dpo).get("/api/v1/overview").json()
    assert privacy["privacy"] == {
        "open_review_count": 1,
        "active_incident_count": 3,
    }
    assert privacy["student"] is None
    assert privacy["guidance"] is None
    assert privacy["platform"] is None

    ordinary = auth_client(ordinary_officer).get("/api/v1/overview").json()
    assert ordinary["student"] is None
    assert ordinary["guidance"] is None
    assert ordinary["platform"] is None
    assert ordinary["privacy"] is None

    set_user_capability_override(
        user=ordinary_officer,
        capability=Capability.objects.get(code="privacy_governance.view"),
        effect="GRANT",
        reason="Synthetic override must not fabricate DPO identity",
    )
    overridden = auth_client(ordinary_officer).get("/api/v1/overview").json()
    assert overridden["privacy"] is None
