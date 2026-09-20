from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.authentication.sessions import create_auth_session
from compass.institutional_forms.models import FormFamily, FormRevision, FormRevisionStatus
from compass.inventory.models import (
    AnnualIncomeStatus,
    CivilStatusCategory,
    CurrentReligionCategory,
    FamilyMemberKind,
    GeographicLocationKind,
    InventoryFamilyMember,
    InventoryGeographicLocation,
    LivingArrangement,
    OccupationCategory,
    ParentStatusCategory,
    PWDStatus,
    Sex,
    StudentInventory,
)
from compass.organization.models import (
    AcademicYear,
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from compass.reports.services import calculate_percentage, year_level_label
from compass.student_support.models import ParentLifeStatus, StudentSupportProfile


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    lifecycle: str | None = StudentLifecycleStatus.CURRENT,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Synthetic",
        last_name="Student",
    )
    if role == "STUDENT":
        user.student_lifecycle_status = lifecycle
        user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def make_head(email: str = "head-reports@example.edu") -> User:
    user = make_user(email, role="COUNSELOR", lifecycle=None)
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def make_revision(suffix: str) -> FormRevision:
    family = FormFamily.objects.create(key=f"inventory-{suffix}", title="Synthetic Inventory")
    return FormRevision.objects.create(
        family=family,
        official_code=f"TEST-{suffix}",
        official_revision="0",
        internal_schema_version=1,
        status=FormRevisionStatus.ACTIVE,
    )


def make_organization(suffix: str) -> tuple[Campus, College, Program]:
    campus = Campus.objects.create(code=f"C-{suffix}", name=f"Campus {suffix}")
    college = College.objects.create(
        campus=campus,
        code=f"COL-{suffix}",
        name=f"College {suffix}",
    )
    program = Program.objects.create(
        college=college,
        code=f"P-{suffix}",
        name=f"Program {suffix}",
    )
    return campus, college, program


def submitted_at(year: int = 2026, month: int = 8, day: int = 30):
    return timezone.make_aware(datetime(year, month, day, 12, 0, 0))


def make_inventory(
    *,
    student: User,
    academic_year: AcademicYear,
    revision: FormRevision,
    program: Program | None,
    year_level: int | None = 1,
    submitted: bool = True,
    submitted_time=None,
    sex: str = Sex.MALE,
    date_of_birth=None,
    civil_status_category: str | None = CivilStatusCategory.SINGLE,
    religion: str | None = CurrentReligionCategory.ROMAN_CATHOLIC,
    physical: str | None = PWDStatus.NON_PWD,
    parent_status: str | None = ParentStatusCategory.MARRIED,
    living: str = LivingArrangement.OWN_HOUSE,
    with_parents: bool = True,
    with_location: bool = True,
) -> StudentInventory:
    item = StudentInventory.objects.create(
        student=student,
        academic_year=academic_year,
        form_revision=revision,
        program=program,
        year_level=year_level,
        submitted_at=(submitted_time or submitted_at()) if submitted else None,
        full_name_snapshot="Private Synthetic Name",
        student_number="PRIVATE-123",
        email_address="private@example.edu",
        contact_number="09123456789",
        current_address="Private full address",
        sex=sex,
        date_of_birth=date_of_birth,
        civil_status_category=civil_status_category,
        current_religion_category=religion,
        pwd_status=physical,
        physical_disadvantage="Private medical narrative",
        parent_status_category=parent_status,
        living_arrangement=living,
        current_concerns="Private concern narrative",
        current_fears="Private fear narrative",
    )
    if with_parents:
        InventoryFamilyMember.objects.create(
            inventory=item,
            kind=FamilyMemberKind.FATHER,
            name="Private Father",
            occupation="Private occupation narrative",
            occupation_category=OccupationCategory.FARMER,
            annual_income_status=AnnualIncomeStatus.NONE,
            annual_income_previous_year=Decimal("0"),
        )
        InventoryFamilyMember.objects.create(
            inventory=item,
            kind=FamilyMemberKind.MOTHER,
            name="Private Mother",
            occupation="Private occupation narrative",
            occupation_category=OccupationCategory.GOVERNMENT_EMPLOYEE,
            annual_income_status=AnnualIncomeStatus.NONE,
            annual_income_previous_year=Decimal("0"),
        )
    StudentSupportProfile.objects.create(
        inventory=item,
        mother_life_status=ParentLifeStatus.LIVING if with_parents else None,
        father_life_status=ParentLifeStatus.LIVING if with_parents else None,
    )
    if with_location:
        InventoryGeographicLocation.objects.create(
            inventory=item,
            kind=GeographicLocationKind.CURRENT,
            region_psgc_code="0500000000",
            region_name_snapshot="Bicol Region",
            province_psgc_code="0517000000",
            province_name_snapshot="Synthetic Province",
            city_municipality_psgc_code="0517010000",
            city_municipality_name_snapshot="Synthetic City",
        )
    return item


