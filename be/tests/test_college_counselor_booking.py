"""Targeted tests for ADR-120 College Counselor booking restriction and Head approval flow."""

from __future__ import annotations

import json
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.appointments.counselor_access_models import (
    CounselorBookingRequest,
    CounselorBookingRequestState,
    StudentCounselorApproval,
)
from compass.appointments.counselor_access_services import (
    CounselorBookingHeadUnavailable,
    CounselorRequestDecisionAction,
    change_counselor_approval,
    decide_counselor_booking_request,
    end_counselor_approval,
    resolve_permitted_counselors_for_student,
    submit_counselor_booking_request,
)
from compass.appointments.models import AppointmentStatus
from compass.appointments.services import (
    AppointmentCounselorNotPermitted,
    create_student_appointment,
    list_bookable_slots,
    list_eligible_counselors,
    reschedule_appointment,
)
from compass.audit.models import AuditEvent
from compass.availability.services import replace_office_weekly, replace_provider_weekly
from compass.counseling.case_coverage_models import CaseCoverageState, CounselingCaseCoverage
from compass.counseling.case_models import (
    CounselingCase,
    CounselingCaseOrigin,
    CounselingCaseStatus,
)
from compass.counseling.case_transfer_models import CaseContinuityReason
from compass.notifications.delivery import deliver_email_delivery
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
from compass.notifications.policy import NotificationEvent
from compass.organization.models import Campus, College, CounselorResponsibility
from compass.service_catalog.fixed_slots_services import (
    book_fixed_slot,
    create_fixed_slot,
    list_student_bookable_slots,
)
from compass.service_catalog.models import (
    BookingPathwayCode,
    Service,
    ServiceProviderCoverage,
)
from compass.service_catalog.services import create_service, set_service_active
from compass.student_academics.models import StudentAcademicProfile
from tests.test_appointments import (
    auth_client,
    context,
    csrf,
    future_local_start,
    make_user,
    sync_policy,
    weekly,
)
from tests.test_counseling import create_counseling_service


@pytest.fixture(autouse=True)
def local_email_transport(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)


def _grant_head(user: User) -> None:
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )


def _make_campus_and_college(
    campus_code: str, campus_name: str, college_code: str, college_name: str
) -> tuple[Campus, College]:
    campus = Campus.objects.create(code=campus_code, name=campus_name, is_active=True)
    college = College.objects.create(
        campus=campus, code=college_code, name=college_name, is_active=True
    )
    return campus, college


def _place_student(student: User, college: College) -> StudentAcademicProfile:
    student.student_lifecycle_status = StudentLifecycleStatus.CURRENT
    student.save(update_fields=["student_lifecycle_status"])
    return StudentAcademicProfile.objects.create(
        student=student,
        current_college=college,
    )


def _seed_availability(admin: User, *counselors: User) -> None:
    replace_office_weekly(windows=[weekly()], context=context(admin))
    for counselor in counselors:
        replace_provider_weekly(
            provider_id=counselor.pk,
            windows=[weekly()],
            context=context(admin),
        )


def _counseling_service(admin: User) -> Service:
    service = Service.objects.filter(code="COUNSELING").first()
    if service is not None:
        return service
    return create_counseling_service(admin, active=True)


def _fixed_slot_service(
    admin: User, *, code: str = "CAREER_FIXED", name: str = "Career Fixed Slot"
) -> Service:
    service = create_service(
        code=code,
        name=name,
        booking_pathways=[BookingPathwayCode.FIXED_DATE_SLOT],
        delivery_modes=["IN_PERSON", "ONLINE"],
        provider_coverage=ServiceProviderCoverage.ALL_COUNSELORS,
        context=context(admin),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(admin))


