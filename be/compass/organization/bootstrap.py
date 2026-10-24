"""Explicit seed/adoption only. The persisted catalog is the live authority."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.loader import MigrationLoader

from compass.audit.actions import ORGANIZATION_CATALOG_ADOPTED, ORGANIZATION_CATALOG_INITIALIZED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.canonical import BASELINE_VERSION, CANONICAL_CAMPUSES
from compass.organization.models import Campus, CatalogInitialization, College, Program
from compass.organization.program_policy import validate_program_policy

CATALOG_MIGRATION = ("organization", "0002_program_policy_and_catalog_initialization")
# Cooperative initialization lock; not a fence against old binaries or privileged SQL.
CATALOG_INITIALIZATION_LOCK = 477580715031


class CatalogInitializationError(RuntimeError):
    pass


# Compatibility for old importers, without the old reconciliation implementation.
CanonicalOrganizationSyncError = CatalogInitializationError


@dataclass(frozen=True, slots=True)
class CatalogInitializationResult:
    receipt: CatalogInitialization
    changed: bool = False
    campuses_created: int = 0
    colleges_created: int = 0
    programs_created: int = 0

    def metadata(self):
        return {
            "source": self.receipt.source,
            "baseline_version": self.receipt.baseline_version,
            "campuses_created": self.campuses_created,
            "colleges_created": self.colleges_created,
            "programs_created": self.programs_created,
        }


def require_catalog_schema() -> None:
    """Reject old/incomplete/unknown Organization migration graphs before bootstrap writes."""
    loader = MigrationLoader(connection)
    loader.check_consistent_history(connection)
    applied = set(loader.applied_migrations)
    if (
        CATALOG_MIGRATION not in applied
        or any(key[0] == "organization" and key not in loader.disk_migrations for key in applied)
        or any(leaf not in applied for leaf in loader.graph.leaf_nodes("organization"))
    ):
        raise CatalogInitializationError(
            "Organization schema is incompatible; apply the reviewed catalog migrations with a "
            "compatible release before initialization/adoption."
        )


def check_organization_catalog() -> CatalogInitializationResult:
    require_catalog_schema()
    receipt = CatalogInitialization.objects.filter(pk=1).first()
    if receipt is None:
        raise CatalogInitializationError(
            "Catalog is not initialized. Explicitly seed an empty catalog or adopt existing data."
        )
    # A previously initialized empty catalog is deliberate history, never a reseed trigger.
    return CatalogInitializationResult(receipt)


def initialize_organization_catalog(
    *, action: str, reference: str = "", allow_empty_adoption: bool = False
) -> CatalogInitializationResult:
    if action not in {"seed", "adopt", "check"}:
        raise CatalogInitializationError("Choose seed, adopt or check explicitly.")
    if (
        not isinstance(reference, str)
        or len(reference) > 160
        or any(ord(c) < 32 or ord(c) == 127 for c in reference)
    ):
        raise CatalogInitializationError("Initialization reference must be bounded plain text.")
    if allow_empty_adoption and action != "adopt":
        raise CatalogInitializationError("Empty adoption is only available for explicit adoption.")
    try:
        with transaction.atomic():
            require_catalog_schema()
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CATALOG_INITIALIZATION_LOCK])
            receipt = CatalogInitialization.objects.filter(pk=1).first()
            if receipt is not None:
                return CatalogInitializationResult(receipt)
            if action == "check":
                raise CatalogInitializationError("Catalog has no initialization/adoption receipt.")
            populated = (
                Campus.objects.exists() or College.objects.exists() or Program.objects.exists()
            )
            if action == "seed" and populated:
                raise CatalogInitializationError(
                    "Refusing seed: catalog contains existing data. Use explicit adoption; no "
                    "existing rows will be reconciled or topped up."
                )
            if action == "adopt" and not populated and not allow_empty_adoption:
                raise CatalogInitializationError("Empty adoption requires --allow-empty-adoption.")
            campuses = colleges = programs = 0
            if action == "seed":
                for c in CANONICAL_CAMPUSES:
                    campus = Campus.objects.create(code=c.code, name=c.name, is_active=c.active)
                    campuses += 1
                    for k in c.colleges:
                        college = College.objects.create(
                            campus=campus, code=k.code, name=k.name, is_active=k.active
                        )
                        colleges += 1
                        for p in k.programs:
                            validate_program_policy(
                                p.academic_classification,
                                p.year_level_policy_status,
                                p.applicable_year_levels,
                            )
                            Program.objects.create(
                                college=college,
                                code=p.code,
                                name=p.name,
                                is_active=p.active,
                                academic_classification=p.academic_classification,
                                year_level_policy_status=p.year_level_policy_status,
                                applicable_year_levels=p.applicable_year_levels,
                            )
                            programs += 1
            receipt = CatalogInitialization.objects.create(
                source="SEEDED" if action == "seed" else "ADOPTED",
                baseline_version=BASELINE_VERSION if action == "seed" else None,
                reference=reference.strip(),
            )
            result = CatalogInitializationResult(receipt, True, campuses, colleges, programs)
            record_event(
                context=AuditContext.system(),
                action=ORGANIZATION_CATALOG_INITIALIZED
                if action == "seed"
                else ORGANIZATION_CATALOG_ADOPTED,
                outcome=AuditOutcome.SUCCESS,
                target_type="organization.cataloginitialization",
                target_id=1,
                metadata={**result.metadata(), "reference": receipt.reference},
            )
            return result
    except (DatabaseError, ValidationError) as exc:
        raise CatalogInitializationError(
            "Catalog initialization failed atomically; inspect the synthetic/reviewed environment "
            "before retrying. No reconciliation fallback is available."
        ) from exc


def sync_organization_catalog() -> CatalogInitializationResult:
    """Deprecated seed-only fixture/CLI alias. Populated catalogs require explicit adoption."""
    return initialize_organization_catalog(action="seed")
