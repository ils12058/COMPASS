from __future__ import annotations

import json
from datetime import datetime

import pytest
from django.apps import apps
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.graduate_tracer.models import (
    GTS_SCHEMA_VERSION,
    GraduateTracerEducation,
    GraduateTracerProfessionalExam,
    GraduateTracerResponse,
    GraduateTracerStatus,
    GraduateTracerTraining,
    GTSDegreeReason,
    GTSFirstJobDuration,
)


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
        last_name="Student",
    )
    if role == "STUDENT":
        user.student_lifecycle_status = lifecycle
        user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def make_head(email: str = "head-gts@example.edu") -> User:
    user = make_user(email, role="COUNSELOR", lifecycle=None)
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def post_empty(client: Client, path: str):
    return client.post(path, **csrf(client))


def put_json(client: Client, path: str, payload: dict[str, object]):
    return client.put(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


def valid_unemployed_payload() -> dict[str, object]:
    return {
        "name": "Graduate Student",
        "permanent_address": "Daet, Camarines Norte",
        "email": "graduate@example.edu",
        "telephone_contact_numbers": "054-000-0000",
        "mobile_number": "09170000000",
        "civil_status": "SINGLE",
        "sex": "MALE",
        "birth_date": "2000-01-15",
        "region_of_origin": "REGION_5",
        "province": "Camarines Norte",
        "residence_location": "MUNICIPALITY",
        "education": [
            {
                "degree_and_specialization": "BS Information Systems",
                "college_or_university": "University of Camarines Norte",
                "year_graduated": 2026,
                "honors_or_awards": "",
            }
        ],
        "professional_exams": [],
        "undergraduate_degree_reasons": ["PASSION_PROFESSION"],
        "graduate_study_reasons": [],
        "degree_other_reason": "A personal reason outside the listed checkboxes",
        "trainings": [],
        "advanced_study_reasons": [],
        "advanced_study_other_reason": "",
        "current_employment_state": "NOT_EMPLOYED",
        "unemployment_reasons": ["NO_JOB_OPPORTUNITY"],
        "unemployment_other_reason": "",
        "curriculum_improvement_suggestions": "Keep practical project work.",
    }


def valid_employed_payload() -> dict[str, object]:
    payload = valid_unemployed_payload()
    payload.update(
        {
            "current_employment_state": "EMPLOYED",
            "unemployment_reasons": [],
            "present_employment_status": "REGULAR_PERMANENT",
            "present_occupation": "Information Systems Analyst",
            "employer_business_line": "EDUCATION",
            "place_of_work": "LOCAL",
            "first_job_after_college": False,
            "first_job_duration": "THREE_TO_LT_FOUR_YEARS",
            "first_job_source": "ADVERTISEMENT",
            "time_to_first_job": "THREE_TO_LT_FOUR_YEARS",
            "first_job_level": "PROFESSIONAL_TECHNICAL_SUPERVISORY",
            "current_job_level": "PROFESSIONAL_TECHNICAL_SUPERVISORY",
            "initial_gross_monthly_earning": "FROM_15000_TO_LT_20000",
            "curriculum_relevant_to_first_job": True,
            "useful_competencies": ["COMMUNICATION", "INFORMATION_TECHNOLOGY"],
        }
    )
    return payload


@pytest.mark.django_db
def test_graduate_tracer_is_focused_domain_without_alumni_or_cross_domain_prerequisites():
    field_names = {field.name for field in GraduateTracerResponse._meta.fields}
    assert "student" in field_names
    assert {
        "inventory",
        "academic_year",
        "student_affiliation",
        "appointment",
        "counseling_encounter",
        "exit_interview",
        "good_moral",
        "form_revision",
        "institution_code",
        "control_code",
        "reference_code",
    }.isdisjoint(field_names)
    for model_name in (
        "Alumni",
        "AlumniProfile",
        "Question",
        "SurveyQuestion",
        "SurveyDefinition",
        "SurveyAnswer",
        "GenericResponse",
        "FormCampaign",
        "ReferredAlumni",
    ):
        with pytest.raises(LookupError):
            apps.get_model("graduate_tracer", model_name)
    assert not Role.objects.filter(code="ALUMNI").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("lifecycle", "expected"),
    [
        (StudentLifecycleStatus.CURRENT, 409),
        (StudentLifecycleStatus.GRADUATED, 200),
        (StudentLifecycleStatus.FORMER, 409),
    ],
)
def test_only_graduated_students_can_create_gts(lifecycle, expected):
    sync_policy()
    student = make_user(f"{lifecycle.lower()}-gts@example.edu", lifecycle=lifecycle)
    response = post_empty(auth_client(student), "/api/v1/graduate-tracer/me")
    assert response.status_code == expected
    assert GraduateTracerResponse.objects.count() == (1 if expected == 200 else 0)


