from __future__ import annotations

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.organization.models import Campus, College, Program, StudentAffiliation
from compass.organization.services import (
    remove_student_affiliation,
    set_student_affiliation,
)
from compass.student_academics.models import (
    PlacementVerificationStatus,
    StudentAcademicProfile,
)
from compass.student_academics.services import reconcile_student_academic_profiles


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name="User",
        is_active=active,
    )


def make_college(code: str, campus_code: str) -> College:
    campus = Campus.objects.create(code=campus_code, name=f"{campus_code} Campus")
    return College.objects.create(campus=campus, code=code, name=f"{code} College")


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


@pytest.mark.django_db
def test_profile_model_defaults_and_constraints():
    sync_policy()
    student = make_user("model@example.edu", "STUDENT")

    profile = StudentAcademicProfile.objects.create(student=student)

    assert isinstance(profile.id, uuid.UUID)
    assert profile.current_college is None
    assert profile.current_program is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by is None
    assert profile.created_at is not None
    assert profile.updated_at is not None
    assert StudentAcademicProfile._meta.default_permissions == ()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentAcademicProfile.objects.create(
                student=student, placement_verification_status="BOGUS"
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentAcademicProfile.objects.create(student=student)


@pytest.mark.django_db
def test_gate_off_affiliation_writes_leave_profile_untouched():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    college_a = make_college("A", "MAIN")
    college_b = make_college("B", "OTHER")

    set_student_affiliation(student_id=student.pk, college_id=college_a.pk, context=context(actor))
    assert not StudentAcademicProfile.objects.exists()

    set_student_affiliation(student_id=student.pk, college_id=college_b.pk, context=context(actor))
    assert not StudentAcademicProfile.objects.exists()

    remove_student_affiliation(student_id=student.pk, context=context(actor))
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
@override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=True)
def test_gate_on_set_creates_shadow_profile_with_actor():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    college = make_college("A", "MAIN")

    set_student_affiliation(student_id=student.pk, college_id=college.pk, context=context(actor))

    profile = StudentAcademicProfile.objects.get(student=student)
    assert profile.current_college == college
    assert profile.current_program is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by == actor


@pytest.mark.django_db
@override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=True)
def test_gate_on_transfer_updates_college_and_resets_verification():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    college_a = make_college("A", "MAIN")
    college_b = make_college("B", "OTHER")
    program = Program.objects.create(college=college_a, code="PROG", name="Program")
    set_student_affiliation(student_id=student.pk, college_id=college_a.pk, context=context(actor))
    StudentAcademicProfile.objects.filter(student=student).update(
        current_program=program,
        placement_verification_status=PlacementVerificationStatus.VERIFIED,
        placement_effective_at=timezone.now(),
    )

    set_student_affiliation(student_id=student.pk, college_id=college_b.pk, context=context(actor))

    profile = StudentAcademicProfile.objects.get(student=student)
    assert profile.current_college == college_b
    assert profile.current_program is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by == actor


@pytest.mark.django_db
def test_gate_on_same_college_noop_creates_missing_profile_without_new_audit():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    college = make_college("A", "MAIN")
    with override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=False):
        set_student_affiliation(
            student_id=student.pk, college_id=college.pk, context=context(actor)
        )
    audit_count = AuditEvent.objects.filter(
        action__startswith="organization.student_affiliation"
    ).count()

    with override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=True):
        set_student_affiliation(
            student_id=student.pk, college_id=college.pk, context=context(actor)
        )
        assert StudentAcademicProfile.objects.filter(student=student).exists()
        StudentAcademicProfile.objects.filter(student=student).update(
            placement_verification_status=PlacementVerificationStatus.VERIFIED
        )
        set_student_affiliation(
            student_id=student.pk, college_id=college.pk, context=context(actor)
        )

    profile = StudentAcademicProfile.objects.get(student=student)
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert (
        AuditEvent.objects.filter(action__startswith="organization.student_affiliation").count()
        == audit_count
    )


@pytest.mark.django_db
@override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=True)
def test_gate_on_removal_keeps_profile_and_clears_college():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    college = make_college("A", "MAIN")
    set_student_affiliation(student_id=student.pk, college_id=college.pk, context=context(actor))

    remove_student_affiliation(student_id=student.pk, context=context(actor))

    profile = StudentAcademicProfile.objects.get(student=student)
    assert profile.current_college is None
    assert profile.current_program is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by == actor
    assert not StudentAffiliation.objects.filter(student=student).exists()


