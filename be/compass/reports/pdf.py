"""Printable Student Profiling report presentation over the canonical aggregate result.

The PDF is a presentation of build_student_profiling_report(...) only. Every printed count and
percentage comes from the canonical report, or is a College subtotal of canonical Program counts
with its percentage taken through the same canonical calculate_percentage(...). Before anything is
printed the canonical result is reconciled: rows must sum to the population, every Program column
must sum to its canonical Program total, and coverage must agree with its reconciliation. A report
that fails any of these checks is never printed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from compass.common.institutional_time import institution_timezone_name, to_institution_time
from compass.documents.rendering import DocumentRenderError, render_document_pdf

from .filenames import safe_report_filename_part
from .services import (
    LEGACY_KEY,
    LEGACY_LABEL,
    PARENT_INCOME_LEGEND_NOTE,
    ReportAccessScope,
    ReportError,
    build_student_profiling_report,
    calculate_percentage,
    parent_income_bracket_legend,
    student_profiling_release_context,
)

TEMPLATE_KEY = "student_profiling_report"
TEMPLATE_VERSION = 1

REPORT_TITLE = "STUDENT PROFILE REPORT"
REPORT_SUBTITLE = "Individual Inventory-Based Student Profiling"

# A College cross-tab prints Category, one column per Program, the College total, and the College
# percentage. Beyond this many Programs the columns are no longer readable on A4 portrait, so the
# College prints as a College summary followed by a long-form table with one row per Program and
# category. Programs are never split into partial column chunks.
MAX_CROSS_TAB_PROGRAMS = 5

# Tables with at most this many body rows are kept on one page. Longer tables may break between
# complete rows and repeat their column headers on the next page.
SHORT_TABLE_ROWS = 18

UNCLASSIFIED_GROUP_CODE = "Unclassified / Legacy"

# Presentation order and print titles. Canonical section keys and data are unchanged.
SECTION_SPECS = {
    "sex": ("Sex", "Sex"),
    "age": ("Age at Inventory Submission", "Age (years)"),
    "civil_status": ("Civil Status", "Civil Status"),
    "physical_disadvantage": ("PWD Status", "PWD Status"),
    "current_religion": ("Current Religion", "Religion"),
    "mother_life_status": ("Mother's Life Status", "Life Status"),
    "father_life_status": ("Father's Life Status", "Life Status"),
    "parent_family_status": ("Parent Family Status", "Parent Family Status"),
    "parent_annual_income": ("Combined Parent Annual Income", "Income Bracket"),
    "mother_occupation": ("Mother's Occupation", "Occupation"),
    "father_occupation": ("Father's Occupation", "Occupation"),
    "living_condition": ("Living Condition", "Living Condition"),
    "city_municipality": ("Current City / Municipality of Residence", "City / Municipality"),
}

REPORT_PARTS = (
    (
        "4. Demographics",
        ("sex", "age", "civil_status", "physical_disadvantage", "current_religion"),
    ),
    (
        "5. Family and Household",
        (
            "mother_life_status",
            "father_life_status",
            "parent_family_status",
            "parent_annual_income",
            "mother_occupation",
            "father_occupation",
            "living_condition",
        ),
    ),
    ("6. Geographic Distribution", ("city_municipality",)),
)
SECTION_ORDER = tuple(key for _, keys in REPORT_PARTS for key in keys)

FILTER_LABELS = {
    "academic_year_id": "Academic Year",
    "campus_id": "Campus",
    "college_id": "College",
    "program_id": "Program",
    "year_level": "Year Level",
}

NOT_AVAILABLE_HISTORICAL = "Not available — no historical eligibility roster"


class StudentProfilingDocumentUnavailable(ReportError):
    """The aggregate is valid, but its printable representation is unavailable."""


@dataclass(frozen=True, slots=True)
class StudentProfilingPdfResult:
    pdf_bytes: bytes
    filename: str
    release_context: dict[str, object]


@dataclass(frozen=True, slots=True)
class _Program:
    key: str
    code: str
    name: str
    total: int
    is_legacy: bool


@dataclass(frozen=True, slots=True)
class _Group:
    code: str
    name: str
    campus: str
    programs: tuple[_Program, ...]
    is_unclassified: bool

    @property
    def total(self) -> int:
        return sum(program.total for program in self.programs)


def _unavailable(message: str) -> StudentProfilingDocumentUnavailable:
    return StudentProfilingDocumentUnavailable(f"The Student Profiling {message}")


def _require_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _unavailable(f"{label} is invalid.")
    return value


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise _unavailable(f"{label} is invalid.")
    return value


def _require_count(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise _unavailable(f"{label} is invalid.")
    return value


def _count_text(value: int) -> str:
    return f"{value:,}"


def _percentage_text(value: object) -> str:
    if value is None:
        return "N/A"
    if not isinstance(value, (Decimal, int, float)):
        raise _unavailable("percentage value is invalid.")
    return f"{Decimal(str(value)):.2f}%"


def _total_percentage_text(denominator: int) -> str:
    return _percentage_text(calculate_percentage(denominator, denominator))


def _organization_display(item: object, fallback: str) -> str:
    if item is None:
        return fallback
    value = _require_dict(item, "organization context")
    code = str(value.get("code") or "").strip()
    name = str(value.get("name") or "").strip()
    if code and name:
        return f"{code} — {name}"
    return code or name or fallback


def _institutional_timestamp(value: object) -> str:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise _unavailable("generated timestamp must include timezone information.")
    local = to_institution_time(value)
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return (
        f"{local.day} {local:%B %Y}, {hour}:{local:%M} {meridiem} ({institution_timezone_name()})"
    )


def _cell(text: object, *, numeric: bool = False) -> dict[str, object]:
    return {"text": str(text), "numeric": numeric}


def _row(cells: list[dict[str, object]], kind: str = "data") -> dict[str, object]:
    return {"cells": cells, "kind": kind}


def _column(label: str, width: str, *, numeric: bool = False) -> dict[str, object]:
    return {"label": label, "width": width, "numeric": numeric}


def _table(
    *,
    title: str,
    columns: list[dict[str, object]],
    rows: list[dict[str, object]] | None = None,
    row_blocks: list[list[dict[str, object]]] | None = None,
    key: str = "",
    number: str = "",
    population_note: str = "",
    notes: list[str] | None = None,
) -> dict[str, object]:
    # A row block is printed as one unbreakable table body, so a Program's rows and its total
    # never land on different pages.
    blocks = row_blocks if row_blocks is not None else [rows or []]
    row_count = sum(len(block) for block in blocks)
    return {
        "key": key,
        "number": number,
        "title": title,
        "population_note": population_note,
        "columns": columns,
        "row_blocks": blocks,
        "rows": [row for block in blocks for row in block],
        "notes": notes or [],
        "keep_together": row_count <= SHORT_TABLE_ROWS,
    }


# Canonical reconciliation -------------------------------------------------------------------


def _programs(raw_columns: object, population: int) -> list[_Program]:
    programs: list[_Program] = []
    seen: set[str] = set()
    for raw in _require_list(raw_columns, "Program columns"):
        column = _require_dict(raw, "Program column")
        key = str(column.get("key") or "")
        if not key or key in seen:
            raise _unavailable("Program-column identity is inconsistent.")
        seen.add(key)
        is_legacy = bool(column.get("is_legacy"))
        programs.append(
            _Program(
                key=key,
                code=str(column.get("code") or "").strip(),
                name=str(column.get("name") or "").strip() or LEGACY_LABEL,
                total=_require_count(column.get("submitted_inventory_count"), "Program population"),
                is_legacy=is_legacy,
            )
        )
    if sum(program.total for program in programs) != population:
        raise _unavailable("Program populations do not reconcile to the profile population.")
    if population > 0 and not programs:
        raise _unavailable("report has no Program identity for submitted data.")
    return programs


def _groups(raw_columns: object, programs: list[_Program]) -> list[_Group]:
    """Group Programs by canonical College identity, keeping canonical column order."""

    by_key = {program.key: program for program in programs}
    ordered: dict[str, dict[str, object]] = {}
    unclassified: list[_Program] = []
    for raw in _require_list(raw_columns, "Program columns"):
        column = _require_dict(raw, "Program column")
        program = by_key[str(column["key"])]
        college = column.get("college")
        if program.is_legacy or college is None:
            unclassified.append(program)
            continue
        college = _require_dict(college, "Program College")
        campus = column.get("campus")
        campus_name = campus_code = ""
        if campus is not None:
            campus = _require_dict(campus, "Program Campus")
            campus_name = str(campus.get("name") or "").strip()
            campus_code = str(campus.get("code") or "").strip()
        group = ordered.setdefault(
            str(college.get("id")),
            {
                "code": str(college.get("code") or "").strip(),
                "name": str(college.get("name") or "").strip(),
                "campus": campus_name,
                "campus_code": campus_code,
                "programs": [],
            },
        )
        group["programs"].append(program)

    # College codes are unique only within a Campus; add the Campus when two Colleges share one.
    code_counts: dict[str, int] = {}
    for item in ordered.values():
        code_counts[str(item["code"])] = code_counts.get(str(item["code"]), 0) + 1
    groups = [
        _Group(
            code=(
                f"{item['code']} ({item['campus_code'] or item['campus']})"
                if code_counts[str(item["code"])] > 1
                else str(item["code"])
            ),
            name=str(item["name"]),
            campus=str(item["campus"]),
            programs=tuple(item["programs"]),
            is_unclassified=False,
        )
        for item in ordered.values()
    ]
    if unclassified:
        groups.append(
            _Group(
                code=UNCLASSIFIED_GROUP_CODE,
                name="Inventories without a recorded Program",
                campus="",
                programs=tuple(unclassified),
                is_unclassified=True,
            )
        )
    return groups


def _section_rows(
    section_key: str,
    section: dict[str, object],
    programs: list[_Program],
    population: int,
) -> list[dict[str, object]]:
    """Return canonical rows with a key-matched count lookup after verifying every invariant."""

    if _require_count(section.get("denominator"), f"{section_key} denominator") != population:
        raise _unavailable(f"{section_key} denominator does not match the profile population.")
    program_keys = {program.key for program in programs}
    rows: list[dict[str, object]] = []
    program_sums = dict.fromkeys(program_keys, 0)
    row_sum = 0
    for raw in _require_list(section.get("rows"), f"{section_key} rows"):
        row = _require_dict(raw, f"{section_key} row")
        lookup: dict[str, int] = {}
        for raw_count in _require_list(row.get("program_counts"), "Program counts"):
            entry = _require_dict(raw_count, "Program count")
            key = str(entry.get("program_key") or "")
            if not key or key in lookup:
                raise _unavailable("Program counts contain an invalid or duplicate identity.")
            lookup[key] = _require_count(entry.get("count"), "Program count")
        if set(lookup) != program_keys:
            raise _unavailable("Program counts do not match the canonical Program columns.")
        total = _require_count(row.get("total_count"), f"{section_key} row total")
        if sum(lookup.values()) != total:
            raise _unavailable(f"{section_key} Program counts do not sum to the row total.")
        percentage = row.get("percentage")
        expected = calculate_percentage(total, population)
        if (percentage is None) != (expected is None) or (
            percentage is not None and Decimal(str(percentage)) != expected
        ):
            raise _unavailable(f"{section_key} percentage does not match its denominator.")
        for key, count in lookup.items():
            program_sums[key] += count
        row_sum += total
        rows.append({**row, "lookup": lookup})
    if row_sum != population:
        raise _unavailable(f"{section_key} rows do not sum to the profile population.")
    for program in programs:
        if program_sums[program.key] != program.total:
            raise _unavailable(f"{section_key} counts do not reconcile to the Program population.")
    return rows


def _reconciliation(coverage: dict[str, object], population: int) -> dict[str, int]:
    raw = _require_dict(coverage.get("reconciliation"), "population reconciliation")
    values = {
        key: _require_count(raw.get(key), "population reconciliation")
        for key in (
            "profile_submitted_count",
            "coverage_submitted_count",
            "in_both_count",
            "profile_only_count",
            "coverage_only_count",
        )
    }
    if (
        values["profile_submitted_count"] != population
        or values["coverage_submitted_count"] != coverage.get("submitted_count")
        or values["in_both_count"] + values["profile_only_count"]
        != values["profile_submitted_count"]
        or values["in_both_count"] + values["coverage_only_count"]
        != values["coverage_submitted_count"]
    ):
        raise _unavailable("population reconciliation is inconsistent.")
    return values


# Labels -------------------------------------------------------------------------------------


def _row_label(section_key: str, row: dict[str, object], *, with_province: bool) -> str:
    label = str(row["label"])
    if section_key == "city_municipality" and with_province and row.get("province_name"):
        return f"{label}, {row['province_name']}"
    return label


def _is_printed_overall(row: dict[str, object]) -> bool:
    # Every controlled response is printed, even at zero, so the full option set is visible.
    # Not recorded / legacy is not a response option and is printed only when it occurs.
    return str(row["key"]) != LEGACY_KEY or int(row["total_count"]) > 0


def _income_bracket_rows() -> list[dict[str, object]]:
    return [
        _row([_cell(label), _cell(description)])
        for label, description in parent_income_bracket_legend()
    ]


# Front matter -------------------------------------------------------------------------------


def _scope_colleges(report_context: dict[str, object]) -> tuple[bool, list[str]]:
    scope = _require_dict(report_context.get("reporting_scope"), "reporting scope")
    is_global = scope.get("is_global")
    if not isinstance(is_global, bool):
        raise _unavailable("reporting scope is invalid.")
    labels: list[str] = []
    for raw in _require_list(scope.get("colleges", []), "reporting scope Colleges"):
        college = _require_dict(raw, "reporting scope College")
        campus = college.get("campus")
        campus_name = (
            str(_require_dict(campus, "reporting scope Campus").get("name") or "")
            if campus is not None
            else ""
        )
        label = _organization_display(college, "College")
        labels.append(f"{label} ({campus_name})" if campus_name else label)
    if not is_global and not labels:
        raise _unavailable("reporting scope has no authorized College.")
    return is_global, labels


def _metadata_rows(
    report_context: dict[str, object],
    population: int,
    *,
    is_global: bool,
    scope_labels: list[str],
) -> list[dict[str, object]]:
    academic_year = _require_dict(report_context.get("academic_year"), "Academic Year context")
    year_label = str(academic_year.get("label") or "")
    year_label += (
        " (current Academic Year)"
        if academic_year.get("is_current")
        else " (historical Academic Year)"
    )
    campus = report_context.get("campus")
    college = report_context.get("college")
    program = report_context.get("program")
    within = "" if is_global else " within the reporting scope"
    if college is not None:
        program_default = "All Programs in the selected College"
    else:
        program_default = "All Programs" + within
    values = [
        ("Academic Year", year_label),
        ("Campus filter", _organization_display(campus, "All Campuses" + within)),
        ("College filter", _organization_display(college, "All Colleges" + within)),
        ("Program filter", _organization_display(program, program_default)),
        (
            "Year Level filter",
            str(report_context.get("year_level_label") or "All Year Levels"),
        ),
        (
            "Reporting Scope",
            "Institution-wide"
            if is_global
            else "Limited to assigned Colleges: " + "; ".join(scope_labels),
        ),
        (
            "Submitted Inventory Profile Population",
            f"{_count_text(population)} submitted Individual "
            + ("Inventory" if population == 1 else "Inventories"),
        ),
        ("Generated At", _institutional_timestamp(report_context.get("generated_at"))),
    ]
    return [_row([_cell(label), _cell(value)]) for label, value in values]


def _filter_rows(
    report_context: dict[str, object],
    coverage: dict[str, object],
    *,
    is_global: bool,
) -> list[dict[str, object]]:
    mode = str(coverage["mode"])
    applied = set(_require_list(coverage.get("applied_filters", []), "applied filters"))
    by_affiliation = "Applied — Student's current Guidance affiliation"
    by_inventory = "Applied — College of the Program recorded on the Inventory"
    not_applied = "Not applied — cannot classify Students without an Inventory"
    if mode == "HISTORICAL_LIMITED":
        not_applied = "Not applied — historical coverage uses the reporting scope only"

    rows = [
        _row([_cell("Academic Year"), _cell("Applied"), _cell("Applied")]),
        _row(
            [
                _cell("Reporting scope"),
                _cell("Institution-wide" if is_global else by_inventory),
                _cell(
                    "Institution-wide"
                    if is_global
                    else by_affiliation
                    if mode == "CURRENT"
                    else by_inventory
                ),
            ]
        ),
    ]
    profile_effects = {
        "campus_id": "Applied — Campus of the Program recorded on the Inventory",
        "college_id": by_inventory,
        "program_id": "Applied — Program recorded on the Inventory",
        "year_level": "Applied — Year Level recorded on the Inventory",
    }
    selected = {
        "campus_id": report_context.get("campus") is not None,
        "college_id": report_context.get("college") is not None,
        "program_id": report_context.get("program") is not None,
        "year_level": report_context.get("year_level") is not None,
    }
    for name, profile_effect in profile_effects.items():
        if not selected[name]:
            rows.append(
                _row([_cell(FILTER_LABELS[name]), _cell("Not selected"), _cell("Not selected")])
            )
            continue
        coverage_effect = by_affiliation if name in applied else not_applied
        rows.append(
            _row([_cell(FILTER_LABELS[name]), _cell(profile_effect), _cell(coverage_effect)])
        )
    return rows


def _count_row(label: str, value: int, kind: str = "data") -> dict[str, object]:
    return _row([_cell(label), _cell(_count_text(value), numeric=True)], kind)


def _coverage_tables(
    coverage: dict[str, object],
    methodology: dict[str, object],
    reconciliation: dict[str, int],
) -> dict[str, object]:
    mode = str(coverage.get("mode") or "")
    submitted = _require_count(coverage.get("submitted_count"), "coverage Submitted count")
    draft = _require_count(coverage.get("draft_count"), "coverage Draft count")
    profile_n = reconciliation["profile_submitted_count"]
    coverage_n = reconciliation["coverage_submitted_count"]
    in_both = reconciliation["in_both_count"]
    if mode == "CURRENT":
        eligible = _require_count(coverage.get("eligible_student_count"), "coverage eligible count")
        missing = _require_count(coverage.get("missing_count"), "coverage missing count")
        if submitted + draft + missing != eligible:
            raise _unavailable("coverage states do not sum to the eligible Students.")
        title = "Current Student Inventory Coverage"
        note = str(methodology.get("coverage_note") or "")
        count_header = "Students"
        status_rows = [
            _count_row("Eligible current Students", eligible, "total"),
            _count_row("Submitted", submitted),
            _count_row("Draft", draft),
            _count_row("Without Individual Inventory", missing),
        ]
        status_note = (
            "Submitted + Draft + Without Individual Inventory = Eligible current Students. "
            "Each Student is counted once."
        )
        reconciliation_rows = [
            _count_row("Submitted Inventories in the profile population", profile_n, "subtotal"),
            _count_row("Student also counted as Submitted in Current Coverage", in_both, "indent"),
            _count_row(
                "Student not counted in Current Coverage (no longer an active Current Student, "
                "or currently affiliated outside the coverage scope)",
                reconciliation["profile_only_count"],
                "indent",
            ),
            _count_row("Students counted as Submitted in Current Coverage", coverage_n, "subtotal"),
            _count_row("Inventory also in the profile population", in_both, "indent"),
            _count_row(
                "Inventory outside the profile population (its recorded Program, College, "
                "Campus, or Year Level is outside the selected profile filters, or it has no "
                "recorded Program)",
                reconciliation["coverage_only_count"],
                "indent",
            ),
        ]
    elif mode == "HISTORICAL_LIMITED":
        title = "Inventory Coverage — Historical Academic Year (limited)"
        note = str(methodology.get("historical_coverage_note") or "")
        if not note:
            raise _unavailable("historical coverage note is unavailable.")
        count_header = "Inventories"
        status_rows = [
            _count_row("Submitted", submitted),
            _count_row("Draft", draft),
            _row([_cell("Eligible Students"), _cell(NOT_AVAILABLE_HISTORICAL)]),
            _row([_cell("Without Individual Inventory"), _cell(NOT_AVAILABLE_HISTORICAL)]),
        ]
        status_note = (
            "Historical coverage counts Inventories that exist for the Academic Year. No eligible "
            "or missing count is shown because COMPASS has no historical enrollment roster."
        )
        reconciliation_rows = [
            _count_row("Submitted Inventories in historical coverage", coverage_n, "subtotal"),
            _count_row("Included in the profile population", in_both, "indent"),
            _count_row(
                "Outside the profile population (excluded by the selected Campus, College, "
                "Program, or Year Level profile filters)",
                reconciliation["coverage_only_count"],
                "indent",
            ),
            _count_row("Submitted Inventories in the profile population", profile_n, "subtotal"),
        ]
    else:
        raise _unavailable("coverage mode is unsupported.")

    return {
        "mode": mode,
        "title": title,
        "note": note,
        "status": _table(
            title=title,
            columns=[
                _column("Inventory Status", "62%"),
                _column(count_header, "38%", numeric=True),
            ],
            rows=status_rows,
            notes=[status_note],
        ),
        "reconciliation": _table(
            title="Reconciliation of Coverage and Profile Population",
            columns=[_column("Population", "80%"), _column("Count", "20%", numeric=True)],
            rows=reconciliation_rows,
        ),
    }


def _college_summary_table(groups: list[_Group], population: int) -> dict[str, object]:
    rows = []
    for group in groups:
        share = _percentage_text(calculate_percentage(group.total, population))
        rows.append(
            _row(
                [
                    _cell(group.code if group.is_unclassified else f"{group.code} — {group.name}"),
                    _cell(group.campus or "—"),
                    _cell(_count_text(len(group.programs)), numeric=True),
                    _cell(_count_text(group.total), numeric=True),
                    _cell(share, numeric=True),
                ]
            )
        )
    rows.append(
        _row(
            [
                _cell("Total"),
                _cell(""),
                _cell(_count_text(sum(len(group.programs) for group in groups)), numeric=True),
                _cell(_count_text(population), numeric=True),
                _cell(_total_percentage_text(population), numeric=True),
            ],
            "total",
        )
    )
    return _table(
        title="Submitted Inventory Profile Population by College",
        columns=[
            _column("College", "44%"),
            _column("Campus", "18%"),
            _column("Programs", "11%", numeric=True),
            _column("Inventories", "12%", numeric=True),
            _column("% of Population", "15%", numeric=True),
        ],
        rows=rows,
        notes=[
            "Colleges are taken from the Program recorded on each Inventory. Inventories without "
            "a recorded Program are listed as Unclassified / Legacy and are not attributed to a "
            "College."
        ]
        if any(group.is_unclassified for group in groups)
        else [],
    )


def _methodology(
    methodology: dict[str, object],
    coverage_note: str,
    population: int,
    *,
    appendix_note: str | None,
) -> list[dict[str, str]]:
    profile_note = str(methodology.get("profile_population_note") or "")
    if not profile_note or not coverage_note:
        raise _unavailable("methodology is unavailable.")
    if population == 0:
        return [
            {"term": "Population basis", "text": profile_note},
            {"term": "Coverage basis", "text": coverage_note},
            {
                "term": "Empty population",
                "text": (
                    "No submitted Individual Inventory matched the selected profile filters, so "
                    "no distribution is printed and no percentage is calculated."
                ),
            },
        ]
    items = [
        {"term": "Population basis", "text": profile_note},
        {"term": "Coverage basis", "text": coverage_note},
        {
            "term": "Denominators and percentages",
            "text": (
                "Every distribution in Sections 4 to 6 uses the Submitted Inventory Profile "
                f"Population (n = {_count_text(population)}) as its denominator. Percentages are "
                "calculated from exact counts and rounded half-up to two decimal places. Each row "
                "is rounded independently, so the printed rows may add up to 99.99% or 100.01%; "
                "Total rows show the exact count and 100.00%."
            ),
        },
        {
            "term": "Age",
            "text": (
                "Exact age in years on the institutional date the Inventory was submitted, "
                "calculated from the recorded date of birth. It is not the Student's age today. "
                "Ages are listed individually, without overlapping groups."
            ),
        },
        {
            "term": "Not specified and legacy values",
            "text": (
                "Not specified means the Student chose that response. Not recorded / legacy means "
                "the structured value is missing, usually because an older Inventory predates "
                "structured capture; it is never treated as a Student response. A Not recorded / "
                "legacy row is printed only when at least one Inventory lacks the value."
            ),
        },
        {
            "term": "Residence",
            "text": (
                "City / Municipality uses the structured PSGC location saved for the Student's "
                "current residence. Province and Region are shown as context. Addresses are not "
                "parsed and locations are not inferred."
            ),
        },
        {
            "term": "Confidentiality",
            "text": (
                "Counts are exact and are not suppressed. Aggregate tables are not guaranteed to "
                "be anonymous: small counts, narrow filters, or comparing reports generated with "
                "different filters can reveal information about individual Students. Share this "
                "report only with personnel authorized to view it."
            ),
        },
    ]
    if appendix_note:
        items.insert(-1, {"term": "Program breakdown", "text": appendix_note})
    return items


# Distribution tables ------------------------------------------------------------------------


def _overall_table(
    number: int,
    section_key: str,
    rows: list[dict[str, object]],
    population: int,
) -> dict[str, object]:
    title, category_header = SECTION_SPECS[section_key]
    is_geography = section_key == "city_municipality"
    body: list[dict[str, object]] = []
    for row in rows:
        if not _is_printed_overall(row):
            continue
        cells = [_cell(_row_label(section_key, row, with_province=False))]
        if is_geography:
            cells.append(_cell(row.get("province_name") or "—"))
            cells.append(_cell(row.get("region_name") or "—"))
        cells.append(_cell(_count_text(int(row["total_count"])), numeric=True))
        cells.append(_cell(_percentage_text(row["percentage"]), numeric=True))
        body.append(_row(cells))
    total_cells = [_cell("Total")]
    if is_geography:
        total_cells.extend([_cell(""), _cell("")])
    total_cells.extend(
        [
            _cell(_count_text(population), numeric=True),
            _cell(_total_percentage_text(population), numeric=True),
        ]
    )
    body.append(_row(total_cells, "total"))

    if is_geography:
        columns = [
            _column(category_header, "30%"),
            _column("Province", "22%"),
            _column("Region", "24%"),
            _column("Frequency", "11%", numeric=True),
            _column("Percentage", "13%", numeric=True),
        ]
    else:
        columns = [
            _column(category_header, "58%"),
            _column("Frequency", "20%", numeric=True),
            _column("Percentage", "22%", numeric=True),
        ]
    return _table(
        key=section_key,
        number=f"Table {number}.",
        title=f"Distribution of Students by {title}",
        population_note=(
            f"Population: submitted Individual Inventories (n = {_count_text(population)})"
        ),
        columns=columns,
        rows=body,
    )


def _group_population_note(group: _Group) -> str:
    if group.is_unclassified:
        return (
            f"Population: Inventories without a recorded Program (n = {_count_text(group.total)})"
        )
    if len(group.programs) == 1:
        return (
            f"College population: n = {_count_text(group.total)} "
            f"({group.programs[0].code or group.programs[0].name} only)"
        )
    return f"College population: n = {_count_text(group.total)}"


def _group_rows(group: _Group, rows: list[dict[str, object]]) -> list[tuple[dict, int]]:
    printed = []
    for row in rows:
        subtotal = sum(row["lookup"][program.key] for program in group.programs)
        if subtotal > 0:
            printed.append((row, subtotal))
    return printed


def _cross_tab_table(
    number: str,
    section_key: str,
    group: _Group,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    title, category_header = SECTION_SPECS[section_key]
    programs = group.programs
    show_total_column = len(programs) > 1
    numeric_count = len(programs) + (2 if show_total_column else 1)
    category_width = 46 if numeric_count <= 2 else 40 if numeric_count <= 4 else 30
    numeric_width = f"{(100 - category_width) / numeric_count:.2f}%"
    columns = [_column(category_header, f"{category_width}%")]
    columns.extend(
        _column(
            "Inventories" if program.is_legacy else program.code or program.name,
            numeric_width,
            numeric=True,
        )
        for program in programs
    )
    if show_total_column:
        columns.append(_column(f"{group.code} Total", numeric_width, numeric=True))
    columns.append(
        _column(
            "% of group" if group.is_unclassified else f"% of {group.code}",
            numeric_width,
            numeric=True,
        )
    )

    body = []
    for row, subtotal in _group_rows(group, rows):
        cells = [_cell(_row_label(section_key, row, with_province=True))]
        cells.extend(
            _cell(_count_text(row["lookup"][program.key]), numeric=True) for program in programs
        )
        if show_total_column:
            cells.append(_cell(_count_text(subtotal), numeric=True))
        cells.append(
            _cell(_percentage_text(calculate_percentage(subtotal, group.total)), numeric=True)
        )
        body.append(_row(cells))
    total_cells = [_cell("Total")]
    total_cells.extend(_cell(_count_text(program.total), numeric=True) for program in programs)
    if show_total_column:
        total_cells.append(_cell(_count_text(group.total), numeric=True))
    total_cells.append(_cell(_total_percentage_text(group.total), numeric=True))
    body.append(_row(total_cells, "total"))
    return _table(
        number=number,
        title=f"{group.code} — {title}",
        population_note=_group_population_note(group),
        columns=columns,
        rows=body,
    )


def _college_summary_section_table(
    number: str,
    section_key: str,
    group: _Group,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    title, category_header = SECTION_SPECS[section_key]
    body = [
        _row(
            [
                _cell(_row_label(section_key, row, with_province=True)),
                _cell(_count_text(subtotal), numeric=True),
                _cell(_percentage_text(calculate_percentage(subtotal, group.total)), numeric=True),
            ]
        )
        for row, subtotal in _group_rows(group, rows)
    ]
    body.append(
        _row(
            [
                _cell("Total"),
                _cell(_count_text(group.total), numeric=True),
                _cell(_total_percentage_text(group.total), numeric=True),
            ],
            "total",
        )
    )
    return _table(
        number=number,
        title=f"{group.code} — {title} (College total)",
        population_note=_group_population_note(group),
        columns=[
            _column(category_header, "58%"),
            _column(f"{group.code} Total", "20%", numeric=True),
            _column(f"% of {group.code}", "22%", numeric=True),
        ],
        rows=body,
    )


def _long_form_table(
    number: str,
    section_key: str,
    group: _Group,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    title, category_header = SECTION_SPECS[section_key]
    blocks = []
    for program in group.programs:
        label = program.code or program.name
        block = [
            _row(
                [
                    _cell(label),
                    _cell(_row_label(section_key, row, with_province=True)),
                    _cell(_count_text(row["lookup"][program.key]), numeric=True),
                    _cell(_count_text(program.total), numeric=True),
                    _cell(
                        _percentage_text(
                            calculate_percentage(row["lookup"][program.key], program.total)
                        ),
                        numeric=True,
                    ),
                ]
            )
            for row in rows
            if row["lookup"][program.key] > 0
        ]
        block.append(
            _row(
                [
                    _cell(label),
                    _cell("Total"),
                    _cell(_count_text(program.total), numeric=True),
                    _cell(_count_text(program.total), numeric=True),
                    _cell(_total_percentage_text(program.total), numeric=True),
                ],
                "subtotal",
            )
        )
        blocks.append(block)
    return _table(
        number=number,
        title=f"{group.code} — {title} by Program",
        population_note="Denominator: each Program's submitted Inventories (Program n)",
        columns=[
            _column("Program", "17%"),
            _column(category_header, "37%"),
            _column("Frequency", "14%", numeric=True),
            _column("Program n", "14%", numeric=True),
            _column("% of Program", "18%", numeric=True),
        ],
        row_blocks=blocks,
    )


def _program_population_table(groups: list[_Group], population: int) -> dict[str, object]:
    body = []
    for group in groups:
        for program in group.programs:
            body.append(
                _row(
                    [
                        _cell(group.code),
                        _cell(
                            "No Program recorded"
                            if program.is_legacy
                            else f"{program.code} — {program.name}"
                        ),
                        _cell(_count_text(program.total), numeric=True),
                        _cell(
                            _percentage_text(calculate_percentage(program.total, population)),
                            numeric=True,
                        ),
                    ]
                )
            )
        if len(group.programs) > 1 and len(groups) > 1:
            body.append(
                _row(
                    [
                        _cell(f"{group.code} subtotal"),
                        _cell(""),
                        _cell(_count_text(group.total), numeric=True),
                        _cell(
                            _percentage_text(calculate_percentage(group.total, population)),
                            numeric=True,
                        ),
                    ],
                    "subtotal",
                )
            )
    body.append(
        _row(
            [
                _cell("Total"),
                _cell(""),
                _cell(_count_text(population), numeric=True),
                _cell(_total_percentage_text(population), numeric=True),
            ],
            "total",
        )
    )
    return _table(
        number="Table A.",
        title="Submitted Inventory Profile Population by College and Program",
        population_note=(
            f"Population: submitted Individual Inventories (n = {_count_text(population)})"
        ),
        columns=[
            _column("College", "18%"),
            _column("Program", "52%"),
            _column("Inventories", "14%", numeric=True),
            _column("% of Population", "16%", numeric=True),
        ],
        rows=body,
    )


def _appendix_groups(
    groups: list[_Group],
    section_rows: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    appendix = []
    for group_index, group in enumerate(groups, start=1):
        long_form = len(group.programs) > MAX_CROSS_TAB_PROGRAMS
        tables = []
        table_index = 0
        for section_key in SECTION_ORDER:
            rows = section_rows[section_key]
            if long_form:
                table_index += 1
                tables.append(
                    _college_summary_section_table(
                        f"Table A{group_index}.{table_index}.", section_key, group, rows
                    )
                )
                table_index += 1
                tables.append(
                    _long_form_table(
                        f"Table A{group_index}.{table_index}.", section_key, group, rows
                    )
                )
            else:
                table_index += 1
                tables.append(
                    _cross_tab_table(
                        f"Table A{group_index}.{table_index}.", section_key, group, rows
                    )
                )

        if group.is_unclassified:
            heading = f"A{group_index}. Unclassified / Legacy — Inventories without a Program"
            summary = f"Submitted Inventories: n = {_count_text(group.total)}"
            notes = [
                "These submitted Inventories have no recorded Program, usually because they "
                "predate structured Program capture. They remain in the profile population but "
                "are not attributed to any College or Program."
            ]
        else:
            heading = f"A{group_index}. {group.code} — {group.name}"
            summary = " · ".join(
                part
                for part in (
                    group.campus,
                    f"Submitted Inventories: n = {_count_text(group.total)}",
                    "Programs: "
                    + "; ".join(
                        f"{program.code} ({_count_text(program.total)})"
                        for program in group.programs
                    ),
                )
                if part
            )
            if long_form:
                notes = [
                    f"{group.code} has {len(group.programs)} Programs, more than fit across an "
                    "A4 page, so each distribution prints as a College total followed by a "
                    "long-form table with one row per Program and category."
                ]
            elif len(group.programs) == 1:
                notes = [
                    f"% of {group.code} uses the College population (n = "
                    f"{_count_text(group.total)}) as its denominator."
                ]
            else:
                notes = [
                    f"Program columns sum to the {group.code} Total; % of {group.code} uses the "
                    f"College population (n = {_count_text(group.total)}) as its denominator."
                ]
        notes.append("Categories with no responses in this group are not listed.")
        appendix.append(
            {
                "heading": heading,
                "summary": summary,
                "notes": [" ".join(notes)],
                "tables": tables,
            }
        )
    return appendix


def _disclosure_messages(raw_warnings: list[object]) -> list[str]:
    messages: list[str] = []
    for raw in raw_warnings:
        warning = _require_dict(raw, "disclosure warning metadata")
        message = warning.get("message")
        if not isinstance(message, str):
            raise _unavailable("disclosure warning metadata is invalid.")
        message = message.strip()
        if message and message not in messages:
            messages.append(message)
    return messages


def build_student_profiling_print_context(report: dict[str, object]) -> dict[str, object]:
    report_context = _require_dict(report.get("report_context"), "report context")
    methodology = _require_dict(report.get("methodology"), "methodology")
    coverage = _require_dict(report.get("inventory_coverage"), "coverage")
    sections = _require_dict(report.get("sections"), "sections")
    raw_warnings = _require_list(report.get("disclosure_warnings", []), "disclosure warnings")

    population = _require_count(
        report_context.get("submitted_inventory_count"), "submitted Inventory count"
    )
    programs = _programs(report.get("program_columns"), population)
    groups = _groups(report.get("program_columns"), programs)
    is_global, scope_labels = _scope_colleges(report_context)
    reconciliation = _reconciliation(coverage, population)
    coverage_view = _coverage_tables(coverage, methodology, reconciliation)

    parts: list[dict[str, object]] = []
    appendix: list[dict[str, object]] = []
    appendix_note = None
    program_population = None
    income_legend = None
    if population > 0:
        section_rows = {
            key: _section_rows(
                key, _require_dict(sections.get(key), f"{key} section"), programs, population
            )
            for key in SECTION_ORDER
        }
        number = 0
        for part_title, keys in REPORT_PARTS:
            tables = []
            for key in keys:
                number += 1
                tables.append(_overall_table(number, key, section_rows[key], population))
            parts.append({"title": part_title, "tables": tables})
        income_legend = _table(
            title="Parent Annual Income Brackets",
            columns=[_column("Bracket", "30%"), _column("Combined annual income", "70%")],
            rows=_income_bracket_rows(),
            notes=[PARENT_INCOME_LEGEND_NOTE],
        )
        if len(programs) > 1:
            program_population = _program_population_table(groups, population)
            appendix = _appendix_groups(groups, section_rows)
            appendix_note = (
                "Appendix A repeats each distribution for every College and its Programs. "
                "College tables use that College's submitted Inventories as their denominator, so "
                "their totals reconcile to the College population, not to the institution-wide "
                "total."
            )
        else:
            appendix_note = (
                "The profile population contains a single Program, so Sections 4 to 6 are already "
                "its Program breakdown and no Program appendix is printed."
            )

    return {
        "student_profile": {
            "title": REPORT_TITLE,
            "subtitle": REPORT_SUBTITLE,
            "metadata": _table(
                title="Report Overview",
                columns=[_column("Field", "34%"), _column("Value", "66%")],
                rows=_metadata_rows(
                    report_context,
                    population,
                    is_global=is_global,
                    scope_labels=scope_labels,
                ),
            ),
            "population": population,
            "population_text": _count_text(population),
            "college_summary": _college_summary_table(groups, population) if groups else None,
            "filters": _table(
                title="How the Selected Filters Apply",
                columns=[
                    _column("Filter", "16%"),
                    _column("Submitted Inventory Profile Population", "42%"),
                    _column(coverage_view["title"], "42%"),
                ],
                rows=_filter_rows(report_context, coverage, is_global=is_global),
            ),
            "coverage": coverage_view,
            "methodology": _methodology(
                methodology,
                str(coverage_view["note"]),
                population,
                appendix_note=appendix_note,
            ),
            "disclosure_warning_messages": _disclosure_messages(raw_warnings),
            "parts": parts,
            "income_legend": income_legend,
            "program_population": program_population,
            "appendix": appendix,
            "empty_message": (
                "No submitted Individual Inventories matched the selected profile filters. "
                "Distribution tables are omitted and no percentages are calculated for an empty "
                "population."
                if population == 0
                else None
            ),
        },
        "document_pdf_footer_label": _footer_label(report_context),
    }


def _footer_label(report_context: dict[str, object]) -> str:
    academic_year = _require_dict(report_context.get("academic_year"), "Academic Year context")
    return (
        f"Student Profile Report · Academic Year {academic_year.get('label') or ''} · "
        f"Generated {_institutional_timestamp(report_context.get('generated_at'))}"
    )


def student_profiling_pdf_filename(academic_year_label: str) -> str:
    safe_year = safe_report_filename_part(
        academic_year_label,
        fallback="academic-year",
    )
    return f"student-profile-{safe_year}.pdf"


def render_student_profiling_pdf(
    *,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
    access_scope: ReportAccessScope,
) -> StudentProfilingPdfResult:
    report = build_student_profiling_report(
        academic_year_id=academic_year_id,
        campus_id=campus_id,
        college_id=college_id,
        program_id=program_id,
        year_level=year_level,
        access_scope=access_scope,
    )
    context = build_student_profiling_print_context(report)
    academic_year = _require_dict(
        _require_dict(report.get("report_context"), "report context").get("academic_year"),
        "Academic Year context",
    )
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
        release_context=student_profiling_release_context(report),
    )
