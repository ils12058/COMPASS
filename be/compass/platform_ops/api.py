"""Capability-authorized read-only Platform Operations API."""

from __future__ import annotations

from datetime import datetime

from ninja import Router, Schema

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .catalog import COMMAND_CATALOG, CommandCategory
from .diagnostics import (
    DiagnosticStatus,
    collect_environment_diagnostics,
    collect_platform_health,
)

router = Router(tags=["platform-operations"])


class HealthCheckResponse(Schema):
    code: str
    label: str
    status: DiagnosticStatus
    summary: str


class PlatformHealthResponse(Schema):
    status: DiagnosticStatus
    timestamp: datetime
    summary: str
    checks: list[HealthCheckResponse]


class EnvironmentValueResponse(Schema):
    code: str
    label: str
    value: bool | int | str


class EnvironmentCategoryResponse(Schema):
    code: str
    label: str
    values: list[EnvironmentValueResponse]


class PlatformEnvironmentResponse(Schema):
    timestamp: datetime
    startup_limitation: str
    categories: list[EnvironmentCategoryResponse]


class CommandCatalogEntryResponse(Schema):
    code: str
    category: CommandCategory
    display_name: str
    purpose: str
    invocation: str
    mutates_state: bool
    notes: str


class CommandCatalogResponse(Schema):
    execution_supported: bool
    commands: list[CommandCatalogEntryResponse]


def _require_viewer(request) -> None:
    actor = request.auth_user
    if not actor.is_active or not actor.has_capability("platform_operations.view"):
        raise APIError(
            403,
            "permission_denied",
            "The platform_operations.view capability is required.",
        )


@router.get(
    "/health",
    response=response_with_errors(PlatformHealthResponse, 401, 403),
    auth=session_auth,
    operation_id="platformOperationsHealth",
    summary="Inspect safe platform dependency health",
)
def platform_health(request):
    _require_viewer(request)
    health = collect_platform_health()
    return PlatformHealthResponse(
        status=health.status,
        timestamp=health.timestamp,
        summary=health.summary,
        checks=[
            HealthCheckResponse(
                code=item.code,
                label=item.label,
                status=item.status,
                summary=item.summary,
            )
            for item in health.checks
        ],
    )


@router.get(
    "/environment",
    response=response_with_errors(PlatformEnvironmentResponse, 401, 403),
    auth=session_auth,
    operation_id="platformOperationsEnvironment",
    summary="Inspect safe resolved platform configuration",
)
def platform_environment(request):
    _require_viewer(request)
    environment = collect_environment_diagnostics()
    return PlatformEnvironmentResponse(
        timestamp=environment.timestamp,
        startup_limitation=environment.startup_limitation,
        categories=[
            EnvironmentCategoryResponse(
                code=category.code,
                label=category.label,
                values=[
                    EnvironmentValueResponse(
                        code=value.code,
                        label=value.label,
                        value=value.value,
                    )
                    for value in category.values
                ],
            )
            for category in environment.categories
        ],
    )


@router.get(
    "/commands",
    response=response_with_errors(CommandCatalogResponse, 401, 403),
    auth=session_auth,
    operation_id="platformOperationsCommandCatalog",
    summary="List approved operator command guidance",
)
def platform_command_catalog(request):
    _require_viewer(request)
    return CommandCatalogResponse(
        execution_supported=False,
        commands=[
            CommandCatalogEntryResponse(
                code=item.code,
                category=item.category,
                display_name=item.display_name,
                purpose=item.purpose,
                invocation=item.invocation,
                mutates_state=item.mutates_state,
                notes=item.notes,
            )
            for item in COMMAND_CATALOG
        ],
    )


__all__ = ["router"]
