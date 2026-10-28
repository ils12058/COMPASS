"""Current-use active ancestry, separate from inactive-inclusive reference reads."""


def program_has_active_ancestry(program) -> bool:
    return program.is_active and program.college.is_active and program.college.campus.is_active


def active_programs():
    from compass.organization.models import Program

    return Program.objects.filter(
        is_active=True, college__is_active=True, college__campus__is_active=True
    ).select_related("college__campus")
