from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.call_slips.models import CallSlip
from compass.counseling.models import CounselingEncounter
from compass.exit_interviews.models import (
    CareerMode,
    CollegeFeedbackItem,
    DelayReason,
    ExitInterview,
    ExitInterviewCollegeFeedbackRating,
    ExitInterviewReopenEvent,
    ExitInterviewSelfAssessmentRating,
    ProgramCompletion,
    SelfAssessmentItem,
    SignificantLearningExperience,
    StudyCareerChoice,
    WorkCareerChoice,
)
from compass.exit_interviews.services import ensure_my_current
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.inventory.models import StudentInventory
from compass.inventory.services import require_current_submitted_inventory
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.models import AcademicYear
from compass.referrals.models import Referral
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import Service


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    first_name: str = "Exit",
    last_name: str = "Student",
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=first_name,
        last_name=last_name,
    )


def make_head(email: str = "head-exit@example.edu") -> User:
    user = make_user(email, role="COUNSELOR", first_name="Head", last_name="Guidance")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def make_inventory_revision() -> FormRevision:
    family, _ = FormFamily.objects.get_or_create(
        key="exit_interview_test_inventory",
        defaults={"title": "Test Inventory"},
    )
    revision, _ = FormRevision.objects.get_or_create(
        family=family,
        official_code="TEST-INVENTORY",
        official_revision="0",
        defaults={"internal_schema_version": 1, "status": "ACTIVE"},
    )
    return revision


def make_year(label: str = "2099-2100", *, current: bool = True) -> AcademicYear:
    return AcademicYear.objects.create(label=label, is_current=current)


