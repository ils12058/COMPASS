"""Population units shared by action-ready and background Students.

Each Student's Inventory history, graduate Exit Interview, lifecycle and Graduate Tracer are one
bounded transaction. Existing records are authoritative: a unit that finds a record keeps it, a
unit that finds a conflicting academic identity stops, and an established graduate is never moved
back into enrollment to fabricate missing history.
"""

from datetime import timedelta

from django.db import transaction

from compass.appointments.models import Appointment
from compass.appointments.services import cancel_appointment, mark_appointment_no_show
from compass.exit_interviews.models import ExitInterview
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.graduate_tracer.services import (
    ensure_my_response,
    replace_my_draft,
    submit_my_response,
)
from compass.inventory.models import StudentInventory
from compass.organization.academic_years import get_current_academic_year
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import replace_assigned_evaluation

from .. import workflows as wf
from ..accounts import set_student_lifecycle
from ..content.forms import (
    CAREER_EVALUATION,
    CAREER_INTAKE,
    NO_INVENTORY_INTAKE,
    exit_answers,
    tracer_answers,
)
from ..history import _ensure_year, _make_current, seed_annual_inventory, seed_exit_interview
from ..identities import Lifecycle, StudentSpec
from ..organization import program_for
from ..staff import counselor_for
from ..students import BACKGROUND_STUDENTS, POPULATION_STUDENTS, STUDENTS_BY_KEY
from ..support import SeedSession, StagingSeedConflict, align_timestamps, settle_notifications
from ..timeline import CURRENT_ACADEMIC_YEAR
from .rich import tracer_values

# Four current graduating background Students carry Exit work. Others remain not started.
CURRENT_EXITS = {
    "bg_04": "EARLY",
    "bg_07": "NEARLY",
    "bg_11": "SUBMITTED",
    "bg_14": "SUBMITTED",
}
# Lightweight reservations: most Students remain appointment-free.
APPOINTMENT_STORIES = (
    ("bg_01", "SCHEDULED", "ONLINE"),
    ("bg_02", "SCHEDULED", "IN_PERSON"),
    ("bg_05", "CANCELLED", "IN_PERSON"),
    ("bg_06", "CANCELLED", "IN_PERSON"),
    ("bg_08", "NO_SHOW", "IN_PERSON"),
    ("bg_09", "COMPLETED", "IN_PERSON"),
    ("bg_55", "COMPLETED", "IN_PERSON"),
    ("bg_59", "SCHEDULED", "IN_PERSON"),
)


def _exit(session: SeedSession, student: StudentSpec, label: str, *, depth="SUBMITTED"):
    existing = ExitInterview.objects.filter(
        student=session.user(student.key), academic_year__label=label
    )
    if existing.exists():
        session.record("Exit Interviews", created=False)
        return
    if session.user(student.key).student_lifecycle_status != Lifecycle.CURRENT:
        raise StagingSeedConflict(
            f"{student.key}: missing Exit history requires CURRENT lifecycle back-entry; "
            "review the existing dataset history instead of rewriting lifecycle."
        )
    t = session.timeline
    started = t.on(2026, 4, 14, 18) if label != CURRENT_ACADEMIC_YEAR else t.past(5, 18)
    saved = started + timedelta(minutes=35)
    seed_exit_interview(
        session,
        student,
        started=started,
        saved=saved,
        submitted=saved if depth == "SUBMITTED" else None,
        narrative=exit_answers(student.ordinal, depth=depth),
    )


def seed_population_member(session: SeedSession, student: StudentSpec) -> None:
    with transaction.atomic():
        current = get_current_academic_year()
        history_entered = False
        try:
            for label, year_level in student.year_levels:
                item = StudentInventory.objects.filter(
                    student=session.user(student.key), academic_year__label=label
                ).first()
                if item is not None:
                    if item.program_id != program_for(student).pk or item.year_level != year_level:
                        raise StagingSeedConflict(
                            f"{student.key}/{label}: existing Inventory academic identity "
                            "conflicts."
                        )
                    session.record("Inventories", created=False)
                else:
                    if session.user(student.key).student_lifecycle_status != Lifecycle.CURRENT:
                        raise StagingSeedConflict(
                            f"{student.key}/{label}: missing Inventory history requires "
                            "CURRENT lifecycle; existing history was preserved."
                        )
                    _make_current(session, _ensure_year(session, label))
                    seed_annual_inventory(session, student, label)
                    history_entered = True
                if (
                    student.lifecycle == Lifecycle.GRADUATED
                    and not ExitInterview.objects.filter(
                        student=session.user(student.key), academic_year__label=label
                    ).exists()
                ):
                    _make_current(session, _ensure_year(session, label))
                    _exit(session, student, label)
                    history_entered = True
            if student.lifecycle != Lifecycle.CURRENT and history_entered:
                # A new account is CURRENT until its historical enrolled forms exist. Reruns
                # never move an established graduate/former Student back into enrollment.
                set_student_lifecycle(session, student, student.lifecycle)
        finally:
            _make_current(session, current)
        if student.key in CURRENT_EXITS:
            _exit(session, student, CURRENT_ACADEMIC_YEAR, depth=CURRENT_EXITS[student.key])
        if student.lifecycle == Lifecycle.GRADUATED and student.tracer != "missing":
            if GraduateTracerResponse.objects.filter(student=session.user(student.key)).exists():
                session.record("Graduate Tracer responses", created=False)
            else:
                user = session.user(student.key)
                response = ensure_my_response(student=user, context=session.as_user(student.key))
                replace_my_draft(
                    student=user,
                    values=tracer_values(
                        response,
                        student,
                        tracer_answers(student, program_for(student)),
                        graduation_year=2026,
                    ),
                )
                saved = session.timeline.past(3, 19, student.ordinal % 60)
                if student.tracer != "draft":
                    submit_my_response(
                        student=user, context=session.as_user(student.key), now=saved
                    )
                align_timestamps(
                    response, created_at=saved - timedelta(minutes=25), updated_at=saved
                )
                session.record("Graduate Tracer responses", created=True)


