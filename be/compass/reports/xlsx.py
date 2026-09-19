"""Spreadsheet-native Student Profiling XLSX export over the canonical aggregate result."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .filenames import safe_report_filename_part
from .services import ReportError, build_student_profiling_report

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_EXCEL_COLUMNS = 16_384
EMPTY_REPORT_MESSAGE = "No submitted Individual Inventories matched the selected profile filters."

FILTER_LABELS = {
    "academic_year_id": "Academic Year",
    "campus_id": "Campus",
    "college_id": "College",
    "program_id": "Program",
    "year_level": "Year Level",
}

SECTION_SPECS = (
    ("sex", "Sex", "Category"),
    ("age", "Age", "Age"),
    ("civil_status", "Civil Status", "Category"),
    ("physical_disadvantage", "Physical Disadv.", "Category"),
    ("current_religion", "Religion", "Category"),
    ("mother_life_status", "Mother Life", "Category"),
    ("father_life_status", "Father Life", "Category"),
    ("parent_family_status", "Parent Family", "Category"),
    ("city_municipality", "City Municipality", "City / Municipality"),
    ("parent_annual_income", "Parent Income", "Category"),
    ("mother_occupation", "Mother Occupation", "Category"),
    ("father_occupation", "Father Occupation", "Category"),
    ("living_condition", "Living Condition", "Category"),
)

_THIN_SIDE = Side(style="thin", color="B7B7B7")
_TABLE_BORDER = Border(
    left=_THIN_SIDE,
    right=_THIN_SIDE,
    top=_THIN_SIDE,
    bottom=_THIN_SIDE,
)
_HEADER_FILL = PatternFill(fill_type="solid", fgColor="E7E6E6")
_BOLD = Font(bold=True)
_WRAP = Alignment(wrap_text=True, vertical="top")
_CENTER = Alignment(horizontal="center", vertical="center")
_RIGHT = Alignment(horizontal="right", vertical="center")


class StudentProfilingWorkbookUnavailable(ReportError):
    """The canonical aggregate is valid, but its XLSX representation is unavailable."""


@dataclass(frozen=True, slots=True)
class StudentProfilingXlsxResult:
    xlsx_bytes: bytes
    filename: str


def _require_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StudentProfilingWorkbookUnavailable(
            f"The Student Profiling {label} is unavailable for XLSX export."
        )
    return value


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise StudentProfilingWorkbookUnavailable(
            f"The Student Profiling {label} is unavailable for XLSX export."
        )
    return value


def _write_text(
    worksheet: Worksheet,
    row: int,
    column: int,
    value: object,
    *,
    bold: bool = False,
    wrap: bool = False,
) -> Cell:
    """Write display text explicitly as a string cell, never as an Excel formula."""
    cell = worksheet.cell(row=row, column=column)
    cell.value = "" if value is None else str(value)
    cell.data_type = "s"
    cell.hyperlink = None
    if bold:
        cell.font = _BOLD
    if wrap:
        cell.alignment = _WRAP
    return cell


def _write_table_header(worksheet: Worksheet, row: int, headers: list[str]) -> None:
    for column, header in enumerate(headers, start=1):
        cell = _write_text(worksheet, row, column, header, bold=True, wrap=True)
        cell.fill = _HEADER_FILL
        cell.border = _TABLE_BORDER
        cell.alignment = _CENTER


def _write_table_text(worksheet: Worksheet, row: int, column: int, value: object) -> Cell:
    cell = _write_text(worksheet, row, column, value, wrap=True)
    cell.border = _TABLE_BORDER
    return cell


def _write_table_number(
    worksheet: Worksheet,
    row: int,
    column: int,
    value: int | Decimal,
    *,
    number_format: str | None = None,
) -> Cell:
    cell = worksheet.cell(row=row, column=column, value=value)
    cell.border = _TABLE_BORDER
    cell.alignment = _RIGHT
    if number_format is not None:
        cell.number_format = number_format
    return cell


def _set_capped_width(
    worksheet: Worksheet,
    column: int,
    *,
    minimum: float,
    maximum: float,
) -> None:
    max_length = 0
    for cell in worksheet[get_column_letter(column)]:
        if cell.value is None:
            continue
        max_length = max(max_length, len(str(cell.value)))
    width = max(minimum, min(maximum, max_length + 2))
    worksheet.column_dimensions[get_column_letter(column)].width = width


def _organization_display(item: object, fallback: str) -> str:
    if item is None:
        return fallback
    value = _require_dict(item, "organization context")
    code = str(value.get("code") or "").strip()
    name = str(value.get("name") or "").strip()
    if code and name:
        return f"{code} — {name}"
    return code or name or fallback


def _program_display_columns(program_columns: object) -> list[dict[str, object]]:
    raw_columns = _require_list(program_columns, "Program columns")
    seen_keys: set[str] = set()
    code_counts: dict[str, int] = {}

    for raw_column in raw_columns:
        column = _require_dict(raw_column, "Program column")
        key = str(column.get("key") or "")
        if not key or key in seen_keys:
            raise StudentProfilingWorkbookUnavailable(
                "The Student Profiling Program-column identity is inconsistent."
            )
        seen_keys.add(key)
        code = str(column.get("code") or "").strip()
        if code:
            code_counts[code] = code_counts.get(code, 0) + 1

    display_columns: list[dict[str, object]] = []
    for raw_column in raw_columns:
        column = _require_dict(raw_column, "Program column")
        key = str(column["key"])
        code = str(column.get("code") or "").strip()
        name = str(column.get("name") or "").strip()
        college = column.get("college")
        campus = column.get("campus")
        is_legacy = bool(column.get("is_legacy"))

        college_dict = None if college is None else _require_dict(college, "Program College")
        campus_dict = None if campus is None else _require_dict(campus, "Program Campus")

        if is_legacy:
            display_label = name or "Not recorded / legacy"
        elif code:
            display_label = code
            if code_counts.get(code, 0) > 1:
                context_codes = [
                    str(parent.get("code") or "").strip()
                    for parent in (college_dict, campus_dict)
                    if parent is not None and str(parent.get("code") or "").strip()
                ]
                if context_codes:
                    display_label = f"{code} ({' / '.join(context_codes)})"
        else:
            display_label = name or "Program"

        display_columns.append(
            {
                "key": key,
                "display_label": display_label,
                "code": code,
                "name": name or ("Not recorded / legacy" if is_legacy else "Program"),
                "college": _organization_display(college_dict, "") if college_dict else "",
                "campus": _organization_display(campus_dict, "") if campus_dict else "",
                "is_legacy": is_legacy,
            }
        )
    return display_columns


def _program_count_lookup(
    row: dict[str, object],
    program_columns: list[dict[str, object]],
) -> dict[str, int]:
    raw_counts = _require_list(row.get("program_counts"), "Program counts")
    lookup: dict[str, int] = {}
    for raw_count in raw_counts:
        count = _require_dict(raw_count, "Program count")
        key = str(count.get("program_key") or "")
        if not key or key in lookup:
            raise StudentProfilingWorkbookUnavailable(
                "The Student Profiling Program counts contain an invalid or duplicate identity."
            )
        lookup[key] = int(count.get("count") or 0)

    expected = {str(column["key"]) for column in program_columns}
    if set(lookup) != expected:
        raise StudentProfilingWorkbookUnavailable(
            "The Student Profiling Program counts do not match the canonical Program columns."
        )
    return lookup


def _generated_at_text(value: object) -> str:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise StudentProfilingWorkbookUnavailable(
            "The Student Profiling generated timestamp must include timezone information."
        )
    return value.isoformat(timespec="seconds")


def _percentage_value(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    raise StudentProfilingWorkbookUnavailable("The Student Profiling percentage value is invalid.")


def _coverage_rows(coverage: dict[str, object]) -> list[tuple[str, object]]:
    mode = str(coverage.get("mode") or "")
    if mode == "CURRENT":
        return [
            ("Coverage Mode", mode),
            ("Eligible Students", coverage.get("eligible_student_count")),
            ("Submitted", coverage.get("submitted_count")),
            ("Draft", coverage.get("draft_count")),
            ("Without Individual Inventory", coverage.get("missing_count")),
        ]
    if mode == "HISTORICAL_LIMITED":
        return [
            ("Coverage Mode", mode),
            ("Submitted", coverage.get("submitted_count")),
            ("Draft", coverage.get("draft_count")),
            (
                "Without Individual Inventory",
                "Not available from current COMPASS data",
            ),
        ]
    raise StudentProfilingWorkbookUnavailable("The Student Profiling coverage mode is unsupported.")


def _coverage_ignored_note(coverage: dict[str, object]) -> str | None:
    raw_filters = coverage.get("ignored_filters", [])
    if not isinstance(raw_filters, list):
        raise StudentProfilingWorkbookUnavailable(
            "The Student Profiling ignored coverage filters are invalid."
        )
    labels = [FILTER_LABELS.get(str(item), str(item)) for item in raw_filters]
    if not labels:
        return None
    return "Coverage filters not applicable to missing-Inventory classification: " + ", ".join(
        labels
    )


def _validate_excel_column_limit(program_columns: list[dict[str, object]]) -> None:
    widest_section = len(program_columns) + 5
    if widest_section > MAX_EXCEL_COLUMNS:
        raise StudentProfilingWorkbookUnavailable(
            "The Student Profiling report exceeds the XLSX worksheet column limit."
        )


def _build_summary_sheet(
    worksheet: Worksheet,
    report_context: dict[str, object],
    methodology: dict[str, object],
    coverage: dict[str, object],
    program_columns: list[dict[str, object]],
) -> None:
    worksheet.title = "Summary"
    worksheet.sheet_view.showGridLines = False

    _write_text(worksheet, 1, 1, "Students' Profile", bold=True)
    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    worksheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
    worksheet["A1"].font = Font(bold=True, size=14)

    academic_year = _require_dict(report_context.get("academic_year"), "Academic Year context")
    context_rows = [
        ("Academic Year", academic_year.get("label")),
        ("Campus", _organization_display(report_context.get("campus"), "All Campuses")),
        ("College", _organization_display(report_context.get("college"), "All Colleges")),
        ("Program", _organization_display(report_context.get("program"), "All Programs")),
        ("Year Level", report_context.get("year_level_label") or "All Year Levels"),
        ("Generated At", _generated_at_text(report_context.get("generated_at"))),
        ("Submitted Inventory Count", int(report_context.get("submitted_inventory_count") or 0)),
    ]

    _write_text(worksheet, 3, 1, "Report Context", bold=True)
    row = 4
    for label, value in context_rows:
        _write_text(worksheet, row, 1, label, bold=True, wrap=True)
        if isinstance(value, int):
            worksheet.cell(row=row, column=2, value=value)
        else:
            _write_text(worksheet, row, 2, value, wrap=True)
        row += 1

    row += 1
    _write_text(worksheet, row, 1, "Inventory Coverage", bold=True)
    row += 1
    for label, value in _coverage_rows(coverage):
        _write_text(worksheet, row, 1, label, bold=True, wrap=True)
        if isinstance(value, int):
            worksheet.cell(row=row, column=2, value=value)
        else:
            _write_text(worksheet, row, 2, value, wrap=True)
        row += 1

    row += 1
    _write_text(worksheet, row, 1, "Methodology / Coverage Scope", bold=True)
    row += 1
    _write_text(
        worksheet,
        row,
        1,
        methodology.get("profile_population_note"),
        wrap=True,
    )
    worksheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 1
    _write_text(worksheet, row, 1, coverage.get("scope_note"), wrap=True)
    worksheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)

    ignored_note = _coverage_ignored_note(coverage)
    if ignored_note:
        row += 1
        _write_text(worksheet, row, 1, ignored_note, wrap=True)
        worksheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)

    if int(report_context.get("submitted_inventory_count") or 0) == 0:
        row += 2
        _write_text(worksheet, row, 1, EMPTY_REPORT_MESSAGE, bold=True, wrap=True)
        worksheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)

    row += 2
    _write_text(worksheet, row, 1, "Program Legend / Program Columns", bold=True)
    row += 1
    legend_headers = [
        "Displayed Column",
        "Program Code",
        "Program Name",
        "College",
        "Campus",
        "Legacy",
    ]
    _write_table_header(worksheet, row, legend_headers)
    for program in program_columns:
        row += 1
        values = [
            program["display_label"],
            program["code"],
            program["name"],
            program["college"],
            program["campus"],
            "Yes" if program["is_legacy"] else "No",
        ]
        for column, value in enumerate(values, start=1):
            _write_table_text(worksheet, row, column, value)

    _set_capped_width(worksheet, 1, minimum=24, maximum=38)
    _set_capped_width(worksheet, 2, minimum=20, maximum=72)
    for column in range(3, 7):
        _set_capped_width(worksheet, column, minimum=12, maximum=32)


def _build_section_sheet(
    workbook: Workbook,
    *,
    section_key: str,
    sheet_name: str,
    category_header: str,
    section: dict[str, object],
    program_columns: list[dict[str, object]],
    empty_report: bool,
) -> None:
    worksheet = workbook.create_sheet(title=sheet_name)
    is_geography = section_key == "city_municipality"
    headers = [category_header, "Province", "Region"] if is_geography else [category_header]
    headers.extend(str(program["display_label"]) for program in program_columns)
    headers.extend(["Total", "Percentage (%)"])
    _write_table_header(worksheet, 1, headers)

    if not empty_report:
        raw_rows = _require_list(section.get("rows"), f"{section_key} rows")
        for row_number, raw_row in enumerate(raw_rows, start=2):
            row = _require_dict(raw_row, f"{section_key} row")
            count_lookup = _program_count_lookup(row, program_columns)
            column_number = 1
            _write_table_text(worksheet, row_number, column_number, row.get("label"))
            column_number += 1

            if is_geography:
                _write_table_text(
                    worksheet,
                    row_number,
                    column_number,
                    row.get("province_name") or "",
                )
                column_number += 1
                _write_table_text(
                    worksheet,
                    row_number,
                    column_number,
                    row.get("region_name") or "",
                )
                column_number += 1

            for program in program_columns:
                _write_table_number(
                    worksheet,
                    row_number,
                    column_number,
                    count_lookup[str(program["key"])],
                )
                column_number += 1

            _write_table_number(
                worksheet,
                row_number,
                column_number,
                int(row.get("total_count") or 0),
            )
            column_number += 1
            _write_table_number(
                worksheet,
                row_number,
                column_number,
                _percentage_value(row.get("percentage")),
                number_format="0.00",
            )

    worksheet.freeze_panes = "A2"
    last_column = get_column_letter(len(headers))
    worksheet.auto_filter.ref = f"A1:{last_column}{max(1, worksheet.max_row)}"

    base_offset = 3 if is_geography else 1
    _set_capped_width(worksheet, 1, minimum=25, maximum=35)
    if is_geography:
        _set_capped_width(worksheet, 2, minimum=18, maximum=28)
        _set_capped_width(worksheet, 3, minimum=16, maximum=24)
    for index in range(len(program_columns)):
        _set_capped_width(
            worksheet,
            base_offset + index + 1,
            minimum=10,
            maximum=18,
        )
    _set_capped_width(
        worksheet,
        base_offset + len(program_columns) + 1,
        minimum=10,
        maximum=12,
    )
    _set_capped_width(
        worksheet,
        base_offset + len(program_columns) + 2,
        minimum=14,
        maximum=16,
    )


def build_student_profiling_workbook(report: dict[str, object]) -> Workbook:
    report_context = _require_dict(report.get("report_context"), "report context")
    methodology = _require_dict(report.get("methodology"), "methodology")
    coverage = _require_dict(report.get("inventory_coverage"), "Inventory Coverage")
    sections = _require_dict(report.get("sections"), "sections")
    program_columns = _program_display_columns(report.get("program_columns"))
    _validate_excel_column_limit(program_columns)

    workbook = Workbook()
    _build_summary_sheet(
        workbook.active,
        report_context,
        methodology,
        coverage,
        program_columns,
    )

    empty_report = int(report_context.get("submitted_inventory_count") or 0) == 0
    for section_key, sheet_name, category_header in SECTION_SPECS:
        section = _require_dict(sections.get(section_key), f"{section_key} section")
        _build_section_sheet(
            workbook,
            section_key=section_key,
            sheet_name=sheet_name,
            category_header=category_header,
            section=section,
            program_columns=program_columns,
            empty_report=empty_report,
        )

    return workbook


def _serialize_workbook(workbook: Workbook) -> bytes:
    for worksheet in workbook.worksheets:
        if worksheet.sheet_state != "visible":
            raise StudentProfilingWorkbookUnavailable(
                "The Student Profiling workbook contains an unexpected hidden worksheet."
            )
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    raise StudentProfilingWorkbookUnavailable(
                        "The Student Profiling workbook contains an unexpected formula."
                    )
                if cell.hyperlink is not None:
                    raise StudentProfilingWorkbookUnavailable(
                        "The Student Profiling workbook contains an unexpected hyperlink."
                    )

    stream = BytesIO()
    workbook.save(stream)
    payload = stream.getvalue()
    if not payload:
        raise StudentProfilingWorkbookUnavailable(
            "The Student Profiling workbook could not be serialized."
        )
    return payload


def student_profiling_xlsx_filename(academic_year_label: str) -> str:
    safe_year = safe_report_filename_part(
        academic_year_label,
        fallback="academic-year",
    )
    return f"student-profile-{safe_year}.xlsx"


def render_student_profiling_xlsx(
    *,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
) -> StudentProfilingXlsxResult:
    # Keep canonical filter/report failures outside the XLSX exception boundary.
    report = build_student_profiling_report(
        academic_year_id=academic_year_id,
        campus_id=campus_id,
        college_id=college_id,
        program_id=program_id,
        year_level=year_level,
    )

    try:
        workbook = build_student_profiling_workbook(report)
        payload = _serialize_workbook(workbook)
        report_context = _require_dict(report.get("report_context"), "report context")
        academic_year = _require_dict(
            report_context.get("academic_year"),
            "Academic Year context",
        )
        filename = student_profiling_xlsx_filename(str(academic_year.get("label") or ""))
    except StudentProfilingWorkbookUnavailable:
        raise
    except Exception as exc:
        raise StudentProfilingWorkbookUnavailable(
            "The Student Profiling report XLSX is temporarily unavailable."
        ) from exc

    return StudentProfilingXlsxResult(xlsx_bytes=payload, filename=filename)
