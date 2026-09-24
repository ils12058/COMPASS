"""Django Ninja API for Customer Feedback and Client Satisfaction Measurement."""

from __future__ import annotations

from datetime import date, datetime
from enum import IntEnum, StrEnum
from typing import NoReturn
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from ninja import Header, Router, Schema
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.common.idempotency import (
    IdempotencyConflict,
    IdempotencyOwnershipError,
    IdempotencyUnavailable,
    RedisIdempotencyStore,
    StoredResponse,
    request_fingerprint,
)

from .models import (
    CSMCC1,
    CSMCC2,
    CSMCC3,
    CSMClientType,
    CSMRating,
    CSMSex,
    CustomerFeedbackAccommodatedBy,
    CustomerFeedbackRating,
    CustomerFeedbackService,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    FeedbackConfigurationConflict,
    FeedbackError,
    FeedbackNotFound,
    FeedbackNotPermitted,
    InvalidFeedbackInput,
    create_csm_response,
    create_customer_feedback,
    get_csm_response,
    get_customer_feedback,
    list_csm_responses,
    list_customer_feedback,
)

router = Router(tags=["feedback"])

CUSTOMER_FEEDBACK_SUBMISSION_ROUTE = "/api/v1/feedback/customer-feedback"
CSM_SUBMISSION_ROUTE = "/api/v1/feedback/csm"


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CustomerFeedbackServiceValue(StrEnum):
    COUNSELING = CustomerFeedbackService.COUNSELING
    ADMISSION = CustomerFeedbackService.ADMISSION
    TESTING = CustomerFeedbackService.TESTING
    EDUCATIONAL_INFORMATION = CustomerFeedbackService.EDUCATIONAL_INFORMATION
    REQUEST_FOR_CERTIFICATION = CustomerFeedbackService.REQUEST_FOR_CERTIFICATION
    APPLICATION_FOR_ADMISSION_TEST = CustomerFeedbackService.APPLICATION_FOR_ADMISSION_TEST
    OTHER = CustomerFeedbackService.OTHER


class CustomerFeedbackAccommodatedByValue(StrEnum):
    STUDENT_ASSISTANT = CustomerFeedbackAccommodatedBy.STUDENT_ASSISTANT
    CLERK_PERSONNEL = CustomerFeedbackAccommodatedBy.CLERK_PERSONNEL


class CustomerFeedbackRatingValue(IntEnum):
    POOR = CustomerFeedbackRating.POOR
    FAIR = CustomerFeedbackRating.FAIR
    GOOD = CustomerFeedbackRating.GOOD
    VERY_GOOD = CustomerFeedbackRating.VERY_GOOD
    EXCELLENT = CustomerFeedbackRating.EXCELLENT


class CSMClientTypeValue(StrEnum):
    CITIZEN = CSMClientType.CITIZEN
    BUSINESS = CSMClientType.BUSINESS
    GOVERNMENT = CSMClientType.GOVERNMENT


class CSMSexValue(StrEnum):
    MALE = CSMSex.MALE
    FEMALE = CSMSex.FEMALE


class CSMCC1Value(IntEnum):
    KNOWS_AND_SAW = CSMCC1.KNOWS_AND_SAW
    KNOWS_NOT_SEEN = CSMCC1.KNOWS_NOT_SEEN
    LEARNED_WHEN_SEEN = CSMCC1.LEARNED_WHEN_SEEN
    DOES_NOT_KNOW = CSMCC1.DOES_NOT_KNOW


class CSMCC2Value(IntEnum):
    EASY_TO_SEE = CSMCC2.EASY_TO_SEE
    SOMEWHAT_EASY_TO_SEE = CSMCC2.SOMEWHAT_EASY_TO_SEE
    DIFFICULT_TO_SEE = CSMCC2.DIFFICULT_TO_SEE
    NOT_VISIBLE = CSMCC2.NOT_VISIBLE
    NOT_APPLICABLE = CSMCC2.NOT_APPLICABLE


