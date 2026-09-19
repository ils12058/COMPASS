from __future__ import annotations

import json
from decimal import Decimal

import pytest

from compass.accounts.models import StudentLifecycleStatus
from compass.inventory.models import (
    AnnualIncomeStatus,
    FamilyMemberKind,
    GeographicLocationKind,
    InventoryFamilyMember,
    InventoryGeographicLocation,
)
from compass.organization.models import AcademicYear, StudentAffiliation
from compass.reports.services import LEGACY_KEY, build_student_profiling_report
from tests.test_student_profiling_reports import (
    auth_client,
    make_head,
    make_inventory,
    make_organization,
    make_revision,
    make_user,
    report_row,
    sync_policy,
)


@pytest.mark.django_db
def test_geography_uses_city_psgc_identity_and_not_province_or_address_parsing():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("geo-report")
    _, _, program = make_organization("GEO")
    first_item = make_inventory(
        student=make_user("geo-one@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
    )
    second_item = make_inventory(
        student=make_user("geo-two@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        with_location=False,
    )
    first_geo = first_item.geographic_locations.get(kind=GeographicLocationKind.CURRENT)
    first_geo.city_municipality_psgc_code = "0517240000"
    first_geo.city_municipality_name_snapshot = "Naga City"
    first_geo.province_psgc_code = "0517000000"
    first_geo.province_name_snapshot = "Camarines Sur"
    first_geo.save()
    InventoryGeographicLocation.objects.create(
        inventory=second_item,
        kind=GeographicLocationKind.CURRENT,
        not_specified=True,
    )

    section = build_student_profiling_report()["sections"]["city_municipality"]
    naga = next(
        item for item in section["rows"] if item["city_municipality_psgc_code"] == "0517240000"
    )
    assert naga["label"] == "Naga City"
    assert naga["province_name"] == "Camarines Sur"
    assert not any(item["label"] == "Camarines Sur" for item in section["rows"])
    assert report_row(section, "NOT_SPECIFIED")["total_count"] == 1


@pytest.mark.django_db
def test_parent_income_reuses_normalized_status_and_excludes_spouse():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("income-report")
    _, _, program = make_organization("INC")
    first_item = make_inventory(
        student=make_user("income-one@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
    )
    second_item = make_inventory(
        student=make_user("income-two@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
    )
    legacy_item = make_inventory(
        student=make_user("income-legacy@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
    )

    first_item.family_members.filter(kind=FamilyMemberKind.FATHER).update(
        annual_income_status=AnnualIncomeStatus.REPORTED,
        annual_income_previous_year=Decimal("100000"),
    )
    first_item.family_members.filter(kind=FamilyMemberKind.MOTHER).update(
        annual_income_status=AnnualIncomeStatus.NONE,
        annual_income_previous_year=Decimal("0"),
    )
    InventoryFamilyMember.objects.create(
        inventory=first_item,
        kind=FamilyMemberKind.SPOUSE,
        annual_income_status=AnnualIncomeStatus.REPORTED,
        annual_income_previous_year=Decimal("9999999"),
    )
    second_item.family_members.filter(kind=FamilyMemberKind.MOTHER).update(
        annual_income_status=AnnualIncomeStatus.NOT_SPECIFIED,
        annual_income_previous_year=None,
    )
    legacy_item.family_members.filter(kind=FamilyMemberKind.FATHER).update(
        annual_income_status=None,
        annual_income_previous_year=None,
    )

    section = build_student_profiling_report()["sections"]["parent_annual_income"]
    assert report_row(section, "POOR")["total_count"] == 1
    assert report_row(section, "NOT_SPECIFIED")["total_count"] == 1
    assert report_row(section, LEGACY_KEY)["total_count"] == 1
    assert sum(item["total_count"] for item in section["rows"]) == section["denominator"] == 3


@pytest.mark.django_db
def test_current_coverage_distinguishes_submitted_draft_missing_and_ignores_program_year():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("coverage")
    _, college, program = make_organization("COV")
    submitted_student = make_user("coverage-submitted@example.edu")
    draft_student = make_user("coverage-draft@example.edu")
    missing_student = make_user("coverage-missing@example.edu")
    inactive = make_user("coverage-inactive@example.edu")
    inactive.is_active = False
    inactive.save(update_fields=["is_active", "updated_at"])
    make_user("coverage-former@example.edu", lifecycle=StudentLifecycleStatus.FORMER)
    make_inventory(
        student=submitted_student,
        academic_year=year,
        revision=revision,
        program=program,
        year_level=2,
    )
    make_inventory(
        student=draft_student,
        academic_year=year,
        revision=revision,
        program=program,
        year_level=2,
        submitted=False,
    )
    for student in (submitted_student, draft_student, missing_student):
        StudentAffiliation.objects.create(student=student, college=college)

    report = build_student_profiling_report(program_id=program.pk, year_level=2)
    coverage = report["inventory_coverage"]
    assert coverage["mode"] == "CURRENT"
    assert coverage["eligible_student_count"] == 3
    assert coverage["submitted_count"] == 1
    assert coverage["draft_count"] == 1
    assert coverage["missing_count"] == 1
    assert set(coverage["ignored_filters"]) == {"program_id", "year_level"}
    assert "Program" in coverage["scope_note"]


@pytest.mark.django_db
def test_current_coverage_campus_college_scope_uses_guidance_affiliation_without_mutation():
    sync_policy()
    AcademicYear.objects.create(label="2026-2027", is_current=True)
    campus_a, college_a, _ = make_organization("SCOPE-A")
    _, college_b, _ = make_organization("SCOPE-B")
    first = make_user("scope-a@example.edu")
    second = make_user("scope-b@example.edu")
    StudentAffiliation.objects.create(student=first, college=college_a)
    StudentAffiliation.objects.create(student=second, college=college_b)

    report = build_student_profiling_report(campus_id=campus_a.pk, college_id=college_a.pk)
    coverage = report["inventory_coverage"]
    assert coverage["eligible_student_count"] == 1
    assert coverage["missing_count"] == 1
    assert {"campus_id", "college_id"} <= set(coverage["applied_filters"])
    first.refresh_from_db()
    assert first.organization_student_affiliation.college_id == college_a.pk


@pytest.mark.django_db
def test_historical_coverage_never_uses_today_current_students_as_missing_denominator():
    sync_policy()
    AcademicYear.objects.create(label="2026-2027", is_current=True)
    historical = AcademicYear.objects.create(label="2025-2026")
    revision = make_revision("historical-coverage")
    _, _, program = make_organization("HIST")
    student = make_user("historical-submitted@example.edu")
    make_inventory(student=student, academic_year=historical, revision=revision, program=program)
    for index in range(5):
        make_user(f"current-only-{index}@example.edu")

    coverage = build_student_profiling_report(academic_year_id=historical.pk)["inventory_coverage"]
    assert coverage["mode"] == "HISTORICAL_LIMITED"
    assert coverage["eligible_student_count"] is None
    assert coverage["missing_count"] is None
    assert coverage["submitted_count"] == 1
    assert "historical" in coverage["scope_note"].lower()


@pytest.mark.django_db
def test_aggregate_api_excludes_student_identity_and_private_narratives():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("privacy")
    _, _, program = make_organization("PRIV")
    student = make_user("secret-student@example.edu")
    item = make_inventory(
        student=student,
        academic_year=year,
        revision=revision,
        program=program,
    )
    head = make_head("head-privacy@example.edu")

    response = auth_client(head).get("/api/v1/reports/student-profile")
    assert response.status_code == 200
    payload = json.dumps(response.json())
    for forbidden in (
        str(student.pk),
        "PRIVATE-123",
        "Private Synthetic Name",
        "private@example.edu",
        "09123456789",
        "Private full address",
        "Private Father",
        "Private Mother",
        "Private occupation narrative",
        "Private medical narrative",
        "Private concern narrative",
        "Private fear narrative",
    ):
        assert forbidden not in payload
    assert str(item.program_id) in payload


@pytest.mark.django_db
def test_methodology_is_explicit_and_no_report_persistence_models_exist():
    sync_policy()
    AcademicYear.objects.create(label="2026-2027", is_current=True)
    report = build_student_profiling_report()
    assert "submitted Individual Inventories" in report["methodology"]["profile_population_note"]
    assert "Without Individual Inventory" in report["methodology"]["profile_population_note"]
    assert "Program" in report["methodology"]["coverage_note"]

    from django.apps import apps

    for name in ("Report", "ProfileReport", "ReportSnapshot", "ReportRow", "AnalyticsFact"):
        with pytest.raises(LookupError):
            apps.get_model("reports", name)
