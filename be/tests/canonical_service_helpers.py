"""Construct preexisting Counseling rows for domain regression scenarios.

Normal Catalog creation reserves COUNSELING. These fixtures intentionally bypass that
boundary to model historical/manual rows and invalid configuration drift.
"""

from compass.audit.actions import SERVICE_CREATED
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.models import (
    Service,
    ServiceCounselorProvider,
    ServiceDeliveryMode,
    ServiceProviderCoverage,
)
from compass.service_catalog.services import get_service


def legacy_counseling_service(
    *,
    code: str,
    name: str,
    appointment_booking_enabled: bool,
    context,
    description: str = "",
    default_appointment_duration_minutes: int | None = None,
    cancellation_cutoff_minutes: int | None = None,
    requires_current_inventory: bool = False,
    delivery_modes=None,
    provider_coverage: str = ServiceProviderCoverage.ALL_COUNSELORS,
    selected_counselors=(),
):
    assert code == "COUNSELING"
    service = Service.objects.create(
        code=code,
        name=name,
        description=description,
        appointment_booking_enabled=appointment_booking_enabled,
        default_appointment_duration_minutes=default_appointment_duration_minutes,
        cancellation_cutoff_minutes=cancellation_cutoff_minutes,
        requires_current_inventory=requires_current_inventory,
        provider_coverage=provider_coverage,
    )
    ServiceDeliveryMode.objects.bulk_create(
        [ServiceDeliveryMode(service=service, mode=mode) for mode in delivery_modes or []]
    )
    ServiceCounselorProvider.objects.bulk_create(
        [
            ServiceCounselorProvider(service=service, counselor=counselor)
            for counselor in selected_counselors
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
