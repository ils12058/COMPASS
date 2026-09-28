"""Runtime Guidance configuration the demo depends on, set through the owning services.

Canonical structure (Campus, College, Program, Forms, the Counseling Service) comes only from the
synchronizers. This module adds legitimate runtime relationships on top of it: Counselor
responsibility, Staff supervision, Student affiliation, ONLINE Counseling delivery, and
Availability. Existing configuration is reused; a conflicting relationship fails preflight.
"""

from __future__ import annotations

from datetime import time

from compass.availability.models import (
    OfficeAvailabilityWindow,
    OfficeUnavailability,
    ProviderAvailabilityWindow,
    ProviderUnavailability,
)
from compass.availability.services import (
    create_office_exception,
    create_provider_exception,
    replace_office_weekly,
    replace_provider_weekly,
)
from compass.organization.models import (
    College,
    CounselorResponsibility,
    Program,
    StaffSupervision,
    StudentAffiliation,
)
from compass.organization.services import (
    remove_staff_supervisor,
    set_counselor_responsibility,
    set_staff_supervisor,
    set_student_affiliation,
)
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import DeliveryMode, Service, ServiceDeliveryMode
from compass.service_catalog.services import update_service

from .cast import (
    COUNSELOR_A,
    COUNSELOR_B,
    COUNSELOR_RESPONSIBILITIES,
    FORMER_STAFF,
    HEAD_GUIDANCE,
    STAFF_SUPERVISION,
    STUDENTS,
    StudentPersona,
)
from .support import DemoSeedConflict, SeedSession

WEEKDAYS = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")
MORNING = (time(8, 0), time(12, 0))
AFTERNOON = (time(13, 0), time(17, 0))


def _windows(*blocks: tuple[tuple[time, time], str]) -> list[dict[str, object]]:
    return [
        {"weekday": weekday, "start_time": start, "end_time": end, "mode_scope": scope}
        for weekday in WEEKDAYS
        for (start, end), scope in blocks
    ]


OFFICE_WEEK = _windows((MORNING, "ALL"), (AFTERNOON, "ALL"))
PROVIDER_WEEKS = {
    HEAD_GUIDANCE.key: _windows(((time(13, 0), time(16, 0)), "ALL")),
    COUNSELOR_A.key: _windows((MORNING, "ALL"), (AFTERNOON, "ALL")),
    COUNSELOR_B.key: _windows((MORNING, "IN_PERSON"), (AFTERNOON, "ALL")),
}
# Believable dated exceptions, placed on days without seeded demo appointments.
OFFICE_EXCEPTION_REASON = "GCO quarterly planning workshop (afternoon)"
PROVIDER_EXCEPTION_REASON = "Attending the regional guidance and counseling conference"


def college_for(campus_code: str, college_code: str) -> College:
    college = (
        College.objects.select_related("campus")
        .filter(campus__code=campus_code, code=college_code, is_active=True, campus__is_active=True)
        .first()
    )
    if college is None:
        raise DemoSeedConflict(
            f"College {campus_code}/{college_code} is not in the synchronized active catalog."
        )
    return college


def program_for(persona: StudentPersona) -> Program:
    program = (
        Program.objects.select_related("college__campus")
        .filter(
            college__campus__code=persona.campus_code,
            college__code=persona.college_code,
            code=persona.program_code,
            is_active=True,
        )
        .first()
    )
    if program is None:
        raise DemoSeedConflict(
            f"Program {persona.campus_code}/{persona.college_code}/{persona.program_code} is not "
            "in the synchronized active catalog."
        )
    return program


def check_organization_conflicts(session_users: dict[str, object]) -> None:
    """Refuse to reassign real routing: demo relationships may only be absent or already demo."""

    for counselor_key, campus_code, college_code in COUNSELOR_RESPONSIBILITIES:
        college = college_for(campus_code, college_code)
        current = CounselorResponsibility.objects.filter(college=college).first()
        expected = session_users.get(counselor_key)
        if current is not None and (expected is None or current.counselor_id != expected.pk):
            raise DemoSeedConflict(
                f"College {campus_code}/{college_code} already has a different Counselor "
                "responsibility; the demo seeder does not reassign existing routing."
            )
    for staff_key, supervisor_key in STAFF_SUPERVISION:
        staff = session_users.get(staff_key)
        if staff is None:
            continue
        current = StaffSupervision.objects.filter(staff_id=staff.pk).first()
        supervisor = session_users.get(supervisor_key)
        if current is not None and (supervisor is None or current.supervisor_id != supervisor.pk):
            raise DemoSeedConflict(f"{staff_key} is already supervised by a non-demo Counselor.")
    for persona in STUDENTS:
        student = session_users.get(persona.key)
        if student is None:
            continue
        current = StudentAffiliation.objects.filter(student_id=student.pk).first()
        if current is None:
            continue
        expected = college_for(persona.campus_code, persona.college_code)
        if current.college_id != expected.pk:
            raise DemoSeedConflict(
                f"{persona.label} is affiliated with a different College than the dataset."
            )