def report_row(section: dict[str, object], key: str) -> dict[str, object]:
    return next(item for item in section["rows"] if item["key"] == key)


@pytest.mark.django_db
def test_reports_view_is_counselor_baseline_but_does_not_fabricate_scope():
    sync_policy()
    head = make_head()
    counselor = make_user("counselor-reports@example.edu", role="COUNSELOR", lifecycle=None)
    staff = make_user("staff-reports@example.edu", role="GUIDANCE_SERVICES_STAFF", lifecycle=None)
    student = make_user("student-reports@example.edu")
    admin = make_user("admin-reports@example.edu", role="IT_ADMIN", lifecycle=None)

    assert head.has_capability("reports.view")
    assert counselor.has_capability("reports.view")
    for user in (staff, student, admin):
        assert not user.has_capability("reports.view")

    set_user_capability_override(
        user=admin,
        capability=Capability.objects.get(code="reports.view"),
        effect="GRANT",
        reason="Synthetic approved exception",
    )
    assert admin.has_capability("reports.view")
    assert auth_client(admin).get("/api/v1/reports/student-profile").status_code == 403


@pytest.mark.django_db
def test_student_profile_endpoint_authorization_and_unauthenticated_boundary():
    sync_policy()
    AcademicYear.objects.create(label="2026-2027", is_current=True)
    head = make_head()
    denied = [
        make_user("ordinary@example.edu", role="COUNSELOR", lifecycle=None),
        make_user("staff@example.edu", role="GUIDANCE_SERVICES_STAFF", lifecycle=None),
        make_user("student@example.edu"),
        make_user("it@example.edu", role="IT_ADMIN", lifecycle=None),
    ]

    assert auth_client(head).get("/api/v1/reports/student-profile").status_code == 200
    for user in denied:
        assert auth_client(user).get("/api/v1/reports/student-profile").status_code == 403
    assert Client().get("/api/v1/reports/student-profile").status_code == 401


