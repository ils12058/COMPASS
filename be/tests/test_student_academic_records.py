from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, StudentLifecycleStatus, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.models import AcademicYear, Campus, College, Program
from compass.student_academics.models import (
    AcademicTerm,
    EnrollmentStatus,
    PlacementVerificationStatus,
    StudentAcademicPeriodRecord,
    StudentAcademicProfile,
    StudentGraduationRecord,
)
from compass.student_academics.services import (
    InvalidStudentAcademicInput,
    StudentAcademicConflict,
    StudentAcademicNotFound,
    clear_current_placement,
    get_student_academic_record,
    list_current_placements,
    record_academic_period,
    record_graduation,
    set_current_placement,
)

BASE = "/api/v1/student-academics"


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str = "STUDENT", *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name="User",
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def make_college(
    code: str = "CCMS",
    *,
    campus_code: str = "MAIN",
    active: bool = True,
    campus_active: bool = True,
) -> College:
    campus, _ = Campus.objects.get_or_create(
        code=campus_code,
        defaults={"name": f"{campus_code} Campus", "is_active": campus_active},
    )
    return College.objects.create(
        campus=campus,
        code=code,
        name=f"{code} College",
        is_active=active,
    )


def make_academic_year(label: str = "2026-2027", *, current: bool = False) -> AcademicYear:
    return AcademicYear.objects.create(label=label, is_current=current)


def auth_client(user: User, *, recent_mfa: bool = True) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


@pytest.mark.django_db
def test_model_defaults_one_to_one_status_and_permissions():
    sync_policy()
    student = make_user("model.student@example.edu")
    profile = StudentAcademicProfile.objects.create(student=student)

    assert profile.current_college is None
    assert profile.current_program is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by is None
    assert profile.created_at is not None
    assert profile.updated_at is not None
    assert StudentAcademicProfile._meta.default_permissions == ()
    assert StudentAcademicProfile._meta.ordering == ("student_id",)
    assert StudentAcademicProfile._meta.get_field("student").remote_field.one_to_one is True

    with pytest.raises(IntegrityError):
        StudentAcademicProfile.objects.create(student=student)


@pytest.mark.django_db
def test_set_creates_canonical_placement_and_audit():
    sync_policy()
    actor = make_user("set.actor@example.edu", "IT_ADMIN")
    student = make_user("set.student@example.edu")
    college = make_college()

    profile = set_current_placement(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )

    assert profile.student_id == student.pk
    assert profile.current_college_id == college.pk
    assert profile.current_program_id is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by == actor
    event = AuditEvent.objects.get(action="student_academics.placement.set")
    assert event.target_type == "student_academics.studentacademicprofile"
    assert event.target_id == str(student.pk)
    assert event.metadata == {
        "previous_college_id": None,
        "new_college_id": str(college.pk),
    }


@pytest.mark.django_db
def test_overwrite_resets_deferred_academic_fields_and_audits_previous_college():
    sync_policy()
    actor = make_user("overwrite.actor@example.edu", "IT_ADMIN")
    student = make_user("overwrite.student@example.edu")
    old_college = make_college("OLD")
    new_college = make_college("NEW", campus_code="OTHER")
    program = Program.objects.create(college=old_college, code="BSIS", name="BS IS")
    profile = StudentAcademicProfile.objects.create(
        student=student,
        current_college=old_college,
        current_program=program,
        placement_verification_status=PlacementVerificationStatus.VERIFIED,
        placement_effective_at=timezone.now() - timedelta(days=2),
    )
    updated = set_current_placement(
        student_id=student.pk,
        college_id=new_college.pk,
        context=context(actor),
    )

    assert updated.pk == profile.pk
    assert updated.current_college_id == new_college.pk
    assert updated.current_program_id is None
    assert updated.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert updated.placement_effective_at is None
    assert updated.updated_by == actor
    event = AuditEvent.objects.get(action="student_academics.placement.set")
    assert event.metadata == {
        "previous_college_id": str(old_college.pk),
        "new_college_id": str(new_college.pk),
    }


@pytest.mark.django_db
def test_same_college_noop_does_not_touch_updated_at_or_audit():
    sync_policy()
    actor = make_user("noop.actor@example.edu", "IT_ADMIN")
    student = make_user("noop.student@example.edu")
    college = make_college()
    profile = set_current_placement(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )
    profile_id = profile.pk
    updated_at = profile.updated_at
    audits = AuditEvent.objects.filter(action="student_academics.placement.set").count()

    again = set_current_placement(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )

    assert again.pk == profile_id
    assert again.updated_at == updated_at
    assert AuditEvent.objects.filter(action="student_academics.placement.set").count() == audits


@pytest.mark.django_db
def test_clear_keeps_profile_row_and_resets_placement():
    sync_policy()
    actor = make_user("clear.actor@example.edu", "IT_ADMIN")
    student = make_user("clear.student@example.edu")
    college = make_college()
    program = Program.objects.create(college=college, code="BSIS", name="BS IS")
    profile = StudentAcademicProfile.objects.create(
        student=student,
        current_college=college,
        current_program=program,
        placement_verification_status=PlacementVerificationStatus.VERIFIED,
        placement_effective_at=timezone.now(),
    )

    removed = clear_current_placement(student_id=student.pk, context=context(actor))

    assert removed is True
    profile.refresh_from_db()
    assert profile.current_college_id is None
    assert profile.current_program_id is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by == actor
    event = AuditEvent.objects.get(action="student_academics.placement.cleared")
    assert event.target_type == "student_academics.studentacademicprofile"
    assert event.target_id == str(student.pk)
    assert event.metadata == {"previous_college_id": str(college.pk)}


