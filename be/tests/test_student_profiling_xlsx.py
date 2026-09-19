from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from django.test import Client
from openpyxl import load_workbook

from compass.accounts.models import Designation, UserDesignation
from compass.reports import api as reports_api
from compass.reports import xlsx as report_xlsx
from compass.reports.pdf import student_profiling_pdf_filename
from compass.reports.services import (
    InvalidReportFilter,
    ReportConfigurationConflict,
    ReportNotFound,
)
from compass.reports.xlsx import (
    EMPTY_REPORT_MESSAGE,
    MAX_EXCEL_COLUMNS,
    SECTION_SPECS,
    XLSX_CONTENT_TYPE,
    StudentProfilingWorkbookUnavailable,
    StudentProfilingXlsxResult,
    _validate_excel_column_limit,
    render_student_profiling_xlsx,
    student_profiling_xlsx_filename,
)
from tests.test_student_profiling_pdf import (
    auth_client,
    make_head,
    make_user,
    sync_policy,
    synthetic_report,
)

EXPECTED_SHEETS = [
    "Summary",
    "Sex",
    "Age",
    "Civil Status",
    "Physical Disadv.",
    "Religion",
    "Mother Life",
    "Father Life",
    "Parent Family",
    "City Municipality",
    "Parent Income",
    "Mother Occupation",
    "Father Occupation",
    "Living Condition",
]


def fake_xlsx_result() -> StudentProfilingXlsxResult:
    return StudentProfilingXlsxResult(
        xlsx_bytes=b"synthetic-xlsx-payload",
        filename="student-profile-2026-2027.xlsx",
    )


def workbook_from_report(monkeypatch, report):
    monkeypatch.setattr(
        report_xlsx,
        "build_student_profiling_report",
        lambda **kwargs: report,
    )
    result = render_student_profiling_xlsx()
    return load_workbook(BytesIO(result.xlsx_bytes), data_only=False, keep_links=False)


def workbook_values(workbook) -> list[object]:
    return [
        cell.value
        for worksheet in workbook.worksheets
        for row in worksheet.iter_rows()
        for cell in row
        if cell.value is not None
    ]


def assert_no_formulas_or_hyperlinks(workbook) -> None:
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                assert cell.data_type != "f"
                assert cell.hyperlink is None


@pytest.mark.django_db
def test_xlsx_endpoint_reuses_reports_view_without_recent_mfa(monkeypatch):
    sync_policy()
    monkeypatch.setattr(
        reports_api,
        "render_student_profiling_xlsx",
        lambda **kwargs: fake_xlsx_result(),
    )

    head = make_head("head-xlsx@example.edu")
    counselor = make_user("ordinary-xlsx@example.edu", "COUNSELOR")
    staff = make_user("staff-xlsx@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student-xlsx@example.edu", "STUDENT")
    admin = make_user("admin-xlsx@example.edu", "IT_ADMIN")
    dpo = make_user("dpo-xlsx@example.edu", "IT_ADMIN")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )

    response = auth_client(head).get("/api/v1/reports/student-profile/xlsx")
    assert response.status_code == 200
    assert response["Content-Type"] == XLSX_CONTENT_TYPE
    assert response["Content-Disposition"] == (
        'attachment; filename="student-profile-2026-2027.xlsx"'
    )
    assert response.content == b"synthetic-xlsx-payload"

    for user in (counselor, staff, student, admin, dpo):
        assert auth_client(user).get("/api/v1/reports/student-profile/xlsx").status_code == 403
    assert Client().get("/api/v1/reports/student-profile/xlsx").status_code == 401


