"""Shared, sanitized platform diagnostics for HTTP and operator CLI surfaces."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import redis
from django.conf import settings
from django.db import connection
from django.utils import timezone

from compass.integrations.mail import Mailer
from compass.integrations.storage import ObjectStorage
from compass.tasks import infrastructure_noop

logger = logging.getLogger("compass.platform_ops")

_STORAGE_DIAGNOSTIC_KEY = "__compass_diagnostics__/reserved-read-only-probe"
WORKER_SMOKE_DEFAULT_TIMEOUT_SECONDS = 5.0
WORKER_SMOKE_MAX_TIMEOUT_SECONDS = 10.0


class DiagnosticStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CHECKED = "NOT_CHECKED"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    code: str
    label: str
    status: DiagnosticStatus
    summary: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class PlatformHealth:
    status: DiagnosticStatus
    timestamp: datetime
    summary: str
    checks: tuple[DiagnosticCheck, ...]


@dataclass(frozen=True, slots=True)
class ConfigurationValue:
    code: str
    label: str
    value: bool | int | str


@dataclass(frozen=True, slots=True)
class ConfigurationCategory:
    code: str
    label: str
    values: tuple[ConfigurationValue, ...]


@dataclass(frozen=True, slots=True)
class EnvironmentDiagnostics:
    timestamp: datetime
    startup_limitation: str
    categories: tuple[ConfigurationCategory, ...]


def _log_probe_failure(*, code: str, exc: BaseException) -> None:
    logger.warning(
        "platform diagnostic probe failed",
        extra={
            "event": "platform_diagnostic_probe_failed",
            "check_code": code,
            "status": DiagnosticStatus.UNAVAILABLE.value,
            "exception_class": type(exc).__name__,
        },
    )


def _unavailable(code: str, label: str) -> DiagnosticCheck:
    return DiagnosticCheck(
        code=code,
        label=label,
        status=DiagnosticStatus.UNAVAILABLE,
        summary="The dependency did not respond successfully to the safe diagnostic probe.",
    )


def probe_database() -> DiagnosticCheck:
    code = "database"
    label = "PostgreSQL"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        _log_probe_failure(code=code, exc=exc)
        return _unavailable(code, label)
    return DiagnosticCheck(
        code=code,
        label=label,
        status=DiagnosticStatus.HEALTHY,
        summary="PostgreSQL responded to the readiness query.",
    )


def _probe_redis(*, code: str, label: str, url: str) -> DiagnosticCheck:
    client = None
    try:
        timeout = max(0.1, float(settings.REDIS_SOCKET_TIMEOUT))
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        if client.ping() is not True:
            return _unavailable(code, label)
    except Exception as exc:
        _log_probe_failure(code=code, exc=exc)
        return _unavailable(code, label)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    return DiagnosticCheck(
        code=code,
        label=label,
        status=DiagnosticStatus.HEALTHY,
        summary="Redis responded to a read-only PING.",
    )


def probe_redis_cache() -> DiagnosticCheck:
    return _probe_redis(
        code="redis_cache",
        label="Redis cache",
        url=settings.REDIS_CACHE_URL,
    )


def probe_redis_rate_limit() -> DiagnosticCheck:
    return _probe_redis(
        code="redis_rate_limit",
        label="Redis rate limiter",
        url=settings.REDIS_RATE_LIMIT_URL,
    )


def probe_redis_idempotency() -> DiagnosticCheck:
    return _probe_redis(
        code="redis_idempotency",
        label="Redis idempotency",
        url=settings.REDIS_IDEMPOTENCY_URL,
    )


def probe_celery_broker() -> DiagnosticCheck:
    return _probe_redis(
        code="celery_broker",
        label="Celery broker",
        url=settings.CELERY_BROKER_URL,
    )


def probe_object_storage() -> DiagnosticCheck:
    code = "object_storage"
    label = "Object storage"
    try:
        # False is an expected answer: the reserved key is deliberately not created.
        ObjectStorage().exists(_STORAGE_DIAGNOSTIC_KEY)
    except Exception as exc:
        _log_probe_failure(code=code, exc=exc)
        return _unavailable(code, label)
    return DiagnosticCheck(
        code=code,
        label=label,
        status=DiagnosticStatus.HEALTHY,
        summary="Object storage answered a read-only existence check.",
    )


def probe_smtp() -> DiagnosticCheck:
    code = "smtp"
    label = "SMTP"
    try:
        Mailer().probe_connection()
    except Exception as exc:
        _log_probe_failure(code=code, exc=exc)
        return _unavailable(code, label)
    return DiagnosticCheck(
        code=code,
        label=label,
        status=DiagnosticStatus.HEALTHY,
        summary="SMTP connection and authentication completed without sending a message.",
    )


def run_worker_smoke(
    *, timeout_seconds: float = WORKER_SMOKE_DEFAULT_TIMEOUT_SECONDS
) -> DiagnosticCheck:
    if not 0 < timeout_seconds <= WORKER_SMOKE_MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"worker smoke timeout must be greater than zero and at most "
            f"{WORKER_SMOKE_MAX_TIMEOUT_SECONDS:g} seconds"
        )
    code = "celery_worker_smoke"
    label = "Celery worker smoke"
    try:
        result = infrastructure_noop.delay()
        payload = result.get(timeout=timeout_seconds)
    except Exception as exc:
        _log_probe_failure(code=code, exc=exc)
        return _unavailable(code, label)
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return _unavailable(code, label)
    return DiagnosticCheck(
        code=code,
        label=label,
        status=DiagnosticStatus.HEALTHY,
        summary="A harmless diagnostic task was executed and its result was received.",
    )


def celery_worker_passive_status() -> DiagnosticCheck:
    return DiagnosticCheck(
        code="celery_worker",
        label="Celery worker",
        status=DiagnosticStatus.NOT_CHECKED,
        summary="Run the COMPASS doctor worker smoke check for active worker verification.",
        required=False,
    )


def celery_beat_passive_status() -> DiagnosticCheck:
    return DiagnosticCheck(
        code="celery_beat",
        label="Celery Beat",
        status=DiagnosticStatus.NOT_CHECKED,
        summary="Runtime Beat heartbeat is not available in this COMPASS slice.",
        required=False,
    )


def daily_passive_status() -> DiagnosticCheck:
    if not settings.DAILY_ENABLED:
        return DiagnosticCheck(
            code="daily",
            label="Daily.co",
            status=DiagnosticStatus.DISABLED,
            summary="Daily.co integration is disabled.",
            required=False,
        )
    return DiagnosticCheck(
        code="daily",
        label="Daily.co",
        status=DiagnosticStatus.NOT_CHECKED,
        summary="Daily.co is enabled; passive provider connectivity is not checked.",
        required=False,
    )


def turnstile_passive_status() -> DiagnosticCheck:
    if not settings.TURNSTILE_ENABLED:
        return DiagnosticCheck(
            code="turnstile",
            label="Cloudflare Turnstile",
            status=DiagnosticStatus.DISABLED,
            summary="Turnstile integration is disabled.",
            required=False,
        )
    return DiagnosticCheck(
        code="turnstile",
        label="Cloudflare Turnstile",
        status=DiagnosticStatus.NOT_CHECKED,
        summary="Turnstile is enabled; passive provider connectivity is not checked.",
        required=False,
    )


def derive_overall_status(checks: tuple[DiagnosticCheck, ...]) -> DiagnosticStatus:
    if any(
        item.required
        and item.status in {DiagnosticStatus.UNAVAILABLE, DiagnosticStatus.DEGRADED}
        for item in checks
    ):
        return DiagnosticStatus.DEGRADED
    return DiagnosticStatus.HEALTHY


def _safe_probe(probe: Callable[[], DiagnosticCheck], *, code: str, label: str) -> DiagnosticCheck:
    try:
        return probe()
    except Exception as exc:
        _log_probe_failure(code=code, exc=exc)
        return _unavailable(code, label)


def collect_platform_health() -> PlatformHealth:
    probes: tuple[tuple[str, str, Callable[[], DiagnosticCheck]], ...] = (
        ("database", "PostgreSQL", probe_database),
        ("redis_cache", "Redis cache", probe_redis_cache),
        ("redis_rate_limit", "Redis rate limiter", probe_redis_rate_limit),
        ("redis_idempotency", "Redis idempotency", probe_redis_idempotency),
        ("celery_broker", "Celery broker", probe_celery_broker),
        ("object_storage", "Object storage", probe_object_storage),
        ("smtp", "SMTP", probe_smtp),
    )
    checked = tuple(
        _safe_probe(probe, code=code, label=label) for code, label, probe in probes
    )
    checks = checked + (
        celery_worker_passive_status(),
        celery_beat_passive_status(),
        daily_passive_status(),
        turnstile_passive_status(),
    )
    status = derive_overall_status(checks)
    has_not_checked = any(item.status == DiagnosticStatus.NOT_CHECKED for item in checks)
    if status == DiagnosticStatus.DEGRADED:
        summary = "One or more required passive platform dependencies are unavailable."
    elif has_not_checked:
        summary = (
            "Required passive dependencies are healthy; some runtime/provider checks "
            "were intentionally not performed."
        )
    else:
        summary = "Required passive platform dependencies are healthy."
    return PlatformHealth(
        status=status,
        timestamp=timezone.now(),
        summary=summary,
        checks=checks,
    )


def _smtp_transport_mode() -> str:
    if settings.SMTP_USE_SSL:
        return "SSL"
    if settings.SMTP_USE_TLS:
        return "TLS"
    return "PLAIN"


def _notification_recovery_configured() -> bool:
    schedule = settings.CELERY_BEAT_SCHEDULE.get("notification-email-recovery")
    return bool(
        schedule
        and schedule.get("task") == "compass.notifications.email.dispatch_due"
        and schedule.get("schedule") == settings.NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS
    )


def collect_environment_diagnostics() -> EnvironmentDiagnostics:
    database = settings.DATABASES.get("default", {})
    categories = (
        ConfigurationCategory(
            code="application",
            label="Application",
            values=(
                ConfigurationValue("environment_mode", "Environment mode", settings.APP_ENV),
                ConfigurationValue("debug_enabled", "Debug enabled", bool(settings.DEBUG)),
                ConfigurationValue(
                    "api_docs_enabled",
                    "API documentation enabled",
                    bool(settings.API_DOCS_ENABLED),
                ),
            ),
        ),
        ConfigurationCategory(
            code="database",
            label="Database",
            values=(
                ConfigurationValue(
                    "configured",
                    "Database configured",
                    bool(database.get("ENGINE")),
                ),
            ),
        ),
        ConfigurationCategory(
            code="redis",
            label="Redis and Celery",
            values=(
                ConfigurationValue(
                    "cache_configured",
                    "Redis cache configured",
                    bool(settings.REDIS_CACHE_URL),
                ),
                ConfigurationValue(
                    "rate_limit_configured",
                    "Redis rate limiter configured",
                    bool(settings.REDIS_RATE_LIMIT_URL),
                ),
                ConfigurationValue(
                    "idempotency_configured",
                    "Redis idempotency configured",
                    bool(settings.REDIS_IDEMPOTENCY_URL),
                ),
                ConfigurationValue(
                    "celery_broker_configured",
                    "Celery broker configured",
                    bool(settings.CELERY_BROKER_URL),
                ),
            ),
        ),
        ConfigurationCategory(
            code="object_storage",
            label="Object storage",
            values=(
                ConfigurationValue(
                    "configured",
                    "Object storage configured",
                    bool(
                        settings.S3_BUCKET_NAME
                        and settings.S3_ACCESS_KEY_ID
                        and settings.S3_SECRET_ACCESS_KEY
                    ),
                ),
                ConfigurationValue(
                    "addressing_style",
                    "Addressing style",
                    settings.S3_ADDRESSING_STYLE,
                ),
                ConfigurationValue(
                    "tls_verification_enabled",
                    "TLS verification enabled",
                    bool(settings.S3_VERIFY),
                ),
            ),
        ),
        ConfigurationCategory(
            code="smtp",
            label="SMTP",
            values=(
                ConfigurationValue(
                    "configured",
                    "SMTP configured",
                    bool(settings.SMTP_HOST and settings.DEFAULT_FROM_EMAIL),
                ),
                ConfigurationValue(
                    "transport_mode",
                    "SMTP transport mode",
                    _smtp_transport_mode(),
                ),
                ConfigurationValue(
                    "authentication_configured",
                    "SMTP authentication configured",
                    bool(settings.SMTP_USERNAME and settings.SMTP_PASSWORD),
                ),
            ),
        ),
        ConfigurationCategory(
            code="authentication",
            label="Authentication security",
            values=(
                ConfigurationValue(
                    "secure_cookie_enabled",
                    "Secure authentication cookie",
                    bool(settings.AUTH_COOKIE_SECURE),
                ),
                ConfigurationValue(
                    "same_site_mode",
                    "Authentication cookie SameSite",
                    settings.AUTH_COOKIE_SAMESITE,
                ),
                ConfigurationValue(
                    "totp_encryption_configured",
                    "TOTP encryption configured",
                    bool(settings.AUTH_TOTP_ENCRYPTION_KEY),
                ),
                ConfigurationValue(
                    "turnstile_enabled",
                    "Turnstile enabled",
                    bool(settings.TURNSTILE_ENABLED),
                ),
                ConfigurationValue(
                    "turnstile_configured",
                    "Turnstile configured",
                    bool(settings.TURNSTILE_SECRET_KEY),
                ),
            ),
        ),
        ConfigurationCategory(
            code="daily",
            label="Daily.co",
            values=(
                ConfigurationValue(
                    "enabled",
                    "Daily.co enabled",
                    bool(settings.DAILY_ENABLED),
                ),
                ConfigurationValue(
                    "credentials_configured",
                    "Daily.co credentials configured",
                    bool(settings.DAILY_API_KEY and settings.DAILY_WEBHOOK_HMAC),
                ),
            ),
        ),
        ConfigurationCategory(
            code="notification_delivery",
            label="Notification delivery",
            values=(
                ConfigurationValue(
                    "retry_policy_configured",
                    "Notification retry policy configured",
                    bool(
                        settings.NOTIFICATION_EMAIL_MAX_ATTEMPTS >= 1
                        and settings.NOTIFICATION_EMAIL_RETRY_BASE_SECONDS >= 1
                        and settings.NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS > settings.SMTP_TIMEOUT
                    ),
                ),
                ConfigurationValue(
                    "recovery_schedule_configured",
                    "Notification recovery schedule configured",
                    _notification_recovery_configured(),
                ),
            ),
        ),
    )
    return EnvironmentDiagnostics(
        timestamp=timezone.now(),
        startup_limitation=(
            "Diagnostics are available only after Django settings load successfully. "
            "Configuration errors that prevent startup remain visible in deployment logs."
        ),
        categories=categories,
    )


__all__ = [
    "ConfigurationCategory",
    "ConfigurationValue",
    "DiagnosticCheck",
    "DiagnosticStatus",
    "EnvironmentDiagnostics",
    "PlatformHealth",
    "celery_beat_passive_status",
    "celery_worker_passive_status",
    "collect_environment_diagnostics",
    "collect_platform_health",
    "derive_overall_status",
    "probe_celery_broker",
    "probe_database",
    "probe_object_storage",
    "probe_redis_cache",
    "probe_redis_idempotency",
    "probe_redis_rate_limit",
    "probe_smtp",
    "run_worker_smoke",
    "WORKER_SMOKE_DEFAULT_TIMEOUT_SECONDS",
    "WORKER_SMOKE_MAX_TIMEOUT_SECONDS",
]
