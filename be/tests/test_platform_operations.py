from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.accounts.policy import CAPABILITY_CODES
from compass.accounts.services import effective_capabilities, set_user_capability_override
from compass.api.v1.constants import API_VERSION
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.notifications.models import Notification
from compass.platform_ops.diagnostics import (
    DiagnosticCheck,
    DiagnosticStatus,
    PlatformHealth,
    collect_platform_health,
    derive_overall_status,
    probe_database,
    probe_object_storage,
    probe_smtp,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Platform",
        last_name="Operator",
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def healthy_platform_health() -> PlatformHealth:
    return PlatformHealth(
        status=DiagnosticStatus.HEALTHY,
        timestamp=timezone.now(),
        summary="All checked platform dependencies are responding.",
        checks=(
            DiagnosticCheck(
                code="database",
                label="PostgreSQL",
                status=DiagnosticStatus.HEALTHY,
                summary="PostgreSQL responded to the readiness query.",
            ),
        ),
    )


@pytest.mark.django_db
def test_platform_operations_capability_is_it_admin_baseline_only():
    sync_policy()
    assert "platform_operations.view" in CAPABILITY_CODES
    assert "platform_operations.manage" in CAPABILITY_CODES

    admin = make_user("platform-admin@example.edu", "IT_ADMIN")
    counselor = make_user("platform-counselor@example.edu", "COUNSELOR")
    staff = make_user("platform-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("platform-student@example.edu", "STUDENT")
    officer = make_user("platform-officer@example.edu", "INSTITUTIONAL_OFFICER")
    dpo = make_user("platform-dpo@example.edu", "INSTITUTIONAL_OFFICER")
    head = make_user("platform-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert admin.has_capability("platform_operations.view")
    assert admin.has_capability("platform_operations.manage")
    for user in (counselor, staff, student, officer, dpo, head):
        assert not user.has_capability("platform_operations.view")
        assert not user.has_capability("platform_operations.manage")


@pytest.mark.django_db
def test_platform_operations_routes_use_effective_capability_not_role_shortcut():
    sync_policy()
    counselor = make_user("delegated-platform-viewer@example.edu", "COUNSELOR")
    set_user_capability_override(
        user=counselor,
        capability="platform_operations.view",
        effect="GRANT",
        reason="Temporary diagnostic access",
    )
    assert "platform_operations.view" in effective_capabilities(counselor)
    client = auth_client(counselor)

    with patch(
        "compass.platform_ops.api.collect_platform_health",
        return_value=healthy_platform_health(),
    ):
        response = client.get("/api/v1/platform/health")

    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


@pytest.mark.django_db
def test_platform_operations_routes_require_authentication_and_capability():
    sync_policy()
    anonymous = Client()
    assert anonymous.get("/api/v1/platform/health").status_code == 401
    assert anonymous.get("/api/v1/platform/environment").status_code == 401
    assert anonymous.post("/api/v1/platform/health/worker-smoke").status_code == 401
    assert anonymous.get("/api/v1/platform/commands").status_code == 404

    student = make_user("no-platform-access@example.edu", "STUDENT")
    client = auth_client(student)
    assert client.get("/api/v1/platform/health").status_code == 403
    assert client.get("/api/v1/platform/environment").status_code == 403
    assert client.post("/api/v1/platform/health/worker-smoke", **csrf(client)).status_code == 403
    assert client.get("/api/v1/platform/commands").status_code == 404


def test_database_probe_uses_existing_select_one_semantics_and_sanitizes_failure():
    cursor = MagicMock()
    with patch("compass.platform_ops.diagnostics.connection.cursor", return_value=cursor):
        healthy = probe_database()
    assert healthy.status == DiagnosticStatus.HEALTHY
    cursor.__enter__.return_value.execute.assert_called_once_with("SELECT 1")

    cursor = MagicMock()
    cursor.__enter__.side_effect = OperationalError("postgres://secret-host/private")
    with patch("compass.platform_ops.diagnostics.connection.cursor", return_value=cursor):
        failed = probe_database()
    assert failed.status == DiagnosticStatus.UNAVAILABLE
    assert "secret-host" not in failed.summary
    assert "private" not in failed.summary


@pytest.mark.parametrize("failed_index", range(4))
@override_settings(
    REDIS_CACHE_URL="redis://cache-secret@example.invalid/1",
    REDIS_RATE_LIMIT_URL="redis://rate-secret@example.invalid/2",
    REDIS_IDEMPOTENCY_URL="redis://idem-secret@example.invalid/3",
    CELERY_BROKER_URL="redis://broker-secret@example.invalid/0",
)
def test_redis_concerns_and_celery_broker_fail_independently(failed_index):
    clients = [MagicMock() for _ in range(4)]
    for index, client in enumerate(clients):
        if index == failed_index:
            client.ping.side_effect = RuntimeError(
                "redis://username:password@private-host/secret-db"
            )
        else:
            client.ping.return_value = True

    cursor = MagicMock()
    with (
        patch("compass.platform_ops.diagnostics.connection.cursor", return_value=cursor),
        patch("compass.platform_ops.diagnostics.redis.Redis.from_url", side_effect=clients),
        patch("compass.platform_ops.diagnostics.ObjectStorage.exists", return_value=False),
        patch("compass.platform_ops.diagnostics.Mailer.probe_connection"),
    ):
        health = collect_platform_health()

    redis_codes = ["redis_cache", "redis_rate_limit", "redis_idempotency", "celery_broker"]
    by_code = {item.code: item for item in health.checks}
    for index, code in enumerate(redis_codes):
        expected = (
            DiagnosticStatus.UNAVAILABLE if index == failed_index else DiagnosticStatus.HEALTHY
        )
        assert by_code[code].status == expected
    assert set(by_code) == {
        "database",
        "redis_cache",
        "redis_rate_limit",
        "redis_idempotency",
        "celery_broker",
        "object_storage",
        "smtp",
    }
    assert "password" not in json.dumps(
        [{"summary": item.summary, "code": item.code} for item in health.checks]
    )
    assert health.status == DiagnosticStatus.DEGRADED
    assert health.summary == "One or more checked platform dependencies are unavailable."


def test_storage_probe_treats_false_as_success_and_sanitizes_exceptions():
    with patch(
        "compass.platform_ops.diagnostics.ObjectStorage.exists", return_value=False
    ) as exists:
        healthy = probe_object_storage()
    assert healthy.status == DiagnosticStatus.HEALTHY
    exists.assert_called_once()
    assert "reserved-read-only-probe" in exists.call_args.args[0]

    with patch(
        "compass.platform_ops.diagnostics.ObjectStorage.exists",
        side_effect=RuntimeError("s3://access:secret@private-endpoint/bucket"),
    ):
        failed = probe_object_storage()
    assert failed.status == DiagnosticStatus.UNAVAILABLE
    assert "private-endpoint" not in failed.summary
    assert "bucket" not in failed.summary


def test_smtp_probe_is_connection_only_and_never_sends_message():
    with (
        patch("compass.platform_ops.diagnostics.Mailer.probe_connection") as probe,
        patch("compass.integrations.mail.Mailer.send") as send,
    ):
        healthy = probe_smtp()
    assert healthy.status == DiagnosticStatus.HEALTHY
    probe.assert_called_once_with()
    send.assert_not_called()

    with patch(
        "compass.platform_ops.diagnostics.Mailer.probe_connection",
        side_effect=RuntimeError("smtp://user:secret@private-host"),
    ):
        failed = probe_smtp()
    assert failed.status == DiagnosticStatus.UNAVAILABLE
    assert "private-host" not in failed.summary


@pytest.mark.parametrize(
    ("daily_enabled", "turnstile_enabled"),
    [(False, False), (True, True)],
)
def test_automatic_health_contains_only_real_probes(daily_enabled, turnstile_enabled):
    cursor = MagicMock()
    with (
        override_settings(DAILY_ENABLED=daily_enabled, TURNSTILE_ENABLED=turnstile_enabled),
        patch("compass.platform_ops.diagnostics.connection.cursor", return_value=cursor),
        patch("compass.platform_ops.diagnostics.redis.Redis.from_url") as redis_factory,
        patch("compass.platform_ops.diagnostics.ObjectStorage.exists", return_value=False),
        patch("compass.platform_ops.diagnostics.Mailer.probe_connection"),
    ):
        redis_factory.return_value.ping.return_value = True
        health = collect_platform_health()

    assert [item.code for item in health.checks] == [
        "database",
        "redis_cache",
        "redis_rate_limit",
        "redis_idempotency",
        "celery_broker",
        "object_storage",
        "smtp",
    ]
    assert health.status == DiagnosticStatus.HEALTHY
    assert health.summary == "All checked platform dependencies are responding."


def test_overall_status_derivation_is_deterministic():
    healthy = DiagnosticCheck("a", "A", DiagnosticStatus.HEALTHY, "ok")
    optional_unknown = DiagnosticCheck(
        "worker", "Worker", DiagnosticStatus.NOT_CHECKED, "unknown", required=False
    )
    optional_disabled = DiagnosticCheck(
        "daily", "Daily", DiagnosticStatus.DISABLED, "disabled", required=False
    )
    failed = DiagnosticCheck("db", "DB", DiagnosticStatus.UNAVAILABLE, "failed")

    assert derive_overall_status((healthy, optional_unknown, optional_disabled)) == (
        DiagnosticStatus.HEALTHY
    )
    assert derive_overall_status((healthy, failed, optional_unknown)) == DiagnosticStatus.DEGRADED


@pytest.mark.django_db
@override_settings(
    SECRET_KEY="SENTINEL_DJANGO_SECRET",
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "PASSWORD": "SENTINEL_DB_PASSWORD",
        }
    },
    REDIS_CACHE_URL="redis://SENTINEL_REDIS_PASSWORD@cache.invalid/1",
    REDIS_RATE_LIMIT_URL="redis://SENTINEL_REDIS_PASSWORD@rate.invalid/2",
    REDIS_IDEMPOTENCY_URL="redis://SENTINEL_REDIS_PASSWORD@idem.invalid/3",
    CELERY_BROKER_URL="redis://SENTINEL_REDIS_PASSWORD@broker.invalid/0",
    S3_BUCKET_NAME="SENTINEL_BUCKET",
    S3_ACCESS_KEY_ID="SENTINEL_S3_ACCESS",
    S3_SECRET_ACCESS_KEY="SENTINEL_S3_SECRET",
    SMTP_PASSWORD="SENTINEL_SMTP_PASSWORD",
    DAILY_API_KEY="SENTINEL_DAILY_API_KEY",
    DAILY_WEBHOOK_HMAC="SENTINEL_DAILY_WEBHOOK",
    TURNSTILE_SECRET_KEY="SENTINEL_TURNSTILE_SECRET",
    AUTH_TOTP_ENCRYPTION_KEY="SENTINEL_TOTP_KEY",
)
def test_environment_endpoint_is_safe_resolved_projection_with_no_secret_values():
    sync_policy()
    admin = make_user("environment-admin@example.edu", "IT_ADMIN")
    response = auth_client(admin).get("/api/v1/platform/environment")

    assert response.status_code == 200
    body = response.json()
    categories = {category["code"]: category for category in body["categories"]}
    assert {
        "application",
        "database",
        "redis",
        "object_storage",
        "smtp",
        "authentication",
        "daily",
        "notification_delivery",
    } == set(categories)
    assert "Django settings load successfully" in body["startup_limitation"]
    application_values = {
        value["code"]: value["value"] for value in categories["application"]["values"]
    }
    assert application_values["environment_mode"] == settings.APP_ENV
    assert application_values["application_version"] == settings.APPLICATION_VERSION
    assert application_values["api_version"] == API_VERSION
    assert application_values["build_id"] == settings.COMPASS_BUILD_ID
    assert application_values["build_timestamp"] is None

    authentication_values = {
        value["code"]: value["value"] for value in categories["authentication"]["values"]
    }
    daily_values = {value["code"]: value["value"] for value in categories["daily"]["values"]}
    notification_values = {
        value["code"]: value["value"]
        for value in categories["notification_delivery"]["values"]
    }
    assert authentication_values["turnstile_enabled"] is settings.TURNSTILE_ENABLED
    assert authentication_values["turnstile_configured"] is True
    assert daily_values["enabled"] is settings.DAILY_ENABLED
    assert daily_values["credentials_configured"] is True
    assert "recovery_schedule_configured" in notification_values

    serialized = json.dumps(body)
    for sentinel in (
        "SENTINEL_DJANGO_SECRET",
        "SENTINEL_DB_PASSWORD",
        "SENTINEL_REDIS_PASSWORD",
        "SENTINEL_BUCKET",
        "SENTINEL_S3_ACCESS",
        "SENTINEL_S3_SECRET",
        "SENTINEL_SMTP_PASSWORD",
        "SENTINEL_DAILY_API_KEY",
        "SENTINEL_DAILY_WEBHOOK",
        "SENTINEL_TURNSTILE_SECRET",
        "SENTINEL_TOTP_KEY",
    ):
        assert sentinel not in serialized


@pytest.mark.django_db
def test_worker_smoke_endpoint_uses_view_capability_default_timeout_and_creates_no_rows():
    sync_policy()
    viewer = make_user("worker-viewer@example.edu", "COUNSELOR")
    set_user_capability_override(
        user=viewer,
        capability="platform_operations.view",
        effect="GRANT",
        reason="Temporary worker diagnostic access",
    )
    client = auth_client(viewer)
    before_audit = AuditEvent.objects.count()
    before_notifications = Notification.objects.count()

    with patch(
        "compass.platform_ops.api.run_worker_smoke",
        return_value=DiagnosticCheck(
            code="celery_worker_smoke",
            label="Background worker",
            status=DiagnosticStatus.HEALTHY,
            summary="A diagnostic task completed successfully.",
        ),
    ) as worker:
        response = client.post(
            "/api/v1/platform/health/worker-smoke?timeout_seconds=999",
            **csrf(client),
        )

    assert response.status_code == 200
    assert response.json() == {
        "code": "celery_worker_smoke",
        "label": "Background worker",
        "status": "HEALTHY",
        "summary": "A diagnostic task completed successfully.",
    }
    worker.assert_called_once_with()
    assert AuditEvent.objects.count() == before_audit
    assert Notification.objects.count() == before_notifications


@pytest.mark.django_db
def test_worker_smoke_unavailable_is_diagnostic_data_not_api_failure():
    sync_policy()
    admin = make_user("worker-unavailable@example.edu", "IT_ADMIN")
    client = auth_client(admin)
    with patch(
        "compass.platform_ops.api.run_worker_smoke",
        return_value=DiagnosticCheck(
            code="celery_worker_smoke",
            label="Background worker",
            status=DiagnosticStatus.UNAVAILABLE,
            summary="The dependency did not respond successfully to the safe diagnostic probe.",
        ),
    ):
        response = client.post("/api/v1/platform/health/worker-smoke", **csrf(client))

    assert response.status_code == 200
    assert response.json()["status"] == "UNAVAILABLE"
    assert "broker" not in response.json()["summary"].lower()
    assert "credential" not in response.json()["summary"].lower()


@pytest.mark.django_db
def test_worker_smoke_unexpected_failure_returns_safe_server_error():
    sync_policy()
    admin = make_user("worker-error@example.edu", "IT_ADMIN")
    client = auth_client(admin)
    with patch(
        "compass.platform_ops.api.run_worker_smoke",
        side_effect=RuntimeError("redis://user:secret@private-broker/task-secret"),
    ):
        response = client.post("/api/v1/platform/health/worker-smoke", **csrf(client))

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "worker_smoke_failed"
    serialized = json.dumps(body)
    assert "private-broker" not in serialized
    assert "task-secret" not in serialized


def test_public_liveness_and_readiness_do_not_depend_on_platform_probes(client):
    with (
        patch(
            "compass.platform_ops.diagnostics.Mailer.probe_connection",
            side_effect=RuntimeError("smtp unavailable"),
        ),
        patch(
            "compass.platform_ops.diagnostics.ObjectStorage.exists",
            side_effect=RuntimeError("storage unavailable"),
        ),
    ):
        live = client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok", "checks": {"application": "ok"}}

    cursor = MagicMock()
    with (
        patch("compass.api.v1.health.connection.cursor", return_value=cursor),
        patch("compass.api.v1.health.canonical_counseling_readiness", return_value=(True, "ok")),
        patch(
            "compass.platform_ops.diagnostics.Mailer.probe_connection",
            side_effect=RuntimeError("smtp unavailable"),
        ),
    ):
        ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ok",
        "checks": {"application": "ok", "database": "ok", "canonical_services": "ok"},
    }
