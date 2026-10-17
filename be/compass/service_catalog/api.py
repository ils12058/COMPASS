"""Thin Django Ninja API for Service Catalog configuration."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.appointments.access import appointment_management_access_allowed
from compass.appointments.services import (
    AppointmentCurrentStudentRequired,
    AppointmentTimeConflict,
    AppointmentTimeUnavailable,
)
from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.step_up import require_recent_mfa_for_request
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.service_catalog.access import current_slot_staff
from compass.service_catalog.canonical import is_system_required_service_code
from compass.service_catalog.fixed_slots_services import (
    CounselorNotQualifiedForService,
    DeliveryModeNotSupported,
    FixedSlotError,
    ServiceNotEligibleForFixedSlots,
    SlotAlreadyBookedError,
    SlotCannotBeModifiedError,
    SlotConflictError,
    SlotNotFoundError,
    SlotTimeInvalid,
    SlotUnavailableError,
    book_fixed_slot,
    create_fixed_slot,
    has_slot_booking_history,
    is_slot_booked,
    list_staff_fixed_slots,
    list_student_bookable_slots,
    update_fixed_slot,
    withdraw_fixed_slot,
)
from compass.service_catalog.services import (
    DEFAULT_PAGE_SIZE,
    CanonicalServiceRequired,
    CanonicalServiceReserved,
    InvalidServiceCatalogInput,
    ServiceCatalogConflict,
    ServiceCatalogError,
    ServiceCatalogNotFound,
    ServiceOrdering,
    ServiceSchedulingConsequenceReviewRequired,
    activation_blockers,
    create_service,
    get_service,
    get_service_providers,
    list_operational_provider_candidates,
    list_provider_candidates,
    list_services,
    service_booking_pathways,
    set_service_active,
    update_service,
)

router = Router(tags=["services"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class DeliveryMode(StrEnum):
    IN_PERSON = "IN_PERSON"
    ONLINE = "ONLINE"


class BookingPathway(StrEnum):
    FLEXIBLE_APPOINTMENT = "FLEXIBLE_APPOINTMENT"
    FIXED_DATE_SLOT = "FIXED_DATE_SLOT"
    GROUP_SESSION = "GROUP_SESSION"


class ServiceProviderCoverage(StrEnum):
    """Which active Counselors may provide new work. Counselor is the one provider class."""

    ALL_COUNSELORS = "ALL_COUNSELORS"
    SELECTED_COUNSELORS = "SELECTED_COUNSELORS"


class ServiceActivationBlocker(StrEnum):
    DELIVERY_MODE_MISSING = "DELIVERY_MODE_MISSING"
    APPOINTMENT_DURATION_MISSING = "APPOINTMENT_DURATION_MISSING"
    SELECTED_COUNSELORS_MISSING = "SELECTED_COUNSELORS_MISSING"


class ServiceCreateRequest(StrictSchema):
    code: str
    name: str
    description: str = ""
    # Whether Students may create new Appointments for this Service. It does not make an
    # Appointment mandatory for workflows with their own direct initiation.
    appointment_booking_enabled: bool = False
    # Optional for legacy API callers; independent pathways can coexist.
    booking_pathways: list[BookingPathway] | None = None
    # Appointment-only settings; they must stay empty while booking is unavailable.
    default_appointment_duration_minutes: int | None = None
    cancellation_cutoff_minutes: int | None = None
    requires_current_inventory: bool = False
    delivery_modes: list[DeliveryMode] = Field(default_factory=list)
    provider_coverage: ServiceProviderCoverage = ServiceProviderCoverage.ALL_COUNSELORS
    selected_counselor_ids: list[UUID] = Field(default_factory=list)


class ServiceUpdateRequest(StrictSchema):
    name: str = ""
    description: str = ""
    appointment_booking_enabled: bool = False
    booking_pathways: list[BookingPathway] | None = None
    default_appointment_duration_minutes: int | None = None
    cancellation_cutoff_minutes: int | None = None
    requires_current_inventory: bool = False
    delivery_modes: list[DeliveryMode] = Field(default_factory=list)
    provider_coverage: ServiceProviderCoverage = ServiceProviderCoverage.ALL_COUNSELORS
    # Replaces the selection; send it with provider_coverage SELECTED_COUNSELORS.
    selected_counselor_ids: list[UUID] = Field(default_factory=list)
    acknowledge_scheduling_consequences: bool = False


class ServiceDisableRequest(StrictSchema):
    acknowledge_scheduling_consequences: bool = False


class ServiceResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str
    appointment_booking_enabled: bool
    booking_pathways: list[BookingPathway]
    default_appointment_duration_minutes: int | None
    cancellation_cutoff_minutes: int | None
    requires_current_inventory: bool
    delivery_modes: list[DeliveryMode]
    provider_coverage: ServiceProviderCoverage
    is_active: bool
    is_system_required: bool
    # Why an inactive Service cannot be enabled yet; empty when it could be, and for active ones.
    activation_blockers: list[ServiceActivationBlocker]
    created_at: datetime
    updated_at: datetime


class ServiceListResponse(StrictSchema):
    items: list[ServiceResponse]
    page: int
    page_size: int
    has_next: bool
    # The ordering applied: the requested one, or code A–Z.
    ordering: ServiceOrdering


class ServiceProviderCounselor(StrictSchema):
    id: UUID
    display_name: str
    # A selected Counselor whose account is inactive stays listed but is not eligible.
    is_active: bool


class ServiceProvidersResponse(StrictSchema):
    provider_coverage: ServiceProviderCoverage
    counselors: list[ServiceProviderCounselor]


class ServiceProviderCandidate(StrictSchema):
    id: UUID
    display_name: str


class ServiceProviderCandidatePage(StrictSchema):
    items: list[ServiceProviderCandidate]
    page: int
    page_size: int
    has_next: bool


class ServiceSlotCreateRequest(StrictSchema):
    provider_id: UUID
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime | None = None
    is_published: bool = True


class ServiceSlotUpdateRequest(StrictSchema):
    provider_id: UUID | None = None
    delivery_mode: DeliveryMode | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_published: bool | None = None


class ServiceSlotResponse(StrictSchema):
    id: UUID
    service_id: UUID
    provider_id: UUID
    provider_name: str
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime
    is_published: bool
    withdrawn_at: datetime | None = None
    has_booking_history: bool
    is_booked: bool
    appointment_id: UUID | None = None
    appointment_reference_code: str | None = None
    student_name: str | None = None


class StudentBookableSlotResponse(StrictSchema):
    id: UUID
    service_id: UUID
    provider_id: UUID
    provider_name: str
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime


class BookSlotResponse(StrictSchema):
    appointment_id: UUID
    reference_code: str
    service_id: UUID
    provider_id: UUID
    delivery_mode: DeliveryMode
    starts_at: datetime
    ends_at: datetime


def _raise_slot_error(exc: Exception) -> NoReturn:
    if isinstance(exc, SlotNotFoundError):
        raise APIError(404, "slot_not_found", str(exc)) from exc
    if isinstance(exc, SlotConflictError):
        raise APIError(409, "slot_conflict", str(exc)) from exc
    if isinstance(exc, SlotAlreadyBookedError):
        raise APIError(409, "slot_already_booked", str(exc)) from exc
    if isinstance(exc, SlotCannotBeModifiedError):
        raise APIError(409, "slot_cannot_be_modified", str(exc)) from exc
    if isinstance(exc, (SlotUnavailableError, ServiceNotEligibleForFixedSlots)):
        raise APIError(409, "slot_unavailable", str(exc)) from exc
    if isinstance(exc, CounselorNotQualifiedForService):
        raise APIError(409, "counselor_not_qualified", str(exc)) from exc
    if isinstance(exc, DeliveryModeNotSupported):
        raise APIError(422, "delivery_mode_not_supported", str(exc)) from exc
    if isinstance(exc, SlotTimeInvalid):
        raise APIError(422, "slot_time_invalid", str(exc)) from exc
    if isinstance(exc, AppointmentCurrentStudentRequired):
        raise APIError(403, "current_student_required", str(exc)) from exc
    if isinstance(exc, (AppointmentTimeConflict, AppointmentTimeUnavailable)):
        raise APIError(409, "appointment_conflict", str(exc)) from exc
    if isinstance(exc, FixedSlotError):
        raise APIError(400, "invalid_slot_request", str(exc)) from exc
    raise APIError(500, "internal_error", "The fixed slot operation failed.") from exc


def _slot_response(slot, *, actor=None) -> dict[str, object]:
    booked = is_slot_booked(slot)
    appt = slot.current_appointment if slot.current_appointment_id else None
    can_view_booking = bool(
        appt and actor is not None and appointment_management_access_allowed(actor, appt)
    )
    return {
        "id": slot.pk,
        "service_id": slot.service_id,
        "provider_id": slot.provider_id,
        "provider_name": slot.provider.get_full_name(),
        "delivery_mode": slot.delivery_mode,
        "starts_at": slot.starts_at,
        "ends_at": slot.ends_at,
        "is_published": slot.is_published,
        "withdrawn_at": slot.withdrawn_at,
        "has_booking_history": has_slot_booking_history(slot),
        "is_booked": booked,
        "appointment_id": appt.pk if can_view_booking else None,
        "appointment_reference_code": appt.reference_code if can_view_booking else None,
        "student_name": (
            appt.student.get_full_name() if can_view_booking and appt and appt.student else None
        ),
    }


def _student_slot_response(slot) -> dict[str, object]:
    return {
        "id": slot.pk,
        "service_id": slot.service_id,
        "provider_id": slot.provider_id,
        "provider_name": slot.provider.get_full_name(),
        "delivery_mode": slot.delivery_mode,
        "starts_at": slot.starts_at,
        "ends_at": slot.ends_at,
    }


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    if not request.auth_user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        require_recent_mfa_for_request(request)


def _raise(exc: ServiceCatalogError) -> NoReturn:
    if isinstance(exc, ServiceCatalogNotFound):
        raise APIError(404, "service_not_found", str(exc)) from exc
    if isinstance(exc, CanonicalServiceRequired):
        raise APIError(409, "canonical_service_required", str(exc)) from exc
    if isinstance(exc, CanonicalServiceReserved):
        raise APIError(409, "canonical_service_reserved", str(exc)) from exc
    if isinstance(exc, ServiceSchedulingConsequenceReviewRequired):
        raise APIError(
            409,
            "service_scheduling_consequence_review_required",
            str(exc),
            details={
                "existing_appointment_dependency_detected": (
                    exc.existing_appointment_dependency_detected
                ),
                "existing_fixed_slot_dependency_detected": (
                    exc.existing_fixed_slot_dependency_detected
                ),
                "existing_group_session_dependency_detected": (
                    exc.existing_group_session_dependency_detected
                ),
                "provider_dependency_detected": exc.provider_dependency_detected,
                "counseling_online_enabled": exc.counseling_online_enabled,
            },
        ) from exc
    if isinstance(exc, ServiceCatalogConflict):
        raise APIError(409, "service_catalog_conflict", str(exc)) from exc
    if isinstance(exc, InvalidServiceCatalogInput):
        raise APIError(422, "invalid_service_catalog_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Service Catalog operation could not be completed."
    ) from exc


def _service(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "appointment_booking_enabled": item.appointment_booking_enabled,
        "booking_pathways": service_booking_pathways(item),
        "default_appointment_duration_minutes": item.default_appointment_duration_minutes,
        "cancellation_cutoff_minutes": item.cancellation_cutoff_minutes,
        "requires_current_inventory": item.requires_current_inventory,
        "delivery_modes": sorted(
            assignment.mode for assignment in item.delivery_mode_assignments.all()
        ),
        "provider_coverage": item.provider_coverage,
        "is_active": item.is_active,
        "is_system_required": is_system_required_service_code(item.code),
        "activation_blockers": [] if item.is_active else list(activation_blockers(item)),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _request_values(payload, fields: dict[str, object]) -> dict[str, object]:
    values = dict(fields)
    if "booking_pathways" in values and values["booking_pathways"] is not None:
        values["booking_pathways"] = [value.value for value in payload.booking_pathways]
        if "appointment_booking_enabled" not in payload.model_fields_set:
            values["appointment_booking_enabled"] = (
                BookingPathway.FLEXIBLE_APPOINTMENT.value in values["booking_pathways"]
            )
    if "delivery_modes" in values:
        values["delivery_modes"] = [value.value for value in payload.delivery_modes]
    if "provider_coverage" in values:
        values["provider_coverage"] = payload.provider_coverage.value
    if "selected_counselor_ids" in values:
        values["selected_counselor_ids"] = list(payload.selected_counselor_ids)
    return values


@router.get(
    "",
    response=response_with_errors(ServiceListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="servicesList",
)
def services_list(
    request,
    include_inactive: bool = False,
    search: str | None = None,
    appointment_booking_enabled: bool | None = None,
    ordering: ServiceOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require(request, "services.catalog.view")
    if include_inactive:
        _require(request, "services.manage")
    try:
        result = list_services(
            include_inactive=include_inactive,
            search=search,
            appointment_booking_enabled=appointment_booking_enabled,
            ordering=ordering,
            page=page,
            page_size=page_size,
        )
    except ServiceCatalogError as exc:
        _raise(exc)
    return {
        "items": [_service(item) for item in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
        "ordering": result.ordering,
    }


@router.post(
    "",
    response=response_with_errors(ServiceResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="servicesCreate",
)
def services_create(request, payload: ServiceCreateRequest):
    _require(request, "services.manage", recent_mfa=True)
    try:
        item = create_service(
            **_request_values(payload, payload.model_dump()), context=_context(request)
        )
    except ServiceCatalogError as exc:
        _raise(exc)
    return Status(201, _service(item))


@router.get(
    "/provider-candidates",
    response=response_with_errors(ServiceProviderCandidatePage, 401, 403, 422),
    auth=session_auth,
    operation_id="servicesListProviderCandidates",
)
def services_list_provider_candidates(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    """Active Counselors that may be selected as Service providers (no College filtering)."""

    _require(request, "services.manage")
    try:
        result = list_provider_candidates(search=search, page=page, page_size=page_size)
    except ServiceCatalogError as exc:
        _raise(exc)
    return {
        "items": [{"id": user.pk, "display_name": user.get_full_name()} for user in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.get(
    "/{service_id}",
    response=response_with_errors(ServiceResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="servicesGet",
)
def services_get(request, service_id: UUID):
    _require(request, "services.catalog.view")
    try:
        item = get_service(service_id)
    except ServiceCatalogError as exc:
        _raise(exc)
    if not item.is_active and not request.auth_user.has_capability("services.manage"):
        raise APIError(404, "service_not_found", "The requested Service was not found.")
    return _service(item)


@router.get(
    "/{service_id}/providers",
    response=response_with_errors(ServiceProvidersResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="servicesGetProviders",
)
def services_get_providers(request, service_id: UUID):
    _require(request, "services.manage")
    try:
        result = get_service_providers(service_id)
    except ServiceCatalogError as exc:
        _raise(exc)
    return {
        "provider_coverage": result.provider_coverage,
        "counselors": [
            {"id": user.pk, "display_name": user.get_full_name(), "is_active": user.is_active}
            for user in result.counselors
        ],
    }


@router.get(
    "/{service_id}/operational-provider-candidates",
    response=response_with_errors(ServiceProviderCandidatePage, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="servicesListOperationalProviderCandidates",
)
def services_list_operational_provider_candidates(
    request,
    service_id: UUID,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    """Read only qualified providers within the caller's Appointment responsibility scope."""

    _require(request, "appointments.manage")
    try:
        result = list_operational_provider_candidates(
            actor=request.auth_user,
            service_id=service_id,
            search=search,
            page=page,
            page_size=page_size,
        )
    except PermissionError as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc
    except ServiceCatalogError as exc:
        _raise(exc)
    return {
        "items": [{"id": user.pk, "display_name": user.get_full_name()} for user in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.patch(
    "/{service_id}",
    response=response_with_errors(ServiceResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesUpdate",
)
def services_update(request, service_id: UUID, payload: ServiceUpdateRequest):
    _require(request, "services.manage", recent_mfa=True)
    changes = payload.model_dump(exclude_unset=True)
    acknowledge_scheduling_consequences = bool(
        changes.pop("acknowledge_scheduling_consequences", False)
    )
    try:
        return _service(
            update_service(
                service_id=service_id,
                changes=_request_values(payload, changes),
                context=_context(request),
                acknowledge_scheduling_consequences=acknowledge_scheduling_consequences,
            )
        )
    except ServiceCatalogError as exc:
        _raise(exc)


@router.post(
    "/{service_id}/enable",
    response=response_with_errors(ServiceResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesEnable",
)
def services_enable(request, service_id: UUID):
    _require(request, "services.manage", recent_mfa=True)
    try:
        return _service(
            set_service_active(service_id=service_id, is_active=True, context=_context(request))
        )
    except ServiceCatalogError as exc:
        _raise(exc)


@router.post(
    "/{service_id}/disable",
    response=response_with_errors(ServiceResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesDisable",
)
def services_disable(request, service_id: UUID, payload: ServiceDisableRequest):
    _require(request, "services.manage", recent_mfa=True)
    try:
        return _service(
            set_service_active(
                service_id=service_id,
                is_active=False,
                context=_context(request),
                acknowledge_scheduling_consequences=payload.acknowledge_scheduling_consequences,
            )
        )
    except ServiceCatalogError as exc:
        _raise(exc)


def _require_slot_management(request, *, recent_mfa: bool = False) -> None:
    user = request.auth_user
    if current_slot_staff(user) is None:
        raise APIError(
            403,
            "permission_denied",
            "Guidance staff authority with appointments.manage capability is required.",
        )
    if recent_mfa:
        require_recent_mfa_for_request(request)


def _require_student_slot_access(request, capability: str) -> None:
    user = request.auth_user
    role_code = getattr(getattr(user, "role", None), "code", None)
    if not (user.is_active and role_code == "STUDENT" and user.has_capability(capability)):
        raise APIError(
            403,
            "permission_denied",
            f"Student authority with {capability} capability is required.",
        )


@router.get(
    "/{service_id}/slots",
    response=response_with_errors(list[ServiceSlotResponse], 401, 403, 404, 422),
    auth=session_auth,
    operation_id="servicesListSlots",
)
def services_list_slots(
    request,
    service_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    provider_id: UUID | None = None,
):
    _require_slot_management(request)
    slots = list_staff_fixed_slots(
        actor=request.auth_user,
        service_id=service_id,
        from_date=from_date,
        to_date=to_date,
        provider_id=provider_id,
    )
    return [_slot_response(slot, actor=request.auth_user) for slot in slots]


@router.post(
    "/{service_id}/slots",
    response=response_with_errors(ServiceSlotResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesCreateSlot",
)
def services_create_slot(request, service_id: UUID, payload: ServiceSlotCreateRequest):
    _require_slot_management(request, recent_mfa=True)
    try:
        slot = create_fixed_slot(
            service_id=service_id,
            provider_id=payload.provider_id,
            delivery_mode=payload.delivery_mode.value,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            is_published=payload.is_published,
            actor=request.auth_user,
            context=_context(request),
        )
        return _slot_response(slot, actor=request.auth_user)
    except Exception as exc:
        _raise_slot_error(exc)


@router.get(
    "/{service_id}/slots/bookable",
    response=response_with_errors(list[StudentBookableSlotResponse], 401, 403, 404, 422),
    auth=session_auth,
    operation_id="servicesListBookableSlots",
)
def services_list_bookable_slots(
    request,
    service_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    delivery_mode: DeliveryMode | None = None,
    provider_id: UUID | None = None,
):
    _require_student_slot_access(request, "appointments.view_self")
    slots = list_student_bookable_slots(
        service_id=service_id,
        student=request.auth_user,
        from_date=from_date,
        to_date=to_date,
        delivery_mode=delivery_mode.value if delivery_mode else None,
        provider_id=provider_id,
    )
    return [_student_slot_response(slot) for slot in slots]


@router.patch(
    "/{service_id}/slots/{slot_id}",
    response=response_with_errors(ServiceSlotResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesUpdateSlot",
)
def services_update_slot(
    request,
    service_id: UUID,
    slot_id: UUID,
    payload: ServiceSlotUpdateRequest,
):
    _require_slot_management(request, recent_mfa=True)
    changes = payload.model_dump(exclude_unset=True)
    try:
        slot = update_fixed_slot(
            slot_id=slot_id,
            service_id=service_id,
            actor=request.auth_user,
            context=_context(request),
            delivery_mode=changes.get("delivery_mode"),
            starts_at=changes.get("starts_at"),
            ends_at=changes.get("ends_at"),
            is_published=changes.get("is_published"),
            provider_id=changes.get("provider_id"),
        )
        return _slot_response(slot, actor=request.auth_user)
    except Exception as exc:
        _raise_slot_error(exc)


@router.post(
    "/{service_id}/slots/{slot_id}/withdraw",
    response=response_with_errors(ServiceSlotResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesWithdrawSlot",
    summary="Withdraw a fixed-date appointment slot",
)
def services_withdraw_slot(request, service_id: UUID, slot_id: UUID):
    _require_slot_management(request, recent_mfa=True)
    try:
        slot = withdraw_fixed_slot(
            slot_id=slot_id,
            service_id=service_id,
            actor=request.auth_user,
            context=_context(request),
        )
        return _slot_response(slot, actor=request.auth_user)
    except Exception as exc:
        _raise_slot_error(exc)


@router.post(
    "/{service_id}/slots/{slot_id}/book",
    response=response_with_errors(BookSlotResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesBookSlot",
)
def services_book_slot(request, service_id: UUID, slot_id: UUID):
    _require_student_slot_access(request, "appointments.manage_self")
    try:
        appointment = book_fixed_slot(
            slot_id=slot_id,
            service_id=service_id,
            student=request.auth_user,
            context=_context(request),
        )
        return {
            "appointment_id": appointment.pk,
            "reference_code": appointment.reference_code,
            "service_id": appointment.service_id,
            "provider_id": appointment.provider_id,
            "delivery_mode": appointment.delivery_mode,
            "starts_at": appointment.starts_at,
            "ends_at": appointment.ends_at,
        }
    except Exception as exc:
        _raise_slot_error(exc)
