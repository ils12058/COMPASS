"""FAC-1 institutional identity, least privilege and compatibility regressions."""

import json
from uuid import uuid4

import pytest
from django.test import Client
from django.utils import timezone

from compass.account_management.csv_import import (
    CsvImportConflict,
    CsvImportInvalidRows,
    provision_accounts_from_csv,
)
from compass.account_management.faculty import set_faculty_affiliation
from compass.account_management.services import (
    DuplicateEmail,
    InvalidManagementInput,
    ManagementNotAuthorized,
    OrganizationRelationshipConflict,
    change_role,
    create_account,
    set_account_active,
    set_capability_override,
)
from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import Capability, Role, RoleCapability, User, UserCapabilityOverride
from compass.accounts.policy import CAPABILITY_CODES, ROLE_CAPABILITY_GRANTS
from compass.accounts.services import effective_capabilities, set_user_capability_override
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import RecentMFARequired, create_auth_session
from compass.organization.catalog_services import _impact
from compass.organization.models import Campus, College, FacultyAffiliation, StudentAffiliation
from compass.organization.services import resolve_default_counselor_for_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_faculty():
    sync_identity_policy()
    admin = person("IT_ADMIN", "admin")
    issued = create_auth_session(admin, mfa_verified_at=timezone.now())
    campus = Campus.objects.create(code="FAC-CAMPUS", name="Faculty Campus")
    college = College.objects.create(campus=campus, code="FAC-COLLEGE", name="Faculty College")
    context = AuditContext.user(admin)
    return dict(actor=admin, actor_session=issued.session, context=context), college


def person(role="FACULTY", label="faculty"):
    return User.objects.create_user(
        email=f"{label}@synthetic.invalid",
        institutional_id=f"FAC-{label}",
        first_name="Synthetic",
        last_name=label,
        role=role,
    )


def provision(args, college=None, label="created"):
    return create_account(
        **args,
        institutional_id=f"FAC-{label}",
        email=f"{label}@synthetic.invalid",
        first_name="Synthetic",
        last_name=label,
        role="FACULTY",
        faculty_college_id=college.pk if college else None,
    )


def assign(args, target, college, version=0):
    return set_faculty_affiliation(
        **args,
        target_id=target.pk,
        college_id=college.pk if college else None,
        expected_resource_version=version,
        basis="Synthetic institutional assignment",
    )


def client_for(user, *, csrf=False):
    issued = create_auth_session(user, mfa_verified_at=timezone.now())
    client = Client(enforce_csrf_checks=csrf)
    client.cookies["compass_session"] = issued.token
    return client


def test_faculty_policy_sync_and_existing_role_baselines(setup_faculty):
    faculty_role = Role.objects.get(code="FACULTY")
    for _ in range(2):
        assert not sync_identity_policy().changed
        assert Role.objects.get(code="FACULTY").pk == faculty_role.pk
    assert ROLE_CAPABILITY_GRANTS["FACULTY"] == frozenset()
    for role, grants in ROLE_CAPABILITY_GRANTS.items():
        assert effective_capabilities(person(role, role)) == grants
    assert not faculty_role.capability_grants.exists()


def test_faculty_ceiling_blocks_persisted_grants_and_old_overrides(setup_faculty):
    faculty = person()
    for code in CAPABILITY_CODES:
        capability = Capability.objects.get(code=code)
        RoleCapability.objects.create(role=faculty.role, capability=capability)
        UserCapabilityOverride.objects.create(
            user=faculty,
            capability=capability,
            effect="GRANT",
            reason="Synthetic legacy state",
        )
    assert effective_capabilities(faculty) == frozenset()
    with pytest.raises(ValueError, match="Faculty"):
        set_user_capability_override(
            user=faculty,
            capability="accounts.manage",
            effect="GRANT",
            reason="Not eligible",
        )
    assert not sync_identity_policy().changed  # ceiling also covers unknown retained DB grants
    assert effective_capabilities(faculty) == frozenset()


