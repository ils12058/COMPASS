"""Typed public schemas for Student Profiling aggregate reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict

from .policy import ReportDisclosureWarningCode


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CoverageModeValue(StrEnum):
    CURRENT = "CURRENT"
    HISTORICAL_LIMITED = "HISTORICAL_LIMITED"


class AcademicYearReference(StrictSchema):
    id: UUID
    label: str
    is_current: bool


class OrganizationReference(StrictSchema):
    id: UUID
    code: str
    name: str


class ReportScopeCollege(StrictSchema):
    id: UUID
    code: str
    name: str
    campus: OrganizationReference


class ReportScopeResponse(StrictSchema):
    is_global: bool
    colleges: list[ReportScopeCollege]


class ProgramColumn(StrictSchema):
    key: str
    program_id: UUID
    code: str
    name: str
    submitted_inventory_count: int
    college: OrganizationReference
    campus: OrganizationReference


class ProgramCount(StrictSchema):
    program_key: str
    count: int


class ReportDisclosureWarning(StrictSchema):
    code: ReportDisclosureWarningCode
    message: str


class DistributionRow(StrictSchema):
    key: str
    label: str
    total_count: int
    percentage: float | None
    program_counts: list[ProgramCount]


class DistributionSection(StrictSchema):
    key: str
    label: str
    denominator: int
    rows: list[DistributionRow]


class GeographicDistributionRow(DistributionRow):
    city_municipality_psgc_code: str
    province_psgc_code: str | None
    province_name: str | None
    region_psgc_code: str
    region_name: str


class GeographicDistributionSection(StrictSchema):
    key: str
    label: str
    denominator: int
    rows: list[GeographicDistributionRow]


class ReportContext(StrictSchema):
    academic_year: AcademicYearReference
    campus: OrganizationReference | None
    college: OrganizationReference | None
    program: OrganizationReference | None
    year_level: int | None
    year_level_label: str | None
    submitted_inventory_count: int
    reporting_scope: ReportScopeResponse
    generated_at: datetime


class PopulationReconciliation(StrictSchema):
    profile_submitted_count: int
    coverage_submitted_count: int
    in_both_count: int
    profile_only_count: int
    coverage_only_count: int


class AcademicAlignment(StrictSchema):
    current_student_count: int | None
    current_with_placement_count: int | None
    current_without_placement_count: int | None
    submitted_inventory_count: int
    submitted_with_program_count: int
    submitted_without_program_count: int
    placement_program_match_count: int | None
    placement_program_mismatch_count: int | None
    precedence_note: str


class InventoryCoverage(StrictSchema):
    mode: CoverageModeValue
    eligible_student_count: int | None
    submitted_count: int
    draft_count: int
    missing_count: int | None
    applied_filters: list[str]
    ignored_filters: list[str]
    scope_note: str
    reconciliation: PopulationReconciliation
    academic_alignment: AcademicAlignment


class Methodology(StrictSchema):
    profile_population_note: str
    coverage_note: str
    historical_coverage_note: str | None
    access_scope_note: str


class StudentProfilingSections(StrictSchema):
    sex: DistributionSection
    age: DistributionSection
    civil_status: DistributionSection
    physical_disadvantage: DistributionSection
    current_religion: DistributionSection
    mother_life_status: DistributionSection
    father_life_status: DistributionSection
    parent_family_status: DistributionSection
    city_municipality: GeographicDistributionSection
    parent_annual_income: DistributionSection
    mother_occupation: DistributionSection
    father_occupation: DistributionSection
    living_condition: DistributionSection


class StudentProfilingReportResponse(StrictSchema):
    report_context: ReportContext
    methodology: Methodology
    disclosure_warnings: list[ReportDisclosureWarning]
    program_columns: list[ProgramColumn]
    inventory_coverage: InventoryCoverage
    sections: StudentProfilingSections
