from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.authentication.sessions import create_auth_session
from compass.graduate_tracer.models import (
    GraduateTracerEducation,
    GraduateTracerProfessionalExam,
    GraduateTracerResponse,
    GraduateTracerStatus,
    GraduateTracerTraining,
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
import compass.reports.graduate_tracer as graduate_tracer_report
from compass.reports.graduate_tracer import NOT_RECORDED, build_graduate_tracer_report


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    lifecycle: str | None = StudentLifecycleStatus.GRADUATED,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Graduate",
        last_name="Reporter",
    )
    if role == "STUDENT":
        user.student_lifecycle_status = lifecycle
        user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def make_head(email: str = "gts-report-head@example.edu") -> User:
    user = make_user(email, role="COUNSELOR", lifecycle=None)
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def at_local(year: int, month: int, day: int, hour: int = 12):
    return timezone.make_aware(
        datetime(year, month, day, hour, 0, 0),
        timezone.get_current_timezone(),
    )


def make_response(
    email: str,
    *,
    submitted: bool = True,
    submitted_at=None,
    **values,
) -> GraduateTracerResponse:
    student = make_user(email)
    defaults = {
        "civil_status": GTSCivilStatus.SINGLE,
        "sex": GTSSex.MALE,
        "region_of_origin": GTSRegionOfOrigin.REGION_5,
        "residence_location": GTSResidenceLocation.MUNICIPALITY,
        "current_employment_state": GTSEmploymentState.NOT_EMPLOYED,
        "unemployment_reasons": [GTSUnemploymentReason.NO_JOB_OPPORTUNITY],
    }
    defaults.update(values)
    return GraduateTracerResponse.objects.create(
        student=student,
        status=(GraduateTracerStatus.SUBMITTED if submitted else GraduateTracerStatus.DRAFT),
        submitted_at=(submitted_at or timezone.now()) if submitted else None,
        **defaults,
    )


@pytest.mark.django_db
def test_report_population_is_frozen_before_section_queries():
    first = make_response(
        "snapshot-first@example.edu",
        sex=GTSSex.MALE,
    )
    original = graduate_tracer_report._scalar_distribution
    inserted = False

    def insert_after_population_snapshot(queryset, **kwargs):
        nonlocal inserted
        if not inserted:
            inserted = True
            make_response(
                "snapshot-late@example.edu",
                sex=GTSSex.FEMALE,
            )
        return original(queryset, **kwargs)

    with patch(
        "compass.reports.graduate_tracer._scalar_distribution",
        side_effect=insert_after_population_snapshot,
    ):
        report = build_graduate_tracer_report()

    assert GraduateTracerResponse.objects.filter(
        status=GraduateTracerStatus.SUBMITTED
    ).count() == 2
    assert report["report_context"]["submitted_response_count"] == 1
    assert report["sections"]["sex"]["denominator"] == 1
    assert row(report, "sex", GTSSex.MALE)["count"] == 1
    assert row(report, "sex", GTSSex.FEMALE)["count"] == 0
    assert first.pk is not None


def row(report: dict[str, object], section: str, key: str) -> dict[str, object]:
    section_data = report["sections"][section]
    return next(item for item in section_data["rows"] if item["key"] == key)


@pytest.mark.django_db
def test_graduate_tracer_report_authorization_uses_reports_view_and_override_semantics():
    sync_policy()
    head = make_head()
    counselor = make_user("gts-counselor@example.edu", role="COUNSELOR", lifecycle=None)
    staff = make_user(
        "gts-staff@example.edu",
        role="GUIDANCE_SERVICES_STAFF",
        lifecycle=None,
    )
    student = make_user("gts-student@example.edu")
    admin = make_user("gts-admin@example.edu", role="IT_ADMIN", lifecycle=None)
    dpo = make_user(
        "gts-dpo@example.edu",
        role="INSTITUTIONAL_OFFICER",
        lifecycle=None,
    )
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )

    assert auth_client(head).get("/api/v1/reports/graduate-tracer").status_code == 200
    assert auth_client(head).get("/api/v1/reports/graduate-tracer/xlsx").status_code == 200
    for denied in (counselor, staff, student, admin, dpo):
        client = auth_client(denied)
        assert client.get("/api/v1/reports/graduate-tracer").status_code == 403
        assert client.get("/api/v1/reports/graduate-tracer/xlsx").status_code == 403

    set_user_capability_override(
        user=counselor,
        capability=Capability.objects.get(code="reports.view"),
        effect="GRANT",
        reason="Synthetic approved reporting exception",
    )
    counselor_client = auth_client(counselor)
    assert counselor_client.get("/api/v1/reports/graduate-tracer").status_code == 200
    assert counselor_client.get("/api/v1/reports/graduate-tracer/xlsx").status_code == 200


