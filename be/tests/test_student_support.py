from __future__ import annotations

import json
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.institutional_forms.models import FormFamily, FormRevision, FormRevisionStatus
from compass.inventory.models import (
    CivilStatusCategory,
    PWDStatus,
    StudentInventory,
)
from compass.inventory.services import (
    InvalidInventoryInput,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.models import (
    AcademicYear,
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
    StudentSupportProfile,
)
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str = "STUDENT") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        last_name="Support",
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def make_org(suffix: str) -> tuple[Campus, College, Program]:
    campus = Campus.objects.create(code=f"CAMP-{suffix}", name=f"Campus {suffix}")
    college = College.objects.create(
        campus=campus,
        code=f"COL-{suffix}",
        name=f"College {suffix}",
    )
    program = Program.objects.create(
        college=college,
        code=f"PROG-{suffix}",
        name=f"Program {suffix}",
    )
    return campus, college, program


def make_revision(suffix: str) -> FormRevision:
    family = FormFamily.objects.create(
        key=f"student-support-{suffix}",
        title="Synthetic F5",
    )
    return FormRevision.objects.create(
        family=family,
        official_code=f"TEST-{suffix}",
        official_revision="0",
        internal_schema_version=1,
        status=FormRevisionStatus.ACTIVE,
    )


def make_inventory(
    *,
    student: User,
    year: AcademicYear,
    program: Program,
    suffix: str,
    submitted: bool = True,
    pwd_status: str | None = PWDStatus.NON_PWD,
    civil_status: str | None = CivilStatusCategory.SINGLE,
    four_ps_status: str | None = FourPsStatus.NOT_SPECIFIED,
    indigenous_peoples_status: str | None = IndigenousPeoplesStatus.NOT_SPECIFIED,
    mother_life_status: str | None = ParentLifeStatus.LIVING,
    father_life_status: str | None = ParentLifeStatus.LIVING,
) -> StudentInventory:
    item = StudentInventory.objects.create(
        student=student,
        academic_year=year,
        form_revision=make_revision(suffix),
        program=program,
        year_level=1,
        submitted_at=timezone.now() if submitted else None,
        civil_status_category=civil_status,
        pwd_status=pwd_status,
    )
    StudentSupportProfile.objects.create(
        inventory=item,
        four_ps_status=four_ps_status,
        indigenous_peoples_status=indigenous_peoples_status,
        mother_life_status=mother_life_status,
        father_life_status=father_life_status,
    )
    return item


def affiliate(student: User, college: College, *, counselor: User | None = None) -> None:
    StudentAffiliation.objects.create(student=student, college=college)
    if counselor is not None:
        CounselorResponsibility.objects.create(college=college, counselor=counselor)


def make_head(email: str = "head.student.support@example.edu") -> User:
    head = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return head


