"""Lifecycle and organizational boundaries shared by Referral and Call Slip pickers."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from compass.accounts.models import Designation, Role, StudentLifecycleStatus, User, UserDesignation
from compass.call_slips.services import list_eligible_students as list_call_slip_students
from compass.exit_interviews.opportunities import list_eligible_students as list_exit_students
from compass.operational_students import list_scoped_operational_students
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.referrals.services import list_eligible_students as list_referral_students


def list_handled_students(*, actor, **kwargs):
    return list_scoped_operational_students(
        college_ids=resolve_operational_responsibility_scope(actor).college_ids, **kwargs
    )


def _user(email: str, role: str = "STUDENT") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="Student",
    )


def _lifecycle(user: User, status: StudentLifecycleStatus) -> User:
    user.student_lifecycle_status = status
    user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    "list_students",
    [list_referral_students, list_call_slip_students],
)
def test_institution_wide_picker_requires_active_current_lifecycle(list_students):
    call_command("sync_identity_policy", verbosity=0)
    head = _user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    current_a = _user("amy@example.edu")
    current_b = _user("zoe@example.edu")
    graduated = _lifecycle(_user("graduate@example.edu"), StudentLifecycleStatus.GRADUATED)
    former = _lifecycle(_user("former@example.edu"), StudentLifecycleStatus.FORMER)
    disabled = _user("disabled@example.edu")
    disabled.is_active = False
    disabled.save(update_fields=["is_active", "updated_at"])

    # None of these Students has an affiliation; institution-wide eligibility must use lifecycle.
    page = list_students(actor=head, page_size=50)
    assert {item.id for item in page.items} == {current_a.pk, current_b.pk}
    assert all(item.college is None for item in page.items)
    assert graduated.is_active and former.is_active

    first = list_students(actor=head, page_size=1)
    second = list_students(actor=head, page=2, page_size=1)
    assert [item.id for item in first.items] == [current_a.pk]
    assert [item.id for item in second.items] == [current_b.pk]
    assert first.has_next and not second.has_next
    assert [item.id for item in list_students(actor=head, search="amy").items] == [current_a.pk]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "list_students",
    [list_handled_students, list_referral_students, list_call_slip_students],
)
def test_college_picker_preserves_scope_and_projection_after_lifecycle_filter(list_students):
    call_command("sync_identity_policy", verbosity=0)
    campus = Campus.objects.create(code="MAIN", name="Main Campus")
    college = College.objects.create(campus=campus, code="IN", name="College In")
    other = College.objects.create(campus=campus, code="OUT", name="College Out")
    counselor = _user("counselor@example.edu", "COUNSELOR")
    CounselorResponsibility.objects.create(college=college, counselor=counselor)

    current = _user("current@example.edu")
    outside = _user("outside@example.edu")
    graduated = _lifecycle(_user("graduate@example.edu"), StudentLifecycleStatus.GRADUATED)
    former = _lifecycle(_user("former@example.edu"), StudentLifecycleStatus.FORMER)
    StudentAffiliation.objects.create(student=current, college=college)
    StudentAffiliation.objects.create(student=outside, college=other)
    StudentAffiliation.objects.create(student=graduated, college=college)
    StudentAffiliation.objects.create(student=former, college=college)

    page = list_students(actor=counselor, page_size=50)
    assert [item.id for item in page.items] == [current.pk]
    assert page.items[0].college is not None
    assert page.items[0].college.id == college.pk
    assert page.items[0].college.code == "IN"
    assert not page.has_next
    assert [item.id for item in list_students(actor=counselor, search="current").items] == [
        current.pk
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "list_students", [list_referral_students, list_call_slip_students, list_exit_students]
)
def test_gss_head_picker_uses_only_explicit_and_valid_fallback_colleges(list_students):
    call_command("sync_identity_policy", verbosity=0)
    head = _user("picker-head@example.edu", "COUNSELOR")
    other = _user("picker-other@example.edu", "COUNSELOR")
    gss = _user("picker-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    StaffSupervision.objects.create(staff=gss, supervisor=head)
    campus = Campus.objects.create(code="PICK", name="Picker")
    colleges = [
        College.objects.create(campus=campus, code=code, name=code) for code in ("EX", "FB", "OUT")
    ]
    CounselorResponsibility.objects.create(college=colleges[0], counselor=head)
    CounselorResponsibility.objects.create(college=colleges[2], counselor=other)
    students = [_user(f"picker-{i}@example.edu") for i in range(3)]
    for student, college in zip(students, colleges, strict=True):
        StudentAffiliation.objects.create(student=student, college=college)

    def listed(actor):
        return {
            item.id for item in list_students(actor=actor, search=None, page=1, page_size=50).items
        }

    assert listed(head) == {student.pk for student in students}
    assert listed(gss) == {students[0].pk, students[1].pk}
    UserDesignation.objects.create(
        user=other, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    assert listed(gss) == {students[0].pk}
    head.is_active = False
    head.save(update_fields=["is_active"])
    assert listed(gss) == set()
