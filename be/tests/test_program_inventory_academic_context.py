from __future__ import annotations

from dataclasses import fields

import pytest
from django.apps import apps
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.accounts.profiles import PersonProfileContext
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.inventory.models import StudentInventory
from compass.inventory.services import (
    InvalidInventoryInput,
    InventoryConflict,
    ensure_current_inventory,
    get_my_inventory_history_item,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import (
    create_academic_year,
    set_current_academic_year,
)
from compass.organization.models import (
    Campus,
    College,
    Program,
    StudentAffiliation,
)
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name="User",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def configure_year(actor: User, label: str = "2026-2027"):
    year = create_academic_year(label=label, context=context(actor))
    return set_current_academic_year(academic_year_id=year.pk, context=context(actor))


def make_program(
    actor: User,
    *,
    campus_code: str = "MAIN",
    college_code: str = "CCMS",
    program_code: str = "BSIS",
    program_name: str = "BS Information Systems",
) -> Program:
    campus = Campus.objects.create(code=campus_code, name=f"{campus_code} Campus")
    college = College.objects.create(
        campus=campus,
        code=college_code,
        name=f"{college_code} College",
    )
    return Program.objects.create(
        college=college,
        code=program_code,
        name=program_name,
    )


@pytest.mark.django_db
def test_inventory_draft_is_lightweight_then_normalizes_program_year_and_course_snapshot():
    sync_policy()
    actor = make_user("inventory-admin@example.edu", "IT_ADMIN")
    student = make_user("inventory-student@example.edu", "STUDENT")
    configure_year(actor)
    program = make_program(actor)

    draft = ensure_current_inventory(student=student, context=context(student))
    assert draft.program_id is None
    assert draft.year_level is None

    updated = replace_current_inventory(
        student=student,
        values={
            "program_id": program.pk,
            "year_level": 3,
            "course_currently_enrolled": "Arbitrary client text",
            "major": "Optional Major",
        },
    )
    assert updated.program_id == program.pk
    assert updated.year_level == 3
    assert updated.major == "Optional Major"
    assert updated.course_currently_enrolled == program.name

    with pytest.raises(InvalidInventoryInput):
        replace_current_inventory(student=student, values={"year_level": 0})
    with pytest.raises(InvalidInventoryInput):
        replace_current_inventory(student=student, values={"year_level": 11})


@pytest.mark.django_db
def test_inventory_submission_requires_structured_program_and_year_level():
    sync_policy()
    actor = make_user("submit-admin@example.edu", "IT_ADMIN")
    student = make_user("submit-student@example.edu", "STUDENT")
    configure_year(actor)
    program = make_program(actor)
    ensure_current_inventory(student=student, context=context(student))

    with pytest.raises(InventoryConflict, match="Program is required"):
        submit_current_inventory(student=student, context=context(student))

    replace_current_inventory(student=student, values={"program_id": program.pk})
    with pytest.raises(InventoryConflict, match="Year Level is required"):
        submit_current_inventory(student=student, context=context(student))

    replace_current_inventory(
        student=student,
        values={
            **minimum_normalized_inventory_values(program_id=program.pk),
            "course_currently_enrolled": "Wrong input",
        },
    )
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None
    assert submitted.program_id == program.pk
    assert submitted.year_level == 1
    assert submitted.course_currently_enrolled == program.name


@pytest.mark.django_db
def test_inactive_program_or_parent_chain_blocks_edit_and_submission():
    sync_policy()
    actor = make_user("inactive-admin@example.edu", "IT_ADMIN")
    student = make_user("inactive-student@example.edu", "STUDENT")
    configure_year(actor)
    program = make_program(actor)
    ensure_current_inventory(student=student, context=context(student))
    replace_current_inventory(
        student=student,
        values={"program_id": program.pk, "year_level": 1},
    )

    Program.objects.filter(pk=program.pk).update(is_active=False)
    with pytest.raises(InventoryConflict, match="must all be active"):
        submit_current_inventory(student=student, context=context(student))
    with pytest.raises(InventoryConflict, match="must all be active"):
        replace_current_inventory(student=student, values={"nickname": "Still draft"})

    Program.objects.filter(pk=program.pk).update(is_active=True)
    College.objects.filter(pk=program.college_id).update(is_active=False)
    with pytest.raises(InventoryConflict, match="must all be active"):
        submit_current_inventory(student=student, context=context(student))

    College.objects.filter(pk=program.college_id).update(is_active=True)
    Campus.objects.filter(pk=program.college.campus_id).update(is_active=False)
    with pytest.raises(InventoryConflict, match="must all be active"):
        submit_current_inventory(student=student, context=context(student))


@pytest.mark.django_db
def test_submitted_inventory_snapshot_survives_program_rename_and_deactivation():
    sync_policy()
    actor = make_user("history-admin@example.edu", "IT_ADMIN")
    student = make_user("history-student@example.edu", "STUDENT")
    configure_year(actor)
    program = make_program(actor, program_name="BS Information Systems")
    ensure_current_inventory(student=student, context=context(student))
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(
            program_id=program.pk,
            year_level=4,
        ),
    )
    submitted = submit_current_inventory(student=student, context=context(student))
    frozen_course = submitted.course_currently_enrolled

    Program.objects.filter(pk=program.pk).update(
        name="Bachelor of Science in Information Systems",
        is_active=False,
    )

    historical = get_my_inventory_history_item(
        student=student,
        inventory_id=submitted.pk,
    )
    assert historical.program_id == program.pk
    assert historical.course_currently_enrolled == frozen_course
    assert historical.course_currently_enrolled == "BS Information Systems"
    with pytest.raises(InventoryConflict, match="locked"):
        replace_current_inventory(student=student, values={"major": "Changed"})


