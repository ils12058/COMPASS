from __future__ import annotations

import json
from datetime import datetime

import pytest

from compass.accounts.models import StudentLifecycleStatus
from compass.inventory.models import (
    CivilStatusCategory,
    CurrentReligionCategory,
    ParentStatusCategory,
    PWDStatus,
    Sex,
)
from compass.organization.models import AcademicYear
from compass.student_support.models import ParentLifeStatus
from compass.reports.services import (
    LEGACY_KEY,
    LEGACY_LABEL,
    InvalidReportFilter,
    build_student_profiling_report,
)
from tests.test_student_profiling_reports import (
    make_inventory,
    make_organization,
    make_revision,
    make_user,
    report_row,
    submitted_at,
    sync_policy,
)


@pytest.mark.django_db
def test_current_and_historical_academic_year_selection():
    sync_policy()
    current = AcademicYear.objects.create(label="2026-2027", is_current=True)
    historical = AcademicYear.objects.create(label="2025-2026")
    revision = make_revision("ay")
    _, _, program = make_organization("AY")
    student = make_user("ay-profile@example.edu")
    make_inventory(student=student, academic_year=historical, revision=revision, program=program)

    current_report = build_student_profiling_report()
    historical_report = build_student_profiling_report(academic_year_id=historical.pk)

    assert current_report["report_context"]["academic_year"]["id"] == current.pk
    assert current_report["report_context"]["submitted_inventory_count"] == 0
    assert historical_report["report_context"]["submitted_inventory_count"] == 1
    assert historical_report["inventory_coverage"]["mode"] == "HISTORICAL_LIMITED"
    assert historical_report["inventory_coverage"]["missing_count"] is None


@pytest.mark.django_db
def test_filters_use_inventory_program_hierarchy_and_reject_contradictions():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("filters")
    campus_a, college_a, program_a = make_organization("A")
    campus_b, college_b, program_b = make_organization("B")
    student_a = make_user("filter-a@example.edu")
    student_b = make_user("filter-b@example.edu")
    make_inventory(student=student_a, academic_year=year, revision=revision, program=program_a)
    make_inventory(
        student=student_b,
        academic_year=year,
        revision=revision,
        program=program_b,
        year_level=2,
    )

    assert (
        build_student_profiling_report(campus_id=campus_a.pk)["report_context"][
            "submitted_inventory_count"
        ]
        == 1
    )
    assert (
        build_student_profiling_report(college_id=college_b.pk)["report_context"][
            "submitted_inventory_count"
        ]
        == 1
    )
    assert (
        build_student_profiling_report(program_id=program_b.pk)["report_context"][
            "submitted_inventory_count"
        ]
        == 1
    )
    assert (
        build_student_profiling_report(year_level=2)["report_context"]["submitted_inventory_count"]
        == 1
    )

    with pytest.raises(InvalidReportFilter, match="College"):
        build_student_profiling_report(campus_id=campus_a.pk, college_id=college_b.pk)
    with pytest.raises(InvalidReportFilter, match="Program"):
        build_student_profiling_report(college_id=college_a.pk, program_id=program_b.pk)
    with pytest.raises(InvalidReportFilter, match="Program"):
        build_student_profiling_report(campus_id=campus_a.pk, program_id=program_b.pk)


@pytest.mark.django_db
def test_inactive_historical_program_remains_reportable_and_empty_filter_is_valid():
    sync_policy()
    year = AcademicYear.objects.create(label="2025-2026")
    revision = make_revision("inactive")
    _, _, program = make_organization("OLD")
    student = make_user("old-program@example.edu")
    make_inventory(student=student, academic_year=year, revision=revision, program=program)
    program.is_active = False
    program.save(update_fields=["is_active", "updated_at"])

    report = build_student_profiling_report(academic_year_id=year.pk, program_id=program.pk)
    assert report["report_context"]["submitted_inventory_count"] == 1

    _, _, empty_program = make_organization("EMPTY")
    empty = build_student_profiling_report(
        academic_year_id=year.pk,
        program_id=empty_program.pk,
    )
    assert empty["report_context"]["submitted_inventory_count"] == 0
    assert empty["program_columns"] == []
    assert empty["sections"]["age"]["rows"] == []


@pytest.mark.django_db
def test_profile_population_is_submitted_snapshot_not_current_lifecycle():
    sync_policy()
    historical = AcademicYear.objects.create(label="2025-2026")
    revision = make_revision("population")
    _, _, program = make_organization("POP")
    graduated = make_user("graduated-profile@example.edu")
    former = make_user("former-profile@example.edu")
    draft_student = make_user("draft-profile@example.edu")
    make_inventory(student=graduated, academic_year=historical, revision=revision, program=program)
    make_inventory(student=former, academic_year=historical, revision=revision, program=program)
    make_inventory(
        student=draft_student,
        academic_year=historical,
        revision=revision,
        program=program,
        submitted=False,
    )
    make_user("missing-profile@example.edu")
    graduated.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    graduated.save(update_fields=["student_lifecycle_status", "updated_at"])
    former.student_lifecycle_status = StudentLifecycleStatus.FORMER
    former.save(update_fields=["student_lifecycle_status", "updated_at"])

    report = build_student_profiling_report(academic_year_id=historical.pk)
    assert report["report_context"]["submitted_inventory_count"] == 2
    assert report_row(report["sections"]["sex"], Sex.MALE)["total_count"] == 2
    assert report["inventory_coverage"]["submitted_count"] == 2
    assert report["inventory_coverage"]["draft_count"] == 1
    assert report["inventory_coverage"]["missing_count"] is None