@pytest.mark.django_db
def test_population_is_submitted_schema_v1_history_and_ignores_later_account_state():
    sync_policy()
    submitted = make_response("gts-history@example.edu")
    make_response("gts-draft@example.edu", submitted=False)

    submitted.student.is_active = False
    submitted.student.student_lifecycle_status = StudentLifecycleStatus.FORMER
    submitted.student.save(update_fields=["is_active", "student_lifecycle_status", "updated_at"])

    report = build_graduate_tracer_report()
    assert report["report_context"]["submitted_response_count"] == 1
    assert report["report_context"]["instrument_schema_version"] == 1
    assert report["sections"]["sex"]["denominator"] == 1
    assert row(report, "sex", GTSSex.MALE)["count"] == 1


@pytest.mark.django_db
def test_empty_report_is_typed_and_zero_safe():
    report = build_graduate_tracer_report()

    assert report["report_context"]["submitted_response_count"] == 0
    for section in report["sections"].values():
        assert section["denominator"] == 0
        assert all(item["count"] == 0 for item in section["rows"])
        assert all(item["percentage"] == Decimal("0.00") for item in section["rows"])


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_submission_period_filters_are_inclusive_local_dates_not_cohorts():
    sync_policy()
    make_response(
        "gts-before@example.edu",
        submitted_at=at_local(2026, 8, 31, 23),
    )
    make_response(
        "gts-start@example.edu",
        submitted_at=at_local(2026, 9, 1, 0),
    )
    make_response(
        "gts-end@example.edu",
        submitted_at=at_local(2026, 9, 30, 23),
    )
    make_response(
        "gts-after@example.edu",
        submitted_at=at_local(2026, 10, 1, 0),
    )

    head = make_head("gts-filter-head@example.edu")
    client = auth_client(head)

    bounded = client.get(
        "/api/v1/reports/graduate-tracer?submitted_from=2026-09-01&submitted_to=2026-09-30"
    )
    from_only = client.get("/api/v1/reports/graduate-tracer?submitted_from=2026-10-01")
    to_only = client.get("/api/v1/reports/graduate-tracer?submitted_to=2026-08-31")
    invalid = client.get(
        "/api/v1/reports/graduate-tracer?submitted_from=2026-10-01&submitted_to=2026-09-01"
    )

    assert bounded.status_code == 200
    assert bounded.json()["report_context"]["submitted_response_count"] == 2
    assert bounded.json()["report_context"]["submitted_from"] == "2026-09-01"
    assert bounded.json()["report_context"]["submitted_to"] == "2026-09-30"
    assert from_only.json()["report_context"]["submitted_response_count"] == 1
    assert to_only.json()["report_context"]["submitted_response_count"] == 1
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_report_filter"