class CSMCC3Value(IntEnum):
    HELPED_VERY_MUCH = CSMCC3.HELPED_VERY_MUCH
    SOMEWHAT_HELPED = CSMCC3.SOMEWHAT_HELPED
    DID_NOT_HELP = CSMCC3.DID_NOT_HELP
    NOT_APPLICABLE = CSMCC3.NOT_APPLICABLE


class CSMRatingValue(IntEnum):
    NOT_APPLICABLE = CSMRating.NOT_APPLICABLE
    STRONGLY_DISAGREE = CSMRating.STRONGLY_DISAGREE
    DISAGREE = CSMRating.DISAGREE
    NEITHER_AGREE_NOR_DISAGREE = CSMRating.NEITHER_AGREE_NOR_DISAGREE
    AGREE = CSMRating.AGREE
    STRONGLY_AGREE = CSMRating.STRONGLY_AGREE


class CustomerFeedbackSubmitRequest(StrictSchema):
    services_received: list[CustomerFeedbackServiceValue]
    other_service: str = ""
    talked_to_guidance_counselor: bool
    accommodated_by: CustomerFeedbackAccommodatedByValue | None = None
    office_visit_count: int = Field(ge=1, le=10000)
    personnel_accommodating_rating: CustomerFeedbackRatingValue
    personnel_job_knowledge_rating: CustomerFeedbackRatingValue
    personnel_flexibility_rating: CustomerFeedbackRatingValue
    personnel_information_accuracy_rating: CustomerFeedbackRatingValue
    personnel_appearance_rating: CustomerFeedbackRatingValue
    personnel_commitment_delivery_rating: CustomerFeedbackRatingValue
    transaction_duration: str
    office_location_rating: CustomerFeedbackRatingValue
    office_cleanliness_rating: CustomerFeedbackRatingValue
    office_environment_rating: CustomerFeedbackRatingValue
    office_hours_rating: CustomerFeedbackRatingValue
    personnel_availability_rating: CustomerFeedbackRatingValue
    overall_satisfaction_rating: CustomerFeedbackRatingValue
    additional_feedback: str = ""
    future_service_improvement: str = ""
    respondent_name: str = ""
    course_year: str
    address: str = ""
    mobile_number: str = ""


class FeedbackSubmissionResponse(StrictSchema):
    id: UUID
    submitted_at: datetime
    submitted: bool


class FormRevisionSummary(StrictSchema):
    id: UUID
    family_key: str
    official_code: str
    official_revision: str
    internal_schema_version: int


class CustomerFeedbackSummaryResponse(StrictSchema):
    id: UUID
    submitted_at: datetime
    respondent_name: str
    services_received: list[CustomerFeedbackServiceValue]


class CustomerFeedbackDetailResponse(CustomerFeedbackSummaryResponse):
    form_revision: FormRevisionSummary
    other_service: str
    talked_to_guidance_counselor: bool
    accommodated_by: CustomerFeedbackAccommodatedByValue | None
    office_visit_count: int
    personnel_accommodating_rating: CustomerFeedbackRatingValue
    personnel_job_knowledge_rating: CustomerFeedbackRatingValue
    personnel_flexibility_rating: CustomerFeedbackRatingValue
    personnel_information_accuracy_rating: CustomerFeedbackRatingValue
    personnel_appearance_rating: CustomerFeedbackRatingValue
    personnel_commitment_delivery_rating: CustomerFeedbackRatingValue
    transaction_duration: str
    office_location_rating: CustomerFeedbackRatingValue
    office_cleanliness_rating: CustomerFeedbackRatingValue
    office_environment_rating: CustomerFeedbackRatingValue
    office_hours_rating: CustomerFeedbackRatingValue
    personnel_availability_rating: CustomerFeedbackRatingValue
    overall_satisfaction_rating: CustomerFeedbackRatingValue
    additional_feedback: str
    future_service_improvement: str
    course_year: str
    address: str
    mobile_number: str