@pytest.mark.django_db
def test_dynamic_program_columns_include_legacy_and_no_hardcoded_sample_programs():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("program-columns")
    _, _, alpha = make_organization("ALPHA")
    _, _, beta = make_organization("BETA")
    make_inventory(
        student=make_user("alpha@example.edu"),
        academic_year=year,
        revision=revision,
        program=alpha,
    )
    make_inventory(
        student=make_user("beta@example.edu"),
        academic_year=year,
        revision=revision,
        program=beta,
        sex=Sex.FEMALE,
    )
    make_inventory(
        student=make_user("legacy-program@example.edu"),
        academic_year=year,
        revision=revision,
        program=None,
        year_level=None,
    )

    report = build_student_profiling_report()
    assert [column["name"] for column in report["program_columns"]] == [
        alpha.name,
        beta.name,
        LEGACY_LABEL,
    ]
    for key in (Sex.MALE, Sex.FEMALE):
        item = report_row(report["sections"]["sex"], key)
        assert sum(count["count"] for count in item["program_counts"]) == item["total_count"]
    serialized = json.dumps(report, default=str)
    assert "BSIT" not in serialized
    assert "BSIS" not in serialized


@pytest.mark.django_db
def test_exact_age_uses_submission_date_and_no_twenty_plus_bucket():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("age")
    _, _, program = make_organization("AGE")
    birthday = datetime(2005, 8, 30).date()
    make_inventory(
        student=make_user("age-before@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        date_of_birth=birthday,
        submitted_time=submitted_at(2026, 8, 29),
    )
    make_inventory(
        student=make_user("age-on@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        date_of_birth=birthday,
        submitted_time=submitted_at(2026, 8, 30),
    )
    make_inventory(
        student=make_user("age-unknown@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        date_of_birth=None,
    )

    age_rows = build_student_profiling_report()["sections"]["age"]["rows"]
    assert [(item["key"], item["total_count"]) for item in age_rows] == [
        ("20", 1),
        ("21", 1),
        (LEGACY_KEY, 1),
    ]
    assert all("Above" not in item["label"] for item in age_rows)


@pytest.mark.django_db
def test_not_specified_and_not_recorded_legacy_are_distinct():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("legacy-categories")
    _, _, program = make_organization("LEG")
    make_inventory(
        student=make_user("explicit@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.NOT_SPECIFIED,
        religion=CurrentReligionCategory.NOT_SPECIFIED,
        physical=PWDStatus.NOT_SPECIFIED,
        parent_status=ParentStatusCategory.NOT_SPECIFIED,
    )
    make_inventory(
        student=make_user("legacy@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=None,
        religion=None,
        physical=None,
        parent_status=None,
        with_parents=False,
        with_location=False,
    )

    report = build_student_profiling_report()
    for section_name in (
        "civil_status",
        "current_religion",
        "physical_disadvantage",
        "parent_family_status",
    ):
        section = report["sections"][section_name]
        assert report_row(section, "NOT_SPECIFIED")["total_count"] == 1
        assert report_row(section, LEGACY_KEY)["total_count"] == 1
    assert "Nort specified" not in json.dumps(report, default=str)


@pytest.mark.django_db
def test_parent_life_sections_have_independent_student_denominators():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("parent-life")
    _, _, program = make_organization("LIFE")
    items = [
        make_inventory(
            student=make_user(f"life-{index}@example.edu"),
            academic_year=year,
            revision=revision,
            program=program,
        )
        for index in range(3)
    ]
    items[1].support_profile.mother_life_status = ParentLifeStatus.DECEASED
    items[1].support_profile.father_life_status = ParentLifeStatus.DECEASED
    items[1].support_profile.save(
        update_fields=["mother_life_status", "father_life_status", "updated_at"]
    )
    items[2].support_profile.father_life_status = ParentLifeStatus.NOT_SPECIFIED
    items[2].support_profile.save(update_fields=["father_life_status", "updated_at"])

    report = build_student_profiling_report()
    mother = report["sections"]["mother_life_status"]
    father = report["sections"]["father_life_status"]
    assert mother["denominator"] == father["denominator"] == 3
    assert report_row(mother, ParentLifeStatus.LIVING)["total_count"] == 2
    assert report_row(mother, ParentLifeStatus.DECEASED)["total_count"] == 1
    assert report_row(father, ParentLifeStatus.LIVING)["total_count"] == 1
    assert report_row(father, ParentLifeStatus.DECEASED)["total_count"] == 1
    assert report_row(father, ParentLifeStatus.NOT_SPECIFIED)["total_count"] == 1