@pytest.mark.django_db
def test_student_support_capability_is_counselor_only_by_default_and_head_inherits():
    sync_policy()
    counselor = make_user("support-counselor@example.edu", "COUNSELOR")
    head = make_head()
    staff = make_user("support-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("support-student@example.edu")
    admin = make_user("support-admin@example.edu", "IT_ADMIN")
    dpo = make_user("support-dpo@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )

    assert counselor.has_capability("student_support.view")
    assert head.has_capability("student_support.view")
    for denied in (staff, student, admin, dpo):
        assert not denied.has_capability("student_support.view")


@pytest.mark.django_db
def test_unsupported_role_override_still_cannot_access_support_context():
    sync_policy()
    admin = make_user("support-override-admin@example.edu", "IT_ADMIN")
    set_user_capability_override(
        user=admin,
        capability=Capability.objects.get(code="student_support.view"),
        effect="GRANT",
        reason="Synthetic stale override",
    )
    assert admin.has_capability("student_support.view")

    response = auth_client(admin).get(f"/api/v1/student-support/students/{uuid4()}/context")
    assert response.status_code == 403


@pytest.mark.django_db
def test_head_can_view_any_current_submitted_student_support_context():
    sync_policy()
    head = make_head("support-head-anywhere@example.edu")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, college, program = make_org("HEAD")
    student = make_user("support-head-student@example.edu")
    affiliate(student, college)
    make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="head",
        pwd_status=PWDStatus.PWD,
        civil_status=CivilStatusCategory.SOLO_PARENT,
        four_ps_status=FourPsStatus.BENEFICIARY,
        indigenous_peoples_status=IndigenousPeoplesStatus.MEMBER,
        mother_life_status=ParentLifeStatus.DECEASED,
        father_life_status=ParentLifeStatus.DECEASED,
    )

    response = auth_client(head).get(f"/api/v1/student-support/students/{student.pk}/context")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["inventory_status"] == "SUBMITTED"
    assert [item["code"] for item in body["indicators"]] == [
        "PWD",
        "SOLO_PARENT",
        "FOUR_PS_BENEFICIARY",
        "INDIGENOUS_PEOPLES_MEMBER",
        "MOTHER_DECEASED",
        "FATHER_DECEASED",
    ]


@pytest.mark.django_db
def test_ordinary_counselor_scope_is_current_affiliation_and_responsibility_only():
    sync_policy()
    counselor = make_user("support-scope-counselor@example.edu", "COUNSELOR")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, in_college, in_program = make_org("IN")
    _, out_college, out_program = make_org("OUT")
    in_student = make_user("support-in-scope@example.edu")
    out_student = make_user("support-out-scope@example.edu")
    affiliate(in_student, in_college, counselor=counselor)
    affiliate(out_student, out_college)
    make_inventory(
        student=in_student,
        year=year,
        program=in_program,
        suffix="in-scope",
        four_ps_status=FourPsStatus.BENEFICIARY,
    )
    make_inventory(
        student=out_student,
        year=year,
        program=out_program,
        suffix="out-scope",
        four_ps_status=FourPsStatus.BENEFICIARY,
    )
    client = auth_client(counselor)

    allowed = client.get(f"/api/v1/student-support/students/{in_student.pk}/context")
    concealed = client.get(f"/api/v1/student-support/students/{out_student.pk}/context")

    assert allowed.status_code == 200
    assert concealed.status_code == 404
    assert str(out_student.pk) not in concealed.content.decode()


@pytest.mark.django_db
def test_counselor_without_responsibility_and_inactive_org_get_no_support_data():
    sync_policy()
    counselor = make_user("support-no-scope@example.edu", "COUNSELOR")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    campus, college, program = make_org("STALE")
    student = make_user("support-stale-student@example.edu")
    affiliate(student, college)
    make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="stale",
        pwd_status=PWDStatus.PWD,
    )
    client = auth_client(counselor)

    assert client.get(f"/api/v1/student-support/students/{student.pk}/context").status_code == 404

    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    campus.is_active = False
    campus.save(update_fields=["is_active", "updated_at"])
    assert client.get(f"/api/v1/student-support/students/{student.pk}/context").status_code == 404


@pytest.mark.django_db
def test_missing_draft_and_historical_inventory_never_expose_positive_current_indicators():
    sync_policy()
    counselor = make_user("support-current-only@example.edu", "COUNSELOR")
    current = AcademicYear.objects.create(label="2026-2027", is_current=True)
    historical = AcademicYear.objects.create(label="2025-2026")
    _, college, program = make_org("CURRENT")
    missing = make_user("support-missing@example.edu")
    draft = make_user("support-draft@example.edu")
    historical_only = make_user("support-historical@example.edu")
    for student in (missing, draft, historical_only):
        affiliate(student, college)
    CounselorResponsibility.objects.create(college=college, counselor=counselor)

    make_inventory(
        student=draft,
        year=current,
        program=program,
        suffix="draft",
        submitted=False,
        pwd_status=PWDStatus.PWD,
        four_ps_status=FourPsStatus.BENEFICIARY,
    )
    make_inventory(
        student=historical_only,
        year=historical,
        program=program,
        suffix="historical",
        pwd_status=PWDStatus.PWD,
        four_ps_status=FourPsStatus.BENEFICIARY,
    )

    client = auth_client(counselor)
    expected = {
        missing.pk: "MISSING",
        draft.pk: "DRAFT",
        historical_only.pk: "MISSING",
    }
    for student_id, status in expected.items():
        response = client.get(f"/api/v1/student-support/students/{student_id}/context")
        assert response.status_code == 200
        body = response.json()
        assert body["inventory_status"] == status
        assert body["available"] is False
        assert body["indicators"] == []


