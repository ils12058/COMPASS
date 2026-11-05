from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.appointments.models import AppointmentStatus
from compass.appointments.services import complete_appointment
from compass.audit.models import AuditEvent
from compass.counseling.finish_service import (
    CounselingAppointmentClosed,
    CounselingFinishConflict,
    CounselingFinishECounselingAccessOpen,
    CounselingFinishLifecycleConflict,
    finish_counseling_appointment,
)
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.counseling.services import (
    CounselingAppointmentInvalid,
    CounselingNotPermitted,
    CounselingRoutineInterviewAlreadyLinked,
    CounselingRoutineInterviewMismatch,
    InvalidCounselingInput,
    create_encounter,
)
from compass.feedback.models import FeedbackOpportunity, FeedbackOpportunitySourceType
from compass.notifications.models import Notification
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import ensure_for_appointment
from compass.service_catalog.services import create_service
from tests.test_counseling import (
    actual_times,
    auth_client,
    context,
    create_counseling_service,
    csrf,
    make_appointment,
    make_user,
    sync_policy,
)
from tests.test_routine_interviews import configure_year, submit_inventory

FINISH_RESPONSE_FIELDS = {
    "appointment_id",
    "appointment_status",
    "encounter_id",
    "encounter_result",
    "routine_interview_id",
    "routine_interview_linked",
    "already_finished",
}


def setup_domain(prefix: str = "finish"):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    return admin, counselor, student, service


def finish_payload(*, start, end, occurred: bool = True) -> dict[str, object]:
    return {
        "actual_started_at": start.isoformat(),
        "actual_ended_at": end.isoformat(),
        "counseling_occurred": occurred,
    }


def finish_url(appointment) -> str:
    return f"/api/v1/counseling/appointments/{appointment.pk}/finish"


def finish_via_api(client: Client, appointment, *, start, end, occurred: bool = True):
    return client.post(
        finish_url(appointment),
        data=json.dumps(finish_payload(start=start, end=end, occurred=occurred)),
        content_type="application/json",
        **csrf(client),
    )


def finish_direct(
    counselor: User,
    appointment,
    *,
    start=None,
    end=None,
    occurred: bool = True,
    now=None,
):
    if start is None:
        start, end = actual_times()
    return finish_counseling_appointment(
        appointment_id=appointment.pk,
        counselor=counselor,
        counseling_occurred=occurred,
        actual_started_at=start,
        actual_ended_at=end,
        context=context(counselor),
        now=now,
    )


def audit_count(action: str, target_id=None) -> int:
    queryset = AuditEvent.objects.filter(action=action)
    if target_id is not None:
        queryset = queryset.filter(target_id=str(target_id))
    return queryset.count()


def error_code(response) -> str:
    return response.json()["error"]["code"]


def setup_domain_with_routine(prefix: str):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, provider=counselor, service=service)
    routine = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    return admin, counselor, student, service, appointment, routine


@pytest.mark.django_db
def test_finish_records_completion_and_encounter_atomically():
    _, counselor, student, service = setup_domain("normal")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == FINISH_RESPONSE_FIELDS
    assert body["appointment_id"] == str(appointment.pk)
    assert body["appointment_status"] == "COMPLETED"
    assert body["encounter_result"] == "CREATED"
    assert body["already_finished"] is False
    assert body["routine_interview_id"] is None
    assert body["routine_interview_linked"] is False

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.COMPLETED
    assert appointment.completed_by_id == counselor.pk
    assert appointment.completed_at is not None

    encounter = CounselingEncounter.objects.get(pk=body["encounter_id"])
    assert encounter.appointment_id == appointment.pk
    assert encounter.student_id == student.pk
    assert encounter.counselor_id == counselor.pk
    assert encounter.service_id == service.pk
    assert encounter.service_name_snapshot == "Counseling"
    assert encounter.entry_mode == CounselingEntryMode.APPOINTMENT
    assert encounter.delivery_mode == "IN_PERSON"
    assert encounter.created_by_id == counselor.pk
    assert encounter.started_at == start
    assert encounter.ended_at == end

    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
    )
    assert opportunity.student_id == student.pk
    assert (
        Notification.objects.filter(
            recipient=student,
            event_code="feedback.invitation",
            source_type="feedback_opportunity",
            source_id=opportunity.pk,
        ).count()
        == 1
    )
    assert audit_count("appointment.completed", appointment.pk) == 1
    assert audit_count("counseling.encounter.created", encounter.pk) == 1


