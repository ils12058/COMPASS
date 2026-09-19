from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.notifications.models import Notification
from compass.platform_ops.diagnostics import (
    ConfigurationCategory,
    ConfigurationValue,
    DiagnosticCheck,
    DiagnosticStatus,
    EnvironmentDiagnostics,
    PlatformHealth,
    run_worker_smoke,
)


def environment_fixture() -> EnvironmentDiagnostics:
    return EnvironmentDiagnostics(
        timestamp=timezone.now(),
        startup_limitation="Settings must load before diagnostics are available.",
        categories=(
            ConfigurationCategory(
                code="application",
                label="Application",
                values=(
                    ConfigurationValue("environment_mode", "Environment mode", "local-staging"),
                    ConfigurationValue("debug_enabled", "Debug enabled", True),
                ),
            ),
        ),
    )


def health_fixture(status: DiagnosticStatus = DiagnosticStatus.HEALTHY) -> PlatformHealth:
    check_status = (
        DiagnosticStatus.HEALTHY
        if status == DiagnosticStatus.HEALTHY
        else DiagnosticStatus.UNAVAILABLE
    )
    return PlatformHealth(
        status=status,
        timestamp=timezone.now(),
        summary="Synthetic diagnostic result.",
        checks=(
            DiagnosticCheck(
                code="database",
                label="PostgreSQL",
                status=check_status,
                summary="Synthetic safe database result.",
            ),
            DiagnosticCheck(
                code="celery_worker",
                label="Celery worker",
                status=DiagnosticStatus.NOT_CHECKED,
                summary="Run the COMPASS doctor worker smoke check for active worker verification.",
                required=False,
            ),
            DiagnosticCheck(
                code="celery_beat",
                label="Celery Beat",
                status=DiagnosticStatus.NOT_CHECKED,
                summary="Runtime Beat heartbeat is not available in this COMPASS slice.",
                required=False,
            ),
        ),
    )


def test_configuration_only_skips_runtime_and_worker_smoke():
    output = StringIO()
    with (
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_environment_diagnostics",
            return_value=environment_fixture(),
        ) as environment,
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_platform_health"
        ) as health,
        patch("compass.platform_ops.management.commands.compass_doctor.run_worker_smoke") as worker,
    ):
        call_command("compass_doctor", "--configuration-only", stdout=output)

    environment.assert_called_once_with()
    health.assert_not_called()
    worker.assert_not_called()
    assert "Application configuration" in output.getvalue()


def test_default_doctor_uses_shared_passive_diagnostics_and_does_not_smoke_worker():
    output = StringIO()
    with (
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_environment_diagnostics",
            return_value=environment_fixture(),
        ),
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_platform_health",
            return_value=health_fixture(),
        ) as health,
        patch("compass.platform_ops.management.commands.compass_doctor.run_worker_smoke") as worker,
    ):
        call_command("compass_doctor", stdout=output)

    health.assert_called_once_with()
    worker.assert_not_called()
    rendered = output.getvalue()
    assert "[WARN] Celery worker" in rendered
    assert "[WARN] Celery Beat" in rendered
    assert "Runtime Beat heartbeat is not available" in rendered


def test_worker_smoke_invokes_existing_noop_and_recognizes_expected_result():
    async_result = MagicMock()
    async_result.get.return_value = {"status": "ok", "request_id": None}
    with patch(
        "compass.platform_ops.diagnostics.infrastructure_noop.delay",
        return_value=async_result,
    ) as delay:
        result = run_worker_smoke(timeout_seconds=3.0)

    delay.assert_called_once_with()
    async_result.get.assert_called_once_with(timeout=3.0)
    assert result.status == DiagnosticStatus.HEALTHY


