from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from django.core.management import call_command
from openpyxl import load_workbook

from compass.accounts.models import Role, StudentLifecycleStatus, User
from compass.graduate_tracer.models import (
    GTSBusinessLine,
    GTSEmploymentState,
    GTSPresentEmploymentStatus,
    GraduateTracerEducation,
    GraduateTracerResponse,
    GraduateTracerStatus,
)
from compass.reports.graduate_tracer_xlsx import (
    EMPTY_REPORT_MESSAGE,
    render_graduate_tracer_xlsx,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_student(email: str) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code="STUDENT"),
        first_name="Graduate",
        last_name="Workbook",
    )
    user.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def make_response(email: str, **values) -> GraduateTracerResponse:
    defaults = {
        "sex": "MALE",
        "civil_status": "SINGLE",
        "region_of_origin": "REGION_5",
        "residence_location": "MUNICIPALITY",
        "current_employment_state": GTSEmploymentState.NOT_EMPLOYED,
        "unemployment_reasons": ["NO_JOB_OPPORTUNITY"],
    }
    defaults.update(values)
    from django.utils import timezone

    return GraduateTracerResponse.objects.create(
        student=make_student(email),
        status=GraduateTracerStatus.SUBMITTED,
        submitted_at=timezone.now(),
        **defaults,
    )


def workbook_values(workbook) -> list[str]:
    values: list[str] = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    values.append(str(cell.value))
    return values


@pytest.mark.django_db
def test_graduate_tracer_xlsx_is_aggregate_only_safe_and_compact():
    sync_policy()
    sentinel = "SENTINEL-RAW-GTS-XLSX"
    item = make_response(
        "gts-xlsx-private@example.edu",
        name_snapshot=sentinel,
        permanent_address_snapshot=sentinel,
        present_occupation=sentinel,
        unemployment_other_reason=sentinel,
        curriculum_improvement_suggestions=sentinel,
    )
    GraduateTracerEducation.objects.create(
        response=item,
        position=1,
        degree_and_specialization=sentinel,
        college_or_university=sentinel,
        year_graduated=2026,
        honors_or_awards=sentinel,
    )
    make_response(
        "gts-xlsx-employed@example.edu",
        current_employment_state=GTSEmploymentState.EMPLOYED,
        unemployment_reasons=[],
        present_employment_status=GTSPresentEmploymentStatus.REGULAR_PERMANENT,
        employer_business_line=GTSBusinessLine.EDUCATION,
        place_of_work="LOCAL",
        first_job_after_college=False,
        first_job_duration="ONE_TO_SIX_MONTHS",
        first_job_source="ADVERTISEMENT",
        time_to_first_job="LESS_THAN_MONTH",
        first_job_level="PROFESSIONAL_TECHNICAL_SUPERVISORY",
        current_job_level="PROFESSIONAL_TECHNICAL_SUPERVISORY",
        initial_gross_monthly_earning="FROM_15000_TO_LT_20000",
        curriculum_relevant_to_first_job=False,
    )

    result = render_graduate_tracer_xlsx()
    assert result.xlsx_bytes.startswith(b"PK")
    assert result.filename == "graduate-tracer-schema-v1.xlsx"

    workbook = load_workbook(BytesIO(result.xlsx_bytes), data_only=False)
    assert workbook.sheetnames == [
        "Summary",
        "Respondent Profile",
        "Employment",
        "First Job",
        "Reasons & Skills",
    ]
    assert all(worksheet.sheet_state == "visible" for worksheet in workbook.worksheets)

    values = workbook_values(workbook)
    serialized = "\n".join(values)
    assert sentinel not in serialized
    assert "gts-xlsx-private@example.edu" not in serialized
    assert "Raw" not in workbook.sheetnames

    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                assert cell.data_type != "f"
                assert cell.hyperlink is None

    employment = workbook["Employment"]
    employed_row = None
    for row in employment.iter_rows():
        if row[0].value == GTSEmploymentState.EMPLOYED.label:
            employed_row = row
            break
    assert employed_row is not None
    assert employed_row[1].value == 1
    assert float(employed_row[2].value) == 50.0
    assert employed_row[2].number_format == "0.00"


@pytest.mark.django_db
def test_zero_result_xlsx_still_has_context_methodology_and_zero_sections():
    result = render_graduate_tracer_xlsx()
    workbook = load_workbook(BytesIO(result.xlsx_bytes), data_only=False)

    values = workbook_values(workbook)
    assert EMPTY_REPORT_MESSAGE in values
    assert "Submitted Response Count" in values
    assert "0" in values
    assert any("No response rate is calculated" in value for value in values)
    assert workbook.sheetnames == [
        "Summary",
        "Respondent Profile",
        "Employment",
        "First Job",
        "Reasons & Skills",
    ]


@pytest.mark.django_db
def test_filtered_xlsx_filename_is_deterministic_and_contains_only_safe_dates():
    result = render_graduate_tracer_xlsx(
        submitted_from=date(2026, 1, 1),
        submitted_to=date(2026, 12, 31),
    )
    assert (
        result.filename
        == "graduate-tracer-schema-v1-submitted-2026-01-01-to-2026-12-31.xlsx"
    )
    assert result.release_context == {
        "instrument_schema_version": 1,
        "submitted_from": "2026-01-01",
        "submitted_to": "2026-12-31",
    }