@pytest.mark.django_db
def test_no_current_academic_year_is_safe_configuration_error():
    sync_policy()
    counselor = make_user("support-no-year-counselor@example.edu", "COUNSELOR")
    _, college, _ = make_org("NOYEAR")
    student = make_user("support-no-year-student@example.edu")
    affiliate(student, college, counselor=counselor)

    response = auth_client(counselor).get(f"/api/v1/student-support/students/{student.pk}/context")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "current_academic_year_not_configured"


@pytest.mark.django_db
def test_negative_and_unknown_states_create_no_positive_support_badges():
    sync_policy()
    counselor = make_user("support-negative-counselor@example.edu", "COUNSELOR")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, college, program = make_org("NEG")
    student = make_user("support-negative@example.edu")
    affiliate(student, college, counselor=counselor)
    make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="negative",
        pwd_status=PWDStatus.NON_PWD,
        civil_status=CivilStatusCategory.MARRIED,
        four_ps_status=FourPsStatus.NOT_BENEFICIARY,
        indigenous_peoples_status=IndigenousPeoplesStatus.NOT_MEMBER,
        mother_life_status=ParentLifeStatus.LIVING,
        father_life_status=ParentLifeStatus.NOT_SPECIFIED,
    )

    response = auth_client(counselor).get(f"/api/v1/student-support/students/{student.pk}/context")
    assert response.status_code == 200
    assert response.json()["indicators"] == []


@pytest.mark.django_db
def test_support_context_is_privacy_minimized_and_has_no_scores_or_narratives():
    sync_policy()
    counselor = make_user("support-private-counselor@example.edu", "COUNSELOR")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, college, program = make_org("PRIVATE")
    student = make_user("support-private@example.edu")
    affiliate(student, college, counselor=counselor)
    item = make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="private",
        pwd_status=PWDStatus.PWD,
        four_ps_status=FourPsStatus.BENEFICIARY,
    )
    item.physical_disadvantage = "SENTINEL PRIVATE PHYSICAL NARRATIVE"
    item.current_concerns = "SENTINEL PRIVATE COUNSELING CONCERN"
    item.save(update_fields=["physical_disadvantage", "current_concerns", "updated_at"])

    response = auth_client(counselor).get(f"/api/v1/student-support/students/{student.pk}/context")
    serialized = response.content.decode()

    assert response.status_code == 200
    assert "SENTINEL" not in serialized
    for forbidden in (
        "physical_disadvantage",
        "four_ps_status",
        "indigenous_peoples_status",
        "mother_life_status",
        "father_life_status",
        "risk_score",
        "vulnerability_score",
        "priority_score",
        "support_score",
        "high_risk",
        "low_risk",
    ):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_support_profile_is_nested_in_inventory_and_family_rows_have_no_life_status():
    sync_policy()
    student = make_user("support-inventory-student@example.edu")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, _, program = make_org("API")
    item = make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="api",
        submitted=False,
    )
    client = auth_client(student)

    payload = minimum_normalized_inventory_values(program_id=program.pk)
    payload["pwd_status"] = "PWD"
    payload["physical_disadvantage"] = "Mobility limitation"
    payload["support_profile"] = {
        "four_ps_status": "BENEFICIARY",
        "indigenous_peoples_status": "MEMBER",
        "mother_life_status": "DECEASED",
        "father_life_status": "LIVING",
    }
    response = client.put(
        "/api/v1/inventory/me/current",
        data=json.dumps(payload, default=str),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.get("/api/v1/auth/csrf").json()["csrf_token"],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pwd_status"] == "PWD"
    assert "physical_disadvantage_status" not in body
    assert body["support_profile"] == payload["support_profile"]
    assert all("life_status" not in row for row in body["family_members"])
    item.refresh_from_db()
    assert item.support_profile.four_ps_status == FourPsStatus.BENEFICIARY


@pytest.mark.django_db
def test_support_profile_draft_fields_may_be_null_but_submission_requires_explicit_values():
    sync_policy()
    student = make_user("support-submit-student@example.edu")
    AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, _, program = make_org("SUBMIT")
    make_inventory(
        student=student,
        year=AcademicYear.objects.get(is_current=True),
        program=program,
        suffix="submit",
        submitted=False,
        four_ps_status=None,
        indigenous_peoples_status=None,
        mother_life_status=None,
        father_life_status=None,
    )

    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["support_profile"] = {
        "four_ps_status": None,
        "indigenous_peoples_status": None,
        "mother_life_status": None,
        "father_life_status": None,
    }
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="Student Support fields"):
        submit_current_inventory(
            student=student,
            context=AuditContext.user(student),
        )

    values["support_profile"] = {
        "four_ps_status": "NOT_SPECIFIED",
        "indigenous_peoples_status": "NOT_SPECIFIED",
        "mother_life_status": "NOT_SPECIFIED",
        "father_life_status": "NOT_SPECIFIED",
    }
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(
        student=student,
        context=AuditContext.user(student),
    )
    assert submitted.submitted_at is not None
    assert submitted.support_profile.four_ps_status == FourPsStatus.NOT_SPECIFIED