class CustomerFeedbackPageResponse(StrictSchema):
    items: list[CustomerFeedbackSummaryResponse]
    page: int
    page_size: int
    has_next: bool


class CSMSubmitRequest(StrictSchema):
    client_type: CSMClientTypeValue
    sex: CSMSexValue
    age: int = Field(ge=0, le=150)
    region_of_residence: str
    service_availed: str
    cc1: CSMCC1Value
    cc2: CSMCC2Value
    cc3: CSMCC3Value
    sqd0: CSMRatingValue
    sqd1: CSMRatingValue
    sqd2: CSMRatingValue
    sqd3: CSMRatingValue
    sqd4: CSMRatingValue
    sqd5: CSMRatingValue
    sqd6: CSMRatingValue
    sqd7: CSMRatingValue
    sqd8: CSMRatingValue
    suggestions: str = ""
    email: str = ""


class CSMSummaryResponse(StrictSchema):
    id: UUID
    submitted_at: datetime
    instrument_schema_version: int
    client_type: CSMClientTypeValue
    service_availed: str


class CSMDetailResponse(CSMSummaryResponse):
    sex: CSMSexValue
    age: int
    region_of_residence: str
    cc1: CSMCC1Value
    cc2: CSMCC2Value
    cc3: CSMCC3Value
    sqd0: CSMRatingValue
    sqd1: CSMRatingValue
    sqd2: CSMRatingValue
    sqd3: CSMRatingValue
    sqd4: CSMRatingValue
    sqd5: CSMRatingValue
    sqd6: CSMRatingValue
    sqd7: CSMRatingValue
    sqd8: CSMRatingValue
    suggestions: str
    email: str


class CSMPageResponse(StrictSchema):
    items: list[CSMSummaryResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    actor = request.auth_user
    if not actor.is_active or actor.role.code != "STUDENT" or not actor.has_capability(capability):
        raise APIError(403, "permission_denied", "Student Feedback submission access is required.")


def _require_viewer(request, capability: str) -> None:
    actor = request.auth_user
    if not actor.is_active or not actor.has_capability(capability):
        raise APIError(
            403, "permission_denied", "Head Guidance Feedback review authority is required."
        )


def _raise(exc: FeedbackError) -> NoReturn:
    if isinstance(exc, FeedbackNotFound):
        raise APIError(404, "feedback_not_found", str(exc)) from exc
    if isinstance(exc, FeedbackNotPermitted):
        raise APIError(403, "permission_denied", str(exc)) from exc
    if isinstance(exc, FeedbackConfigurationConflict):
        raise APIError(409, "feedback_configuration_conflict", str(exc)) from exc
    if isinstance(exc, InvalidFeedbackInput):
        raise APIError(422, "invalid_feedback_request", str(exc)) from exc
    raise APIError(500, "internal_error", "The Feedback operation could not be completed.") from exc


def _submission(item) -> dict[str, object]:
    return {"id": item.pk, "submitted_at": item.submitted_at, "submitted": True}


def _json_response(payload: dict[str, object], *, status: int) -> JsonResponse:
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _begin_submission_idempotency(
    request,
    *,
    route: str,
    idempotency_key: str,
):
    store = RedisIdempotencyStore.from_settings()
    fingerprint = request_fingerprint(
        method="POST",
        route=route,
        query_string=request.META.get("QUERY_STRING", ""),
        body=request.body,
    )
    try:
        decision = store.begin(
            actor_id=str(request.auth_user.pk),
            method="POST",
            route=route,
            key=idempotency_key,
            fingerprint=fingerprint,
        )
    except ValueError as exc:
        raise APIError(422, "invalid_idempotency_key", str(exc)) from exc
    except IdempotencyConflict as exc:
        raise APIError(
            409,
            "idempotency_key_conflict",
            "The Idempotency-Key was already used for a different Feedback submission.",
        ) from exc
    except IdempotencyUnavailable as exc:
        raise APIError(
            503,
            "idempotency_unavailable",
            "The Feedback submission replay boundary is temporarily unavailable.",
        ) from exc

    if decision.outcome == "replay":
        assert decision.response is not None
        return store, decision, HttpResponse(
            decision.response.body,
            status=decision.response.status_code,
            content_type=decision.response.content_type,
        )
    if decision.outcome == "in_progress":
        raise APIError(
            409,
            "idempotency_in_progress",
            "A Feedback submission with this Idempotency-Key is already in progress.",
        )
    assert decision.reservation is not None
    return store, decision, None


def _complete_submission_or_503(store, reservation, response: HttpResponse) -> None:
    try:
        store.complete(
            reservation,
            StoredResponse(
                status_code=response.status_code,
                body=bytes(response.content),
                content_type=response.get("Content-Type", "application/json"),
            ),
        )
    except (IdempotencyUnavailable, IdempotencyOwnershipError, ValueError) as exc:
        raise APIError(
            503,
            "idempotency_unavailable",
            "The Feedback submission replay boundary could not be completed safely.",
        ) from exc


def _abandon_submission_or_503(store, reservation) -> None:
    try:
        store.abandon(reservation)
    except (IdempotencyUnavailable, IdempotencyOwnershipError) as exc:
        raise APIError(
            503,
            "idempotency_unavailable",
            "The Feedback submission replay boundary could not be released safely.",
        ) from exc


def _customer_summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "submitted_at": item.submitted_at,
        "respondent_name": item.respondent_name_snapshot,
        "services_received": item.services_received,
    }


