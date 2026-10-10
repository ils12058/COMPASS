"""Bounded deterministic placement through ordinary Appointment discovery (ADR-095)."""

from datetime import datetime, timedelta

from compass.appointments.services import AppointmentError, list_bookable_slots

from .cast import StudentPersona
from .support import DemoSeedConflict, SeedSession
from .timeline import NON_WORKING_DAYS

# Preserve story chronology: search the desired day and the following four calendar days.
# Past work remains before the anchor; future work remains after it.
SEARCH_DAYS = 5


def choose_slot(
    session: SeedSession,
    student: StudentPersona,
    provider_key: str,
    *,
    service_id,
    mode: str,
    desired: datetime,
    booked_at: datetime,
):
    last_day = desired.date() + timedelta(days=SEARCH_DAYS - 1)
    for offset in range(SEARCH_DAYS):
        day = desired.date() + timedelta(days=offset)
        if day.weekday() >= 5 or day in NON_WORKING_DAYS:
            continue
        if (day < session.timeline.anchor) != (desired.date() < session.timeline.anchor):
            continue
        if day == session.timeline.anchor:
            continue
        try:
            slots = list_bookable_slots(
                student=session.user(student.key),
                service_id=service_id,
                provider_id=session.users[provider_key].pk,
                delivery_mode=mode,
                target_date=day,
                now=booked_at,
            ).items
        except AppointmentError as exc:
            raise DemoSeedConflict(
                f"{student.key}/{provider_key}/{mode}: booking discovery rejected the current "
                f"configuration ({type(exc).__name__})."
            ) from exc
        if slots:
            target = session.timeline.at(day, desired.hour, desired.minute)
            return min(slots, key=lambda slot: (abs(slot.starts_at - target), slot.starts_at))
    raise DemoSeedConflict(
        f"{student.key}/{provider_key}/{mode}: no compatible Appointment slot in "
        f"{desired.date().isoformat()} through {last_day.isoformat()}; review Service "
        "qualification, office/provider Availability, exceptions, and reservations. "
        "Existing Availability was preserved."
    )
