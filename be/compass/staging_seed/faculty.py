"""Synthetic Faculty identities and their independent background Student targets."""

from .identities import FacultySpec

FACULTY = tuple(
    FacultySpec(
        key=f"faculty_{college.lower()}",
        label=f"Faculty ({college})",
        institutional_id=f"STG-F-{number:04d}",
        email_local_part=f"stg-faculty-{college.lower()}",
        first_name=first,
        middle_name="",
        last_name=last,
        campus_code=campus,
        college_code=college,
        fresh_student=fresh,
        received_student=received,
        summary=f"{college} Faculty: submit a digital Referral and open a received submission.",
        limitations="Own submissions only; use the named background Student for fresh submission.",
    )
    for number, (college, campus, first, last, fresh, received) in enumerate(
        (
            ("CCMS", "MAIN", "Liora", "Soliven", "bg_01", "bg_05"),
            ("CAS", "MAIN", "Nestor", "Valmonte", "bg_02", "bg_06"),
            ("CBPA", "MAIN", "Celina", "Mirasol", "bg_03", "bg_07"),
            ("COED", "ABANO", "Dario", "Almeda", "bg_04", "bg_08"),
            ("COENG", "MAIN", "Mireya", "Sandoval", "bg_48", "bg_49"),
        ),
        1,
    )
)


def check_faculty_conflicts(users):
    from compass.organization.models import FacultyAffiliation

    from .organization import college_for
    from .support import StagingSeedConflict

    for spec in FACULTY:
        user = users.get(spec.key)
        if user is None:
            continue
        current = FacultyAffiliation.objects.filter(faculty=user).first()
        college = college_for(spec.campus_code, spec.college_code)
        if current is not None and current.college_id != college.pk:
            raise StagingSeedConflict(f"{spec.key}: Faculty home College conflicts with dataset.")


def seed_faculty_affiliations(session):
    from compass.account_management.faculty import (
        validate_faculty_college,
        write_faculty_affiliation,
    )
    from compass.accounts.models import User
    from compass.organization.models import FacultyAffiliation

    from .organization import college_for

    for spec in FACULTY:
        target = User.objects.select_for_update().get(pk=session.users[spec.key].pk)
        college = validate_faculty_college(
            role=target.role.code,
            college_id=college_for(spec.campus_code, spec.college_code).pk,
        )
        exists = FacultyAffiliation.objects.filter(faculty=target, college=college).exists()
        write_faculty_affiliation(
            target=target,
            actor=session.user("it_admin"),
            college=college,
            basis="Synthetic Staging Dataset v1 Faculty home College assignment.",
            context=session.system(),
        )
        session.record("Faculty affiliations", created=not exists)
