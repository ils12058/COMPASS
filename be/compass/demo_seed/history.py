"""Academic Years and historical back-entry through the normal current-year services.

Inventory, Exit Interview, and Routine Interview services only act on the institution's current
Academic Year, by design. To give the cast believable multi-year histories through those same
services, a clean database is walked forward year by year: each historical Academic Year becomes
current, its records are entered, end-of-year lifecycle transitions are applied, and the dataset's
current year is selected last. All of it happens in one transaction, so no other session ever
observes a historical year as current. On a clean database the audit trail therefore reads as a
normal progression 2024-2025 -> 2025-2026 -> 2026-2027.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import transaction

from compass.accounts.profiles import update_my_profile
from compass.exit_interviews.opportunities import open_opportunity
from compass.exit_interviews.services import (
    ensure_my_current,
    replace_my_current,
    submit_my_current,
)
from compass.inventory.models import StudentInventory
from compass.inventory.services import (
    derive_age_on,
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import (
    create_academic_year,
    get_current_academic_year,
    set_current_academic_year,
)
from compass.organization.models import AcademicYear

from .accounts import set_student_lifecycle
from .cast import (
    ALUMNI,
    FORMER,
    RECENT_GRADUATE,
    STUDENTS,
    AuthState,
    Lifecycle,
    StudentPersona,
)
from .configuration import program_for
from .inventory_data import inventory_values, inventory_year, inventory_years
from .narratives import ALUMNI_EXIT_INTERVIEW, RECENT_GRADUATE_EXIT_INTERVIEW
from .support import DemoSeedConflict, SeedSession, align_timestamps
from .timeline import CURRENT_ACADEMIC_YEAR, DATASET_ACADEMIC_YEARS, HISTORICAL_ACADEMIC_YEARS

# Historical Exit Interviews: (persona, Academic Year, started, submitted).
HISTORICAL_EXIT_INTERVIEWS = (
    (ALUMNI, "2024-2025", (2025, 3, 17, 10, 5), (2025, 3, 20, 14, 30), ALUMNI_EXIT_INTERVIEW),
    (
        RECENT_GRADUATE,
        "2025-2026",
        (2026, 4, 13, 9, 40),
        (2026, 4, 16, 15, 10),
        RECENT_GRADUATE_EXIT_INTERVIEW,
    ),
)
# Lifecycle changes recorded when each historical Academic Year closes.
END_OF_YEAR_TRANSITIONS = {
    "2024-2025": ((ALUMNI, Lifecycle.GRADUATED),),
    "2025-2026": ((RECENT_GRADUATE, Lifecycle.GRADUATED), (FORMER, Lifecycle.FORMER)),
}
# How long before submission a Student opened the form (created_at of the annual record).
FORM_STARTED_BEFORE = timedelta(minutes=45)


def historical_inventory_plan() -> tuple[tuple[StudentPersona, str], ...]:
    return tuple(
        (persona, label)
        for persona in STUDENTS
        for label in inventory_years(persona)
        if label in HISTORICAL_ACADEMIC_YEARS
    )


def _existing_inventory(session: SeedSession, persona: StudentPersona, label: str):
    student = session.users.get(persona.key)
    if student is None:
        return None
    return StudentInventory.objects.filter(student=student, academic_year__label=label).first()


def historical_state(session: SeedSession) -> str:
    plan = historical_inventory_plan()
    present = sum(
        1 for persona, label in plan if _existing_inventory(session, persona, label) is not None
    )
    if present == 0:
        return "missing"
    if present == len(plan):
        return "complete"
    return "partial"


def check_history_preconditions(session: SeedSession) -> None:
    current = get_current_academic_year()
    if current is not None and current.label not in DATASET_ACADEMIC_YEARS:
        raise DemoSeedConflict(
            f"The current Academic Year is {current.label}; demo dataset version 1 requires "
            f"{CURRENT_ACADEMIC_YEAR}. Resolve Academic Year configuration before seeding."
        )
    state = historical_state(session)
    if state == "partial":
        raise DemoSeedConflict(
            "Only part of the demo cast's historical Inventories exist. Review the demo history "
            "manually; the seeder does not repair partial history."
        )
    if state == "missing":
        for persona, _label in historical_inventory_plan():
            user = session.users.get(persona.key)
            if user is not None and user.student_lifecycle_status != Lifecycle.CURRENT:
                raise DemoSeedConflict(
                    f"{persona.label} must still be CURRENT for historical back-entry."
                )


def _moment(parts: tuple[int, int, int, int, int], session: SeedSession) -> datetime:
    return session.timeline.on(*parts)


def seed_profiles(session: SeedSession, *, created_keys: set[str]) -> None:
    """Newly provisioned ready Students maintain their own current profile, as users do."""

    for persona in STUDENTS:
        if persona.key not in created_keys or persona.auth_state != AuthState.READY:
            continue
        update_my_profile(
            user=session.user(persona.key),
            changes={
                "date_of_birth": persona.date_of_birth,
                "civil_status": persona.civil_status,
                "current_address": persona.home_address,
                "permanent_address": persona.home_address,
            },
            context=session.as_user(persona.key),
        )


def seed_annual_inventory(session: SeedSession, persona: StudentPersona, label: str) -> None:
    """Enter one annual Inventory through the current-year services and align its dates."""

    student = session.user(persona.key)
    context = session.as_user(persona.key)
    year = inventory_year(persona, label)
    saved_at = _moment(year.saved_at, session)
    ensure_current_inventory(student=student, context=context)
    values = inventory_values(persona, label, email=session.emails[persona.key])
    values["program_id"] = program_for(persona).pk
    replace_current_inventory(student=student, values=values)
    item = StudentInventory.objects.get(student=student, academic_year__label=label)
    if year.draft:
        align_timestamps(item, created_at=saved_at - FORM_STARTED_BEFORE, updated_at=saved_at)
    else:
        submit_current_inventory(student=student, context=context)
        align_timestamps(
            item,
            created_at=saved_at - FORM_STARTED_BEFORE,
            updated_at=saved_at,
            submitted_at=saved_at,
            first_submitted_at=saved_at,
            last_submitted_at=saved_at,
        )
    session.record("Inventories", created=True)


def seed_exit_interview(
    session: SeedSession,
    persona: StudentPersona,
    *,
    started: datetime,
    saved: datetime,
    submitted: datetime | None,
    narrative: dict[str, object],
) -> None:
    student = session.user(persona.key)
    context = session.as_user(persona.key)
    # The demo scenario explicitly opens manual access; it never infers graduation.
    opportunity = open_opportunity(
        actor=session.user("head_guidance"),
        student_id=student.pk,
        academic_year_id=get_current_academic_year().pk,
        source="MANUAL",
        note="",
        context=session.as_user("head_guidance"),
    )
    align_timestamps(opportunity, created_at=started, updated_at=started, opened_at=started)
    item = ensure_my_current(student=student, context=context)
    reference = (submitted or started).date()
    values = {
        "student_name_snapshot": item.student_name_snapshot,
        "age_snapshot": derive_age_on(date_of_birth=persona.date_of_birth, on_date=reference),
        "civil_status_snapshot": item.civil_status_snapshot,
        "course_snapshot": item.course_snapshot,
        "major_snapshot": item.major_snapshot,
        "email_snapshot": item.email_snapshot,
        "home_address_snapshot": item.home_address_snapshot,
        "contact_number_snapshot": item.contact_number_snapshot,
        **narrative,
    }
    replace_my_current(student=student, values=values)
    if submitted is not None:
        submit_my_current(student=student, context=context, now=submitted)
        align_timestamps(opportunity, updated_at=submitted)
    align_timestamps(item, created_at=started, updated_at=submitted or saved)
    session.record("Exit Interviews", created=True)


def _ensure_year(session: SeedSession, label: str) -> AcademicYear:
    year = AcademicYear.objects.filter(label=label).first()
    if year is None:
        year = create_academic_year(label=label, context=session.system())
        session.record("Academic Years", created=True)
    else:
        session.record("Academic Years", created=False)
    return year


def _make_current(session: SeedSession, year: AcademicYear) -> None:
    current = get_current_academic_year()
    if current is None or current.pk != year.pk:
        set_current_academic_year(academic_year_id=year.pk, context=session.system())


def run_academic_timeline(session: SeedSession) -> None:
    with transaction.atomic():
        state = historical_state(session)
        if state == "partial":
            raise DemoSeedConflict("demo history became partial while seeding")
        if state == "complete":
            for label in HISTORICAL_ACADEMIC_YEARS:
                _ensure_year(session, label)
            _make_current(session, _ensure_year(session, CURRENT_ACADEMIC_YEAR))
            session.record("Inventories", created=False, count=len(historical_inventory_plan()))
            session.record("Exit Interviews", created=False, count=len(HISTORICAL_EXIT_INTERVIEWS))
            return

        for label in HISTORICAL_ACADEMIC_YEARS:
            year = _ensure_year(session, label)
            _make_current(session, year)
            for persona, planned_label in historical_inventory_plan():
                if planned_label == label:
                    seed_annual_inventory(session, persona, label)
            for persona, planned_label, started, submitted, narrative in HISTORICAL_EXIT_INTERVIEWS:
                if planned_label == label:
                    seed_exit_interview(
                        session,
                        persona,
                        started=_moment(started, session),
                        saved=_moment(submitted, session),
                        submitted=_moment(submitted, session),
                        narrative=narrative,
                    )
            for persona, status in END_OF_YEAR_TRANSITIONS.get(label, ()):
                set_student_lifecycle(session, persona, status)
                session.record("Lifecycle transitions", created=True)

        _make_current(session, _ensure_year(session, CURRENT_ACADEMIC_YEAR))


__all__ = [
    "END_OF_YEAR_TRANSITIONS",
    "HISTORICAL_EXIT_INTERVIEWS",
    "check_history_preconditions",
    "historical_inventory_plan",
    "historical_state",
    "run_academic_timeline",
    "seed_annual_inventory",
    "seed_exit_interview",
    "seed_profiles",
]
