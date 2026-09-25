from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.access_scope import resolve_organizational_access_scope
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StaffSupervision,
    StudentAffiliation,
)
from compass.organization.services import (
    OrganizationConflict,
    effective_responsibility_colleges,
    resolve_default_counselor_for_student,
    set_counselor_responsibility,
    set_staff_supervisor,
    set_student_affiliation,
)


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


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


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
def test_policy_grants_organization_capabilities_and_revoke_still_wins():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    head = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    UserDesignation.objects.create(user=counselor, designation=head)

    assert admin.has_capability("organization.manage")
    assert student.has_capability("organization.structure.view")
    assert counselor.has_capability("organization.manage")

    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code="organization.manage"),
        effect="REVOKE",
        reason="separation",
    )
    assert not counselor.has_capability("organization.manage")


@pytest.mark.django_db
def test_structural_reads_are_available_without_organization_management():
    sync_policy()
    campus = Campus.objects.create(code="READ", name="Read Campus")
    college = College.objects.create(campus=campus, code="READ", name="Read College")
    program = Program.objects.create(college=college, code="READ", name="Read Program")
    for role_code in ("STUDENT", "GUIDANCE_SERVICES_STAFF", "COUNSELOR", "IT_ADMIN"):
        actor = make_user(f"read-{role_code.lower()}@example.edu", role_code)
        client = auth_client(actor)
        for collection, record_id in (
            ("campuses", campus.pk),
            ("colleges", college.pk),
            ("programs", program.pk),
        ):
            assert client.get(f"/api/v1/organization/{collection}").status_code == 200
            assert client.get(f"/api/v1/organization/{collection}/{record_id}").status_code == 200
        if role_code in {"STUDENT", "GUIDANCE_SERVICES_STAFF", "COUNSELOR"}:
            assert not actor.has_capability("organization.manage")
            for path in (
                "counselor-responsibilities",
                "staff-supervisions",
                "student-affiliations",
            ):
                assert client.get(f"/api/v1/organization/{path}").status_code == 403
            assert (
                client.get("/api/v1/organization/people", {"role": "COUNSELOR"}).status_code == 403
            )
            assert (
                client.post(
                    "/api/v1/organization/campuses",
                    data=json.dumps({"code": "DENIED", "name": "Denied"}),
                    content_type="application/json",
                    **csrf(client),
                ).status_code
                == 403
            )

    officer = make_user("read-officer@example.edu", "INSTITUTIONAL_OFFICER")
    assert auth_client(officer).get("/api/v1/organization/campuses").status_code == 403