def ensure_organization(session: SeedSession) -> None:
    context = session.system()
    for counselor_key, campus_code, college_code in COUNSELOR_RESPONSIBILITIES:
        college = college_for(campus_code, college_code)
        exists = CounselorResponsibility.objects.filter(
            college=college, counselor=session.users[counselor_key]
        ).exists()
        if not exists:
            set_counselor_responsibility(
                college_id=college.pk,
                counselor_id=session.users[counselor_key].pk,
                context=context,
            )
        session.record("Counselor responsibilities", created=not exists)

    for staff_key, supervisor_key in STAFF_SUPERVISION:
        staff = session.user(staff_key)
        exists = StaffSupervision.objects.filter(staff=staff).exists()
        if exists:
            session.record("Staff supervision", created=False)
        elif staff.is_active:
            set_staff_supervisor(
                staff_id=staff.pk,
                supervisor_id=session.users[supervisor_key].pk,
                context=context,
            )
            session.record("Staff supervision", created=True)

    for persona in STUDENTS:
        if not persona.affiliated:
            continue
        student = session.users[persona.key]
        exists = StudentAffiliation.objects.filter(student=student).exists()
        if not exists:
            set_student_affiliation(
                student_id=student.pk,
                college_id=college_for(persona.campus_code, persona.college_code).pk,
                context=context,
            )
        session.record("Student affiliations", created=not exists)


def ensure_counseling_configuration(session: SeedSession) -> None:
    """Enable ONLINE Counseling and a usable weekly schedule; never replace existing schedules."""

    context = session.system()
    service = Service.objects.get(code=COUNSELING_SERVICE_CODE)
    modes = set(ServiceDeliveryMode.objects.filter(service=service).values_list("mode", flat=True))
    if DeliveryMode.ONLINE not in modes:
        # ADR-060 leaves ONLINE as an explicit deployment choice; the demo makes that choice so
        # the E-Counseling workspace has an eligible Appointment. Daily stays lazy.
        update_service(
            service_id=service.pk,
            changes={"delivery_modes": sorted({*modes, DeliveryMode.ONLINE})},
            context=context,
        )
    session.record("Counseling delivery modes", created=DeliveryMode.ONLINE not in modes)

    office_exists = OfficeAvailabilityWindow.objects.exists()
    if not office_exists:
        replace_office_weekly(windows=OFFICE_WEEK, context=context)
    session.record("Office weekly schedule", created=not office_exists)

    for key, windows in PROVIDER_WEEKS.items():
        provider = session.users[key]
        exists = ProviderAvailabilityWindow.objects.filter(provider=provider).exists()
        if not exists:
            replace_provider_weekly(provider_id=provider.pk, windows=windows, context=context)
        session.record("Provider weekly schedules", created=not exists)

    timeline = session.timeline
    office_day = timeline.business_day(10)
    if not OfficeUnavailability.objects.filter(reason=OFFICE_EXCEPTION_REASON).exists():
        create_office_exception(
            starts_at=timeline.at(office_day, 13),
            ends_at=timeline.at(office_day, 17),
            mode_scope="ALL",
            reason=OFFICE_EXCEPTION_REASON,
            context=context,
        )
        session.record("Availability exceptions", created=True)
    else:
        session.record("Availability exceptions", created=False)

    counselor_b = session.users[COUNSELOR_B.key]
    leave_day = timeline.business_day(8)
    if not ProviderUnavailability.objects.filter(
        provider=counselor_b, reason=PROVIDER_EXCEPTION_REASON
    ).exists():
        create_provider_exception(
            provider_id=counselor_b.pk,
            starts_at=timeline.at(leave_day, 8),
            ends_at=timeline.at(leave_day, 17),
            mode_scope="ALL",
            reason=PROVIDER_EXCEPTION_REASON,
            context=context,
        )
        session.record("Availability exceptions", created=True)
    else:
        session.record("Availability exceptions", created=False)


def offboard_former_staff(session: SeedSession) -> None:
    """End the departed staff member's supervision once their historical records exist."""

    staff = session.users[FORMER_STAFF.key]
    if StaffSupervision.objects.filter(staff=staff).exists():
        remove_staff_supervisor(staff_id=staff.pk, context=session.system())


__all__ = [
    "OFFICE_EXCEPTION_REASON",
    "OFFICE_WEEK",
    "PROVIDER_EXCEPTION_REASON",
    "PROVIDER_WEEKS",
    "check_organization_conflicts",
    "college_for",
    "ensure_counseling_configuration",
    "ensure_organization",
    "offboard_former_staff",
    "program_for",
]
