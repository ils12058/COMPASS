from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

import compass.reports.services as profiling_report
from compass.accounts.models import StudentLifecycleStatus
from compass.inventory.models import (
    AnnualIncomeStatus,
    CivilStatusCategory,
    CurrentReligionCategory,
    FamilyMemberKind,
    ParentStatusCategory,
    PWDStatus,
    Sex,
)
from compass.organization.models import AcademicYear, Program
from compass.reports.services import (
    GLOBAL_REPORT_ACCESS_SCOPE,
    LEGACY_KEY,
    LEGACY_LABEL,
    InvalidReportFilter,
    build_student_profiling_report,
)
from compass.student_support.models import ParentLifeStatus
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
def test_profile_report_population_is_frozen_before_program_and_section_queries():
    sync_policy()
    year = AcademicYear.objects.create(label="2030-2031", is_current=True)
    revision = make_revision("snapshot")
    _, _, program = make_organization("SNAP")
    first_student = make_user("profile-snapshot-first@example.edu")
    make_inventory(
        student=first_student,
        academic_year=year,
        revision=revision,
        program=program,
        sex=Sex.MALE,
    )

    original = profiling_report._program_columns
    inserted = False
    captured_program_total = 0

    def insert_after_population_snapshot(queryset):
        nonlocal inserted, captured_program_total
        if not inserted:
            inserted = True
            late_student = make_user("profile-snapshot-late@example.edu")
            make_inventory(
                student=late_student,
                academic_year=year,
                revision=revision,
                program=program,
                sex=Sex.FEMALE,
            )
        result = original(queryset)
        captured_program_total = sum(result[1].values())
        return result

    with patch(
        "compass.reports.services._program_columns",
        side_effect=insert_after_population_snapshot,
    ):
        report = build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, academic_year_id=year.pk
        )

    assert report["report_context"]["submitted_inventory_count"] == 1
    assert captured_program_total == 1
    sex_section = report["sections"]["sex"]
    assert sex_section["denominator"] == 1
    assert report_row(sex_section, Sex.MALE)["total_count"] == 1
    assert report_row(sex_section, Sex.FEMALE)["total_count"] == 0


@pytest.mark.django_db
def test_current_and_historical_academic_year_selection():
    sync_policy()
    current = AcademicYear.objects.create(label="2026-2027", is_current=True)
    historical = AcademicYear.objects.create(label="2025-2026")
    revision = make_revision("ay")
    _, _, program = make_organization("AY")
    student = make_user("ay-profile@example.edu")
    make_inventory(student=student, academic_year=historical, revision=revision, program=program)

    current_report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    historical_report = build_student_profiling_report(
        access_scope=GLOBAL_REPORT_ACCESS_SCOPE, academic_year_id=historical.pk
    )

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
        build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, campus_id=campus_a.pk
        )["report_context"]["submitted_inventory_count"]
        == 1
    )
    assert (
        build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, college_id=college_b.pk
        )["report_context"]["submitted_inventory_count"]
        == 1
    )
    assert (
        build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, program_id=program_b.pk
        )["report_context"]["submitted_inventory_count"]
        == 1
    )
    assert (
        build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE, year_level=2)[
            "report_context"
        ]["submitted_inventory_count"]
        == 1
    )

    with pytest.raises(InvalidReportFilter, match="College"):
        build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, campus_id=campus_a.pk, college_id=college_b.pk
        )
    with pytest.raises(InvalidReportFilter, match="Program"):
        build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE,
            college_id=college_a.pk,
            program_id=program_b.pk,
        )
    with pytest.raises(InvalidReportFilter, match="Program"):
        build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, campus_id=campus_a.pk, program_id=program_b.pk
        )


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

    report = build_student_profiling_report(
        access_scope=GLOBAL_REPORT_ACCESS_SCOPE, academic_year_id=year.pk, program_id=program.pk
    )
    assert report["report_context"]["submitted_inventory_count"] == 1

    _, _, empty_program = make_organization("EMPTY")
    empty = build_student_profiling_report(
        access_scope=GLOBAL_REPORT_ACCESS_SCOPE,
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

    report = build_student_profiling_report(
        access_scope=GLOBAL_REPORT_ACCESS_SCOPE, academic_year_id=historical.pk
    )
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

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
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

    age_rows = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)["sections"][
        "age"
    ]["rows"]
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

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
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

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    mother = report["sections"]["mother_life_status"]
    father = report["sections"]["father_life_status"]
    assert mother["denominator"] == father["denominator"] == 3
    assert report_row(mother, ParentLifeStatus.LIVING)["total_count"] == 2
    assert report_row(mother, ParentLifeStatus.DECEASED)["total_count"] == 1
    assert report_row(father, ParentLifeStatus.LIVING)["total_count"] == 1
    assert report_row(father, ParentLifeStatus.DECEASED)["total_count"] == 1
    assert report_row(father, ParentLifeStatus.NOT_SPECIFIED)["total_count"] == 1