@pytest.mark.django_db
def test_submitted_historical_null_support_profile_remains_readable_and_immutable():
    sync_policy()
    student = make_user("support-legacy-history@example.edu")
    historical = AcademicYear.objects.create(label="2025-2026")
    current = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, _, program = make_org("LEGACY")
    old = make_inventory(
        student=student,
        year=historical,
        program=program,
        suffix="legacy-history",
        submitted=True,
        pwd_status=None,
        four_ps_status=None,
        indigenous_peoples_status=None,
        mother_life_status=None,
        father_life_status=None,
    )

    response = auth_client(student).get(f"/api/v1/inventory/me/{old.pk}")
    assert response.status_code == 200
    assert response.json()["support_profile"]["four_ps_status"] is None
    assert response.json()["pwd_status"] is None

    # A current-year draft can change without mutating the historical snapshot.
    current_item = make_inventory(
        student=student,
        year=current,
        program=program,
        suffix="current-history",
        submitted=False,
    )
    replace_current_inventory(student=student, values={"nickname": "Current only"})
    old.refresh_from_db()
    current_item.refresh_from_db()
    assert old.nickname == ""
    assert current_item.nickname == "Current only"


@pytest.mark.django_db
def test_support_profile_failure_rolls_back_inventory_root_and_children(monkeypatch):
    sync_policy()
    student = make_user("support-rollback@example.edu")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, _, program = make_org("ROLLBACK")
    make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="rollback",
        submitted=False,
    )

    def fail_support(*_args, **_kwargs):
        raise RuntimeError("synthetic support persistence failure")

    monkeypatch.setattr(
        "compass.inventory.services._apply_support_profile",
        fail_support,
    )
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["nickname"] = "Must Roll Back"
    values["family_members"][0]["name"] = "Must Roll Back Parent"

    with pytest.raises(RuntimeError, match="synthetic support persistence failure"):
        replace_current_inventory(student=student, values=values)

    item = StudentInventory.objects.get(student=student, academic_year=year)
    assert item.nickname == ""
    assert not item.family_members.filter(name="Must Roll Back Parent").exists()


@pytest.mark.django_db
def test_inventory_audit_metadata_never_contains_support_or_pwd_values():
    sync_policy()
    student = make_user("support-audit@example.edu")
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    _, _, program = make_org("AUDIT")
    make_inventory(
        student=student,
        year=year,
        program=program,
        suffix="audit",
        submitted=False,
    )
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["pwd_status"] = "PWD"
    values["physical_disadvantage"] = "SENTINEL PWD DETAIL"
    values["support_profile"] = {
        "four_ps_status": "BENEFICIARY",
        "indigenous_peoples_status": "MEMBER",
        "mother_life_status": "DECEASED",
        "father_life_status": "DECEASED",
    }
    replace_current_inventory(student=student, values=values)
    submit_current_inventory(student=student, context=AuditContext.user(student))

    event = AuditEvent.objects.get(action="inventory.submitted")
    serialized = json.dumps(event.metadata, default=str)
    for forbidden in (
        "PWD",
        "SENTINEL PWD DETAIL",
        "BENEFICIARY",
        "MEMBER",
        "DECEASED",
        "four_ps",
        "indigenous",
        "life_status",
    ):
        assert forbidden not in serialized
