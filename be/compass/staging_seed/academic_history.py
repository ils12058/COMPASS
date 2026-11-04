"""Canonical academic-period and graduation history for the seeded Student population.

Runs after every lifecycle alignment, so a graduation record reflects the lifecycle the
dataset already established instead of changing it early. Periods are recorded through the
owning service for each Academic Year already present; missing years are skipped, never
invented.
"""

from __future__ import annotations

from datetime import date

from compass.organization.models import AcademicYear
from compass.student_academics.models import (
    StudentAcademicPeriodRecord,
    StudentGraduationRecord,
)
from compass.student_academics.services import record_academic_period, record_graduation

from .identities import Lifecycle
from .organization import college_for
from .students import STUDENTS
from .support import SeedSession

ACADEMIC_TERM = "FIRST_SEMESTER"
GRADUATION_VERIFICATION_SOURCE = "Staging seed: Registrar confirmation"


def seed_academic_history(session: SeedSession) -> None:
    context = session.system()
    years = {year.label: year for year in AcademicYear.objects.all()}
    for persona in STUDENTS:
        if not persona.year_levels:
            continue
        student = session.users.get(persona.key)
        if student is None:
            continue
        college = college_for(persona.campus_code, persona.college_code)
        for label, year_level in persona.year_levels:
            academic_year = years.get(label)
            if academic_year is None:
                continue
            exists = StudentAcademicPeriodRecord.objects.filter(
                student=student, academic_year=academic_year, term=ACADEMIC_TERM
            ).exists()
            if not exists:
                record_academic_period(
                    student_id=student.pk,
                    academic_year_id=academic_year.pk,
                    term=ACADEMIC_TERM,
                    college_id=college.pk,
                    year_level=year_level,
                    enrollment_status="ENROLLED",
                    context=context,
                )
            session.record("Student academic periods", created=not exists)

        if persona.lifecycle != Lifecycle.GRADUATED:
            continue
        final_label = persona.year_levels[-1][0]
        if final_label not in years:
            continue
        exists = StudentGraduationRecord.objects.filter(student=student).exists()
        if not exists:
            record_graduation(
                student_id=student.pk,
                graduated_college_id=college.pk,
                graduation_date=date(int(final_label.rsplit("-", 1)[1]), 6, 30),
                verification_source=GRADUATION_VERIFICATION_SOURCE,
                context=context,
            )
        session.record("Student graduations", created=not exists)


__all__ = ["ACADEMIC_TERM", "GRADUATION_VERIFICATION_SOURCE", "seed_academic_history"]