@pytest.mark.django_db
def test_inventory_program_does_not_mutate_guidance_student_affiliation():
    sync_policy()
    actor = make_user("routing-admin@example.edu", "IT_ADMIN")
    student = make_user("routing-student@example.edu", "STUDENT")
    configure_year(actor)

    campus_a = Campus.objects.create(code="A", name="Campus A")
    college_a = College.objects.create(campus=campus_a, code="A", name="College A")
    campus_b = Campus.objects.create(code="B", name="Campus B")
    college_b = College.objects.create(campus=campus_b, code="B", name="College B")
    program_b = Program.objects.create(
        college=college_b,
        code="BSCPE",
        name="BS Computer Engineering",
    )
    StudentAffiliation.objects.create(student=student, college=college_a, assigned_by=actor)
    affiliation_audits_before = AuditEvent.objects.filter(
        action__startswith="organization.student_affiliation"
    ).count()

    ensure_current_inventory(student=student, context=context(student))
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(
            program_id=program_b.pk,
            year_level=2,
        ),
    )
    submitted = submit_current_inventory(student=student, context=context(student))

    affiliation = StudentAffiliation.objects.get(student=student)
    assert affiliation.college_id == college_a.pk
    assert submitted.program.college_id == college_b.pk
    assert (
        AuditEvent.objects.filter(action__startswith="organization.student_affiliation").count()
        == affiliation_audits_before
    )


@pytest.mark.django_db
def test_academic_year_switch_keeps_existing_narrow_semantics():
    sync_policy()
    actor = make_user("year-admin@example.edu", "IT_ADMIN")
    student = make_user("year-student@example.edu", "STUDENT")
    campus = Campus.objects.create(code="MAIN", name="Main")
    college = College.objects.create(campus=campus, code="CCMS", name="CCMS")
    StudentAffiliation.objects.create(student=student, college=college, assigned_by=actor)

    first = configure_year(actor, "2026-2027")
    second = create_academic_year(label="2027-2028", context=context(actor))
    before_inventory_count = StudentInventory.objects.count()
    before_program_count = Program.objects.count()

    set_current_academic_year(academic_year_id=second.pk, context=context(actor))

    affiliation = StudentAffiliation.objects.get(student=student)
    assert affiliation.college_id == college.pk
    assert StudentInventory.objects.count() == before_inventory_count
    assert Program.objects.count() == before_program_count
    first.refresh_from_db()
    second.refresh_from_db()
    assert not first.is_current
    assert second.is_current


@pytest.mark.django_db
def test_legacy_submitted_inventory_without_structured_context_remains_readable():
    sync_policy()
    actor = make_user("legacy-admin@example.edu", "IT_ADMIN")
    student = make_user("legacy-student@example.edu", "STUDENT")
    configure_year(actor)
    item = ensure_current_inventory(student=student, context=context(student))
    StudentInventory.objects.filter(pk=item.pk).update(
        submitted_at=timezone.now(),
        course_currently_enrolled="Legacy Free Text",
        program=None,
        year_level=None,
    )

    historical = get_my_inventory_history_item(student=student, inventory_id=item.pk)
    assert historical.submitted_at is not None
    assert historical.program_id is None
    assert historical.year_level is None
    assert historical.course_currently_enrolled == "Legacy Free Text"


@pytest.mark.django_db
def test_no_sis_like_classification_or_profile_fields_are_introduced():
    profile_fields = {field.name for field in fields(PersonProfileContext)}
    assert {"program", "year_level", "major"}.isdisjoint(profile_fields)
    with pytest.raises(LookupError):
        apps.get_model("organization", "StudentAcademicClassification")