def _customer_detail(item) -> dict[str, object]:
    revision = item.form_revision
    return {
        **_customer_summary(item),
        "form_revision": {
            "id": revision.pk,
            "family_key": revision.family.key,
            "official_code": revision.official_code,
            "official_revision": revision.official_revision,
            "internal_schema_version": revision.internal_schema_version,
        },
        "other_service": item.other_service,
        "talked_to_guidance_counselor": item.talked_to_guidance_counselor,
        "accommodated_by": item.accommodated_by or None,
        "office_visit_count": item.office_visit_count,
        "personnel_accommodating_rating": item.personnel_accommodating_rating,
        "personnel_job_knowledge_rating": item.personnel_job_knowledge_rating,
        "personnel_flexibility_rating": item.personnel_flexibility_rating,
        "personnel_information_accuracy_rating": item.personnel_information_accuracy_rating,
        "personnel_appearance_rating": item.personnel_appearance_rating,
        "personnel_commitment_delivery_rating": item.personnel_commitment_delivery_rating,
        "transaction_duration": item.transaction_duration,
        "office_location_rating": item.office_location_rating,
        "office_cleanliness_rating": item.office_cleanliness_rating,
        "office_environment_rating": item.office_environment_rating,
        "office_hours_rating": item.office_hours_rating,
        "personnel_availability_rating": item.personnel_availability_rating,
        "overall_satisfaction_rating": item.overall_satisfaction_rating,
        "additional_feedback": item.additional_feedback,
        "future_service_improvement": item.future_service_improvement,
        "course_year": item.course_year_snapshot,
        "address": item.address_snapshot,
        "mobile_number": item.mobile_number_snapshot,
    }


def _csm_summary(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "submitted_at": item.submitted_at,
        "instrument_schema_version": item.instrument_schema_version,
        "client_type": item.client_type,
        "service_availed": item.service_availed,
    }


def _csm_detail(item) -> dict[str, object]:
    return {
        **_csm_summary(item),
        "sex": item.sex,
        "age": item.age,
        "region_of_residence": item.region_of_residence,
        "cc1": item.cc1,
        "cc2": item.cc2,
        "cc3": item.cc3,
        "sqd0": item.sqd0,
        "sqd1": item.sqd1,
        "sqd2": item.sqd2,
        "sqd3": item.sqd3,
        "sqd4": item.sqd4,
        "sqd5": item.sqd5,
        "sqd6": item.sqd6,
        "sqd7": item.sqd7,
        "sqd8": item.sqd8,
        "suggestions": item.suggestions,
        "email": item.email,
    }


