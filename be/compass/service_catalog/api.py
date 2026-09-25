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
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.service_catalog.services import (
    DEFAULT_PAGE_SIZE,
    CanonicalServiceRequired,
    CanonicalServiceReserved,
    InvalidServiceCatalogInput,
    ServiceCatalogConflict,
    ServiceCatalogError,
    ServiceCatalogNotFound,
    create_service,
    get_service,
    list_services,
    set_service_active,
    update_service,
)

router = Router(tags=["services"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AppointmentPolicy(StrEnum):
    NONE = "NONE"
    OPTIONAL = "OPTIONAL"
    REQUIRED = "REQUIRED"


class DeliveryMode(StrEnum):
    IN_PERSON = "IN_PERSON"
    ONLINE = "ONLINE"


class ProviderRoleCode(StrEnum):
    """Response compatibility for historical provider-role assignments."""

    COUNSELOR = "COUNSELOR"
    GUIDANCE_SERVICES_STAFF = "GUIDANCE_SERVICES_STAFF"


class ConfigurableProviderRoleCode(StrEnum):
    """ADR-050 provider configuration accepted for new Service mutations."""

    COUNSELOR = "COUNSELOR"


class ServiceCreateRequest(StrictSchema):
    code: str
    name: str
    appointment_policy: AppointmentPolicy
    description: str = ""
    default_duration_minutes: int | None = None
    cancellation_cutoff_minutes: int | None = None
    requires_current_inventory: bool = False
    delivery_modes: list[DeliveryMode] = Field(default_factory=list)
    provider_roles: list[ConfigurableProviderRoleCode] = Field(default_factory=list)


class ServiceUpdateRequest(StrictSchema):
    name: str = ""
    description: str = ""
    appointment_policy: AppointmentPolicy = AppointmentPolicy.NONE
    default_duration_minutes: int | None = None
    cancellation_cutoff_minutes: int | None = None
    requires_current_inventory: bool = False
    delivery_modes: list[DeliveryMode] = Field(default_factory=list)
    provider_roles: list[ConfigurableProviderRoleCode] = Field(default_factory=list)


class ServiceResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    description: str
    appointment_policy: AppointmentPolicy
    default_duration_minutes: int | None
    cancellation_cutoff_minutes: int | None
    requires_current_inventory: bool
    delivery_modes: list[DeliveryMode]
    provider_roles: list[ProviderRoleCode]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ServiceListResponse(StrictSchema):
    items: list[ServiceResponse]
    page: int
    page_size: int
    has_next: bool


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    if not request.auth_user.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _raise(exc: ServiceCatalogError) -> NoReturn:
    if isinstance(exc, ServiceCatalogNotFound):
        raise APIError(404, "service_not_found", str(exc)) from exc
    if isinstance(exc, CanonicalServiceRequired):
        raise APIError(409, "canonical_service_required", str(exc)) from exc
    if isinstance(exc, CanonicalServiceReserved):
        raise APIError(409, "canonical_service_reserved", str(exc)) from exc
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
        "appointment_policy": item.appointment_policy,
        "default_duration_minutes": item.default_duration_minutes,
        "cancellation_cutoff_minutes": item.cancellation_cutoff_minutes,
        "requires_current_inventory": item.requires_current_inventory,
        "delivery_modes": sorted(
            assignment.mode for assignment in item.delivery_mode_assignments.all()
        ),
        "provider_roles": sorted(
            assignment.role.code for assignment in item.provider_role_assignments.all()
        ),
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


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
    appointment_policy: AppointmentPolicy | None = None,
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
            appointment_policy=appointment_policy.value if appointment_policy else None,
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
    }


@router.post(
    "",
    response=response_with_errors(ServiceResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="servicesCreate",
)
def services_create(request, payload: ServiceCreateRequest):
    _require(request, "services.manage", recent_mfa=True)
    values = payload.model_dump()
    values["appointment_policy"] = payload.appointment_policy.value
    values["delivery_modes"] = [value.value for value in payload.delivery_modes]
    values["provider_roles"] = [value.value for value in payload.provider_roles]
    try:
        item = create_service(**values, context=_context(request))
    except ServiceCatalogError as exc:
        _raise(exc)
    return Status(201, _service(item))


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


@router.patch(
    "/{service_id}",
    response=response_with_errors(ServiceResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="servicesUpdate",
)
def services_update(request, service_id: UUID, payload: ServiceUpdateRequest):
    _require(request, "services.manage", recent_mfa=True)
    changes = payload.model_dump(exclude_unset=True)
    if "appointment_policy" in changes:
        changes["appointment_policy"] = payload.appointment_policy.value
    if "delivery_modes" in changes:
        changes["delivery_modes"] = [value.value for value in payload.delivery_modes]
    if "provider_roles" in changes:
        changes["provider_roles"] = [value.value for value in payload.provider_roles]
    try:
        return _service(
            update_service(service_id=service_id, changes=changes, context=_context(request))
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
def services_disable(request, service_id: UUID):
    _require(request, "services.manage", recent_mfa=True)
    try:
        return _service(
            set_service_active(service_id=service_id, is_active=False, context=_context(request))
        )
    except ServiceCatalogError as exc:
        _raise(exc)
