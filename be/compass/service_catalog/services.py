"""Transactional Service Catalog use cases and current Counselor qualification (ADR-089)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.functions import Lower
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    SERVICE_CREATED,
    SERVICE_DISABLED,
    SERVICE_ENABLED,
    SERVICE_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.ordering import parse_ordering
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import (
    MAX_SERVICE_DURATION_MINUTES,
    MIN_SERVICE_DURATION_MINUTES,
    DeliveryMode,
    Service,
    ServiceCounselorProvider,
    ServiceDeliveryMode,
    ServiceProviderCoverage,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_DESCRIPTION_LENGTH = 2000
MAX_SELECTED_COUNSELORS = 200
SERVICE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$", re.ASCII)
# Counselor is the one operational provider class (ADR-050, ADR-089). Guidance Services Staff
# administer Appointments but never provide Services.
PROVIDER_ROLE_CODE = "COUNSELOR"
ELIGIBLE_PROVIDER_ROLE_CODES = frozenset({PROVIDER_ROLE_CODE})

APPOINTMENT_SETTING_FIELDS = (
    "default_appointment_duration_minutes",
    "cancellation_cutoff_minutes",
    "requires_current_inventory",
)


class ServiceCatalogError(RuntimeError):
    pass


class ServiceCatalogNotFound(ServiceCatalogError):
    pass


class InvalidServiceCatalogInput(ServiceCatalogError):
    pass


class ServiceCatalogConflict(ServiceCatalogError):
    pass


class ServiceSchedulingConsequenceReviewRequired(ServiceCatalogConflict):
    """A legal Service change needs explicit review of its scheduling consequences."""

    def __init__(
        self,
        message: str,
        *,
        existing_appointment_dependency_detected: bool,
        provider_dependency_detected: bool,
        counseling_online_enabled: bool,
    ) -> None:
        super().__init__(message)
        self.existing_appointment_dependency_detected = existing_appointment_dependency_detected
        self.provider_dependency_detected = provider_dependency_detected
        self.counseling_online_enabled = counseling_online_enabled


class CanonicalServiceRequired(ServiceCatalogConflict):
    """A normal catalog mutation would break required Counseling configuration."""


class CanonicalServiceReserved(ServiceCatalogConflict):
    """The canonical code can only be provisioned by deployment synchronization."""


class ServiceOrdering(StrEnum):
    """Closed Service Catalog orderings (ADR-090); the catalog reads by code A–Z."""

    CODE_ASC = "CODE_ASC"
    CODE_DESC = "CODE_DESC"
    NAME_ASC = "NAME_ASC"
    NAME_DESC = "NAME_DESC"


_SERVICE_ORDER_BY: dict[ServiceOrdering, tuple] = {
    ServiceOrdering.CODE_ASC: ("code", "id"),
    ServiceOrdering.CODE_DESC: ("-code", "-id"),
    ServiceOrdering.NAME_ASC: (Lower("name"), "code", "id"),
    ServiceOrdering.NAME_DESC: (Lower("name").desc(), "-code", "-id"),
}


@dataclass(frozen=True, slots=True)
class ServicePage:
    items: tuple[Service, ...]
    page: int
    page_size: int
    has_next: bool
    ordering: ServiceOrdering | None = None


@dataclass(frozen=True, slots=True)
class ProviderCandidatePage:
    items: tuple[User, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class ServiceProviderConfiguration:
    provider_coverage: str
    # Selected Counselors, including any whose account has since become inactive.
    counselors: tuple[User, ...]


@dataclass(frozen=True, slots=True)
class _ServiceConfiguration:
    name: str
    appointment_booking_enabled: bool
    default_appointment_duration_minutes: int | None
    cancellation_cutoff_minutes: int | None
    requires_current_inventory: bool
    delivery_modes: frozenset[str]
    provider_coverage: str
    selected_counselor_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class _ServiceSchedulingConsequences:
    existing_appointment_dependency_detected: bool
    provider_dependency_detected: bool
    counseling_online_enabled: bool

    @property
    def requires_review(self) -> bool:
        return (
            self.existing_appointment_dependency_detected
            or self.provider_dependency_detected
            or self.counseling_online_enabled
        )


class ServiceActivationBlocker:
    """Why an inactive Service cannot be enabled yet (stable API values)."""

    DELIVERY_MODE_MISSING = "DELIVERY_MODE_MISSING"
    APPOINTMENT_DURATION_MISSING = "APPOINTMENT_DURATION_MISSING"
    SELECTED_COUNSELORS_MISSING = "SELECTED_COUNSELORS_MISSING"


# Normalization ---------------------------------------------------------------------------------


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


def _normalize_bool(value: bool, field: str) -> bool:
    if type(value) is not bool:
        raise InvalidServiceCatalogInput(f"{field} must be a boolean")
    return value


def _normalize_duration(value: int | None) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise InvalidServiceCatalogInput(
            "default_appointment_duration_minutes must be an integer or null"
        )
    if not MIN_SERVICE_DURATION_MINUTES <= value <= MAX_SERVICE_DURATION_MINUTES:
        raise InvalidServiceCatalogInput(
            f"default_appointment_duration_minutes must be between "
            f"{MIN_SERVICE_DURATION_MINUTES} and {MAX_SERVICE_DURATION_MINUTES}"
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


def _normalize_modes(values: list[str] | tuple[str, ...] | None) -> frozenset[str]:
    if values is None:
        return frozenset()
    normalized = [value.value if isinstance(value, DeliveryMode) else value for value in values]
    if len(normalized) != len(set(normalized)):
        raise InvalidServiceCatalogInput("delivery_modes must not contain duplicates")
    if not set(normalized) <= set(DeliveryMode.values):
        raise InvalidServiceCatalogInput("delivery_modes may contain only IN_PERSON or ONLINE")
    return frozenset(normalized)


def _normalize_coverage(value: str | ServiceProviderCoverage) -> str:
    normalized = value.value if isinstance(value, ServiceProviderCoverage) else value
    if normalized not in ServiceProviderCoverage.values:
        raise InvalidServiceCatalogInput(
            "provider_coverage must be ALL_COUNSELORS or SELECTED_COUNSELORS"
        )
    return str(normalized)


def _normalize_counselor_ids(values: list[UUID] | tuple[UUID, ...] | None) -> frozenset[UUID]:
    if values is None:
        return frozenset()
    if not isinstance(values, (list, tuple)) or not all(isinstance(v, UUID) for v in values):
        raise InvalidServiceCatalogInput("selected_counselor_ids must be a list of UUIDs")
    if len(values) != len(set(values)):
        raise InvalidServiceCatalogInput("selected_counselor_ids must not contain duplicates")
    if len(values) > MAX_SELECTED_COUNSELORS:
        raise InvalidServiceCatalogInput(
            f"selected_counselor_ids may contain at most {MAX_SELECTED_COUNSELORS} Counselors"
        )
    return frozenset(values)


def _normalize_booking_settings(
    *,
    booking_enabled: bool,
    duration: int | None,
    cutoff: int | None,
    requires_inventory: bool,
    explicit: frozenset[str],
) -> tuple[int | None, int | None, bool]:
    """Keep Appointment-only settings empty while booking is off.

    Turning booking off clears them. Supplying one explicitly alongside disabled booking is
    rejected instead of silently discarded.
    """

    if booking_enabled:
        return duration, cutoff, requires_inventory
    supplied = {
        "default_appointment_duration_minutes": duration is not None,
        "cancellation_cutoff_minutes": cutoff is not None,
        "requires_current_inventory": requires_inventory,
    }
    conflicting = sorted(field for field in explicit if supplied.get(field))
    if conflicting:
        raise ServiceCatalogConflict(
            "Appointment settings apply only when Appointment booking is available: "
            + ", ".join(conflicting)
            + "."
        )
    return None, None, False


# Configuration reads ---------------------------------------------------------------------------


def _configured_modes(service_id: UUID) -> frozenset[str]:
    return frozenset(
        ServiceDeliveryMode.objects.filter(service_id=service_id).values_list("mode", flat=True)
    )


def _selected_counselor_ids(service_id: UUID) -> frozenset[UUID]:
    return frozenset(
        ServiceCounselorProvider.objects.filter(service_id=service_id).values_list(
            "counselor_id", flat=True
        )
    )


def _current_configuration(service: Service) -> _ServiceConfiguration:
    return _ServiceConfiguration(
        name=service.name,
        appointment_booking_enabled=service.appointment_booking_enabled,
        default_appointment_duration_minutes=service.default_appointment_duration_minutes,
        cancellation_cutoff_minutes=service.cancellation_cutoff_minutes,
        requires_current_inventory=service.requires_current_inventory,
        delivery_modes=_configured_modes(service.pk),
        provider_coverage=service.provider_coverage,
        selected_counselor_ids=_selected_counselor_ids(service.pk),
    )


def _active_counselors() -> QuerySet[User]:
    return User.objects.filter(is_active=True, role__code=PROVIDER_ROLE_CODE)


def activation_blockers(service: Service) -> tuple[str, ...]:
    """Return why ``service`` could not be enabled with its saved configuration."""

    return _blockers(_current_configuration(service))


def _blockers(configuration: _ServiceConfiguration) -> tuple[str, ...]:
    blockers: list[str] = []
    if not configuration.delivery_modes:
        blockers.append(ServiceActivationBlocker.DELIVERY_MODE_MISSING)
    if (
        configuration.appointment_booking_enabled
        and configuration.default_appointment_duration_minutes is None
    ):
        blockers.append(ServiceActivationBlocker.APPOINTMENT_DURATION_MISSING)
    if (
        configuration.provider_coverage == ServiceProviderCoverage.SELECTED_COUNSELORS
        and not _active_counselors().filter(pk__in=configuration.selected_counselor_ids).exists()
    ):
        blockers.append(ServiceActivationBlocker.SELECTED_COUNSELORS_MISSING)
    return tuple(blockers)


_BLOCKER_MESSAGES = {
    ServiceActivationBlocker.DELIVERY_MODE_MISSING: (
        "An active Service must have at least one delivery mode."
    ),
    ServiceActivationBlocker.APPOINTMENT_DURATION_MISSING: (
        "An active Service with Appointment booking needs a default Appointment duration."
    ),
    ServiceActivationBlocker.SELECTED_COUNSELORS_MISSING: (
        "An active Service limited to selected Counselors needs at least one active selected "
        "Counselor."
    ),
}


def _validate_active_configuration(configuration: _ServiceConfiguration) -> None:
    _normalize_name(configuration.name)
    blockers = _blockers(configuration)
    if blockers:
        raise ServiceCatalogConflict(_BLOCKER_MESSAGES[blockers[0]])


# Current Counselor qualification ---------------------------------------------------------------


def service_counselor_eligible(service: Service, counselor: User) -> bool:
    """Whether ``counselor`` is currently qualified to provide NEW work for ``service``.

    Qualification only: an active Counselor, and either ALL_COUNSELORS coverage or an explicit
    selection. College responsibility, Availability, delivery mode, record access, and existing
    Appointment ownership are separate layers and are not consulted.
    """

    if not getattr(service, "pk", None) or not getattr(counselor, "pk", None):
        return False
    if not counselor.is_active or counselor.role.code != PROVIDER_ROLE_CODE:
        return False
    if service.provider_coverage == ServiceProviderCoverage.ALL_COUNSELORS:
        return True
    return ServiceCounselorProvider.objects.filter(
        service_id=service.pk, counselor_id=counselor.pk
    ).exists()


def service_eligible_counselors(service: Service) -> QuerySet[User]:
    """Active Counselors currently qualified to provide NEW work for ``service``."""

    queryset = _active_counselors().select_related("role")
    if service.provider_coverage == ServiceProviderCoverage.ALL_COUNSELORS:
        return queryset
    return queryset.filter(service_provider_qualifications__service_id=service.pk)


def service_has_eligible_counselor_q() -> Q:
    """A Service-level filter: at least one active Counselor is currently qualified."""

    selected = ServiceCounselorProvider.objects.filter(
        service_id=OuterRef("pk"),
        counselor__is_active=True,
        counselor__role__code=PROVIDER_ROLE_CODE,
    )
    return Q(provider_coverage=ServiceProviderCoverage.ALL_COUNSELORS) | Q(Exists(selected))


def service_supports_delivery_mode(service: Service, mode: str | DeliveryMode) -> bool:
    """Return whether a saved Service currently offers one canonical delivery mode."""

    normalized = mode.value if isinstance(mode, DeliveryMode) else mode
    if not getattr(service, "pk", None) or normalized not in DeliveryMode.values:
        return False
    return ServiceDeliveryMode.objects.filter(service_id=service.pk, mode=normalized).exists()


def _counselor_eligible_under(configuration: _ServiceConfiguration, counselor: User) -> bool:
    if not counselor.is_active or counselor.role.code != PROVIDER_ROLE_CODE:
        return False
    if configuration.provider_coverage == ServiceProviderCoverage.ALL_COUNSELORS:
        return True
    return counselor.pk in configuration.selected_counselor_ids


def _validate_new_selections(*, added: frozenset[UUID]) -> None:
    """Newly selected providers must be existing active Counselors.

    A Counselor already selected whose account later became inactive may stay selected; they
    simply stop being eligible until reactivated.
    """

    if not added:
        return
    rows = {
        user.pk: user
        for user in User.objects.select_related("role").filter(pk__in=sorted(added, key=str))
    }
    if len(rows) != len(added):
        raise InvalidServiceCatalogInput("A selected Counselor account was not found.")
    for user in rows.values():
        if user.role.code != PROVIDER_ROLE_CODE:
            raise ServiceCatalogConflict("Only Counselors can be selected as Service providers.")
        if not user.is_active:
            raise ServiceCatalogConflict("An inactive account cannot be selected as a provider.")


def _normalize_selection(
    *, coverage: str, selected: frozenset[UUID], explicit: bool
) -> frozenset[UUID]:
    if coverage == ServiceProviderCoverage.ALL_COUNSELORS:
        if explicit and selected:
            raise ServiceCatalogConflict(
                "Selected Counselors apply only when provider coverage is SELECTED_COUNSELORS."
            )
        return frozenset()
    return selected


# Scheduling consequences -----------------------------------------------------------------------


def _scheduling_consequences(
    *,
    service: Service,
    current: _ServiceConfiguration,
    proposed: _ServiceConfiguration,
    now: datetime,
) -> _ServiceSchedulingConsequences:
    """Detect legal changes whose effect on future scheduled Appointments needs review.

    Existing Appointments are never changed; review confirms the operator understands they stay
    scheduled under their saved provenance while new work follows the new configuration.
    """

    counseling_online_enabled = (
        service.code == COUNSELING_SERVICE_CODE
        and DeliveryMode.ONLINE not in current.delivery_modes
        and DeliveryMode.ONLINE in proposed.delivery_modes
    )
    if not service.is_active:
        return _ServiceSchedulingConsequences(False, False, counseling_online_enabled)

    from compass.appointments.models import Appointment, AppointmentStatus

    future_scheduled = Appointment.objects.filter(
        service_id=service.pk,
        status=AppointmentStatus.SCHEDULED,
        starts_at__gt=now,
    )
    existing_dependency = False
    if current.appointment_booking_enabled and not proposed.appointment_booking_enabled:
        existing_dependency = future_scheduled.exists()
    removed_modes = current.delivery_modes - proposed.delivery_modes
    if removed_modes and not existing_dependency:
        existing_dependency = future_scheduled.filter(delivery_mode__in=removed_modes).exists()

    provider_dependency = False
    if (
        current.provider_coverage != proposed.provider_coverage
        or current.selected_counselor_ids != proposed.selected_counselor_ids
    ):
        providers = User.objects.select_related("role").filter(
            pk__in=future_scheduled.values("provider_id")
        )
        provider_dependency = any(
            _counselor_eligible_under(current, provider)
            and not _counselor_eligible_under(proposed, provider)
            for provider in providers
        )
    return _ServiceSchedulingConsequences(
        existing_appointment_dependency_detected=existing_dependency,
        provider_dependency_detected=provider_dependency,
        counseling_online_enabled=counseling_online_enabled,
    )


def _require_review(consequences: _ServiceSchedulingConsequences, acknowledged: bool) -> None:
    if consequences.requires_review and not acknowledged:
        raise ServiceSchedulingConsequenceReviewRequired(
            "Review the scheduling consequences before saving this Service change.",
            existing_appointment_dependency_detected=(
                consequences.existing_appointment_dependency_detected
            ),
            provider_dependency_detected=consequences.provider_dependency_detected,
            counseling_online_enabled=consequences.counseling_online_enabled,
        )


def _consequence_metadata(consequences: _ServiceSchedulingConsequences) -> dict[str, object]:
    if not consequences.requires_review:
        return {}
    return {
        "scheduling_consequence_acknowledged": True,
        "existing_appointment_dependency_detected": (
            consequences.existing_appointment_dependency_detected
        ),
        "provider_dependency_detected": consequences.provider_dependency_detected,
        "counseling_online_enabled": consequences.counseling_online_enabled,
    }


# Catalog use cases -----------------------------------------------------------------------------


def _service_queryset():
    return Service.objects.prefetch_related("delivery_mode_assignments")


def list_services(
    *,
    include_inactive: bool = False,
    search: str | None = None,
    appointment_booking_enabled: bool | None = None,
    ordering: str | ServiceOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ServicePage:
    if type(page) is not int or page < 1:
        raise InvalidServiceCatalogInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidServiceCatalogInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    resolved = parse_ordering(
        ordering,
        ServiceOrdering,
        default=ServiceOrdering.CODE_ASC,
        error=InvalidServiceCatalogInput,
    )
    qs = _service_queryset().order_by(*_SERVICE_ORDER_BY[resolved])
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if search and search.strip():
        term = search.strip()[:160]
        qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
    if appointment_booking_enabled is not None:
        qs = qs.filter(
            appointment_booking_enabled=_normalize_bool(
                appointment_booking_enabled, "appointment_booking_enabled"
            )
        )
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return ServicePage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size, resolved)


def get_service(service_id: UUID) -> Service:
    service = _service_queryset().filter(pk=service_id).first()
    if service is None:
        raise ServiceCatalogNotFound("The requested Service was not found.")
    return service


def get_service_providers(service_id: UUID) -> ServiceProviderConfiguration:
    service = get_service(service_id)
    counselors = tuple(
        User.objects.select_related("role")
        .filter(service_provider_qualifications__service_id=service.pk)
        .order_by("last_name", "first_name", "pk")
    )
    return ServiceProviderConfiguration(service.provider_coverage, counselors)


def list_provider_candidates(
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ProviderCandidatePage:
    """Active Counselors that may be selected as Service providers, without College filtering."""

    if type(page) is not int or page < 1:
        raise InvalidServiceCatalogInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidServiceCatalogInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    qs = _active_counselors()
    if search is not None:
        if not isinstance(search, str):
            raise InvalidServiceCatalogInput("search must be text")
        for token in search.strip()[:160].split():
            qs = qs.filter(
                Q(first_name__icontains=token)
                | Q(middle_name__icontains=token)
                | Q(last_name__icontains=token)
            )
    qs = qs.order_by("last_name", "first_name", "pk")
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return ProviderCandidatePage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def _replace_selection(service: Service, selected: frozenset[UUID]) -> None:
    ServiceCounselorProvider.objects.filter(service=service).exclude(
        counselor_id__in=selected
    ).delete()
    existing = _selected_counselor_ids(service.pk)
    ServiceCounselorProvider.objects.bulk_create(
        [
            ServiceCounselorProvider(service=service, counselor_id=counselor_id)
            for counselor_id in sorted(selected - existing, key=str)
        ]
    )


def create_service(
    *,
    code: str,
    name: str,
    appointment_booking_enabled: bool = False,
    description: str | None = "",
    default_appointment_duration_minutes: int | None = None,
    cancellation_cutoff_minutes: int | None = None,
    requires_current_inventory: bool = False,
    delivery_modes: list[str] | tuple[str, ...] | None = None,
    provider_coverage: str = ServiceProviderCoverage.ALL_COUNSELORS,
    selected_counselor_ids: list[UUID] | tuple[UUID, ...] | None = None,
    context: AuditContext,
) -> Service:
    """Create an inactive Service; it may be incomplete until it is enabled separately."""

    normalized_code = normalize_service_code(code)
    if normalized_code == COUNSELING_SERVICE_CODE:
        raise CanonicalServiceReserved(
            "COUNSELING is system-managed. Run sync_canonical_services to provision it."
        )
    booking = _normalize_bool(appointment_booking_enabled, "appointment_booking_enabled")
    duration, cutoff, requires_inventory = _normalize_booking_settings(
        booking_enabled=booking,
        duration=_normalize_duration(default_appointment_duration_minutes),
        cutoff=_normalize_cancellation_cutoff(cancellation_cutoff_minutes),
        requires_inventory=_normalize_bool(
            requires_current_inventory, "requires_current_inventory"
        ),
        explicit=frozenset(APPOINTMENT_SETTING_FIELDS),
    )
    modes = _normalize_modes(delivery_modes)
    coverage = _normalize_coverage(provider_coverage)
    selected = _normalize_selection(
        coverage=coverage,
        selected=_normalize_counselor_ids(selected_counselor_ids),
        explicit=True,
    )
    normalized_name = _normalize_name(name)
    normalized_description = _normalize_description(description)

    with transaction.atomic():
        _validate_new_selections(added=selected)
        try:
            service = Service.objects.create(
                code=normalized_code,
                name=normalized_name,
                description=normalized_description,
                appointment_booking_enabled=booking,
                default_appointment_duration_minutes=duration,
                cancellation_cutoff_minutes=cutoff,
                requires_current_inventory=requires_inventory,
                provider_coverage=coverage,
                is_active=False,
            )
        except IntegrityError as exc:
            raise ServiceCatalogConflict("A Service with this code already exists.") from exc
        ServiceDeliveryMode.objects.bulk_create(
            [ServiceDeliveryMode(service=service, mode=mode) for mode in sorted(modes)]
        )
        _replace_selection(service, selected)
        record_event(
            context=context,
            action=SERVICE_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.service",
            target_id=service.pk,
            metadata={"code": service.code},
        )
    return get_service(service.pk)


_UPDATABLE_FIELDS = frozenset(
    {
        "name",
        "description",
        "appointment_booking_enabled",
        *APPOINTMENT_SETTING_FIELDS,
        "delivery_modes",
        "provider_coverage",
        "selected_counselor_ids",
    }
)


def update_service(
    *,
    service_id: UUID,
    changes: dict[str, object],
    context: AuditContext,
    acknowledge_scheduling_consequences: bool = False,
    now: datetime | None = None,
) -> Service:
    if not set(changes) <= _UPDATABLE_FIELDS:
        raise InvalidServiceCatalogInput("The Service update contains unsupported fields.")
    if type(acknowledge_scheduling_consequences) is not bool:
        raise InvalidServiceCatalogInput("acknowledge_scheduling_consequences must be a boolean.")
    current_time = now or timezone.now()
    if timezone.is_naive(current_time):
        raise InvalidServiceCatalogInput("The Service update time must be timezone-aware.")

    with transaction.atomic():
        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise ServiceCatalogNotFound("The requested Service was not found.")
        current = _current_configuration(service)

        next_name = _normalize_name(changes["name"]) if "name" in changes else service.name
        next_description = (
            _normalize_description(changes["description"])
            if "description" in changes
            else service.description
        )
        next_booking = (
            _normalize_bool(changes["appointment_booking_enabled"], "appointment_booking_enabled")
            if "appointment_booking_enabled" in changes
            else service.appointment_booking_enabled
        )
        next_duration, next_cutoff, next_requirement = _normalize_booking_settings(
            booking_enabled=next_booking,
            duration=(
                _normalize_duration(changes["default_appointment_duration_minutes"])
                if "default_appointment_duration_minutes" in changes
                else service.default_appointment_duration_minutes
            ),
            cutoff=(
                _normalize_cancellation_cutoff(changes["cancellation_cutoff_minutes"])
                if "cancellation_cutoff_minutes" in changes
                else service.cancellation_cutoff_minutes
            ),
            requires_inventory=(
                _normalize_bool(changes["requires_current_inventory"], "requires_current_inventory")
                if "requires_current_inventory" in changes
                else service.requires_current_inventory
            ),
            explicit=frozenset(field for field in APPOINTMENT_SETTING_FIELDS if field in changes),
        )
        next_modes = (
            _normalize_modes(changes["delivery_modes"])
            if "delivery_modes" in changes
            else current.delivery_modes
        )
        next_coverage = (
            _normalize_coverage(changes["provider_coverage"])
            if "provider_coverage" in changes
            else service.provider_coverage
        )
        next_selected = _normalize_selection(
            coverage=next_coverage,
            selected=(
                _normalize_counselor_ids(changes["selected_counselor_ids"])
                if "selected_counselor_ids" in changes
                else current.selected_counselor_ids
            ),
            explicit="selected_counselor_ids" in changes,
        )
        _validate_new_selections(added=next_selected - current.selected_counselor_ids)

        proposed = _ServiceConfiguration(
            name=next_name,
            appointment_booking_enabled=next_booking,
            default_appointment_duration_minutes=next_duration,
            cancellation_cutoff_minutes=next_cutoff,
            requires_current_inventory=next_requirement,
            delivery_modes=next_modes,
            provider_coverage=next_coverage,
            selected_counselor_ids=next_selected,
        )
        if service.is_active:
            _validate_active_configuration(proposed)

        scalar_values = {
            "name": next_name,
            "description": next_description,
            "appointment_booking_enabled": next_booking,
            "default_appointment_duration_minutes": next_duration,
            "cancellation_cutoff_minutes": next_cutoff,
            "requires_current_inventory": next_requirement,
            "provider_coverage": next_coverage,
        }
        changed_fields = [
            field for field, value in scalar_values.items() if getattr(service, field) != value
        ]
        if current.delivery_modes != next_modes:
            changed_fields.append("delivery_modes")
        if current.selected_counselor_ids != next_selected:
            changed_fields.append("selected_counselor_ids")
        if not changed_fields:
            return get_service(service.pk)

        consequences = _scheduling_consequences(
            service=service, current=current, proposed=proposed, now=current_time
        )
        _require_review(consequences, acknowledge_scheduling_consequences)

        scalar_changed = [field for field in changed_fields if field in scalar_values]
        for field in scalar_changed:
            setattr(service, field, scalar_values[field])
        if scalar_changed:
            service.save(update_fields=[*scalar_changed, "updated_at"])
        if current.delivery_modes != next_modes:
            ServiceDeliveryMode.objects.filter(service=service).delete()
            ServiceDeliveryMode.objects.bulk_create(
                [ServiceDeliveryMode(service=service, mode=mode) for mode in sorted(next_modes)]
            )
        if current.selected_counselor_ids != next_selected:
            _replace_selection(service, next_selected)
        record_event(
            context=context,
            action=SERVICE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.service",
            target_id=service.pk,
            metadata={"changed_fields": changed_fields, **_consequence_metadata(consequences)},
        )
    return get_service(service.pk)


def set_service_active(
    *,
    service_id: UUID,
    is_active: bool,
    context: AuditContext,
    acknowledge_scheduling_consequences: bool = False,
    now: datetime | None = None,
) -> Service:
    """Enable or disable a Service. Disabling stops new work and never cancels Appointments."""

    current_time = now or timezone.now()
    with transaction.atomic():
        service = Service.objects.select_for_update().filter(pk=service_id).first()
        if service is None:
            raise ServiceCatalogNotFound("The requested Service was not found.")
        if service.code == COUNSELING_SERVICE_CODE and not is_active:
            raise CanonicalServiceRequired(
                "The canonical Counseling Service is required by COMPASS and cannot be disabled."
            )
        if service.is_active == is_active:
            return get_service(service.pk)
        consequences = _ServiceSchedulingConsequences(False, False, False)
        if is_active:
            _validate_active_configuration(_current_configuration(service))
        else:
            from compass.appointments.models import Appointment, AppointmentStatus

            consequences = _ServiceSchedulingConsequences(
                existing_appointment_dependency_detected=Appointment.objects.filter(
                    service_id=service.pk,
                    status=AppointmentStatus.SCHEDULED,
                    starts_at__gt=current_time,
                ).exists(),
                provider_dependency_detected=False,
                counseling_online_enabled=False,
            )
            _require_review(consequences, acknowledge_scheduling_consequences)
        service.is_active = is_active
        service.save(update_fields=["is_active", "updated_at"])
        record_event(
            context=context,
            action=SERVICE_ENABLED if is_active else SERVICE_DISABLED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.catalog.service",
            target_id=service.pk,
            metadata=_consequence_metadata(consequences),
        )
    return get_service(service.pk)
