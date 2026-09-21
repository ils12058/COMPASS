"""Capability-authorized COMPASS Platform Operations API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .activity import (
    DEFAULT_PAGE_SIZE as ACTIVITY_DEFAULT_PAGE_SIZE,
)
from .activity import (
    TechnicalActivityPaginationError,
    list_technical_activity,
)
from .catalog import COMMAND_CATALOG, CommandCategory
from .diagnostics import (
    DiagnosticStatus,
    collect_environment_diagnostics,
    collect_platform_health,
)
from .email_operations import (
    DEFAULT_PAGE_SIZE as EMAIL_DEFAULT_PAGE_SIZE,
)
from .email_operations import (
    EmailDeliveryNotFound,
    EmailDeliveryNotRetryable,
    EmailDeliveryOperationsError,
    EmailDeliveryPaginationError,
    get_email_delivery_summary,
    list_email_deliveries,
    retry_email_delivery,
)
from .services import (
    InvalidMaintenanceWindow,
    MaintenanceAlreadyEnabled,
    MaintenanceError,
    MaintenanceNotEnabled,
    MaintenanceScheduleConflict,
    MaintenanceScheduleNotFound,
    MaintenanceSnapshot,
    cancel_maintenance_schedule,
    disable_manual_maintenance,
    enable_manual_maintenance,
    get_maintenance_snapshot,
    schedule_maintenance,
)

router = Router(tags=["platform-operations"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class HealthCheckResponse(StrictSchema):
    code: str
    label: str
    status: DiagnosticStatus
    summary: str


class PlatformHealthResponse(StrictSchema):
    status: DiagnosticStatus
    timestamp: datetime
    summary: str
    checks: list[HealthCheckResponse]


class EnvironmentValueResponse(StrictSchema):
    code: str
    label: str
    value: bool | int | str | None


class EnvironmentCategoryResponse(StrictSchema):
    code: str
    label: str
    values: list[EnvironmentValueResponse]


class PlatformEnvironmentResponse(StrictSchema):
    timestamp: datetime
    startup_limitation: str
    categories: list[EnvironmentCategoryResponse]


class CommandCatalogEntryResponse(StrictSchema):
    code: str
    category: CommandCategory
    display_name: str
    purpose: str
    invocation: str
    mutates_state: bool
    notes: str


class CommandCatalogResponse(StrictSchema):
    execution_supported: bool
    commands: list[CommandCatalogEntryResponse]


class PublicPlatformStatus(StrEnum):
    OPERATIONAL = "operational"
    MAINTENANCE_SCHEDULED = "maintenance_scheduled"
    MAINTENANCE_ACTIVE = "maintenance_active"


class PlatformPublicStatusResponse(StrictSchema):
    status: PublicPlatformStatus
    message: str | None
    starts_at: datetime | None
    ends_at: datetime | None


class MaintenanceResponse(StrictSchema):
    state: str
    source: str
    message: str
    manual_expected_end_at: datetime | None
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    schedule_upcoming: bool
    schedule_active: bool


class MaintenanceEnableRequest(StrictSchema):
    message: str
    expected_end_at: datetime | None = None


class MaintenanceScheduleRequest(StrictSchema):
    message: str
    starts_at: datetime
    ends_at: datetime


class EmailDeliverySummaryResponse(StrictSchema):
    pending_count: int
    processing_count: int
    failed_count: int
    cancelled_count: int
    sent_today: int
    oldest_pending_at: datetime | None
    due_pending_count: int


class EmailDeliveryItemResponse(StrictSchema):
    id: UUID
    event_code: str
    status: str
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    sent_at: datetime | None
    failure_code: str


class EmailDeliveryPageResponse(StrictSchema):
    items: list[EmailDeliveryItemResponse]
    page: int
    page_size: int
    has_next: bool


class TechnicalActivityItemResponse(StrictSchema):
    id: UUID
    type: str
    title: str
    description: str
    occurred_at: datetime
    actor_type: str
    actor_display_name: str | None


class TechnicalActivityPageResponse(StrictSchema):
    items: list[TechnicalActivityItemResponse]
    page: int
    page_size: int
    has_next: bool


def _require(request, capability: str, *, recent_mfa: bool = False) -> None:
    actor = request.auth_user
    if not actor.is_active or not actor.has_capability(capability):
        raise APIError(403, "permission_denied", f"The {capability} capability is required.")
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _maintenance_view(snapshot: MaintenanceSnapshot) -> MaintenanceResponse:
    return MaintenanceResponse(
        state=snapshot.state.value,
        source=snapshot.source.value,
        message=snapshot.message,
        manual_expected_end_at=snapshot.manual_expected_end_at,
        scheduled_start_at=snapshot.scheduled_start_at,
        scheduled_end_at=snapshot.scheduled_end_at,
        schedule_upcoming=snapshot.schedule_upcoming,
        schedule_active=snapshot.schedule_active,
    )


def _raise_maintenance_error(exc: MaintenanceError) -> NoReturn:
    if isinstance(exc, MaintenanceAlreadyEnabled):
        raise APIError(409, "maintenance_already_enabled", str(exc)) from exc
    if isinstance(exc, MaintenanceNotEnabled):
        raise APIError(409, "maintenance_not_enabled", str(exc)) from exc
    if isinstance(exc, MaintenanceScheduleConflict):
        raise APIError(409, "maintenance_schedule_conflict", str(exc)) from exc
    if isinstance(exc, MaintenanceScheduleNotFound):
        raise APIError(404, "maintenance_schedule_not_found", str(exc)) from exc
    if isinstance(exc, InvalidMaintenanceWindow):
        raise APIError(422, "invalid_maintenance_window", str(exc)) from exc
    raise APIError(500, "internal_error", "The Maintenance Mode operation failed.") from exc


def _raise_email_error(exc: EmailDeliveryOperationsError) -> NoReturn:
    if isinstance(exc, EmailDeliveryNotFound):
        raise APIError(404, "email_delivery_not_found", str(exc)) from exc
    if isinstance(exc, EmailDeliveryNotRetryable):
        raise APIError(409, "email_delivery_not_retryable", str(exc)) from exc
    if isinstance(exc, EmailDeliveryPaginationError):
        raise APIError(422, "invalid_email_delivery_request", str(exc)) from exc
    raise APIError(500, "internal_error", "The EmailDelivery operation failed.") from exc


@router.get(
    "/status",
    response=PlatformPublicStatusResponse,
    operation_id="platformPublicStatus",
    summary="Read public COMPASS service status",
)
def platform_public_status(request):
    snapshot = get_maintenance_snapshot()

    if snapshot.state == "NORMAL":
        return PlatformPublicStatusResponse(
            status=PublicPlatformStatus.OPERATIONAL,
            message=None,
            starts_at=None,
            ends_at=None,
        )

    if snapshot.state == "SCHEDULED":
        return PlatformPublicStatusResponse(
            status=PublicPlatformStatus.MAINTENANCE_SCHEDULED,
            message=snapshot.message,
            starts_at=snapshot.scheduled_start_at,
            ends_at=snapshot.scheduled_end_at,
        )

    return PlatformPublicStatusResponse(
        status=PublicPlatformStatus.MAINTENANCE_ACTIVE,
        message=snapshot.message,
        starts_at=(
            snapshot.scheduled_start_at
            if snapshot.source == "SCHEDULED"
            else None
        ),
        ends_at=(
            snapshot.scheduled_end_at
            if snapshot.source == "SCHEDULED"
            else snapshot.manual_expected_end_at
        ),
    )


@router.get(
    "/health",
    response=response_with_errors(PlatformHealthResponse, 401, 403),
    auth=session_auth,
    operation_id="platformOperationsHealth",
    summary="Inspect safe platform dependency health",
)
def platform_health(request):
    _require(request, "platform_operations.view")
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
    _require(request, "platform_operations.view")
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
    _require(request, "platform_operations.view")
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


@router.get(
    "/maintenance",
    response=response_with_errors(MaintenanceResponse, 401, 403),
    auth=session_auth,
    operation_id="platformOperationsGetMaintenance",
    summary="Inspect effective Maintenance Mode",
)
def platform_maintenance_get(request):
    _require(request, "platform_operations.view")
    return _maintenance_view(get_maintenance_snapshot())


@router.post(
    "/maintenance/enable",
    response=response_with_errors(MaintenanceResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="platformOperationsEnableMaintenance",
    summary="Enable manual Maintenance Mode",
)
def platform_maintenance_enable(request, payload: MaintenanceEnableRequest):
    _require(request, "platform_operations.manage", recent_mfa=True)
    try:
        snapshot = enable_manual_maintenance(
            message=payload.message,
            expected_end_at=payload.expected_end_at,
            context=_context(request),
        )
    except MaintenanceError as exc:
        _raise_maintenance_error(exc)
    return _maintenance_view(snapshot)


@router.post(
    "/maintenance/disable",
    response=response_with_errors(MaintenanceResponse, 401, 403, 409),
    auth=session_auth,
    operation_id="platformOperationsDisableMaintenance",
    summary="Disable manual Maintenance Mode",
)
def platform_maintenance_disable(request):
    _require(request, "platform_operations.manage", recent_mfa=True)
    try:
        snapshot = disable_manual_maintenance(context=_context(request))
    except MaintenanceError as exc:
        _raise_maintenance_error(exc)
    return _maintenance_view(snapshot)


@router.put(
    "/maintenance/schedule",
    response=response_with_errors(MaintenanceResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="platformOperationsScheduleMaintenance",
    summary="Create or replace a Maintenance Mode schedule",
)
def platform_maintenance_schedule(request, payload: MaintenanceScheduleRequest):
    _require(request, "platform_operations.manage", recent_mfa=True)
    try:
        snapshot = schedule_maintenance(
            message=payload.message,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            context=_context(request),
        )
    except MaintenanceError as exc:
        _raise_maintenance_error(exc)
    return _maintenance_view(snapshot)


@router.delete(
    "/maintenance/schedule",
    response=response_with_errors(MaintenanceResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="platformOperationsCancelMaintenanceSchedule",
    summary="Cancel the configured Maintenance Mode schedule",
)
def platform_maintenance_cancel_schedule(request):
    _require(request, "platform_operations.manage", recent_mfa=True)
    try:
        snapshot = cancel_maintenance_schedule(context=_context(request))
    except MaintenanceError as exc:
        _raise_maintenance_error(exc)
    return _maintenance_view(snapshot)


@router.get(
    "/email-deliveries/summary",
    response=response_with_errors(EmailDeliverySummaryResponse, 401, 403),
    auth=session_auth,
    operation_id="platformOperationsGetEmailDeliverySummary",
    summary="Inspect aggregate EmailDelivery state",
)
def platform_email_delivery_summary(request):
    _require(request, "platform_operations.view")
    result = get_email_delivery_summary()
    return EmailDeliverySummaryResponse(
        pending_count=result.pending_count,
        processing_count=result.processing_count,
        failed_count=result.failed_count,
        cancelled_count=result.cancelled_count,
        sent_today=result.sent_today,
        oldest_pending_at=result.oldest_pending_at,
        due_pending_count=result.due_pending_count,
    )


@router.get(
    "/email-deliveries",
    response=response_with_errors(EmailDeliveryPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="platformOperationsListEmailDeliveries",
    summary="List safe EmailDelivery operational state",
)
def platform_email_deliveries(
    request,
    page: int = 1,
    page_size: int = EMAIL_DEFAULT_PAGE_SIZE,
    status: str | None = None,
):
    _require(request, "platform_operations.view")
    try:
        result = list_email_deliveries(page=page, page_size=page_size, status=status)
    except EmailDeliveryOperationsError as exc:
        _raise_email_error(exc)
    return EmailDeliveryPageResponse(
        items=[
            EmailDeliveryItemResponse(
                id=item.id,
                event_code=item.event_code,
                status=item.status,
                attempt_count=item.attempt_count,
                created_at=item.created_at,
                updated_at=item.updated_at,
                last_attempt_at=item.last_attempt_at,
                next_attempt_at=item.next_attempt_at,
                sent_at=item.sent_at,
                failure_code=item.failure_code,
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.post(
    "/email-deliveries/{delivery_id}/retry",
    response=response_with_errors(EmailDeliveryItemResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="platformOperationsRetryEmailDelivery",
    summary="Request one eligible EmailDelivery retry",
)
def platform_email_delivery_retry(request, delivery_id: UUID):
    _require(request, "platform_operations.manage", recent_mfa=True)
    try:
        item = retry_email_delivery(
            delivery_id=delivery_id,
            context=_context(request),
        )
    except EmailDeliveryOperationsError as exc:
        _raise_email_error(exc)
    return EmailDeliveryItemResponse(
        id=item.id,
        event_code=item.event_code,
        status=item.status,
        attempt_count=item.attempt_count,
        created_at=item.created_at,
        updated_at=item.updated_at,
        last_attempt_at=item.last_attempt_at,
        next_attempt_at=item.next_attempt_at,
        sent_at=item.sent_at,
        failure_code=item.failure_code,
    )


@router.get(
    "/activity",
    response=response_with_errors(TechnicalActivityPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="platformOperationsListActivity",
    summary="List curated technical runtime activity",
)
def platform_activity(
    request,
    page: int = 1,
    page_size: int = ACTIVITY_DEFAULT_PAGE_SIZE,
):
    _require(request, "platform_operations.view")
    try:
        result = list_technical_activity(page=page, page_size=page_size)
    except TechnicalActivityPaginationError as exc:
        raise APIError(422, "invalid_pagination", str(exc)) from exc
    return TechnicalActivityPageResponse(
        items=[
            TechnicalActivityItemResponse(
                id=item.id,
                type=item.type,
                title=item.title,
                description=item.description,
                occurred_at=item.occurred_at,
                actor_type=item.actor_type,
                actor_display_name=item.actor_display_name,
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


__all__ = ["router"]