def test_creation_provenance_repeat_provisioning_and_safe_missing_home(setup_faculty):
    args, college = setup_faculty
    faculty = provision(args, college)
    affiliation = FacultyAffiliation.objects.get(faculty=faculty)
    assert affiliation.college_id == college.pk
    assert affiliation.assigned_by == args["actor"]
    assert affiliation.basis == "ACCOUNT_CREATION"
    with pytest.raises(DuplicateEmail):
        provision(args, college)
    assert not faculty.has_usable_password()
    assert faculty.student_lifecycle_status is None
    assert effective_capabilities(faculty) == frozenset()
    assign(args, faculty, college, 1)
    assert AuditEvent.objects.filter(action="account.faculty_affiliation.changed").count() == 1
    unassigned = provision(args, label="unassigned")
    assert not FacultyAffiliation.objects.filter(faculty=unassigned).exists()
    assert (
        client_for(unassigned).get("/api/v1/auth/session").json()["user"]["faculty_affiliation"]
        is None
    )


@pytest.mark.parametrize("invalid", ["college", "campus", "missing", "malformed"])
def test_invalid_or_inactive_ancestry_is_rejected_atomically(setup_faculty, invalid):
    args, college = setup_faculty
    college_id = college.pk
    if invalid == "college":
        College.objects.filter(pk=college.pk).update(is_active=False)
    elif invalid == "campus":
        Campus.objects.filter(pk=college.campus_id).update(is_active=False)
    elif invalid == "missing":
        college_id = uuid4()
    else:
        college_id = "invalid"
    with pytest.raises(InvalidManagementInput):
        create_account(
            **args,
            institutional_id="INVALID",
            email="invalid@synthetic.invalid",
            first_name="Synthetic",
            last_name="Invalid",
            role="FACULTY",
            faculty_college_id=college_id,
        )
    assert not User.objects.filter(email="invalid@synthetic.invalid").exists()
    assert not FacultyAffiliation.objects.exists()


def test_affiliation_versions_role_changes_and_catalog_retirement(setup_faculty):
    args, college = setup_faculty
    faculty = provision(args, college)
    assert "active_faculty_affiliations" in {issue.code for issue in _impact(college).blockers}
    other = College.objects.create(campus=college.campus, code="OTHER", name="Other College")
    assign(args, faculty, other, 1)
    with pytest.raises(OrganizationRelationshipConflict):
        assign(args, faculty, college, 1)
    assert FacultyAffiliation.objects.get(faculty=faculty).college_id == other.pk
    change_role(**args, target_id=faculty.pk, role="INSTITUTIONAL_OFFICER")
    assert FacultyAffiliation.objects.get(faculty=faculty).college_id is None
    change_role(**args, target_id=faculty.pk, role="FACULTY")
    faculty.refresh_from_db()
    assert FacultyAffiliation.objects.get(faculty=faculty).resource_version == 3
    assert effective_capabilities(faculty) == frozenset()
    assign(args, faculty, college, 3)
    set_account_active(**args, target_id=faculty.pk, is_active=False)
    assert _impact(college).can_deactivate
    College.objects.filter(pk=college.pk).update(is_active=False)
    with pytest.raises(OrganizationRelationshipConflict):
        set_account_active(**args, target_id=faculty.pk, is_active=True)
    # An administrator can repair an inactive account before reactivation.
    assign(args, faculty, other, 4)
    set_account_active(**args, target_id=faculty.pk, is_active=True)
    assert not _impact(college).counts["active_faculty_affiliations"]


def test_assignment_requires_current_institutional_actor_and_recent_mfa(setup_faculty):
    args, college = setup_faculty
    faculty = person()
    own_args = {**args, "actor": faculty, "actor_session": create_auth_session(faculty).session}
    with pytest.raises(ManagementNotAuthorized):
        assign(own_args, faculty, college)
    stale_mfa = {**args, "actor_session": create_auth_session(args["actor"]).session}
    with pytest.raises(RecentMFARequired):
        assign(stale_mfa, faculty, college)
    args["actor"].is_active = False
    args["actor"].save(update_fields=["is_active"])
    with pytest.raises(ManagementNotAuthorized):
        assign(args, faculty, college)
    assert not FacultyAffiliation.objects.exists()


