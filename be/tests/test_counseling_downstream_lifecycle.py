from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from compass.counseling.services import (
    CounselingFeedbackChronologyConflict,
    CounselingFeedbackProvenanceConflict,
    CounselingFinalizedRoutineConflict,
    create_encounter,
    update_encounter,
)
from compass.feedback.models import (
    CustomerFeedbackResponse,
    CustomerFeedbackService,
    FeedbackOpportunity,
    FeedbackOpportunitySourceType,
)
from compass.feedback.services import create_csm_response, create_customer_feedback
from compass.notifications.models import Notification
from compass.routine_interviews.services import (
    ensure_for_appointment,
    finalize_assigned_evaluation,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from tests.test_counseling import auth_client, csrf
from tests.test_feedback import valid_csm_payload, valid_f14_payload
from tests.test_routine_interviews import (
    configure_year,
    context,
    create_counseling_service,
    direct_routine,
    make_appointment,
    make_user,
    submit_inventory,
    sync_policy,
)


def setup_domain(prefix: str):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    return admin, student, counselor, service


def finalize_direct(prefix: str, *, entry_mode: str = "WALK_IN"):
    _, student, counselor, service = setup_domain(prefix)
    routine = direct_routine(
        counselor=counselor,
        student=student,
        mode=entry_mode,
        key=f"{prefix}-routine",
    )
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"college_experience": "Submitted before finalization."},
    )
    submit_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        context=context(student),
    )
    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        values={"academic_adjustment_rating": 7},
    )
    ended_at = timezone.now() - timedelta(minutes=10)
    encounter = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=45),
        ended_at=ended_at,
        context=context(counselor),
    )
    routine = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=encounter.pk,
        context=context(counselor),
    )
    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
    )
    return student, counselor, routine, encounter, opportunity


@pytest.mark.django_db
def test_finalized_direct_routine_allows_safe_correction_and_blocks_invalidating_change():
    student, counselor, routine, encounter, opportunity = finalize_direct("direct-safe")
    original_opportunity_id = opportunity.pk
    corrected_end = encounter.ended_at - timedelta(minutes=2)

    corrected = update_encounter(
        encounter_id=encounter.pk,
        counselor=counselor,
        changes={
            "started_at": encounter.started_at + timedelta(minutes=1),
            "ended_at": corrected_end,
        },
        context=context(counselor),
    )
    assert corrected.ended_at == corrected_end
    routine.refresh_from_db()
    assert routine.evaluation_finalized_at is not None
    assert routine.counseling_encounter_id == encounter.pk
    opportunity.refresh_from_db()
    assert opportunity.pk == original_opportunity_id
    assert opportunity.service_completed_at == corrected_end

    with pytest.raises(CounselingFinalizedRoutineConflict):
        update_encounter(
            encounter_id=encounter.pk,
            counselor=counselor,
            changes={"entry_mode": "REFERRED"},
            context=context(counselor),
        )

    encounter.refresh_from_db()
    assert encounter.entry_mode == "WALK_IN"
    opportunity.refresh_from_db()
    assert opportunity.service_completed_at == corrected_end

    client = auth_client(counselor)
    response = client.patch(
        f"/api/v1/counseling/encounters/{encounter.pk}",
        data=json.dumps({"delivery_mode": "ONLINE"}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "counseling_finalized_routine_conflict"
    assert student.pk == encounter.student_id


@pytest.mark.django_db
def test_appointment_backed_finalized_routine_rejects_unlinking_encounter():
    _, student, counselor, service = setup_domain("appointment-link")
    appointment = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
        mode="IN_PERSON",
    )
    routine = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"career_goals": "Submitted."},
    )
    submit_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        context=context(student),
    )
    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        values={"academic_adjustment_rating": 8},
    )
    ended_at = timezone.now() - timedelta(minutes=10)
    encounter = create_encounter(
        counselor=counselor,
        entry_mode="APPOINTMENT",
        appointment_id=appointment.pk,
        started_at=ended_at - timedelta(minutes=40),
        ended_at=ended_at,
        context=context(counselor),
    )
    finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=None,
        context=context(counselor),
    )

    with pytest.raises(CounselingFinalizedRoutineConflict):
        update_encounter(
            encounter_id=encounter.pk,
            counselor=counselor,
            changes={"appointment_id": None, "entry_mode": "WALK_IN"},
            context=context(counselor),
        )

    encounter.refresh_from_db()
    assert encounter.appointment_id == appointment.pk
    assert encounter.entry_mode == "APPOINTMENT"