@pytest.mark.django_db
def test_non_student_and_inactive_student_cannot_create_gts():
    sync_policy()
    counselor = make_user("counselor-gts@example.edu", role="COUNSELOR", lifecycle=None)
    assert post_empty(auth_client(counselor), "/api/v1/graduate-tracer/me").status_code == 403

    student = make_user("inactive-gts@example.edu")
    client = auth_client(student)
    student.is_active = False
    student.save(update_fields=["is_active", "updated_at"])
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code in {401, 403}


@pytest.mark.django_db
def test_ensure_prefills_profile_once_without_fabricating_mobile_semantics():
    sync_policy()
    student = make_user("profile-gts@example.edu")
    student.permanent_address = "Original Permanent Address"
    student.contact_number = "054-123-4567"
    student.date_of_birth = timezone.localdate().replace(year=2000)
    student.civil_status = "Married"
    student.save(
        update_fields=[
            "permanent_address",
            "contact_number",
            "date_of_birth",
            "civil_status",
            "updated_at",
        ]
    )
    client = auth_client(student)

    response = post_empty(client, "/api/v1/graduate-tracer/me")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Graduate Student"
    assert body["permanent_address"] == "Original Permanent Address"
    assert body["email"] == "profile-gts@example.edu"
    assert body["telephone_contact_numbers"] == "054-123-4567"
    assert body["mobile_number"] == ""
    assert body["civil_status"] == "MARRIED"

    student.first_name = "Changed"
    student.permanent_address = "Changed Address"
    student.contact_number = "09999999999"
    student.save(
        update_fields=[
            "first_name",
            "permanent_address",
            "contact_number",
            "updated_at",
        ]
    )
    again = post_empty(client, "/api/v1/graduate-tracer/me")
    assert again.status_code == 200
    assert again.json()["name"] == "Graduate Student"
    assert again.json()["permanent_address"] == "Original Permanent Address"
    assert again.json()["telephone_contact_numbers"] == "054-123-4567"


