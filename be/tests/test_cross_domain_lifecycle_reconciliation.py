from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from compass.appointments.models import AppointmentStatus
from compass.appointments.services import (
    AppointmentActionBlocker,
    AppointmentActionConsequenceCode,
    AppointmentECounselingAccessOpen,
    AppointmentECounselingAccessStarted,
    AppointmentECounselingRoomLinked,
    appointment_actions_for,
    cancel_appointment,
    complete_appointment,
    mark_appointment_no_show,
)
from compass.ecounseling.models import ECounselingRoom
from compass.ecounseling.services import ECounselingJoinState, ecounseling_access_window
from compass.routine_interviews.content import read_intake
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    RoutineInterviewParentClosed,
    RoutineWorkflowState,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    replace_assigned_evaluation,
    replace_my_intake,
    routine_workflow_state,
    submit_my_intake,
)
from compass.service_catalog.services import update_service
from tests.test_appointments import create_affiliation
from tests.test_routine_interviews import (
    auth_client,
    configure_year,
    context,
    create_counseling_service,
    csrf,
    direct_routine,
    make_appointment,
    make_user,
    submit_inventory,
    sync_policy,
)


def setup_online_appointment(prefix: str):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    create_affiliation(student, counselor)
    appointment = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
        mode="ONLINE",
    )
    return admin, student, counselor, service, appointment


def set_window(appointment, *, starts_at, cutoff=None):
    appointment.starts_at = starts_at
    appointment.ends_at = starts_at + timedelta(hours=1)
    appointment.cancellation_cutoff_minutes = cutoff
    appointment.save(
        update_fields=[
            "starts_at",
            "ends_at",
            "cancellation_cutoff_minutes",
            "updated_at",
        ]
    )
    return appointment


@pytest.mark.django_db
@override_settings(
    ECOUNSELING_JOIN_EARLY_SECONDS=600,
    ECOUNSELING_REJOIN_GRACE_SECONDS=900,
)
def test_online_appointment_transitions_share_exact_ecounseling_boundaries():
    _, student, counselor, service, before = setup_online_appointment("boundary")
    base = timezone.now() + timedelta(hours=2)
    set_window(before, starts_at=base)
    join_from = base - timedelta(minutes=10)

    window = ecounseling_access_window(before, now=join_from)
    assert window.state == ECounselingJoinState.OPEN
    assert window.available_from == join_from
    assert window.available_until == before.ends_at + timedelta(minutes=15)

    cancelled = cancel_appointment(
        appointment_id=before.pk,
        actor=student,
        administrative=False,
        context=context(student),
        now=join_from - timedelta(seconds=1),
    )
    assert cancelled.status == AppointmentStatus.CANCELLED

    at_boundary = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
        mode="ONLINE",
    )
    set_window(at_boundary, starts_at=base + timedelta(days=1))
    exact_join_from = at_boundary.starts_at - timedelta(minutes=10)
    with pytest.raises(AppointmentECounselingAccessStarted):
        cancel_appointment(
            appointment_id=at_boundary.pk,
            actor=student,
            administrative=False,
            context=context(student),
            now=exact_join_from,
        )

    completion = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
        mode="ONLINE",
    )
    set_window(completion, starts_at=base - timedelta(days=1))
    join_until = completion.ends_at + timedelta(minutes=15)
    with pytest.raises(AppointmentECounselingAccessOpen):
        complete_appointment(
            appointment_id=completion.pk,
            actor=counselor,
            context=context(counselor),
            now=join_until,
        )
    completed = complete_appointment(
        appointment_id=completion.pk,
        actor=counselor,
        context=context(counselor),
        now=join_until + timedelta(seconds=1),
    )
    assert completed.status == AppointmentStatus.COMPLETED

    no_show = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
        mode="ONLINE",
    )
    set_window(no_show, starts_at=base - timedelta(days=2))
    no_show_until = no_show.ends_at + timedelta(minutes=15)
    with pytest.raises(AppointmentECounselingAccessOpen):
        mark_appointment_no_show(
            appointment_id=no_show.pk,
            actor=counselor,
            context=context(counselor),
            now=no_show_until,
        )
    marked = mark_appointment_no_show(
        appointment_id=no_show.pk,
        actor=counselor,
        context=context(counselor),
        now=no_show_until + timedelta(seconds=1),
    )
    assert marked.status == AppointmentStatus.NO_SHOW


