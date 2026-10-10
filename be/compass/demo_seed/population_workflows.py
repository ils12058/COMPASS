"""Additive v2 population units. Existing forms and history remain authoritative."""

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

from .accounts import set_student_lifecycle
from .configuration import program_for
from .history import _ensure_year, _make_current, seed_annual_inventory, seed_exit_interview
from .personas import Lifecycle
from .population import MEMBERS_BY_KEY, POPULATION
from .population_forms import (
    CAREER_EVALUATION,
    CAREER_INTAKE,
    NO_INVENTORY_INTAKE,
    exit_answers,
    tracer_answers,
)
from .scenarios import (
    _book,
    _complete,
    _direct_routine,
    _encounter,
    _finalize_evaluation,
    _student_intake,
    _tracer_values,
)
from .support import DemoSeedConflict, SeedSession, align_timestamps, settle_notifications
from .timeline import CURRENT_ACADEMIC_YEAR

# Only four current graduating Students receive extra Exit work. Others remain not started.
CURRENT_EXITS = {
    "population_04": "EARLY",
    "population_07": "NEARLY",
    "population_11": "SUBMITTED",
    "population_14": "SUBMITTED",
}


def _exit(session, member, label, *, index, depth="SUBMITTED"):
    p = member.persona
    existing = ExitInterview.objects.filter(student=session.user(p.key), academic_year__label=label)
    if existing.exists():
        session.record("Exit Interviews", created=False)
        return
    if session.user(p.key).student_lifecycle_status != Lifecycle.CURRENT:
        raise DemoSeedConflict(
            f"{p.key}: missing Exit history requires CURRENT lifecycle back-entry; "
            "review the existing demo history instead of rewriting lifecycle."
        )
    t = session.timeline
    started = t.on(2026, 4, 14, 18) if label != CURRENT_ACADEMIC_YEAR else t.past(5, 18)
    saved = started + timedelta(minutes=35)
    seed_exit_interview(
        session,
        p,
        started=started,
        saved=saved,
        submitted=saved if depth == "SUBMITTED" else None,
        narrative=exit_answers(index, depth=depth),
    )


def seed_population_member(session: SeedSession, member) -> None:
    p = member.persona
    with transaction.atomic():
        current = get_current_academic_year()
        history_entered = False
        try:
            for label, year_level in p.year_levels:
                item = StudentInventory.objects.filter(
                    student=session.user(p.key), academic_year__label=label
                ).first()
                if item is not None:
                    if item.program_id != program_for(p).pk or item.year_level != year_level:
                        raise DemoSeedConflict(
                            f"{p.key}/{label}: existing Inventory academic identity conflicts."
                        )
                    session.record("Inventories", created=False)
                else:
                    if session.user(p.key).student_lifecycle_status != Lifecycle.CURRENT:
                        raise DemoSeedConflict(
                            f"{p.key}/{label}: missing Inventory history requires "
                            "CURRENT lifecycle; existing history was preserved."
                        )
                    _make_current(session, _ensure_year(session, label))
                    seed_annual_inventory(session, p, label)
                    history_entered = True
                if (
                    p.lifecycle == Lifecycle.GRADUATED
                    and not ExitInterview.objects.filter(
                        student=session.user(p.key), academic_year__label=label
                    ).exists()
                ):
                    _make_current(session, _ensure_year(session, label))
                    _exit(session, member, label, index=int(p.key[-2:]))
                    history_entered = True
            if p.lifecycle != Lifecycle.CURRENT and history_entered:
                # A new account is CURRENT until its historical enrolled forms exist. Reruns
                # never move an established graduate/former Student back into enrollment.
                set_student_lifecycle(session, p, p.lifecycle)
        finally:
            _make_current(session, current)
        if p.key in CURRENT_EXITS:
            _exit(
                session,
                member,
                CURRENT_ACADEMIC_YEAR,
                index=int(p.key[-2:]),
                depth=CURRENT_EXITS[p.key],
            )
        if p.lifecycle == Lifecycle.GRADUATED and member.tracer != "missing":
            if GraduateTracerResponse.objects.filter(student=session.user(p.key)).exists():
                session.record("Graduate Tracer responses", created=False)
            else:
                user = session.user(p.key)
                response = ensure_my_response(student=user, context=session.as_user(p.key))
                replace_my_draft(
                    student=user,
                    values=_tracer_values(response, p, tracer_answers(member, program_for(p))),
                )
                saved = session.timeline.past(3, 19, int(p.key[-2:]))
                if member.tracer != "draft":
                    submit_my_response(student=user, context=session.as_user(p.key), now=saved)
                align_timestamps(
                    response, created_at=saved - timedelta(minutes=25), updated_at=saved
                )
                session.record("Graduate Tracer responses", created=True)


