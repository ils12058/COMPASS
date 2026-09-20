from unittest.mock import MagicMock, patch

import pytest
from django.db import OperationalError
from django.test import override_settings


def test_live_endpoint_is_process_only(client):
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"application": "ok"}}
    assert response["X-Request-ID"]


def test_ready_endpoint_checks_postgres(client):
    cursor = MagicMock()
    with patch("compass.api.v1.health.connection.cursor", return_value=cursor) as cursor_factory:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"
    cursor_factory.assert_called_once_with()
    cursor.__enter__.return_value.execute.assert_called_once_with("SELECT 1")


@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    ALLOWED_HOSTS=["testserver", "localhost"],
)
def test_internal_ready_probe_can_use_trusted_forwarded_https_without_disabling_redirect(client):
    plain = client.get("/api/v1/health/ready", HTTP_HOST="localhost")
    assert plain.status_code in {301, 302}
    assert plain["Location"].startswith("https://")

    cursor = MagicMock()
    with patch("compass.api.v1.health.connection.cursor", return_value=cursor):
        trusted_probe = client.get(
            "/api/v1/health/ready",
            HTTP_HOST="localhost",
            HTTP_X_FORWARDED_PROTO="https",
        )
    assert trusted_probe.status_code == 200
    assert trusted_probe.json()["checks"]["database"] == "ok"


def test_ready_endpoint_returns_503_when_postgres_is_unavailable(client):
    cursor = MagicMock()
    cursor.__enter__.side_effect = OperationalError("database unavailable")
    with patch("compass.api.v1.health.connection.cursor", return_value=cursor):
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"application": "ok", "database": "failed"},
    }


@pytest.mark.django_db
def test_unknown_api_route_uses_safe_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()["error"]
    assert payload["code"] == "not_found"
    assert payload["message"] == "The requested resource was not found."
    assert payload["request_id"] == response["X-Request-ID"]