def _setup_world() -> dict[str, object]:
    sync_policy()
    admin = make_user("ccb-admin@example.edu", "IT_ADMIN")
    head = make_user("ccb-head@example.edu", "COUNSELOR", first_name="Helena", last_name="Head")
    _grant_head(head)
    college_counselor = make_user(
        "ccb-college@example.edu", "COUNSELOR", first_name="Clara", last_name="College"
    )
    other_campus_counselor = make_user(
        "ccb-other@example.edu", "COUNSELOR", first_name="Oscar", last_name="Other"
    )
    third_counselor = make_user(
        "ccb-third@example.edu", "COUNSELOR", first_name="Tessa", last_name="Third"
    )
    goa = make_user("ccb-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")

    _, college_a = _make_campus_and_college("MAIN", "Main Campus", "CCS", "College of Computing")
    _, college_b = _make_campus_and_college("WEST", "West Campus", "CBA", "College of Business")
    _, college_unassigned = _make_campus_and_college(
        "NORTH", "North Campus", "COE", "College of Education"
    )

    CounselorResponsibility.objects.create(counselor=college_counselor, college=college_a)
    CounselorResponsibility.objects.create(counselor=other_campus_counselor, college=college_b)

    student = make_user(
        "ccb-student@example.edu",
        "STUDENT",
        institutional_id="2026-0001",
        first_name="Sonia",
        last_name="Student",
    )
    _place_student(student, college_a)

    unassigned_student = make_user(
        "ccb-unassigned@example.edu",
        "STUDENT",
        institutional_id="2026-0002",
        first_name="Uma",
        last_name="Unassigned",
    )
    _place_student(unassigned_student, college_unassigned)

    _seed_availability(admin, head, college_counselor, other_campus_counselor, third_counselor)
    service = _counseling_service(admin)

    return {
        "admin": admin,
        "head": head,
        "college_counselor": college_counselor,
        "other_campus_counselor": other_campus_counselor,
        "third_counselor": third_counselor,
        "goa": goa,
        "college_a": college_a,
        "college_b": college_b,
        "college_unassigned": college_unassigned,
        "student": student,
        "unassigned_student": unassigned_student,
        "service": service,
    }