@pytest.mark.django_db
def test_student_profile_enforces_current_counselor_college_scope_across_filters_and_history():
    sync_policy()
    current_year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    historical_year = AcademicYear.objects.create(label="2025-2026", is_current=False)
    revision = make_revision("counselor-scope")

    campus_a = Campus.objects.create(code="C-A", name="Campus A")
    college_a1 = College.objects.create(campus=campus_a, code="A1", name="College A1")
    college_a2 = College.objects.create(campus=campus_a, code="A2", name="College A2")
    program_a1 = Program.objects.create(college=college_a1, code="P-A1", name="Program A1")
    program_a2 = Program.objects.create(college=college_a2, code="P-A2", name="Program A2")

    campus_b = Campus.objects.create(code="C-B", name="Campus B")
    college_b1 = College.objects.create(campus=campus_b, code="B1", name="College B1")
    program_b1 = Program.objects.create(college=college_b1, code="P-B1", name="Program B1")

    counselor_a = make_user("scope-a@example.edu", role="COUNSELOR", lifecycle=None)
    counselor_b = make_user("scope-b@example.edu", role="COUNSELOR", lifecycle=None)
    zero_scope = make_user("scope-none@example.edu", role="COUNSELOR", lifecycle=None)
    head = make_head("scope-head@example.edu")
    CounselorResponsibility.objects.create(college=college_a1, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=college_b1, counselor=counselor_b)

    student_a1 = make_user("scope-student-a1@example.edu")
    student_a2 = make_user("scope-student-a2@example.edu")
    student_b1 = make_user("scope-student-b1@example.edu")
    StudentAffiliation.objects.create(student=student_a1, college=college_a1)
    StudentAffiliation.objects.create(student=student_a2, college=college_a2)
    StudentAffiliation.objects.create(student=student_b1, college=college_b1)

    for student, program in (
        (student_a1, program_a1),
        (student_a2, program_a2),
        (student_b1, program_b1),
    ):
        make_inventory(
            student=student,
            academic_year=current_year,
            revision=revision,
            program=program,
        )
        make_inventory(
            student=student,
            academic_year=historical_year,
            revision=revision,
            program=program,
            submitted_time=submitted_at(2025, 8, 30),
        )

    client = auth_client(counselor_a)
    unfiltered = client.get("/api/v1/reports/student-profile")
    assert unfiltered.status_code == 200
    unfiltered_body = unfiltered.json()
    assert unfiltered_body["report_context"]["submitted_inventory_count"] == 1
    assert [column["college"]["code"] for column in unfiltered_body["program_columns"]] == ["A1"]
    assert unfiltered_body["inventory_coverage"]["eligible_student_count"] == 1
    assert "Counselor-assigned Colleges" in unfiltered_body["methodology"]["profile_population_note"]
    assert "A1" in unfiltered_body["methodology"]["profile_population_note"]

    assert client.get(
        "/api/v1/reports/student-profile",
        {"college_id": college_a1.pk},
    ).status_code == 200
    assert client.get(
        "/api/v1/reports/student-profile",
        {"program_id": program_a1.pk},
    ).status_code == 200

    campus_a_response = client.get(
        "/api/v1/reports/student-profile",
        {"campus_id": campus_a.pk},
    )
    assert campus_a_response.status_code == 200
    assert campus_a_response.json()["report_context"]["submitted_inventory_count"] == 1

    for params in (
        {"college_id": college_a2.pk},
        {"college_id": college_b1.pk},
        {"program_id": program_a2.pk},
        {"program_id": program_b1.pk},
        {"campus_id": campus_b.pk},
    ):
        response = client.get("/api/v1/reports/student-profile", params)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    historical = client.get(
        "/api/v1/reports/student-profile",
        {"academic_year_id": historical_year.pk},
    )
    assert historical.status_code == 200
    assert historical.json()["report_context"]["submitted_inventory_count"] == 1
    assert historical.json()["inventory_coverage"]["submitted_count"] == 1

    head_report = auth_client(head).get("/api/v1/reports/student-profile")
    assert head_report.status_code == 200
    assert head_report.json()["report_context"]["submitted_inventory_count"] == 3

    assert auth_client(zero_scope).get("/api/v1/reports/student-profile").status_code == 403


@pytest.mark.parametrize(
    ("value", "label"),
    [(1, "1st Year"), (2, "2nd Year"), (3, "3rd Year"), (4, "4th Year"), (5, "5th Year")],
)
def test_year_level_labels_are_numeric_ordinals(value, label):
    assert year_level_label(value) == label
    assert all(term not in label for term in ("Freshman", "Sophomore", "Junior", "Senior"))


def test_percentage_rounding_is_half_up_and_zero_safe():
    assert calculate_percentage(71, 217) == Decimal("32.72")
    assert calculate_percentage(39, 217) == Decimal("17.97")
    assert calculate_percentage(0, 0) == Decimal("0.00")
    assert calculate_percentage(7, 7) == Decimal("100.00")