@pytest.mark.django_db
def test_clear_without_profile_returns_false_without_audit():
    sync_policy()
    actor = make_user("missing.actor@example.edu", "IT_ADMIN")
    student = make_user("missing.student@example.edu")

    assert clear_current_placement(student_id=student.pk, context=context(actor)) is False
    assert not AuditEvent.objects.filter(action="student_academics.placement.cleared").exists()


@pytest.mark.django_db
def test_set_rejects_inactive_student_and_non_student():
    sync_policy()
    actor = make_user("invalid.actor@example.edu", "IT_ADMIN")
    inactive = make_user("inactive.student@example.edu", active=False)
    counselor = make_user("not.student@example.edu", "COUNSELOR")
    college = make_college()

    with pytest.raises(InvalidStudentAcademicInput):
        set_current_placement(
            student_id=inactive.pk,
            college_id=college.pk,
            context=context(actor),
        )
    with pytest.raises(InvalidStudentAcademicInput):
        set_current_placement(
            student_id=counselor.pk,
            college_id=college.pk,
            context=context(actor),
        )
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_clear_allows_inactive_student_and_rejects_non_student():
    sync_policy()
    actor = make_user("clear-inactive.actor@example.edu", "IT_ADMIN")
    student = make_user("clear-inactive.student@example.edu")
    college = make_college()
    StudentAcademicProfile.objects.create(student=student, current_college=college)
    User.objects.filter(pk=student.pk).update(is_active=False)

    assert clear_current_placement(student_id=student.pk, context=context(actor)) is True

    counselor = make_user("clear-not-student@example.edu", "COUNSELOR")
    with pytest.raises(InvalidStudentAcademicInput):
        clear_current_placement(student_id=counselor.pk, context=context(actor))


@pytest.mark.django_db
def test_set_rejects_missing_targets_and_inactive_catalog():
    sync_policy()
    actor = make_user("catalog.actor@example.edu", "IT_ADMIN")
    student = make_user("catalog.student@example.edu")
    inactive_college = make_college("OFF", active=False)
    inactive_campus_college = make_college("CAMPUS-OFF", campus_code="OFF", campus_active=False)

    with pytest.raises(StudentAcademicNotFound):
        set_current_placement(
            student_id=uuid4(),
            college_id=make_college("UNKNOWN").pk,
            context=context(actor),
        )
    with pytest.raises(StudentAcademicNotFound):
        set_current_placement(
            student_id=student.pk,
            college_id=uuid4(),
            context=context(actor),
        )
    with pytest.raises(StudentAcademicConflict):
        set_current_placement(
            student_id=student.pk,
            college_id=inactive_college.pk,
            context=context(actor),
        )
    with pytest.raises(StudentAcademicConflict):
        set_current_placement(
            student_id=student.pk,
            college_id=inactive_campus_college.pk,
            context=context(actor),
        )


@pytest.mark.django_db
def test_list_excludes_cleared_and_unplaced_students_with_filters_search_and_pagination():
    sync_policy()
    campus_a = Campus.objects.create(code="A", name="Campus A")
    campus_b = Campus.objects.create(code="B", name="Campus B")
    college_a = College.objects.create(campus=campus_a, code="A", name="College A")
    college_b = College.objects.create(campus=campus_b, code="B", name="College B")
    students = [make_user(f"listing.{index}@example.edu") for index in range(4)]
    for index, student in enumerate(students, start=1):
        student.institutional_id = f"LIST-{index:03d}"
        student.first_name = ("Alpha", "Beta", "Gamma", "Delta")[index - 1]
        student.middle_name = "Middle"
        student.last_name = "Sorted"
        student.save(
            update_fields=[
                "institutional_id",
                "first_name",
                "middle_name",
                "last_name",
                "updated_at",
            ]
        )
    StudentAcademicProfile.objects.create(student=students[0], current_college=college_a)
    StudentAcademicProfile.objects.create(student=students[1], current_college=college_a)
    StudentAcademicProfile.objects.create(student=students[2], current_college=college_b)
    StudentAcademicProfile.objects.create(student=students[3])

    first = list_current_placements(page_size=2)
    assert first.page == 1
    assert first.page_size == 2
    assert first.has_next is True
    assert len(first.items) == 2
    assert {item.student_id for item in first.items} == {students[0].pk, students[1].pk}

    second = list_current_placements(page=2, page_size=2)
    assert second.has_next is False
    assert [item.student_id for item in second.items] == [students[2].pk]

    assert [item.student_id for item in list_current_placements(search="LIST-002").items] == [
        students[1].pk
    ]
    assert [item.student_id for item in list_current_placements(search="Gamma").items] == [
        students[2].pk
    ]
    assert [item.student_id for item in list_current_placements(search="Middle").items] == [
        students[0].pk,
        students[1].pk,
        students[2].pk,
    ]
    assert [item.student_id for item in list_current_placements(search="Sorted").items] == [
        students[0].pk,
        students[1].pk,
        students[2].pk,
    ]
    assert {item.student_id for item in list_current_placements(college_id=college_a.pk).items} == {
        students[0].pk,
        students[1].pk,
    }
    assert {item.student_id for item in list_current_placements(campus_id=campus_b.pk).items} == {
        students[2].pk
    }
    assert [
        item.student_id for item in list_current_placements(student_id=students[2].pk).items
    ] == [students[2].pk]

    with pytest.raises(InvalidStudentAcademicInput):
        list_current_placements(page=0)
    with pytest.raises(InvalidStudentAcademicInput):
        list_current_placements(page_size=0)


