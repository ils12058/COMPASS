"""Submission and restricted raw-review services for Feedback instruments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.profiles import get_person_profile_context
from compass.audit.actions import CSM_SUBMITTED, CUSTOMER_FEEDBACK_SUBMITTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)

from .models import (
    CSMCC1,
    CSMCC2,
    CSMCC3,
    ClientSatisfactionResponse,
    CSMClientType,
    CSMRating,
    CSMSex,
    CustomerFeedbackAccommodatedBy,
    CustomerFeedbackRating,
    CustomerFeedbackResponse,
    CustomerFeedbackService,
)

CSM_SCHEMA_VERSION = 1
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_FEEDBACK_TEXT_LENGTH = 4000
MAX_SEARCH_LENGTH = 160
MAX_CSM_SERVICE_FILTER_LENGTH = 255


class FeedbackError(RuntimeError):
    pass


class FeedbackNotFound(FeedbackError):
    pass


class FeedbackNotPermitted(FeedbackError):
    pass


class FeedbackConfigurationConflict(FeedbackError):
    pass


class InvalidFeedbackInput(FeedbackError):
    pass


@dataclass(frozen=True, slots=True)
class FeedbackPage:
    items: tuple[object, ...]
    page: int
    page_size: int
    has_next: bool


def _validate_student(actor: User, capability: str) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "STUDENT"
        or not actor.has_capability(capability)
    ):
        raise FeedbackNotPermitted("Active Student Feedback submission access is required.")


def _validate_viewer(actor: User, capability: str) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability(capability)
    ):
        raise FeedbackNotPermitted("Head Guidance Feedback review authority is required.")


def _clean_text(value: object, field_name: str, maximum: int, *, required: bool) -> str:
    if not isinstance(value, str):
        raise InvalidFeedbackInput(f"{field_name} must be text.")
    cleaned = value.strip()
    if required and not cleaned:
        raise InvalidFeedbackInput(f"{field_name} is required.")
    if len(cleaned) > maximum:
        raise InvalidFeedbackInput(f"{field_name} is too long.")
    return cleaned


def _clean_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidFeedbackInput(f"{field_name} must be between {minimum} and {maximum}.")
    return value


def _choice(value: object, allowed: set[object], field_name: str):
    candidate = value.value if hasattr(value, "value") else value
    if candidate not in allowed:
        raise InvalidFeedbackInput(f"{field_name} contains an unsupported source value.")
    return candidate


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidFeedbackInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidFeedbackInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _customer_queryset():
    return CustomerFeedbackResponse.objects.select_related("form_revision", "form_revision__family")


def _optional_text(value: object, field_name: str, maximum: int) -> str:
    if value is None:
        return ""
    return _clean_text(value, field_name, maximum, required=False)


def _submission_boundary(value: date, *, following_day: bool = False) -> datetime:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvalidFeedbackInput("submission date filters must be calendar dates.")
    local_date = value + timedelta(days=1) if following_day else value
    return timezone.make_aware(
        datetime.combine(local_date, time.min),
        timezone.get_current_timezone(),
    )


def _validate_submission_range(
    submitted_from: date | None,
    submitted_to: date | None,
) -> None:
    if submitted_from is not None:
        _submission_boundary(submitted_from)
    if submitted_to is not None:
        _submission_boundary(submitted_to)
    if submitted_from is not None and submitted_to is not None and submitted_from > submitted_to:
        raise InvalidFeedbackInput("submitted_from must be on or before submitted_to.")


def _normalize_services(raw: object) -> list[str]:
    if not isinstance(raw, (list, tuple)) or not raw:
        raise InvalidFeedbackInput("services_received must contain at least one source service.")
    normalized: list[str] = []
    for item in raw:
        value = _choice(item, set(CustomerFeedbackService.values), "services_received")
        if value in normalized:
            raise InvalidFeedbackInput("services_received must not contain duplicate values.")
        normalized.append(value)
    return normalized


def _normalize_customer_feedback(values: dict[str, object], profile) -> dict[str, object]:
    services = _normalize_services(values.get("services_received"))
    other_service = _clean_text(
        values.get("other_service", ""), "other_service", 255, required=False
    )
    if CustomerFeedbackService.OTHER in services and not other_service:
        raise InvalidFeedbackInput("other_service is required when OTHER is selected.")
    if CustomerFeedbackService.OTHER not in services and other_service:
        raise InvalidFeedbackInput("other_service must be blank unless OTHER is selected.")

    talked = values.get("talked_to_guidance_counselor")
    if type(talked) is not bool:
        raise InvalidFeedbackInput("talked_to_guidance_counselor must be true or false.")
    raw_accommodated = values.get("accommodated_by")
    accommodated = (
        ""
        if raw_accommodated in {None, ""}
        else _choice(
            raw_accommodated,
            set(CustomerFeedbackAccommodatedBy.values),
            "accommodated_by",
        )
    )
    if talked and accommodated:
        raise InvalidFeedbackInput(
            "accommodated_by must be blank when the Guidance Counselor was reached."
        )
    if not talked and not accommodated:
        raise InvalidFeedbackInput(
            "accommodated_by is required when the Guidance Counselor was not reached."
        )

    normalized: dict[str, object] = {
        "services_received": services,
        "other_service": other_service,
        "talked_to_guidance_counselor": talked,
        "accommodated_by": accommodated,
        "office_visit_count": _clean_int(
            values.get("office_visit_count"), "office_visit_count", 1, 10000
        ),
        "transaction_duration": _clean_text(
            values.get("transaction_duration", ""), "transaction_duration", 200, required=True
        ),
        "additional_feedback": _clean_text(
            values.get("additional_feedback", ""),
            "additional_feedback",
            MAX_FEEDBACK_TEXT_LENGTH,
            required=False,
        ),
        "future_service_improvement": _clean_text(
            values.get("future_service_improvement", ""),
            "future_service_improvement",
            MAX_FEEDBACK_TEXT_LENGTH,
            required=False,
        ),
        "course_year_snapshot": _clean_text(
            values.get("course_year", ""), "course_year", 160, required=True
        ),
    }
    for field_name in (
        "personnel_accommodating_rating",
        "personnel_job_knowledge_rating",
        "personnel_flexibility_rating",
        "personnel_information_accuracy_rating",
        "personnel_appearance_rating",
        "personnel_commitment_delivery_rating",
        "office_location_rating",
        "office_cleanliness_rating",
        "office_environment_rating",
        "office_hours_rating",
        "personnel_availability_rating",
        "overall_satisfaction_rating",
    ):
        normalized[field_name] = _choice(
            values.get(field_name), set(CustomerFeedbackRating.values), field_name
        )

    supplied_name = _clean_text(
        values.get("respondent_name", ""), "respondent_name", 200, required=False
    )
    normalized["respondent_name_snapshot"] = supplied_name or profile.full_name.strip()
    if not normalized["respondent_name_snapshot"]:
        raise InvalidFeedbackInput("respondent_name is required.")

    supplied_address = _clean_text(values.get("address", ""), "address", 2000, required=False)
    normalized["address_snapshot"] = (
        supplied_address or profile.current_address.strip() or profile.permanent_address.strip()
    )
    supplied_mobile = _clean_text(
        values.get("mobile_number", ""), "mobile_number", 64, required=False
    )
    normalized["mobile_number_snapshot"] = supplied_mobile or profile.contact_number.strip()
    return normalized


def create_customer_feedback(
    *,
    student: User,
    values: dict[str, object],
    context: AuditContext,
) -> CustomerFeedbackResponse:
    _validate_student(student, "feedback.submit_customer_feedback")
    with transaction.atomic():
        locked = (
            User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk=student.pk)
            .first()
        )
        if locked is None:
            raise FeedbackNotFound("The Student account was not found.")
        _validate_student(locked, "feedback.submit_customer_feedback")
        try:
            revision = require_active_supported_form_revision("customer_feedback")
        except InstitutionalFormConflict as exc:
            raise FeedbackConfigurationConflict(str(exc)) from exc
        profile = get_person_profile_context(locked)
        normalized = _normalize_customer_feedback(values, profile)
        item = CustomerFeedbackResponse.objects.create(form_revision=revision, **normalized)
        record_event(
            context=context,
            action=CUSTOMER_FEEDBACK_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="feedback.customerfeedbackresponse",
            target_id=item.pk,
            metadata={
                "family_key": revision.family.key,
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "internal_schema_version": revision.internal_schema_version,
            },
        )
        return _customer_queryset().get(pk=item.pk)


def _normalize_csm(values: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {
        "instrument_schema_version": CSM_SCHEMA_VERSION,
        "client_type": _choice(values.get("client_type"), set(CSMClientType.values), "client_type"),
        "sex": _choice(values.get("sex"), set(CSMSex.values), "sex"),
        "age": _clean_int(values.get("age"), "age", 0, 150),
        "region_of_residence": _clean_text(
            values.get("region_of_residence", ""), "region_of_residence", 160, required=True
        ),
        "service_availed": _clean_text(
            values.get("service_availed", ""), "service_availed", 255, required=True
        ),
        "cc1": _choice(values.get("cc1"), set(CSMCC1.values), "cc1"),
        "cc2": _choice(values.get("cc2"), set(CSMCC2.values), "cc2"),
        "cc3": _choice(values.get("cc3"), set(CSMCC3.values), "cc3"),
        "suggestions": _clean_text(
            values.get("suggestions", ""), "suggestions", MAX_FEEDBACK_TEXT_LENGTH, required=False
        ),
    }
    email = _clean_text(values.get("email", ""), "email", 320, required=False)
    if email:
        try:
            validate_email(email)
        except ValidationError as exc:
            raise InvalidFeedbackInput(
                "email must be a valid email address when supplied."
            ) from exc
    normalized["email"] = email

    if normalized["cc1"] == CSMCC1.DOES_NOT_KNOW:
        if normalized["cc2"] != CSMCC2.NOT_APPLICABLE or normalized["cc3"] != CSMCC3.NOT_APPLICABLE:
            raise InvalidFeedbackInput("CC1 answer 4 requires N/A for both CC2 and CC3.")
    elif normalized["cc2"] == CSMCC2.NOT_APPLICABLE or normalized["cc3"] == CSMCC3.NOT_APPLICABLE:
        raise InvalidFeedbackInput("CC1 answers 1-3 require substantive CC2 and CC3 answers.")

    for index in range(9):
        field_name = f"sqd{index}"
        normalized[field_name] = _choice(values.get(field_name), set(CSMRating.values), field_name)
    return normalized


def create_csm_response(
    *,
    student: User,
    values: dict[str, object],
    context: AuditContext,
) -> ClientSatisfactionResponse:
    _validate_student(student, "feedback.submit_csm")
    normalized = _normalize_csm(values)
    with transaction.atomic():
        locked = (
            User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk=student.pk)
            .first()
        )
        if locked is None:
            raise FeedbackNotFound("The Student account was not found.")
        _validate_student(locked, "feedback.submit_csm")
        item = ClientSatisfactionResponse.objects.create(**normalized)
        record_event(
            context=context,
            action=CSM_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="feedback.clientsatisfactionresponse",
            target_id=item.pk,
            metadata={"instrument_schema_version": CSM_SCHEMA_VERSION},
        )
        return item


def list_customer_feedback(
    *,
    actor: User,
    search: str | None = None,
    service: str | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> FeedbackPage:
    _validate_viewer(actor, "feedback.view_customer_feedback")
    page, page_size = _pagination(page, page_size)
    term = _optional_text(search, "search", MAX_SEARCH_LENGTH)
    _validate_submission_range(submitted_from, submitted_to)
    queryset = _customer_queryset()
    if term:
        queryset = queryset.filter(respondent_name_snapshot__icontains=term)
    if service is not None:
        selected_service = _choice(
            service,
            set(CustomerFeedbackService.values),
            "service",
        )
        queryset = queryset.filter(services_received__contains=[selected_service])
    if submitted_from is not None:
        queryset = queryset.filter(submitted_at__gte=_submission_boundary(submitted_from))
    if submitted_to is not None:
        queryset = queryset.filter(
            submitted_at__lt=_submission_boundary(submitted_to, following_day=True)
        )
    queryset = queryset.order_by("-submitted_at", "id")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return FeedbackPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def get_customer_feedback(*, actor: User, response_id: UUID) -> CustomerFeedbackResponse:
    _validate_viewer(actor, "feedback.view_customer_feedback")
    item = _customer_queryset().filter(pk=response_id).first()
    if item is None:
        raise FeedbackNotFound("The requested Customer Feedback response was not found.")
    return item


def list_csm_responses(
    *,
    actor: User,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    client_type: str | None = None,
    service: str | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
) -> FeedbackPage:
    _validate_viewer(actor, "feedback.view_csm")
    page, page_size = _pagination(page, page_size)
    service_term = _optional_text(
        service,
        "service",
        MAX_CSM_SERVICE_FILTER_LENGTH,
    )
    _validate_submission_range(submitted_from, submitted_to)
    queryset = ClientSatisfactionResponse.objects.all()
    if client_type is not None:
        client_type = _choice(client_type, set(CSMClientType.values), "client_type")
        queryset = queryset.filter(client_type=client_type)
    if service_term:
        queryset = queryset.filter(service_availed__icontains=service_term)
    if submitted_from is not None:
        queryset = queryset.filter(submitted_at__gte=_submission_boundary(submitted_from))
    if submitted_to is not None:
        queryset = queryset.filter(
            submitted_at__lt=_submission_boundary(submitted_to, following_day=True)
        )
    queryset = queryset.order_by("-submitted_at", "id")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return FeedbackPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def get_csm_response(*, actor: User, response_id: UUID) -> ClientSatisfactionResponse:
    _validate_viewer(actor, "feedback.view_csm")
    item = ClientSatisfactionResponse.objects.filter(pk=response_id).first()
    if item is None:
        raise FeedbackNotFound("The requested CSM response was not found.")
    return item
