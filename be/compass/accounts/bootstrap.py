"""Explicit synchronization of the version-controlled identity policy into PostgreSQL."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from django.db import transaction

from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    UserCapabilityOverride,
)
from compass.accounts.policy import (
    CAPABILITY_DEFINITIONS,
    DESIGNATION_CAPABILITY_GRANTS,
    DESIGNATION_DEFINITIONS,
    ROLE_CAPABILITY_GRANTS,
    ROLE_DEFINITIONS,
)
from compass.audit.actions import IDENTITY_POLICY_SYNCED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

RENAMED_LEGACY_CAPABILITY_CODES = ("organization.view", "services.view")
RETIRED_CAPABILITY_CODES = (
    "institutional_forms.manage",
    "document_branding.view",
    "document_branding.manage",
)


class IdentityPolicySyncError(RuntimeError):
    """Persisted identity state cannot be reconciled until an operator acts."""


@dataclass(frozen=True, slots=True)
class IdentityPolicySyncResult:
    roles_created: int = 0
    roles_updated: int = 0
    designations_created: int = 0
    designations_updated: int = 0
    capabilities_created: int = 0
    capabilities_updated: int = 0
    role_grants_created: int = 0
    designation_grants_created: int = 0
    retired_role_grants_deleted: int = 0
    retired_designation_grants_deleted: int = 0
    retired_overrides_deleted: int = 0
    retired_capabilities_deleted: int = 0

    @property
    def changed(self) -> bool:
        return any(asdict(self).values())

    def metadata(self) -> dict[str, int]:
        return asdict(self)


def _sync_definition(model, definition) -> tuple[object, str]:
    defaults = {
        "name": definition.name,
        "description": definition.description,
    }
    obj, created = model.objects.get_or_create(code=definition.code, defaults=defaults)
    if created:
        return obj, "created"

    changed_fields = [
        field_name for field_name, value in defaults.items() if getattr(obj, field_name) != value
    ]
    if changed_fields:
        for field_name in changed_fields:
            setattr(obj, field_name, defaults[field_name])
        obj.save(update_fields=changed_fields)
        return obj, "updated"
    return obj, "unchanged"


def sync_identity_policy() -> IdentityPolicySyncResult:
    """Reconcile canonical roles, designations, capabilities, and baseline grants.

    Unknown database rows are retained; only retired capability state is removed.
    """

    counts = {field_name: 0 for field_name in IdentityPolicySyncResult.__dataclass_fields__}

    with transaction.atomic():
        if Capability.objects.filter(code__in=RENAMED_LEGACY_CAPABILITY_CODES).exists():
            raise IdentityPolicySyncError(
                "Legacy capability rows remain. Run accounts migration "
                "0006_rename_reference_capabilities before sync_identity_policy."
            )
        counts["retired_role_grants_deleted"] = RoleCapability.objects.filter(
            capability__code__in=RETIRED_CAPABILITY_CODES
        ).count()
        RoleCapability.objects.filter(capability__code__in=RETIRED_CAPABILITY_CODES).delete()
        counts["retired_designation_grants_deleted"] = DesignationCapability.objects.filter(
            capability__code__in=RETIRED_CAPABILITY_CODES
        ).count()
        DesignationCapability.objects.filter(capability__code__in=RETIRED_CAPABILITY_CODES).delete()
        counts["retired_overrides_deleted"] = UserCapabilityOverride.objects.filter(
            capability__code__in=RETIRED_CAPABILITY_CODES
        ).count()
        UserCapabilityOverride.objects.filter(
            capability__code__in=RETIRED_CAPABILITY_CODES
        ).delete()
        counts["retired_capabilities_deleted"] = Capability.objects.filter(
            code__in=RETIRED_CAPABILITY_CODES
        ).count()
        Capability.objects.filter(code__in=RETIRED_CAPABILITY_CODES).delete()

        roles = {}
        for definition in ROLE_DEFINITIONS:
            role, result = _sync_definition(Role, definition)
            roles[definition.code] = role
            if result == "created":
                counts["roles_created"] += 1
            elif result == "updated":
                counts["roles_updated"] += 1

        designations = {}
        for definition in DESIGNATION_DEFINITIONS:
            designation, result = _sync_definition(Designation, definition)
            designations[definition.code] = designation
            if result == "created":
                counts["designations_created"] += 1
            elif result == "updated":
                counts["designations_updated"] += 1

        capabilities = {}
        for definition in CAPABILITY_DEFINITIONS:
            capability, result = _sync_definition(Capability, definition)
            capabilities[definition.code] = capability
            if result == "created":
                counts["capabilities_created"] += 1
            elif result == "updated":
                counts["capabilities_updated"] += 1

        for role_code, capability_codes in ROLE_CAPABILITY_GRANTS.items():
            for capability_code in capability_codes:
                _grant, created = RoleCapability.objects.get_or_create(
                    role=roles[role_code],
                    capability=capabilities[capability_code],
                )
                if created:
                    counts["role_grants_created"] += 1

        for designation_code, capability_codes in DESIGNATION_CAPABILITY_GRANTS.items():
            for capability_code in capability_codes:
                _grant, created = DesignationCapability.objects.get_or_create(
                    designation=designations[designation_code],
                    capability=capabilities[capability_code],
                )
                if created:
                    counts["designation_grants_created"] += 1

        result = IdentityPolicySyncResult(**counts)
        if result.changed:
            record_event(
                context=AuditContext.system(),
                action=IDENTITY_POLICY_SYNCED,
                outcome=AuditOutcome.SUCCESS,
                metadata=result.metadata(),
            )
    return result


__all__ = [
    "IdentityPolicySyncError",
    "IdentityPolicySyncResult",
    "RENAMED_LEGACY_CAPABILITY_CODES",
    "RETIRED_CAPABILITY_CODES",
    "sync_identity_policy",
]