@pytest.mark.django_db
def test_list_requires_organization_manage_and_returns_unverified_projection():
    sync_policy()
    admin = make_user("list.admin@example.edu", "IT_ADMIN")
    student = make_user("list.student@example.edu")
    counselor = make_user("list.counselor@example.edu", "COUNSELOR")
    college = make_college()
    StudentAcademicProfile.objects.create(student=student, current_college=college)

    counselor_denied = auth_client(counselor).get(f"{BASE}/placements")
    assert counselor_denied.status_code == 403

    student_denied = auth_client(make_user("list.other@example.edu")).get(f"{BASE}/placements")
    assert student_denied.status_code == 403

    response = auth_client(admin).get(f"{BASE}/placements")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert payload["has_next"] is False
    assert payload["items"] == [
        {
            "student": {
                "id": str(student.pk),
                "institutional_id": None,
                "full_name": "Test User",
                "email": student.email,
                "role": "STUDENT",
                "is_active": True,
                "responsibility_scope": None,
            },
            "college": {
                "id": str(college.pk),
                "code": "CCMS",
                "name": "CCMS College",
                "campus": {
                    "id": str(college.campus_id),
                    "code": "MAIN",
                    "name": "MAIN Campus",
                    "is_active": True,
                    "resource_version": 1,
                },
                "is_active": True,
                "resource_version": 1,
            },
            "verification_status": "UNVERIFIED",
        }
    ]


@pytest.mark.django_db
def test_writes_require_recent_mfa_and_manage():
    sync_policy()
    admin = make_user("mfa.admin@example.edu", "IT_ADMIN")
    student = make_user("mfa.student@example.edu")
    college = make_college()

    stale = auth_client(admin, recent_mfa=False)
    denied = stale.put(
        f"{BASE}/students/{student.pk}/placement",
        data={"college_id": str(college.pk)},
        content_type="application/json",
        **csrf(stale),
    )
    assert denied.status_code == 403
    assert not StudentAcademicProfile.objects.exists()

    student_client = auth_client(student)
    forbidden = student_client.put(
        f"{BASE}/students/{student.pk}/placement",
        data={"college_id": str(college.pk)},
        content_type="application/json",
        **csrf(student_client),
    )
    assert forbidden.status_code == 403

    fresh = auth_client(admin)
    created = fresh.put(
        f"{BASE}/students/{student.pk}/placement",
        data={"college_id": str(college.pk)},
        content_type="application/json",
        **csrf(fresh),
    )
    assert created.status_code == 200
    assert created.json()["verification_status"] == "UNVERIFIED"

    stale_delete = auth_client(admin, recent_mfa=False)
    assert (
        stale_delete.delete(
            f"{BASE}/students/{student.pk}/placement", **csrf(stale_delete)
        ).status_code
        == 403
    )

    removed = fresh.delete(f"{BASE}/students/{student.pk}/placement", **csrf(fresh))
    assert removed.status_code == 200
    assert removed.json() == {"removed": True}
    assert StudentAcademicProfile.objects.filter(student=student).exists()


@pytest.mark.django_db
def test_http_errors_map_not_found_conflict_and_invalid_input():
    sync_policy()
    admin = make_user("errors.admin@example.edu", "IT_ADMIN")
    student = make_user("errors.student@example.edu")
    inactive = make_college("ERR-OFF", active=False)
    client = auth_client(admin)
    headers = csrf(client)

    missing = client.put(
        f"{BASE}/students/{uuid4()}/placement",
        data={"college_id": str(make_college("ERR-X").pk)},
        content_type="application/json",
        **headers,
    )
    assert missing.status_code == 404

    conflict = client.put(
        f"{BASE}/students/{student.pk}/placement",
        data={"college_id": str(inactive.pk)},
        content_type="application/json",
        **headers,
    )
    assert conflict.status_code == 409

    invalid = client.put(
        f"{BASE}/students/{student.pk}/placement",
        data={"college_id": "not-a-uuid"},
        content_type="application/json",
        **headers,
    )
    assert invalid.status_code == 422