@pytest.mark.django_db
def test_finish_never_substitutes_scheduled_times_and_rejects_invalid_actual_times():
    _, counselor, student, service = setup_domain("times")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start = appointment.starts_at + timedelta(minutes=7)
    end = appointment.ends_at - timedelta(minutes=9)

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)

    assert response.status_code == 200
    encounter = CounselingEncounter.objects.get(appointment_id=appointment.pk)
    assert encounter.started_at == start
    assert encounter.ended_at == end
    assert encounter.started_at != appointment.starts_at
    assert encounter.ended_at != appointment.ends_at

    client = auth_client(counselor)
    now = timezone.now()
    invalid_bodies = [
        {
            "actual_started_at": (now - timedelta(minutes=30)).isoformat(),
            "counseling_occurred": True,
        },
        finish_payload(
            start=now - timedelta(minutes=30),
            end=now.replace(tzinfo=None) - timedelta(minutes=5),
        ),
        finish_payload(start=now - timedelta(minutes=5), end=now - timedelta(minutes=30)),
        finish_payload(start=now - timedelta(hours=1), end=now + timedelta(hours=1)),
        {
            **finish_payload(start=now - timedelta(minutes=30), end=now - timedelta(minutes=5)),
            "request_key": "not-accepted",
        },
    ]
    for index, body in enumerate(invalid_bodies):
        rejected = make_appointment(student=student, provider=counselor, service=service)
        response = client.post(
            finish_url(rejected),
            data=json.dumps(body),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 422, index
        rejected.refresh_from_db()
        assert rejected.status == AppointmentStatus.SCHEDULED
        assert not CounselingEncounter.objects.filter(appointment=rejected).exists()
        assert audit_count("appointment.completed", rejected.pk) == 0


@pytest.mark.django_db
def test_finish_requires_counseling_occurred_attestation_before_writing():
    _, counselor, student, service = setup_domain("attestation")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()

    with pytest.raises(InvalidCounselingInput):
        finish_direct(counselor, appointment, start=start, end=end, occurred=False)

    response = finish_via_api(
        auth_client(counselor), appointment, start=start, end=end, occurred=False
    )
    assert response.status_code == 422
    assert error_code(response) == "counseling_invalid_request"

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_replay_returns_existing_without_new_writes():
    _, counselor, student, service = setup_domain("replay")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()

    first = finish_direct(counselor, appointment, start=start, end=end)
    assert first.encounter_result == "CREATED"
    appointment.refresh_from_db()
    completed_at = appointment.completed_at
    counts = (
        CounselingEncounter.objects.count(),
        FeedbackOpportunity.objects.count(),
        Notification.objects.filter(event_code="feedback.invitation").count(),
        audit_count("appointment.completed"),
        audit_count("counseling.encounter.created"),
    )

    second = finish_direct(counselor, appointment, start=start, end=end)

    assert second.encounter_result == "EXISTING"
    assert second.already_finished is True
    assert second.encounter.pk == first.encounter.pk
    assert second.appointment.pk == first.appointment.pk
    appointment.refresh_from_db()
    assert appointment.completed_at == completed_at
    assert (
        CounselingEncounter.objects.count(),
        FeedbackOpportunity.objects.count(),
        Notification.objects.filter(event_code="feedback.invitation").count(),
        audit_count("appointment.completed"),
        audit_count("counseling.encounter.created"),
    ) == counts


@pytest.mark.django_db
def test_finish_contradictory_replay_is_a_conflict_and_never_edits_the_encounter():
    _, counselor, student, service = setup_domain("contradiction")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    first = finish_direct(counselor, appointment, start=start, end=end)
    counts = (
        CounselingEncounter.objects.count(),
        audit_count("appointment.completed"),
        audit_count("counseling.encounter.created"),
    )

    with pytest.raises(CounselingFinishConflict):
        finish_direct(counselor, appointment, start=start, end=end + timedelta(minutes=1))

    response = finish_via_api(
        auth_client(counselor), appointment, start=start, end=end + timedelta(minutes=1)
    )
    assert response.status_code == 409
    assert error_code(response) == "counseling_finish_conflict"

    encounter = CounselingEncounter.objects.get(pk=first.encounter.pk)
    assert encounter.started_at == start
    assert encounter.ended_at == end
    assert (
        CounselingEncounter.objects.count(),
        audit_count("appointment.completed"),
        audit_count("counseling.encounter.created"),
    ) == counts


@pytest.mark.django_db
def test_finish_documents_an_administratively_completed_appointment_without_new_completion():
    _, counselor, student, service = setup_domain("late-documentation")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    completed = complete_appointment(
        appointment_id=appointment.pk,
        actor=counselor,
        context=context(counselor),
    )
    completed_at = completed.completed_at
    assert audit_count("appointment.completed", appointment.pk) == 1
    start, end = actual_times()

    result = finish_direct(counselor, appointment, start=start, end=end)

    assert result.encounter_result == "CREATED"
    assert result.already_finished is False
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.COMPLETED
    assert appointment.completed_at == completed_at
    assert appointment.completed_by_id == counselor.pk
    assert CounselingEncounter.objects.filter(appointment=appointment).count() == 1
    assert audit_count("appointment.completed", appointment.pk) == 1


@pytest.mark.django_db
def test_finish_replays_an_administratively_completed_appointment_with_identical_encounter():
    _, counselor, student, service = setup_domain("complete-then-replay")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    encounter = create_encounter(
        counselor=counselor,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        appointment_id=appointment.pk,
        started_at=start,
        ended_at=end,
        context=context(counselor),
    )
    complete_appointment(
        appointment_id=appointment.pk,
        actor=counselor,
        context=context(counselor),
    )
    counts = (
        CounselingEncounter.objects.count(),
        FeedbackOpportunity.objects.count(),
        audit_count("appointment.completed"),
        audit_count("counseling.encounter.created"),
    )

    result = finish_direct(counselor, appointment, start=start, end=end)

    assert result.encounter_result == "EXISTING"
    assert result.already_finished is True
    assert result.encounter.pk == encounter.pk
    assert (
        CounselingEncounter.objects.count(),
        FeedbackOpportunity.objects.count(),
        audit_count("appointment.completed"),
        audit_count("counseling.encounter.created"),
    ) == counts


@pytest.mark.django_db
def test_finish_rejects_a_non_appointment_encounter_without_completing():
    _, counselor, student, service = setup_domain("entry-mode")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    create_encounter(
        counselor=counselor,
        entry_mode="REFERRED",
        appointment_id=appointment.pk,
        started_at=start,
        ended_at=end,
        context=context(counselor),
    )

    with pytest.raises(CounselingFinishConflict):
        finish_direct(counselor, appointment, start=start, end=end)

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "counseling_finish_conflict"
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_rejects_cancelled_and_no_show_appointments():
    _, counselor, student, service = setup_domain("closed")

    for status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
        appointment = make_appointment(
            student=student, provider=counselor, service=service, status=status
        )
        start, end = actual_times()
        with pytest.raises(CounselingAppointmentClosed):
            finish_direct(counselor, appointment, start=start, end=end)
        response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
        assert response.status_code == 409
        assert error_code(response) == "counseling_appointment_closed"
        appointment.refresh_from_db()
        assert appointment.status == status
        assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
        assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_before_scheduled_start_is_a_lifecycle_conflict():
    _, counselor, student, service = setup_domain("before-start")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    now = timezone.now()
    appointment.starts_at = now + timedelta(hours=2)
    appointment.ends_at = now + timedelta(hours=3)
    appointment.save(update_fields=["starts_at", "ends_at", "updated_at"])
    start, end = actual_times()

    with pytest.raises(CounselingFinishLifecycleConflict):
        finish_direct(counselor, appointment, start=start, end=end)

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "appointment_lifecycle_conflict"
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_rejects_an_open_ecounseling_window_for_scheduled_and_completed():
    _, counselor, student, service = setup_domain("ecounseling")
    now = timezone.now()
    start, end = now - timedelta(minutes=5), now - timedelta(minutes=1)

    scheduled = make_appointment(
        student=student, provider=counselor, service=service, delivery_mode="ONLINE"
    )
    scheduled.starts_at = now - timedelta(minutes=5)
    scheduled.ends_at = now + timedelta(minutes=55)
    scheduled.save(update_fields=["starts_at", "ends_at", "updated_at"])

    with pytest.raises(CounselingFinishECounselingAccessOpen):
        finish_direct(counselor, scheduled, start=start, end=end)
    response = finish_via_api(auth_client(counselor), scheduled, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "ecounseling_access_open"
    scheduled.refresh_from_db()
    assert scheduled.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=scheduled).exists()
    assert audit_count("appointment.completed", scheduled.pk) == 0

    completed = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="ONLINE",
        status=AppointmentStatus.COMPLETED,
    )
    completed.starts_at = now - timedelta(minutes=5)
    completed.ends_at = now + timedelta(minutes=55)
    completed.save(update_fields=["starts_at", "ends_at", "updated_at"])

    with pytest.raises(CounselingFinishECounselingAccessOpen):
        finish_direct(counselor, completed, start=start, end=end)
    response = finish_via_api(auth_client(counselor), completed, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "ecounseling_access_open"
    completed.refresh_from_db()
    assert completed.status == AppointmentStatus.COMPLETED
    assert not CounselingEncounter.objects.filter(appointment=completed).exists()
    assert audit_count("appointment.completed", completed.pk) == 0


@pytest.mark.django_db
def test_finish_authorization_matrix_returns_no_resource_details():
    admin, counselor, student, service = setup_domain("authz")
    other = make_user("authz-other@example.edu", "COUNSELOR")
    gss = make_user("authz-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    head = make_user("authz-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    body = json.dumps(finish_payload(start=start, end=end))

    anonymous = Client().post(finish_url(appointment), data=body, content_type="application/json")
    assert anonymous.status_code == 401
    assert error_code(anonymous) == "authentication_required"

    for user in (student, gss, admin):
        client = auth_client(user)
        response = client.post(
            finish_url(appointment),
            data=body,
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 403
        assert error_code(response) == "permission_denied"

    for user in (other, head):
        client = auth_client(user)
        response = client.post(
            finish_url(appointment),
            data=body,
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 404
        assert error_code(response) == "counseling_resource_not_found"
        serialized = response.content.decode()
        assert str(appointment.pk) not in serialized
        assert appointment.reference_code not in serialized
        assert student.email not in serialized

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()

    provider = auth_client(counselor)
    success = provider.post(
        finish_url(appointment),
        data=body,
        content_type="application/json",
        **csrf(provider),
    )
    assert success.status_code == 200
    assert success.json()["encounter_result"] == "CREATED"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "capability",
    ["counseling.manage_assigned", "appointments.manage"],
)
def test_finish_service_rejects_revoked_capabilities_before_any_write(capability):
    _, counselor, student, service = setup_domain(f"revoke-{capability}")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code=capability),
        effect="REVOKE",
        reason="synthetic separation of duties",
    )
    start, end = actual_times()

    with pytest.raises(CounselingNotPermitted):
        finish_direct(counselor, appointment, start=start, end=end)

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_service_rejects_inactive_and_non_counselor_callers_before_any_write():
    admin, counselor, student, service = setup_domain("inactive")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()

    counselor.is_active = False
    counselor.save(update_fields=["is_active"])
    with pytest.raises(CounselingNotPermitted):
        finish_direct(counselor, appointment, start=start, end=end)

    for caller in (student, admin):
        with pytest.raises(CounselingNotPermitted):
            finish_direct(caller, appointment, start=start, end=end)

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_rejects_a_non_canonical_counseling_service():
    admin, counselor, student, _ = setup_domain("service")
    other_service = create_service(
        code="CAREER_GUIDANCE",
        name="Career Guidance",
        context=context(admin),
    )
    appointment = make_appointment(student=student, provider=counselor, service=other_service)
    start, end = actual_times()

    with pytest.raises(CounselingAppointmentInvalid):
        finish_direct(counselor, appointment, start=start, end=end)

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "counseling_appointment_invalid"
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0


@pytest.mark.django_db
def test_finish_links_the_deterministic_routine_and_reports_it():
    _, counselor, _, _, appointment, routine = setup_domain_with_routine("routine-match")
    start, end = actual_times()

    result = finish_direct(counselor, appointment, start=start, end=end)

    assert result.routine_interview is not None
    assert result.routine_interview.pk == routine.pk
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == result.encounter.pk
    assert audit_count("routine_interview.encounter_linked", routine.pk) == 1

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
    assert response.status_code == 200
    body = response.json()
    assert body["routine_interview_id"] == str(routine.pk)
    assert body["routine_interview_linked"] is True
    assert body["encounter_result"] == "EXISTING"
    assert body["already_finished"] is True


@pytest.mark.django_db
def test_finish_rejects_a_mismatched_routine_before_writing():
    _, counselor, _, _, appointment, routine = setup_domain_with_routine("routine-mismatch")
    RoutineInterview.objects.filter(pk=routine.pk).update(delivery_mode="ONLINE")
    start, end = actual_times()

    with pytest.raises(CounselingRoutineInterviewMismatch):
        finish_direct(counselor, appointment, start=start, end=end)

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "counseling_routine_interview_mismatch"
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0
    routine.refresh_from_db()
    assert routine.counseling_encounter_id is None


@pytest.mark.django_db
def test_finish_rejects_a_finalized_routine_linked_to_a_different_encounter():
    admin, counselor, student, service, appointment, routine = setup_domain_with_routine(
        "routine-linked-elsewhere"
    )
    start, end = actual_times()
    other_appointment = make_appointment(student=student, provider=counselor, service=service)
    other_encounter = create_encounter(
        counselor=counselor,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        appointment_id=other_appointment.pk,
        started_at=start,
        ended_at=end,
        context=context(counselor),
    )
    RoutineInterview.objects.filter(pk=routine.pk).update(
        counseling_encounter_id=other_encounter.pk,
        evaluation_finalized_at=timezone.now(),
    )

    with pytest.raises(CounselingRoutineInterviewAlreadyLinked):
        finish_direct(counselor, appointment, start=start, end=end)

    response = finish_via_api(auth_client(counselor), appointment, start=start, end=end)
    assert response.status_code == 409
    assert error_code(response) == "counseling_routine_interview_already_linked"
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == other_encounter.pk


@pytest.mark.django_db
def test_finish_never_creates_or_similarity_links_a_routine():
    admin, counselor, student, service = setup_domain("routine-similarity")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=start,
        ended_at=end,
        context=context(counselor),
    )

    result = finish_direct(counselor, appointment, start=start, end=end)

    assert result.routine_interview is None
    assert not RoutineInterview.objects.filter(appointment_id=appointment.pk).exists()
    assert audit_count("routine_interview.encounter_linked") == 0
    assert CounselingEncounter.objects.filter(appointment=appointment).count() == 1