@pytest.mark.django_db
def test_submitted_feedback_survives_valid_completion_reconciliation_without_new_invitation():
    student, counselor, _, encounter, opportunity = finalize_direct("submitted-feedback")
    customer = create_customer_feedback(
        student=student,
        opportunity_id=opportunity.pk,
        values=valid_f14_payload(),
        context=context(student),
    )
    csm = create_csm_response(
        student=student,
        opportunity_id=opportunity.pk,
        values=valid_csm_payload(),
        context=context(student),
    )
    opportunity.refresh_from_db()
    customer_marker = opportunity.customer_feedback_submitted_at
    csm_marker = opportunity.csm_submitted_at
    invitation_count = Notification.objects.filter(
        recipient=student,
        event_code="feedback.invitation",
        source_type="feedback_opportunity",
        source_id=opportunity.pk,
    ).count()
    corrected_end = encounter.ended_at - timedelta(minutes=3)

    corrected = update_encounter(
        encounter_id=encounter.pk,
        counselor=counselor,
        changes={"ended_at": corrected_end},
        context=context(counselor),
    )
    assert corrected.ended_at == corrected_end

    opportunity.refresh_from_db()
    assert opportunity.service_completed_at == corrected_end
    assert opportunity.customer_feedback_submitted_at == customer_marker
    assert opportunity.csm_submitted_at == csm_marker
    assert CustomerFeedbackResponse.objects.get(pk=customer.pk).additional_feedback == "Helpful visit."
    assert csm.pk is not None
    assert (
        Notification.objects.filter(
            recipient=student,
            event_code="feedback.invitation",
            source_type="feedback_opportunity",
            source_id=opportunity.pk,
        ).count()
        == invitation_count
        == 1
    )


@pytest.mark.django_db
def test_feedback_chronology_conflict_rolls_back_encounter_and_opportunity():
    _, student, counselor, service = setup_domain("chronology")
    ended_at = timezone.now() - timedelta(hours=1)
    encounter = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=30),
        ended_at=ended_at,
        context=context(counselor),
    )
    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
    )
    issued_at = timezone.now() - timedelta(minutes=30)
    FeedbackOpportunity.objects.filter(pk=opportunity.pk).update(created_at=issued_at)
    opportunity.refresh_from_db()
    proposed_end = issued_at + timedelta(minutes=10)
    assert proposed_end < timezone.now()

    with pytest.raises(CounselingFeedbackChronologyConflict):
        update_encounter(
            encounter_id=encounter.pk,
            counselor=counselor,
            changes={"ended_at": proposed_end},
            context=context(counselor),
        )

    encounter.refresh_from_db()
    opportunity.refresh_from_db()
    assert encounter.ended_at == ended_at
    assert opportunity.service_completed_at == ended_at
    assert service.pk == encounter.service_id

    client = auth_client(counselor)
    response = client.patch(
        f"/api/v1/counseling/encounters/{encounter.pk}",
        data=json.dumps({"ended_at": proposed_end.isoformat()}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "counseling_feedback_chronology_conflict"


@pytest.mark.django_db
def test_feedback_provenance_corruption_and_missing_opportunity_fail_closed():
    _, student, counselor, _ = setup_domain("provenance")
    ended_at = timezone.now() - timedelta(minutes=20)
    encounter = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=30),
        ended_at=ended_at,
        context=context(counselor),
    )
    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
    )
    original_start = encounter.started_at
    FeedbackOpportunity.objects.filter(pk=opportunity.pk).update(
        service_kind=CustomerFeedbackService.REQUEST_FOR_CERTIFICATION
    )

    with pytest.raises(CounselingFeedbackProvenanceConflict):
        update_encounter(
            encounter_id=encounter.pk,
            counselor=counselor,
            changes={"started_at": original_start + timedelta(minutes=1)},
            context=context(counselor),
        )
    encounter.refresh_from_db()
    assert encounter.started_at == original_start

    FeedbackOpportunity.objects.filter(pk=opportunity.pk).delete()
    with pytest.raises(CounselingFeedbackProvenanceConflict):
        update_encounter(
            encounter_id=encounter.pk,
            counselor=counselor,
            changes={"started_at": original_start + timedelta(minutes=2)},
            context=context(counselor),
        )
    encounter.refresh_from_db()
    assert encounter.started_at == original_start


@pytest.mark.django_db
def test_true_noop_correction_does_not_touch_feedback_opportunity():
    _, student, counselor, _ = setup_domain("noop")
    ended_at = timezone.now() - timedelta(minutes=15)
    encounter = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=30),
        ended_at=ended_at,
        context=context(counselor),
    )
    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
    )
    updated_at = opportunity.updated_at

    unchanged = update_encounter(
        encounter_id=encounter.pk,
        counselor=counselor,
        changes={},
        context=context(counselor),
    )
    assert unchanged.pk == encounter.pk
    opportunity.refresh_from_db()
    assert opportunity.updated_at == updated_at