@pytest.mark.django_db
@override_settings(
    ECOUNSELING_JOIN_EARLY_SECONDS=600,
    ECOUNSELING_REJOIN_GRACE_SECONDS=900,
)
def test_action_projection_matches_mutations_and_room_is_hard_cancellation_blocker():
    admin, student, counselor, service, appointment = setup_online_appointment("projection")
    start = timezone.now() + timedelta(hours=2)
    set_window(appointment, starts_at=start)
    routine = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )

    before = start - timedelta(minutes=10, seconds=1)
    allowed = appointment_actions_for(actor=counselor, item=appointment, now=before)
    assert allowed.cancel.allowed is True
    assert allowed.cancel.blocker is None
    assert len(allowed.cancel.consequences) == 1
    consequence = allowed.cancel.consequences[0]
    assert consequence.code == AppointmentActionConsequenceCode.ROUTINE_INTERVIEW_WILL_CLOSE
    assert consequence.routine_interview_id == routine.pk

    access_started = appointment_actions_for(
        actor=counselor,
        item=appointment,
        now=start - timedelta(minutes=10),
    )
    assert access_started.cancel.allowed is False
    assert access_started.cancel.blocker == AppointmentActionBlocker.ECOUNSELING_ACCESS_STARTED
    assert access_started.cancel.consequences == ()

    during = appointment_actions_for(actor=counselor, item=appointment, now=start)
    assert during.complete.blocker == AppointmentActionBlocker.ECOUNSELING_ACCESS_OPEN

    ECounselingRoom.objects.create(
        appointment=appointment,
        daily_room_name=f"legacy-{appointment.pk}",
    )
    with pytest.raises(AppointmentECounselingRoomLinked):
        cancel_appointment(
            appointment_id=appointment.pk,
            actor=student,
            administrative=False,
            context=context(student),
            now=before,
        )

    # Existing Appointment lifecycle safety is not disabled by later Service changes.
    update_service(
        service_id=service.pk,
        changes={"delivery_modes": ["IN_PERSON"]},
        acknowledge_scheduling_consequences=True,
        context=context(admin),
    )
    still_blocked = appointment_actions_for(
        actor=counselor,
        item=appointment,
        now=start - timedelta(minutes=10),
    )
    assert still_blocked.cancel.blocker == AppointmentActionBlocker.ECOUNSELING_ACCESS_STARTED


@pytest.mark.django_db
@override_settings(
    ECOUNSELING_JOIN_EARLY_SECONDS=600,
    ECOUNSELING_REJOIN_GRACE_SECONDS=900,
)
def test_cancelled_appointment_preserves_routine_content_and_blocks_every_mutation_path():
    _, student, counselor, _, appointment = setup_online_appointment("cancel-routine")
    start = timezone.now() + timedelta(hours=2)
    set_window(appointment, starts_at=start)
    routine = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"college_experience": "Preserve this draft."},
    )

    cancelled = cancel_appointment(
        appointment_id=appointment.pk,
        actor=student,
        administrative=False,
        context=context(student),
        now=start - timedelta(minutes=11),
    )
    assert cancelled.status == AppointmentStatus.CANCELLED

    preserved = RoutineInterview.objects.get(pk=routine.pk)
    assert read_intake(preserved)["college_experience"] == "Preserve this draft."
    assert (
        routine_workflow_state(
            RoutineInterview.objects.select_related("appointment").get(pk=routine.pk)
        )
        == RoutineWorkflowState.CLOSED_APPOINTMENT_CANCELLED
    )

    with pytest.raises(RoutineInterviewParentClosed):
        replace_my_intake(
            student=student,
            routine_interview_id=routine.pk,
            values={"college_experience": "Blocked."},
        )
    with pytest.raises(RoutineInterviewParentClosed):
        submit_my_intake(
            student=student,
            routine_interview_id=routine.pk,
            context=context(student),
        )
    with pytest.raises(RoutineInterviewParentClosed):
        replace_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=routine.pk,
            values={"academic_adjustment_rating": 7},
        )
    with pytest.raises(RoutineInterviewParentClosed):
        finalize_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=routine.pk,
            encounter_id=None,
            context=context(counselor),
        )

    student_client = auth_client(student)
    response = student_client.get(f"/api/v1/routine-interviews/me/{routine.pk}")
    assert response.status_code == 200
    assert response.json()["workflow_state"] == "CLOSED_APPOINTMENT_CANCELLED"
    assert response.json()["intake"]["college_experience"] == "Preserve this draft."

    blocked_api = student_client.put(
        f"/api/v1/routine-interviews/me/{routine.pk}/intake",
        data='{"college_experience":"Blocked API edit"}',
        content_type="application/json",
        **csrf(student_client),
    )
    assert blocked_api.status_code == 409
    assert blocked_api.json()["error"]["code"] == "routine_interview_closed_by_appointment"