def seed_population_forms(session: SeedSession) -> None:
    for student in POPULATION_STUDENTS:
        try:
            seed_population_member(session, student)
        except StagingSeedConflict as exc:
            raise StagingSeedConflict(f"{student.key}: {exc}") from exc


def _counselor(student: StudentSpec) -> str:
    return counselor_for(student.campus_code, student.college_code)


def seed_secondary_stories(session: SeedSession) -> None:
    # Two compact Routine stories add a second pending evaluation and prove ADR-088 with no
    # Inventory. They have no Shared Summary; an Encounter need not have one.
    for key, intake, finalize in (
        ("bg_38", NO_INVENTORY_INTAKE, False),
        ("bg_27", CAREER_INTAKE, True),
    ):
        student = STUDENTS_BY_KEY[key]
        counselor = _counselor(student)
        with transaction.atomic():
            if RoutineInterview.objects.filter(student=session.user(key)).exists():
                session.record("Secondary Routine stories", created=False)
                continue
            t = session.timeline
            routine = wf.direct_routine(
                session, counselor, student, entry_mode="WALK_IN", created=t.past(7, 14)
            )
            wf.student_intake(
                session, student, routine, intake, saved=t.past(7, 14, 25), submit=True
            )
            wf.encounter(
                session,
                counselor,
                student,
                entry_mode="WALK_IN",
                started=t.past(7, 14),
                ended=t.past(7, 14, 45),
                recorded=t.past(7, 15),
                routine=routine,
            )
            if finalize:
                wf.finalize_evaluation(
                    session, counselor, routine, CAREER_EVALUATION, at=t.past(7, 16)
                )
            else:
                replace_assigned_evaluation(
                    counselor=session.user(counselor),
                    routine_interview_id=routine.pk,
                    values={"academic_adjustment_rating": 8, "financial_adjustment_rating": 7},
                )
            session.record("Secondary Routine stories", created=True)

    # Each Student's booking is a bounded unit; existing Appointments are never rewritten.
    for index, (key, state, mode) in enumerate(APPOINTMENT_STORIES, 1):
        student = STUDENTS_BY_KEY[key]
        counselor = _counselor(student)
        with transaction.atomic():
            if Appointment.objects.filter(student=session.user(key)).exists():
                session.record("Background Appointment stories", created=False)
                continue
            t = session.timeline
            desired = t.future(5 + index, 14) if state == "SCHEDULED" else t.past(10 + index, 14)
            appointment = wf.book(
                session,
                student,
                counselor,
                starts_at=desired,
                booked_at=t.past(22 + index, 10),
                mode=mode,
            )
            if state == "CANCELLED":
                cancelled = cancel_appointment(
                    appointment_id=appointment.pk,
                    actor=session.user(key),
                    administrative=False,
                    context=session.as_user(key),
                    now=t.past(21 + index, 12),
                )
                settle_notifications(source_id=cancelled.pk, occurred_at=cancelled.cancelled_at)
            elif state == "NO_SHOW":
                mark_appointment_no_show(
                    appointment_id=appointment.pk,
                    actor=session.user(counselor),
                    context=session.as_user(counselor),
                    now=appointment.ends_at + timedelta(minutes=20),
                )
            elif state == "COMPLETED":
                wf.complete(
                    session, counselor, appointment, at=appointment.ends_at + timedelta(minutes=20)
                )
                wf.encounter(
                    session,
                    counselor,
                    student,
                    entry_mode="APPOINTMENT",
                    started=appointment.starts_at,
                    ended=appointment.ends_at,
                    recorded=appointment.ends_at + timedelta(minutes=25),
                    appointment=appointment,
                )
            session.record("Background Appointment stories", created=True)


__all__ = [
    "APPOINTMENT_STORIES",
    "BACKGROUND_STUDENTS",
    "CURRENT_EXITS",
    "seed_population_forms",
    "seed_population_member",
    "seed_secondary_stories",
]
