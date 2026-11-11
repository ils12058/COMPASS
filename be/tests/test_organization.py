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
from compass.organization.access_scope import (
    resolve_general_guidance_college_scope,
    resolve_operational_responsibility_scope,
)
from compass.organization.bootstrap import initialize_organization_catalog
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StaffSupervision,
)
from compass.organization.services import (
    effective_responsibility_colleges,
    resolve_default_counselor_for_student,
    set_counselor_responsibility,
    set_staff_supervisor,
)
from compass.student_academics.models import StudentAcademicProfile
from compass.student_academics.services import (
    clear_current_placement,
    set_current_placement,
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
    for role_code in ("STUDENT", "GUIDANCE_OFFICE_ASSISTANT", "COUNSELOR", "IT_ADMIN"):
        actor = make_user(f"read-{role_code.lower()}@example.edu", role_code)
        client = auth_client(actor)
        for collection, record_id in (
            ("campuses", campus.pk),
            ("colleges", college.pk),
            ("programs", program.pk),
        ):
            assert client.get(f"/api/v1/organization/{collection}").status_code == 200
            assert client.get(f"/api/v1/organization/{collection}/{record_id}").status_code == 200
        if role_code in {"STUDENT", "GUIDANCE_OFFICE_ASSISTANT", "COUNSELOR"}:
            assert not actor.has_capability("organization.manage")
            for path in (
                "counselor-responsibilities",
                "staff-supervisions",
            ):
                assert client.get(f"/api/v1/organization/{path}").status_code == 403
            assert (
                client.get("/api/v1/organization/people", {"role": "COUNSELOR"}).status_code == 403
            )
            removed_write = client.post(
                "/api/v1/organization/campuses",
                data=json.dumps(
                    {"code": "DENIED", "name": "Denied", "is_active": False, "basis": "Synthetic"}
                ),
                content_type="application/json",
                **csrf(client),
            )
            assert removed_write.status_code == 403

    officer = make_user("read-officer@example.edu", "INSTITUTIONAL_OFFICER")
    assert auth_client(officer).get("/api/v1/organization/campuses").status_code == 403


@pytest.mark.django_db
def test_program_read_exposes_exact_academic_classification_and_pending_policy():
    sync_policy()
    initialize_organization_catalog(action="seed")
    student = make_user("program-metadata@example.edu", "STUDENT")
    response = auth_client(student).get("/api/v1/organization/programs", {"is_active": True})
    assert response.status_code == 200
    items = response.json()["items"]

    def find(campus: str, college: str, code: str):
        return next(
            item
            for item in items
            if item["college"]["campus"]["code"] == campus
            and item["college"]["code"] == college
            and item["code"] == code
        )

    bachelors = find("MAIN", "CCMS", "BSIS")
    assert bachelors["academic_classification"] == "BACHELORS"
    assert bachelors["year_level_policy_status"] == "CONFIGURED"
    assert bachelors["applicable_year_levels"] == [1, 2, 3, 4]

    masters = find("MAIN", "CCMS", "MIT")
    assert masters["academic_classification"] == "MASTERS"
    assert masters["year_level_policy_status"] == "PENDING_POLICY"
    assert masters["applicable_year_levels"] is None

    doctoral = find("MAIN", "GS", "DBA")
    assert doctoral["academic_classification"] == "DOCTORAL"
    assert doctoral["year_level_policy_status"] == "PENDING_POLICY"
    assert doctoral["applicable_year_levels"] is None


@pytest.mark.django_db
def test_effective_scope_head_and_goa_inheritance_are_dynamic_not_capability_inheritance():
    sync_policy()
    campus = Campus.objects.create(code="MAIN", name="Main")
    college_a = College.objects.create(campus=campus, code="A", name="A")
    college_b = College.objects.create(campus=campus, code="B", name="B")
    counselor = make_user("c@example.edu", "COUNSELOR")
    staff = make_user("goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")

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
def test_operational_scope_is_canonical_and_fail_closed():
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
    staff = make_user("auth-scope-staff@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    head_staff = make_user("auth-scope-head-staff@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    unsupervised = make_user("auth-scope-unsupervised@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    inactive_supervisor = make_user(
        "auth-scope-inactive-supervisor@example.edu",
        "COUNSELOR",
        active=False,
    )
    inactive_staff = make_user(
        "auth-scope-inactive-staff@example.edu",
        "GUIDANCE_OFFICE_ASSISTANT",
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

    counselor_scope = resolve_operational_responsibility_scope(counselor)
    assert counselor_scope.college_ids == (college.pk,)

    staff_scope = resolve_operational_responsibility_scope(staff)
    assert staff_scope == counselor_scope

    head_scope = resolve_operational_responsibility_scope(head)
    assert head_scope.college_ids == ()

    head_staff_scope = resolve_operational_responsibility_scope(head_staff)
    assert head_staff_scope == head_scope

    for actor in (unsupervised, inactive_staff, unsupported):
        scope = resolve_operational_responsibility_scope(actor)
        assert scope.college_ids == ()


@pytest.mark.django_db
def test_general_guidance_college_scope_separates_head_visibility_from_handled_workload():
    sync_policy()
    campus = Campus.objects.create(code="VISIBLE", name="Active Campus")
    inactive_campus = Campus.objects.create(code="HIDDEN", name="Inactive Campus", is_active=False)
    assigned_a = College.objects.create(campus=campus, code="A", name="Assigned A")
    assigned_b = College.objects.create(campus=campus, code="B", name="Assigned B")
    unassigned = College.objects.create(campus=campus, code="C", name="Unassigned")
    inactive_college = College.objects.create(
        campus=campus, code="D", name="Inactive College", is_active=False
    )
    inactive_campus_college = College.objects.create(
        campus=inactive_campus, code="E", name="Inactive Campus College"
    )
    carlo = make_user("scope-carlo@example.edu", "COUNSELOR")
    other = make_user("scope-other@example.edu", "COUNSELOR")
    head = make_user("scope-head@example.edu", "COUNSELOR")
    goa = make_user("scope-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    head_goa = make_user("scope-head-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    admin = make_user("scope-admin@example.edu", "IT_ADMIN")
    designation = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    head.designations.add(designation)
    CounselorResponsibility.objects.create(college=assigned_a, counselor=carlo)
    CounselorResponsibility.objects.create(college=assigned_b, counselor=other)
    CounselorResponsibility.objects.create(college=inactive_college, counselor=carlo)
    CounselorResponsibility.objects.create(college=inactive_campus_college, counselor=carlo)
    StaffSupervision.objects.create(staff=goa, supervisor=carlo)
    StaffSupervision.objects.create(staff=head_goa, supervisor=head)

    def visible(actor):
        return set(resolve_general_guidance_college_scope(actor).college_ids)

    eligible = {assigned_a.pk, assigned_b.pk, unassigned.pk}
    assert visible(head) == visible(head_goa) == eligible
    assert visible(carlo) == visible(goa) == {assigned_a.pk}
    assert visible(other) == {assigned_b.pk}
    assert visible(admin) == set()
    assert not head_goa.designations.filter(pk=designation.pk).exists()
    # Handled assignment/fallback is intentionally a different contract.
    assert set(resolve_operational_responsibility_scope(head).college_ids) == {unassigned.pk}
    assert set(resolve_operational_responsibility_scope(head_goa).college_ids) == {unassigned.pk}
    # Each Head sees every eligible College, but multiple Heads invalidate
    # the unique-Head handled fallback instead of selecting one arbitrarily.
    other.designations.add(designation)
    assert visible(head) == visible(other) == visible(head_goa) == eligible
    assert resolve_operational_responsibility_scope(head).college_ids == ()
    assert resolve_operational_responsibility_scope(head_goa).college_ids == ()


@pytest.mark.django_db
def test_general_guidance_goa_scope_rechecks_current_supervision_designation_and_identity():
    sync_policy()
    campus = Campus.objects.create(code="DYNAMIC", name="Current Campus")
    college_a = College.objects.create(campus=campus, code="A", name="College A")
    college_b = College.objects.create(campus=campus, code="B", name="College B")
    carlo = make_user("dynamic-carlo@example.edu", "COUNSELOR")
    head = make_user("dynamic-head@example.edu", "COUNSELOR")
    staff = make_user("dynamic-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    unsupervised = make_user("dynamic-unsupervised@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    CounselorResponsibility.objects.create(college=college_a, counselor=carlo)
    StaffSupervision.objects.create(staff=staff, supervisor=carlo)

    def visible(actor):
        return set(resolve_general_guidance_college_scope(actor).college_ids)

    assert visible(staff) == {college_a.pk}
    assert visible(unsupervised) == set()
    StaffSupervision.objects.filter(staff=staff).update(supervisor=head)
    assert visible(staff) == {college_a.pk, college_b.pk}
    # Losing Head status immediately narrows the inherited visibility.
    head.designations.clear()
    assert visible(head) == visible(staff) == set()
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    assert visible(staff) == {college_a.pk, college_b.pk}

    StaffSupervision.objects.filter(staff=staff).update(supervisor=carlo)
    assert visible(staff) == {college_a.pk}
    StaffSupervision.objects.filter(staff=staff).update(supervisor=head)
    User.objects.filter(pk=head.pk).update(is_active=False)
    assert visible(head) == visible(staff) == set()
    User.objects.filter(pk=head.pk).update(is_active=True)
    assert visible(staff) == {college_a.pk, college_b.pk}
    User.objects.filter(pk=head.pk).update(role=Role.objects.get(code="IT_ADMIN"))
    assert visible(head) == visible(staff) == set()
    StaffSupervision.objects.filter(staff=staff).delete()
    assert visible(staff) == set()

    StaffSupervision.objects.create(staff=staff, supervisor=carlo)
    assert visible(staff) == {college_a.pk}
    User.objects.filter(pk=staff.pk).update(is_active=False)
    assert visible(staff) == set()
    User.objects.filter(pk=staff.pk).update(is_active=True)
    User.objects.filter(pk=staff.pk).update(role=Role.objects.get(code="IT_ADMIN"))
    assert visible(staff) == set()


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

    set_current_placement(
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
def test_default_counselor_reports_missing_academic_placement():
    sync_policy()
    student = make_user("no-placement@example.edu", "STUDENT")

    result = resolve_default_counselor_for_student(student)
    assert result.counselor is None
    assert result.source == "UNRESOLVED"
    assert result.reason == "NO_PLACEMENT"

    StudentAcademicProfile.objects.create(student=student)
    result = resolve_default_counselor_for_student(student)
    assert result.counselor is None
    assert result.reason == "NO_PLACEMENT"


@pytest.mark.django_db
def test_disabled_supervisor_keeps_relationship_but_staff_operational_scope_is_empty():
    sync_policy()
    admin = make_user("relationship-admin@example.edu", "IT_ADMIN")
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    counselor = make_user("c@example.edu", "COUNSELOR")
    staff = make_user("staff@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
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

    set_current_placement(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )
    count = AuditEvent.objects.filter(action="student_academics.placement.set").count()
    set_current_placement(
        student_id=student.pk,
        college_id=college.pk,
        context=context(actor),
    )
    assert StudentAcademicProfile.objects.filter(student=student).count() == 1
    assert AuditEvent.objects.filter(action="student_academics.placement.set").count() == count


@pytest.mark.django_db
def test_role_changes_are_blocked_until_organization_relationship_is_removed():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("s@example.edu", "STUDENT")
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    StudentAcademicProfile.objects.create(student=student, current_college=college)
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

    clear_current_placement(student_id=student.pk, context=context(admin))
    assert StudentAcademicProfile.objects.filter(student=student).exists()
    allowed = client.put(
        f"/api/v1/accounts/{student.pk}/role",
        data=json.dumps({"role": "COUNSELOR"}),
        content_type="application/json",
        **headers,
    )
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_legacy_arbitrary_structural_write_routes_remain_removed():
    sync_policy()
    actor = make_user("structure-admin@example.edu", "IT_ADMIN")
    client = auth_client(actor)
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    program = Program.objects.create(college=college, code="P", name="Program")
    headers = csrf(client)

    requests = (
        ("post", "/api/v1/organization/campuses", {"code": "N", "name": "North"}),
        ("patch", f"/api/v1/organization/campuses/{campus.pk}", {"name": "Changed"}),
        ("post", f"/api/v1/organization/campuses/{campus.pk}/enable", None),
        ("post", f"/api/v1/organization/campuses/{campus.pk}/disable", None),
        (
            "post",
            "/api/v1/organization/colleges",
            {"campus_id": str(campus.pk), "code": "N", "name": "New"},
        ),
        ("patch", f"/api/v1/organization/colleges/{college.pk}", {"name": "Changed"}),
        ("post", f"/api/v1/organization/colleges/{college.pk}/enable", None),
        ("post", f"/api/v1/organization/colleges/{college.pk}/disable", None),
        (
            "post",
            "/api/v1/organization/programs",
            {"college_id": str(college.pk), "code": "N", "name": "New"},
        ),
        ("patch", f"/api/v1/organization/programs/{program.pk}", {"name": "Changed"}),
        ("post", f"/api/v1/organization/programs/{program.pk}/enable", None),
        ("post", f"/api/v1/organization/programs/{program.pk}/disable", None),
    )

    for method, path, payload in requests:
        response = getattr(client, method)(
            path,
            data=json.dumps(payload) if payload is not None else None,
            content_type="application/json",
            **headers,
        )
        assert response.status_code in (
            {403, 422}
            if method == "post" and path.endswith(("campuses", "colleges", "programs"))
            else {404, 405}
        )


@pytest.mark.django_db
def test_organization_manage_still_governs_operational_relationships_with_recent_mfa():
    sync_policy()
    campus = Campus.objects.create(code="M", name="Main")
    college = College.objects.create(campus=campus, code="C", name="College")
    head = make_user("head@example.edu", "COUNSELOR")
    assigned = make_user("assigned@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    stale = auth_client(head, recent_mfa=False)
    stale_response = stale.put(
        f"/api/v1/organization/colleges/{college.pk}/counselor",
        data=json.dumps({"counselor_id": str(assigned.pk)}),
        content_type="application/json",
        **csrf(stale),
    )
    assert stale_response.status_code == 403

    fresh = auth_client(head)
    assigned_response = fresh.put(
        f"/api/v1/organization/colleges/{college.pk}/counselor",
        data=json.dumps({"counselor_id": str(assigned.pk)}),
        content_type="application/json",
        **csrf(fresh),
    )
    assert assigned_response.status_code == 200
    assert assigned_response.json()["counselor"]["id"] == str(assigned.pk)

    UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="organization.manage"),
        effect="REVOKE",
        reason="separation",
    )
    denied = fresh.delete(
        f"/api/v1/organization/colleges/{college.pk}/counselor",
        **csrf(fresh),
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_eligible_people_projection_is_complete_and_excludes_inactive_users():
    sync_policy()
    admin = make_user("people-admin@example.edu", "IT_ADMIN")
    active = make_user("active-counselor@example.edu", "COUNSELOR")
    head = make_user("head-counselor@example.edu", "COUNSELOR")
    inactive = make_user("inactive-counselor@example.edu", "COUNSELOR", active=False)
    active.institutional_id = "EMP-001"
    active.first_name = "Active"
    active.last_name = "Counselor"
    active.save(update_fields=["institutional_id", "first_name", "last_name", "updated_at"])
    head.institutional_id = "EMP-002"
    head.first_name = "Head"
    head.last_name = "Counselor"
    head.save(update_fields=["institutional_id", "first_name", "last_name", "updated_at"])
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

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
            "responsibility_scope": "ASSIGNED_COLLEGES",
        },
        {
            "id": str(head.pk),
            "institutional_id": "EMP-002",
            "full_name": "Head Counselor",
            "email": head.email,
            "role": "COUNSELOR",
            "is_active": True,
            "responsibility_scope": "ASSIGNED_AND_FALLBACK_COLLEGES",
        },
    ]
    assert str(inactive.pk) not in {item["id"] for item in payload["items"]}


@pytest.mark.django_db
def test_officer_institutional_officer_is_never_head_guidance_fallback():
    sync_policy()
    campus = Campus.objects.create(code="officer-FALLBACK", name="officer Fallback")
    college = College.objects.create(campus=campus, code="officer-COL", name="officer College")
    student = make_user("officer-routing-student@example.edu", "STUDENT")
    officer = make_user("officer-routing-officer@example.edu", "INSTITUTIONAL_OFFICER")
    set_current_placement(
        student_id=student.pk,
        college_id=college.pk,
        context=context(officer),
    )

    result = resolve_default_counselor_for_student(student)

    assert result.counselor is None
    assert result.reason == "NO_HEAD_FALLBACK"
    assert effective_responsibility_colleges(officer) == ()


@pytest.mark.django_db
def test_head_workload_matches_routing_and_goa_inherits_only_handled_colleges():
    sync_policy()
    campus = Campus.objects.create(code="WORK", name="Workload")
    colleges = {
        code: College.objects.create(campus=campus, code=code, name=code) for code in "ABCDEFX"
    }
    head = make_user("work-head@example.edu", "COUNSELOR")
    other = make_user("work-other@example.edu", "COUNSELOR")
    inactive = make_user("work-inactive@example.edu", "COUNSELOR", active=False)
    unsupported = make_user("work-admin@example.edu", "IT_ADMIN")
    staff = make_user("work-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    StaffSupervision.objects.create(staff=staff, supervisor=head)
    for code, counselor in [
        ("A", other),
        ("B", other),
        ("D", inactive),
        ("E", head),
        ("F", unsupported),
    ]:
        CounselorResponsibility.objects.create(college=colleges[code], counselor=counselor)
    colleges["X"].is_active = False
    colleges["X"].save(update_fields=["is_active"])
    off_campus = Campus.objects.create(code="OFF-WORK", name="Off", is_active=False)
    off_college = College.objects.create(campus=off_campus, code="OFF", name="Off")
    CounselorResponsibility.objects.create(college=off_college, counselor=head)
    expected = {colleges[code].pk for code in "CDEF"}
    assert set(resolve_operational_responsibility_scope(head).college_ids) == expected
    assert resolve_operational_responsibility_scope(
        staff
    ) == resolve_operational_responsibility_scope(head)
    assert {c.pk for c in effective_responsibility_colleges(head)} == expected
    for code, college in colleges.items():
        student = make_user(f"work-{code}@example.edu", "STUDENT")
        StudentAcademicProfile.objects.create(student=student, current_college=college)
        resolution = resolve_default_counselor_for_student(student)
        if code in "AB":
            assert resolution.counselor == other
            assert resolution.source == "COLLEGE_RESPONSIBILITY"
        elif code == "X":
            assert resolution.source == "UNRESOLVED"
        else:
            assert resolution.counselor == head
            assert resolution.source == (
                "COLLEGE_RESPONSIBILITY" if code == "E" else "HEAD_GUIDANCE_FALLBACK"
            )
    assert not staff.designations.exists()
    for capability in (
        "organization.manage",
        "reports.view",
        "inventory.view",
        "student_support.view",
        "counseling.manage_assigned",
        "ecounseling.view_assigned",
    ):
        assert not staff.has_capability(capability)
    # Overrides enable actions, never manufacture workload for unsupported roles.
    UserCapabilityOverride.objects.create(
        user=unsupported,
        capability=Capability.objects.get(code="appointments.manage"),
        effect="GRANT",
        reason="synthetic scope regression",
    )
    assert unsupported.has_capability("appointments.manage")
    assert resolve_operational_responsibility_scope(unsupported).college_ids == ()
    # An invalid supervision role also fails closed, even with responsibility rows.
    StaffSupervision.objects.filter(staff=staff).update(supervisor=unsupported)
    assert resolve_operational_responsibility_scope(staff).college_ids == ()


@pytest.mark.django_db
def test_ambiguous_or_inactive_heads_never_receive_implicit_fallback_workload():
    sync_policy()
    campus = Campus.objects.create(code="MULTI", name="Multiple Heads")
    explicit = College.objects.create(campus=campus, code="EX", name="Explicit")
    fallback = College.objects.create(campus=campus, code="FB", name="Fallback")
    student = make_user("multi-student@example.edu", "STUDENT")
    StudentAcademicProfile.objects.create(student=student, current_college=fallback)
    heads = [make_user(f"multi-h{i}@example.edu", "COUNSELOR") for i in range(2)]
    staff = [make_user(f"multi-g{i}@example.edu", "GUIDANCE_OFFICE_ASSISTANT") for i in range(2)]
    for head, goa in zip(heads, staff, strict=True):
        UserDesignation.objects.create(
            user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
        )
        StaffSupervision.objects.create(staff=goa, supervisor=head)
    CounselorResponsibility.objects.create(college=explicit, counselor=heads[0])
    assert resolve_default_counselor_for_student(student).reason == "AMBIGUOUS_HEAD_CONFIGURATION"
    for index in range(2):
        expected = (explicit.pk,) if index == 0 else ()
        assert resolve_operational_responsibility_scope(heads[index]).college_ids == expected
        assert resolve_operational_responsibility_scope(staff[index]).college_ids == expected
    # Explicit assignment wins even when Head fallback is ambiguous.
    StudentAcademicProfile.objects.filter(student=student).update(current_college=explicit)
    assert resolve_default_counselor_for_student(student).counselor == heads[0]
    for head in heads:
        head.is_active = False
        head.save(update_fields=["is_active"])
    assert resolve_default_counselor_for_student(student).reason == "NO_HEAD_FALLBACK"
    for actor in heads + staff:
        assert resolve_operational_responsibility_scope(actor).college_ids == ()
