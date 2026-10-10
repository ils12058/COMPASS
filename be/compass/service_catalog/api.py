"""Thin Django Ninja API for Service Catalog configuration."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.step_up import require_recent_mfa_for_request
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.service_catalog.canonical import is_system_required_service_code
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
    list_provider_candidates,
    list_services,
    set_service_active,
    update_service,
)

router = Router(tags=["services"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class DeliveryMode(StrEnum):
    IN_PERSON = "IN_PERSON"
    ONLINE = "ONLINE"


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
