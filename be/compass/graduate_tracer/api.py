"""Django Ninja API for the supplied CHED Graduate Tracer Survey foundation."""

from __future__ import annotations

from datetime import date, datetime
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
    GraduateTracerStatus,
    GTSAdvancedStudyReason,
    GTSBusinessLine,
    GTSCivilStatus,
    GTSDegreeReason,
    GTSEarningBracket,
    GTSEmploymentState,
    GTSFirstJobDuration,
    GTSFirstJobSource,
    GTSJobLevel,
    GTSJobReason,
    GTSPlaceOfWork,
    GTSPresentEmploymentStatus,
    GTSRegionOfOrigin,
    GTSResidenceLocation,
    GTSSex,
    GTSStayingReason,
    GTSUnemploymentReason,
    GTSUsefulCompetency,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    GraduateTracerConflict,
    GraduateTracerError,
    GraduateTracerGraduatedStudentRequired,
    GraduateTracerNotFound,
    GraduateTracerNotPermitted,
    InvalidGraduateTracerInput,
    ensure_my_response,
    get_my_response,
    get_submitted_for_head,
    list_submitted_for_head,
    replace_my_draft,
    submit_my_response,
)

router = Router(tags=["graduate-tracer"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class GraduateTracerStatusValue(StrEnum):
    DRAFT = GraduateTracerStatus.DRAFT
    SUBMITTED = GraduateTracerStatus.SUBMITTED


class GTSCivilStatusValue(StrEnum):
    SINGLE = GTSCivilStatus.SINGLE
    SEPARATED = GTSCivilStatus.SEPARATED
    WIDOW_WIDOWER = GTSCivilStatus.WIDOW_WIDOWER
    MARRIED = GTSCivilStatus.MARRIED
    SINGLE_PARENT = GTSCivilStatus.SINGLE_PARENT


class GTSSexValue(StrEnum):
    MALE = GTSSex.MALE
    FEMALE = GTSSex.FEMALE


class GTSRegionOfOriginValue(StrEnum):
    REGION_1 = GTSRegionOfOrigin.REGION_1
    REGION_2 = GTSRegionOfOrigin.REGION_2
    REGION_3 = GTSRegionOfOrigin.REGION_3
    REGION_4 = GTSRegionOfOrigin.REGION_4
    REGION_5 = GTSRegionOfOrigin.REGION_5
    REGION_6 = GTSRegionOfOrigin.REGION_6
    REGION_7 = GTSRegionOfOrigin.REGION_7
    REGION_8 = GTSRegionOfOrigin.REGION_8
    REGION_9 = GTSRegionOfOrigin.REGION_9
    REGION_10 = GTSRegionOfOrigin.REGION_10
    REGION_11 = GTSRegionOfOrigin.REGION_11
    REGION_12 = GTSRegionOfOrigin.REGION_12
    NCR = GTSRegionOfOrigin.NCR
    CAR = GTSRegionOfOrigin.CAR
    ARMM = GTSRegionOfOrigin.ARMM
    CARAGA = GTSRegionOfOrigin.CARAGA


class GTSResidenceLocationValue(StrEnum):
    CITY = GTSResidenceLocation.CITY
    MUNICIPALITY = GTSResidenceLocation.MUNICIPALITY


class GTSDegreeReasonValue(StrEnum):
    HIGH_GRADES_RELATED_COURSE = GTSDegreeReason.HIGH_GRADES_RELATED_COURSE
    GOOD_GRADES_HIGH_SCHOOL = GTSDegreeReason.GOOD_GRADES_HIGH_SCHOOL
    PARENTS_RELATIVES = GTSDegreeReason.PARENTS_RELATIVES
    PEER_INFLUENCE = GTSDegreeReason.PEER_INFLUENCE
    ROLE_MODEL = GTSDegreeReason.ROLE_MODEL
    PASSION_PROFESSION = GTSDegreeReason.PASSION_PROFESSION
    IMMEDIATE_EMPLOYMENT = GTSDegreeReason.IMMEDIATE_EMPLOYMENT
    STATUS_PRESTIGE = GTSDegreeReason.STATUS_PRESTIGE
    COURSE_AVAILABILITY = GTSDegreeReason.COURSE_AVAILABILITY
    CAREER_ADVANCEMENT = GTSDegreeReason.CAREER_ADVANCEMENT
    AFFORDABLE = GTSDegreeReason.AFFORDABLE
    ATTRACTIVE_COMPENSATION = GTSDegreeReason.ATTRACTIVE_COMPENSATION
    EMPLOYMENT_ABROAD = GTSDegreeReason.EMPLOYMENT_ABROAD
    NO_PARTICULAR_CHOICE = GTSDegreeReason.NO_PARTICULAR_CHOICE


class GTSAdvancedStudyReasonValue(StrEnum):
    PROMOTION = GTSAdvancedStudyReason.PROMOTION
    PROFESSIONAL_DEVELOPMENT = GTSAdvancedStudyReason.PROFESSIONAL_DEVELOPMENT
    OTHER = GTSAdvancedStudyReason.OTHER


class GTSEmploymentStateValue(StrEnum):
    EMPLOYED = GTSEmploymentState.EMPLOYED
    NOT_EMPLOYED = GTSEmploymentState.NOT_EMPLOYED
    NEVER_EMPLOYED = GTSEmploymentState.NEVER_EMPLOYED


class GTSUnemploymentReasonValue(StrEnum):
    ADVANCE_STUDY = GTSUnemploymentReason.ADVANCE_STUDY
    FAMILY_CONCERN = GTSUnemploymentReason.FAMILY_CONCERN
    HEALTH_RELATED = GTSUnemploymentReason.HEALTH_RELATED
    LACK_WORK_EXPERIENCE = GTSUnemploymentReason.LACK_WORK_EXPERIENCE
    NO_JOB_OPPORTUNITY = GTSUnemploymentReason.NO_JOB_OPPORTUNITY
    DID_NOT_LOOK = GTSUnemploymentReason.DID_NOT_LOOK
    OTHER = GTSUnemploymentReason.OTHER


class GTSPresentEmploymentStatusValue(StrEnum):
    REGULAR_PERMANENT = GTSPresentEmploymentStatus.REGULAR_PERMANENT
    TEMPORARY = GTSPresentEmploymentStatus.TEMPORARY
    CASUAL = GTSPresentEmploymentStatus.CASUAL
    CONTRACTUAL = GTSPresentEmploymentStatus.CONTRACTUAL
    SELF_EMPLOYED = GTSPresentEmploymentStatus.SELF_EMPLOYED


class GTSBusinessLineValue(StrEnum):
    AGRICULTURE_HUNTING_FORESTRY = GTSBusinessLine.AGRICULTURE_HUNTING_FORESTRY
    FISHING = GTSBusinessLine.FISHING
    MINING_QUARRYING = GTSBusinessLine.MINING_QUARRYING
    MANUFACTURING = GTSBusinessLine.MANUFACTURING
    ELECTRICITY_GAS_WATER = GTSBusinessLine.ELECTRICITY_GAS_WATER
    CONSTRUCTION = GTSBusinessLine.CONSTRUCTION
    WHOLESALE_RETAIL_REPAIR = GTSBusinessLine.WHOLESALE_RETAIL_REPAIR
    HOTELS_RESTAURANTS = GTSBusinessLine.HOTELS_RESTAURANTS
    TRANSPORT_STORAGE_COMMUNICATION = GTSBusinessLine.TRANSPORT_STORAGE_COMMUNICATION
    FINANCIAL_INTERMEDIATION = GTSBusinessLine.FINANCIAL_INTERMEDIATION
    REAL_ESTATE_RENTING_BUSINESS = GTSBusinessLine.REAL_ESTATE_RENTING_BUSINESS
    PUBLIC_ADMIN_DEFENSE_SOCIAL_SECURITY = GTSBusinessLine.PUBLIC_ADMIN_DEFENSE_SOCIAL_SECURITY
    EDUCATION = GTSBusinessLine.EDUCATION
    HEALTH_SOCIAL_WORK = GTSBusinessLine.HEALTH_SOCIAL_WORK
    OTHER_COMMUNITY_SOCIAL_PERSONAL = GTSBusinessLine.OTHER_COMMUNITY_SOCIAL_PERSONAL
    PRIVATE_HOUSEHOLDS_EMPLOYED_PERSONS = GTSBusinessLine.PRIVATE_HOUSEHOLDS_EMPLOYED_PERSONS
    EXTRA_TERRITORIAL_ORGANIZATIONS = GTSBusinessLine.EXTRA_TERRITORIAL_ORGANIZATIONS


class GTSPlaceOfWorkValue(StrEnum):
    LOCAL = GTSPlaceOfWork.LOCAL
    ABROAD = GTSPlaceOfWork.ABROAD


class GTSStayingReasonValue(StrEnum):
    SALARIES_BENEFITS = GTSStayingReason.SALARIES_BENEFITS
    CAREER_CHALLENGE = GTSStayingReason.CAREER_CHALLENGE
    RELATED_SPECIAL_SKILL = GTSStayingReason.RELATED_SPECIAL_SKILL
    RELATED_COURSE = GTSStayingReason.RELATED_COURSE
    PROXIMITY_RESIDENCE = GTSStayingReason.PROXIMITY_RESIDENCE
    PEER_INFLUENCE = GTSStayingReason.PEER_INFLUENCE
    FAMILY_INFLUENCE = GTSStayingReason.FAMILY_INFLUENCE
    OTHER = GTSStayingReason.OTHER


class GTSJobReasonValue(StrEnum):
    SALARIES_BENEFITS = GTSJobReason.SALARIES_BENEFITS
    CAREER_CHALLENGE = GTSJobReason.CAREER_CHALLENGE
    RELATED_SPECIAL_SKILLS = GTSJobReason.RELATED_SPECIAL_SKILLS
    PROXIMITY_RESIDENCE = GTSJobReason.PROXIMITY_RESIDENCE
    OTHER = GTSJobReason.OTHER


class GTSFirstJobDurationValue(StrEnum):
    LESS_THAN_MONTH = GTSFirstJobDuration.LESS_THAN_MONTH
    ONE_TO_SIX_MONTHS = GTSFirstJobDuration.ONE_TO_SIX_MONTHS
    SEVEN_TO_ELEVEN_MONTHS = GTSFirstJobDuration.SEVEN_TO_ELEVEN_MONTHS
    ONE_TO_LT_TWO_YEARS = GTSFirstJobDuration.ONE_TO_LT_TWO_YEARS
    TWO_TO_LT_THREE_YEARS = GTSFirstJobDuration.TWO_TO_LT_THREE_YEARS
    THREE_TO_LT_FOUR_YEARS = GTSFirstJobDuration.THREE_TO_LT_FOUR_YEARS
    OTHER = GTSFirstJobDuration.OTHER


class GTSFirstJobSourceValue(StrEnum):
    ADVERTISEMENT = GTSFirstJobSource.ADVERTISEMENT
    WALK_IN = GTSFirstJobSource.WALK_IN
    RECOMMENDED = GTSFirstJobSource.RECOMMENDED
    FRIENDS = GTSFirstJobSource.FRIENDS
    SCHOOL_PLACEMENT = GTSFirstJobSource.SCHOOL_PLACEMENT
    FAMILY_BUSINESS = GTSFirstJobSource.FAMILY_BUSINESS
    JOB_FAIR_PESO = GTSFirstJobSource.JOB_FAIR_PESO
    OTHER = GTSFirstJobSource.OTHER


class GTSJobLevelValue(StrEnum):
    RANK_CLERICAL = GTSJobLevel.RANK_CLERICAL
    PROFESSIONAL_TECHNICAL_SUPERVISORY = GTSJobLevel.PROFESSIONAL_TECHNICAL_SUPERVISORY
    MANAGERIAL_EXECUTIVE = GTSJobLevel.MANAGERIAL_EXECUTIVE
    SELF_EMPLOYED = GTSJobLevel.SELF_EMPLOYED


class GTSEarningBracketValue(StrEnum):
    BELOW_5000 = GTSEarningBracket.BELOW_5000
    FROM_5000_TO_LT_10000 = GTSEarningBracket.FROM_5000_TO_LT_10000
    FROM_10000_TO_LT_15000 = GTSEarningBracket.FROM_10000_TO_LT_15000
    FROM_15000_TO_LT_20000 = GTSEarningBracket.FROM_15000_TO_LT_20000
    FROM_20000_TO_LT_25000 = GTSEarningBracket.FROM_20000_TO_LT_25000
    FROM_25000_UP = GTSEarningBracket.FROM_25000_UP


class GTSUsefulCompetencyValue(StrEnum):
    COMMUNICATION = GTSUsefulCompetency.COMMUNICATION
    HUMAN_RELATIONS = GTSUsefulCompetency.HUMAN_RELATIONS
    ENTREPRENEURIAL = GTSUsefulCompetency.ENTREPRENEURIAL
    INFORMATION_TECHNOLOGY = GTSUsefulCompetency.INFORMATION_TECHNOLOGY
    PROBLEM_SOLVING = GTSUsefulCompetency.PROBLEM_SOLVING
    CRITICAL_THINKING = GTSUsefulCompetency.CRITICAL_THINKING
    OTHER = GTSUsefulCompetency.OTHER


class GraduateTracerEducationPayload(StrictSchema):
    degree_and_specialization: str
    college_or_university: str
    year_graduated: int = Field(ge=1900)
    honors_or_awards: str = ""


class GraduateTracerProfessionalExamPayload(StrictSchema):
    examination_name: str
    date_taken: date | None = None
    rating: str = ""


class GraduateTracerTrainingPayload(StrictSchema):
    title: str
    duration_and_credits: str = ""
    institution: str = ""


class GraduateTracerDraftPayload(StrictSchema):
    name: str = ""
    permanent_address: str = ""
    email: str = ""
    telephone_contact_numbers: str = ""
    mobile_number: str = ""
    civil_status: GTSCivilStatusValue | None = None
    sex: GTSSexValue | None = None
    birth_date: date | None = None
    region_of_origin: GTSRegionOfOriginValue | None = None
    province: str = ""
    residence_location: GTSResidenceLocationValue | None = None

    education: list[GraduateTracerEducationPayload] = Field(default_factory=list)
    professional_exams: list[GraduateTracerProfessionalExamPayload] = Field(default_factory=list)

    undergraduate_degree_reasons: list[GTSDegreeReasonValue] = Field(default_factory=list)
    graduate_study_reasons: list[GTSDegreeReasonValue] = Field(default_factory=list)
    degree_other_reason: str = ""

    trainings: list[GraduateTracerTrainingPayload] = Field(default_factory=list)
    advanced_study_reasons: list[GTSAdvancedStudyReasonValue] = Field(default_factory=list)
    advanced_study_other_reason: str = ""

    current_employment_state: GTSEmploymentStateValue | None = None
    unemployment_reasons: list[GTSUnemploymentReasonValue] = Field(default_factory=list)
    unemployment_other_reason: str = ""

    present_employment_status: GTSPresentEmploymentStatusValue | None = None
    self_employed_college_skills: str = ""
    present_occupation: str = ""
    employer_business_line: GTSBusinessLineValue | None = None
    place_of_work: GTSPlaceOfWorkValue | None = None
    first_job_after_college: bool | None = None

    reasons_for_staying_on_job: list[GTSStayingReasonValue] = Field(default_factory=list)
    reasons_for_staying_other: str = ""
    first_job_related_to_course: bool | None = None
    reasons_for_accepting_first_job: list[GTSJobReasonValue] = Field(default_factory=list)
    reasons_for_accepting_other: str = ""
    reasons_for_changing_job: list[GTSJobReasonValue] = Field(default_factory=list)
    reasons_for_changing_other: str = ""

    first_job_duration: GTSFirstJobDurationValue | None = None
    first_job_duration_other: str = ""
    first_job_source: GTSFirstJobSourceValue | None = None
    first_job_source_other: str = ""
    time_to_first_job: GTSFirstJobDurationValue | None = None
    time_to_first_job_other: str = ""
    first_job_level: GTSJobLevelValue | None = None
    current_job_level: GTSJobLevelValue | None = None
    initial_gross_monthly_earning: GTSEarningBracketValue | None = None
    curriculum_relevant_to_first_job: bool | None = None
    useful_competencies: list[GTSUsefulCompetencyValue] = Field(default_factory=list)
    useful_competencies_other: str = ""
    curriculum_improvement_suggestions: str = ""


class GraduateTracerStudentSummary(StrictSchema):
    id: UUID
    institutional_id: str | None
    display_name: str


class GraduateTracerDetailResponse(GraduateTracerDraftPayload):
    id: UUID
    student_id: UUID
    student: GraduateTracerStudentSummary
    instrument_schema_version: int
    status: GraduateTracerStatusValue
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GraduateTracerSummaryResponse(StrictSchema):
    id: UUID
    student_id: UUID
    student: GraduateTracerStudentSummary
    name: str
    current_employment_state: GTSEmploymentStateValue
    instrument_schema_version: int
    submitted_at: datetime


class GraduateTracerPageResponse(StrictSchema):
    items: list[GraduateTracerSummaryResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    actor = request.auth_user
    if not actor.is_active or actor.role.code != "STUDENT" or not actor.has_capability(capability):
        raise APIError(
            403,
            "permission_denied",
            "Student Graduate Tracer access is required.",
        )


def _require_viewer(request) -> None:
    actor = request.auth_user
    if not actor.is_active or not actor.has_capability("graduate_tracer.view"):
        raise APIError(
            403,
            "permission_denied",
            "Head Guidance Graduate Tracer review authority is required.",
        )


def _raise(exc: GraduateTracerError) -> NoReturn:
    if isinstance(exc, GraduateTracerNotFound):
        raise APIError(404, "graduate_tracer_not_found", str(exc)) from exc
    if isinstance(exc, GraduateTracerNotPermitted):
        raise APIError(403, "permission_denied", str(exc)) from exc
    if isinstance(exc, GraduateTracerGraduatedStudentRequired):
        raise APIError(409, "graduated_student_required", str(exc)) from exc
    if isinstance(exc, GraduateTracerConflict):
        raise APIError(409, "graduate_tracer_conflict", str(exc)) from exc
    if isinstance(exc, InvalidGraduateTracerInput):
        raise APIError(422, "invalid_graduate_tracer_request", str(exc)) from exc
    raise APIError(
        500,
        "internal_error",
        "The Graduate Tracer operation could not be completed.",
    ) from exc


def _education_rows(item) -> list[dict[str, object]]:
    return [
        {
            "degree_and_specialization": row.degree_and_specialization,
            "college_or_university": row.college_or_university,
            "year_graduated": row.year_graduated,
            "honors_or_awards": row.honors_or_awards,
        }
        for row in item.education_rows.all()
    ]


def _professional_exam_rows(item) -> list[dict[str, object]]:
    return [
        {
            "examination_name": row.examination_name,
            "date_taken": row.date_taken,
            "rating": row.rating,
        }
        for row in item.professional_exam_rows.all()
    ]


def _training_rows(item) -> list[dict[str, object]]:
    return [
        {
            "title": row.title,
            "duration_and_credits": row.duration_and_credits,
            "institution": row.institution,
        }
        for row in item.training_rows.all()
    ]


def _student_summary(item) -> dict[str, object]:
    return {
        "id": item.student_id,
        "institutional_id": item.student.institutional_id,
        "display_name": item.student.get_full_name(),
    }


def _detail(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student_id": item.student_id,
        "student": _student_summary(item),
        "instrument_schema_version": item.instrument_schema_version,
        "status": item.status,
        "submitted_at": item.submitted_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "name": item.name_snapshot,
        "permanent_address": item.permanent_address_snapshot,
        "email": item.email_snapshot,
        "telephone_contact_numbers": item.telephone_contact_numbers_snapshot,
        "mobile_number": item.mobile_number_snapshot,
        "civil_status": item.civil_status or None,
        "sex": item.sex or None,
        "birth_date": item.birth_date,
        "region_of_origin": item.region_of_origin or None,
        "province": item.province,
        "residence_location": item.residence_location or None,
        "education": _education_rows(item),
        "professional_exams": _professional_exam_rows(item),
        "undergraduate_degree_reasons": item.undergraduate_degree_reasons,
        "graduate_study_reasons": item.graduate_study_reasons,
        "degree_other_reason": item.degree_other_reason,
        "trainings": _training_rows(item),
        "advanced_study_reasons": item.advanced_study_reasons,
        "advanced_study_other_reason": item.advanced_study_other_reason,
        "current_employment_state": item.current_employment_state or None,
        "unemployment_reasons": item.unemployment_reasons,
        "unemployment_other_reason": item.unemployment_other_reason,
        "present_employment_status": item.present_employment_status or None,
        "self_employed_college_skills": item.self_employed_college_skills,
        "present_occupation": item.present_occupation,
        "employer_business_line": item.employer_business_line or None,
        "place_of_work": item.place_of_work or None,
        "first_job_after_college": item.first_job_after_college,
        "reasons_for_staying_on_job": item.reasons_for_staying_on_job,
        "reasons_for_staying_other": item.reasons_for_staying_other,
        "first_job_related_to_course": item.first_job_related_to_course,
        "reasons_for_accepting_first_job": item.reasons_for_accepting_first_job,
        "reasons_for_accepting_other": item.reasons_for_accepting_other,
        "reasons_for_changing_job": item.reasons_for_changing_job,
        "reasons_for_changing_other": item.reasons_for_changing_other,
        "first_job_duration": item.first_job_duration or None,
        "first_job_duration_other": item.first_job_duration_other,
        "first_job_source": item.first_job_source or None,
        "first_job_source_other": item.first_job_source_other,
        "time_to_first_job": item.time_to_first_job or None,
        "time_to_first_job_other": item.time_to_first_job_other,
        "first_job_level": item.first_job_level or None,
        "current_job_level": item.current_job_level or None,
        "initial_gross_monthly_earning": item.initial_gross_monthly_earning or None,
        "curriculum_relevant_to_first_job": item.curriculum_relevant_to_first_job,
        "useful_competencies": item.useful_competencies,
        "useful_competencies_other": item.useful_competencies_other,
        "curriculum_improvement_suggestions": item.curriculum_improvement_suggestions,
    }


def _summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "student_id": item.student_id,
        "student": _student_summary(item),
        "name": item.name_snapshot,
        "current_employment_state": item.current_employment_state,
        "instrument_schema_version": item.instrument_schema_version,
        "submitted_at": item.submitted_at,
    }


def _payload_values(payload: GraduateTracerDraftPayload) -> dict[str, object]:
    values = payload.model_dump(mode="python")
    values["name_snapshot"] = values.pop("name")
    values["permanent_address_snapshot"] = values.pop("permanent_address")
    values["email_snapshot"] = values.pop("email")
    values["telephone_contact_numbers_snapshot"] = values.pop("telephone_contact_numbers")
    values["mobile_number_snapshot"] = values.pop("mobile_number")
    return values


@router.post(
    "/me",
    response=response_with_errors(GraduateTracerDetailResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="graduateTracerEnsureMyResponse",
)
def graduate_tracer_ensure_my_response(request):
    _require_student(request, "graduate_tracer.manage_self")
    try:
        item = ensure_my_response(student=request.auth_user, context=_context(request))
    except GraduateTracerError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/me",
    response=response_with_errors(GraduateTracerDetailResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="graduateTracerGetMyResponse",
)
def graduate_tracer_get_my_response(request):
    _require_student(request, "graduate_tracer.view_self")
    try:
        item = get_my_response(request.auth_user)
    except GraduateTracerError as exc:
        _raise(exc)
    return _detail(item)


@router.put(
    "/me",
    response=response_with_errors(
        GraduateTracerDetailResponse,
        401,
        403,
        404,
        409,
        422,
    ),
    auth=session_auth,
    operation_id="graduateTracerReplaceMyDraft",
)
def graduate_tracer_replace_my_draft(request, payload: GraduateTracerDraftPayload):
    _require_student(request, "graduate_tracer.manage_self")
    try:
        item = replace_my_draft(
            student=request.auth_user,
            values=_payload_values(payload),
        )
    except GraduateTracerError as exc:
        _raise(exc)
    return _detail(item)


@router.post(
    "/me/submit",
    response=response_with_errors(
        GraduateTracerDetailResponse,
        401,
        403,
        404,
        409,
        422,
    ),
    auth=session_auth,
    operation_id="graduateTracerSubmitMyResponse",
)
def graduate_tracer_submit_my_response(request):
    _require_student(request, "graduate_tracer.manage_self")
    try:
        item = submit_my_response(
            student=request.auth_user,
            context=_context(request),
        )
    except GraduateTracerError as exc:
        _raise(exc)
    return _detail(item)


@router.get(
    "/responses",
    response=response_with_errors(GraduateTracerPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="graduateTracerListResponses",
)
def graduate_tracer_list_responses(
    request,
    search: str | None = None,
    student_id: UUID | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    current_employment_state: GTSEmploymentStateValue | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_viewer(request)
    try:
        result = list_submitted_for_head(
            actor=request.auth_user,
            search=search,
            student_id=student_id,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
            current_employment_state=(
                current_employment_state.value if current_employment_state is not None else None
            ),
            page=page,
            page_size=page_size,
        )
    except GraduateTracerError as exc:
        _raise(exc)
    return {
        "items": [_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/responses/{response_id}",
    response=response_with_errors(GraduateTracerDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="graduateTracerGetResponse",
)
def graduate_tracer_get_response(request, response_id: UUID):
    _require_viewer(request)
    try:
        item = get_submitted_for_head(
            actor=request.auth_user,
            response_id=response_id,
        )
    except GraduateTracerError as exc:
        _raise(exc)
    return _detail(item)