@pytest.mark.django_db
def test_small_student_profile_population_warns_without_suppressing_rows():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("small-population")
    _, _, program = make_organization("SMALL-POP")

    for index, sex in enumerate((Sex.MALE, Sex.FEMALE), start=1):
        make_inventory(
            student=make_user(f"small-population-{index}@example.edu"),
            academic_year=year,
            revision=revision,
            program=program,
            sex=sex,
        )

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    sex_section = report["sections"]["sex"]

    assert report["disclosure_warnings"] == [
        {
            "code": "SMALL_POPULATION",
            "message": (
                "This report includes results from a small population or category. "
                "Use and share these results carefully because some aggregate results "
                "may be easier to associate with individual respondents."
            ),
        }
    ]
    assert sex_section["denominator"] == 2
    assert report_row(sex_section, Sex.MALE)["total_count"] == 1
    assert report_row(sex_section, Sex.FEMALE)["total_count"] == 1


@pytest.mark.django_db
def test_student_profile_small_cell_warns_once_and_keeps_exact_count():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("small-cell")
    _, _, program = make_organization("SMALL-CELL")

    sexes = [Sex.MALE, Sex.MALE, Sex.MALE, Sex.MALE, Sex.FEMALE]
    for index, sex in enumerate(sexes, start=1):
        make_inventory(
            student=make_user(f"small-cell-{index}@example.edu"),
            academic_year=year,
            revision=revision,
            program=program,
            sex=sex,
        )

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    female = report_row(report["sections"]["sex"], Sex.FEMALE)

    assert [warning["code"] for warning in report["disclosure_warnings"]] == ["SMALL_CELL"]
    assert female["total_count"] == 1
    assert female["percentage"] == Decimal("20.00")


@pytest.mark.django_db
def test_empty_student_profile_has_no_disclosure_warning_and_null_percentages():
    sync_policy()
    AcademicYear.objects.create(label="2026-2027", is_current=True)

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)

    assert report["report_context"]["submitted_inventory_count"] == 0
    assert report["disclosure_warnings"] == []
    assert report_row(report["sections"]["sex"], Sex.MALE)["percentage"] is None


def assert_report_reconciles(report: dict[str, object]) -> None:
    """Every invariant the printed and exported representations rely on."""

    population = report["report_context"]["submitted_inventory_count"]
    columns = report["program_columns"]
    totals = {column["key"]: column["submitted_inventory_count"] for column in columns}
    assert sum(totals.values()) == population
    assert len(totals) == len(columns)
    for key, section in report["sections"].items():
        assert section["denominator"] == population, key
        assert sum(row["total_count"] for row in section["rows"]) == population, key
        program_sums = dict.fromkeys(totals, 0)
        for row in section["rows"]:
            counts = {item["program_key"]: item["count"] for item in row["program_counts"]}
            assert set(counts) == set(totals), key
            assert sum(counts.values()) == row["total_count"], (key, row["key"])
            assert row["percentage"] == profiling_report.calculate_percentage(
                row["total_count"], population
            )
            for program_key, count in counts.items():
                program_sums[program_key] += count
        assert program_sums == totals, key
    reconciliation = report["inventory_coverage"]["reconciliation"]
    assert reconciliation["profile_submitted_count"] == population
    assert (
        reconciliation["in_both_count"] + reconciliation["profile_only_count"]
        == reconciliation["profile_submitted_count"]
    )
    assert (
        reconciliation["in_both_count"] + reconciliation["coverage_only_count"]
        == reconciliation["coverage_submitted_count"]
        == report["inventory_coverage"]["submitted_count"]
    )