def test_worker_smoke_timeout_failure_is_safe_and_bounded():
    async_result = MagicMock()
    async_result.get.side_effect = TimeoutError("redis://user:secret@private-broker/0 task-secret")
    with patch(
        "compass.platform_ops.diagnostics.infrastructure_noop.delay",
        return_value=async_result,
    ):
        result = run_worker_smoke(timeout_seconds=2.0)

    assert result.status == DiagnosticStatus.UNAVAILABLE
    assert "private-broker" not in result.summary
    assert "task-secret" not in result.summary
    async_result.get.assert_called_once_with(timeout=2.0)

    with pytest.raises(ValueError):
        run_worker_smoke(timeout_seconds=11.0)


def test_doctor_worker_smoke_is_explicit_and_failure_is_nonzero():
    output = StringIO()
    with (
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_environment_diagnostics",
            return_value=environment_fixture(),
        ),
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_platform_health",
            return_value=health_fixture(),
        ),
        patch(
            "compass.platform_ops.management.commands.compass_doctor.run_worker_smoke",
            return_value=DiagnosticCheck(
                code="celery_worker_smoke",
                label="Celery worker smoke",
                status=DiagnosticStatus.UNAVAILABLE,
                summary="The dependency did not respond successfully to the safe diagnostic probe.",
            ),
        ) as worker,
    ):
        with pytest.raises(CommandError, match="worker smoke diagnostic failed"):
            call_command(
                "compass_doctor",
                "--worker-smoke",
                "--worker-timeout",
                "4",
                stdout=output,
            )

    worker.assert_called_once_with(timeout_seconds=4.0)


def test_failed_required_runtime_diagnostic_produces_command_error():
    with (
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_environment_diagnostics",
            return_value=environment_fixture(),
        ),
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_platform_health",
            return_value=health_fixture(DiagnosticStatus.DEGRADED),
        ),
    ):
        with pytest.raises(CommandError, match="required COMPASS runtime diagnostics failed"):
            call_command("compass_doctor", stdout=StringIO())


@override_settings(
    SECRET_KEY="CLI_SENTINEL_SECRET",
    REDIS_CACHE_URL="redis://CLI_SENTINEL_REDIS@private/1",
    S3_SECRET_ACCESS_KEY="CLI_SENTINEL_S3",
    SMTP_PASSWORD="CLI_SENTINEL_SMTP",
    DAILY_API_KEY="CLI_SENTINEL_DAILY",
    DAILY_WEBHOOK_HMAC="CLI_SENTINEL_WEBHOOK",
    TURNSTILE_SECRET_KEY="CLI_SENTINEL_TURNSTILE",
    AUTH_TOTP_ENCRYPTION_KEY="CLI_SENTINEL_TOTP",
)
def test_configuration_cli_output_never_contains_secret_values():
    output = StringIO()
    call_command("compass_doctor", "--configuration-only", stdout=output)
    rendered = output.getvalue()
    for sentinel in (
        "CLI_SENTINEL_SECRET",
        "CLI_SENTINEL_REDIS",
        "CLI_SENTINEL_S3",
        "CLI_SENTINEL_SMTP",
        "CLI_SENTINEL_DAILY",
        "CLI_SENTINEL_WEBHOOK",
        "CLI_SENTINEL_TURNSTILE",
        "CLI_SENTINEL_TOTP",
    ):
        assert sentinel not in rendered


@pytest.mark.django_db
def test_doctor_creates_no_domain_or_audit_rows():
    before_audit = AuditEvent.objects.count()
    before_notifications = Notification.objects.count()
    with (
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_environment_diagnostics",
            return_value=environment_fixture(),
        ),
        patch(
            "compass.platform_ops.management.commands.compass_doctor.collect_platform_health",
            return_value=health_fixture(),
        ),
    ):
        call_command("compass_doctor", stdout=StringIO())

    assert AuditEvent.objects.count() == before_audit
    assert Notification.objects.count() == before_notifications


def test_configuration_only_and_worker_smoke_are_mutually_exclusive():
    with pytest.raises(CommandError, match="cannot be combined"):
        call_command(
            "compass_doctor",
            "--configuration-only",
            "--worker-smoke",
            stdout=StringIO(),
        )
