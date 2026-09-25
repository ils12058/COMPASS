"""Construct preexisting Counseling rows for domain regression scenarios.

Normal Catalog creation reserves COUNSELING. These fixtures intentionally bypass that
boundary to model historical/manual rows and invalid configuration drift.
"""

from compass.accounts.models import Role
from compass.audit.actions import SERVICE_CREATED
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.models import Service, ServiceDeliveryMode, ServiceProviderRole
from compass.service_catalog.services import get_service


def legacy_counseling_service(
    *,
    code: str,
    name: str,
    appointment_policy: str,
    context,
    description: str = "",
    default_duration_minutes: int | None = None,
    cancellation_cutoff_minutes: int | None = None,
    requires_current_inventory: bool = False,
    delivery_modes=None,
    provider_roles=None,
):
    assert code == "COUNSELING"
    service = Service.objects.create(
        code=code,
        name=name,
        description=description,
        appointment_policy=appointment_policy,
        default_duration_minutes=default_duration_minutes,
        cancellation_cutoff_minutes=cancellation_cutoff_minutes,
        requires_current_inventory=requires_current_inventory,
    )
    ServiceDeliveryMode.objects.bulk_create(
        [ServiceDeliveryMode(service=service, mode=mode) for mode in delivery_modes or []]
    )
    ServiceProviderRole.objects.bulk_create(
        [
            ServiceProviderRole(service=service, role=Role.objects.get(code=role_code))
            for role_code in provider_roles or []
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