@pytest.mark.django_db
def test_every_section_reconciles_across_colleges_campuses_programs_and_legacy():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("reconcile-all")
    _, college_a, program_a1 = make_organization("REC-A")
    program_a2 = Program.objects.create(college=college_a, code="P-REC-A2", name="Program A2")
    program_a3 = Program.objects.create(
        college=college_a, code="P-REC-A3", name="Program A3", is_active=False
    )
    _, college_b, program_b = make_organization("REC-B")
    variations = [
        {"program": program_a1, "sex": Sex.MALE},
        {"program": program_a1, "sex": Sex.FEMALE, "civil_status_category": None},
        {"program": program_a2, "religion": CurrentReligionCategory.NOT_SPECIFIED},
        {"program": program_a2, "with_parents": False},
        {"program": program_a3, "with_location": False, "physical": PWDStatus.PWD},
        {"program": program_b, "parent_status": ParentStatusCategory.WIDOWED},
        {"program": program_b, "date_of_birth": datetime(2007, 1, 5).date()},
        {"program": None, "year_level": None, "with_parents": False, "with_location": False},
    ]
    for index, values in enumerate(variations):
        make_inventory(
            student=make_user(f"reconcile-all-{index}@example.edu"),
            academic_year=year,
            revision=revision,
            **values,
        )
    make_inventory(
        student=make_user("reconcile-all-draft@example.edu"),
        academic_year=year,
        revision=revision,
        program=program_a1,
        submitted=False,
    )

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    assert report["report_context"]["submitted_inventory_count"] == len(variations)
    assert_report_reconciles(report)
    by_key = {column["key"]: column for column in report["program_columns"]}
    assert by_key[f"program:{program_a3.pk}"]["submitted_inventory_count"] == 1
    assert by_key[profiling_report.LEGACY_PROGRAM_KEY]["submitted_inventory_count"] == 1

    for filters in (
        {"college_id": college_a.pk},
        {"college_id": college_b.pk},
        {"program_id": program_a3.pk},
        {"year_level": 1},
    ):
        filtered = build_student_profiling_report(
            access_scope=GLOBAL_REPORT_ACCESS_SCOPE, **filters
        )
        assert_report_reconciles(filtered)
        # College and Program filters never pull unclassified legacy Inventories into a College.
        assert all(not column["is_legacy"] for column in filtered["program_columns"])

    scoped = build_student_profiling_report(
        access_scope=profiling_report.ReportAccessScope(
            is_global=False, college_ids=(college_b.pk,)
        )
    )
    assert_report_reconciles(scoped)
    assert scoped["report_context"]["submitted_inventory_count"] == 2


@pytest.mark.django_db
def test_single_submitted_inventory_reconciles_and_zero_population_has_no_percentages():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("one-inventory")
    _, _, program = make_organization("ONE")

    empty = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    assert_report_reconciles(empty)
    assert all(
        row["percentage"] is None
        for section in empty["sections"].values()
        for row in section["rows"]
    )

    make_inventory(
        student=make_user("one-inventory@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
    )
    single = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    assert_report_reconciles(single)
    assert report_row(single["sections"]["sex"], Sex.MALE)["percentage"] == Decimal("100.00")


@pytest.mark.django_db
def test_age_uses_the_institutional_submission_date_not_the_utc_date():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("age-institutional")
    _, _, program = make_organization("AGE-INST")
    # 2026-08-29 17:30 UTC is 2026-08-30 01:30 in Asia/Manila: the 21st birthday has arrived.
    make_inventory(
        student=make_user("age-institutional@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        date_of_birth=datetime(2005, 8, 30).date(),
        submitted_time=datetime(2026, 8, 29, 17, 30, tzinfo=UTC),
    )

    rows = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)["sections"][
        "age"
    ]["rows"]
    assert [(row["key"], row["total_count"]) for row in rows] == [("21", 1)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("father", "mother", "expected"),
    [
        ((AnnualIncomeStatus.REPORTED, "131483"), (AnnualIncomeStatus.NONE, "0"), "POOR"),
        ((AnnualIncomeStatus.REPORTED, "131484"), (AnnualIncomeStatus.NONE, "0"), "LOW_INCOME"),
        (
            (AnnualIncomeStatus.REPORTED, "100000"),
            (AnnualIncomeStatus.REPORTED, "31484"),
            "LOW_INCOME",
        ),
        ((AnnualIncomeStatus.REPORTED, "2626680"), (AnnualIncomeStatus.NONE, "0"), "UPPER_INCOME"),
        ((AnnualIncomeStatus.REPORTED, "2626681"), (AnnualIncomeStatus.NONE, "0"), "RICH"),
        ((AnnualIncomeStatus.NONE, "0"), (AnnualIncomeStatus.NONE, "0"), "NONE"),
        (
            (AnnualIncomeStatus.NOT_SPECIFIED, None),
            (AnnualIncomeStatus.REPORTED, "50000"),
            "NOT_SPECIFIED",
        ),
    ],
)
def test_report_income_brackets_follow_canonical_boundaries(father, mother, expected):
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision(f"income-{expected.lower()}")
    _, _, program = make_organization(f"INC-{expected}")
    item = make_inventory(
        student=make_user(f"income-{expected.lower()}@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
    )
    for kind, (status, amount) in (
        (FamilyMemberKind.FATHER, father),
        (FamilyMemberKind.MOTHER, mother),
    ):
        item.family_members.filter(kind=kind).update(
            annual_income_status=status,
            annual_income_previous_year=None if amount is None else Decimal(amount),
        )

    section = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)["sections"][
        "parent_annual_income"
    ]
    assert report_row(section, expected)["total_count"] == 1
    assert sum(row["total_count"] for row in section["rows"]) == 1