@router.post(
    "/customer-feedback",
    response=response_with_errors(
        FeedbackSubmissionResponse,
        401,
        403,
        409,
        422,
        503,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="feedbackSubmitCustomerFeedback",
)
def feedback_submit_customer_feedback(
    request,
    payload: CustomerFeedbackSubmitRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_student(request, "feedback.submit_customer_feedback")
    store, decision, replay = _begin_submission_idempotency(
        request,
        route=CUSTOMER_FEEDBACK_SUBMISSION_ROUTE,
        idempotency_key=idempotency_key,
    )
    if replay is not None:
        return replay
    assert decision.reservation is not None

    try:
        item = create_customer_feedback(
            student=request.auth_user,
            values=payload.model_dump(mode="python"),
            context=_context(request),
        )
    except FeedbackError as exc:
        _abandon_submission_or_503(store, decision.reservation)
        _raise(exc)

    response = _json_response(_submission(item), status=201)
    _complete_submission_or_503(store, decision.reservation, response)
    return response


@router.get(
    "/customer-feedback/responses",
    response=response_with_errors(CustomerFeedbackPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="feedbackListCustomerFeedbackResponses",
)
def feedback_list_customer_feedback_responses(
    request,
    search: str | None = None,
    service: CustomerFeedbackServiceValue | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_viewer(request, "feedback.view_customer_feedback")
    try:
        result = list_customer_feedback(
            actor=request.auth_user,
            search=search,
            service=service.value if service is not None else None,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
            page=page,
            page_size=page_size,
        )
    except FeedbackError as exc:
        _raise(exc)
    return {
        "items": [_customer_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/customer-feedback/responses/{response_id}",
    response=response_with_errors(CustomerFeedbackDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="feedbackGetCustomerFeedbackResponse",
)
def feedback_get_customer_feedback_response(request, response_id: UUID):
    _require_viewer(request, "feedback.view_customer_feedback")
    try:
        item = get_customer_feedback(actor=request.auth_user, response_id=response_id)
    except FeedbackError as exc:
        _raise(exc)
    return _customer_detail(item)


@router.post(
    "/csm",
    response=response_with_errors(
        FeedbackSubmissionResponse,
        401,
        403,
        409,
        422,
        503,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="feedbackSubmitCsm",
)
def feedback_submit_csm(
    request,
    payload: CSMSubmitRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    _require_student(request, "feedback.submit_csm")
    store, decision, replay = _begin_submission_idempotency(
        request,
        route=CSM_SUBMISSION_ROUTE,
        idempotency_key=idempotency_key,
    )
    if replay is not None:
        return replay
    assert decision.reservation is not None

    try:
        item = create_csm_response(
            student=request.auth_user,
            values=payload.model_dump(mode="python"),
            context=_context(request),
        )
    except FeedbackError as exc:
        _abandon_submission_or_503(store, decision.reservation)
        _raise(exc)

    response = _json_response(_submission(item), status=201)
    _complete_submission_or_503(store, decision.reservation, response)
    return response


@router.get(
    "/csm/responses",
    response=response_with_errors(CSMPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="feedbackListCsmResponses",
)
def feedback_list_csm_responses(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    client_type: CSMClientTypeValue | None = None,
    service: str | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
):
    _require_viewer(request, "feedback.view_csm")
    try:
        result = list_csm_responses(
            actor=request.auth_user,
            page=page,
            page_size=page_size,
            client_type=client_type.value if client_type is not None else None,
            service=service,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
        )
    except FeedbackError as exc:
        _raise(exc)
    return {
        "items": [_csm_summary(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/csm/responses/{response_id}",
    response=response_with_errors(CSMDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="feedbackGetCsmResponse",
)
def feedback_get_csm_response(request, response_id: UUID):
    _require_viewer(request, "feedback.view_csm")
    try:
        item = get_csm_response(actor=request.auth_user, response_id=response_id)
    except FeedbackError as exc:
        _raise(exc)
    return _csm_detail(item)