@pytest.mark.django_db
def test_audit_failure_rolls_back_set_update_and_clear(monkeypatch):
    sync_policy()
    actor = make_user("rollback.actor@example.edu", "IT_ADMIN")
    student = make_user("rollback.student@example.edu")
    college = make_college()
    other = make_college("OTHER", campus_code="SECOND")

    def failed_audit(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr("compass.student_academics.services.record_event", failed_audit)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        set_current_placement(
            student_id=student.pk,
            college_id=college.pk,
            context=context(actor),
        )
    assert not StudentAcademicProfile.objects.exists()

    profile = StudentAcademicProfile.objects.create(student=student, current_college=college)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        set_current_placement(
            student_id=student.pk,
            college_id=other.pk,
            context=context(actor),
        )
    profile.refresh_from_db()
    assert profile.current_college_id == college.pk

    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        clear_current_placement(student_id=student.pk, context=context(actor))
    profile.refresh_from_db()
    assert profile.current_college_id == college.pk


@pytest.mark.django_db
def test_profile_save_failure_rolls_back_without_audit(monkeypatch):
    sync_policy()
    actor = make_user("save.actor@example.edu", "IT_ADMIN")
    student = make_user("save.student@example.edu")
    college = make_college()

    def failed_save(self, *args, **kwargs):
        raise RuntimeError("Synthetic profile failure")

    monkeypatch.setattr(StudentAcademicProfile, "save", failed_save)
    with pytest.raises(RuntimeError, match="Synthetic profile failure"):
        set_current_placement(
            student_id=student.pk,
            college_id=college.pk,
            context=context(actor),
        )
    assert not StudentAcademicProfile.objects.exists()
    assert not AuditEvent.objects.filter(action="student_academics.placement.set").exists()


@pytest.mark.django_db
def test_retired_affiliation_routes_are_gone():
    sync_policy()
    admin = make_user("routes.admin@example.edu", "IT_ADMIN")
    client = auth_client(admin)

    student = make_user("routes.student@example.edu")
    assert client.get("/api/v1/organization/student-affiliations").status_code == 404
    assert (
        client.put(
            f"/api/v1/organization/students/{student.pk}/affiliation",
            data={"college_id": str(make_college().pk)},
            content_type="application/json",
            **csrf(client),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/organization/students/{student.pk}/affiliation",
            **csrf(client),
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_period_and_graduation_models_defaults_constraints_and_permissions():
    sync_policy()
    student = make_user("period.model@example.edu")
    college = make_college()
    year = make_academic_year()

    period = StudentAcademicPeriodRecord.objects.create(
        student=student,
        academic_year=year,
        term=AcademicTerm.FIRST_SEMESTER,
        college=college,
    )
    assert period.enrollment_status == EnrollmentStatus.UNKNOWN
    assert period.year_level is None
    assert period.program_id is None
    assert period.created_by is None
    assert period.updated_by is None
    assert period.created_at is not None
    assert period.updated_at is not None
    assert StudentAcademicPeriodRecord._meta.default_permissions == ()
    assert StudentAcademicPeriodRecord._meta.ordering == (
        "student_id",
        "-academic_year__label",
        "term",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentAcademicPeriodRecord.objects.create(
                student=student,
                academic_year=year,
                term=AcademicTerm.FIRST_SEMESTER,
                college=college,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentAcademicPeriodRecord.objects.create(
                student=student,
                academic_year=year,
                term="SUMMER",
                college=college,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentAcademicPeriodRecord.objects.create(
                student=student,
                academic_year=year,
                term=AcademicTerm.SECOND_SEMESTER,
                college=college,
                enrollment_status="WITHDRAWN",
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentAcademicPeriodRecord.objects.create(
                student=student,
                academic_year=year,
                term=AcademicTerm.SECOND_SEMESTER,
                college=college,
                year_level=0,
            )

    graduation = StudentGraduationRecord.objects.create(
        student=student,
        graduated_college=college,
        graduation_date=date(2026, 6, 30),
        verification_source="Registrar confirmation",
        verified_at=timezone.now(),
    )
    assert graduation.graduated_program_id is None
    assert graduation.verified_by is None
    assert StudentGraduationRecord._meta.default_permissions == ()
    assert StudentGraduationRecord._meta.ordering == ("student_id",)
    assert StudentGraduationRecord._meta.get_field("student").remote_field.one_to_one is True
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentGraduationRecord.objects.create(
                student=student,
                graduated_college=college,
                graduation_date=date(2026, 6, 30),
                verification_source="Second confirmation",
                verified_at=timezone.now(),
            )


@pytest.mark.django_db
def test_record_period_creates_updates_and_audits_flat_metadata():
    sync_policy()
    actor = make_user("period.actor@example.edu", "IT_ADMIN")
    student = make_user("period.student@example.edu")
    college = make_college()
    other_college = make_college("OTHER", campus_code="OTHER")
    other_actor = make_user("period.other.actor@example.edu", "IT_ADMIN")
    year = make_academic_year()

    record = record_academic_period(
        student_id=student.pk,
        academic_year_id=year.pk,
        term=AcademicTerm.FIRST_SEMESTER,
        college_id=college.pk,
        year_level=2,
        enrollment_status=EnrollmentStatus.ENROLLED,
        context=context(actor),
    )

    assert record.student_id == student.pk
    assert record.academic_year_id == year.pk
    assert record.college_id == college.pk
    assert record.term == AcademicTerm.FIRST_SEMESTER
    assert record.year_level == 2
    assert record.enrollment_status == EnrollmentStatus.ENROLLED
    assert record.program_id is None
    assert record.created_by == actor
    assert record.updated_by == actor
    event = AuditEvent.objects.get(action="student_academics.period.recorded")
    assert event.target_type == "student_academics.studentacademicperiodrecord"
    assert event.target_id == str(record.pk)
    assert event.metadata == {
        "created": True,
        "student_id": str(student.pk),
        "academic_year_id": str(year.pk),
        "term": "FIRST_SEMESTER",
        "previous_college_id": None,
        "new_college_id": str(college.pk),
        "previous_year_level": None,
        "new_year_level": 2,
        "previous_enrollment_status": None,
        "new_enrollment_status": "ENROLLED",
    }

    updated = record_academic_period(
        student_id=student.pk,
        academic_year_id=year.pk,
        term=AcademicTerm.FIRST_SEMESTER,
        college_id=other_college.pk,
        year_level=3,
        enrollment_status=EnrollmentStatus.NOT_ENROLLED,
        context=context(other_actor),
    )

    assert updated.pk == record.pk
    assert updated.college_id == other_college.pk
    assert updated.year_level == 3
    assert updated.enrollment_status == EnrollmentStatus.NOT_ENROLLED
    assert updated.program_id is None
    assert updated.created_by == actor
    assert updated.updated_by == other_actor
    update_event = AuditEvent.objects.filter(
        action="student_academics.period.recorded", target_id=str(record.pk)
    ).latest("occurred_at")
    assert update_event.metadata == {
        "created": False,
        "student_id": str(student.pk),
        "academic_year_id": str(year.pk),
        "term": "FIRST_SEMESTER",
        "previous_college_id": str(college.pk),
        "new_college_id": str(other_college.pk),
        "previous_year_level": 2,
        "new_year_level": 3,
        "previous_enrollment_status": "ENROLLED",
        "new_enrollment_status": "NOT_ENROLLED",
    }

    updated_at = updated.updated_at
    audits = AuditEvent.objects.filter(action="student_academics.period.recorded").count()
    again = record_academic_period(
        student_id=student.pk,
        academic_year_id=year.pk,
        term=AcademicTerm.FIRST_SEMESTER,
        college_id=other_college.pk,
        year_level=3,
        enrollment_status=EnrollmentStatus.NOT_ENROLLED,
        context=context(other_actor),
    )
    assert again.pk == updated.pk
    assert again.updated_at == updated_at
    assert AuditEvent.objects.filter(action="student_academics.period.recorded").count() == audits


@pytest.mark.django_db
def test_record_period_validation_and_history_correction_for_inactive_students():
    sync_policy()
    actor = make_user("period.validation.actor@example.edu", "IT_ADMIN")
    student = make_user("period.validation.student@example.edu")
    inactive = make_user("period.inactive.student@example.edu", active=False)
    counselor = make_user("period.counselor@example.edu", "COUNSELOR")
    college = make_college()
    inactive_college = make_college("PERIOD-OFF", active=False)
    inactive_campus_college = make_college(
        "PERIOD-CAMPUS-OFF", campus_code="PERIOD-OFF", campus_active=False
    )
    year = make_academic_year()

    def attempt(**overrides):
        payload = {
            "student_id": student.pk,
            "academic_year_id": year.pk,
            "term": AcademicTerm.FIRST_SEMESTER,
            "college_id": college.pk,
            "year_level": 1,
            "enrollment_status": EnrollmentStatus.ENROLLED,
            "context": context(actor),
        }
        payload.update(overrides)
        return record_academic_period(**payload)

    with pytest.raises(InvalidStudentAcademicInput):
        attempt(student_id=counselor.pk)
    with pytest.raises(StudentAcademicNotFound):
        attempt(student_id=uuid4())
    with pytest.raises(StudentAcademicNotFound):
        attempt(academic_year_id=uuid4())
    with pytest.raises(StudentAcademicNotFound):
        attempt(college_id=uuid4())
    with pytest.raises(StudentAcademicConflict):
        attempt(college_id=inactive_college.pk)
    with pytest.raises(StudentAcademicConflict):
        attempt(college_id=inactive_campus_college.pk)
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(term="SUMMER")
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(enrollment_status="WITHDRAWN")
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(year_level=0)
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(year_level=9)
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(year_level=True)

    record = attempt(student_id=inactive.pk)
    assert record.student_id == inactive.pk

    student.student_lifecycle_status = StudentLifecycleStatus.FORMER
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    former_record = attempt(term=AcademicTerm.SECOND_SEMESTER)
    assert former_record.term == AcademicTerm.SECOND_SEMESTER
    student.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.FORMER


@pytest.mark.django_db
def test_record_period_does_not_change_placement_or_lifecycle():
    sync_policy()
    actor = make_user("period.placement.actor@example.edu", "IT_ADMIN")
    student = make_user("period.placement.student@example.edu")
    college = make_college()
    year = make_academic_year()
    profile = set_current_placement(
        student_id=student.pk, college_id=college.pk, context=context(actor)
    )
    updated_at = profile.updated_at

    record_academic_period(
        student_id=student.pk,
        academic_year_id=year.pk,
        term=AcademicTerm.FIRST_SEMESTER,
        college_id=college.pk,
        year_level=4,
        enrollment_status=EnrollmentStatus.ENROLLED,
        context=context(actor),
    )

    profile.refresh_from_db()
    student.refresh_from_db()
    assert profile.current_college_id == college.pk
    assert profile.updated_at == updated_at
    assert student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert not AuditEvent.objects.filter(
        action="student_academics.placement.cleared", target_id=str(student.pk)
    ).exists()


@pytest.mark.django_db
def test_record_graduation_clears_placement_and_transitions_lifecycle():
    sync_policy()
    actor = make_user("graduation.actor@example.edu", "IT_ADMIN")
    student = make_user("graduation.student@example.edu")
    college = make_college()
    program = Program.objects.create(college=college, code="BSIS", name="BS IS")
    profile = StudentAcademicProfile.objects.create(
        student=student,
        current_college=college,
        current_program=program,
        placement_verification_status=PlacementVerificationStatus.VERIFIED,
        placement_effective_at=timezone.now(),
    )
    before = timezone.now()

    record = record_graduation(
        student_id=student.pk,
        graduated_college_id=college.pk,
        graduation_date=date(2026, 6, 30),
        verification_source="  Registrar confirmation  ",
        context=context(actor),
    )

    assert record.student_id == student.pk
    assert record.graduated_college_id == college.pk
    assert record.graduated_program_id is None
    assert record.graduation_date == date(2026, 6, 30)
    assert record.verification_source == "Registrar confirmation"
    assert record.verified_by == actor
    assert record.verified_at >= before
    profile.refresh_from_db()
    assert profile.current_college_id is None
    assert profile.current_program_id is None
    assert profile.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert profile.placement_effective_at is None
    assert profile.updated_by == actor
    student.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.GRADUATED
    placement_event = AuditEvent.objects.get(action="student_academics.placement.cleared")
    assert placement_event.metadata == {
        "previous_college_id": str(college.pk),
        "cause": "graduation",
    }
    event = AuditEvent.objects.get(action="student_academics.graduation.recorded")
    assert event.target_type == "student_academics.studentgraduationrecord"
    assert event.target_id == str(record.pk)
    assert event.metadata == {
        "created": True,
        "student_id": str(student.pk),
        "previous_college_id": None,
        "new_college_id": str(college.pk),
        "previous_graduation_date": None,
        "new_graduation_date": "2026-06-30",
        "previous_source": None,
        "new_source": "Registrar confirmation",
        "lifecycle_from": "CURRENT",
        "lifecycle_to": "GRADUATED",
        "placement_cleared": True,
    }


@pytest.mark.django_db
def test_record_graduation_correction_noop_and_lifecycle_resubmission():
    sync_policy()
    actor = make_user("graduation.update.actor@example.edu", "IT_ADMIN")
    student = make_user("graduation.update.student@example.edu")
    college = make_college()
    other_college = make_college("GRAD-OTHER", campus_code="GRAD-OTHER")

    first = record_graduation(
        student_id=student.pk,
        graduated_college_id=college.pk,
        graduation_date=date(2026, 6, 30),
        verification_source="Registrar confirmation",
        context=context(actor),
    )
    corrected = record_graduation(
        student_id=student.pk,
        graduated_college_id=other_college.pk,
        graduation_date=date(2026, 7, 1),
        verification_source="Corrected registrar confirmation",
        context=context(actor),
    )

    assert corrected.pk == first.pk
    assert corrected.graduated_college_id == other_college.pk
    assert corrected.graduation_date == date(2026, 7, 1)
    events = AuditEvent.objects.filter(action="student_academics.graduation.recorded")
    assert events.count() == 2
    event = events.latest("occurred_at")
    assert event.metadata["created"] is False
    assert event.metadata["previous_college_id"] == str(college.pk)
    assert event.metadata["new_college_id"] == str(other_college.pk)
    assert event.metadata["previous_graduation_date"] == "2026-06-30"
    assert event.metadata["new_graduation_date"] == "2026-07-01"
    assert event.metadata["previous_source"] == "Registrar confirmation"
    assert event.metadata["new_source"] == "Corrected registrar confirmation"
    assert event.metadata["lifecycle_from"] == "GRADUATED"
    assert event.metadata["lifecycle_to"] == "GRADUATED"
    assert event.metadata["placement_cleared"] is False
    assert not AuditEvent.objects.filter(action="student_academics.placement.cleared").exists()

    verified_at = corrected.verified_at
    audits = events.count()
    again = record_graduation(
        student_id=student.pk,
        graduated_college_id=other_college.pk,
        graduation_date=date(2026, 7, 1),
        verification_source="Corrected registrar confirmation",
        context=context(actor),
    )
    assert again.pk == first.pk
    assert again.verified_at == verified_at
    assert (
        AuditEvent.objects.filter(action="student_academics.graduation.recorded").count() == audits
    )

    User.objects.filter(pk=student.pk).update(
        student_lifecycle_status=StudentLifecycleStatus.CURRENT
    )
    resubmitted = record_graduation(
        student_id=student.pk,
        graduated_college_id=other_college.pk,
        graduation_date=date(2026, 7, 1),
        verification_source="Corrected registrar confirmation",
        context=context(actor),
    )
    assert resubmitted.pk == first.pk
    student.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.GRADUATED
    resubmission = AuditEvent.objects.filter(action="student_academics.graduation.recorded").latest(
        "occurred_at"
    )
    assert resubmission.metadata["lifecycle_from"] == "CURRENT"
    assert resubmission.metadata["lifecycle_to"] == "GRADUATED"
    assert resubmission.metadata["placement_cleared"] is False


@pytest.mark.django_db
def test_record_graduation_with_already_cleared_placement_does_not_clear_or_audit():
    sync_policy()
    actor = make_user("graduation.cleared.actor@example.edu", "IT_ADMIN")
    student = make_user("graduation.cleared.student@example.edu")
    college = make_college()
    StudentAcademicProfile.objects.create(student=student)

    record = record_graduation(
        student_id=student.pk,
        graduated_college_id=college.pk,
        graduation_date=date(2026, 6, 30),
        verification_source="Registrar confirmation",
        context=context(actor),
    )

    event = AuditEvent.objects.get(action="student_academics.graduation.recorded")
    assert event.metadata["placement_cleared"] is False
    assert not AuditEvent.objects.filter(action="student_academics.placement.cleared").exists()
    student.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.GRADUATED
    assert record.graduated_college_id == college.pk


@pytest.mark.django_db
def test_record_graduation_validation_and_inactive_student():
    sync_policy()
    actor = make_user("graduation.validation.actor@example.edu", "IT_ADMIN")
    student = make_user("graduation.validation.student@example.edu")
    inactive = make_user("graduation.inactive.student@example.edu", active=False)
    counselor = make_user("graduation.counselor@example.edu", "COUNSELOR")
    college = make_college()
    inactive_college = make_college("GRAD-OFF", active=False)

    def attempt(**overrides):
        payload = {
            "student_id": student.pk,
            "graduated_college_id": college.pk,
            "graduation_date": date(2026, 6, 30),
            "verification_source": "Registrar confirmation",
            "context": context(actor),
        }
        payload.update(overrides)
        return record_graduation(**payload)

    with pytest.raises(InvalidStudentAcademicInput):
        attempt(student_id=counselor.pk)
    with pytest.raises(StudentAcademicNotFound):
        attempt(student_id=uuid4())
    with pytest.raises(StudentAcademicNotFound):
        attempt(graduated_college_id=uuid4())
    with pytest.raises(StudentAcademicConflict):
        attempt(graduated_college_id=inactive_college.pk)
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(verification_source="   ")
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(verification_source="x" * 201)
    with pytest.raises(InvalidStudentAcademicInput):
        attempt(graduation_date="2026-06-30")

    record = attempt(student_id=inactive.pk, verification_source="x" * 200)
    assert record.verification_source == "x" * 200
    inactive.refresh_from_db()
    assert inactive.student_lifecycle_status == StudentLifecycleStatus.GRADUATED


@pytest.mark.django_db
def test_get_student_academic_record_aggregates_placement_periods_and_graduation():
    sync_policy()
    actor = make_user("record.actor@example.edu", "IT_ADMIN")
    student = make_user("record.student@example.edu")
    college = make_college()
    other_college = make_college("REC-OTHER", campus_code="REC-OTHER")
    years = {label: make_academic_year(label) for label in ("2024-2025", "2025-2026", "2026-2027")}
    profile = set_current_placement(
        student_id=student.pk, college_id=college.pk, context=context(actor)
    )
    for label, term, year_level in (
        ("2025-2026", AcademicTerm.FIRST_SEMESTER, 3),
        ("2026-2027", AcademicTerm.SECOND_SEMESTER, 4),
        ("2024-2025", AcademicTerm.FIRST_SEMESTER, 2),
        ("2026-2027", AcademicTerm.FIRST_SEMESTER, 4),
    ):
        record_academic_period(
            student_id=student.pk,
            academic_year_id=years[label].pk,
            term=term,
            college_id=college.pk,
            year_level=year_level,
            enrollment_status=EnrollmentStatus.ENROLLED,
            context=context(actor),
        )

    record = get_student_academic_record(student_id=student.pk)

    assert record.student.pk == student.pk
    assert record.lifecycle_status == StudentLifecycleStatus.CURRENT
    assert record.placement is not None
    assert record.placement.pk == profile.pk
    assert [(item.academic_year.label, item.term) for item in record.periods] == [
        ("2026-2027", "FIRST_SEMESTER"),
        ("2026-2027", "SECOND_SEMESTER"),
        ("2025-2026", "FIRST_SEMESTER"),
        ("2024-2025", "FIRST_SEMESTER"),
    ]
    assert record.graduation is None

    record_graduation(
        student_id=student.pk,
        graduated_college_id=other_college.pk,
        graduation_date=date(2026, 6, 30),
        verification_source="Registrar confirmation",
        context=context(actor),
    )
    graduated = get_student_academic_record(student_id=student.pk)
    assert graduated.placement is None
    assert graduated.lifecycle_status == StudentLifecycleStatus.GRADUATED
    assert graduated.graduation is not None
    assert graduated.graduation.graduated_college_id == other_college.pk


@pytest.mark.django_db
def test_get_student_academic_record_handles_absent_profile_and_invalid_students():
    sync_policy()
    student = make_user("record.empty@example.edu")
    cleared = make_user("record.cleared@example.edu")
    college = make_college()
    StudentAcademicProfile.objects.create(student=cleared, current_college=college)
    clear_current_placement(
        student_id=cleared.pk,
        context=context(make_user("record.clear.actor@example.edu", "IT_ADMIN")),
    )

    assert get_student_academic_record(student_id=student.pk).placement is None
    assert get_student_academic_record(student_id=cleared.pk).placement is None
    assert get_student_academic_record(student_id=student.pk).periods == ()
    assert get_student_academic_record(student_id=student.pk).graduation is None

    with pytest.raises(StudentAcademicNotFound):
        get_student_academic_record(student_id=uuid4())
    with pytest.raises(InvalidStudentAcademicInput):
        get_student_academic_record(
            student_id=make_user("record.counselor@example.edu", "COUNSELOR").pk
        )


@pytest.mark.django_db
def test_record_http_authorization_mfa_errors_and_round_trip():
    sync_policy()
    admin = make_user("record.http.admin@example.edu", "IT_ADMIN")
    student = make_user("record.http.student@example.edu")
    counselor = make_user("record.http.counselor@example.edu", "COUNSELOR")
    college = make_college()
    inactive = make_college("HTTP-OFF", active=False)
    year = make_academic_year()
    period_payload = {
        "academic_year_id": str(year.pk),
        "term": "FIRST_SEMESTER",
        "college_id": str(college.pk),
        "year_level": 2,
        "enrollment_status": "ENROLLED",
    }
    graduation_payload = {
        "graduated_college_id": str(college.pk),
        "graduation_date": "2026-06-30",
        "verification_source": "Registrar confirmation",
    }

    assert Client().get(f"{BASE}/students/{student.pk}/record").status_code == 401
    assert auth_client(counselor).get(f"{BASE}/students/{student.pk}/record").status_code == 403

    client = auth_client(admin)
    headers = csrf(client)
    empty = client.get(f"{BASE}/students/{student.pk}/record")
    assert empty.status_code == 200
    assert empty.json() == {
        "student": {
            "id": str(student.pk),
            "institutional_id": None,
            "full_name": "Test User",
            "email": student.email,
            "role": "STUDENT",
            "is_active": True,
            "responsibility_scope": None,
        },
        "lifecycle_status": "CURRENT",
        "placement": None,
        "periods": [],
        "graduation": None,
    }

    stale = auth_client(admin, recent_mfa=False)
    denied = stale.put(
        f"{BASE}/students/{student.pk}/periods",
        data=period_payload,
        content_type="application/json",
        **csrf(stale),
    )
    assert denied.status_code == 403

    unknown_key = client.put(
        f"{BASE}/students/{student.pk}/periods",
        data={**period_payload, "program_id": str(uuid4())},
        content_type="application/json",
        **headers,
    )
    assert unknown_key.status_code == 422

    period_created = client.put(
        f"{BASE}/students/{student.pk}/periods",
        data=period_payload,
        content_type="application/json",
        **headers,
    )
    assert period_created.status_code == 200
    assert period_created.json()["academic_year"] == {
        "id": str(year.pk),
        "label": "2026-2027",
        "is_current": False,
    }
    assert period_created.json()["enrollment_status"] == "ENROLLED"

    conflict = client.put(
        f"{BASE}/students/{student.pk}/periods",
        data={**period_payload, "college_id": str(inactive.pk)},
        content_type="application/json",
        **headers,
    )
    assert conflict.status_code == 409

    graduation_created = client.put(
        f"{BASE}/students/{student.pk}/graduation",
        data=graduation_payload,
        content_type="application/json",
        **headers,
    )
    assert graduation_created.status_code == 200
    assert graduation_created.json()["verified_by"]["id"] == str(admin.pk)

    aggregate = client.get(f"{BASE}/students/{student.pk}/record").json()
    assert aggregate["lifecycle_status"] == "GRADUATED"
    assert aggregate["placement"] is None
    assert len(aggregate["periods"]) == 1
    assert aggregate["graduation"]["graduation_date"] == "2026-06-30"

    assert client.get(f"{BASE}/students/{uuid4()}/record").status_code == 404
    assert client.get(f"{BASE}/students/{counselor.pk}/record").status_code == 422


@pytest.mark.django_db
def test_no_delete_routes_exist_for_periods_or_graduation():
    sync_policy()
    admin = make_user("record.delete.admin@example.edu", "IT_ADMIN")
    student = make_user("record.delete.student@example.edu")
    client = auth_client(admin)
    headers = csrf(client)

    assert client.delete(f"{BASE}/students/{student.pk}/periods", **headers).status_code == 405
    assert client.delete(f"{BASE}/students/{student.pk}/graduation", **headers).status_code == 405


@pytest.mark.django_db
def test_audit_failure_rolls_back_graduation_placement_and_lifecycle(monkeypatch):
    sync_policy()
    actor = make_user("graduation.rollback.actor@example.edu", "IT_ADMIN")
    student = make_user("graduation.rollback.student@example.edu")
    college = make_college()
    profile = StudentAcademicProfile.objects.create(student=student, current_college=college)

    def failed_audit(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr("compass.student_academics.services.record_event", failed_audit)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        record_graduation(
            student_id=student.pk,
            graduated_college_id=college.pk,
            graduation_date=date(2026, 6, 30),
            verification_source="Registrar confirmation",
            context=context(actor),
        )

    assert not StudentGraduationRecord.objects.exists()
    profile.refresh_from_db()
    assert profile.current_college_id == college.pk
    student.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert not AuditEvent.objects.filter(action="student_academics.graduation.recorded").exists()


@pytest.mark.django_db
def test_profile_save_failure_rolls_back_graduation_without_audit(monkeypatch):
    sync_policy()
    actor = make_user("graduation.save.actor@example.edu", "IT_ADMIN")
    student = make_user("graduation.save.student@example.edu")
    college = make_college()
    StudentAcademicProfile.objects.create(student=student, current_college=college)

    def failed_save(self, *args, **kwargs):
        raise RuntimeError("Synthetic profile failure")

    monkeypatch.setattr(StudentAcademicProfile, "save", failed_save)
    with pytest.raises(RuntimeError, match="Synthetic profile failure"):
        record_graduation(
            student_id=student.pk,
            graduated_college_id=college.pk,
            graduation_date=date(2026, 6, 30),
            verification_source="Registrar confirmation",
            context=context(actor),
        )

    assert not StudentGraduationRecord.objects.exists()
    student.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert not AuditEvent.objects.filter(action="student_academics.graduation.recorded").exists()
    assert not AuditEvent.objects.filter(action="student_academics.placement.cleared").exists()


@pytest.mark.django_db
def test_clearing_an_already_cleared_profile_is_a_noop_without_audit():
    sync_policy()
    actor = make_user("cleared.noop.actor@example.edu", "IT_ADMIN")
    student = make_user("cleared.noop.student@example.edu")
    profile = StudentAcademicProfile.objects.create(student=student)
    updated_at = profile.updated_at

    assert clear_current_placement(student_id=student.pk, context=context(actor)) is False

    profile.refresh_from_db()
    assert profile.updated_at == updated_at
    assert not AuditEvent.objects.filter(action="student_academics.placement.cleared").exists()


@pytest.mark.django_db
def test_list_current_placements_excludes_non_student_profiles():
    sync_policy()
    counselor = make_user("list.nonstudent@example.edu", "COUNSELOR")
    college = make_college()
    StudentAcademicProfile.objects.create(student=counselor, current_college=college)

    assert list_current_placements().items == ()
    assert list_current_placements(student_id=counselor.pk).items == ()