def csv_data(college_id, *, label="csv", role="FACULTY"):
    return (
        "institutional_id,email,first_name,last_name,role,faculty_college_id\n"
        f"FAC-{label},{label}@synthetic.invalid,Synthetic,{label},{role},{college_id}\n"
    ).encode()


def test_csv_dry_run_exact_skip_conflicts_and_no_affiliation_updates(setup_faculty):
    args, college = setup_faculty
    data = csv_data(college.pk)
    preview = provision_accounts_from_csv(**args, data=data, dry_run=True)
    assert preview.valid and preview.create_count == 1 and not preview.committed
    assert preview.rows[0].faculty_college_id == college.pk
    assert not FacultyAffiliation.objects.exists()
    result = provision_accounts_from_csv(**args, data=data, dry_run=False)
    assert result.committed and result.create_count == 1
    assert provision_accounts_from_csv(**args, data=data, dry_run=False).skip_count == 1
    altered = csv_data("")
    preview = provision_accounts_from_csv(**args, data=altered, dry_run=True)
    assert preview.conflict_count == 1
    with pytest.raises(CsvImportConflict):
        provision_accounts_from_csv(**args, data=altered, dry_run=False)
    assert FacultyAffiliation.objects.get().college_id == college.pk
    for bad in (csv_data(college.pk, role="STUDENT"), csv_data("not-a-uuid")):
        assert provision_accounts_from_csv(**args, data=bad, dry_run=True).invalid_count == 1
    mixed = csv_data(college.pk, label="new") + altered.splitlines(keepends=True)[1]
    with pytest.raises(CsvImportConflict):
        provision_accounts_from_csv(**args, data=mixed, dry_run=False)
    assert not User.objects.filter(email="new@synthetic.invalid").exists()
    set_account_active(
        **args, target_id=User.objects.get(email="csv@synthetic.invalid").pk, is_active=False
    )
    assert provision_accounts_from_csv(**args, data=data, dry_run=True).conflict_count == 1


def test_faculty_cannot_read_gco_records_even_with_persisted_grants(setup_faculty):
    faculty = person()
    for capability in Capability.objects.all():
        UserCapabilityOverride.objects.create(
            user=faculty,
            capability=capability,
            effect="GRANT",
            reason="Synthetic stale authority",
        )
    client = client_for(faculty)
    for path in (
        "/api/v1/referrals",
        "/api/v1/referrals/students",
        "/api/v1/assessment-records",
        "/api/v1/routine-interviews",
        "/api/v1/routine-interviews/me",
        "/api/v1/accounts",
        "/api/v1/accounts/faculty-colleges",
        "/api/v1/platform/health",
        "/api/v1/inventory/me/status",
        "/api/v1/guidance-followups",
        f"/api/v1/counseling/encounters/{uuid4()}",
    ):
        assert client.get(path).status_code == 403, path
    summary = client.get("/api/v1/overview")
    assert summary.status_code == 200
    assert all(summary.json()[key] is None for key in ("student", "guidance", "platform"))