@pytest.mark.django_db
@override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=True)
def test_profile_write_failure_rolls_back_affiliation(monkeypatch):
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    college = make_college("A", "MAIN")

    def fail(*args, **kwargs):
        raise RuntimeError("profile write failed")

    monkeypatch.setattr(StudentAcademicProfile.objects, "update_or_create", fail)

    with pytest.raises(RuntimeError, match="profile write failed"):
        set_student_affiliation(
            student_id=student.pk, college_id=college.pk, context=context(actor)
        )

    assert not StudentAffiliation.objects.filter(student=student).exists()
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_backfill_is_dry_run_capable_batched_idempotent_and_excludes_non_students():
    sync_policy()
    active = make_user("active@example.edu", "STUDENT")
    inactive = make_user("inactive@example.edu", "STUDENT", active=False)
    non_student = make_user("counselor@example.edu", "COUNSELOR")
    inactive_college_student = make_user("inactive-college@example.edu", "STUDENT")
    college = make_college("BF", "BF-MAIN")
    other_college = make_college("BFE", "BF-OTHER")
    inactive_college = make_college("BFI", "BF-INACTIVE")
    inactive_college.is_active = False
    inactive_college.save(update_fields=["is_active", "updated_at"])

    for student in (active, inactive, non_student):
        StudentAffiliation.objects.create(student=student, college=college)
    StudentAffiliation.objects.create(student=inactive_college_student, college=inactive_college)
    StudentAcademicProfile.objects.create(
        student=active,
        current_college=other_college,
        placement_verification_status=PlacementVerificationStatus.VERIFIED,
    )

    out = StringIO()
    err = StringIO()
    call_command(
        "backfill_student_academic_profiles",
        dry_run=True,
        batch_size=1,
        stdout=out,
        stderr=err,
    )

    dry_output = out.getvalue()
    assert "affiliations_total=4" in dry_output
    assert "eligible=3" in dry_output
    assert "missing_profiles=2" in dry_output
    assert "existing_profiles=1" in dry_output
    assert "inactive_student_accounts=1" in dry_output
    assert "non_student_role_rows=1" in dry_output
    assert "inactive_college_rows=1" in dry_output
    assert "created=0" in dry_output
    assert "non-Student-role affiliations were excluded" in err.getvalue()
    assert StudentAcademicProfile.objects.count() == 1

    out = StringIO()
    call_command(
        "backfill_student_academic_profiles",
        dry_run=False,
        batch_size=1,
        stdout=out,
        stderr=StringIO(),
    )
    assert "created=2" in out.getvalue()
    assert StudentAcademicProfile.objects.count() == 3
    assert not StudentAcademicProfile.objects.filter(student=non_student).exists()
    preserved = StudentAcademicProfile.objects.get(student=active)
    assert preserved.current_college == other_college
    assert preserved.placement_verification_status == PlacementVerificationStatus.VERIFIED
    copied = StudentAcademicProfile.objects.get(student=inactive)
    assert copied.current_college == college
    assert copied.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert copied.placement_effective_at is None
    assert StudentAcademicProfile.objects.filter(
        student=inactive_college_student, current_college=inactive_college
    ).exists()

    out = StringIO()
    call_command(
        "backfill_student_academic_profiles",
        dry_run=False,
        batch_size=2,
        stdout=out,
        stderr=StringIO(),
    )
    assert "created=0" in out.getvalue()
    assert StudentAcademicProfile.objects.count() == 3

    with pytest.raises(CommandError, match="--batch-size"):
        call_command("backfill_student_academic_profiles", dry_run=True, batch_size=0)


@pytest.mark.django_db
def test_reconciliation_detects_every_blocking_mismatch():
    sync_policy()
    college_a = make_college("RA", "RA-MAIN")
    college_b = make_college("RB", "RB-MAIN")
    program = Program.objects.create(college=college_a, code="RP", name="Program")

    missing = make_user("missing@example.edu", "STUDENT")
    drift = make_user("drift@example.edu", "STUDENT")
    program_present = make_user("program@example.edu", "STUDENT")
    effective = make_user("effective@example.edu", "STUDENT")
    verified = make_user("verified@example.edu", "STUDENT")
    orphan = make_user("orphan@example.edu", "STUDENT")
    for student in (missing, drift, program_present, effective, verified):
        StudentAffiliation.objects.create(student=student, college=college_a)
    StudentAcademicProfile.objects.create(student=drift, current_college=college_b)
    StudentAcademicProfile.objects.create(
        student=program_present, current_college=college_a, current_program=program
    )
    StudentAcademicProfile.objects.create(
        student=effective,
        current_college=college_a,
        placement_effective_at=timezone.now(),
    )
    StudentAcademicProfile.objects.create(
        student=verified,
        current_college=college_a,
        placement_verification_status=PlacementVerificationStatus.VERIFIED,
    )
    StudentAcademicProfile.objects.create(student=orphan, current_college=college_a)

    report = reconcile_student_academic_profiles()

    assert report.affiliations_without_profile == 1
    assert report.profile_college_drift == 1
    assert report.profile_program_present == 1
    assert report.profile_effective_at_present == 1
    assert report.profile_verified == 1
    assert report.profiles_without_affiliation == 1
    assert report.blocking_total == 6
    assert report.non_student_profiles == 0
    assert report.inactive_student_profiles == 0

    with pytest.raises(CommandError, match="blocking profile mismatch"):
        call_command(
            "reconcile_student_academic_profiles",
            fail_on_mismatch=True,
            stdout=StringIO(),
            stderr=StringIO(),
        )


@pytest.mark.django_db
def test_reconciliation_reports_non_student_and_inactive_profiles_separately():
    sync_policy()
    college = make_college("NS", "NS-MAIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR", active=False)
    inactive_student = make_user("inactive@example.edu", "STUDENT", active=False)
    for student in (counselor, inactive_student):
        StudentAffiliation.objects.create(student=student, college=college)
        StudentAcademicProfile.objects.create(student=student, current_college=college)

    out = StringIO()
    err = StringIO()
    call_command(
        "reconcile_student_academic_profiles",
        fail_on_mismatch=True,
        stdout=out,
        stderr=err,
    )

    output = out.getvalue()
    assert "blocking_total=0" in output
    assert "non_student_profiles=1" in output
    assert "inactive_student_profiles=1" in output
    assert "non-Student profiles exist" in err.getvalue()
    assert "inactive Student profiles exist" in err.getvalue()


@pytest.mark.django_db
@override_settings(STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=True)
def test_student_without_affiliation_gets_no_profile():
    sync_policy()
    student = make_user("unplaced@example.edu", "STUDENT")

    assert not StudentAcademicProfile.objects.filter(student=student).exists()