@pytest.mark.django_db
def test_draft_replacement_is_response_local_and_repeatable_rows_do_not_duplicate():
    sync_policy()
    student = make_user("rows-gts@example.edu")
    student.permanent_address = "Profile Address"
    student.save(update_fields=["permanent_address", "updated_at"])
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    payload = valid_unemployed_payload()
    payload["name"] = "Corrected GTS Name"
    payload["education"] = [
        {
            "degree_and_specialization": "BS Information Systems",
            "college_or_university": "UCN",
            "year_graduated": 2026,
            "honors_or_awards": "Cum Laude",
        },
        {
            "degree_and_specialization": "BS Secondary Degree",
            "college_or_university": "Another University",
            "year_graduated": 2024,
            "honors_or_awards": "",
        },
    ]
    payload["professional_exams"] = [
        {
            "examination_name": "Civil Service Examination",
            "date_taken": "2026-03-01",
            "rating": "Passed",
        },
        {"examination_name": "Other Examination", "date_taken": None, "rating": ""},
    ]
    payload["trainings"] = [
        {"title": "Data Training", "duration_and_credits": "3 days", "institution": "UCN"},
        {"title": "Security Training", "duration_and_credits": "", "institution": ""},
    ]
    response = put_json(client, "/api/v1/graduate-tracer/me", payload)
    assert response.status_code == 200
    item = GraduateTracerResponse.objects.get()
    assert item.name_snapshot == "Corrected GTS Name"
    assert GraduateTracerEducation.objects.filter(response=item).count() == 2
    assert GraduateTracerProfessionalExam.objects.filter(response=item).count() == 2
    assert GraduateTracerTraining.objects.filter(response=item).count() == 2

    second = valid_unemployed_payload()
    second["professional_exams"] = [
        {
            "examination_name": "Civil Service Examination",
            "date_taken": "2026-03-01",
            "rating": "Passed",
        }
    ]
    second["trainings"] = []
    assert put_json(client, "/api/v1/graduate-tracer/me", second).status_code == 200
    assert GraduateTracerEducation.objects.filter(response=item).count() == 1
    assert GraduateTracerProfessionalExam.objects.filter(response=item).count() == 1
    assert GraduateTracerTraining.objects.filter(response=item).count() == 0

    student.refresh_from_db()
    assert student.get_full_name() == "Graduate Student"
    assert student.permanent_address == "Profile Address"