@pytest.mark.django_db
def test_finish_rolls_back_completion_when_feedback_persistence_fails(monkeypatch):
    _, counselor, student, service = setup_domain("rollback")
    appointment = make_appointment(student=student, provider=counselor, service=service)

    def fail_notification(**_kwargs):
        raise RuntimeError("synthetic notification persistence failure")

    monkeypatch.setattr(
        "compass.counseling.services.create_notification_for_event",
        fail_notification,
    )
    start, end = actual_times()

    with pytest.raises(RuntimeError, match="synthetic notification persistence failure"):
        finish_direct(counselor, appointment, start=start, end=end)

    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert appointment.completed_at is None
    assert appointment.completed_by_id is None
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert not FeedbackOpportunity.objects.filter(student=student).exists()
    assert not Notification.objects.filter(recipient=student).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0
    assert audit_count("counseling.encounter.created") == 0


@pytest.mark.django_db
def test_legacy_paths_keep_partial_states_and_finish_reconciles_them():
    _, counselor, student, service = setup_domain("legacy")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()

    encounter = create_encounter(
        counselor=counselor,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        appointment_id=appointment.pk,
        started_at=start,
        ended_at=end,
        context=context(counselor),
    )
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED

    completed = complete_appointment(
        appointment_id=appointment.pk,
        actor=counselor,
        context=context(counselor),
    )
    assert completed.status == AppointmentStatus.COMPLETED
    assert CounselingEncounter.objects.filter(appointment=appointment).count() == 1
    assert audit_count("appointment.completed", appointment.pk) == 1

    result = finish_direct(counselor, appointment, start=start, end=end)
    assert result.encounter.pk == encounter.pk
    assert result.encounter_result == "EXISTING"
    assert result.already_finished is True
    assert audit_count("appointment.completed", appointment.pk) == 1
