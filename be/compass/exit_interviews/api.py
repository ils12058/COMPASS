"""Student self-service and Head Guidance API for Exit Interview records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .models import (
    CareerMode,
    CollegeFeedbackItem,
    DelayReason,
    ExitInterviewStatus,
    ProgramCompletion,
    SelfAssessmentItem,
    SignificantLearningExperience,
    StudyCareerChoice,
    WorkCareerChoice,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    ExitInterviewConflict,
    ExitInterviewCurrentAcademicYearNotConfigured,
    ExitInterviewError,
    ExitInterviewInventoryRequired,
    ExitInterviewNotFound,
    ExitInterviewNotPermitted,
    InvalidExitInterviewInput,
    ensure_my_current,
    get_for_head,
    get_mine,
    get_my_current,
    list_for_head,
    list_mine,
    reopen_for_correction,
    replace_my_current,
    submit_my_current,
)

router = Router(tags=["exit-interviews"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ExitInterviewStatusValue(StrEnum):
    DRAFT = ExitInterviewStatus.DRAFT
    SUBMITTED = ExitInterviewStatus.SUBMITTED


class ProgramCompletionValue(StrEnum):
    ACCORDING_TO_SCHEDULE = ProgramCompletion.ACCORDING_TO_SCHEDULE
    WITH_SOME_DELAY = ProgramCompletion.WITH_SOME_DELAY


class DelayReasonValue(StrEnum):
    TRANSFEREE = DelayReason.TRANSFEREE
    ACADEMIC_FAILURES = DelayReason.ACADEMIC_FAILURES
    OTHER = DelayReason.OTHER


class SignificantLearningValue(StrEnum):
    INDEPENDENCE = SignificantLearningExperience.INDEPENDENCE
    INTERPERSONAL_RELATIONS = SignificantLearningExperience.INTERPERSONAL_RELATIONS
    INTELLECTUAL_GROWTH = SignificantLearningExperience.INTELLECTUAL_GROWTH
    SPIRITUAL_GROWTH = SignificantLearningExperience.SPIRITUAL_GROWTH
    RESPONSIBILITY = SignificantLearningExperience.RESPONSIBILITY
    WORKING_UNDER_PRESSURE = SignificantLearningExperience.WORKING_UNDER_PRESSURE
    TIME_MANAGEMENT = SignificantLearningExperience.TIME_MANAGEMENT
    SETTING_PRIORITIES = SignificantLearningExperience.SETTING_PRIORITIES
    OTHER = SignificantLearningExperience.OTHER


class CareerModeValue(StrEnum):
    WORK = CareerMode.WORK
    STUDY = CareerMode.STUDY


class WorkCareerChoiceValue(StrEnum):
    RELATED_FIELD = WorkCareerChoice.RELATED_FIELD
    UNRELATED_FIELD = WorkCareerChoice.UNRELATED_FIELD
    FAMILY_BUSINESS = WorkCareerChoice.FAMILY_BUSINESS
    OWN_BUSINESS = WorkCareerChoice.OWN_BUSINESS
    WORK_ABROAD = WorkCareerChoice.WORK_ABROAD
    NO_DEFINITE_PLAN = WorkCareerChoice.NO_DEFINITE_PLAN


class StudyCareerChoiceValue(StrEnum):
    RELATED_FIELD = StudyCareerChoice.RELATED_FIELD
    UNRELATED_FIELD = StudyCareerChoice.UNRELATED_FIELD


class SelfAssessmentItemValue(StrEnum):
    PRIDE_CONFIDENCE_CNSC = SelfAssessmentItem.PRIDE_CONFIDENCE_CNSC
    ACADEMIC_RECREATION_BALANCE = SelfAssessmentItem.ACADEMIC_RECREATION_BALANCE
    HOLISTIC_PERSONAL_WELL_BEING = SelfAssessmentItem.HOLISTIC_PERSONAL_WELL_BEING
    INTEGRATE_KNOWLEDGE_EXPERIENCE = SelfAssessmentItem.INTEGRATE_KNOWLEDGE_EXPERIENCE
    CAREER_GOAL_CLARITY = SelfAssessmentItem.CAREER_GOAL_CLARITY
    SELF_ESTEEM = SelfAssessmentItem.SELF_ESTEEM
    SELF_AWARENESS = SelfAssessmentItem.SELF_AWARENESS
    COPE_WITH_PRESSURES = SelfAssessmentItem.COPE_WITH_PRESSURES
    DEAL_WITH_DIFFERENT_WALKS = SelfAssessmentItem.DEAL_WITH_DIFFERENT_WALKS
    LEADERSHIP = SelfAssessmentItem.LEADERSHIP
    COMMUNICATION_SKILLS = SelfAssessmentItem.COMMUNICATION_SKILLS
    CIVIC_MINDEDNESS = SelfAssessmentItem.CIVIC_MINDEDNESS
    INITIATIVE = SelfAssessmentItem.INITIATIVE
    DECISION_MAKING = SelfAssessmentItem.DECISION_MAKING
    RELATIONSHIP_WITH_GOD = SelfAssessmentItem.RELATIONSHIP_WITH_GOD


class CollegeFeedbackItemValue(StrEnum):
    DEAN_AVAILABILITY = CollegeFeedbackItem.DEAN_AVAILABILITY
    DEAN_OPEN_MINDEDNESS = CollegeFeedbackItem.DEAN_OPEN_MINDEDNESS
    DEAN_CONCERN_FOR_STUDENTS = CollegeFeedbackItem.DEAN_CONCERN_FOR_STUDENTS
    DEAN_COMMITMENT = CollegeFeedbackItem.DEAN_COMMITMENT
    DEAN_APPROACHABILITY = CollegeFeedbackItem.DEAN_APPROACHABILITY
    PROGRAM_CHAIR_AVAILABILITY = CollegeFeedbackItem.PROGRAM_CHAIR_AVAILABILITY
    PROGRAM_CHAIR_APPROACHABILITY = CollegeFeedbackItem.PROGRAM_CHAIR_APPROACHABILITY
    PROGRAM_CHAIR_CONCERN_FOR_STUDENTS = CollegeFeedbackItem.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS
    FACULTY_AVAILABILITY = CollegeFeedbackItem.FACULTY_AVAILABILITY
    FACULTY_APPROACHABILITY = CollegeFeedbackItem.FACULTY_APPROACHABILITY
    FACULTY_KNOWLEDGE_SUBJECT_MATTER = CollegeFeedbackItem.FACULTY_KNOWLEDGE_SUBJECT_MATTER
    FACULTY_TEACHING_SKILLS = CollegeFeedbackItem.FACULTY_TEACHING_SKILLS
    CURRICULUM_RELEVANCE_SUBJECTS = CollegeFeedbackItem.CURRICULUM_RELEVANCE_SUBJECTS
    CURRICULUM_SYSTEMATIC_SEQUENCING = CollegeFeedbackItem.CURRICULUM_SYSTEMATIC_SEQUENCING
    CURRICULUM_COMPLETENESS = CollegeFeedbackItem.CURRICULUM_COMPLETENESS
    GUIDANCE_COUNSELOR_AVAILABILITY = CollegeFeedbackItem.GUIDANCE_COUNSELOR_AVAILABILITY
    GUIDANCE_COUNSELOR_APPROACHABILITY = CollegeFeedbackItem.GUIDANCE_COUNSELOR_APPROACHABILITY
    GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS = (
        CollegeFeedbackItem.GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS
    )
    GUIDANCE_COUNSELOR_EFFICIENCY = CollegeFeedbackItem.GUIDANCE_COUNSELOR_EFFICIENCY
    OFFICE_STAFF_SERVICE_ORIENTED = CollegeFeedbackItem.OFFICE_STAFF_SERVICE_ORIENTED
    OFFICE_STAFF_AVAILABILITY = CollegeFeedbackItem.OFFICE_STAFF_AVAILABILITY
    OFFICE_STAFF_CONCERN_FOR_STUDENTS = CollegeFeedbackItem.OFFICE_STAFF_CONCERN_FOR_STUDENTS
    OFFICE_STAFF_APPROACHABILITY = CollegeFeedbackItem.OFFICE_STAFF_APPROACHABILITY
    FACILITIES_MAINTENANCE_CONDITION = CollegeFeedbackItem.FACILITIES_MAINTENANCE_CONDITION
    FACILITIES_AVAILABILITY = CollegeFeedbackItem.FACILITIES_AVAILABILITY
    FACILITIES_COMPLETENESS = CollegeFeedbackItem.FACILITIES_COMPLETENESS


class AcademicYearSummary(StrictSchema):
    id: UUID
    label: str


class StudentSummary(StrictSchema):
    id: UUID
    display_name: str


class SelfAssessmentRatingPayload(StrictSchema):
    item_code: SelfAssessmentItemValue
    rating: int = Field(ge=1, le=5)


class CollegeFeedbackRatingPayload(StrictSchema):
    item_code: CollegeFeedbackItemValue
    rating: int = Field(
        ge=0,
        le=5,
        description=(
            "Source Page 2 visibly permits numeric 0; the source does not define its meaning."
        ),
    )


class ExitInterviewDraftPayload(StrictSchema):
    student_name: str = ""
    age: int | None = Field(default=None, ge=0, le=150)
    civil_status: str = ""
    course: str = ""
    major: str = ""
    email_address: str = ""
    home_address: str = ""
    contact_number: str = ""

    program_completion: ProgramCompletionValue | None = None
    extra_terms_count: int | None = Field(default=None, ge=1)
    delay_reasons: list[DelayReasonValue] = Field(default_factory=list)
    delay_other: str = ""

    significant_learning_experiences: list[SignificantLearningValue] = Field(default_factory=list)
    significant_learning_other: str = ""

    career_modes: list[CareerModeValue] = Field(default_factory=list)
    work_choices: list[WorkCareerChoiceValue] = Field(default_factory=list)
    study_choices: list[StudyCareerChoiceValue] = Field(default_factory=list)

    self_assessment_ratings: list[SelfAssessmentRatingPayload] = Field(default_factory=list)
    college_feedback_ratings: list[CollegeFeedbackRatingPayload] = Field(default_factory=list)

    dean_comments: str = ""
    program_chair_comments: str = ""
    faculty_comments: str = ""
    curriculum_comments: str = ""
    guidance_counselor_comments: str = ""
    office_staff_comments: str = ""
    facilities_comments: str = ""
    suggestions_recommendations: str = ""


class SelfAssessmentRatingResponse(StrictSchema):
    item_code: SelfAssessmentItemValue
    item_label: str
    rating: int


class CollegeFeedbackRatingResponse(StrictSchema):
    item_code: CollegeFeedbackItemValue
    item_label: str
    category: str
    rating: int = Field(
        description=(
            "Numeric source response. Value 0 is preserved without a fabricated semantic label."
        )
    )


class ReopenEventResponse(StrictSchema):
    id: UUID
    reopened_at: datetime
    reopened_by: StudentSummary
    reason: str


class ExitInterviewDetailResponse(ExitInterviewDraftPayload):
    id: UUID
    student: StudentSummary
    academic_year: AcademicYearSummary
    inventory_id: UUID
    status: ExitInterviewStatusValue
    self_assessment_ratings: list[SelfAssessmentRatingResponse]
    college_feedback_ratings: list[CollegeFeedbackRatingResponse]
    first_submitted_at: datetime | None
    last_submitted_at: datetime | None
    reopen_events: list[ReopenEventResponse]
    created_at: datetime
    updated_at: datetime


class ExitInterviewSummaryResponse(StrictSchema):
    id: UUID
    student: StudentSummary
    student_name: str
    academic_year: AcademicYearSummary
    status: ExitInterviewStatusValue
    first_submitted_at: datetime | None
    last_submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExitInterviewHistoryResponse(StrictSchema):
    items: list[ExitInterviewSummaryResponse]


class ExitInterviewPageResponse(StrictSchema):
    items: list[ExitInterviewSummaryResponse]
    page: int
    page_size: int
    has_next: bool


class ReopenRequest(StrictSchema):
    reason: str


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or user.role.code != "STUDENT" or not user.has_capability(capability):
        raise APIError(403, "permission_denied", "Student Exit Interview access is required.")


def _require_head(request, capability: str) -> None:
    user = request.auth_user
    if not user.is_active or not user.has_capability(capability):
        raise APIError(
            403, "permission_denied", "Head Guidance Exit Interview authority is required."
        )


def _raise(exc: ExitInterviewError) -> NoReturn:
    if isinstance(exc, ExitInterviewNotFound):
        raise APIError(404, "exit_interview_not_found", str(exc)) from exc
    if isinstance(exc, ExitInterviewNotPermitted):
        raise APIError(403, "permission_denied", str(exc)) from exc
    if isinstance(exc, ExitInterviewCurrentAcademicYearNotConfigured):
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    if isinstance(exc, ExitInterviewInventoryRequired):
        raise APIError(409, "exit_interview_inventory_required", str(exc)) from exc
    if isinstance(exc, ExitInterviewConflict):
        raise APIError(409, "exit_interview_conflict", str(exc)) from exc
    if isinstance(exc, InvalidExitInterviewInput):
        raise APIError(422, "invalid_exit_interview_request", str(exc)) from exc
    raise APIError(
        500,
        "internal_error",
        "The Exit Interview operation could not be completed.",
    ) from exc


def _academic_year(item) -> dict[str, object]:
    return {"id": item.pk, "label": item.label}


def _person(user) -> dict[str, object]:
    return {"id": user.pk, "display_name": user.get_full_name()}


def _feedback_category(item_code: str) -> str:
    if item_code.startswith("DEAN_"):
        return "DEAN"
    if item_code.startswith("PROGRAM_CHAIR_"):
        return "PROG CHAIR"
    if item_code.startswith("FACULTY_"):
        return "FACULTY"
    if item_code.startswith("CURRICULUM_"):
        return "CURRICULUM"
    if item_code.startswith("GUIDANCE_COUNSELOR_"):
        return "GUIDANCE COUNSELOR"
    if item_code.startswith("OFFICE_STAFF_"):
        return "OFFICE STAFF"
    if item_code.startswith("FACILITIES_"):
        return "FACILITIES"
    raise RuntimeError("Unsupported fixed College Feedback item code.")


def _ordered_self_ratings(item) -> list[dict[str, object]]:
    by_code = {row.item_code: row for row in item.self_assessment_ratings.all()}
    return [
        {
            "item_code": code,
            "item_label": SelfAssessmentItem(code).label,
            "rating": by_code[code].rating,
        }
        for code in SelfAssessmentItem.values
        if code in by_code
    ]


def _ordered_feedback_ratings(item) -> list[dict[str, object]]:
    by_code = {row.item_code: row for row in item.college_feedback_ratings.all()}
    return [
        {
            "item_code": code,
            "item_label": CollegeFeedbackItem(code).label,
            "category": _feedback_category(code),
            "rating": by_code[code].rating,
        }
        for code in CollegeFeedbackItem.values
        if code in by_code
    ]


def _reopen_events(item) -> list[dict[str, object]]:
    return [
        {
            "id": event.pk,
            "reopened_at": event.reopened_at,
            "reopened_by": _person(event.reopened_by),
            "reason": event.reason,
        }
        for event in item.reopen_events.all()
    ]


def _summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student": _person(item.student),
        "student_name": item.student_name_snapshot,
        "academic_year": _academic_year(item.academic_year),
        "status": item.status,
        "first_submitted_at": item.first_submitted_at,
        "last_submitted_at": item.last_submitted_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _detail(item) -> dict[str, object]:
    return {
        **_summary(item),
        "inventory_id": item.inventory_id,
        "age": item.age_snapshot,
        "civil_status": item.civil_status_snapshot,
        "course": item.course_snapshot,
        "major": item.major_snapshot,
        "email_address": item.email_snapshot,
        "home_address": item.home_address_snapshot,
        "contact_number": item.contact_number_snapshot,
        "program_completion": item.program_completion or None,
        "extra_terms_count": item.extra_terms_count,
        "delay_reasons": item.delay_reasons,
        "delay_other": item.delay_other,
        "significant_learning_experiences": item.significant_learning_experiences,
        "significant_learning_other": item.significant_learning_other,
        "career_modes": item.career_modes,
        "work_choices": item.work_choices,
        "study_choices": item.study_choices,
        "self_assessment_ratings": _ordered_self_ratings(item),
        "college_feedback_ratings": _ordered_feedback_ratings(item),
        "dean_comments": item.dean_comments,
        "program_chair_comments": item.program_chair_comments,
        "faculty_comments": item.faculty_comments,
        "curriculum_comments": item.curriculum_comments,
        "guidance_counselor_comments": item.guidance_counselor_comments,
        "office_staff_comments": item.office_staff_comments,
        "facilities_comments": item.facilities_comments,
        "suggestions_recommendations": item.suggestions_recommendations,
        "reopen_events": _reopen_events(item),
    }


def _payload_values(payload: ExitInterviewDraftPayload) -> dict[str, object]:
    values = payload.model_dump(mode="python")
    values["student_name_snapshot"] = values.pop("student_name")
    values["age_snapshot"] = values.pop("age")
    values["civil_status_snapshot"] = values.pop("civil_status")
    values["course_snapshot"] = values.pop("course")
    values["major_snapshot"] = values.pop("major")
    values["email_snapshot"] = values.pop("email_address")
    values["home_address_snapshot"] = values.pop("home_address")
    values["contact_number_snapshot"] = values.pop("contact_number")
    return values


# Static Student self routes are registered before UUID routes.


@router.post(
    "/me/current",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="exitInterviewsEnsureMyCurrent",
)
def exit_interviews_ensure_my_current(request):
    _require_student(request, "exit_interviews.manage_self")
    try:
        item = ensure_my_current(student=request.auth_user, context=_context(request))
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/me/current",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="exitInterviewsGetMyCurrent",
)
def exit_interviews_get_my_current(request):
    _require_student(request, "exit_interviews.view_self")
    try:
        item = get_my_current(request.auth_user)
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)


@router.put(
    "/me/current",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="exitInterviewsUpdateMyCurrent",
)
def exit_interviews_update_my_current(request, payload: ExitInterviewDraftPayload):
    _require_student(request, "exit_interviews.manage_self")
    try:
        item = replace_my_current(
            student=request.auth_user,
            values=_payload_values(payload),
        )
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)


@router.post(
    "/me/current/submit",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="exitInterviewsSubmitMyCurrent",
)
def exit_interviews_submit_my_current(request):
    _require_student(request, "exit_interviews.manage_self")
    try:
        item = submit_my_current(
            student=request.auth_user,
            context=_context(request),
        )
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/me",
    response=response_with_errors(ExitInterviewHistoryResponse, 401, 403),
    auth=session_auth,
    operation_id="exitInterviewsListMine",
)
def exit_interviews_list_mine(request):
    _require_student(request, "exit_interviews.view_self")
    try:
        items = list_mine(request.auth_user)
    except ExitInterviewError as exc:
        _raise(exc)
    return {"items": [_summary(item) for item in items]}


@router.get(
    "/me/{exit_interview_id}",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="exitInterviewsGetMine",
)
def exit_interviews_get_mine(request, exit_interview_id: UUID):
    _require_student(request, "exit_interviews.view_self")
    try:
        item = get_mine(student=request.auth_user, exit_interview_id=exit_interview_id)
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "",
    response=response_with_errors(ExitInterviewPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="exitInterviewsList",
)
def exit_interviews_list(
    request,
    academic_year_id: UUID | None = None,
    status: ExitInterviewStatusValue | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_head(request, "exit_interviews.view")
    try:
        result = list_for_head(
            actor=request.auth_user,
            academic_year_id=academic_year_id,
            status=status.value if status is not None else None,
            page=page,
            page_size=page_size,
        )
    except ExitInterviewError as exc:
        _raise(exc)
    return {
        "items": [_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{exit_interview_id}",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="exitInterviewsGet",
)
def exit_interviews_get(request, exit_interview_id: UUID):
    _require_head(request, "exit_interviews.view")
    try:
        item = get_for_head(actor=request.auth_user, exit_interview_id=exit_interview_id)
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)


@router.post(
    "/{exit_interview_id}/reopen",
    response=response_with_errors(ExitInterviewDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="exitInterviewsReopen",
)
def exit_interviews_reopen(
    request,
    exit_interview_id: UUID,
    payload: ReopenRequest,
):
    _require_head(request, "exit_interviews.reopen")
    try:
        item = reopen_for_correction(
            actor=request.auth_user,
            exit_interview_id=exit_interview_id,
            reason=payload.reason,
            context=_context(request),
        )
    except ExitInterviewError as exc:
        _raise(exc)
    return _detail(item)
