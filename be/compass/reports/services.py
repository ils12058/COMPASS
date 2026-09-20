"""Read-only Student Profiling aggregate selectors and deterministic calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.db.models import Count, Q
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.inventory.models import (
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
from compass.inventory.services import (
    InvalidInventoryInput,
    ParentIncomeBand,
    classify_parent_annual_income,
    combine_parent_annual_income,
    derive_age_on,
)
from compass.organization.academic_years import AcademicYearConflict, require_current_academic_year
from compass.organization.models import AcademicYear, Campus, College, Program
from compass.student_support.models import ParentLifeStatus, StudentSupportProfile

LEGACY_KEY = "NOT_RECORDED_LEGACY"
LEGACY_LABEL = "Not recorded / legacy"
LEGACY_PROGRAM_KEY = "legacy:not-recorded"
NOT_SPECIFIED_KEY = "NOT_SPECIFIED"

PROFILE_METHODOLOGY = (
    "Student profile statistics are derived from submitted Individual Inventories for the "
    "selected Academic Year and applied profile filters. Students without a submitted Individual "
    "Inventory may not have sufficient Inventory-based academic context, such as Program or Year "
    "Level, to be attributed to those filters. Without Individual Inventory is presented "
    "separately "
    "as a coverage indicator and must not be interpreted as Program- or Year-Level-specific unless "
    "an authoritative source for that classification exists."
)
CURRENT_COVERAGE_NOTE = (
    "Current-Academic-Year coverage compares active CURRENT Student accounts with their Inventory "
    "state. Campus and College coverage filters, when supplied, use current Guidance "
    "StudentAffiliation; Program and Year Level do not classify MISSING Students."
)
HISTORICAL_COVERAGE_NOTE = (
    "Historical Academic Years can report existing submitted and draft Inventories, but "
    "authoritative "
    "MISSING coverage cannot be reconstructed because COMPASS has no historical enrollment or "
    "eligibility roster for that Academic Year."
)


class ReportError(RuntimeError):
    pass


class ReportNotFound(ReportError):
    pass


class ReportConfigurationConflict(ReportError):
    pass


class InvalidReportFilter(ReportError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedReportFilters:
    academic_year: AcademicYear
    campus: Campus | None
    college: College | None
    program: Program | None
    year_level: int | None


def calculate_percentage(count: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0.00")
    return (Decimal(count) * Decimal("100") / Decimal(denominator)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def year_level_label(year_level: int) -> str:
    if type(year_level) is not int or not 1 <= year_level <= 10:
        raise InvalidReportFilter("year_level must be between 1 and 10.")
    remainder = year_level % 100
    if 10 <= remainder <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(year_level % 10, "th")
    return f"{year_level}{suffix} Year"


def _organization_reference(item) -> dict[str, object] | None:
    if item is None:
        return None
    return {"id": item.pk, "code": item.code, "name": item.name}


def resolve_report_filters(
    *,
    academic_year_id: UUID | None,
    campus_id: UUID | None,
    college_id: UUID | None,
    program_id: UUID | None,
    year_level: int | None,
) -> ResolvedReportFilters:
    if academic_year_id is None:
        try:
            academic_year = require_current_academic_year()
        except AcademicYearConflict as exc:
            raise ReportConfigurationConflict(str(exc)) from exc
    else:
        academic_year = AcademicYear.objects.filter(pk=academic_year_id).first()
        if academic_year is None:
            raise ReportNotFound("The requested Academic Year was not found.")

    campus = Campus.objects.filter(pk=campus_id).first() if campus_id is not None else None
    if campus_id is not None and campus is None:
        raise ReportNotFound("The requested Campus was not found.")

    college = (
        College.objects.select_related("campus").filter(pk=college_id).first()
        if college_id is not None
        else None
    )
    if college_id is not None and college is None:
        raise ReportNotFound("The requested College was not found.")

    program = (
        Program.objects.select_related("college__campus").filter(pk=program_id).first()
        if program_id is not None
        else None
    )
    if program_id is not None and program is None:
        raise ReportNotFound("The requested Program was not found.")

    if year_level is not None:
        year_level_label(year_level)

    if campus is not None and college is not None and college.campus_id != campus.pk:
        raise InvalidReportFilter("The selected College does not belong to the selected Campus.")
    if college is not None and program is not None and program.college_id != college.pk:
        raise InvalidReportFilter("The selected Program does not belong to the selected College.")
    if campus is not None and program is not None and program.college.campus_id != campus.pk:
        raise InvalidReportFilter("The selected Program does not belong to the selected Campus.")

    return ResolvedReportFilters(
        academic_year=academic_year,
        campus=campus,
        college=college,
        program=program,
        year_level=year_level,
    )


def _profile_queryset(filters: ResolvedReportFilters):
    queryset = StudentInventory.objects.filter(
        academic_year_id=filters.academic_year.pk,
        submitted_at__isnull=False,
    )
    if filters.campus is not None:
        queryset = queryset.filter(program__college__campus_id=filters.campus.pk)
    if filters.college is not None:
        queryset = queryset.filter(program__college_id=filters.college.pk)
    if filters.program is not None:
        queryset = queryset.filter(program_id=filters.program.pk)
    if filters.year_level is not None:
        queryset = queryset.filter(year_level=filters.year_level)
    return queryset


def _program_key(program_id: UUID | None) -> str:
    return LEGACY_PROGRAM_KEY if program_id is None else f"program:{program_id}"


def _program_columns(base_queryset) -> tuple[list[dict[str, object]], dict[str, int]]:
    rows = list(
        base_queryset.values(
            "program_id",
            "program__code",
            "program__name",
            "program__college_id",
            "program__college__code",
            "program__college__name",
            "program__college__campus_id",
            "program__college__campus__code",
            "program__college__campus__name",
        )
        .annotate(total=Count("id"))
        .order_by(
            "program__college__campus__code",
            "program__college__code",
            "program__code",
            "program_id",
        )
    )
    columns: list[dict[str, object]] = []
    totals: dict[str, int] = {}
    legacy_total = 0
    for row in rows:
        program_id = row["program_id"]
        total = int(row["total"])
        if program_id is None:
            legacy_total += total
            continue
        key = _program_key(program_id)
        totals[key] = total
        columns.append(
            {
                "key": key,
                "program_id": program_id,
                "code": row["program__code"],
                "name": row["program__name"],
                "college": {
                    "id": row["program__college_id"],
                    "code": row["program__college__code"],
                    "name": row["program__college__name"],
                },
                "campus": {
                    "id": row["program__college__campus_id"],
                    "code": row["program__college__campus__code"],
                    "name": row["program__college__campus__name"],
                },
                "is_legacy": False,
            }
        )
    if legacy_total:
        totals[LEGACY_PROGRAM_KEY] = legacy_total
        columns.append(
            {
                "key": LEGACY_PROGRAM_KEY,
                "program_id": None,
                "code": None,
                "name": LEGACY_LABEL,
                "college": None,
                "campus": None,
                "is_legacy": True,
            }
        )
    return columns, totals


def _program_count_rows(
    columns: list[dict[str, object]],
    counts: dict[str, int],
) -> list[dict[str, object]]:
    return [
        {"program_key": str(column["key"]), "count": int(counts.get(str(column["key"]), 0))}
        for column in columns
    ]


def _row(
    *,
    key: str,
    label: str,
    denominator: int,
    counts: dict[str, int],
    columns: list[dict[str, object]],
) -> dict[str, object]:
    total = sum(counts.values())
    return {
        "key": key,
        "label": label,
        "total_count": total,
        "percentage": calculate_percentage(total, denominator),
        "program_counts": _program_count_rows(columns, counts),
    }


def _scalar_section(
    *,
    base_queryset,
    field: str,
    choices,
    key: str,
    label: str,
    denominator: int,
    columns: list[dict[str, object]],
) -> dict[str, object]:
    choice_pairs = list(choices)
    labels = {value: choice_label for value, choice_label in choice_pairs}
    counts: dict[str, dict[str, int]] = {value: {} for value, _ in choice_pairs}
    counts[LEGACY_KEY] = {}
    for result in base_queryset.values(field, "program_id").annotate(total=Count("id")):
        raw = result[field]
        category = raw if raw in labels else LEGACY_KEY
        program_key = _program_key(result["program_id"])
        counts[category][program_key] = counts[category].get(program_key, 0) + int(result["total"])
    rows = [
        _row(
            key=value,
            label=choice_label,
            denominator=denominator,
            counts=counts[value],
            columns=columns,
        )
        for value, choice_label in choice_pairs
    ]
    rows.append(
        _row(
            key=LEGACY_KEY,
            label=LEGACY_LABEL,
            denominator=denominator,
            counts=counts[LEGACY_KEY],
            columns=columns,
        )
    )
    return {"key": key, "label": label, "denominator": denominator, "rows": rows}


def _age_section(
    *,
    base_queryset,
    denominator: int,
    columns: list[dict[str, object]],
) -> dict[str, object]:
    counts: dict[str, dict[str, int]] = {}
    observed_ages: set[int] = set()
    legacy_seen = False
    for result in base_queryset.values("date_of_birth", "submitted_at", "program_id"):
        dob = result["date_of_birth"]
        submitted_at = result["submitted_at"]
        if dob is None or submitted_at is None:
            category = LEGACY_KEY
            legacy_seen = True
        else:
            age = derive_age_on(date_of_birth=dob, on_date=submitted_at.date())
            if age < 0:
                category = LEGACY_KEY
                legacy_seen = True
            else:
                category = str(age)
                observed_ages.add(age)
        program_key = _program_key(result["program_id"])
        bucket = counts.setdefault(category, {})
        bucket[program_key] = bucket.get(program_key, 0) + 1
    rows = [
        _row(
            key=str(age),
            label=str(age),
            denominator=denominator,
            counts=counts.get(str(age), {}),
            columns=columns,
        )
        for age in sorted(observed_ages)
    ]
    if legacy_seen:
        rows.append(
            _row(
                key=LEGACY_KEY,
                label=LEGACY_LABEL,
                denominator=denominator,
                counts=counts.get(LEGACY_KEY, {}),
                columns=columns,
            )
        )
    return {
        "key": "age",
        "label": "Distribution of Students based on Age",
        "denominator": denominator,
        "rows": rows,
    }


def _family_section(
    *,
    base_queryset,
    program_totals: dict[str, int],
    family_kind: str,
    field: str,
    choices,
    key: str,
    label: str,
    denominator: int,
    columns: list[dict[str, object]],
) -> dict[str, object]:
    choice_pairs = list(choices)
    labels = {value: choice_label for value, choice_label in choice_pairs}
    counts: dict[str, dict[str, int]] = {value: {} for value, _ in choice_pairs}
    counts[LEGACY_KEY] = {}
    observed_by_program: dict[str, int] = {}
    child_rows = (
        InventoryFamilyMember.objects.filter(
            inventory_id__in=base_queryset.values("id"),
            kind=family_kind,
        )
        .values(field, "inventory__program_id")
        .annotate(total=Count("id"))
    )
    for result in child_rows:
        program_key = _program_key(result["inventory__program_id"])
        total = int(result["total"])
        observed_by_program[program_key] = observed_by_program.get(program_key, 0) + total
        raw = result[field]
        category = raw if raw in labels else LEGACY_KEY
        counts[category][program_key] = counts[category].get(program_key, 0) + total
    for program_key, base_total in program_totals.items():
        missing = base_total - observed_by_program.get(program_key, 0)
        if missing > 0:
            counts[LEGACY_KEY][program_key] = counts[LEGACY_KEY].get(program_key, 0) + missing
    rows = [
        _row(
            key=value,
            label=choice_label,
            denominator=denominator,
            counts=counts[value],
            columns=columns,
        )
        for value, choice_label in choice_pairs
    ]
    rows.append(
        _row(
            key=LEGACY_KEY,
            label=LEGACY_LABEL,
            denominator=denominator,
            counts=counts[LEGACY_KEY],
            columns=columns,
        )
    )
    return {"key": key, "label": label, "denominator": denominator, "rows": rows}


def _support_profile_section(
    *,
    base_queryset,
    program_totals: dict[str, int],
    field: str,
    choices,
    key: str,
    label: str,
    denominator: int,
    columns: list[dict[str, object]],
) -> dict[str, object]:
    choice_pairs = list(choices)
    labels = {value: choice_label for value, choice_label in choice_pairs}
    counts: dict[str, dict[str, int]] = {value: {} for value, _ in choice_pairs}
    counts[LEGACY_KEY] = {}
    observed_by_program: dict[str, int] = {}

    rows = (
        StudentSupportProfile.objects.filter(
            inventory_id__in=base_queryset.values("id"),
        )
        .values(field, "inventory__program_id")
        .annotate(total=Count("id"))
    )
    for result in rows:
        program_key = _program_key(result["inventory__program_id"])
        total = int(result["total"])
        observed_by_program[program_key] = observed_by_program.get(program_key, 0) + total
        raw = result[field]
        category = raw if raw in labels else LEGACY_KEY
        counts[category][program_key] = counts[category].get(program_key, 0) + total

    for program_key, base_total in program_totals.items():
        missing = base_total - observed_by_program.get(program_key, 0)
        if missing > 0:
            counts[LEGACY_KEY][program_key] = counts[LEGACY_KEY].get(program_key, 0) + missing

    rows_out = [
        _row(
            key=value,
            label=choice_label,
            denominator=denominator,
            counts=counts[value],
            columns=columns,
        )
        for value, choice_label in choice_pairs
    ]
    rows_out.append(
        _row(
            key=LEGACY_KEY,
            label=LEGACY_LABEL,
            denominator=denominator,
            counts=counts[LEGACY_KEY],
            columns=columns,
        )
    )
    return {"key": key, "label": label, "denominator": denominator, "rows": rows_out}


def _geography_section(
    *,
    base_queryset,
    program_totals: dict[str, int],
    denominator: int,
    columns: list[dict[str, object]],
) -> dict[str, object]:
    counts: dict[str, dict[str, int]] = {}
    metadata: dict[str, dict[str, str | None]] = {}
    observed_by_program: dict[str, int] = {}
    rows = (
        InventoryGeographicLocation.objects.filter(
            inventory_id__in=base_queryset.values("id"),
            kind=GeographicLocationKind.CURRENT,
        )
        .values(
            "not_specified",
            "city_municipality_psgc_code",
            "city_municipality_name_snapshot",
            "province_psgc_code",
            "province_name_snapshot",
            "region_psgc_code",
            "region_name_snapshot",
            "inventory__program_id",
        )
        .order_by(
            "city_municipality_psgc_code",
            "city_municipality_name_snapshot",
            "province_psgc_code",
            "region_psgc_code",
        )
    )
    for result in rows:
        program_key = _program_key(result["inventory__program_id"])
        observed_by_program[program_key] = observed_by_program.get(program_key, 0) + 1
        if result["not_specified"]:
            category = NOT_SPECIFIED_KEY
            metadata.setdefault(
                category,
                {
                    "label": "Not specified",
                    "city_municipality_psgc_code": None,
                    "province_psgc_code": None,
                    "province_name": None,
                    "region_psgc_code": None,
                    "region_name": None,
                },
            )
        elif result["city_municipality_psgc_code"] and result["city_municipality_name_snapshot"]:
            code = result["city_municipality_psgc_code"]
            category = f"CITY_MUNICIPALITY:{code}"
            metadata.setdefault(
                category,
                {
                    "label": result["city_municipality_name_snapshot"],
                    "city_municipality_psgc_code": code,
                    "province_psgc_code": result["province_psgc_code"] or None,
                    "province_name": result["province_name_snapshot"] or None,
                    "region_psgc_code": result["region_psgc_code"] or None,
                    "region_name": result["region_name_snapshot"] or None,
                },
            )
        else:
            category = LEGACY_KEY
            metadata.setdefault(
                category,
                {
                    "label": LEGACY_LABEL,
                    "city_municipality_psgc_code": None,
                    "province_psgc_code": None,
                    "province_name": None,
                    "region_psgc_code": None,
                    "region_name": None,
                },
            )
        bucket = counts.setdefault(category, {})
        bucket[program_key] = bucket.get(program_key, 0) + 1
    for program_key, base_total in program_totals.items():
        missing = base_total - observed_by_program.get(program_key, 0)
        if missing > 0:
            bucket = counts.setdefault(LEGACY_KEY, {})
            bucket[program_key] = bucket.get(program_key, 0) + missing
            metadata.setdefault(
                LEGACY_KEY,
                {
                    "label": LEGACY_LABEL,
                    "city_municipality_psgc_code": None,
                    "province_psgc_code": None,
                    "province_name": None,
                    "region_psgc_code": None,
                    "region_name": None,
                },
            )

    city_keys = sorted(
        (category for category in counts if category.startswith("CITY_MUNICIPALITY:")),
        key=lambda category: (
            str(metadata[category]["label"]),
            str(metadata[category]["city_municipality_psgc_code"]),
        ),
    )
    ordered_keys = city_keys
    if NOT_SPECIFIED_KEY in counts:
        ordered_keys.append(NOT_SPECIFIED_KEY)
    if LEGACY_KEY in counts:
        ordered_keys.append(LEGACY_KEY)

    report_rows: list[dict[str, object]] = []
    for category in ordered_keys:
        item = _row(
            key=category,
            label=str(metadata[category]["label"]),
            denominator=denominator,
            counts=counts[category],
            columns=columns,
        )
        item.update(
            {
                "city_municipality_psgc_code": metadata[category]["city_municipality_psgc_code"],
                "province_psgc_code": metadata[category]["province_psgc_code"],
                "province_name": metadata[category]["province_name"],
                "region_psgc_code": metadata[category]["region_psgc_code"],
                "region_name": metadata[category]["region_name"],
            }
        )
        report_rows.append(item)
    return {
        "key": "city_municipality",
        "label": "Distribution of Students based on City / Municipality",
        "denominator": denominator,
        "rows": report_rows,
    }


def _income_section(
    *,
    base_queryset,
    denominator: int,
    columns: list[dict[str, object]],
) -> dict[str, object]:
    inventory_program = dict(base_queryset.values_list("id", "program_id"))
    parents: dict[UUID, dict[str, tuple[str | None, Decimal | None]]] = {}
    for result in InventoryFamilyMember.objects.filter(
        inventory_id__in=inventory_program,
        kind__in=[FamilyMemberKind.FATHER, FamilyMemberKind.MOTHER],
    ).values(
        "inventory_id",
        "kind",
        "annual_income_status",
        "annual_income_previous_year",
    ):
        parents.setdefault(result["inventory_id"], {})[result["kind"]] = (
            result["annual_income_status"],
            result["annual_income_previous_year"],
        )

    ordered_bands = [
        ParentIncomeBand.POOR,
        ParentIncomeBand.LOW_INCOME,
        ParentIncomeBand.LOWER_MIDDLE_INCOME,
        ParentIncomeBand.MIDDLE_MIDDLE_INCOME,
        ParentIncomeBand.UPPER_MIDDLE_INCOME,
        ParentIncomeBand.UPPER_INCOME,
        ParentIncomeBand.RICH,
        ParentIncomeBand.NONE,
        ParentIncomeBand.NOT_SPECIFIED,
    ]
    labels = {
        ParentIncomeBand.POOR: "Poor",
        ParentIncomeBand.LOW_INCOME: "Low Income",
        ParentIncomeBand.LOWER_MIDDLE_INCOME: "Lower Middle Income",
        ParentIncomeBand.MIDDLE_MIDDLE_INCOME: "Middle Middle Income",
        ParentIncomeBand.UPPER_MIDDLE_INCOME: "Upper Middle Income",
        ParentIncomeBand.UPPER_INCOME: "Upper Income",
        ParentIncomeBand.RICH: "Rich",
        ParentIncomeBand.NONE: "None",
        ParentIncomeBand.NOT_SPECIFIED: "Not specified",
    }
    counts: dict[str, dict[str, int]] = {str(band): {} for band in ordered_bands}
    counts[LEGACY_KEY] = {}
    for inventory_id, program_id in inventory_program.items():
        program_key = _program_key(program_id)
        pair = parents.get(inventory_id, {})
        father = pair.get(FamilyMemberKind.FATHER)
        mother = pair.get(FamilyMemberKind.MOTHER)
        if father is None or mother is None or father[0] is None or mother[0] is None:
            category = LEGACY_KEY
        else:
            try:
                combined = combine_parent_annual_income(
                    father_status=father[0],
                    father_amount=father[1],
                    mother_status=mother[0],
                    mother_amount=mother[1],
                )
                category = str(classify_parent_annual_income(combined))
            except InvalidInventoryInput:
                category = LEGACY_KEY
        bucket = counts.setdefault(category, {})
        bucket[program_key] = bucket.get(program_key, 0) + 1

    report_rows = [
        _row(
            key=str(band),
            label=labels[band],
            denominator=denominator,
            counts=counts[str(band)],
            columns=columns,
        )
        for band in ordered_bands
    ]
    report_rows.append(
        _row(
            key=LEGACY_KEY,
            label=LEGACY_LABEL,
            denominator=denominator,
            counts=counts[LEGACY_KEY],
            columns=columns,
        )
    )
    return {
        "key": "parent_annual_income",
        "label": "Distribution of Students based on Parent Annual Income",
        "denominator": denominator,
        "rows": report_rows,
    }


def _coverage(filters: ResolvedReportFilters) -> dict[str, object]:
    ignored = []
    if filters.program is not None:
        ignored.append("program_id")
    if filters.year_level is not None:
        ignored.append("year_level")

    if filters.academic_year.is_current:
        eligible = User.objects.filter(
            is_active=True,
            role__code="STUDENT",
            student_lifecycle_status=StudentLifecycleStatus.CURRENT,
        )
        applied = ["academic_year_id"]
        if filters.campus is not None:
            eligible = eligible.filter(
                organization_student_affiliation__college__campus_id=filters.campus.pk
            )
            applied.append("campus_id")
        if filters.college is not None:
            eligible = eligible.filter(
                organization_student_affiliation__college_id=filters.college.pk
            )
            applied.append("college_id")
        eligible_ids = list(eligible.distinct().values_list("id", flat=True))
        eligible_count = len(eligible_ids)
        inventory_counts = StudentInventory.objects.filter(
            academic_year_id=filters.academic_year.pk,
            student_id__in=eligible_ids,
        ).aggregate(
            submitted=Count("id", filter=Q(submitted_at__isnull=False)),
            draft=Count("id", filter=Q(submitted_at__isnull=True)),
        )
        submitted_count = int(inventory_counts["submitted"] or 0)
        draft_count = int(inventory_counts["draft"] or 0)
        return {
            "mode": "CURRENT",
            "eligible_student_count": eligible_count,
            "submitted_count": submitted_count,
            "draft_count": draft_count,
            "missing_count": max(eligible_count - submitted_count - draft_count, 0),
            "applied_filters": applied,
            "ignored_filters": ignored,
            "scope_note": CURRENT_COVERAGE_NOTE,
        }

    inventory_counts = StudentInventory.objects.filter(
        academic_year_id=filters.academic_year.pk
    ).aggregate(
        submitted=Count("id", filter=Q(submitted_at__isnull=False)),
        draft=Count("id", filter=Q(submitted_at__isnull=True)),
    )
    historical_ignored = ignored[:]
    if filters.campus is not None:
        historical_ignored.append("campus_id")
    if filters.college is not None:
        historical_ignored.append("college_id")
    return {
        "mode": "HISTORICAL_LIMITED",
        "eligible_student_count": None,
        "submitted_count": int(inventory_counts["submitted"] or 0),
        "draft_count": int(inventory_counts["draft"] or 0),
        "missing_count": None,
        "applied_filters": ["academic_year_id"],
        "ignored_filters": historical_ignored,
        "scope_note": HISTORICAL_COVERAGE_NOTE,
    }


def build_student_profiling_report(
    *,
    academic_year_id: UUID | None = None,
    campus_id: UUID | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
) -> dict[str, object]:
    filters = resolve_report_filters(
        academic_year_id=academic_year_id,
        campus_id=campus_id,
        college_id=college_id,
        program_id=program_id,
        year_level=year_level,
    )
    population_ids = list(_profile_queryset(filters).values_list("id", flat=True))
    # Submitted Inventories are immutable. Freeze report membership once so all section queries
    # describe the same logical population even if another submission commits mid-generation.
    base_queryset = StudentInventory.objects.filter(pk__in=population_ids)
    denominator = len(population_ids)
    columns, program_totals = _program_columns(base_queryset)

    sections = {
        "sex": _scalar_section(
            base_queryset=base_queryset,
            field="sex",
            choices=Sex.choices,
            key="sex",
            label="Distribution of Students based on Sex",
            denominator=denominator,
            columns=columns,
        ),
        "age": _age_section(
            base_queryset=base_queryset,
            denominator=denominator,
            columns=columns,
        ),
        "civil_status": _scalar_section(
            base_queryset=base_queryset,
            field="civil_status_category",
            choices=CivilStatusCategory.choices,
            key="civil_status",
            label="Distribution of Students based on Civil Status",
            denominator=denominator,
            columns=columns,
        ),
        "physical_disadvantage": _scalar_section(
            base_queryset=base_queryset,
            field="pwd_status",
            choices=PWDStatus.choices,
            key="physical_disadvantage",
            label="Distribution of Students based on PWD Status",
            denominator=denominator,
            columns=columns,
        ),
        "current_religion": _scalar_section(
            base_queryset=base_queryset,
            field="current_religion_category",
            choices=CurrentReligionCategory.choices,
            key="current_religion",
            label="Distribution of Students based on Current Religion",
            denominator=denominator,
            columns=columns,
        ),
        "mother_life_status": _support_profile_section(
            base_queryset=base_queryset,
            program_totals=program_totals,
            field="mother_life_status",
            choices=ParentLifeStatus.choices,
            key="mother_life_status",
            label="Distribution of Students based on Mother Life Status",
            denominator=denominator,
            columns=columns,
        ),
        "father_life_status": _support_profile_section(
            base_queryset=base_queryset,
            program_totals=program_totals,
            field="father_life_status",
            choices=ParentLifeStatus.choices,
            key="father_life_status",
            label="Distribution of Students based on Father Life Status",
            denominator=denominator,
            columns=columns,
        ),
        "parent_family_status": _scalar_section(
            base_queryset=base_queryset,
            field="parent_status_category",
            choices=ParentStatusCategory.choices,
            key="parent_family_status",
            label="Distribution of Students based on Parent Family Status",
            denominator=denominator,
            columns=columns,
        ),
        "city_municipality": _geography_section(
            base_queryset=base_queryset,
            program_totals=program_totals,
            denominator=denominator,
            columns=columns,
        ),
        "parent_annual_income": _income_section(
            base_queryset=base_queryset,
            denominator=denominator,
            columns=columns,
        ),
        "mother_occupation": _family_section(
            base_queryset=base_queryset,
            program_totals=program_totals,
            family_kind=FamilyMemberKind.MOTHER,
            field="occupation_category",
            choices=OccupationCategory.choices,
            key="mother_occupation",
            label="Distribution of Students based on Mother Occupation",
            denominator=denominator,
            columns=columns,
        ),
        "father_occupation": _family_section(
            base_queryset=base_queryset,
            program_totals=program_totals,
            family_kind=FamilyMemberKind.FATHER,
            field="occupation_category",
            choices=OccupationCategory.choices,
            key="father_occupation",
            label="Distribution of Students based on Father Occupation",
            denominator=denominator,
            columns=columns,
        ),
        "living_condition": _scalar_section(
            base_queryset=base_queryset,
            field="living_arrangement",
            choices=LivingArrangement.choices,
            key="living_condition",
            label="Distribution of Students based on Living Condition",
            denominator=denominator,
            columns=columns,
        ),
    }

    historical_note = None if filters.academic_year.is_current else HISTORICAL_COVERAGE_NOTE
    return {
        "report_context": {
            "academic_year": {
                "id": filters.academic_year.pk,
                "label": filters.academic_year.label,
                "is_current": filters.academic_year.is_current,
            },
            "campus": _organization_reference(filters.campus),
            "college": _organization_reference(filters.college),
            "program": _organization_reference(filters.program),
            "year_level": filters.year_level,
            "year_level_label": (
                year_level_label(filters.year_level) if filters.year_level is not None else None
            ),
            "submitted_inventory_count": denominator,
            "generated_at": timezone.now(),
        },
        "methodology": {
            "profile_population_note": PROFILE_METHODOLOGY,
            "coverage_note": CURRENT_COVERAGE_NOTE,
            "historical_coverage_note": historical_note,
        },
        "program_columns": columns,
        "inventory_coverage": _coverage(filters),
        "sections": sections,
    }


def student_profiling_release_context(report: dict[str, object]) -> dict[str, object]:
    """Return only safe resolved filter context for release auditing."""

    report_context = report.get("report_context")
    if not isinstance(report_context, dict):
        raise ReportConfigurationConflict("The Student Profiling report context is invalid.")

    academic_year = report_context.get("academic_year")
    if not isinstance(academic_year, dict) or academic_year.get("id") is None:
        raise ReportConfigurationConflict("The Student Profiling Academic Year context is invalid.")

    def organization_values(name: str) -> tuple[str | None, str | None]:
        item = report_context.get(name)
        if item is None:
            return None, None
        if not isinstance(item, dict):
            raise ReportConfigurationConflict(f"The Student Profiling {name} context is invalid.")
        item_id = item.get("id")
        item_code = item.get("code")
        return (
            str(item_id) if item_id is not None else None,
            str(item_code) if item_code is not None else None,
        )

    campus_id, campus_code = organization_values("campus")
    college_id, college_code = organization_values("college")
    program_id, program_code = organization_values("program")
    year_level = report_context.get("year_level")
    if year_level is not None and type(year_level) is not int:
        raise ReportConfigurationConflict("The Student Profiling Year Level context is invalid.")

    return {
        "academic_year_id": str(academic_year["id"]),
        "academic_year_label": str(academic_year.get("label") or ""),
        "campus_id": campus_id,
        "campus_code": campus_code,
        "college_id": college_id,
        "college_code": college_code,
        "program_id": program_id,
        "program_code": program_code,
        "year_level": year_level,
    }
