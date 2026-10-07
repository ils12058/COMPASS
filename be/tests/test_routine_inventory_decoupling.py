"""ADR-088: Individual Inventory is optional initiation provenance for a Routine Interview."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.appointments.services import (
    AppointmentCurrentInventoryRequired,
    create_student_appointment,
)
from compass.audit.models import AuditEvent
from compass.counseling.context_access import resolve_counseling_context
from compass.counseling.context_services import get_context_inventory
from compass.counseling.services import create_encounter
from compass.inventory.models import StudentInventory
from compass.inventory.services import (
    ensure_current_inventory,
    reopen_inventory_for_correction,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import (
    AcademicYear,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from compass.routine_interviews.content import initial_content
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    create_direct,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    list_assigned,
    list_direct_student_candidates,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from compass.service_catalog.services import update_service
from tests.inventory_test_helpers import (
    ensure_inventory_form_revision,
    minimum_normalized_inventory_values,
)
from tests.test_routine_interviews import (
    auth_client,
    configure_program,
    configure_year,
    context,
    create_counseling_service,
    make_appointment,
    make_user,
    sync_policy,
)


def setup_domain(prefix: str, *, year: bool = True):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    academic_year = configure_year(admin) if year else None
    service = create_counseling_service(admin)
    return admin, student, counselor, service, academic_year


def draft_inventory(student, program) -> StudentInventory:
    ensure_current_inventory(student=student, context=context(student))
    return replace_current_inventory(
        student=student,
        values={
            **minimum_normalized_inventory_values(program_id=program.pk),
            "full_name_snapshot": student.get_full_name(),
            "course_currently_enrolled": "BS Information Systems",
            "major": "Data",
        },
    )


def submitted_inventory(student, program) -> StudentInventory:
    draft_inventory(student, program)
    return submit_current_inventory(student=student, context=context(student))


def reopen(inventory: StudentInventory, counselor) -> StudentInventory:
    StudentAffiliation.objects.get_or_create(
        student=inventory.student, defaults={"college": inventory.program.college}
    )
    CounselorResponsibility.objects.get_or_create(
        college=inventory.program.college, defaults={"counselor": counselor}
    )
    return reopen_inventory_for_correction(
        actor=counselor,
        inventory_id=inventory.pk,
        reason="Please correct the annual record.",
        context=context(counselor),
    )


def direct(counselor, student, *, key: str = "key-1", mode: str = "WALK_IN") -> RoutineInterview:
    return create_direct(
        counselor=counselor,
        student_id=student.pk,
        entry_mode=mode,
        delivery_mode="IN_PERSON",
        idempotency_key=key,
        request_fingerprint=(key.encode().hex() * 64)[:64],
        context=context(counselor),
    )


def submit_intake(student, routine) -> RoutineInterview:
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"college_experience": "Submitted intake."},
    )
    return submit_my_intake(
        student=student, routine_interview_id=routine.pk, context=context(student)
    )


def record_from_context(counselor, student, routine):
    ended_at = timezone.now() - timedelta(minutes=10)
    return create_encounter(
        counselor=counselor,
        entry_mode=routine.entry_mode,
        student_id=student.pk,
        delivery_mode=routine.delivery_mode,
        routine_interview_id=routine.pk,
        started_at=ended_at - timedelta(minutes=30),
        ended_at=ended_at,
        context=context(counselor),
    )


# Appointment-backed creation ------------------------------------------------------------------


@pytest.mark.django_db
def test_appointment_routine_binds_only_a_submitted_current_inventory():
    _, student, counselor, service, year = setup_domain("appointment-states")
    program = configure_program()

    def ensure():
        appointment = make_appointment(student=student, counselor=counselor, service=service)
        return ensure_for_appointment(
            student=student, appointment_id=appointment.pk, context=context(student)
        )

    missing = ensure()
    draft_inventory(student, program)
    draft = ensure()
    inventory = submit_current_inventory(student=student, context=context(student))
    submitted = ensure()
    reopen(inventory, counselor)
    reopened = ensure()

    assert (missing.inventory_id, missing.academic_year_id) == (None, year.pk)
    assert (draft.inventory_id, draft.academic_year_id) == (None, year.pk)
    assert (submitted.inventory_id, submitted.academic_year_id) == (inventory.pk, year.pk)
    assert (reopened.inventory_id, reopened.academic_year_id) == (None, year.pk)

    # Ensuring again returns the same record, never a second one.
    again = ensure_for_appointment(
        student=student, appointment_id=missing.appointment_id, context=context(student)
    )
    assert again.pk == missing.pk
    assert RoutineInterview.objects.filter(appointment_id=missing.appointment_id).count() == 1

    events = {
        event.target_id: event.metadata
        for event in AuditEvent.objects.filter(action="routine_interview.created")
    }
    assert events[str(missing.pk)]["inventory_bound"] is False
    assert events[str(missing.pk)]["academic_year"] == year.label
    assert events[str(submitted.pk)]["inventory_bound"] is True


@pytest.mark.django_db
def test_routine_is_created_without_a_configured_academic_year():
    _, student, counselor, service, _ = setup_domain("no-year", year=False)
    appointment = make_appointment(student=student, counselor=counselor, service=service)

    scheduled = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )
    walk_in = direct(counselor, student)
    for routine in (scheduled, walk_in):
        assert routine.academic_year_id is None
        assert routine.inventory_id is None
    event = AuditEvent.objects.get(action="routine_interview.created", target_id=str(scheduled.pk))
    assert event.metadata["academic_year"] is None
    assert event.metadata["inventory_bound"] is False


# Direct creation and candidates ---------------------------------------------------------------


@pytest.mark.django_db
def test_direct_candidates_and_creation_do_not_require_inventory():
    _, student, counselor, _, year = setup_domain("direct-states")
    program = configure_program()
    missing = make_user("direct-missing@example.edu", "STUDENT")
    drafting = make_user("direct-draft@example.edu", "STUDENT")
    reopened = make_user("direct-reopened@example.edu", "STUDENT")
    submitted = submitted_inventory(student, program)
    draft_inventory(drafting, program)
    reopen(submitted_inventory(reopened, program), counselor)

    page = list_direct_student_candidates(counselor=counselor, page_size=50)
    by_student = {candidate.student.pk: candidate.inventory for candidate in page.items}
    assert by_student[student.pk] == submitted
    for unbound in (missing, drafting, reopened):
        assert by_student[unbound.pk] is None

    # The candidate API never exposes draft Inventory content.
    response = auth_client(counselor).get(
        "/api/v1/routine-interviews/direct/student-candidates", {"page_size": 50}
    )
    rows = {row["id"]: row for row in response.json()["items"]}
    assert rows[str(student.pk)]["inventory_context"]["course"] == "BS Information Systems"
    assert rows[str(drafting.pk)]["inventory_context"] is None
    assert rows[str(reopened.pk)]["inventory_context"] is None

    for unbound in (missing, drafting, reopened):
        routine = direct(counselor, unbound, key=f"key-{unbound.pk}")
        assert routine.inventory_id is None
        assert routine.academic_year_id == year.pk
        replay = direct(counselor, unbound, key=f"key-{unbound.pk}")
        assert replay.pk == routine.pk
    assert direct(counselor, student, key="bound").inventory_id == submitted.pk


# No retroactive attachment --------------------------------------------------------------------


@pytest.mark.django_db
def test_later_inventory_submission_never_attaches_to_an_earlier_routine():
    _, student, counselor, _, _ = setup_domain("retroactive")
    routine = submit_intake(student, direct(counselor, student))
    access = resolve_counseling_context(
        actor=counselor,
        anchor_type="ROUTINE_INTERVIEW",
        anchor_id=routine.pk,
        now=routine.intake_submitted_at + timedelta(minutes=1),
    )
    missing = get_context_inventory(access)
    assert (missing.inventory_source_status, missing.available) == ("MISSING", False)

    inventory = submitted_inventory(student, configure_program())
    routine.refresh_from_db()
    assert routine.inventory_id is None
    assert (
        auth_client(counselor)
        .get(f"/api/v1/routine-interviews/{routine.pk}")
        .json()["inventory_context"]
        is None
    )

    # The Counseling workspace may show the Student's current Inventory as general context,
    # but that is never written back into the Routine Interview.
    enriched = get_context_inventory(access)
    assert enriched.inventory == inventory
    routine.refresh_from_db()
    assert routine.inventory_id is None
    assert direct(counselor, student, key="later").inventory_id == inventory.pk


# Inventory reopen regression ------------------------------------------------------------------


@pytest.mark.django_db
def test_reopened_bound_inventory_never_blocks_or_leaks_through_the_routine():
    _, student, counselor, _, year = setup_domain("reopen")
    inventory = submitted_inventory(student, configure_program())
    routine = direct(counselor, student)
    assert routine.inventory_id == inventory.pk

    reopen(inventory, counselor)
    # The Student starts correcting the annual record; its draft values stay private. Course
    # follows the selected Program, so the correction switches Program.
    corrected_program = Program.objects.create(
        college=inventory.program.college, code="DRAFT", name="DRAFT-PROGRAM-SENTINEL"
    )
    replace_current_inventory(
        student=student,
        values={
            **minimum_normalized_inventory_values(program_id=corrected_program.pk),
            "full_name_snapshot": "DRAFT-NAME-SENTINEL",
            "major": "DRAFT-MAJOR-SENTINEL",
        },
    )
    assert StudentInventory.objects.get(pk=inventory.pk).major == "DRAFT-MAJOR-SENTINEL"

    routine = submit_intake(student, routine)
    assert routine.intake_submitted_at is not None

    responses = [
        auth_client(counselor).get(f"/api/v1/routine-interviews/{routine.pk}"),
        auth_client(student).get(f"/api/v1/routine-interviews/me/{routine.pk}"),
        auth_client(counselor).get("/api/v1/routine-interviews"),
        auth_client(student).get("/api/v1/routine-interviews/me"),
    ]
    for response in responses:
        assert response.status_code == 200
        assert "SENTINEL" not in json.dumps(response.json())
    detail = responses[0].json()
    assert detail["inventory_context"]["id"] == str(inventory.pk)
    assert detail["inventory_context"]["available"] is False
    assert detail["inventory_context"]["course"] is None
    assert detail["academic_year"] == {"id": str(year.pk), "label": year.label}

    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        values={"academic_adjustment_rating": 7},
    )
    encounter = record_from_context(counselor, student, routine)
    finalized = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=None,
        context=context(counselor),
    )
    assert finalized.evaluation_finalized_at is not None
    assert finalized.counseling_encounter_id == encounter.pk
    assert finalized.inventory_id == inventory.pk
    assert finalized.academic_year_id == year.pk

    # Resubmission makes the corrected official values visible again.
    submit_current_inventory(student=student, context=context(student))
    restored = auth_client(counselor).get(f"/api/v1/routine-interviews/{routine.pk}").json()
    assert restored["inventory_context"]["available"] is True
    assert restored["inventory_context"]["course"] == "DRAFT-PROGRAM-SENTINEL"
    assert restored["inventory_context"]["major"] == "DRAFT-MAJOR-SENTINEL"


# API, authorization, and queue ----------------------------------------------------------------


@pytest.mark.django_db
def test_unbound_routine_serializes_with_its_own_academic_year_and_relationships():
    _, student, counselor, _, year = setup_domain("serialize")
    other_counselor = make_user("serialize-other-counselor@example.edu", "COUNSELOR")
    other_student = make_user("serialize-other-student@example.edu", "STUDENT")
    routine = direct(counselor, student)

    counselor_detail = auth_client(counselor).get(f"/api/v1/routine-interviews/{routine.pk}")
    student_detail = auth_client(student).get(f"/api/v1/routine-interviews/me/{routine.pk}")
    for response in (counselor_detail, student_detail):
        assert response.status_code == 200
        assert response.json()["inventory_context"] is None
        assert response.json()["academic_year"] == {"id": str(year.pk), "label": year.label}
    assert counselor_detail.json()["student"]["display_name"] == student.get_full_name()

    assert (
        auth_client(other_counselor).get(f"/api/v1/routine-interviews/{routine.pk}").status_code
        == 404
    )
    assert (
        auth_client(other_student).get(f"/api/v1/routine-interviews/me/{routine.pk}").status_code
        == 404
    )


@pytest.mark.django_db
def test_queue_filters_by_the_routine_academic_year():
    admin, student, counselor, _, first_year = setup_domain("queue")
    bound = direct(counselor, student, key="bound")
    RoutineInterview.objects.filter(pk=bound.pk).update(academic_year=None)  # pre-configuration
    unconfigured = RoutineInterview.objects.get(pk=bound.pk)
    first = direct(counselor, student, key="first")

    second_year = create_academic_year(label="2027-2028", context=context(admin))
    set_current_academic_year(academic_year_id=second_year.pk, context=context(admin))
    second = direct(counselor, student, key="second")
    first.refresh_from_db()
    assert first.academic_year_id == first_year.pk  # never rewritten by the switch

    def ids(**filters):
        page = list_assigned(counselor=counselor, page_size=50, **filters)
        return {item.pk for item in page.items}

    assert ids(academic_year_id=first_year.pk) == {first.pk}
    assert ids(academic_year_id=second_year.pk) == {second.pk}
    assert ids() == {unconfigured.pk, first.pk, second.pk}


# Counseling Context and Encounters ------------------------------------------------------------


@pytest.mark.django_db
def test_unbound_routine_keeps_counseling_context_and_encounter_lifecycle():
    _, student, counselor, service, _ = setup_domain("context")
    routine = submit_intake(student, direct(counselor, student))
    access = resolve_counseling_context(
        actor=counselor,
        anchor_type="ROUTINE_INTERVIEW",
        anchor_id=routine.pk,
        now=routine.intake_submitted_at + timedelta(minutes=1),
    )
    overview = auth_client(counselor).get(
        f"/api/v1/counseling/context/ROUTINE_INTERVIEW/{routine.pk}"
    )
    assert overview.status_code == 200
    assert overview.json()["routine_interview"]["id"] == str(routine.pk)
    assert get_context_inventory(access).available is False

    # Finalization depends on the Encounter, not on any Inventory.
    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        values={"academic_adjustment_rating": 5},
    )
    encounter = record_from_context(counselor, student, routine)
    finalized = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=None,
        context=context(counselor),
    )
    assert finalized.counseling_encounter_id == encounter.pk
    assert finalized.inventory_id is None


# Service Catalog separation -------------------------------------------------------------------


@pytest.mark.django_db
def test_service_inventory_prerequisite_stays_an_appointment_rule_only():
    admin, student, counselor, service, _ = setup_domain("service-rule")
    service = update_service(
        service_id=service.pk,
        changes={"requires_current_inventory": True},
        context=context(admin),
    )
    with pytest.raises(AppointmentCurrentInventoryRequired):
        create_student_appointment(
            student=student,
            service_id=service.pk,
            provider_id=counselor.pk,
            delivery_mode="IN_PERSON",
            starts_at=timezone.now() + timedelta(days=2),
            context=context(student),
        )

    # Once an Appointment exists, its Routine Interview does not re-enforce the Service rule.
    appointment = make_appointment(student=student, counselor=counselor, service=service)
    routine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=context(student)
    )
    assert routine.inventory_id is None
    service.refresh_from_db()
    assert service.requires_current_inventory is True


# Migration ------------------------------------------------------------------------------------

BEFORE = [("routine_interviews", "0003_remove_plaintext_routine_content")]
LATEST = [("routine_interviews", "0004_optional_inventory_and_academic_year")]


@pytest.mark.django_db(transaction=True)
def test_migration_keeps_inventory_links_and_backfills_academic_year():
    ensure_inventory_form_revision()
    _, student, counselor, _, year = setup_domain("migration")
    inventory = submitted_inventory(student, configure_program())
    assert RoutineInterview._meta.get_field("inventory").null

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        Legacy = executor.loader.project_state(BEFORE).apps.get_model(
            "routine_interviews", "RoutineInterview"
        )
        routine_id = Legacy._meta.get_field("id").default()
        Legacy.objects.create(
            id=routine_id,
            student_id=student.pk,
            counselor_id=counselor.pk,
            inventory_id=inventory.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            **initial_content(routine_id),
        )

        MigrationExecutor(connection).migrate(LATEST)
        migrated = RoutineInterview.objects.get(pk=routine_id)
        assert migrated.inventory_id == inventory.pk
        assert migrated.academic_year_id == year.pk == inventory.academic_year_id

        # A Routine Interview without an Inventory cannot be represented by the old schema.
        RoutineInterview.objects.filter(pk=routine_id).update(inventory=None)
        with pytest.raises(RuntimeError, match="cannot be reversed"):
            MigrationExecutor(connection).migrate(BEFORE)
        assert AcademicYear.objects.filter(pk=year.pk).exists()
    finally:
        RoutineInterview.objects.all().delete()
        MigrationExecutor(connection).migrate(LATEST)