@pytest.mark.django_db
def test_q14_columns_are_separate_and_others_is_one_shared_free_text_line():
    sync_policy()
    assert "OTHER" not in GTSDegreeReason.values
    student = make_user("q14-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    payload = valid_unemployed_payload()
    payload["undergraduate_degree_reasons"] = ["PASSION_PROFESSION", "IMMEDIATE_EMPLOYMENT"]
    payload["graduate_study_reasons"] = ["CAREER_ADVANCEMENT"]
    payload["degree_other_reason"] = "One source-level Others line"
    response = put_json(client, "/api/v1/graduate-tracer/me", payload)
    assert response.status_code == 200
    item = GraduateTracerResponse.objects.get()
    assert item.undergraduate_degree_reasons == ["PASSION_PROFESSION", "IMMEDIATE_EMPLOYMENT"]
    assert item.graduate_study_reasons == ["CAREER_ADVANCEMENT"]
    assert item.degree_other_reason == "One source-level Others line"
    assert not hasattr(item, "undergraduate_degree_other_reason")
    assert not hasattr(item, "graduate_study_other_reason")

    invalid = valid_unemployed_payload()
    invalid["undergraduate_degree_reasons"] = ["OTHER"]
    assert put_json(client, "/api/v1/graduate-tracer/me", invalid).status_code == 422


@pytest.mark.django_db
def test_q29_uses_same_source_duration_buckets_including_three_to_less_than_four_years():
    sync_policy()
    assert "THREE_TO_LT_FOUR_YEARS" in GTSFirstJobDuration.values
    student = make_user("q29-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200
    payload = valid_employed_payload()
    saved = put_json(client, "/api/v1/graduate-tracer/me", payload)
    assert saved.status_code == 200
    assert saved.json()["time_to_first_job"] == "THREE_TO_LT_FOUR_YEARS"
    submitted = post_empty(client, "/api/v1/graduate-tracer/me/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "SUBMITTED"


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["NOT_EMPLOYED", "NEVER_EMPLOYED"])
def test_unemployed_branches_submit_without_employed_answers(state):
    sync_policy()
    student = make_user(f"{state.lower()}-branch@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200
    payload = valid_unemployed_payload()
    payload["current_employment_state"] = state
    assert put_json(client, "/api/v1/graduate-tracer/me", payload).status_code == 200
    submitted = post_empty(client, "/api/v1/graduate-tracer/me/submit")
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["present_employment_status"] is None
    assert body["present_occupation"] == ""


@pytest.mark.django_db
def test_branch_change_clears_now_inapplicable_employment_answers():
    sync_policy()
    student = make_user("branch-switch-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200
    assert (
        put_json(client, "/api/v1/graduate-tracer/me", valid_employed_payload()).status_code == 200
    )

    payload = valid_unemployed_payload()
    payload.update(
        {
            "present_employment_status": "REGULAR_PERMANENT",
            "present_occupation": "Stale occupation",
            "first_job_duration": "LESS_THAN_MONTH",
        }
    )
    switched = put_json(client, "/api/v1/graduate-tracer/me", payload)
    assert switched.status_code == 200
    body = switched.json()
    assert body["present_employment_status"] is None
    assert body["present_occupation"] == ""
    assert body["first_job_duration"] is None


@pytest.mark.django_db
def test_job_change_reasons_survive_when_current_job_is_not_first_job():
    sync_policy()
    student = make_user("job-change-not-first-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    payload = valid_employed_payload()
    payload.update(
        {
            "first_job_after_college": False,
            "first_job_related_to_course": True,
            "reasons_for_staying_on_job": ["SALARIES_BENEFITS"],
            "reasons_for_changing_job": ["SALARIES_BENEFITS", "CAREER_CHALLENGE"],
            "reasons_for_changing_other": "",
        }
    )
    updated = put_json(client, "/api/v1/graduate-tracer/me", payload)

    assert updated.status_code == 200
    body = updated.json()
    assert body["reasons_for_changing_job"] == ["SALARIES_BENEFITS", "CAREER_CHALLENGE"]
    assert body["reasons_for_changing_other"] == ""
    assert body["reasons_for_staying_on_job"] == []
    assert body["first_job_related_to_course"] is None


@pytest.mark.django_db
def test_job_change_other_survives_ambiguous_employed_branch():
    sync_policy()
    student = make_user("job-change-other-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    payload = valid_employed_payload()
    payload["reasons_for_changing_job"] = ["OTHER"]
    payload["reasons_for_changing_other"] = "Needed a different work arrangement."
    updated = put_json(client, "/api/v1/graduate-tracer/me", payload)

    assert updated.status_code == 200
    body = updated.json()
    assert body["reasons_for_changing_job"] == ["OTHER"]
    assert body["reasons_for_changing_other"] == "Needed a different work arrangement."


@pytest.mark.django_db
def test_job_change_other_validation_remains_submission_safe():
    sync_policy()
    student = make_user("job-change-other-validation-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    missing_other_text = valid_employed_payload()
    missing_other_text["reasons_for_changing_job"] = ["OTHER"]
    missing_other_text["reasons_for_changing_other"] = ""
    assert put_json(client, "/api/v1/graduate-tracer/me", missing_other_text).status_code == 200
    missing_text_submit = post_empty(client, "/api/v1/graduate-tracer/me/submit")
    assert missing_text_submit.status_code == 422
    assert missing_text_submit.json()["error"]["code"] == "invalid_graduate_tracer_request"

    unexpected_other_text = valid_employed_payload()
    unexpected_other_text["reasons_for_changing_job"] = ["SALARIES_BENEFITS"]
    unexpected_other_text["reasons_for_changing_other"] = "Unexpected companion text."
    assert put_json(client, "/api/v1/graduate-tracer/me", unexpected_other_text).status_code == 200
    unexpected_text_submit = post_empty(client, "/api/v1/graduate-tracer/me/submit")
    assert unexpected_text_submit.status_code == 422
    assert unexpected_text_submit.json()["error"]["code"] == "invalid_graduate_tracer_request"


@pytest.mark.django_db
def test_unemployed_transition_still_clears_job_change_answers():
    sync_policy()
    student = make_user("job-change-unemployed-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    employed = valid_employed_payload()
    employed["reasons_for_changing_job"] = ["OTHER"]
    employed["reasons_for_changing_other"] = "Changed industries."
    assert put_json(client, "/api/v1/graduate-tracer/me", employed).status_code == 200

    switched = put_json(client, "/api/v1/graduate-tracer/me", valid_unemployed_payload())
    assert switched.status_code == 200
    body = switched.json()
    assert body["reasons_for_changing_job"] == []
    assert body["reasons_for_changing_other"] == ""


@pytest.mark.django_db
def test_job_change_reasons_survive_first_job_related_to_course_no_branch():
    sync_policy()
    student = make_user("job-change-course-no-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    payload = valid_employed_payload()
    payload.update(
        {
            "first_job_after_college": True,
            "reasons_for_staying_on_job": ["SALARIES_BENEFITS"],
            "first_job_related_to_course": False,
            "reasons_for_changing_job": ["CAREER_CHALLENGE"],
        }
    )
    updated = put_json(client, "/api/v1/graduate-tracer/me", payload)

    assert updated.status_code == 200
    assert updated.json()["reasons_for_changing_job"] == ["CAREER_CHALLENGE"]


@pytest.mark.django_db
def test_submission_freezes_response_and_repeat_submit_is_idempotent():
    sync_policy()
    student = make_user("immutable-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200
    assert (
        put_json(client, "/api/v1/graduate-tracer/me", valid_unemployed_payload()).status_code
        == 200
    )

    first = post_empty(client, "/api/v1/graduate-tracer/me/submit")
    assert first.status_code == 200
    first_time = first.json()["submitted_at"]
    assert GraduateTracerResponse.objects.get().status == GraduateTracerStatus.SUBMITTED

    update = valid_unemployed_payload()
    update["name"] = "Changed"
    assert put_json(client, "/api/v1/graduate-tracer/me", update).status_code == 409

    second = post_empty(client, "/api/v1/graduate-tracer/me/submit")
    assert second.status_code == 200
    assert second.json()["submitted_at"] == first_time
    assert AuditEvent.objects.filter(action="graduate_tracer.submitted").count() == 1


@pytest.mark.django_db
def test_lifecycle_change_preserves_historical_owner_read_but_blocks_mutation():
    sync_policy()
    student = make_user("former-after-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200
    assert (
        put_json(client, "/api/v1/graduate-tracer/me", valid_unemployed_payload()).status_code
        == 200
    )

    student.student_lifecycle_status = StudentLifecycleStatus.FORMER
    student.save(update_fields=["student_lifecycle_status", "updated_at"])

    assert client.get("/api/v1/graduate-tracer/me").status_code == 200
    assert (
        put_json(client, "/api/v1/graduate-tracer/me", valid_unemployed_payload()).status_code
        == 409
    )
    assert post_empty(client, "/api/v1/graduate-tracer/me/submit").status_code == 409
    assert GraduateTracerResponse.objects.count() == 1


@pytest.mark.django_db
def test_head_reads_only_submitted_and_other_operational_roles_are_denied():
    sync_policy()
    draft_student = make_user("draft-gts@example.edu")
    draft_client = auth_client(draft_student)
    draft_id = post_empty(draft_client, "/api/v1/graduate-tracer/me").json()["id"]

    submitted_student = make_user("submitted-gts@example.edu")
    submitted_client = auth_client(submitted_student)
    assert post_empty(submitted_client, "/api/v1/graduate-tracer/me").status_code == 200
    assert (
        put_json(
            submitted_client, "/api/v1/graduate-tracer/me", valid_unemployed_payload()
        ).status_code
        == 200
    )
    submitted_id = post_empty(submitted_client, "/api/v1/graduate-tracer/me/submit").json()["id"]

    head = auth_client(make_head())
    listed = head.get("/api/v1/graduate-tracer/responses")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["items"]] == [submitted_id]
    detail = head.get(f"/api/v1/graduate-tracer/responses/{submitted_id}")
    assert detail.status_code == 200
    # Detail carries the same bounded Student identity as the review queue row.
    assert detail.json()["student"] == listed.json()["items"][0]["student"]
    assert set(detail.json()["student"]) == {"id", "institutional_id", "display_name"}
    assert head.get(f"/api/v1/graduate-tracer/responses/{draft_id}").status_code == 404

    counselor = auth_client(make_user("ordinary-gts@example.edu", role="COUNSELOR", lifecycle=None))
    gss = auth_client(
        make_user("gss-gts@example.edu", role="GUIDANCE_SERVICES_STAFF", lifecycle=None)
    )
    admin = auth_client(make_user("admin-gts@example.edu", role="IT_ADMIN", lifecycle=None))
    dpo_user = make_user("dpo-gts@example.edu", role="COUNSELOR", lifecycle=None)
    UserDesignation.objects.create(
        user=dpo_user,
        designation=Designation.objects.get(code="DPO"),
    )
    dpo = auth_client(dpo_user)
    for denied in (counselor, gss, admin, dpo):
        assert denied.get("/api/v1/graduate-tracer/responses").status_code == 403


@pytest.mark.django_db
def test_audit_metadata_is_structural_only_and_contains_no_answers():
    sync_policy()
    student = make_user("audit-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200
    payload = valid_unemployed_payload()
    payload["curriculum_improvement_suggestions"] = "Sensitive curriculum feedback"
    assert put_json(client, "/api/v1/graduate-tracer/me", payload).status_code == 200
    assert post_empty(client, "/api/v1/graduate-tracer/me/submit").status_code == 200

    created = AuditEvent.objects.get(action="graduate_tracer.draft_created")
    submitted = AuditEvent.objects.get(action="graduate_tracer.submitted")
    assert created.metadata == {
        "instrument_schema_version": GTS_SCHEMA_VERSION,
        "transition": "NONE -> DRAFT",
    }
    assert submitted.metadata == {
        "instrument_schema_version": GTS_SCHEMA_VERSION,
        "transition": "DRAFT -> SUBMITTED",
    }
    serialized = json.dumps([created.metadata, submitted.metadata])
    assert "Sensitive curriculum feedback" not in serialized
    assert "audit-gts@example.edu" not in serialized


@pytest.mark.django_db
def test_server_owned_fields_and_unsupported_source_values_are_rejected():
    sync_policy()
    student = make_user("strict-gts@example.edu")
    client = auth_client(student)
    assert post_empty(client, "/api/v1/graduate-tracer/me").status_code == 200

    extra = valid_unemployed_payload()
    extra["student_id"] = str(student.pk)
    extra["instrument_schema_version"] = 999
    extra["status"] = "SUBMITTED"
    assert put_json(client, "/api/v1/graduate-tracer/me", extra).status_code == 422

    invalid = valid_unemployed_payload()
    invalid["region_of_origin"] = "BARMM"
    assert put_json(client, "/api/v1/graduate-tracer/me", invalid).status_code == 422


@pytest.mark.django_db
def test_submitted_review_list_filters_identity_dates_employment_and_preserves_draft_privacy():
    sync_policy()
    alpha = make_user("review-alpha-gts@example.edu")
    alpha.institutional_id = "GTS-2026-ALPHA"
    alpha.first_name = "Alpha"
    alpha.middle_name = "Middlemark"
    alpha.last_name = "Tracer"
    alpha.save(
        update_fields=[
            "institutional_id",
            "first_name",
            "middle_name",
            "last_name",
            "updated_at",
        ]
    )
    alpha_client = auth_client(alpha)
    assert post_empty(alpha_client, "/api/v1/graduate-tracer/me").status_code == 200
    alpha_payload = valid_employed_payload()
    alpha_payload["name"] = "Historical Alpha Graduate"
    assert put_json(alpha_client, "/api/v1/graduate-tracer/me", alpha_payload).status_code == 200
    alpha_id = post_empty(alpha_client, "/api/v1/graduate-tracer/me/submit").json()["id"]

    beta = make_user("review-beta-gts@example.edu")
    beta.institutional_id = "GTS-2026-BETA"
    beta.first_name = "Beta"
    beta.last_name = "Tracer"
    beta.save(
        update_fields=[
            "institutional_id",
            "first_name",
            "last_name",
            "updated_at",
        ]
    )
    beta_client = auth_client(beta)
    assert post_empty(beta_client, "/api/v1/graduate-tracer/me").status_code == 200
    beta_payload = valid_unemployed_payload()
    beta_payload["name"] = "Historical Beta Graduate"
    assert put_json(beta_client, "/api/v1/graduate-tracer/me", beta_payload).status_code == 200
    beta_id = post_empty(beta_client, "/api/v1/graduate-tracer/me/submit").json()["id"]

    draft = make_user("review-draft-gts@example.edu")
    draft.institutional_id = "GTS-2026-DRAFT"
    draft.save(update_fields=["institutional_id", "updated_at"])
    assert post_empty(auth_client(draft), "/api/v1/graduate-tracer/me").status_code == 200

    zone = timezone.get_current_timezone()
    alpha_submitted = timezone.make_aware(datetime(2026, 9, 20, 23, 59), zone)
    beta_submitted = timezone.make_aware(datetime(2026, 9, 21, 0, 0), zone)
    GraduateTracerResponse.objects.filter(pk=alpha_id).update(submitted_at=alpha_submitted)
    GraduateTracerResponse.objects.filter(pk=beta_id).update(submitted_at=beta_submitted)

    head = auth_client(make_head("review-list-gts-head@example.edu"))
    for term in (
        "GTS-2026-ALPHA",
        "Alpha",
        "Middlemark",
        "Tracer",
        "Historical Alpha Graduate",
    ):
        response = head.get("/api/v1/graduate-tracer/responses", {"search": term})
        assert response.status_code == 200
        assert alpha_id in [row["id"] for row in response.json()["items"]]

    exact = head.get(
        "/api/v1/graduate-tracer/responses",
        {"student_id": str(alpha.pk)},
    )
    assert exact.status_code == 200
    assert [row["id"] for row in exact.json()["items"]] == [alpha_id]
    summary = exact.json()["items"][0]
    assert summary["student_id"] == str(alpha.pk)
    assert summary["student"] == {
        "id": str(alpha.pk),
        "institutional_id": "GTS-2026-ALPHA",
        "display_name": "Alpha Middlemark Tracer",
    }
    assert summary["name"] == "Historical Alpha Graduate"

    from_date = head.get(
        "/api/v1/graduate-tracer/responses",
        {"submitted_from": "2026-09-21"},
    )
    assert [row["id"] for row in from_date.json()["items"]] == [beta_id]

    to_date = head.get(
        "/api/v1/graduate-tracer/responses",
        {"submitted_to": "2026-09-20"},
    )
    assert [row["id"] for row in to_date.json()["items"]] == [alpha_id]

    combined_dates = head.get(
        "/api/v1/graduate-tracer/responses",
        {"submitted_from": "2026-09-20", "submitted_to": "2026-09-20"},
    )
    assert [row["id"] for row in combined_dates.json()["items"]] == [alpha_id]

    employed = head.get(
        "/api/v1/graduate-tracer/responses",
        {"current_employment_state": "EMPLOYED"},
    )
    assert [row["id"] for row in employed.json()["items"]] == [alpha_id]

    draft_search = head.get(
        "/api/v1/graduate-tracer/responses",
        {"search": "GTS-2026-DRAFT"},
    )
    assert draft_search.status_code == 200
    assert draft_search.json()["items"] == []

    paged = head.get("/api/v1/graduate-tracer/responses", {"page_size": 1})
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["has_next"] is True

    reversed_range = head.get(
        "/api/v1/graduate-tracer/responses",
        {"submitted_from": "2026-09-22", "submitted_to": "2026-09-21"},
    )
    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "invalid_graduate_tracer_request"

    overlong = head.get(
        "/api/v1/graduate-tracer/responses",
        {"search": "x" * 161},
    )
    assert overlong.status_code == 422
    assert overlong.json()["error"]["code"] == "invalid_graduate_tracer_request"
