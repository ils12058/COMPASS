"""Source-controlled operator command reference for COMPASS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommandCategory(StrEnum):
    BOOTSTRAP = "BOOTSTRAP"
    DEPLOYMENT = "DEPLOYMENT"
    DIAGNOSTIC = "DIAGNOSTIC"


@dataclass(frozen=True, slots=True)
class CommandCatalogEntry:
    code: str
    category: CommandCategory
    display_name: str
    purpose: str
    invocation: str
    mutates_state: bool
    notes: str


COMMAND_CATALOG = (
    CommandCatalogEntry(
        code="create_it_admin",
        category=CommandCategory.BOOTSTRAP,
        display_name="Create initial IT Administrator",
        purpose="Create the first COMPASS IT Administrator without Django superuser semantics.",
        invocation=(
            "python manage.py create_it_admin --email <operator-email> "
            "--first-name <first-name> --last-name <last-name>"
        ),
        mutates_state=True,
        notes="Requires the canonical IT_ADMIN role to be synchronized. Credentials are not shown.",
    ),
    CommandCatalogEntry(
        code="sync_identity_policy",
        category=CommandCategory.DEPLOYMENT,
        display_name="Synchronize identity policy",
        purpose="Synchronize code-owned roles, designations, capabilities, and baseline grants.",
        invocation="python manage.py sync_identity_policy",
        mutates_state=True,
        notes="Idempotent in normal use; run during controlled deployment.",
    ),
    CommandCatalogEntry(
        code="migrate",
        category=CommandCategory.DEPLOYMENT,
        display_name="Apply database migrations",
        purpose="Apply committed Django database migrations during controlled deployment.",
        invocation="python manage.py migrate --noinput",
        mutates_state=True,
        notes="Run from an authorized deployment environment, never from the browser.",
    ),
    CommandCatalogEntry(
        code="check_deploy",
        category=CommandCategory.DEPLOYMENT,
        display_name="Run Django deployment checks",
        purpose="Evaluate Django deployment checks against the resolved configuration.",
        invocation="python manage.py check --deploy",
        mutates_state=False,
        notes="Read-only validation; startup configuration must already be loadable.",
    ),
    CommandCatalogEntry(
        code="export_openapi_check",
        category=CommandCategory.DEPLOYMENT,
        display_name="Validate OpenAPI contract",
        purpose="Verify the committed deterministic OpenAPI artifact matches the generated schema.",
        invocation="python manage.py export_openapi --check",
        mutates_state=False,
        notes="Read-only contract validation.",
    ),
    CommandCatalogEntry(
        code="compass_doctor",
        category=CommandCategory.DIAGNOSTIC,
        display_name="Run COMPASS diagnostics",
        purpose="Evaluate safe configuration posture and passive runtime dependency checks.",
        invocation="python manage.py compass_doctor",
        mutates_state=False,
        notes="Does not perform worker execution unless --worker-smoke is explicitly supplied.",
    ),
    CommandCatalogEntry(
        code="compass_doctor_configuration",
        category=CommandCategory.DIAGNOSTIC,
        display_name="Run configuration-only diagnostics",
        purpose="Inspect safe resolved configuration posture without runtime network probes.",
        invocation="python manage.py compass_doctor --configuration-only",
        mutates_state=False,
        notes="Django settings must already have loaded successfully.",
    ),
    CommandCatalogEntry(
        code="compass_doctor_worker_smoke",
        category=CommandCategory.DIAGNOSTIC,
        display_name="Run Celery worker smoke check",
        purpose="Verify broker, worker execution, and result retrieval with a harmless task.",
        invocation="python manage.py compass_doctor --worker-smoke",
        mutates_state=False,
        notes="Sends only the existing compass.infrastructure.noop diagnostic Celery task.",
    ),
)


__all__ = ["COMMAND_CATALOG", "CommandCatalogEntry", "CommandCategory"]
