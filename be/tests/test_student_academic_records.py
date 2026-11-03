from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.models import Campus, College, Program
from compass.student_academics.models import (
    PlacementVerificationStatus,
    StudentAcademicProfile,
)
from compass.student_academics.services import (
    InvalidStudentAcademicInput,
    StudentAcademicConflict,
    StudentAcademicNotFound,
    clear_current_placement,
    list_current_placements,
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
