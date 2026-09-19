"""Privacy-safe aggregate reporting over submitted Graduate Tracer Survey responses."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Q
from django.utils import timezone

from compass.graduate_tracer.models import (
    GTS_SCHEMA_VERSION,
    GraduateTracerResponse,
    GraduateTracerStatus,
    GTSBusinessLine,
    GTSCivilStatus,
    GTSEarningBracket,
    GTSEmploymentState,
    GTSFirstJobDuration,
    GTSFirstJobSource,
    GTSJobLevel,
    GTSPlaceOfWork,
    GTSPresentEmploymentStatus,
    GTSRegionOfOrigin,
    GTSResidenceLocation,
    GTSSex,
    GTSStayingReason,
    GTSUnemploymentReason,
    GTSUsefulCompetency,
)

NOT_RECORDED = "NOT_RECORDED"
NOT_RECORDED_LABEL = "Not recorded"

METHODOLOGY = {
    "population": "Submitted schema-v1 Graduate Tracer Survey responses in COMPASS.",
    "drafts": "Draft responses are excluded.",
    "submission_period": (
        "submitted_from and submitted_to filter response submission dates, not graduation cohorts."
    ),
    "response_rate": (
        "No response rate is calculated because COMPASS has no authoritative Graduate Tracer "
        "campaign or graduate-roster denominator."
    ),
    "academic_grouping": (
        "No Program, College, or Campus grouping is performed because the survey has no canonical "
        "historical academic-program binding."
    ),
    "free_text": "Free-text survey fields are not automatically classified or aggregated.",
    "multi_select": (
        "Multi-select percentages are respondent-selection rates and may sum above 100%."
    ),
}


class GraduateTracerReportError(RuntimeError):
    pass


class InvalidGraduateTracerReportFilter(GraduateTracerReportError):
    pass


def calculate_percentage(count: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0.00")
    return (Decimal(count) * Decimal("100") / Decimal(denominator)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _submission_boundary(value: date, *, following_day: bool = False) -> datetime:
    local_date = value + timedelta(days=1) if following_day else value
    return timezone.make_aware(
        datetime.combine(local_date, time.min),
        timezone.get_current_timezone(),
    )


def _base_queryset(*, submitted_from: date | None, submitted_to: date | None):
    if submitted_from is not None and submitted_to is not None:
        if submitted_from > submitted_to:
            raise InvalidGraduateTracerReportFilter(
                "submitted_from must be on or before submitted_to."
            )

    queryset = GraduateTracerResponse.objects.filter(
        status=GraduateTracerStatus.SUBMITTED,
        instrument_schema_version=GTS_SCHEMA_VERSION,
        submitted_at__isnull=False,
    )
    if submitted_from is not None:
        queryset = queryset.filter(submitted_at__gte=_submission_boundary(submitted_from))
    if submitted_to is not None:
        queryset = queryset.filter(
            submitted_at__lt=_submission_boundary(submitted_to, following_day=True)
        )
    return queryset


def _row(*, key: str, label: str, count: int, denominator: int) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "count": count,
        "percentage": calculate_percentage(count, denominator),
    }


def _section(
    *,
    key: str,
    label: str,
    denominator: int,
    denominator_label: str,
    multiple_selection: bool,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "denominator": denominator,
        "denominator_label": denominator_label,
        "multiple_selection": multiple_selection,
        "rows": rows,
    }


def _scalar_distribution(
    queryset,
    *,
    field: str,
    choices,
    key: str,
    label: str,
    denominator_label: str,
) -> dict[str, object]:
    denominator = queryset.count()
    choice_pairs = list(choices)
    values = [value for value, _label in choice_pairs]
    observed = {
        item[field]: int(item["total"])
        for item in queryset.values(field).annotate(total=Count("id"))
        if item[field] in values
    }
    rows = [
        _row(
            key=value,
            label=choice_label,
            count=observed.get(value, 0),
            denominator=denominator,
        )
        for value, choice_label in choice_pairs
    ]
    missing = queryset.exclude(**{f"{field}__in": values}).count()
    if missing:
        rows.append(
            _row(
                key=NOT_RECORDED,
                label=NOT_RECORDED_LABEL,
                count=missing,
                denominator=denominator,
            )
        )
    return _section(
        key=key,
        label=label,
        denominator=denominator,
        denominator_label=denominator_label,
        multiple_selection=False,
        rows=rows,
    )


def _boolean_distribution(
    queryset,
    *,
    field: str,
    key: str,
    label: str,
    denominator_label: str,
) -> dict[str, object]:
    denominator = queryset.count()
    observed = {
        item[field]: int(item["total"])
        for item in queryset.values(field).annotate(total=Count("id"))
    }
    rows = [
        _row(
            key="YES",
            label="Yes",
            count=observed.get(True, 0),
            denominator=denominator,
        ),
        _row(
            key="NO",
            label="No",
            count=observed.get(False, 0),
            denominator=denominator,
        ),
    ]
    missing = observed.get(None, 0)
    if missing:
        rows.append(
            _row(
                key=NOT_RECORDED,
                label=NOT_RECORDED_LABEL,
                count=missing,
                denominator=denominator,
            )
        )
    return _section(
        key=key,
        label=label,
        denominator=denominator,
        denominator_label=denominator_label,
        multiple_selection=False,
        rows=rows,
    )


def _multi_select_distribution(
    queryset,
    *,
    field: str,
    choices,
    key: str,
    label: str,
    denominator_label: str,
) -> dict[str, object]:
    denominator = queryset.count()
    choice_pairs = list(choices)
    values = [value for value, _label in choice_pairs]
    rows = []
    for value, choice_label in choice_pairs:
        count = queryset.filter(**{f"{field}__contains": [value]}).count()
        rows.append(
            _row(
                key=value,
                label=choice_label,
                count=count,
                denominator=denominator,
            )
        )

    malformed = queryset.filter(Q(**{field: []}) | ~Q(**{f"{field}__contained_by": values})).count()
    if malformed:
        rows.append(
            _row(
                key=NOT_RECORDED,
                label=NOT_RECORDED_LABEL,
                count=malformed,
                denominator=denominator,
            )
        )
    return _section(
        key=key,
        label=label,
        denominator=denominator,
        denominator_label=denominator_label,
        multiple_selection=True,
        rows=rows,
    )


def build_graduate_tracer_report(
    *,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
) -> dict[str, object]:
    base = _base_queryset(
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )
    all_label = "Submitted schema-v1 responses"
    employed = base.filter(current_employment_state=GTSEmploymentState.EMPLOYED)
    employed_label = "Employed respondents"
    unemployed = base.filter(
        current_employment_state__in=[
            GTSEmploymentState.NOT_EMPLOYED,
            GTSEmploymentState.NEVER_EMPLOYED,
        ]
    )
    first_job_yes = employed.filter(first_job_after_college=True)
    curriculum_relevant = employed.filter(curriculum_relevant_to_first_job=True)

    sections = {
        "sex": _scalar_distribution(
            base,
            field="sex",
            choices=GTSSex.choices,
            key="sex",
            label="Sex",
            denominator_label=all_label,
        ),
        "civil_status": _scalar_distribution(
            base,
            field="civil_status",
            choices=GTSCivilStatus.choices,
            key="civil_status",
            label="Civil Status",
            denominator_label=all_label,
        ),
        "region_of_origin": _scalar_distribution(
            base,
            field="region_of_origin",
            choices=GTSRegionOfOrigin.choices,
            key="region_of_origin",
            label="Region of Origin",
            denominator_label=all_label,
        ),
        "residence_location": _scalar_distribution(
            base,
            field="residence_location",
            choices=GTSResidenceLocation.choices,
            key="residence_location",
            label="Residence Location",
            denominator_label=all_label,
        ),
        "current_employment_state": _scalar_distribution(
            base,
            field="current_employment_state",
            choices=GTSEmploymentState.choices,
            key="current_employment_state",
            label="Current Employment State",
            denominator_label=all_label,
        ),
        "unemployment_reasons": _multi_select_distribution(
            unemployed,
            field="unemployment_reasons",
            choices=GTSUnemploymentReason.choices,
            key="unemployment_reasons",
            label="Unemployment Reasons",
            denominator_label="Not-employed and never-employed respondents",
        ),
        "present_employment_status": _scalar_distribution(
            employed,
            field="present_employment_status",
            choices=GTSPresentEmploymentStatus.choices,
            key="present_employment_status",
            label="Present Employment Status",
            denominator_label=employed_label,
        ),
        "employer_business_line": _scalar_distribution(
            employed,
            field="employer_business_line",
            choices=GTSBusinessLine.choices,
            key="employer_business_line",
            label="Employer Business Line",
            denominator_label=employed_label,
        ),
        "place_of_work": _scalar_distribution(
            employed,
            field="place_of_work",
            choices=GTSPlaceOfWork.choices,
            key="place_of_work",
            label="Place of Work",
            denominator_label=employed_label,
        ),
        "first_job_after_college": _boolean_distribution(
            employed,
            field="first_job_after_college",
            key="first_job_after_college",
            label="First Job After College",
            denominator_label=employed_label,
        ),
        "reasons_for_staying_on_job": _multi_select_distribution(
            first_job_yes,
            field="reasons_for_staying_on_job",
            choices=GTSStayingReason.choices,
            key="reasons_for_staying_on_job",
            label="Reasons for Staying on Current/First Job",
            denominator_label="Employed respondents whose first job after college is current",
        ),
        "first_job_related_to_course": _boolean_distribution(
            first_job_yes,
            field="first_job_related_to_course",
            key="first_job_related_to_course",
            label="First Job Related to Course",
            denominator_label="Employed respondents whose first job after college is current",
        ),
        "first_job_duration": _scalar_distribution(
            employed,
            field="first_job_duration",
            choices=GTSFirstJobDuration.choices,
            key="first_job_duration",
            label="First Job Duration",
            denominator_label=employed_label,
        ),
        "first_job_source": _scalar_distribution(
            employed,
            field="first_job_source",
            choices=GTSFirstJobSource.choices,
            key="first_job_source",
            label="First Job Source",
            denominator_label=employed_label,
        ),
        "time_to_first_job": _scalar_distribution(
            employed,
            field="time_to_first_job",
            choices=GTSFirstJobDuration.choices,
            key="time_to_first_job",
            label="Time to First Job",
            denominator_label=employed_label,
        ),
        "first_job_level": _scalar_distribution(
            employed,
            field="first_job_level",
            choices=GTSJobLevel.choices,
            key="first_job_level",
            label="First Job Level",
            denominator_label=employed_label,
        ),
        "current_job_level": _scalar_distribution(
            employed,
            field="current_job_level",
            choices=GTSJobLevel.choices,
            key="current_job_level",
            label="Current Job Level",
            denominator_label=employed_label,
        ),
        "initial_gross_monthly_earning": _scalar_distribution(
            employed,
            field="initial_gross_monthly_earning",
            choices=GTSEarningBracket.choices,
            key="initial_gross_monthly_earning",
            label="Initial Gross Monthly Earning",
            denominator_label=employed_label,
        ),
        "curriculum_relevant_to_first_job": _boolean_distribution(
            employed,
            field="curriculum_relevant_to_first_job",
            key="curriculum_relevant_to_first_job",
            label="Curriculum Relevance to First Job",
            denominator_label=employed_label,
        ),
        "useful_competencies": _multi_select_distribution(
            curriculum_relevant,
            field="useful_competencies",
            choices=GTSUsefulCompetency.choices,
            key="useful_competencies",
            label="Useful Competencies",
            denominator_label=(
                "Employed respondents reporting curriculum relevance to their first job"
            ),
        ),
    }
    return {
        "report_context": {
            "instrument_schema_version": GTS_SCHEMA_VERSION,
            "submitted_from": submitted_from,
            "submitted_to": submitted_to,
            "submitted_response_count": base.count(),
            "generated_at": timezone.now(),
        },
        "methodology": dict(METHODOLOGY),
        "sections": sections,
    }


def graduate_tracer_release_context(
    *,
    submitted_from: date | None,
    submitted_to: date | None,
) -> dict[str, object]:
    return {
        "instrument_schema_version": GTS_SCHEMA_VERSION,
        "submitted_from": submitted_from.isoformat() if submitted_from else None,
        "submitted_to": submitted_to.isoformat() if submitted_to else None,
    }


__all__ = [
    "GraduateTracerReportError",
    "InvalidGraduateTracerReportFilter",
    "METHODOLOGY",
    "NOT_RECORDED",
    "build_graduate_tracer_report",
    "calculate_percentage",
    "graduate_tracer_release_context",
]
