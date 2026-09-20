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
from compass.authentication.sessions import create_auth_session
from compass.platform_ops.catalog import COMMAND_CATALOG
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


def healthy_platform_health() -> PlatformHealth:
    return PlatformHealth(
        status=DiagnosticStatus.HEALTHY,
        timestamp=timezone.now(),
        summary="Required passive platform dependencies are healthy.",
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
    assert anonymous.get("/api/v1/platform/commands").status_code == 401

    student = make_user("no-platform-access@example.edu", "STUDENT")
    client = auth_client(student)
    assert client.get("/api/v1/platform/health").status_code == 403
    assert client.get("/api/v1/platform/environment").status_code == 403
    assert client.get("/api/v1/platform/commands").status_code == 403


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
    assert by_code["celery_worker"].status == DiagnosticStatus.NOT_CHECKED
    assert by_code["celery_beat"].status == DiagnosticStatus.NOT_CHECKED
    assert "password" not in json.dumps(
        [{"summary": item.summary, "code": item.code} for item in health.checks]
    )
    assert health.status == DiagnosticStatus.DEGRADED


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


@override_settings(DAILY_ENABLED=False, TURNSTILE_ENABLED=False)
def test_disabled_external_integrations_are_reported_honestly_without_provider_calls():
    cursor = MagicMock()
    with (
        patch("compass.platform_ops.diagnostics.connection.cursor", return_value=cursor),
        patch("compass.platform_ops.diagnostics.redis.Redis.from_url") as redis_factory,
        patch("compass.platform_ops.diagnostics.ObjectStorage.exists", return_value=False),
        patch("compass.platform_ops.diagnostics.Mailer.probe_connection"),
    ):
        redis_factory.return_value.ping.return_value = True
        health = collect_platform_health()

    by_code = {item.code: item for item in health.checks}
    assert by_code["daily"].status == DiagnosticStatus.DISABLED
    assert by_code["turnstile"].status == DiagnosticStatus.DISABLED
    assert health.status == DiagnosticStatus.HEALTHY


@override_settings(DAILY_ENABLED=True, TURNSTILE_ENABLED=True)
def test_enabled_external_integrations_are_not_passively_called_or_falsely_green():
    cursor = MagicMock()
    with (
        patch("compass.platform_ops.diagnostics.connection.cursor", return_value=cursor),
        patch("compass.platform_ops.diagnostics.redis.Redis.from_url") as redis_factory,
        patch("compass.platform_ops.diagnostics.ObjectStorage.exists", return_value=False),
        patch("compass.platform_ops.diagnostics.Mailer.probe_connection"),
    ):
        redis_factory.return_value.ping.return_value = True
        health = collect_platform_health()

    by_code = {item.code: item for item in health.checks}
    assert by_code["daily"].status == DiagnosticStatus.NOT_CHECKED
    assert by_code["turnstile"].status == DiagnosticStatus.NOT_CHECKED
    assert health.status == DiagnosticStatus.HEALTHY
    assert "not performed" in health.summary


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
def test_command_catalog_is_curated_deterministic_and_never_executes_from_browser():
    sync_policy()
    admin = make_user("catalog-admin@example.edu", "IT_ADMIN")
    response = auth_client(admin).get("/api/v1/platform/commands")

    assert response.status_code == 200
    body = response.json()
    assert body["execution_supported"] is False
    expected_codes = [item.code for item in COMMAND_CATALOG]
    assert [item["code"] for item in body["commands"]] == expected_codes
    assert {item["category"] for item in body["commands"]} <= {
        "BOOTSTRAP",
        "DEPLOYMENT",
        "DIAGNOSTIC",
    }

    serialized = json.dumps(body).lower()
    for forbidden in (
        " manage.py shell",
        " manage.py dbshell",
        "flush",
        "backup now",
        "restore",
        "redis-cli",
        "celery purge",
    ):
        assert forbidden not in serialized
    assert Client().post("/api/v1/platform/commands/run").status_code == 404


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
        patch(
            "compass.platform_ops.diagnostics.Mailer.probe_connection",
            side_effect=RuntimeError("smtp unavailable"),
        ),
    ):
        ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ok",
        "checks": {"application": "ok", "database": "ok"},
    }
