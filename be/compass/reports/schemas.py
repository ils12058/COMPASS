"""Typed public schemas for Student Profiling aggregate reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict


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


class ProgramColumn(StrictSchema):
    key: str
    program_id: UUID | None
    code: str | None
    name: str
    college: OrganizationReference | None
    campus: OrganizationReference | None
    is_legacy: bool


class ProgramCount(StrictSchema):
    program_key: str
    count: int


class DistributionRow(StrictSchema):
    key: str
    label: str
    total_count: int
    percentage: float
    program_counts: list[ProgramCount]


class DistributionSection(StrictSchema):
    key: str
    label: str
    denominator: int
    rows: list[DistributionRow]


class GeographicDistributionRow(DistributionRow):
    city_municipality_psgc_code: str | None
    province_psgc_code: str | None
    province_name: str | None
    region_psgc_code: str | None
    region_name: str | None


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
    generated_at: datetime


class InventoryCoverage(StrictSchema):
    mode: CoverageModeValue
    eligible_student_count: int | None
    submitted_count: int
    draft_count: int
    missing_count: int | None
    applied_filters: list[str]
    ignored_filters: list[str]
    scope_note: str


class Methodology(StrictSchema):
    profile_population_note: str
    coverage_note: str
    historical_coverage_note: str | None


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
    program_columns: list[ProgramColumn]
    inventory_coverage: InventoryCoverage
    sections: StudentProfilingSections