@pytest.mark.django_db
def test_profile_and_employment_distributions_use_explicit_conditional_denominators():
    sync_policy()
    make_response(
        "gts-employed-one@example.edu",
        sex=GTSSex.FEMALE,
        civil_status=GTSCivilStatus.MARRIED,
        region_of_origin=GTSRegionOfOrigin.NCR,
        residence_location=GTSResidenceLocation.CITY,
        current_employment_state=GTSEmploymentState.EMPLOYED,
        unemployment_reasons=[],
        present_employment_status=GTSPresentEmploymentStatus.REGULAR_PERMANENT,
        employer_business_line=GTSBusinessLine.EDUCATION,
        place_of_work=GTSPlaceOfWork.LOCAL,
        first_job_after_college=True,
        reasons_for_staying_on_job=[
            GTSStayingReason.SALARIES_BENEFITS,
            GTSStayingReason.CAREER_CHALLENGE,
        ],
        first_job_related_to_course=True,
        first_job_duration=GTSFirstJobDuration.ONE_TO_SIX_MONTHS,
        first_job_source=GTSFirstJobSource.ADVERTISEMENT,
        time_to_first_job=GTSFirstJobDuration.LESS_THAN_MONTH,
        first_job_level=GTSJobLevel.PROFESSIONAL_TECHNICAL_SUPERVISORY,
        current_job_level=GTSJobLevel.MANAGERIAL_EXECUTIVE,
        initial_gross_monthly_earning=GTSEarningBracket.FROM_15000_TO_LT_20000,
        curriculum_relevant_to_first_job=True,
        useful_competencies=[
            GTSUsefulCompetency.COMMUNICATION,
            GTSUsefulCompetency.INFORMATION_TECHNOLOGY,
            GTSUsefulCompetency.OTHER,
        ],
    )
    make_response(
        "gts-employed-two@example.edu",
        current_employment_state=GTSEmploymentState.EMPLOYED,
        unemployment_reasons=[],
        present_employment_status=GTSPresentEmploymentStatus.TEMPORARY,
        employer_business_line=GTSBusinessLine.HEALTH_SOCIAL_WORK,
        place_of_work=GTSPlaceOfWork.ABROAD,
        first_job_after_college=False,
        first_job_duration=GTSFirstJobDuration.SEVEN_TO_ELEVEN_MONTHS,
        first_job_source=GTSFirstJobSource.FRIENDS,
        time_to_first_job=GTSFirstJobDuration.ONE_TO_SIX_MONTHS,
        first_job_level=GTSJobLevel.RANK_CLERICAL,
        current_job_level=GTSJobLevel.PROFESSIONAL_TECHNICAL_SUPERVISORY,
        initial_gross_monthly_earning=GTSEarningBracket.FROM_10000_TO_LT_15000,
        curriculum_relevant_to_first_job=False,
    )
    make_response(
        "gts-unemployed@example.edu",
        current_employment_state=GTSEmploymentState.NOT_EMPLOYED,
        unemployment_reasons=[
            GTSUnemploymentReason.NO_JOB_OPPORTUNITY,
            GTSUnemploymentReason.NO_JOB_OPPORTUNITY,
            GTSUnemploymentReason.OTHER,
        ],
    )
    make_response(
        "gts-never@example.edu",
        current_employment_state=GTSEmploymentState.NEVER_EMPLOYED,
        unemployment_reasons=[GTSUnemploymentReason.NO_JOB_OPPORTUNITY],
    )

    report = build_graduate_tracer_report()

    employment = report["sections"]["current_employment_state"]
    assert employment["denominator"] == 4
    assert row(report, "current_employment_state", GTSEmploymentState.EMPLOYED) == {
        "key": GTSEmploymentState.EMPLOYED,
        "label": GTSEmploymentState.EMPLOYED.label,
        "count": 2,
        "percentage": Decimal("50.00"),
    }
    assert report["sections"]["present_employment_status"]["denominator"] == 2
    assert report["sections"]["employer_business_line"]["denominator"] == 2
    assert report["sections"]["place_of_work"]["denominator"] == 2

    unemployment = report["sections"]["unemployment_reasons"]
    assert unemployment["denominator"] == 2
    assert unemployment["multiple_selection"] is True
    assert row(
        report,
        "unemployment_reasons",
        GTSUnemploymentReason.NO_JOB_OPPORTUNITY,
    )["percentage"] == Decimal("100.00")
    assert row(
        report,
        "unemployment_reasons",
        GTSUnemploymentReason.OTHER,
    )["percentage"] == Decimal("50.00")

    staying = report["sections"]["reasons_for_staying_on_job"]
    related = report["sections"]["first_job_related_to_course"]
    assert staying["denominator"] == related["denominator"] == 1
    assert row(
        report,
        "reasons_for_staying_on_job",
        GTSStayingReason.SALARIES_BENEFITS,
    )["percentage"] == Decimal("100.00")

    competencies = report["sections"]["useful_competencies"]
    assert competencies["denominator"] == 1
    assert sum(item["percentage"] for item in competencies["rows"]) >= Decimal("300.00")