def test_api_provisioning_csrf_versioning_and_no_self_affiliation_writer(setup_faculty):
    args, college = setup_faculty
    client = client_for(args["actor"], csrf=True)
    response = client.get("/api/v1/auth/csrf")
    headers = {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}
    payload = dict(
        institutional_id="API-1",
        email="api@synthetic.invalid",
        first_name="Api",
        last_name="Faculty",
        role="FACULTY",
        faculty_college_id=str(college.pk),
    )
    assert (
        client.post(
            "/api/v1/accounts", json.dumps(payload), content_type="application/json"
        ).status_code
        == 403
    )
    response = client.post(
        "/api/v1/accounts", json.dumps(payload), content_type="application/json", **headers
    )
    assert response.status_code == 201
    faculty_id = response.json()["id"]
    assert response.json()["faculty_affiliation"]["college_id"] == str(college.pk)
    response = client.put(
        f"/api/v1/accounts/{faculty_id}/faculty-affiliation",
        json.dumps(
            {
                "college_id": None,
                "expected_resource_version": 0,
                "basis": "Outdated review",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 409
    faculty = User.objects.get(pk=faculty_id)
    own = client_for(faculty)
    assert (
        own.put(
            f"/api/v1/accounts/{faculty_id}/faculty-affiliation",
            json.dumps(
                {
                    "college_id": None,
                    "expected_resource_version": 1,
                    "basis": "Self attempt",
                }
            ),
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        own.patch(
            "/api/v1/me/profile",
            json.dumps({"faculty_college_id": str(college.pk)}),
            content_type="application/json",
        ).status_code
        == 422
    )


def test_student_affiliation_and_cross_college_routing_remain_independent(setup_faculty):
    args, college = setup_faculty
    student = person("STUDENT", "student")
    student_college = College.objects.create(
        campus=college.campus, code="STUDENT", name="Student College"
    )
    original = StudentAffiliation.objects.create(student=student, college=student_college)
    before = resolve_default_counselor_for_student(student)
    faculty = provision(args, college)
    assign(args, faculty, student_college, 1)
    original.refresh_from_db()
    assert original.college_id == student_college.pk
    assert resolve_default_counselor_for_student(student) == before
    assert not StudentAffiliation.objects.filter(student=faculty).exists()


def test_faculty_catalog_impact_api_includes_strict_counts_and_blockers(setup_faculty):
    args, college = setup_faculty
    provision(args, college)
    set_user_capability_override(
        user=args["actor"],
        capability="organization.catalog.manage",
        effect="GRANT",
        reason="Synthetic catalog impact inspection",
    )
    response = client_for(args["actor"]).get(f"/api/v1/organization/colleges/{college.pk}/impact")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["faculty_affiliations"] == 1
    assert body["counts"]["active_faculty_affiliations"] == 1
    assert body["counts"]["inactive_faculty_affiliations"] == 0
    assert {"code": "active_faculty_affiliations", "count": 1} in body["blockers"]


def test_affiliation_audit_failure_rolls_back_account_and_assignment(setup_faculty, monkeypatch):
    args, college = setup_faculty

    def failed_audit(**kwargs):
        raise RuntimeError("Synthetic unavailable audit store")

    monkeypatch.setattr("compass.account_management.faculty.record_event", failed_audit)
    with pytest.raises(RuntimeError, match="audit store"):
        provision(args, college)
    assert not User.objects.filter(email="created@synthetic.invalid").exists()
    assert not FacultyAffiliation.objects.exists()
    assert not AuditEvent.objects.filter(action="account.created").exists()


def test_csv_commit_revalidates_retired_college_after_preview(setup_faculty):
    args, college = setup_faculty
    data = csv_data(college.pk)
    assert provision_accounts_from_csv(**args, data=data, dry_run=True).valid
    College.objects.filter(pk=college.pk).update(is_active=False)
    with pytest.raises(CsvImportInvalidRows):
        provision_accounts_from_csv(**args, data=data, dry_run=False)
    assert not User.objects.filter(email="csv@synthetic.invalid").exists()


def test_entering_faculty_revokes_sessions_and_rejects_managed_grants(setup_faculty):
    args, _ = setup_faculty
    counselor = person("COUNSELOR", "changing")
    issued = create_auth_session(counselor, mfa_verified_at=timezone.now())
    assert effective_capabilities(counselor) == ROLE_CAPABILITY_GRANTS["COUNSELOR"]
    change_role(**args, target_id=counselor.pk, role="FACULTY")
    counselor.refresh_from_db()
    issued.session.refresh_from_db()
    assert issued.session.revoked_at is not None
    assert effective_capabilities(counselor) == frozenset()
    with pytest.raises(InvalidManagementInput, match="Faculty"):
        set_capability_override(
            **args,
            target_id=counselor.pk,
            capability="referrals.view",
            effect="GRANT",
            reason="Synthetic denied grant",
        )
    assert not UserCapabilityOverride.objects.filter(user=counselor).exists()