@pytest.mark.django_db
def test_xlsx_endpoint_forwards_same_report_filters(monkeypatch):
    sync_policy()
    head = make_head("head-xlsx-filters@example.edu")
    client = auth_client(head)
    academic_year_id = uuid4()
    campus_id = uuid4()
    college_id = uuid4()
    program_id = uuid4()
    captured: list[dict[str, object]] = []

    def fake_render(**kwargs):
        captured.append(kwargs)
        return fake_xlsx_result()

    monkeypatch.setattr(reports_api, "render_student_profiling_xlsx", fake_render)
    response = client.get(
        "/api/v1/reports/student-profile/xlsx",
        {
            "academic_year_id": academic_year_id,
            "campus_id": campus_id,
            "college_id": college_id,
            "program_id": program_id,
            "year_level": 4,
        },
    )
    assert response.status_code == 200
    assert captured == [
        {
            "academic_year_id": academic_year_id,
            "campus_id": campus_id,
            "college_id": college_id,
            "program_id": program_id,
            "year_level": 4,
        }
    ]

    captured.clear()
    assert client.get("/api/v1/reports/student-profile/xlsx").status_code == 200
    assert captured == [
        {
            "academic_year_id": None,
            "campus_id": None,
            "college_id": None,
            "program_id": None,
            "year_level": None,
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("exc", "status_code", "error_code"),
    [
        (ReportNotFound("missing filter"), 404, "report_filter_not_found"),
        (
            ReportConfigurationConflict("configuration conflict"),
            409,
            "report_configuration_conflict",
        ),
        (InvalidReportFilter("contradictory filters"), 422, "invalid_report_filter"),
        (
            StudentProfilingWorkbookUnavailable("private workbook detail"),
            503,
            "report_workbook_unavailable",
        ),
    ],
)
def test_xlsx_endpoint_preserves_report_errors_and_hides_workbook_details(
    monkeypatch,
    exc,
    status_code,
    error_code,
):
    sync_policy()
    head = make_head(f"head-xlsx-error-{status_code}@example.edu")

    def fail(**kwargs):
        raise exc

    monkeypatch.setattr(reports_api, "render_student_profiling_xlsx", fail)
    response = auth_client(head).get("/api/v1/reports/student-profile/xlsx")
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    if status_code == 503:
        assert "private workbook detail" not in response.content.decode()


def test_render_service_calls_canonical_builder_once_and_forwards_exact_filters(monkeypatch):
    report = synthetic_report(program_count=3, submitted_count=3)
    calls: list[dict[str, object]] = []
    filters = {
        "academic_year_id": uuid4(),
        "campus_id": uuid4(),
        "college_id": uuid4(),
        "program_id": uuid4(),
        "year_level": 5,
    }

    def fake_builder(**kwargs):
        calls.append(kwargs)
        return report

    monkeypatch.setattr(report_xlsx, "build_student_profiling_report", fake_builder)
    result = render_student_profiling_xlsx(**filters)

    assert calls == [filters]
    assert result.filename == "student-profile-2026-2027.xlsx"
    workbook = load_workbook(BytesIO(result.xlsx_bytes), data_only=False, keep_links=False)
    assert workbook.sheetnames == EXPECTED_SHEETS


def test_canonical_report_errors_remain_outside_workbook_error_boundary(monkeypatch):
    expected = ReportNotFound("canonical filter failure")

    def fail_builder(**kwargs):
        raise expected

    monkeypatch.setattr(report_xlsx, "build_student_profiling_report", fail_builder)
    with pytest.raises(ReportNotFound) as raised:
        render_student_profiling_xlsx()
    assert raised.value is expected


def test_workbook_generation_failures_are_wrapped_without_internal_details(monkeypatch):
    monkeypatch.setattr(
        report_xlsx,
        "build_student_profiling_report",
        lambda **kwargs: synthetic_report(program_count=2),
    )

    def fail_workbook(report):
        raise ValueError("/private/path/openpyxl/zip detail")

    monkeypatch.setattr(report_xlsx, "build_student_profiling_workbook", fail_workbook)
    with pytest.raises(
        StudentProfilingWorkbookUnavailable,
        match="temporarily unavailable",
    ) as raised:
        render_student_profiling_xlsx()
    assert "/private/path" not in str(raised.value)


def test_workbook_is_valid_deterministic_visible_and_formula_free(monkeypatch):
    report = synthetic_report(program_count=3, submitted_count=3)
    workbook = workbook_from_report(monkeypatch, report)

    assert workbook.sheetnames == EXPECTED_SHEETS
    assert len(workbook.worksheets) == 14
    assert getattr(workbook, "vba_archive", None) is None
    assert all(worksheet.sheet_state == "visible" for worksheet in workbook.worksheets)
    assert_no_formulas_or_hyperlinks(workbook)

    for _, sheet_name, _ in SECTION_SPECS:
        worksheet = workbook[sheet_name]
        assert worksheet.freeze_panes == "A2"
        assert worksheet.auto_filter.ref
        assert all(cell.font.bold for cell in worksheet[1])


def test_summary_preserves_timezone_context_current_coverage_and_methodology(monkeypatch):
    report = synthetic_report(program_count=2, submitted_count=2, mode="CURRENT")
    report["report_context"]["year_level_label"] = "3rd Year"
    expected_timestamp = report["report_context"]["generated_at"].isoformat(timespec="seconds")
    workbook = workbook_from_report(monkeypatch, report)
    values = workbook_values(workbook)

    for expected in (
        "Students' Profile",
        "Academic Year",
        "2026-2027",
        "All Campuses",
        "All Colleges",
        "All Programs",
        "3rd Year",
        "Generated At",
        expected_timestamp,
        "Submitted Inventory Count",
        "Inventory Coverage",
        "CURRENT",
        "Eligible Students",
        "Submitted",
        "Draft",
        "Without Individual Inventory",
        "PROFILE POPULATION NOTE.",
        "CANONICAL CURRENT COVERAGE SCOPE NOTE.",
        "Coverage filters not applicable to missing-Inventory classification: Program, Year Level",
        "Program Legend / Program Columns",
    ):
        assert expected in values

    assert "DUPLICATE GENERIC COVERAGE NOTE SHOULD NOT PRINT." not in values
    assert expected_timestamp.endswith("+00:00") or expected_timestamp[-6] in {"+", "-"}

    methodology_cell = next(
        cell
        for row in workbook["Summary"].iter_rows()
        for cell in row
        if cell.value == "PROFILE POPULATION NOTE."
    )
    assert methodology_cell.alignment.wrap_text is True


def test_historical_summary_does_not_fabricate_eligible_or_missing_counts(monkeypatch):
    report = synthetic_report(program_count=2, submitted_count=2, mode="HISTORICAL_LIMITED")
    workbook = workbook_from_report(monkeypatch, report)
    values = workbook_values(workbook)

    assert "HISTORICAL_LIMITED" in values
    assert "Eligible Students" not in values
    assert "Not available from current COMPASS data" in values
    assert "CANONICAL HISTORICAL COVERAGE SCOPE NOTE." in values
    assert "DUPLICATE GENERIC COVERAGE NOTE SHOULD NOT PRINT." not in values
    assert "DUPLICATE HISTORICAL METHODOLOGY NOTE SHOULD NOT PRINT." not in values


def test_section_sheet_uses_all_programs_key_lookup_and_canonical_percentage(monkeypatch):
    report = synthetic_report(program_count=4, submitted_count=4)
    programs = report["program_columns"]
    row = report["sections"]["sex"]["rows"][0]
    expected_counts = {
        str(program["key"]): (index + 1) * 10 for index, program in enumerate(programs)
    }
    row["program_counts"] = list(
        reversed([{"program_key": key, "count": count} for key, count in expected_counts.items()])
    )
    row["total_count"] = 777
    row["percentage"] = Decimal("32.72")

    workbook = workbook_from_report(monkeypatch, report)
    worksheet = workbook["Sex"]
    headers = [cell.value for cell in worksheet[1]]
    exported = [cell.value for cell in worksheet[2]]

    assert headers == [
        "Category",
        "P-01",
        "P-02",
        "P-03",
        "P-04",
        "Total",
        "Percentage (%)",
    ]
    assert exported[1:5] == [expected_counts[str(program["key"])] for program in programs]
    assert exported[5] == 777
    assert Decimal(str(exported[6])).quantize(Decimal("0.01")) == Decimal("32.72")
    assert worksheet.cell(row=2, column=7).number_format == "0.00"


def test_duplicate_program_codes_are_disambiguated_and_legend_keeps_identity(monkeypatch):
    report = synthetic_report(program_count=2, submitted_count=2)
    first, second = report["program_columns"]
    first["code"] = second["code"] = "DUP"
    first["college"] = {"id": uuid4(), "code": "COL-A", "name": "College A"}
    first["campus"] = {"id": uuid4(), "code": "CAMP-A", "name": "Campus A"}
    second["college"] = {"id": uuid4(), "code": "COL-B", "name": "College B"}
    second["campus"] = {"id": uuid4(), "code": "CAMP-B", "name": "Campus B"}

    workbook = workbook_from_report(monkeypatch, report)
    sex_headers = [cell.value for cell in workbook["Sex"][1]]
    values = workbook_values(workbook)

    assert sex_headers[1] == "DUP (COL-A / CAMP-A)"
    assert sex_headers[2] == "DUP (COL-B / CAMP-B)"
    assert sex_headers[1] != sex_headers[2]
    assert "COL-A — College A" in values
    assert "COL-B — College B" in values
    assert first["name"] in values
    assert second["name"] in values


def test_legacy_program_column_is_retained(monkeypatch):
    report = synthetic_report(program_count=2, submitted_count=2)
    legacy = {
        "key": "legacy:not-recorded",
        "program_id": None,
        "code": None,
        "name": "Not recorded / legacy",
        "college": None,
        "campus": None,
        "is_legacy": True,
    }
    report["program_columns"].append(legacy)
    for section in report["sections"].values():
        for row in section["rows"]:
            row["program_counts"] = [
                *row["program_counts"],
                {"program_key": "legacy:not-recorded", "count": 0},
            ]

    workbook = workbook_from_report(monkeypatch, report)
    assert "Not recorded / legacy" in [cell.value for cell in workbook["Sex"][1]]
    assert "Not recorded / legacy" in workbook_values(workbook)


def test_geography_sheet_preserves_canonical_city_province_region_context(monkeypatch):
    report = synthetic_report(program_count=2, submitted_count=2)
    base_row = report["sections"]["city_municipality"]["rows"][0]
    report["sections"]["city_municipality"]["rows"] = [
        base_row,
        {
            **base_row,
            "key": "NOT_SPECIFIED",
            "label": "Not specified",
            "province_name": None,
            "region_name": None,
        },
        {
            **base_row,
            "key": "NOT_RECORDED_LEGACY",
            "label": "Not recorded / legacy",
            "province_name": None,
            "region_name": None,
        },
    ]

    workbook = workbook_from_report(monkeypatch, report)
    worksheet = workbook["City Municipality"]
    assert [cell.value for cell in worksheet[1]][:3] == [
        "City / Municipality",
        "Province",
        "Region",
    ]
    assert [cell.value for cell in worksheet[2]][:3] == [
        "Synthetic City",
        "Synthetic Province",
        "Bicol Region",
    ]
    labels = [worksheet.cell(row=row, column=1).value for row in range(2, worksheet.max_row + 1)]
    assert "Not specified" in labels
    assert "Not recorded / legacy" in labels


def test_empty_report_keeps_stable_sheet_structure_with_headers_only(monkeypatch):
    report = synthetic_report(program_count=0, submitted_count=0)
    workbook = workbook_from_report(monkeypatch, report)

    assert workbook.sheetnames == EXPECTED_SHEETS
    assert EMPTY_REPORT_MESSAGE in workbook_values(workbook)
    for _, sheet_name, _ in SECTION_SPECS:
        worksheet = workbook[sheet_name]
        assert worksheet.max_row == 1
        assert worksheet.freeze_panes == "A2"


def test_untrusted_display_text_is_forced_to_text_cells_and_never_formulas(monkeypatch):
    report = synthetic_report(program_count=1, submitted_count=1)
    program = report["program_columns"][0]
    program["code"] = "=SUM(1,1)"
    program["name"] = "+1+1"
    program["college"] = {"id": uuid4(), "code": "-1+1", "name": ""}
    program["campus"] = {"id": uuid4(), "code": "@SUM(A1:A2)", "name": ""}
    report["sections"]["city_municipality"]["rows"][0]["label"] = "=CITY()"

    workbook = workbook_from_report(monkeypatch, report)
    dangerous = {"=SUM(1,1)", "+1+1", "-1+1", "@SUM(A1:A2)", "=CITY()"}
    seen: dict[str, str] = {}

    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.value in dangerous:
                    seen[str(cell.value)] = cell.data_type
                assert cell.data_type != "f"
                assert cell.hyperlink is None

    assert seen == {value: "s" for value in dangerous}


def test_export_ignores_unexpected_private_keys_and_has_no_hidden_raw_sheet(monkeypatch):
    report = synthetic_report(program_count=2, submitted_count=2)
    secrets = {
        "PRIVATE-STUDENT-UUID",
        "PRIVATE-STUDENT-NUMBER",
        "private-student@example.edu",
        "PRIVATE-PHONE",
        "PRIVATE-EXACT-ADDRESS",
        "PRIVATE-PARENT-NAME",
        "PRIVATE-NARRATIVE",
    }
    report["private_student_uuid"] = "PRIVATE-STUDENT-UUID"
    report["private_student_number"] = "PRIVATE-STUDENT-NUMBER"
    report["private_email"] = "private-student@example.edu"
    report["private_phone"] = "PRIVATE-PHONE"
    report["private_address"] = "PRIVATE-EXACT-ADDRESS"
    report["private_parent_name"] = "PRIVATE-PARENT-NAME"
    report["sections"]["sex"]["rows"][0]["private_narrative"] = "PRIVATE-NARRATIVE"

    workbook = workbook_from_report(monkeypatch, report)
    serialized_values = {str(value) for value in workbook_values(workbook)}
    assert secrets.isdisjoint(serialized_values)
    assert set(workbook.sheetnames) == set(EXPECTED_SHEETS)
    assert all(worksheet.sheet_state == "visible" for worksheet in workbook.worksheets)


def test_filename_sanitization_is_shared_with_pdf_without_behavior_regression():
    assert student_profiling_xlsx_filename("2026-2027") == "student-profile-2026-2027.xlsx"
    assert student_profiling_xlsx_filename(" AY 2026/2027 ") == (
        "student-profile-AY-2026-2027.xlsx"
    )
    assert student_profiling_pdf_filename("2026-2027") == "student-profile-2026-2027.pdf"
    assert student_profiling_pdf_filename(" AY 2026/2027 ") == ("student-profile-AY-2026-2027.pdf")
    assert "/" not in student_profiling_xlsx_filename("../../AY 2026/2027")


def test_excel_column_limit_fails_safely_without_chunking_or_truncation():
    too_many_programs = [{}] * (MAX_EXCEL_COLUMNS - 4)
    with pytest.raises(
        StudentProfilingWorkbookUnavailable,
        match="column limit",
    ):
        _validate_excel_column_limit(too_many_programs)