@pytest.mark.django_db
@override_settings(
    ECOUNSELING_JOIN_EARLY_SECONDS=600,
    ECOUNSELING_REJOIN_GRACE_SECONDS=900,
)
def test_no_show_closes_appointment_routine_but_completed_and_direct_routines_remain_active():
    _, student, counselor, service, no_show_appointment = setup_online_appointment(
        "terminal-routine"
    )
    past_start = timezone.now() - timedelta(hours=3)
    set_window(no_show_appointment, starts_at=past_start)
    no_show_routine = ensure_for_appointment(
        student=student,
        appointment_id=no_show_appointment.pk,
        context=context(student),
    )
    replace_my_intake(
        student=student,
        routine_interview_id=no_show_routine.pk,
        values={"academic_goals": "Keep this historical answer."},
    )
    close_time = no_show_appointment.ends_at + timedelta(minutes=15, seconds=1)
    marked = mark_appointment_no_show(
        appointment_id=no_show_appointment.pk,
        actor=counselor,
        context=context(counselor),
        now=close_time,
    )
    assert marked.status == AppointmentStatus.NO_SHOW
    no_show_routine.refresh_from_db()
    assert read_intake(no_show_routine)["academic_goals"] == "Keep this historical answer."
    assert (
        routine_workflow_state(
            RoutineInterview.objects.select_related("appointment").get(pk=no_show_routine.pk)
        )
        == RoutineWorkflowState.CLOSED_APPOINTMENT_NO_SHOW
    )

    completed_appointment = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
        mode="ONLINE",
    )
    set_window(completed_appointment, starts_at=timezone.now() - timedelta(hours=3))
    completed_routine = ensure_for_appointment(
        student=student,
        appointment_id=completed_appointment.pk,
        context=context(student),
    )
    completed = complete_appointment(
        appointment_id=completed_appointment.pk,
        actor=counselor,
        context=context(counselor),
        now=completed_appointment.ends_at + timedelta(minutes=15, seconds=1),
    )
    assert completed.status == AppointmentStatus.COMPLETED
    assert (
        routine_workflow_state(
            RoutineInterview.objects.select_related("appointment").get(pk=completed_routine.pk)
        )
        == RoutineWorkflowState.ACTIVE
    )
    updated = replace_my_intake(
        student=student,
        routine_interview_id=completed_routine.pk,
        values={"career_goals": "Evaluation work can continue."},
    )
    assert read_intake(updated)["career_goals"] == "Evaluation work can continue."

    direct = direct_routine(
        counselor=counselor,
        student=student,
        key="direct-unaffected",
    )
    assert routine_workflow_state(direct) == RoutineWorkflowState.ACTIVE
    direct_updated = replace_my_intake(
        student=student,
        routine_interview_id=direct.pk,
        values={"family_description": "Direct Routine remains editable."},
    )
    assert read_intake(direct_updated)["family_description"] == "Direct Routine remains editable."
