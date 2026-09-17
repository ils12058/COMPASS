"""Transactional Service Catalog use cases and narrow provider-role eligibility helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from compass.accounts.models import Role, User
from compass.audit.actions import (
    SERVICE_CREATED,
    SERVICE_DISABLED,
    SERVICE_ENABLED,
    SERVICE_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.models import (
    MAX_SERVICE_DURATION_MINUTES,
    MIN_SERVICE_DURATION_MINUTES,
    AppointmentPolicy,
    DeliveryMode,
    Service,
    ServiceDeliveryMode,
    ServiceProviderRole,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_DESCRIPTION_LENGTH = 2000
SERVICE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$", re.ASCII)
ELIGIBLE_PROVIDER_ROLE_CODES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})


class ServiceCatalogError(RuntimeError):
    pass


class ServiceCatalogNotFound(ServiceCatalogError):
    pass


class InvalidServiceCatalogInput(ServiceCatalogError):
    pass


class ServiceCatalogConflict(ServiceCatalogError):
    pass


@dataclass(frozen=True, slots=True)
class ServicePage:
    items: tuple[Service, ...]
    page: int
    page_size: int
    has_next: bool


def normalize_service_code(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidServiceCatalogInput("code is required")
    normalized = value.strip().upper()
    if not SERVICE_CODE_RE.fullmatch(normalized):
        raise InvalidServiceCatalogInput(
            "code must start with A-Z and contain only A-Z, 0-9, or underscore"
        )
    return normalized


def _normalize_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidServiceCatalogInput("name is required")
    normalized = value.strip()
    if len(normalized) > 160:
        raise InvalidServiceCatalogInput("name is too long")
    return normalized


def _normalize_description(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidServiceCatalogInput("description must be a string")
    normalized = value.strip()
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise InvalidServiceCatalogInput("description is too long")
    return normalized


def _normalize_policy(value: str | AppointmentPolicy) -> str:
    normalized = value.value if isinstance(value, AppointmentPolicy) else value
    if normalized not in AppointmentPolicy.values:
        raise InvalidServiceCatalogInput("appointment_policy must be NONE, OPTIONAL, or REQUIRED")
    return normalized


def _normalize_duration(value: int | None) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise InvalidServiceCatalogInput("default_duration_minutes must be an integer or null")
    if not MIN_SERVICE_DURATION_MINUTES <= value <= MAX_SERVICE_DURATION_MINUTES:
        raise InvalidServiceCatalogInput(
            f"default_duration_minutes must be between {MIN_SERVICE_DURATION_MINUTES} "
            f"and {MAX_SERVICE_DURATION_MINUTES}"
        )
    return value


def _normalize_cancellation_cutoff(value: int | None) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise InvalidServiceCatalogInput(
            "cancellation_cutoff_minutes must be a non-negative integer or null"
        )
    return value


def _normalize_inventory_requirement(value: bool) -> bool:
    if type(value) is not bool:
        raise InvalidServiceCatalogInput("requires_current_inventory must be a boolean")
    return value


def _normalize_modes(values: list[str] | tuple[str, ...] | None) -> frozenset[str]:
    if values is None:
        return frozenset()
    normalized = [value.value if isinstance(value, DeliveryMode) else value for value in values]
    if len(normalized) != len(set(normalized)):
        raise InvalidServiceCatalogInput("delivery_modes must not contain duplicates")
    if not set(normalized) <= set(DeliveryMode.values):
        raise InvalidServiceCatalogInput("delivery_modes may contain only IN_PERSON or ONLINE")
    return frozenset(normalized)


def _normalize_provider_roles(values: list[str] | tuple[str, ...] | None) -> frozenset[str]:
    if values is None:
        return frozenset()
    normalized = [getattr(value, "value", value) for value in values]
    if len(normalized) != len(set(normalized)):
        raise InvalidServiceCatalogInput("provider_roles must not contain duplicates")
    if not set(normalized) <= ELIGIBLE_PROVIDER_ROLE_CODES:
        raise InvalidServiceCatalogInput(
            "provider_roles may contain only COUNSELOR or GUIDANCE_SERVICES_STAFF"
        )
    return frozenset(normalized)


def _provider_role_records(role_codes: frozenset[str]) -> dict[str, Role]:
    records = {
        role.code: role for role in Role.objects.filter(code__in=role_codes).order_by("code")
    }
    missing = role_codes - records.keys()
    if missing:
        raise ServiceCatalogConflict("Canonical provider roles have not been synchronized.")
    return records


def _validate_active_configuration(
    *,
    name: str,
    appointment_policy: str,
    default_duration_minutes: int | None,
    cancellation_cutoff_minutes: int | None,
    delivery_modes: frozenset[str],
    provider_roles: frozenset[str],
) -> None:
    _normalize_name(name)
    policy = _normalize_policy(appointment_policy)
    duration = _normalize_duration(default_duration_minutes)
    cutoff = _normalize_cancellation_cutoff(cancellation_cutoff_minutes)
    if not delivery_modes:
        raise ServiceCatalogConflict("An active Service must have at least one delivery mode.")
    if not provider_roles:
        raise ServiceCatalogConflict("An active Service must have at least one provider role.")
    if policy in {AppointmentPolicy.OPTIONAL, AppointmentPolicy.REQUIRED} and duration is None:
        raise ServiceCatalogConflict(
            "OPTIONAL and REQUIRED Services need a default schedulable duration before activation."
        )
    if policy == AppointmentPolicy.NONE and cutoff is not None:
        raise ServiceCatalogConflict(
            "A Service with appointment_policy NONE cannot configure a cancellation cutoff."
        )


def _configured_modes(service_id: UUID) -> frozenset[str]:
    return frozenset(
        ServiceDeliveryMode.objects.filter(service_id=service_id).values_list("mode", flat=True)
    )


def _configured_provider_roles(service_id: UUID) -> frozenset[str]:
    return frozenset(
        ServiceProviderRole.objects.filter(service_id=service_id).values_list(
            "role__code", flat=True
        )
    )


def _service_queryset():
    return Service.objects.prefetch_related(
        "delivery_mode_assignments",
        "provider_role_assignments__role",
    )


def list_services(
    *,
    include_inactive: bool = False,
    search: str | None = None,
    appointment_policy: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ServicePage:
    if type(page) is not int or page < 1:
        raise InvalidServiceCatalogInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidServiceCatalogInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    qs = _service_queryset().order_by("code", "id")
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if search and search.strip():
        term = search.strip()[:160]
        qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
    if appointment_policy is not None:
        qs = qs.filter(appointment_policy=_normalize_policy(appointment_policy))
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return ServicePage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def get_service(service_id: UUID) -> Service:
    service = _service_queryset().filter(pk=service_id).first()
    if service is None:
        raise ServiceCatalogNotFound("The requested Service was not found.")
    return service


def create_service(
    *,
    code: str,
    name: str,
    appointment_policy: str,
    description: str | None = "",
    default_duration_minutes: int | None = None,
    cancellation_cutoff_minutes: int | None = None,
    requires_current_inventory: bool = False,
    delivery_modes: list[str] | tuple[str, ...] | None = None,
    provider_roles: list[str] | tuple[str, ...] | None = None,
    context: AuditContext,
) -> Service:
    normalized_code = normalize_service_code(code)
    normalized_name = _normalize_name(name)
    normalized_description = _normalize_description(description)
    normalized_policy = _normalize_policy(appointment_policy)
    normalized_duration = _normalize_duration(default_duration_minutes)
    normalized_cutoff = _normalize_cancellation_cutoff(cancellation_cutoff_minutes)
    normalized_requirement = _normalize_inventory_requirement(requires_current_inventory)
    normalized_modes = _normalize_modes(delivery_modes)
    normalized_roles = _normalize_provider_roles(provider_roles)

    with transaction.atomic():
        role_records = _provider_role_records(normalized_roles)
        try:
            service = Service.objects.create(
                code=normalized_code,
                name=normalized_name,
                description=normalized_description,
                appointment_policy=normalized_policy,
                default_duration_minutes=normalized_duration,
                cancellation_cutoff_minutes=normalized_cutoff,
                requires_current_inventory=normalized_requirement,
                is_active=False,
            )
        except IntegrityError as exc:
            raise ServiceCatalogConflict("A Service with this code already exists.") from exc
        ServiceDeliveryMode.objects.bulk_create(
            [ServiceDeliveryMode(service=service, mode=mode) for mode in sorted(normalized_modes)]
        )
        ServiceProviderRole.objects.bulk_create(
            [
                ServiceProviderRole(service=service, role=role_records[role_code])
                for role_code in sorted(normalized_roles)
            ]
        )
        record_event(
            context=context,
            action=SERVICE_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.service",
            target_id=service.pk,
            metadata={"code": service.code},
        )
    return get_service(service.pk)


def update_service(
    *,
    service_id: UUID,
    changes: dict[str, object],
    context: AuditContext,
) -> Service:
    allowed = {
        "name",
        "description",
        "appointment_policy",
        "default_duration_minutes",
        "cancellation_cutoff_minutes",
        "requires_current_inventory",
        "delivery_modes",
        "provider_roles",
    }
    if not set(changes) <= allowed:
        raise InvalidServiceCatalogInput("The Service update contains unsupported fields.")

    with transaction.atomic():
        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise ServiceCatalogNotFound("The requested Service was not found.")

        current_modes = _configured_modes(service.pk)
        current_roles = _configured_provider_roles(service.pk)
        next_name = _normalize_name(changes["name"]) if "name" in changes else service.name
        next_description = (
            _normalize_description(changes["description"])
            if "description" in changes
            else service.description
        )
        next_policy = (
            _normalize_policy(changes["appointment_policy"])
            if "appointment_policy" in changes
            else service.appointment_policy
        )
        next_duration = (
            _normalize_duration(changes["default_duration_minutes"])
            if "default_duration_minutes" in changes
            else service.default_duration_minutes
        )
        next_cutoff = (
            _normalize_cancellation_cutoff(changes["cancellation_cutoff_minutes"])
            if "cancellation_cutoff_minutes" in changes
            else service.cancellation_cutoff_minutes
        )
        next_requirement = (
            _normalize_inventory_requirement(changes["requires_current_inventory"])
            if "requires_current_inventory" in changes
            else service.requires_current_inventory
        )
        next_modes = (
            _normalize_modes(changes["delivery_modes"])
            if "delivery_modes" in changes
            else current_modes
        )
        next_roles = (
            _normalize_provider_roles(changes["provider_roles"])
            if "provider_roles" in changes
            else current_roles
        )

        if service.is_active:
            _validate_active_configuration(
                name=next_name,
                appointment_policy=next_policy,
                default_duration_minutes=next_duration,
                cancellation_cutoff_minutes=next_cutoff,
                delivery_modes=next_modes,
                provider_roles=next_roles,
            )

        changed_fields: list[str] = []
        scalar_values = {
            "name": next_name,
            "description": next_description,
            "appointment_policy": next_policy,
            "default_duration_minutes": next_duration,
            "cancellation_cutoff_minutes": next_cutoff,
            "requires_current_inventory": next_requirement,
        }
        for field, value in scalar_values.items():
            if getattr(service, field) != value:
                setattr(service, field, value)
                changed_fields.append(field)
        if current_modes != next_modes:
            changed_fields.append("delivery_modes")
        if current_roles != next_roles:
            changed_fields.append("provider_roles")
        if not changed_fields:
            return get_service(service.pk)

        role_records = _provider_role_records(next_roles) if current_roles != next_roles else {}
        scalar_changed = [field for field in changed_fields if field in scalar_values]
        if scalar_changed:
            service.save(update_fields=[*scalar_changed, "updated_at"])
        if current_modes != next_modes:
            ServiceDeliveryMode.objects.filter(service=service).delete()
            ServiceDeliveryMode.objects.bulk_create(
                [ServiceDeliveryMode(service=service, mode=mode) for mode in sorted(next_modes)]
            )
        if current_roles != next_roles:
            ServiceProviderRole.objects.filter(service=service).delete()
            ServiceProviderRole.objects.bulk_create(
                [
                    ServiceProviderRole(service=service, role=role_records[role_code])
                    for role_code in sorted(next_roles)
                ]
            )
        record_event(
            context=context,
            action=SERVICE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.service",
            target_id=service.pk,
            metadata={"changed_fields": changed_fields},
        )
    return get_service(service.pk)


def set_service_active(
    *,
    service_id: UUID,
    is_active: bool,
    context: AuditContext,
) -> Service:
    with transaction.atomic():
        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise ServiceCatalogNotFound("The requested Service was not found.")
        if service.is_active == is_active:
            return get_service(service.pk)
        if is_active:
            _validate_active_configuration(
                name=service.name,
                appointment_policy=service.appointment_policy,
                default_duration_minutes=service.default_duration_minutes,
                cancellation_cutoff_minutes=service.cancellation_cutoff_minutes,
                delivery_modes=_configured_modes(service.pk),
                provider_roles=_configured_provider_roles(service.pk),
            )
        service.is_active = is_active
        service.save(update_fields=["is_active", "updated_at"])
        record_event(
            context=context,
            action=SERVICE_ENABLED if is_active else SERVICE_DISABLED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.service",
            target_id=service.pk,
            metadata={},
        )
    return get_service(service.pk)


def service_allows_provider_role(service: Service, role_code: str) -> bool:
    if not getattr(service, "pk", None) or role_code not in ELIGIBLE_PROVIDER_ROLE_CODES:
        return False
    return ServiceProviderRole.objects.filter(service_id=service.pk, role__code=role_code).exists()


def provider_role_eligible(service: Service, user: User) -> bool:
    """Check role-level operational eligibility only.

    This does not evaluate routing, organization scope, record access, or availability.
    """
    if not getattr(user, "pk", None) or not user.is_active:
        return False
    role_code = user.role.code
    if role_code not in ELIGIBLE_PROVIDER_ROLE_CODES:
        return False
    return service_allows_provider_role(service, role_code)


def service_supports_delivery_mode(service: Service, mode: str | DeliveryMode) -> bool:
    """Return whether a saved Service supports one canonical delivery mode."""
    normalized = mode.value if isinstance(mode, DeliveryMode) else mode
    if not getattr(service, "pk", None) or normalized not in DeliveryMode.values:
        return False
    return ServiceDeliveryMode.objects.filter(service_id=service.pk, mode=normalized).exists()
