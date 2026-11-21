import pytest
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

from compass.common.security_headers import JsonSecurityHeadersMiddleware


def assert_json_security_headers(response):
    assert response["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    features = dict(
        item.strip().split("=", 1) for item in response["Permissions-Policy"].split(",")
    )
    assert all(allowlist == "()" for allowlist in features.values())
    assert {
        "camera",
        "microphone",
        "display-capture",
        "geolocation",
        "payment",
        "usb",
        "clipboard-read",
        "clipboard-write",
        "publickey-credentials-create",
        "publickey-credentials-get",
        "fullscreen",
        "autoplay",
        "speaker-selection",
        "storage-access",
        "web-share",
        "digital-credentials-get",
        "language-model",
        "local-network",
        "loopback-network",
        "keyboard-map",
        "sync-xhr",
        "ch-ua",
        "ch-ua-model",
        "ch-device-memory",
    } <= features.keys()


def test_public_json_endpoint_receives_restrictive_headers(client):
    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json()["application"] == "COMPASS"
    assert_json_security_headers(response)
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cache-Control"] == "no-store"


def test_authentication_error_is_also_protected(client):
    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert "error" in response.json()
    assert_json_security_headers(response)


def test_api_host_root_json_error_is_protected_for_header_scans(client):
    response = client.get("/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert_json_security_headers(response)


@pytest.mark.parametrize("status", [200, 400, 403, 404, 422, 500, 503])
def test_json_policy_applies_to_success_and_short_circuit_errors(status):
    response = JsonResponse({"synthetic": True}, status=status)
    middleware = JsonSecurityHeadersMiddleware(lambda request: response)

    assert_json_security_headers(middleware(RequestFactory().get("/api/v1/example")))


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        "APPLICATION/JSON; charset=utf-8",
        "application/problem+json",
        "application/vnd.compass+json",
    ],
)
def test_json_media_types_are_scoped_by_content_type(content_type):
    response = HttpResponse("{}", content_type=content_type)
    middleware = JsonSecurityHeadersMiddleware(lambda request: response)

    assert_json_security_headers(middleware(RequestFactory().get("/api/v1/example")))


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/admin/login/", "text/html; charset=utf-8"),
        ("/admin/example", "application/json"),
        ("/email-preview/", "text/html"),
        ("/", "text/html"),
        ("/api/v1/docs", "text/html"),
        ("/api/v1/example", "application/pdf"),
        ("/api/v1/example", "text/html"),
        ("/api/v1/example", "text/json"),
        ("/api/v10/example", "application/json"),
        ("/api/v1-other/example", "application/json"),
        ("/outside-api/", "application/json"),
    ],
)
def test_admin_html_downloads_and_non_api_responses_keep_their_policies(path, content_type):
    response = HttpResponse("synthetic", content_type=content_type)
    middleware = JsonSecurityHeadersMiddleware(lambda request: response)
    request = RequestFactory().get(path)

    assert "Content-Security-Policy" not in middleware(request)
    assert "Permissions-Policy" not in response

    response["Content-Security-Policy"] = "default-src 'self'"
    response["Permissions-Policy"] = "camera=(self)"
    middleware(request)
    assert response["Content-Security-Policy"] == "default-src 'self'"
    assert response["Permissions-Policy"] == "camera=(self)"


def test_policy_wraps_maintenance_responses_and_respects_script_mounts():
    middleware_name = "compass.common.security_headers.JsonSecurityHeadersMiddleware"
    assert settings.MIDDLEWARE.index(middleware_name) < settings.MIDDLEWARE.index(
        "compass.platform_ops.middleware.MaintenanceModeMiddleware"
    )
    request = RequestFactory().get("/mounted/api/v1/example")
    request.path_info = "/api/v1/example"
    middleware = JsonSecurityHeadersMiddleware(lambda request: JsonResponse({"synthetic": True}))
    assert_json_security_headers(middleware(request))