def make_inventory(
    student: User,
    academic_year: AcademicYear,
    *,
    submitted: bool = True,
    course: str = "Bachelor of Science in Information Systems",
    major: str = "Information Systems",
) -> StudentInventory:
    return StudentInventory.objects.create(
        student=student,
        academic_year=academic_year,
        form_revision=make_inventory_revision(),
        submitted_at=timezone.now() if submitted else None,
        full_name_snapshot="Inventory Historical Name",
        course_currently_enrolled=course,
        major=major,
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def valid_payload(*, feedback_zero: bool = False) -> dict[str, object]:
    return {
        "student_name": "Form Local Student",
        "age": 22,
        "civil_status": "Single",
        "course": "BS Information Systems",
        "major": "Information Systems",
        "email_address": "form-local@example.edu",
        "home_address": "Line 1\nLine 2",
        "contact_number": "09171234567",
        "program_completion": "ACCORDING_TO_SCHEDULE",
        "extra_terms_count": None,
        "delay_reasons": [],
        "delay_other": "",
        "significant_learning_experiences": [
            "INDEPENDENCE",
            "TIME_MANAGEMENT",
        ],
        "significant_learning_other": "",
        "career_modes": ["WORK", "STUDY"],
        "work_choices": ["RELATED_FIELD"],
        "study_choices": ["RELATED_FIELD"],
        "self_assessment_ratings": [
            {"item_code": code, "rating": 5} for code in SelfAssessmentItem.values
        ],
        "college_feedback_ratings": [
            {
                "item_code": code,
                "rating": 0 if feedback_zero and index == 0 else 5,
            }
            for index, code in enumerate(CollegeFeedbackItem.values)
        ],
        "dean_comments": "Dean comment",
        "program_chair_comments": "Program Chair comment",
        "faculty_comments": "Faculty comment",
        "curriculum_comments": "Curriculum comment",
        "guidance_counselor_comments": "Guidance comment",
        "office_staff_comments": "Office Staff comment",
        "facilities_comments": "Facilities comment",
        "suggestions_recommendations": "Suggestion",
    }


def ensure_api(client: Client):
    return client.post("/api/v1/exit-interviews/me/current", **csrf(client))


def put_api(client: Client, payload: dict[str, object]):
    return client.put(
        "/api/v1/exit-interviews/me/current",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


def submit_api(client: Client):
    return client.post("/api/v1/exit-interviews/me/current/submit", **csrf(client))


@pytest.mark.django_db
def test_source_schema_is_fixed_and_matches_inspected_two_page_form():
    assert list(ProgramCompletion.labels) == ["According to schedule", "With some delay"]
    assert list(DelayReason.labels) == [
        "Transferee",
        "Academic Failures",
        "Others (pls. specify)",
    ]
    assert list(SignificantLearningExperience.labels) == [
        "Independence",
        "Interpersonal Relations",
        "Intellectual Growth",
        "Spiritual Growth",
        "Responsibility",
        "Working under pressure",
        "Time Management",
        "Setting priorities",
        "Others, pls. specify",
    ]
    assert list(CareerMode.labels) == ["Work", "Study"]
    assert len(WorkCareerChoice.values) == 6
    assert len(StudyCareerChoice.values) == 2

    assert list(SelfAssessmentItem.labels) == [
        "Pride and confidence in being from CNSC",
        "Ability to maintain balance between academics & recreational activities",
        "Awareness of the importance of holistic personal well-being",
        "Ability to integrate knowledge with experience",
        "Clarity of career goals",
        "Self Esteem",
        "Self-Awareness",
        "Ability to cope with pressures",
        "Ability to deal comfortably with people from different walks of life",
        "Leadership",
        "Communication Skills",
        "Civic Mindedness",
        "Initiative",
        "Decision Making",
        "Relationship with God",
    ]
    assert len(SelfAssessmentItem.values) == 15
    assert len(CollegeFeedbackItem.values) == 26


@pytest.mark.django_db
def test_exit_interview_models_are_domain_specific_and_have_no_qms_or_generic_engine():
    fields = {field.name for field in ExitInterview._meta.get_fields()}
    assert "form_revision" not in fields
    assert "reference_code" not in fields
    assert "interview_date" not in fields
    assert "form_date" not in fields
    assert "student_entered_date" not in fields
    assert not FormFamily.objects.filter(key="exit_interview").exists()

    for name in (
        "GenericSurvey",
        "GenericQuestion",
        "GenericResponse",
        "FormField",
        "FormAnswer",
        "QuestionnaireEngine",
    ):
        with pytest.raises(LookupError):
            apps.get_model("exit_interviews", name)


@pytest.mark.django_db
def test_exit_interview_policy_is_student_self_plus_head_only():
    sync_policy()

    assert Capability.objects.count() == 62
    assert RoleCapability.objects.count() == 65
    assert DesignationCapability.objects.count() == 18

    student = make_user("student-policy@example.edu")
    counselor = make_user("counselor-policy@example.edu", role="COUNSELOR")
    staff = make_user("staff-policy@example.edu", role="GUIDANCE_SERVICES_STAFF")
    admin = make_user("admin-policy@example.edu", role="IT_ADMIN")
    dpo = make_user("dpo-policy@example.edu", role="INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    head = make_head()

    assert student.has_capability("exit_interviews.view_self")
    assert student.has_capability("exit_interviews.manage_self")
    assert not student.has_capability("exit_interviews.view")
    assert not student.has_capability("exit_interviews.reopen")

    assert head.has_capability("exit_interviews.view")
    assert head.has_capability("exit_interviews.reopen")
    assert not head.has_capability("exit_interviews.view_self")

    for user in (counselor, staff, admin, dpo):
        assert not user.has_capability("exit_interviews.view")
        assert not user.has_capability("exit_interviews.reopen")
        assert not user.has_capability("exit_interviews.view_self")
        assert not user.has_capability("exit_interviews.manage_self")


@pytest.mark.django_db
def test_ensure_requires_current_academic_year_and_submitted_current_inventory():
    sync_policy()
    student = make_user("prereq@example.edu")
    client = auth_client(student)

    missing_year = ensure_api(client)
    assert missing_year.status_code == 409
    assert missing_year.json()["error"]["code"] == "current_academic_year_not_configured"

    current = make_year()
    missing_inventory = ensure_api(client)
    assert missing_inventory.status_code == 409
    assert missing_inventory.json()["error"]["code"] == "exit_interview_inventory_required"

    make_inventory(student, current, submitted=False)
    draft_inventory = ensure_api(client)
    assert draft_inventory.status_code == 409
    assert draft_inventory.json()["error"]["code"] == "exit_interview_inventory_required"


@pytest.mark.django_db
def test_prior_year_submitted_inventory_does_not_satisfy_current_year_prerequisite():
    sync_policy()
    student = make_user("prior-year@example.edu")
    prior = make_year("2098-2099", current=False)
    current = make_year("2099-2100", current=True)
    make_inventory(student, prior, submitted=True)
    client = auth_client(student)

    response = ensure_api(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "exit_interview_inventory_required"
    assert not ExitInterview.objects.filter(student=student, academic_year=current).exists()


@pytest.mark.django_db
def test_ensure_reuses_canonical_inventory_resolver_and_binds_exact_returned_inventory():
    sync_policy()
    student = make_user("resolver@example.edu")
    current = make_year()
    inventory = make_inventory(student, current, submitted=True)

    with patch(
        "compass.exit_interviews.services.require_current_submitted_inventory",
        wraps=require_current_submitted_inventory,
    ) as resolver:
        item = ensure_my_current(student=student, context=AuditContext.user(student))

    assert resolver.call_count == 1
    called_student = resolver.call_args.args[0]
    assert called_student.pk == student.pk
    assert item.inventory_id == inventory.pk
    assert item.academic_year_id == current.pk


@pytest.mark.django_db
def test_ensure_uses_profile_and_inventory_prefill_once_and_is_idempotent():
    sync_policy()
    student = make_user(
        "prefill@example.edu",
        first_name="Current",
        last_name="Person",
    )
    birthday = date(timezone.localdate().year - 22, 1, 1)
    student.date_of_birth = birthday
    student.civil_status = "Single"
    student.contact_number = "09170000000"
    student.current_address = " Current Address "
    student.permanent_address = " Permanent Address "
    student.save(
        update_fields=[
            "date_of_birth",
            "civil_status",
            "contact_number",
            "current_address",
            "permanent_address",
            "updated_at",
        ]
    )
    current = make_year()
    inventory = make_inventory(
        student,
        current,
        submitted=True,
        course=" BS Information Systems ",
        major=" Information Systems ",
    )
    client = auth_client(student)

    first = ensure_api(client)
    second = ensure_api(client)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert ExitInterview.objects.filter(student=student, academic_year=current).count() == 1

    body = first.json()
    expected_age = (
        timezone.localdate().year
        - birthday.year
        - int(
            (timezone.localdate().month, timezone.localdate().day) < (birthday.month, birthday.day)
        )
    )
    assert body["student_name"] == "Current Person"
    assert body["age"] == expected_age
    assert body["civil_status"] == "Single"
    assert body["course"] == "BS Information Systems"
    assert body["major"] == "Information Systems"
    assert body["email_address"] == student.email
    assert body["home_address"] == "Current Address"
    assert body["contact_number"] == "09170000000"
    assert body["inventory_id"] == str(inventory.pk)

    assert (
        AuditEvent.objects.filter(
            action="exit_interview.created",
            target_id=body["id"],
        ).count()
        == 1
    )
    assert not Service.objects.filter(code="EXIT_INTERVIEW").exists()


@pytest.mark.django_db
def test_home_address_falls_back_to_permanent_and_missing_dob_keeps_age_null():
    sync_policy()
    student = make_user("fallback@example.edu")
    student.current_address = "   "
    student.permanent_address = " Permanent Home "
    student.save(update_fields=["current_address", "permanent_address", "updated_at"])
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)

    response = ensure_api(client)
    assert response.status_code == 200
    assert response.json()["home_address"] == "Permanent Home"
    assert response.json()["age"] is None


@pytest.mark.django_db
def test_profile_and_inventory_changes_after_creation_do_not_refresh_exit_interview():
    sync_policy()
    student = make_user("immutable-prefill@example.edu", first_name="Old", last_name="Name")
    student.contact_number = "old-contact"
    student.current_address = "old-address"
    student.date_of_birth = date(2000, 1, 1)
    student.save(
        update_fields=[
            "contact_number",
            "current_address",
            "date_of_birth",
            "updated_at",
        ]
    )
    current = make_year()
    inventory = make_inventory(student, current, course="Old Course", major="Old Major")
    client = auth_client(student)
    created = ensure_api(client)
    assert created.status_code == 200
    original = created.json()

    student.first_name = "New"
    student.last_name = "Profile"
    student.email = "new-profile@example.edu"
    student.contact_number = "new-contact"
    student.current_address = "new-address"
    student.date_of_birth = date(2005, 1, 1)
    student.save(
        update_fields=[
            "first_name",
            "last_name",
            "email",
            "contact_number",
            "current_address",
            "date_of_birth",
            "updated_at",
        ]
    )
    inventory.course_currently_enrolled = "New Course"
    inventory.major = "New Major"
    inventory.save(update_fields=["course_currently_enrolled", "major", "updated_at"])

    fetched = client.get("/api/v1/exit-interviews/me/current")
    assert fetched.status_code == 200
    body = fetched.json()
    for field in (
        "student_name",
        "age",
        "email_address",
        "contact_number",
        "home_address",
        "course",
        "major",
    ):
        assert body[field] == original[field]


@pytest.mark.django_db
def test_full_put_edits_form_local_values_without_mutating_profile_or_inventory():
    sync_policy()
    student = make_user("form-local@example.edu", first_name="Canonical", last_name="Profile")
    student.contact_number = "profile-contact"
    student.current_address = "profile-address"
    student.save(update_fields=["contact_number", "current_address", "updated_at"])
    current = make_year()
    inventory = make_inventory(student, current, course="Inventory Course", major="Inventory Major")
    client = auth_client(student)
    assert ensure_api(client).status_code == 200

    response = put_api(client, valid_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["student_name"] == "Form Local Student"
    assert body["course"] == "BS Information Systems"
    assert len(body["self_assessment_ratings"]) == 15
    assert len(body["college_feedback_ratings"]) == 26

    student.refresh_from_db()
    inventory.refresh_from_db()
    assert student.get_full_name() == "Canonical Profile"
    assert student.contact_number == "profile-contact"
    assert student.current_address == "profile-address"
    assert inventory.course_currently_enrolled == "Inventory Course"
    assert inventory.major == "Inventory Major"


@pytest.mark.django_db
def test_draft_consistency_enforces_delay_other_learning_and_career_dependencies():
    sync_policy()
    student = make_user("consistency@example.edu")
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)
    assert ensure_api(client).status_code == 200

    payload = valid_payload()
    payload["program_completion"] = "WITH_SOME_DELAY"
    payload["extra_terms_count"] = None
    assert put_api(client, payload).status_code == 422

    payload = valid_payload()
    payload["program_completion"] = "WITH_SOME_DELAY"
    payload["extra_terms_count"] = 2
    payload["delay_reasons"] = ["OTHER"]
    payload["delay_other"] = ""
    assert put_api(client, payload).status_code == 422

    payload = valid_payload()
    payload["significant_learning_experiences"] = ["OTHER"]
    payload["significant_learning_other"] = ""
    assert put_api(client, payload).status_code == 422

    payload = valid_payload()
    payload["career_modes"] = ["STUDY"]
    payload["work_choices"] = ["RELATED_FIELD"]
    assert put_api(client, payload).status_code == 422


@pytest.mark.django_db
def test_ratings_reject_unknown_duplicate_and_out_of_range_values_but_feedback_zero_is_preserved():
    sync_policy()
    student = make_user("ratings@example.edu")
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)
    assert ensure_api(client).status_code == 200

    zero = put_api(client, valid_payload(feedback_zero=True))
    assert zero.status_code == 200
    first_feedback = zero.json()["college_feedback_ratings"][0]
    assert first_feedback["rating"] == 0
    assert "rating_label" not in first_feedback

    self_zero = valid_payload()
    self_zero["self_assessment_ratings"][0]["rating"] = 0
    assert put_api(client, self_zero).status_code == 422

    feedback_six = valid_payload()
    feedback_six["college_feedback_ratings"][0]["rating"] = 6
    assert put_api(client, feedback_six).status_code == 422

    unknown = valid_payload()
    unknown["college_feedback_ratings"][0]["item_code"] = "INVENTED_ITEM"
    assert put_api(client, unknown).status_code == 422

    duplicate = valid_payload()
    duplicate["self_assessment_ratings"][1]["item_code"] = duplicate["self_assessment_ratings"][0][
        "item_code"
    ]
    assert put_api(client, duplicate).status_code == 422


@pytest.mark.django_db
def test_submission_requires_complete_fixed_rating_grids_and_is_idempotent():
    sync_policy()
    student = make_user("submit@example.edu")
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)
    created = ensure_api(client)
    assert created.status_code == 200

    incomplete = valid_payload()
    incomplete["self_assessment_ratings"] = incomplete["self_assessment_ratings"][:-1]
    assert put_api(client, incomplete).status_code == 200
    rejected = submit_api(client)
    assert rejected.status_code == 422

    assert put_api(client, valid_payload()).status_code == 200
    first = submit_api(client)
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "SUBMITTED"
    assert body["first_submitted_at"] is not None
    assert body["last_submitted_at"] == body["first_submitted_at"]

    second = submit_api(client)
    assert second.status_code == 200
    assert second.json()["first_submitted_at"] == body["first_submitted_at"]
    assert second.json()["last_submitted_at"] == body["last_submitted_at"]
    assert (
        AuditEvent.objects.filter(
            action="exit_interview.submitted",
            target_id=body["id"],
        ).count()
        == 1
    )
    assert (
        AuditEvent.objects.filter(
            action="exit_interview.resubmitted",
            target_id=body["id"],
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_submitted_record_is_locked_against_student_put():
    sync_policy()
    student = make_user("locked@example.edu")
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)
    assert ensure_api(client).status_code == 200
    assert put_api(client, valid_payload()).status_code == 200
    assert submit_api(client).status_code == 200

    locked = put_api(client, valid_payload())
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "exit_interview_conflict"


@pytest.mark.django_db
def test_only_head_may_read_all_and_reopen_with_required_reason():
    sync_policy()
    student = make_user("reopen-owner@example.edu")
    current = make_year()
    make_inventory(student, current)
    student_client = auth_client(student)
    assert ensure_api(student_client).status_code == 200
    assert put_api(student_client, valid_payload()).status_code == 200
    submitted = submit_api(student_client)
    exit_id = submitted.json()["id"]

    counselor = make_user("ordinary-counselor@example.edu", role="COUNSELOR")
    staff = make_user("ordinary-staff@example.edu", role="GUIDANCE_SERVICES_STAFF")
    admin = make_user("technical-admin@example.edu", role="IT_ADMIN")
    dpo = make_user("privacy-dpo@example.edu", role="INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    for actor in (student, counselor, staff, admin, dpo):
        client = auth_client(actor)
        assert client.get("/api/v1/exit-interviews").status_code == 403
        assert (
            client.post(
                f"/api/v1/exit-interviews/{exit_id}/reopen",
                data=json.dumps({"reason": "Correction requested"}),
                content_type="application/json",
                **csrf(client),
            ).status_code
            == 403
        )

    head = make_head()
    head_client = auth_client(head)
    listing = head_client.get("/api/v1/exit-interviews")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1
    assert "dean_comments" not in listing.json()["items"][0]
    assert "college_feedback_ratings" not in listing.json()["items"][0]

    detail = head_client.get(f"/api/v1/exit-interviews/{exit_id}")
    assert detail.status_code == 200

    blank_reason = head_client.post(
        f"/api/v1/exit-interviews/{exit_id}/reopen",
        data=json.dumps({"reason": "   "}),
        content_type="application/json",
        **csrf(head_client),
    )
    assert blank_reason.status_code == 422

    reopened = head_client.post(
        f"/api/v1/exit-interviews/{exit_id}/reopen",
        data=json.dumps({"reason": "Student requested a factual correction."}),
        content_type="application/json",
        **csrf(head_client),
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "DRAFT"
    assert len(reopened.json()["reopen_events"]) == 1
    assert reopened.json()["reopen_events"][0]["reason"] == (
        "Student requested a factual correction."
    )
    notification = Notification.objects.get(
        recipient=student,
        event_code="exit_interview.reopened",
        source_type="exit_interview",
        source_id=exit_id,
    )
    assert notification.policy == "MANDATORY_OPERATIONAL"
    assert notification.target_type == "EXIT_INTERVIEW"
    assert notification.target_id == ExitInterview.objects.get(pk=exit_id).pk
    assert "Student requested a factual correction." not in notification.message
    assert EmailDelivery.objects.filter(notification=notification).exists()


@pytest.mark.django_db
def test_reopen_and_resubmit_preserve_first_submission_and_append_correction_history():
    sync_policy()
    student = make_user("cycles@example.edu")
    current = make_year()
    make_inventory(student, current)
    student_client = auth_client(student)
    assert ensure_api(student_client).status_code == 200
    assert put_api(student_client, valid_payload()).status_code == 200
    first = submit_api(student_client).json()
    first_submitted_at = first["first_submitted_at"]
    first_last_submitted_at = first["last_submitted_at"]

    head = make_head()
    head_client = auth_client(head)
    exit_id = first["id"]
    assert (
        head_client.post(
            f"/api/v1/exit-interviews/{exit_id}/reopen",
            data=json.dumps({"reason": "First correction"}),
            content_type="application/json",
            **csrf(head_client),
        ).status_code
        == 200
    )

    corrected = valid_payload()
    corrected["suggestions_recommendations"] = "Corrected historical response"
    assert put_api(student_client, corrected).status_code == 200
    resubmitted = submit_api(student_client)
    assert resubmitted.status_code == 200
    second = resubmitted.json()
    assert second["first_submitted_at"] == first_submitted_at
    assert second["last_submitted_at"] >= first_last_submitted_at
    assert second["suggestions_recommendations"] == "Corrected historical response"
    assert (
        AuditEvent.objects.filter(
            action="exit_interview.resubmitted",
            target_id=exit_id,
        ).count()
        == 1
    )

    assert (
        head_client.post(
            f"/api/v1/exit-interviews/{exit_id}/reopen",
            data=json.dumps({"reason": "Second correction"}),
            content_type="application/json",
            **csrf(head_client),
        ).status_code
        == 200
    )
    history = student_client.get(f"/api/v1/exit-interviews/me/{exit_id}")
    assert history.status_code == 200
    assert [event["reason"] for event in history.json()["reopen_events"]] == [
        "First correction",
        "Second correction",
    ]
    assert ExitInterviewReopenEvent.objects.filter(exit_interview_id=exit_id).count() == 2


@pytest.mark.django_db
def test_reopen_does_not_refresh_profile_or_inventory_snapshots():
    sync_policy()
    student = make_user("reopen-snapshot@example.edu", first_name="Original", last_name="Name")
    student.current_address = "Original Address"
    student.save(update_fields=["current_address", "updated_at"])
    current = make_year()
    inventory = make_inventory(student, current, course="Original Course", major="Original Major")
    student_client = auth_client(student)
    original = ensure_api(student_client).json()
    assert put_api(student_client, valid_payload()).status_code == 200
    submitted = submit_api(student_client).json()

    student.first_name = "Changed"
    student.last_name = "Profile"
    student.current_address = "Changed Address"
    student.save(update_fields=["first_name", "last_name", "current_address", "updated_at"])
    inventory.course_currently_enrolled = "Changed Course"
    inventory.major = "Changed Major"
    inventory.save(update_fields=["course_currently_enrolled", "major", "updated_at"])

    head_client = auth_client(make_head())
    reopened = head_client.post(
        f"/api/v1/exit-interviews/{submitted['id']}/reopen",
        data=json.dumps({"reason": "Correction"}),
        content_type="application/json",
        **csrf(head_client),
    )
    assert reopened.status_code == 200
    # The saved submitted form-local values remain, not today's profile or Inventory.
    assert reopened.json()["student_name"] == "Form Local Student"
    assert reopened.json()["course"] == "BS Information Systems"
    assert reopened.json()["home_address"] == "Line 1\nLine 2"
    assert original["student_name"] == "Original Name"


@pytest.mark.django_db
def test_student_history_survives_current_year_change_without_requiring_new_inventory():
    sync_policy()
    student = make_user("history-year@example.edu")
    first_year = make_year("2098-2099", current=True)
    make_inventory(student, first_year)
    client = auth_client(student)
    created = ensure_api(client)
    exit_id = created.json()["id"]
    assert put_api(client, valid_payload()).status_code == 200
    assert submit_api(client).status_code == 200

    first_year.is_current = False
    first_year.save(update_fields=["is_current", "updated_at"])
    make_year("2099-2100", current=True)

    history = client.get("/api/v1/exit-interviews/me")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()["items"]] == [exit_id]

    detail = client.get(f"/api/v1/exit-interviews/me/{exit_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "SUBMITTED"

    current_missing = client.get("/api/v1/exit-interviews/me/current")
    assert current_missing.status_code == 404


@pytest.mark.django_db
def test_audit_metadata_excludes_answers_ratings_comments_contact_and_reopen_reason():
    sync_policy()
    student = make_user("audit-exit@example.edu")
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)
    created = ensure_api(client)
    exit_id = created.json()["id"]
    payload = valid_payload(feedback_zero=True)
    payload["dean_comments"] = "Sensitive identifiable comment"
    payload["home_address"] = "Sensitive address"
    payload["contact_number"] = "Sensitive phone"
    assert put_api(client, payload).status_code == 200
    assert submit_api(client).status_code == 200

    head_client = auth_client(make_head())
    assert (
        head_client.post(
            f"/api/v1/exit-interviews/{exit_id}/reopen",
            data=json.dumps({"reason": "Sensitive correction reason"}),
            content_type="application/json",
            **csrf(head_client),
        ).status_code
        == 200
    )

    events = AuditEvent.objects.filter(
        action__in=[
            "exit_interview.created",
            "exit_interview.submitted",
            "exit_interview.reopened",
            "exit_interview.resubmitted",
        ],
        target_id=exit_id,
    )
    serialized = json.dumps([event.metadata for event in events])
    for secret in (
        "Sensitive identifiable comment",
        "Sensitive address",
        "Sensitive phone",
        "Sensitive correction reason",
        "Form Local Student",
        "BS Information Systems",
    ):
        assert secret not in serialized
    assert all(event.target_type == "exitinterviews.exitinterview" for event in events)


@pytest.mark.django_db
def test_exit_interview_does_not_create_or_mutate_unrelated_domains():
    sync_policy()
    student = make_user("nocoupling@example.edu")
    current = make_year()
    make_inventory(student, current)
    client = auth_client(student)

    before = {
        "encounters": CounselingEncounter.objects.count(),
        "routine": RoutineInterview.objects.count(),
        "referrals": Referral.objects.count(),
        "call_slips": CallSlip.objects.count(),
    }
    assert ensure_api(client).status_code == 200
    assert put_api(client, valid_payload()).status_code == 200
    assert submit_api(client).status_code == 200

    assert CounselingEncounter.objects.count() == before["encounters"]
    assert RoutineInterview.objects.count() == before["routine"]
    assert Referral.objects.count() == before["referrals"]
    assert CallSlip.objects.count() == before["call_slips"]
    assert not Service.objects.filter(code="EXIT_INTERVIEW").exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_ensure_creates_only_one_current_year_exit_interview():
    sync_policy()
    student = make_user("concurrent-exit@example.edu")
    current = make_year()
    make_inventory(student, current)

    def create_once():
        close_old_connections()
        try:
            local_student = User.objects.select_related("role").get(pk=student.pk)
            item = ensure_my_current(
                student=local_student,
                context=AuditContext.user(local_student),
            )
            return item.pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: create_once(), range(2)))

    assert ids[0] == ids[1]
    assert ExitInterview.objects.filter(student_id=student.pk, academic_year=current).count() == 1
    assert AuditEvent.objects.filter(action="exit_interview.created").count() == 1


@pytest.mark.django_db
def test_database_constraints_protect_rating_ranges_and_item_codes():
    sync_policy()
    student = make_user("db-constraints@example.edu")
    current = make_year()
    make_inventory(student, current)
    item = ensure_my_current(student=student, context=AuditContext.user(student))

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExitInterviewSelfAssessmentRating.objects.create(
                exit_interview=item,
                item_code="INVENTED",
                rating=5,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ExitInterviewCollegeFeedbackRating.objects.create(
                exit_interview=item,
                item_code=CollegeFeedbackItem.DEAN_AVAILABILITY,
                rating=6,
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [StudentLifecycleStatus.GRADUATED, StudentLifecycleStatus.FORMER],
)
def test_non_current_student_keeps_exit_history_but_cannot_mutate_or_be_reopened(status):
    sync_policy()
    student = make_user(f"exit-{status.lower()}@example.edu")
    head = make_head(f"head-{status.lower()}@example.edu")
    current = make_year(label="2099-2100")
    make_inventory(student, current, submitted=True)
    student_client = auth_client(student)

    ensured = ensure_api(student_client)
    assert ensured.status_code == 200
    exit_id = ensured.json()["id"]
    assert put_api(student_client, valid_payload()).status_code == 200
    assert submit_api(student_client).status_code == 200

    student.student_lifecycle_status = status
    student.save(update_fields=["student_lifecycle_status", "updated_at"])

    current_read = student_client.get("/api/v1/exit-interviews/me/current")
    assert current_read.status_code == 200
    listing = student_client.get("/api/v1/exit-interviews/me")
    assert listing.status_code == 200
    detail = student_client.get(f"/api/v1/exit-interviews/me/{exit_id}")
    assert detail.status_code == 200

    blocked_ensure = ensure_api(student_client)
    assert blocked_ensure.status_code == 409
    assert blocked_ensure.json()["error"]["code"] == "current_student_required"
    blocked_edit = put_api(student_client, valid_payload())
    assert blocked_edit.status_code == 409
    assert blocked_edit.json()["error"]["code"] == "current_student_required"
    blocked_submit = submit_api(student_client)
    assert blocked_submit.status_code == 409
    assert blocked_submit.json()["error"]["code"] == "current_student_required"

    head_client = auth_client(head)
    reopen = head_client.post(
        f"/api/v1/exit-interviews/{exit_id}/reopen",
        data=json.dumps({"reason": "Administrative correction request"}),
        content_type="application/json",
        **csrf(head_client),
    )
    assert reopen.status_code == 409
    assert reopen.json()["error"]["code"] == "current_student_required"
    row = ExitInterview.objects.get(pk=exit_id)
    assert row.status == "SUBMITTED"
    assert not ExitInterviewReopenEvent.objects.filter(exit_interview=row).exists()