@pytest.mark.django_db
def test_effective_scope_head_and_gss_inheritance_are_dynamic_not_capability_inheritance():
    sync_policy()
    campus = Campus.objects.create(code="MAIN", name="Main")
    college_a = College.objects.create(campus=campus, code="A", name="A")
    college_b = College.objects.create(campus=campus, code="B", name="B")
    counselor = make_user("c@example.edu", "COUNSELOR")
    staff = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")

    set_counselor_responsibility(
        college_id=college_a.pk,
        counselor_id=counselor.pk,
        context=context(counselor),
    )
    set_staff_supervisor(
        staff_id=staff.pk,
        supervisor_id=counselor.pk,
        context=context(counselor),
    )
    assert {item.pk for item in effective_responsibility_colleges(counselor)} == {college_a.pk}
    assert {item.pk for item in effective_responsibility_colleges(staff)} == {college_a.pk}

    CounselorResponsibility.objects.create(college=college_b, counselor=counselor)
    assert {item.pk for item in effective_responsibility_colleges(staff)} == {
        college_a.pk,
        college_b.pk,
    }

    UserDesignation.objects.create(
        user=counselor,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    assert {item.pk for item in effective_responsibility_colleges(counselor)} == {
        college_a.pk,
        college_b.pk,
    }
    assert {item.pk for item in effective_responsibility_colleges(staff)} == {
        college_a.pk,
        college_b.pk,
    }
    assert not staff.has_capability("organization.manage")


@pytest.mark.django_db
def test_authorization_organizational_scope_resolver_is_canonical_and_fail_closed():
    sync_policy()
    campus = Campus.objects.create(code="AUTH-MAIN", name="Authorization Main")
    inactive_campus = Campus.objects.create(
        code="AUTH-OFF",
        name="Authorization Inactive",
        is_active=False,
    )
    college = College.objects.create(campus=campus, code="AUTH-A", name="Authorization A")
    inactive_college = College.objects.create(
        campus=campus,
        code="AUTH-INACTIVE",
        name="Authorization Inactive College",
        is_active=False,
    )
    inactive_campus_college = College.objects.create(
        campus=inactive_campus,
        code="AUTH-OFF-COL",
        name="Authorization Inactive Campus College",
    )
    counselor = make_user("auth-scope-counselor@example.edu", "COUNSELOR")
    head = make_user("auth-scope-head@example.edu", "COUNSELOR")
    staff = make_user("auth-scope-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    head_staff = make_user("auth-scope-head-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    unsupervised = make_user("auth-scope-unsupervised@example.edu", "GUIDANCE_SERVICES_STAFF")
    inactive_supervisor = make_user(
        "auth-scope-inactive-supervisor@example.edu",
        "COUNSELOR",
        active=False,
    )
    inactive_staff = make_user(
        "auth-scope-inactive-staff@example.edu",
        "GUIDANCE_SERVICES_STAFF",
    )
    unsupported = make_user("auth-scope-admin@example.edu", "IT_ADMIN")

    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    CounselorResponsibility.objects.create(college=inactive_college, counselor=counselor)
    CounselorResponsibility.objects.create(
        college=inactive_campus_college,
        counselor=counselor,
    )
    StaffSupervision.objects.create(staff=staff, supervisor=counselor)
    StaffSupervision.objects.create(staff=inactive_staff, supervisor=inactive_supervisor)
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    StaffSupervision.objects.create(staff=head_staff, supervisor=head)

    counselor_scope = resolve_organizational_access_scope(counselor)
    assert counselor_scope.institution_wide is False
    assert counselor_scope.college_ids == (college.pk,)

    staff_scope = resolve_organizational_access_scope(staff)
    assert staff_scope == counselor_scope

    head_scope = resolve_organizational_access_scope(head)
    assert head_scope.institution_wide is True
    assert head_scope.college_ids == ()

    head_staff_scope = resolve_organizational_access_scope(head_staff)
    assert head_staff_scope.institution_wide is True

    for actor in (unsupervised, inactive_staff, unsupported):
        scope = resolve_organizational_access_scope(actor)
        assert scope.institution_wide is False
        assert scope.college_ids == ()


@pytest.mark.django_db
def test_default_routing_prefers_college_then_head_and_reports_head_ambiguity():
    sync_policy()
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    student = make_user("s@example.edu", "STUDENT")
    counselor = make_user("c@example.edu", "COUNSELOR")
    head_one = make_user("h1@example.edu", "COUNSELOR")
    head_two = make_user("h2@example.edu", "COUNSELOR")
    head = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    UserDesignation.objects.create(user=head_one, designation=head)

    set_student_affiliation(
        student_id=student.pk,
        college_id=college.pk,
        context=context(head_one),
    )
    result = resolve_default_counselor_for_student(student)
    assert result.counselor == head_one
    assert result.source == "HEAD_GUIDANCE_FALLBACK"

    set_counselor_responsibility(
        college_id=college.pk,
        counselor_id=counselor.pk,
        context=context(head_one),
    )
    result = resolve_default_counselor_for_student(student)
    assert result.counselor == counselor
    assert result.source == "COLLEGE_RESPONSIBILITY"

    counselor.is_active = False
    counselor.save(update_fields=["is_active", "updated_at"])
    assert resolve_default_counselor_for_student(student).counselor == head_one

    UserDesignation.objects.create(user=head_two, designation=head)
    result = resolve_default_counselor_for_student(student)
    assert result.counselor is None
    assert result.reason == "AMBIGUOUS_HEAD_CONFIGURATION"


@pytest.mark.django_db
def test_disabled_supervisor_keeps_relationship_but_staff_operational_scope_is_empty():
    sync_policy()
    admin = make_user("relationship-admin@example.edu", "IT_ADMIN")
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    counselor = make_user("c@example.edu", "COUNSELOR")
    staff = make_user("staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    StaffSupervision.objects.create(staff=staff, supervisor=counselor)

    counselor.is_active = False
    counselor.save(update_fields=["is_active", "updated_at"])
    assert StaffSupervision.objects.filter(staff=staff).exists()
    assert effective_responsibility_colleges(staff) == ()

    response = auth_client(admin).get("/api/v1/organization/staff-supervisions")
    assert response.status_code == 200
    assert response.json()["items"][0]["supervisor"]["id"] == str(counselor.pk)
    assert response.json()["items"][0]["supervisor"]["is_active"] is False


@pytest.mark.django_db
def test_assignment_noop_does_not_create_fake_audit_event():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    student = make_user("s@example.edu", "STUDENT")

    set_student_affiliation(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )
    count = AuditEvent.objects.filter(action__startswith="organization.student_affiliation").count()
    set_student_affiliation(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )
    assert StudentAffiliation.objects.filter(student=student).count() == 1
    assert (
        AuditEvent.objects.filter(action__startswith="organization.student_affiliation").count()
        == count
    )


@pytest.mark.django_db
def test_role_changes_are_blocked_until_organization_relationship_is_removed():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("s@example.edu", "STUDENT")
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    StudentAffiliation.objects.create(student=student, college=college, assigned_by=admin)
    client = auth_client(admin)
    headers = csrf(client)

    blocked = client.put(
        f"/api/v1/accounts/{student.pk}/role",
        data=json.dumps({"role": "COUNSELOR"}),
        content_type="application/json",
        **headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "organization_relationship_conflict"

    StudentAffiliation.objects.filter(student=student).delete()
    allowed = client.put(
        f"/api/v1/accounts/{student.pk}/role",
        data=json.dumps({"role": "COUNSELOR"}),
        content_type="application/json",
        **headers,
    )
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_structure_disable_refuses_active_children_and_current_assignments():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    student = make_user("s@example.edu", "STUDENT")
    StudentAffiliation.objects.create(student=student, college=college, assigned_by=actor)

    from compass.organization.services import set_campus_active, set_college_active

    with pytest.raises(OrganizationConflict):
        set_campus_active(campus_id=campus.pk, is_active=False, context=context(actor))
    with pytest.raises(OrganizationConflict):
        set_college_active(college_id=college.pk, is_active=False, context=context(actor))


@pytest.mark.django_db
def test_manager_api_uses_capability_and_recent_mfa_not_role_shortcut():
    sync_policy()
    counselor = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=counselor,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    stale = auth_client(counselor, recent_mfa=False)
    response = stale.post(
        "/api/v1/organization/campuses",
        data=json.dumps({"code": "M", "name": "Main"}),
        content_type="application/json",
        **csrf(stale),
    )
    assert response.status_code == 403

    fresh = auth_client(counselor)
    created = fresh.post(
        "/api/v1/organization/campuses",
        data=json.dumps({"code": "m", "name": "Main"}),
        content_type="application/json",
        **csrf(fresh),
    )
    assert created.status_code == 201
    assert created.json()["code"] == "M"

    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code="organization.manage"),
        effect="REVOKE",
        reason="separation",
    )
    denied = fresh.post(
        "/api/v1/organization/campuses",
        data=json.dumps({"code": "N", "name": "North"}),
        content_type="application/json",
        **csrf(fresh),
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_eligible_people_projection_is_complete_and_excludes_inactive_users():
    sync_policy()
    admin = make_user("people-admin@example.edu", "IT_ADMIN")
    active = make_user("active-counselor@example.edu", "COUNSELOR")
    inactive = make_user("inactive-counselor@example.edu", "COUNSELOR", active=False)
    active.institutional_id = "EMP-001"
    active.first_name = "Active"
    active.last_name = "Counselor"
    active.save(update_fields=["institutional_id", "first_name", "last_name", "updated_at"])

    response = auth_client(admin).get(
        "/api/v1/organization/people",
        {"role": "COUNSELOR"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == [
        {
            "id": str(active.pk),
            "institutional_id": "EMP-001",
            "full_name": "Active Counselor",
            "email": active.email,
            "role": "COUNSELOR",
            "is_active": True,
        }
    ]
    assert str(inactive.pk) not in {item["id"] for item in payload["items"]}


@pytest.mark.django_db
def test_dpo_institutional_officer_is_never_head_guidance_fallback():
    sync_policy()
    campus = Campus.objects.create(code="DPO-FALLBACK", name="DPO Fallback")
    college = College.objects.create(campus=campus, code="DPO-COL", name="DPO College")
    student = make_user("dpo-routing-student@example.edu", "STUDENT")
    officer = make_user("dpo-routing-officer@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=officer,
        designation=Designation.objects.get(code="DPO"),
    )
    set_student_affiliation(
        student_id=student.pk,
        college_id=college.pk,
        context=context(officer),
    )

    result = resolve_default_counselor_for_student(student)

    assert result.counselor is None
    assert result.reason == "NO_HEAD_FALLBACK"
    assert effective_responsibility_colleges(officer) == ()


@pytest.mark.django_db
def test_student_affiliation_collection_is_paginated_searchable_and_filterable():
    sync_policy()
    admin = make_user("affiliation-admin@example.edu", "IT_ADMIN")
    campus = Campus.objects.create(code="AFF-MAIN", name="Affiliation Main")
    other_campus = Campus.objects.create(code="AFF-OTHER", name="Affiliation Other")
    college_a = College.objects.create(campus=campus, code="AFF-A", name="Affiliation A")
    college_b = College.objects.create(campus=other_campus, code="AFF-B", name="Affiliation B")

    students = [
        make_user("affiliation.alpha@example.edu", "STUDENT"),
        make_user("affiliation.beta@example.edu", "STUDENT"),
        make_user("affiliation.gamma@example.edu", "STUDENT"),
    ]
    for index, student in enumerate(students, start=1):
        student.institutional_id = f"AFF-{index:03d}"
        student.first_name = ("Alpha", "Beta", "Gamma")[index - 1]
        student.save(update_fields=["institutional_id", "first_name", "updated_at"])
        StudentAffiliation.objects.create(
            student=student,
            college=college_a if index < 3 else college_b,
        )

    client = auth_client(admin)
    first = client.get("/api/v1/organization/student-affiliations", {"page_size": 2})
    assert first.status_code == 200
    assert first.json()["page"] == 1
    assert first.json()["page_size"] == 2
    assert first.json()["has_next"] is True
    assert len(first.json()["items"]) == 2

    searched = client.get(
        "/api/v1/organization/student-affiliations",
        {"search": "AFF-002"},
    )
    assert searched.status_code == 200
    assert [row["student"]["id"] for row in searched.json()["items"]] == [str(students[1].pk)]
    assert searched.json()["items"][0]["student"]["institutional_id"] == "AFF-002"

    by_college = client.get(
        "/api/v1/organization/student-affiliations",
        {"college_id": str(college_b.pk)},
    )
    assert by_college.status_code == 200
    assert [row["student"]["id"] for row in by_college.json()["items"]] == [str(students[2].pk)]

    by_campus = client.get(
        "/api/v1/organization/student-affiliations",
        {"campus_id": str(campus.pk)},
    )
    assert by_campus.status_code == 200
    assert {row["student"]["id"] for row in by_campus.json()["items"]} == {
        str(students[0].pk),
        str(students[1].pk),
    }

    by_student = client.get(
        "/api/v1/organization/student-affiliations",
        {"student_id": str(students[0].pk)},
    )
    assert by_student.status_code == 200
    assert [row["student"]["id"] for row in by_student.json()["items"]] == [str(students[0].pk)]

    assert (
        client.get(
            "/api/v1/organization/student-affiliations",
            {"page": 0},
        ).status_code
        == 422
    )
