"""Explicit synchronization and read-only readiness for required Service configuration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from compass.accounts.models import Role
from compass.audit.actions import SERVICE_CREATED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import (
    MAX_SERVICE_DURATION_MINUTES,
    MIN_SERVICE_DURATION_MINUTES,
    DeliveryMode,
    Service,
    ServiceDeliveryMode,
    ServiceProviderCoverage,
)
from compass.service_catalog.services import (
    InvalidServiceCatalogInput,
    ServiceActivationBlocker,
    ServiceCatalogConflict,
    _current_configuration,
    _validate_active_configuration,
    activation_blockers,
    set_service_active,
    update_service,
)

COUNSELING_NAME = "Counseling"
COUNSELING_DURATION_MINUTES = 60
COUNSELING_CANCELLATION_CUTOFF_MINUTES = 30


class CanonicalIdentityPolicyMissing(RuntimeError):
    """Canonical provider identity must be synchronized before Service bootstrap."""


@dataclass(frozen=True, slots=True)
class CanonicalServiceSyncResult:
    service_id: UUID
    outcome: str


def canonical_counseling_readiness() -> tuple[bool, str]:
    """Inspect required configuration without changing it or checking optional dependencies."""
    service = Service.objects.filter(code=COUNSELING_SERVICE_CODE).first()
    if service is None:
        return False, "missing"
    if not service.is_active:
        return False, "inactive"
    configuration = _current_configuration(service)
    if not configuration.delivery_modes or not configuration.delivery_modes <= set(
        DeliveryMode.values
    ):
        return False, "delivery_modes_invalid"
    if ServiceActivationBlocker.SELECTED_COUNSELORS_MISSING in activation_blockers(service):
        return False, "selected_counselors_missing"
    try:
        _validate_active_configuration(configuration)
    except (InvalidServiceCatalogInput, ServiceCatalogConflict):
        return False, "active_configuration_invalid"
    return True, "ok"


@transaction.atomic
def sync_canonical_services() -> CanonicalServiceSyncResult:
    """Create or reconcile COUNSELING after identity policy sync.

    Locking the canonical Role serializes concurrent sync commands, including the
    absent-Service case where there is no Service row to lock yet. Valid operator configuration,
    including selected-Counselor coverage and enabled ONLINE delivery, is preserved; only
    structural drift is repaired (ADR-089).
    """
    counselor = Role.objects.select_for_update().filter(code="COUNSELOR").first()
    if counselor is None:
        raise CanonicalIdentityPolicyMissing(
            "COUNSELOR role is missing. Run sync_identity_policy before sync_canonical_services."
        )

    service = Service.objects.select_for_update().filter(code=COUNSELING_SERVICE_CODE).first()
    if service is None:
        # The unique code also protects against a writer that does not use the Role lock.
        try:
            with transaction.atomic():
                service = Service.objects.create(
                    code=COUNSELING_SERVICE_CODE,
                    name=COUNSELING_NAME,
                    appointment_booking_enabled=True,
                    default_appointment_duration_minutes=COUNSELING_DURATION_MINUTES,
                    cancellation_cutoff_minutes=COUNSELING_CANCELLATION_CUTOFF_MINUTES,
                    requires_current_inventory=False,
                    provider_coverage=ServiceProviderCoverage.ALL_COUNSELORS,
                    is_active=True,
                )
        except IntegrityError:
            service = Service.objects.select_for_update().get(code=COUNSELING_SERVICE_CODE)
        else:
            ServiceDeliveryMode.objects.create(service=service, mode=DeliveryMode.IN_PERSON)
            _validate_active_configuration(_current_configuration(service))
            record_event(
                context=AuditContext.system(),
                action=SERVICE_CREATED,
                outcome=AuditOutcome.SUCCESS,
                target_type="service.catalog.service",
                target_id=service.pk,
                metadata={"code": COUNSELING_SERVICE_CODE},
            )
            return CanonicalServiceSyncResult(service.pk, "created")

    changes: dict[str, object] = {}
    if (
        not isinstance(service.name, str)
        or not service.name.strip()
        or len(service.name.strip()) > 160
    ):
        changes["name"] = COUNSELING_NAME

    duration = service.default_appointment_duration_minutes
    if service.appointment_booking_enabled and (
        duration is None
        or not MIN_SERVICE_DURATION_MINUTES <= duration <= MAX_SERVICE_DURATION_MINUTES
    ):
        changes["default_appointment_duration_minutes"] = COUNSELING_DURATION_MINUTES

    configuration = _current_configuration(service)
    valid_modes = configuration.delivery_modes & set(DeliveryMode.values)
    if not valid_modes:
        valid_modes = frozenset({DeliveryMode.IN_PERSON})
    if configuration.delivery_modes != valid_modes:
        changes["delivery_modes"] = sorted(valid_modes)

    # Provider coverage is an institutional choice: sync never widens or rewrites it. A selection
    # left without an active Counselor is reported below for an operator to correct.

    context = AuditContext.system()
    was_inactive = not service.is_active
    if changes:
        # Repairs restore validity for new work; existing Appointments keep their provenance.
        service = update_service(
            service_id=service.pk,
            changes=changes,
            context=context,
            acknowledge_scheduling_consequences=True,
        )
    if not service.is_active:
        service = set_service_active(service_id=service.pk, is_active=True, context=context)
    valid, reason = canonical_counseling_readiness()
    if not valid:
        raise ServiceCatalogConflict(
            f"Canonical Counseling configuration remains invalid: {reason}."
        )
    return CanonicalServiceSyncResult(
        service.pk, "updated" if changes or was_inactive else "unchanged"
    )
