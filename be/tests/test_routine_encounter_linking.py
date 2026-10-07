"""COMPASS links a Routine Interview to its Counseling Encounter when provenance is known."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import set_user_capability_override
from compass.audit.models import AuditEvent
from compass.counseling.context_access import resolve_counseling_context
from compass.counseling.context_services import get_context_overview
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import (
    CounselingLinkedRoutineConflict,
    CounselingNotFound,
    CounselingRoutineInterviewAlreadyLinked,
    CounselingRoutineInterviewMismatch,
    create_encounter,
    update_encounter,
)
from compass.routine_interviews import services as routine_services
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    RoutineInterviewEncounterConflict,
    RoutineInterviewEncounterRequired,
    RoutineInterviewInventoryRequired,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    list_encounter_candidates,
    replace_my_intake,
    submit_my_intake,
)
from tests.inventory_test_helpers import ensure_inventory_form_revision
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

LINKED = "routine_interview.encounter_linked"


def setup_domain(prefix: str, *, inventory: bool = True):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    if inventory:
        submit_inventory(student, student)
    service = create_counseling_service(admin)
    return admin, student, counselor, service


def submit_intake(student: User, routine: RoutineInterview) -> RoutineInterview:
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"college_experience": "Submitted intake."},
    )
    submit_my_intake(student=student, routine_interview_id=routine.pk, context=context(student))
    # Submitted an hour ago, so the interactions recorded below fall inside the workspace window.
    RoutineInterview.objects.filter(pk=routine.pk).update(
        intake_submitted_at=timezone.now() - timedelta(hours=1)
    )
    routine.refresh_from_db()
    return routine


def record(counselor: User, *, minutes_ago: int = 10, **kwargs) -> CounselingEncounter:
    ended_at = timezone.now() - timedelta(minutes=minutes_ago)
    return create_encounter(
        counselor=counselor,
        started_at=ended_at - timedelta(minutes=40),
        ended_at=ended_at,
        context=context(counselor),
        **kwargs,
    )


def legacy_encounter(*, student, counselor, service, appointment=None, entry_mode="WALK_IN"):
    """An Encounter written directly, as records were before automatic linking existed."""

    ended_at = timezone.now() - timedelta(minutes=10)
    return CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        appointment=appointment,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=40),
        ended_at=ended_at,
        created_by=counselor,
    )


def link_events(routine: RoutineInterview) -> list[dict]:
    return list(
        AuditEvent.objects.filter(action=LINKED, target_id=str(routine.pk)).values_list(
            "metadata", flat=True
        )
    )


# Appointment-backed Routine Interview ---------------------------------------------------------


@pytest.mark.django_db
def test_appointment_routine_is_ensured_once_through_the_existing_endpoint():
    _, student, counselor, service = setup_domain("ensure-once")
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    client = auth_client(student)

    first = client.post(
        "/api/v1/routine-interviews/me",
        data=json.dumps({"appointment_id": str(appointment.pk)}),
        content_type="application/json",
        **csrf(client),
    )
    again = client.post(
        "/api/v1/routine-interviews/me",
        data=json.dumps({"appointment_id": str(appointment.pk)}),
        content_type="application/json",
        **csrf(client),
    )
    assert first.status_code == 200
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert RoutineInterview.objects.filter(appointment=appointment).count() == 1
    assert AuditEvent.objects.filter(action="routine_interview.created").count() == 1


@pytest.mark.django_db
def test_inventory_prerequisite_still_gates_the_routine_but_never_the_encounter():
    _, student, counselor, service = setup_domain("inventory-gate", inventory=False)
    appointment = make_appointment(student=student, counselor=counselor, service=service)

    with pytest.raises(RoutineInterviewInventoryRequired):
        ensure_for_appointment(
            student=student, appointment_id=appointment.pk, context=context(student)
        )
    assert not RoutineInterview.objects.exists()

    encounter = record(counselor, entry_mode="APPOINTMENT", appointment_id=appointment.pk)
    assert encounter.appointment_id == appointment.pk
    assert not RoutineInterview.objects.exists()
    assert not AuditEvent.objects.filter(action=LINKED).exists()


# Appointment-backed Encounter -----------------------------------------------------------------


@pytest.mark.django_db
def test_appointment_encounter_is_linked_when_recorded_and_finalizes_without_selection():
    _, student, counselor, service = setup_domain("appointment-link")
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    routine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )
    submit_intake(student, routine)

    encounter = record(counselor, entry_mode="APPOINTMENT", appointment_id=appointment.pk)
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == encounter.pk
    assert routine.evaluation_finalized_at is None
    [event] = link_events(routine)
    assert event == {
        "link_source": "APPOINTMENT",
        "entry_mode": "APPOINTMENT",
        "appointment_id": str(appointment.pk),
        "encounter_id": str(encounter.pk),
    }

    # Retrying the deterministic link is a no-op, and so is ensuring the Routine again.
    assert not routine_services.link_appointment_encounter(
        item=routine, encounter=encounter, context=context(counselor)
    )
    assert (
        ensure_for_appointment(
            student=student, appointment_id=appointment.pk, context=context(student)
        ).counseling_encounter_id
        == encounter.pk
    )
    assert len(link_events(routine)) == 1

    # Nothing is left to choose, so the candidate list is empty.
    assert (
        list_encounter_candidates(counselor=counselor, routine_interview_id=routine.pk).items == ()
    )

    client = auth_client(counselor)
    finalized = client.post(
        f"/api/v1/routine-interviews/{routine.pk}/evaluation/finalize",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert finalized.status_code == 200
    assert finalized.json()["counseling_encounter"]["id"] == str(encounter.pk)
    assert len(link_events(routine)) == 1


@pytest.mark.django_db
def test_routine_ensured_after_the_encounter_is_linked_at_creation():
    _, student, counselor, service = setup_domain("ensure-after")
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    encounter = record(counselor, entry_mode="APPOINTMENT", appointment_id=appointment.pk)

    routine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )
    assert routine.counseling_encounter_id == encounter.pk
    assert [event["link_source"] for event in link_events(routine)] == ["APPOINTMENT"]


@pytest.mark.django_db
def test_incompatible_appointment_encounter_stays_independent_until_corrected():
    _, student, counselor, service = setup_domain("appointment-correct")
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    routine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )

    # Counseling allows a WALK_IN entry on an Appointment; the Routine rules do not.
    encounter = record(counselor, entry_mode="WALK_IN", appointment_id=appointment.pk)
    routine.refresh_from_db()
    assert routine.counseling_encounter_id is None

    update_encounter(
        encounter_id=encounter.pk,
        counselor=counselor,
        changes={"entry_mode": "APPOINTMENT"},
        context=context(counselor),
    )
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == encounter.pk
    assert [event["link_source"] for event in link_events(routine)] == ["APPOINTMENT"]

    # A linked Encounter cannot be corrected out of its Routine Interview, even before
    # finalization; the link is never removed silently.
    with pytest.raises(CounselingLinkedRoutineConflict):
        update_encounter(
            encounter_id=encounter.pk,
            counselor=counselor,
            changes={"appointment_id": None, "entry_mode": "WALK_IN"},
            context=context(counselor),
        )
    encounter.refresh_from_db()
    routine.refresh_from_db()
    assert encounter.appointment_id == appointment.pk
    assert routine.counseling_encounter_id == encounter.pk

    client = auth_client(counselor)
    response = client.patch(
        f"/api/v1/counseling/encounters/{encounter.pk}",
        data=json.dumps({"appointment_id": None, "entry_mode": "WALK_IN"}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "counseling_linked_routine_conflict"


@pytest.mark.django_db
def test_correction_attaching_an_appointment_links_its_routine():
    _, student, counselor, service = setup_domain("attach-appointment")
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    routine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )
    encounter = record(
        counselor, entry_mode="WALK_IN", student_id=student.pk, delivery_mode="IN_PERSON"
    )
    routine.refresh_from_db()
    assert routine.counseling_encounter_id is None

    update_encounter(
        encounter_id=encounter.pk,
        counselor=counselor,
        changes={"appointment_id": appointment.pk, "entry_mode": "APPOINTMENT"},
        context=context(counselor),
    )
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == encounter.pk


# Explicit Routine Interview workspace ---------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("entry_mode", ["WALK_IN", "CALLED_IN", "REFERRED"])
def test_recording_from_direct_routine_context_links_atomically(entry_mode):
    _, student, counselor, _ = setup_domain(f"context-{entry_mode.lower()}")
    routine = submit_intake(
        student, direct_routine(counselor=counselor, student=student, mode=entry_mode)
    )
    client = auth_client(counselor)
    ended_at = timezone.now() - timedelta(minutes=5)

    response = client.post(
        "/api/v1/counseling/encounters",
        data=json.dumps(
            {
                "entry_mode": entry_mode,
                "student_id": str(student.pk),
                "delivery_mode": "IN_PERSON",
                "routine_interview_id": str(routine.pk),
                "started_at": (ended_at - timedelta(minutes=30)).isoformat(),
                "ended_at": ended_at.isoformat(),
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 201
    routine.refresh_from_db()
    assert str(routine.counseling_encounter_id) == response.json()["id"]
    [event] = link_events(routine)
    assert event["link_source"] == "ROUTINE_INTERVIEW_CONTEXT"
    assert event["appointment_id"] is None

    access = resolve_counseling_context(
        actor=counselor, anchor_type="ROUTINE_INTERVIEW", anchor_id=routine.pk
    )
    overview = get_context_overview(access)
    assert str(overview.encounter.id) == response.json()["id"]
    assert overview.encounter.routine_interview_linked is True

    # The Student sees the session only once it backs a finalized Evaluation, as before.
    student_client = auth_client(student)
    assert (
        student_client.get(f"/api/v1/routine-interviews/me/{routine.pk}").json()[
            "counseling_encounter"
        ]
        is None
    )
    finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=None,
        context=context(counselor),
    )
    assert (
        student_client.get(f"/api/v1/routine-interviews/me/{routine.pk}").json()[
            "counseling_encounter"
        ]["id"]
        == response.json()["id"]
    )


@pytest.mark.django_db
def test_routine_context_rejects_mismatches_without_recording_anything():
    _, student, counselor, service = setup_domain("context-mismatch")
    other_student = make_user("context-mismatch-other@example.edu", "STUDENT")
    routine = submit_intake(student, direct_routine(counselor=counselor, student=student))
    appointment = make_appointment(student=student, counselor=counselor, service=service)

    cases = [
        {"student_id": other_student.pk, "entry_mode": "WALK_IN", "delivery_mode": "IN_PERSON"},
        {"student_id": student.pk, "entry_mode": "REFERRED", "delivery_mode": "IN_PERSON"},
        {"student_id": student.pk, "entry_mode": "WALK_IN", "delivery_mode": "ONLINE"},
        {"entry_mode": "APPOINTMENT", "appointment_id": appointment.pk},
    ]
    for case in cases:
        with pytest.raises(CounselingRoutineInterviewMismatch):
            record(counselor, routine_interview_id=routine.pk, **case)
    assert not CounselingEncounter.objects.exists()
    routine.refresh_from_db()
    assert routine.counseling_encounter_id is None


@pytest.mark.django_db
def test_routine_context_requires_the_assigned_counselor_and_routine_capability():
    admin, student, counselor, _ = setup_domain("context-actor")
    other_counselor = make_user("context-actor-other@example.edu", "COUNSELOR")
    routine = submit_intake(student, direct_routine(counselor=counselor, student=student))

    with pytest.raises(CounselingNotFound):
        record(
            other_counselor,
            routine_interview_id=routine.pk,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
        )

    set_user_capability_override(
        user=counselor,
        capability="routine_interviews.manage_assigned",
        effect="REVOKE",
        reason="Routine context linking capability test.",
        created_by=admin,
    )
    client = auth_client(counselor)
    ended_at = timezone.now() - timedelta(minutes=5)
    payload = {
        "entry_mode": "WALK_IN",
        "student_id": str(student.pk),
        "delivery_mode": "IN_PERSON",
        "started_at": (ended_at - timedelta(minutes=30)).isoformat(),
        "ended_at": ended_at.isoformat(),
    }
    denied = client.post(
        "/api/v1/counseling/encounters",
        data=json.dumps({**payload, "routine_interview_id": str(routine.pk)}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 403
    assert not CounselingEncounter.objects.exists()

    # Recording counseling itself never depends on the Routine Interview.
    independent = client.post(
        "/api/v1/counseling/encounters",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )
    assert independent.status_code == 201
    routine.refresh_from_db()
    assert routine.counseling_encounter_id is None


@pytest.mark.django_db
def test_routine_context_retry_is_rejected_once_linked():
    _, student, counselor, _ = setup_domain("context-retry")
    routine = submit_intake(student, direct_routine(counselor=counselor, student=student))
    kwargs = {
        "routine_interview_id": routine.pk,
        "student_id": student.pk,
        "entry_mode": "WALK_IN",
        "delivery_mode": "IN_PERSON",
    }
    first = record(counselor, **kwargs)

    client = auth_client(counselor)
    ended_at = timezone.now() - timedelta(minutes=5)
    retry = client.post(
        "/api/v1/counseling/encounters",
        data=json.dumps(
            {
                "entry_mode": "WALK_IN",
                "student_id": str(student.pk),
                "delivery_mode": "IN_PERSON",
                "routine_interview_id": str(routine.pk),
                "started_at": (ended_at - timedelta(minutes=30)).isoformat(),
                "ended_at": ended_at.isoformat(),
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "counseling_routine_interview_already_linked"
    assert list(CounselingEncounter.objects.values_list("pk", flat=True)) == [first.pk]
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == first.pk


# Generic Encounters and finalization recovery -------------------------------------------------


@pytest.mark.django_db
def test_generic_direct_encounters_are_never_linked_by_similarity():
    _, student, counselor, service = setup_domain("no-fuzzy")
    first = submit_intake(
        student, direct_routine(counselor=counselor, student=student, key="key-1")
    )
    second = submit_intake(
        student, direct_routine(counselor=counselor, student=student, key="key-2")
    )
    generic = record(
        counselor, entry_mode="WALK_IN", student_id=student.pk, delivery_mode="IN_PERSON"
    )
    other = legacy_encounter(student=student, counselor=counselor, service=service)

    for routine in (first, second):
        routine.refresh_from_db()
        assert routine.counseling_encounter_id is None
    assert not AuditEvent.objects.filter(action=LINKED).exists()

    # Both match both Routine Interviews, so COMPASS refuses to choose.
    with pytest.raises(RoutineInterviewEncounterRequired):
        finalize_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=first.pk,
            encounter_id=None,
            context=context(counselor),
        )
    assert {
        item.pk
        for item in list_encounter_candidates(
            counselor=counselor, routine_interview_id=first.pk
        ).items
    } == {generic.pk, other.pk}

    # The workspace reports the similar Encounter, but not as this Routine Interview's.
    access = resolve_counseling_context(
        actor=counselor, anchor_type="ROUTINE_INTERVIEW", anchor_id=first.pk
    )
    assert get_context_overview(access).encounter.routine_interview_linked is False

    # Explicit Counselor recovery links the named Encounter, recorded as recovery.
    finalized = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=first.pk,
        encounter_id=generic.pk,
        context=context(counselor),
    )
    assert finalized.counseling_encounter_id == generic.pk
    assert [event["link_source"] for event in link_events(first)] == ["COUNSELOR_RECOVERY"]

    # An Encounter that belongs to another Routine Interview is never taken over.
    with pytest.raises(RoutineInterviewEncounterConflict, match="already linked"):
        finalize_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=second.pk,
            encounter_id=generic.pk,
            context=context(counselor),
        )
    # Nor does a linked Encounter extend another Routine Interview's workspace.
    second_access = resolve_counseling_context(
        actor=counselor, anchor_type="ROUTINE_INTERVIEW", anchor_id=second.pk
    )
    assert second_access.encounter_id == other.pk


@pytest.mark.django_db
def test_finalization_never_replaces_or_bypasses_an_existing_link():
    _, student, counselor, service = setup_domain("finalize-conflict")
    routine = submit_intake(student, direct_routine(counselor=counselor, student=student))
    linked = record(
        counselor,
        routine_interview_id=routine.pk,
        entry_mode="WALK_IN",
        student_id=student.pk,
        delivery_mode="IN_PERSON",
    )
    other = legacy_encounter(student=student, counselor=counselor, service=service)

    client = auth_client(counselor)
    conflict = client.post(
        f"/api/v1/routine-interviews/{routine.pk}/evaluation/finalize",
        data=json.dumps({"encounter_id": str(other.pk)}),
        content_type="application/json",
        **csrf(client),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "routine_interview_encounter_conflict"
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == linked.pk
    assert routine.evaluation_finalized_at is None

    # Naming the linked Encounter is accepted, as is naming none.
    finalized = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=linked.pk,
        context=context(counselor),
    )
    assert finalized.counseling_encounter_id == linked.pk
    assert len(link_events(routine)) == 1


@pytest.mark.django_db
def test_missing_encounters_still_block_finalization():
    _, student, counselor, service = setup_domain("finalize-missing")
    direct = submit_intake(student, direct_routine(counselor=counselor, student=student))
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    scheduled = submit_intake(
        student,
        ensure_for_appointment(
            student=student, appointment_id=appointment.pk, context=context(student)
        ),
    )

    for routine in (direct, scheduled):
        with pytest.raises(RoutineInterviewEncounterRequired):
            finalize_assigned_evaluation(
                counselor=counselor,
                routine_interview_id=routine.pk,
                encounter_id=None,
                context=context(counselor),
            )
        routine.refresh_from_db()
        assert routine.evaluation_finalized_at is None


@pytest.mark.django_db
def test_legacy_appointment_routine_reconciles_its_single_encounter_at_finalization():
    _, student, counselor, service = setup_domain("legacy-appointment")
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    routine = submit_intake(
        student,
        ensure_for_appointment(
            student=student, appointment_id=appointment.pk, context=context(student)
        ),
    )
    encounter = legacy_encounter(
        student=student,
        counselor=counselor,
        service=service,
        appointment=appointment,
        entry_mode="APPOINTMENT",
    )
    routine.refresh_from_db()
    assert routine.counseling_encounter_id is None

    finalized = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=None,
        context=context(counselor),
    )
    assert finalized.counseling_encounter_id == encounter.pk
    assert [event["link_source"] for event in link_events(routine)] == [
        "APPOINTMENT_RECONCILIATION"
    ]


@pytest.mark.django_db
def test_link_audit_metadata_carries_no_routine_content():
    _, student, counselor, _ = setup_domain("link-audit")
    routine = direct_routine(counselor=counselor, student=student)
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"coping_with_college_challenges": "Highly private response"},
    )
    submit_my_intake(student=student, routine_interview_id=routine.pk, context=context(student))
    record(
        counselor,
        routine_interview_id=routine.pk,
        entry_mode="WALK_IN",
        student_id=student.pk,
        delivery_mode="IN_PERSON",
    )
    serialized = json.dumps(link_events(routine))
    assert "Highly private" not in serialized
    assert "gAAAAA" not in serialized
    assert set(link_events(routine)[0]) == {
        "link_source",
        "entry_mode",
        "appointment_id",
        "encounter_id",
    }


# Concurrency ----------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_routine_context_recordings_link_exactly_one_encounter(monkeypatch):
    ensure_inventory_form_revision()
    _, student, counselor, _ = setup_domain("context-race")
    routine = submit_intake(student, direct_routine(counselor=counselor, student=student))
    monkeypatch.setattr(
        "compass.notifications.services._safe_kick_email_delivery",
        lambda delivery_id: None,
    )

    lock_reached = threading.Event()
    original_lock = routine_services.lock_routine_for_encounter_recording

    def observed_lock(**kwargs):
        if threading.current_thread() is not threading.main_thread():
            lock_reached.set()
        return original_lock(**kwargs)

    monkeypatch.setattr(routine_services, "lock_routine_for_encounter_recording", observed_lock)
    kwargs = {
        "routine_interview_id": routine.pk,
        "student_id": student.pk,
        "entry_mode": "WALK_IN",
        "delivery_mode": "IN_PERSON",
    }

    def competing_recording():
        close_old_connections()
        try:
            actor = User.objects.select_related("role").get(pk=counselor.pk)
            try:
                record(actor, **kwargs)
            except CounselingRoutineInterviewAlreadyLinked:
                return "already linked"
            return "recorded"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            RoutineInterview.objects.select_for_update().get(pk=routine.pk)
            future = executor.submit(competing_recording)
            assert lock_reached.wait(timeout=5)
            assert not future.done()
            winner = record(counselor, **kwargs)
        assert future.result(timeout=10) == "already linked"

    routine.refresh_from_db()
    assert routine.counseling_encounter_id == winner.pk
    assert list(CounselingEncounter.objects.values_list("pk", flat=True)) == [winner.pk]
