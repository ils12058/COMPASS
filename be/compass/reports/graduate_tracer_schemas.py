"""Typed public schemas for Graduate Tracer aggregate reporting."""

from __future__ import annotations

from datetime import date, datetime

from .schemas import StrictSchema


class GraduateTracerDistributionRow(StrictSchema):
    key: str
    label: str
    count: int
    percentage: float


class GraduateTracerDistributionSection(StrictSchema):
    key: str
    label: str
    denominator: int
    denominator_label: str
    multiple_selection: bool
    rows: list[GraduateTracerDistributionRow]


class GraduateTracerReportContext(StrictSchema):
    instrument_schema_version: int
    submitted_from: date | None
    submitted_to: date | None
    submitted_response_count: int
    generated_at: datetime


class GraduateTracerMethodology(StrictSchema):
    population: str
    drafts: str
    submission_period: str
    response_rate: str
    academic_grouping: str
    free_text: str
    multi_select: str


class GraduateTracerSections(StrictSchema):
    sex: GraduateTracerDistributionSection
    civil_status: GraduateTracerDistributionSection
    region_of_origin: GraduateTracerDistributionSection
    residence_location: GraduateTracerDistributionSection
    current_employment_state: GraduateTracerDistributionSection
    unemployment_reasons: GraduateTracerDistributionSection
    present_employment_status: GraduateTracerDistributionSection
    employer_business_line: GraduateTracerDistributionSection
    place_of_work: GraduateTracerDistributionSection
    first_job_after_college: GraduateTracerDistributionSection
    reasons_for_staying_on_job: GraduateTracerDistributionSection
    first_job_related_to_course: GraduateTracerDistributionSection
    first_job_duration: GraduateTracerDistributionSection
    first_job_source: GraduateTracerDistributionSection
    time_to_first_job: GraduateTracerDistributionSection
    first_job_level: GraduateTracerDistributionSection
    current_job_level: GraduateTracerDistributionSection
    initial_gross_monthly_earning: GraduateTracerDistributionSection
    curriculum_relevant_to_first_job: GraduateTracerDistributionSection
    useful_competencies: GraduateTracerDistributionSection


class GraduateTracerReportResponse(StrictSchema):
    report_context: GraduateTracerReportContext
    methodology: GraduateTracerMethodology
    sections: GraduateTracerSections