@pytest.mark.django_db
def test_missing_required_controlled_values_are_not_silently_dropped():
    sync_policy()
    make_response(
        "gts-malformed@example.edu",
        sex="",
        civil_status="",
        region_of_origin="",
        residence_location="",
        current_employment_state=GTSEmploymentState.EMPLOYED,
        unemployment_reasons=[],
        present_employment_status="",
        employer_business_line="",
        place_of_work="",
        first_job_after_college=None,
        first_job_duration="",
        first_job_source="",
        time_to_first_job="",
        first_job_level="",
        current_job_level="",
        initial_gross_monthly_earning="",
        curriculum_relevant_to_first_job=None,
    )

    report = build_graduate_tracer_report()

    for section in (
        "sex",
        "civil_status",
        "region_of_origin",
        "residence_location",
        "present_employment_status",
        "employer_business_line",
        "place_of_work",
        "first_job_after_college",
        "first_job_duration",
        "first_job_source",
        "time_to_first_job",
        "first_job_level",
        "current_job_level",
        "initial_gross_monthly_earning",
        "curriculum_relevant_to_first_job",
    ):
        assert row(report, section, NOT_RECORDED)["count"] == 1


@pytest.mark.django_db
def test_controlled_report_rows_reuse_schema_v1_choice_keys_and_labels():
    report = build_graduate_tracer_report()
    mapping = {
        "sex": GTSSex,
        "civil_status": GTSCivilStatus,
        "region_of_origin": GTSRegionOfOrigin,
        "residence_location": GTSResidenceLocation,
        "current_employment_state": GTSEmploymentState,
        "present_employment_status": GTSPresentEmploymentStatus,
        "employer_business_line": GTSBusinessLine,
        "place_of_work": GTSPlaceOfWork,
        "first_job_duration": GTSFirstJobDuration,
        "first_job_source": GTSFirstJobSource,
        "time_to_first_job": GTSFirstJobDuration,
        "first_job_level": GTSJobLevel,
        "current_job_level": GTSJobLevel,
        "initial_gross_monthly_earning": GTSEarningBracket,
        "unemployment_reasons": GTSUnemploymentReason,
        "reasons_for_staying_on_job": GTSStayingReason,
        "useful_competencies": GTSUsefulCompetency,
    }
    for section_name, choices in mapping.items():
        actual = [(item["key"], item["label"]) for item in report["sections"][section_name]["rows"]]
        assert actual == list(choices.choices)


@pytest.mark.django_db
def test_aggregate_response_excludes_identity_free_text_and_academic_inference():
    sync_policy()
    sentinel = "SENTINEL-GTS-PRIVATE-CONTENT"
    item = make_response(
        "gts-private@example.edu",
        name_snapshot=sentinel,
        permanent_address_snapshot=sentinel,
        email_snapshot="sentinel-private@example.edu",
        telephone_contact_numbers_snapshot=sentinel,
        mobile_number_snapshot=sentinel,
        province=sentinel,
        unemployment_other_reason=sentinel,
        present_occupation=sentinel,
        reasons_for_staying_other=sentinel,
        first_job_duration_other=sentinel,
        first_job_source_other=sentinel,
        time_to_first_job_other=sentinel,
        useful_competencies_other=sentinel,
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
    GraduateTracerProfessionalExam.objects.create(
        response=item,
        position=1,
        examination_name=sentinel,
        rating=sentinel,
    )
    GraduateTracerTraining.objects.create(
        response=item,
        position=1,
        title=sentinel,
        duration_and_credits=sentinel,
        institution=sentinel,
    )

    response = auth_client(make_head("gts-private-head@example.edu")).get(
        "/api/v1/reports/graduate-tracer"
    )
    assert response.status_code == 200
    serialized = response.content.decode()

    for forbidden in (
        sentinel,
        "sentinel-private@example.edu",
        str(item.student_id),
        "program_id",
        "college_id",
        "campus_id",
        "graduation_year",
        "non_response_rate",
    ):
        assert forbidden not in serialized

    body = response.json()
    assert "submission dates, not graduation cohorts" in body["methodology"]["submission_period"]
    assert "No response rate is calculated" in body["methodology"]["response_rate"]