def seed_population_forms(session: SeedSession) -> None:
    for member in POPULATION:
        try:
            seed_population_member(session, member)
        except DemoSeedConflict as exc:
            raise DemoSeedConflict(f"{member.persona.key}: {exc}") from exc


def seed_secondary_stories(session: SeedSession) -> None:
    # Two compact Routine stories add a second pending evaluation and prove ADR-088 with no
    # Inventory. They have no Shared Summary; an Encounter need not have one.
    for key, counselor, intake, finalize in (
        ("population_38", "counselor_a", NO_INVENTORY_INTAKE, False),
        ("population_27", "counselor_b", CAREER_INTAKE, True),
    ):
        with transaction.atomic():
            if RoutineInterview.objects.filter(student=session.user(key)).exists():
                session.record("Secondary Routine stories", created=False)
                continue
            p = MEMBERS_BY_KEY[key].persona
            t = session.timeline
            routine = _direct_routine(
                session, counselor, p, entry_mode="WALK_IN", created=t.past(7, 14)
            )
            _student_intake(session, p, routine, intake, saved=t.past(7, 14, 25), submit=True)
            _encounter(
                session,
                counselor,
                p,
                entry_mode="WALK_IN",
                started=t.past(7, 14),
                ended=t.past(7, 14, 45),
                recorded=t.past(7, 15),
                routine=routine,
            )
            if finalize:
                _finalize_evaluation(
                    session, counselor, routine, CAREER_EVALUATION, at=t.past(7, 16)
                )
            else:
                replace_assigned_evaluation(
                    counselor=session.user(counselor),
                    routine_interview_id=routine.pk,
                    values={"academic_adjustment_rating": 8, "financial_adjustment_rating": 7},
                )
            session.record("Secondary Routine stories", created=True)

    # Eight lightweight reservations: most Students remain appointment-free. Each Student's
    # booking is a bounded unit; existing appointments are never rewritten.
    for index, state in (
        (1, "SCHEDULED"),
        (2, "SCHEDULED"),
        (3, "SCHEDULED"),
        (4, "SCHEDULED"),
        (5, "CANCELLED"),
        (6, "CANCELLED"),
        (8, "NO_SHOW"),
        (9, "COMPLETED"),
    ):
        key = f"population_{index:02d}"
        p = MEMBERS_BY_KEY[key].persona
        counselor = "counselor_b" if p.college_code in {"CBPA", "COED"} else "counselor_a"
        with transaction.atomic():
            if Appointment.objects.filter(student=session.user(key)).exists():
                session.record("Population Appointment stories", created=False)
                continue
            t = session.timeline
            desired = t.future(5 + index, 14) if state == "SCHEDULED" else t.past(10 + index, 14)
            appointment = _book(
                session,
                p,
                counselor,
                starts_at=desired,
                booked_at=t.past(22 + index, 10),
                mode="ONLINE" if index in {1, 3} else "IN_PERSON",
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
                _complete(
                    session, counselor, appointment, at=appointment.ends_at + timedelta(minutes=20)
                )
                _encounter(
                    session,
                    counselor,
                    p,
                    entry_mode="APPOINTMENT",
                    started=appointment.starts_at,
                    ended=appointment.ends_at,
                    recorded=appointment.ends_at + timedelta(minutes=25),
                    appointment=appointment,
                )
            session.record("Population Appointment stories", created=True)