@pytest.mark.django_db
def test_permitted_list_covers_college_head_fallback_active_case_coverage_and_approval() -> None:
    w = _setup_world()
    student = w["student"]
    unassigned_student = w["unassigned_student"]
    college_counselor = w["college_counselor"]
    other_campus_counselor = w["other_campus_counselor"]
    third_counselor = w["third_counselor"]
    head = w["head"]
    service = w["service"]
    admin = w["admin"]

    # 1. Student with assigned College counselor sees ONLY their College counselor.
    eligible = list_eligible_counselors(
        student=student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    assert [c.user.id for c in eligible] == [college_counselor.id]
    assert eligible[0].is_default is True
    assert eligible[0].is_head_approved is False
    assert other_campus_counselor.id not in {c.user.id for c in eligible}

    # 2. Student whose College has no assigned counselor falls back to the unique active Head.
    fallback_eligible = list_eligible_counselors(
        student=unassigned_student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    assert [c.user.id for c in fallback_eligible] == [head.id]
    assert fallback_eligible[0].is_default is True

    # 3. Active Counseling Case primary (e.g. after transfer) and active coverage counselor
    #    are both permitted; unrelated counselor on another campus is still excluded.
    now = timezone.now()
    active_case = CounselingCase.objects.create(
        reference_code="CC-2026-0001",
        student=student,
        primary_counselor=third_counselor,
        status=CounselingCaseStatus.ACTIVE,
        origin=CounselingCaseOrigin.INTAKE,
        opened_by=third_counselor,
    )
    active_coverage = CounselingCaseCoverage.objects.create(
        reference_code="COV-2026-0001",
        case=active_case,
        primary_counselor=third_counselor,
        receiving_counselor=other_campus_counselor,
        prepared_by=third_counselor,
        reason=CaseContinuityReason.PLANNED_ABSENCE,
        starts_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=3),
        state=CaseCoverageState.ACCEPTED,
        submitted_at=now - timedelta(hours=2),
        authorized_by=head,
        authorized_at=now - timedelta(hours=2),
        authorized_version=1,
        review_expires_at=now + timedelta(days=1),
        decided_by=other_campus_counselor,
        decided_at=now - timedelta(hours=1),
        communication_recorded_by=third_counselor,
    )
    eligible_with_case = list_eligible_counselors(
        student=student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    assert {c.user.id for c in eligible_with_case} == {
        college_counselor.id,
        third_counselor.id,
        other_campus_counselor.id,
    }
    assert eligible_with_case[0].user.id == college_counselor.id

    # Expired coverage no longer grants permission.
    CounselingCaseCoverage.objects.filter(pk=active_coverage.pk).update(
        expires_at=now - timedelta(minutes=5),
        starts_at=now - timedelta(hours=3),
    )
    eligible_after_expiry = list_eligible_counselors(
        student=student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    assert {c.user.id for c in eligible_after_expiry} == {college_counselor.id, third_counselor.id}

    # Closed case primary counselor is no longer permitted.
    CounselingCase.objects.filter(pk=active_case.pk).update(status=CounselingCaseStatus.CLOSED)
    eligible_after_close = list_eligible_counselors(
        student=student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    assert [c.user.id for c in eligible_after_close] == [college_counselor.id]

    # 4. Head-approved counselor appears alongside default and is flagged is_head_approved=True.
    StudentCounselorApproval.objects.create(
        student=student,
        counselor=other_campus_counselor,
        approved_by=head,
    )
    eligible_with_approval = list_eligible_counselors(
        student=student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    by_id = {c.user.id: c for c in eligible_with_approval}
    assert set(by_id) == {college_counselor.id, other_campus_counselor.id}
    assert by_id[college_counselor.id].is_default is True
    assert by_id[college_counselor.id].is_head_approved is False
    assert by_id[other_campus_counselor.id].is_default is False
    assert by_id[other_campus_counselor.id].is_head_approved is True

    # 5. Service qualification still intersects on top: a selected-counselors service qualified
    #    only for third_counselor returns an EMPTY list (never offers unrelated counselors).
    restricted_service = create_service(
        code="SPECIALIZED",
        name="Specialized Counseling",
        booking_pathways=[BookingPathwayCode.FLEXIBLE_APPOINTMENT],
        default_appointment_duration_minutes=60,
        delivery_modes=["IN_PERSON"],
        provider_coverage=ServiceProviderCoverage.SELECTED_COUNSELORS,
        selected_counselor_ids=[third_counselor.id],
        context=context(admin),
    )
    restricted_service = set_service_active(
        service_id=restricted_service.pk, is_active=True, context=context(admin)
    )
    assert (
        list_eligible_counselors(
            student=student, service_id=restricted_service.pk, delivery_mode="IN_PERSON"
        )
        == ()
    )


@pytest.mark.django_db
def test_server_refuses_non_permitted_provider_in_normal_and_fixed_slot_booking() -> None:
    w = _setup_world()
    admin = w["admin"]
    student = w["student"]
    college_counselor = w["college_counselor"]
    other_campus_counselor = w["other_campus_counselor"]
    service = w["service"]

    start = future_local_start(hour=10, days=7)
    target_date = start.astimezone(ZoneInfo("Asia/Manila")).date()

    # Service-layer normal booking refusal
    with pytest.raises(AppointmentCounselorNotPermitted):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=other_campus_counselor.id,
            delivery_mode="IN_PERSON",
            starts_at=start,
            context=context(student),
        )

    # Service-layer slot discovery refusal
    with pytest.raises(AppointmentCounselorNotPermitted):
        list_bookable_slots(
            student=student,
            service_id=service.pk,
            provider_id=other_campus_counselor.id,
            delivery_mode="IN_PERSON",
            target_date=target_date,
        )

    # HTTP normal booking refusal (403 appointment_counselor_not_permitted)
    student_client = auth_client(student)
    headers = csrf(student_client)
    resp = student_client.post(
        "/api/v1/appointments",
        data=json.dumps(
            {
                "service_id": str(service.id),
                "provider_id": str(other_campus_counselor.id),
                "delivery_mode": "IN_PERSON",
                "starts_at": start.isoformat(),
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="ccb-refuse-key-1",
        **headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "appointment_counselor_not_permitted"

    # HTTP slot discovery refusal
    slots_resp = student_client.get(
        f"/api/v1/appointments/booking/slots?service_id={service.id}"
        f"&provider_id={other_campus_counselor.id}&delivery_mode=IN_PERSON"
        f"&date={target_date.isoformat()}"
    )
    assert slots_resp.status_code == 403
    assert slots_resp.json()["error"]["code"] == "appointment_counselor_not_permitted"

    # Booking with the student's own College counselor succeeds
    ok_resp = student_client.post(
        "/api/v1/appointments",
        data=json.dumps(
            {
                "service_id": str(service.id),
                "provider_id": str(college_counselor.id),
                "delivery_mode": "IN_PERSON",
                "starts_at": start.isoformat(),
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="ccb-allow-key-1",
        **headers,
    )
    assert ok_resp.status_code == 201

    # Fixed-date slots: only slots for permitted counselors are listed, and direct booking fails.
    fixed_service = _fixed_slot_service(admin, code="FIXED_REFUSE")
    slot_start = future_local_start(hour=13, days=14)
    slot_end = slot_start + timedelta(hours=1)
    permitted_slot = create_fixed_slot(
        service_id=fixed_service.id,
        provider_id=college_counselor.id,
        starts_at=slot_start,
        ends_at=slot_end,
        delivery_mode="IN_PERSON",
        actor=college_counselor,
        context=context(college_counselor),
    )
    forbidden_slot = create_fixed_slot(
        service_id=fixed_service.id,
        provider_id=other_campus_counselor.id,
        starts_at=slot_start,
        ends_at=slot_end,
        delivery_mode="IN_PERSON",
        actor=other_campus_counselor,
        context=context(other_campus_counselor),
    )
    visible_slots = list_student_bookable_slots(service_id=fixed_service.id, student=student)
    assert [slot.id for slot in visible_slots] == [permitted_slot.id]

    with pytest.raises(AppointmentCounselorNotPermitted):
        book_fixed_slot(
            slot_id=forbidden_slot.id,
            service_id=fixed_service.id,
            student=student,
            context=context(student),
        )

    fixed_http_resp = student_client.post(
        f"/api/v1/services/{fixed_service.id}/slots/{forbidden_slot.id}/book",
        **headers,
    )
    assert fixed_http_resp.status_code == 403
    assert fixed_http_resp.json()["error"]["code"] == "appointment_counselor_not_permitted"


@pytest.mark.django_db
def test_full_request_approval_change_end_decline_deactivation_and_confidentiality() -> None:
    w = _setup_world()
    admin = w["admin"]
    head = w["head"]
    student = w["student"]
    college_counselor = w["college_counselor"]
    other_campus_counselor = w["other_campus_counselor"]
    third_counselor = w["third_counselor"]
    goa = w["goa"]
    service = w["service"]

    secret_reason = "CONFIDENTIAL_REASON_NEVER_LEAK_847291"

    student_client = auth_client(student)
    student_headers = csrf(student_client)
    head_client = auth_client(head)
    head_headers = csrf(head_client)

    # 1. Submit request (preferred counselor + confidential reason)
    create_resp = student_client.post(
        "/api/v1/appointments/booking/counselor-request",
        data=json.dumps(
            {
                "preferred_counselor_id": str(other_campus_counselor.id),
                "reason": secret_reason,
            }
        ),
        content_type="application/json",
        **student_headers,
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    request_id = created_data["id"]
    assert created_data["state"] == "PENDING"
    assert secret_reason not in json.dumps(created_data)

    # Reason is encrypted at rest (ciphertext does not contain plaintext).
    db_req = CounselorBookingRequest.objects.get(pk=request_id)
    assert db_req.reason_ciphertext
    assert secret_reason not in db_req.reason_ciphertext

    # Student GET state shows pending request and NEVER exposes reason.
    state_resp = student_client.get("/api/v1/appointments/booking/counselor-request")
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["pending_request"]["id"] == request_id
    assert secret_reason not in json.dumps(state_data)

    # At most one pending request per student (409 on second).
    dup_resp = student_client.post(
        "/api/v1/appointments/booking/counselor-request",
        data=json.dumps({"preferred_counselor_id": str(third_counselor.id)}),
        content_type="application/json",
        **student_headers,
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "counselor_request_pending"

    # Head sees pending request in Work Queue and Overview count.
    work_resp = head_client.get("/api/v1/work")
    assert work_resp.status_code == 200
    work_items = work_resp.json()["items"]
    assert any(
        item["kind"] == "COUNSELOR_BOOKING_REQUEST" and item["source_id"] == request_id
        for item in work_items
    )
    assert secret_reason not in work_resp.content.decode()

    overview_resp = head_client.get("/api/v1/overview")
    assert overview_resp.status_code == 200
    assert overview_resp.json()["guidance"]["pending_counselor_requests_count"] == 1

    # Head receives in-app notification + content-free email (no student name, no reason).
    head_notice = Notification.objects.get(
        recipient=head, event_code=NotificationEvent.COUNSELOR_BOOKING_REQUEST_SUBMITTED
    )
    assert secret_reason not in (head_notice.title + head_notice.message)
    assert "Sonia" not in (head_notice.title + head_notice.message)
    head_delivery = EmailDelivery.objects.get(notification=head_notice)
    assert deliver_email_delivery(head_delivery.pk) == EmailDeliveryStatus.SENT
    assert len(mail.outbox) == 1
    head_email = mail.outbox[0]
    assert "A student asked for a different counselor" in head_email.subject
    assert f"https://portal.example/portal/appointments/counselor-requests/{request_id}" in (
        head_email.body
    )
    email_blob = (
        head_email.subject + head_email.body + "".join(a[0] for a in head_email.alternatives)
    )
    assert secret_reason not in email_blob
    assert "Sonia" not in email_blob
    assert "2026-0001" not in email_blob

    # Audit events NEVER contain reason plaintext.
    for event in AuditEvent.objects.all():
        assert secret_reason not in json.dumps(event.metadata)

    # Confidentiality: ONLY the Head can view the request detail (and reason).
    for non_head in (college_counselor, other_campus_counselor, goa, admin, student):
        client = auth_client(non_head)
        assert (
            client.get(f"/api/v1/appointments/counselor-requests/{request_id}").status_code == 403
        )
        assert client.get("/api/v1/appointments/counselor-requests").status_code == 403
        assert client.get("/api/v1/appointments/counselor-approvals").status_code == 403

    # Head list does NOT include reason; Head detail DOES include student, college, default, reason.
    list_resp = head_client.get("/api/v1/appointments/counselor-requests?state=PENDING")
    assert list_resp.status_code == 200
    assert secret_reason not in list_resp.content.decode()
    assert len(list_resp.json()["items"]) == 1

    detail_resp = head_client.get(f"/api/v1/appointments/counselor-requests/{request_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["reason"] == secret_reason
    assert detail["student"]["college_name"] == "College of Computing"
    assert detail["default_counselor"]["id"] == str(college_counselor.id)
    assert detail["preferred_counselor"]["id"] == str(other_campus_counselor.id)

    # 2. Head approves the request for other_campus_counselor.
    mail.outbox.clear()
    approve_resp = head_client.post(
        f"/api/v1/appointments/counselor-requests/{request_id}/decide",
        data=json.dumps(
            {
                "action": "APPROVE",
                "approved_counselor_id": str(other_campus_counselor.id),
                "note": "Approved for this term and onward.",
                "expected_version": detail["version"],
            }
        ),
        content_type="application/json",
        **head_headers,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["state"] == "APPROVED"
    approval_id = approve_resp.json()["current_approval"]["id"]

    # Student is notified in-app and by content-free email (no reason, no note in email).
    student_notice = Notification.objects.filter(
        recipient=student, event_code=NotificationEvent.COUNSELOR_BOOKING_REQUEST_DECIDED
    ).latest("created_at")
    assert secret_reason not in (student_notice.title + student_notice.message)
    student_delivery = EmailDelivery.objects.get(notification=student_notice)
    assert deliver_email_delivery(student_delivery.pk) == EmailDeliveryStatus.SENT
    assert len(mail.outbox) == 1
    student_email = mail.outbox[0]
    assert "https://portal.example/portal/appointments/book" in student_email.body
    assert secret_reason not in student_email.body
    assert "Approved for this term" not in student_email.body

    # Booking now allows other_campus_counselor — and persists across MULTIPLE appointments.
    first_start = future_local_start(hour=9, days=7)
    first_appt = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=other_campus_counselor.id,
        delivery_mode="IN_PERSON",
        starts_at=first_start,
        context=context(student),
    )
    second_start = future_local_start(hour=11, days=14)
    second_appt = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=other_campus_counselor.id,
        delivery_mode="IN_PERSON",
        starts_at=second_start,
        context=context(student),
    )
    assert first_appt.provider_id == other_campus_counselor.id
    assert second_appt.provider_id == other_campus_counselor.id

    # Fixed-slot booking also allows the approved counselor.
    fixed_service = _fixed_slot_service(admin, code="FIXED_APPR", name="Approved Fixed Slot")
    fixed_start = future_local_start(hour=14, days=21)
    fixed_slot = create_fixed_slot(
        service_id=fixed_service.id,
        provider_id=other_campus_counselor.id,
        starts_at=fixed_start,
        ends_at=fixed_start + timedelta(hours=1),
        delivery_mode="IN_PERSON",
        actor=other_campus_counselor,
        context=context(other_campus_counselor),
    )
    assert fixed_slot.id in {
        s.id for s in list_student_bookable_slots(service_id=fixed_service.id, student=student)
    }
    booked_fixed = book_fixed_slot(
        slot_id=fixed_slot.id,
        service_id=fixed_service.id,
        student=student,
        context=context(student),
    )
    assert booked_fixed.provider_id == other_campus_counselor.id

    # 3. Head changes the approved counselor to third_counselor.
    approvals_resp = head_client.get("/api/v1/appointments/counselor-approvals")
    assert approvals_resp.status_code == 200
    approval_item = approvals_resp.json()["items"][0]
    assert approval_item["id"] == approval_id

    change_resp = head_client.patch(
        f"/api/v1/appointments/counselor-approvals/{approval_id}",
        data=json.dumps(
            {
                "counselor_id": str(third_counselor.id),
                "expected_version": approval_item["version"],
            }
        ),
        content_type="application/json",
        **head_headers,
    )
    assert change_resp.status_code == 200
    assert change_resp.json()["counselor"]["id"] == str(third_counselor.id)
    changed_version = change_resp.json()["version"]

    # Old approved counselor is refused; new approved counselor is permitted.
    assert {
        c.user.id
        for c in list_eligible_counselors(
            student=student, service_id=service.pk, delivery_mode="IN_PERSON"
        )
    } == {college_counselor.id, third_counselor.id}
    with pytest.raises(AppointmentCounselorNotPermitted):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=other_campus_counselor.id,
            delivery_mode="IN_PERSON",
            starts_at=future_local_start(hour=15, days=28),
            context=context(student),
        )

    # 4. Deactivating the approved counselor automatically falls back to the default counselor.
    User.objects.filter(pk=third_counselor.pk).update(is_active=False)
    eligible_deactivated = list_eligible_counselors(
        student=student, service_id=service.pk, delivery_mode="IN_PERSON"
    )
    assert [c.user.id for c in eligible_deactivated] == [college_counselor.id]
    assert eligible_deactivated[0].is_default is True

    # Reactivate third_counselor, then Head ends the approval.
    User.objects.filter(pk=third_counselor.pk).update(is_active=True)
    end_resp = head_client.post(
        f"/api/v1/appointments/counselor-approvals/{approval_id}/end",
        data=json.dumps({"expected_version": changed_version}),
        content_type="application/json",
        **head_headers,
    )
    assert end_resp.status_code == 200
    assert end_resp.json()["ended_at"] is not None

    # Student returns to default counselor only.
    assert [
        c.user.id
        for c in list_eligible_counselors(
            student=student, service_id=service.pk, delivery_mode="IN_PERSON"
        )
    ] == [college_counselor.id]

    # Existing appointments remain intact and can still be rescheduled with the original counselor.
    first_appt.refresh_from_db()
    assert first_appt.status == AppointmentStatus.SCHEDULED
    assert first_appt.provider_id == other_campus_counselor.id
    rescheduled = reschedule_appointment(
        appointment_id=first_appt.pk,
        actor=student,
        starts_at=future_local_start(hour=15, days=7),
        reason=None,
        administrative=False,
        context=context(student),
    )
    assert rescheduled.provider_id == other_campus_counselor.id

    # 5. Student submits another request and Head declines it with a note.
    req2 = submit_counselor_booking_request(
        student=student,
        preferred_counselor_id=other_campus_counselor.id,
        reason="Second confidential reason",
        context=context(student),
    )
    declined = decide_counselor_booking_request(
        actor=head,
        request_id=req2.id,
        action=CounselorRequestDecisionAction.DECLINE,
        approved_counselor_id=None,
        note="Please continue with your College counselor for now.",
        expected_version=req2.version,
        context=context(head),
    )
    assert declined.request.state == CounselorBookingRequestState.DECLINED
    state_after_decline = student_client.get(
        "/api/v1/appointments/booking/counselor-request"
    ).json()
    assert state_after_decline["pending_request"] is None
    assert state_after_decline["latest_decision"]["state"] == "DECLINED"
    assert (
        state_after_decline["latest_decision"]["decision_note"]
        == "Please continue with your College counselor for now."
    )
    assert "Second confidential reason" not in json.dumps(state_after_decline)
    assert [
        c.user.id
        for c in list_eligible_counselors(
            student=student, service_id=service.pk, delivery_mode="IN_PERSON"
        )
    ] == [college_counselor.id]


@pytest.mark.django_db
def test_student_with_head_as_default_can_request_different_counselor() -> None:
    w = _setup_world()
    head = w["head"]
    unassigned_student = w["unassigned_student"]
    college_counselor = w["college_counselor"]
    service = w["service"]

    assert [
        c.user.id
        for c in list_eligible_counselors(
            student=unassigned_student, service_id=service.pk, delivery_mode="IN_PERSON"
        )
    ] == [head.id]

    req = submit_counselor_booking_request(
        student=unassigned_student,
        preferred_counselor_id=college_counselor.id,
        reason="Prefer another counselor",
        context=context(unassigned_student),
    )
    decide_counselor_booking_request(
        actor=head,
        request_id=req.id,
        action=CounselorRequestDecisionAction.APPROVE,
        approved_counselor_id=college_counselor.id,
        note=None,
        expected_version=req.version,
        context=context(head),
    )
    assert {
        c.user.id
        for c in list_eligible_counselors(
            student=unassigned_student, service_id=service.pk, delivery_mode="IN_PERSON"
        )
    } == {head.id, college_counselor.id}


@pytest.mark.django_db
def test_zero_or_two_active_heads_blocks_requests_and_decisions() -> None:
    w = _setup_world()
    head = w["head"]
    student = w["student"]
    other_campus_counselor = w["other_campus_counselor"]

    # Case A: 0 active Heads -> blocked on submission
    User.objects.filter(pk=head.pk).update(is_active=False)
    student_client = auth_client(student)
    headers = csrf(student_client)

    state_zero = student_client.get("/api/v1/appointments/booking/counselor-request").json()
    assert state_zero["head_available"] is False

    resp_zero = student_client.post(
        "/api/v1/appointments/booking/counselor-request",
        data=json.dumps({"preferred_counselor_id": str(other_campus_counselor.id)}),
        content_type="application/json",
        **headers,
    )
    assert resp_zero.status_code == 409
    assert resp_zero.json()["error"]["code"] == "head_guidance_unavailable"
    assert "Guidance Office" in resp_zero.json()["error"]["message"]

    # Restore 1 Head, submit a request, then add a 2nd active Head -> blocked!
    User.objects.filter(pk=head.pk).update(is_active=True)
    req = submit_counselor_booking_request(
        student=student,
        preferred_counselor_id=other_campus_counselor.id,
        reason="Need different counselor",
        context=context(student),
    )
    second_head = make_user("ccb-head2@example.edu", "COUNSELOR", first_name="Henry")
    _grant_head(second_head)

    # Another student cannot submit while two active Heads exist.
    with pytest.raises(CounselorBookingHeadUnavailable):
        submit_counselor_booking_request(
            student=w["unassigned_student"],
            preferred_counselor_id=other_campus_counselor.id,
            reason=None,
            context=context(w["unassigned_student"]),
        )

    # Neither Head can decide while two active Heads exist.
    with pytest.raises(CounselorBookingHeadUnavailable):
        decide_counselor_booking_request(
            actor=head,
            request_id=req.id,
            action=CounselorRequestDecisionAction.APPROVE,
            approved_counselor_id=other_campus_counselor.id,
            note=None,
            expected_version=req.version,
            context=context(head),
        )

    # Overview does not surface pending count to ambiguous Heads.
    overview_two = auth_client(head).get("/api/v1/overview").json()["guidance"]
    assert overview_two["pending_counselor_requests_count"] is None

    # Work queue does not route pending request while two active Heads exist.
    work_two = auth_client(head).get("/api/v1/work").json()["items"]
    assert not any(item["kind"] == "COUNSELOR_BOOKING_REQUEST" for item in work_two)


@pytest.mark.django_db
def test_head_can_book_any_counselor_while_non_head_staff_stays_restricted() -> None:
    w = _setup_world()
    admin = w["admin"]
    head = w["head"]
    goa = w["goa"]
    student = w["student"]
    other_campus_counselor = w["other_campus_counselor"]
    service = w["service"]

    start = future_local_start(hour=10, days=7)

    # Non-Head staff booking on a student's behalf is still bound by the permitted-counselor rule.
    with pytest.raises(AppointmentCounselorNotPermitted):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=other_campus_counselor.id,
            delivery_mode="IN_PERSON",
            starts_at=start,
            actor=goa,
            context=context(goa),
        )

    # The unique active Head can book/arrange an appointment with ANY qualified counselor.
    head_appt = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=other_campus_counselor.id,
        delivery_mode="IN_PERSON",
        starts_at=start,
        actor=head,
        context=context(head),
    )
    assert head_appt.provider_id == other_campus_counselor.id

    # Same rule applies to fixed-slot booking.
    fixed_service = _fixed_slot_service(admin, code="FIXED_HEAD", name="Head Override Fixed Slot")
    slot_start = future_local_start(hour=14, days=14)
    slot = create_fixed_slot(
        service_id=fixed_service.id,
        provider_id=other_campus_counselor.id,
        starts_at=slot_start,
        ends_at=slot_start + timedelta(hours=1),
        delivery_mode="IN_PERSON",
        actor=other_campus_counselor,
        context=context(other_campus_counselor),
    )
    with pytest.raises(AppointmentCounselorNotPermitted):
        book_fixed_slot(
            slot_id=slot.id,
            service_id=fixed_service.id,
            student=student,
            actor=goa,
            context=context(goa),
        )
    head_fixed_appt = book_fixed_slot(
        slot_id=slot.id,
        service_id=fixed_service.id,
        student=student,
        actor=head,
        context=context(head),
    )
    assert head_fixed_appt.provider_id == other_campus_counselor.id


@pytest.mark.django_db
def test_reason_encryption_rotates_with_shared_web_keyring(settings) -> None:
    w = _setup_world()
    student = w["student"]
    head = w["head"]
    other_campus_counselor = w["other_campus_counselor"]

    old_keys = tuple(settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS)
    req = submit_counselor_booking_request(
        student=student,
        preferred_counselor_id=other_campus_counselor.id,
        reason="Confidential rotation text",
        context=context(student),
    )
    old_ciphertext = req.reason_ciphertext

    new_key = Fernet.generate_key().decode("ascii")
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (new_key, *old_keys)
    call_command("rotate_counselor_handoff_summary_encryption", verbosity=0)

    req.refresh_from_db()
    assert req.reason_ciphertext != old_ciphertext
    # Dropping old key proves ciphertext was re-encrypted under new_key.
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (new_key,)
    detail = auth_client(head).get(f"/api/v1/appointments/counselor-requests/{req.id}").json()
    assert detail["reason"] == "Confidential rotation text"
    # Verify helper functions directly as well.
    permitted = resolve_permitted_counselors_for_student(student)
    assert w["college_counselor"].id in permitted
    assert permitted[w["college_counselor"].id].is_default is True
    approval = StudentCounselorApproval.objects.create(
        student=student, counselor=other_campus_counselor, approved_by=head
    )
    updated = change_counselor_approval(
        actor=head,
        approval_id=approval.id,
        counselor_id=w["third_counselor"].id,
        expected_version=approval.version,
        context=context(head),
    )
    ended = end_counselor_approval(
        actor=head,
        approval_id=approval.id,
        expected_version=updated.approval.version,
        context=context(head),
    )
    assert ended.approval.ended_at is not None
