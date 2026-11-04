from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from django.core.management import call_command

from compass.accounts.models import Role, User
from compass.organization.models import Campus, College
from compass.student_academics.models import StudentAcademicProfile
from compass.student_academics.reads import (
    get_current_placement,
    student_is_placed_in_colleges,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str = "STUDENT") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name="User",
    )


def make_college(
    code: str = "CCMS",
    *,
    campus_code: str = "MAIN",
    active: bool = True,
    campus_active: bool = True,
) -> College:
    campus = Campus.objects.create(
        code=campus_code,
        name=f"{campus_code} Campus",
        is_active=campus_active,
    )
    return College.objects.create(
        campus=campus,
        code=code,
        name=f"{code} College",
        is_active=active,
    )


@pytest.mark.django_db
def test_no_profile_returns_none():
    sync_policy()
    student = make_user("reads.no-profile@example.edu")

    assert get_current_placement(student_id=student.pk) is None
    assert get_current_placement(student_id=student.pk, require_active_college=True) is None


@pytest.mark.django_db
def test_cleared_profile_returns_none():
    sync_policy()
    student = make_user("reads.cleared@example.edu")
    StudentAcademicProfile.objects.create(student=student)

    assert get_current_placement(student_id=student.pk) is None
    assert get_current_placement(student_id=student.pk, require_active_college=True) is None


@pytest.mark.django_db
def test_active_placement_exposes_college_facts_and_stable_revision():
    sync_policy()
    student = make_user("reads.active@example.edu")
    college = make_college("CCMS", campus_code="MAIN")
    profile = StudentAcademicProfile.objects.create(student=student, current_college=college)

    placement = get_current_placement(student_id=student.pk)

    assert placement is not None
    assert placement.student_id == student.pk
    assert placement.profile_id == profile.pk
    assert placement.college.id == college.pk
    assert placement.college.code == "CCMS"
    assert placement.college.name == "CCMS College"
    assert placement.college.is_active is True
    assert placement.college.campus_id == college.campus_id
    assert placement.college.campus_code == "MAIN"
    assert placement.college.campus_name == "MAIN Campus"
    assert placement.college.campus_is_active is True
    assert placement.college.is_usable is True
    assert isinstance(placement.updated_at, datetime)
    assert placement.revision == f"student_academics:{profile.pk}:{profile.updated_at.isoformat()}"


@pytest.mark.django_db
def test_inactive_college_or_campus_keeps_facts_but_is_not_usable():
    sync_policy()
    inactive_college_student = make_user("reads.inactive-college@example.edu")
    inactive_college = make_college("CCMS", campus_code="MAIN", active=False)
    StudentAcademicProfile.objects.create(
        student=inactive_college_student, current_college=inactive_college
    )

    placement = get_current_placement(student_id=inactive_college_student.pk)

    assert placement is not None
    assert placement.college.is_active is False
    assert placement.college.campus_is_active is True
    assert placement.college.is_usable is False
    assert (
        get_current_placement(student_id=inactive_college_student.pk, require_active_college=True)
        is None
    )

    inactive_campus_student = make_user("reads.inactive-campus@example.edu")
    inactive_campus_college = make_college("CEA", campus_code="NORTH", campus_active=False)
    StudentAcademicProfile.objects.create(
        student=inactive_campus_student, current_college=inactive_campus_college
    )

    placement = get_current_placement(student_id=inactive_campus_student.pk)

    assert placement is not None
    assert placement.college.is_active is True
    assert placement.college.campus_is_active is False
    assert placement.college.is_usable is False
    assert (
        get_current_placement(student_id=inactive_campus_student.pk, require_active_college=True)
        is None
    )


@pytest.mark.django_db
def test_scope_helper_requires_membership_and_active_ancestry():
    sync_policy()
    student = make_user("reads.scope@example.edu")
    college = make_college("CCMS", campus_code="MAIN")
    other_college = make_college("CEA", campus_code="NORTH")
    profile = StudentAcademicProfile.objects.create(student=student, current_college=college)

    assert student_is_placed_in_colleges(student_id=student.pk, college_ids=()) is False
    assert student_is_placed_in_colleges(student_id=student.pk, college_ids=(college.pk,)) is True
    assert (
        student_is_placed_in_colleges(student_id=student.pk, college_ids=(other_college.pk,))
        is False
    )
    assert (
        student_is_placed_in_colleges(student_id=student.pk, college_ids=(uuid4(), college.pk))
        is True
    )

    College.objects.filter(pk=college.pk).update(is_active=False)
    assert student_is_placed_in_colleges(student_id=student.pk, college_ids=(college.pk,)) is False
    assert (
        student_is_placed_in_colleges(
            student_id=student.pk, college_ids=(college.pk,), require_active_college=False
        )
        is True
    )

    College.objects.filter(pk=college.pk).update(is_active=True)
    Campus.objects.filter(pk=profile.current_college.campus_id).update(is_active=False)
    assert student_is_placed_in_colleges(student_id=student.pk, college_ids=(college.pk,)) is False
    assert (
        student_is_placed_in_colleges(
            student_id=student.pk, college_ids=(college.pk,), require_active_college=False
        )
        is True
    )
