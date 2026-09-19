"""Printable Student Profiling report presentation over the canonical aggregate result."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from compass.documents.rendering import DocumentRenderError, render_document_pdf

from .services import ReportError, build_student_profiling_report

TEMPLATE_KEY = "student_profiling_report"
TEMPLATE_VERSION = 1

# Portrait A4 keeps two concise Program columns readable alongside Category,
# Total, and Percentage. This is presentation-only chunking.
MAX_PROGRAM_COLUMNS_PER_TABLE = 2

SECTION_ORDER = (
    "sex",
    "age",
    "civil_status",
    "physical_disadvantage",
    "current_religion",
    "mother_life_status",
    "father_life_status",
    "parent_family_status",
    "city_municipality",
    "parent_annual_income",
    "mother_occupation",
    "father_occupation",
    "living_condition",
)

FILTER_LABELS = {
    "academic_year_id": "Academic Year",
    "campus_id": "Campus",
    "college_id": "College",
    "program_id": "Program",
    "year_level": "Year Level",
}


class StudentProfilingDocumentUnavailable(ReportError):
    """The aggregate is valid, but its printable representation is unavailable."""


@dataclass(frozen=True, slots=True)
class StudentProfilingPdfResult:
    pdf_bytes: bytes
    filename: str


def _organization_display(item: dict[str, object] | None, fallback: str) -> str:
    if item is None:
        return fallback
    code = str(item.get("code") or "").strip()
    name = str(item.get("name") or "").strip()
    if code and name:
        return f"{code} — {name}"
    return code or name or fallback


def _program_display_columns(
    program_columns: list[dict[str, object]],
) -> list[dict[str, object]]:
    seen_keys: set[str] = set()
    code_counts: dict[str, int] = {}
    for column in program_columns:
        key = str(column["key"])
        if key in seen_keys:
            raise StudentProfilingDocumentUnavailable(
                "The Student Profiling Program-column identity is inconsistent."
            )
        seen_keys.add(key)
        code = str(column.get("code") or "").strip()
        if code:
            code_counts[code] = code_counts.get(code, 0) + 1

    display_columns: list[dict[str, object]] = []
    for column in program_columns:
        key = str(column["key"])
        name = str(column.get("name") or "").strip()
        code = str(column.get("code") or "").strip()
        college = column.get("college")
        campus = column.get("campus")
        is_legacy = bool(column.get("is_legacy"))

        if is_legacy:
            display_label = name or "Not recorded / legacy"
        elif code:
            display_label = code
            if code_counts.get(code, 0) > 1:
                context_codes: list[str] = []
                if isinstance(college, dict) and college.get("code"):
                    context_codes.append(str(college["code"]))
                if isinstance(campus, dict) and campus.get("code"):
                    context_codes.append(str(campus["code"]))
                if context_codes:
                    display_label = f"{code} ({' / '.join(context_codes)})"
        else:
            display_label = name or "Program"

        detail_parts = [part for part in (code, name) if part]
        if isinstance(college, dict):
            college_name = str(college.get("name") or "").strip()
            if college_name:
                detail_parts.append(college_name)
        if isinstance(campus, dict):
            campus_name = str(campus.get("name") or "").strip()
            if campus_name:
                detail_parts.append(campus_name)

        display_columns.append(
            {
                "key": key,
                "display_label": display_label,
                "detail_label": " · ".join(dict.fromkeys(detail_parts)),
                "is_legacy": is_legacy,
            }
        )
    return display_columns


def _percentage_display(value: object) -> str:
    if not isinstance(value, (Decimal, int, float)):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling percentage value is invalid."
        )
    return f"{value:.2f}%"


def _row_display_label(section_key: str, row: dict[str, object]) -> str:
    label = str(row["label"])
    if section_key != "city_municipality":
        return label
    if row.get("province_name"):
        return f"{label} — {row['province_name']}"
    if row.get("region_name"):
        return f"{label} — {row['region_name']}"
    return label


def _row_count_lookup(row: dict[str, object]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for entry in row.get("program_counts", []):
        if not isinstance(entry, dict):
            raise StudentProfilingDocumentUnavailable(
                "The Student Profiling Program counts are inconsistent."
            )
        key = str(entry["program_key"])
        if key in lookup:
            raise StudentProfilingDocumentUnavailable(
                "The Student Profiling Program counts contain a duplicate identity."
            )
        lookup[key] = int(entry["count"])
    return lookup


def _section_chunks(
    section_key: str,
    section: dict[str, object],
    program_columns: list[dict[str, object]],
) -> list[dict[str, object]]:
    raw_rows = section.get("rows", [])
    if not isinstance(raw_rows, list):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling section rows are unavailable."
        )

    row_lookups = [_row_count_lookup(row) for row in raw_rows]
    program_keys = [str(column["key"]) for column in program_columns]
    for lookup in row_lookups:
        missing = [key for key in program_keys if key not in lookup]
        if missing:
            raise StudentProfilingDocumentUnavailable(
                "The Student Profiling Program counts are incomplete."
            )

    chunks: list[dict[str, object]] = []
    for start in range(0, len(program_columns), MAX_PROGRAM_COLUMNS_PER_TABLE):
        columns = program_columns[start : start + MAX_PROGRAM_COLUMNS_PER_TABLE]
        rows: list[dict[str, object]] = []
        for raw_row, lookup in zip(raw_rows, row_lookups, strict=True):
            rows.append(
                {
                    "key": str(raw_row["key"]),
                    "label": _row_display_label(section_key, raw_row),
                    "total_count": int(raw_row["total_count"]),
                    "percentage": _percentage_display(raw_row["percentage"]),
                    "program_counts": [
                        {
                            "program_key": str(column["key"]),
                            "count": lookup[str(column["key"])],
                        }
                        for column in columns
                    ],
                }
            )
        chunks.append({"programs": columns, "rows": rows})
    return chunks


def _coverage_view(coverage: dict[str, object]) -> dict[str, object]:
    mode = str(coverage["mode"])
    if mode == "CURRENT":
        rows = [
            {"label": "Eligible Students", "value": coverage["eligible_student_count"]},
            {"label": "Submitted", "value": coverage["submitted_count"]},
            {"label": "Draft", "value": coverage["draft_count"]},
            {"label": "Without Individual Inventory", "value": coverage["missing_count"]},
        ]
    elif mode == "HISTORICAL_LIMITED":
        rows = [
            {"label": "Submitted", "value": coverage["submitted_count"]},
            {"label": "Draft", "value": coverage["draft_count"]},
            {
                "label": "Without Individual Inventory",
                "value": "Not available from current COMPASS data",
            },
        ]
    else:
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling coverage mode is unsupported."
        )

    ignored_labels = [
        FILTER_LABELS.get(str(name), str(name)) for name in coverage.get("ignored_filters", [])
    ]
    ignored_note = None
    if ignored_labels:
        ignored_note = (
            "Inventory Coverage does not apply the selected "
            + ", ".join(ignored_labels)
            + " filter(s) to its denominator. Those filters remain profile-data filters "
            "and do not classify Students without an Individual Inventory."
        )

    return {
        "mode": mode,
        "rows": rows,
        "scope_note": str(coverage["scope_note"]),
        "ignored_filter_note": ignored_note,
    }


def build_student_profiling_print_context(report: dict[str, object]) -> dict[str, object]:
    report_context = report["report_context"]
    methodology = report["methodology"]
    coverage = report["inventory_coverage"]
    raw_program_columns = report["program_columns"]
    raw_sections = report["sections"]

    if not isinstance(report_context, dict):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling report context is invalid."
        )
    if not isinstance(methodology, dict) or not isinstance(coverage, dict):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling methodology or coverage is invalid."
        )
    if not isinstance(raw_program_columns, list) or not isinstance(raw_sections, dict):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling aggregate presentation data is invalid."
        )

    programs = _program_display_columns(raw_program_columns)
    academic_year = report_context["academic_year"]
    if not isinstance(academic_year, dict):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling Academic Year context is invalid."
        )

    submitted_count = int(report_context["submitted_inventory_count"])
    sections: list[dict[str, object]] = []
    if submitted_count > 0:
        if not programs:
            raise StudentProfilingDocumentUnavailable(
                "The Student Profiling report has no Program identity for submitted data."
            )
        for section_key in SECTION_ORDER:
            section = raw_sections.get(section_key)
            if not isinstance(section, dict):
                raise StudentProfilingDocumentUnavailable(
                    f"The Student Profiling {section_key} section is unavailable."
                )
            sections.append(
                {
                    "key": section_key,
                    "title": str(section["label"]),
                    "denominator": int(section["denominator"]),
                    "chunks": _section_chunks(section_key, section, programs),
                }
            )

    campus = report_context.get("campus")
    college = report_context.get("college")
    program = report_context.get("program")
    if campus is not None and not isinstance(campus, dict):
        raise StudentProfilingDocumentUnavailable("The Campus report context is invalid.")
    if college is not None and not isinstance(college, dict):
        raise StudentProfilingDocumentUnavailable("The College report context is invalid.")
    if program is not None and not isinstance(program, dict):
        raise StudentProfilingDocumentUnavailable("The Program report context is invalid.")

    return {
        "student_profile": {
            "title": "STUDENTS' PROFILE",
            "academic_year": str(academic_year["label"]),
            "campus": _organization_display(campus, "All Campuses"),
            "college": _organization_display(college, "All Colleges"),
            "program": _organization_display(program, "All Programs"),
            "year_level": str(report_context.get("year_level_label") or "All Year Levels"),
            "generated_at": report_context["generated_at"],
            "submitted_inventory_count": submitted_count,
            "coverage": _coverage_view(coverage),
            "profile_population_note": str(methodology["profile_population_note"]),
            "program_legend": programs,
            "sections": sections,
            "empty_message": (
                "No submitted Individual Inventories matched the selected profile filters."
                if submitted_count == 0
                else None
            ),
        }
    }


def _safe_filename_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return safe or "academic-year"


def student_profiling_pdf_filename(academic_year_label: str) -> str:
    return f"student-profile-{_safe_filename_part(academic_year_label)}.pdf"


def render_student_profiling_pdf(
    *,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
) -> StudentProfilingPdfResult:
    report = build_student_profiling_report(
        academic_year_id=academic_year_id,
        campus_id=campus_id,
        college_id=college_id,
        program_id=program_id,
        year_level=year_level,
    )
    context = build_student_profiling_print_context(report)
    report_context = report["report_context"]
    if not isinstance(report_context, dict) or not isinstance(
        report_context.get("academic_year"), dict
    ):
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling Academic Year context is invalid."
        )
    academic_year = report_context["academic_year"]
    try:
        rendered = render_document_pdf(
            TEMPLATE_KEY,
            TEMPLATE_VERSION,
            context=context,
        )
    except DocumentRenderError as exc:
        raise StudentProfilingDocumentUnavailable(
            "The Student Profiling report PDF is temporarily unavailable."
        ) from exc
    return StudentProfilingPdfResult(
        pdf_bytes=rendered.pdf_bytes,
        filename=student_profiling_pdf_filename(str(academic_year["label"])),
    )
