from pathlib import Path
from uuid import UUID

import pytest
from django.test import override_settings

from compass.notifications.email_links import (
    EmailLinkReason,
    NotificationEmailTarget,
    build_notification_email_link,
    notification_email_route,
    validated_portal_origin,
)

ID = "12345678-1234-4234-8234-123456789abc"


@pytest.mark.parametrize(
    ("origin", "environment", "expected"),
    [
        ("https://portal.example", "live-staging", "https://portal.example"),
        ("https://portal.example/", "live-staging", "https://portal.example"),
        ("https://portal.example:443", "live-staging", "https://portal.example:443"),
        ("http://localhost:3000", "local-staging", "http://localhost:3000"),
        ("http://127.0.0.1:3000/", "local-staging", "http://127.0.0.1:3000"),
        ("http://[::1]:3000", "local-staging", "http://[::1]:3000"),
        ("https://localhost:3443", "local-staging", "https://localhost:3443"),
    ],
)
def test_trusted_origin(origin, environment, expected):
    assert validated_portal_origin(origin, app_env=environment) == expected


@pytest.mark.parametrize(
    "origin",
    [
        "",
        None,
        "//portal.example",
        "/portal",
        "http://portal.example",
        "javascript:alert(1)",
        "data:text/html,hello",
        "file:///portal",
        "https://user@portal.example",
        "https://user:pass@portal.example",
        "https://@portal.example",
        "https://portal.example?next=evil",
        "https://portal.example?",
        "https://portal.example#fragment",
        "https://portal.example#",
        "https://portal.example/portal",
        "https://portal.example//",
        "https://portal.example/../",
        "https://portal.example/%2e%2e",
        "https://portal.example:3000",
        "https://portal.example:0",
        "https://portal.example:65536",
        "https://portal.example:",
        "https://portal.example:0443",
        "https://portal.example:abc",
        "https://portal.example.",
        "https://PORTAL.example",
        "HTTPS://portal.example",
        " https://portal.example",
        "https://portal.example\n",
        "https://por\ttal.example",
        "https://portal.example\\@evil.test",
        "https://portal%2eexample",
        "https://portal。example",
        "https://pörtal.example",
        "https://-portal.example",
        "https://portal-.example",
        "https://a..example",
        "https://portal",
        "https://127.0.0.1",
        "https://192.168.1.1",
        "https://2130706433",
        "https://localhost",
        "https://sub.localhost",
        "https://[::1]",
        "http://localhost:3000",
    ],
)
def test_unsafe_live_origin_is_unavailable(origin):
    assert validated_portal_origin(origin, app_env="live-staging") is None


@pytest.mark.parametrize(
    "origin",
    [
        "http://portal.example",
        "http://localhost.evil.test",
        "http://127.1:3000",
        "http://0.0.0.0:3000",
        "http://[::]:3000",
        "http://localhost:0",
        "http://localhost:03000",
    ],
)
def test_local_http_is_explicit_loopback_only(origin):
    assert validated_portal_origin(origin, app_env="local-staging") is None


def test_unknown_environment_fails_closed():
    assert validated_portal_origin("http://localhost:3000", app_env="production") is None


@pytest.mark.parametrize(
    ("kind", "route"),
    [
        ("APPOINTMENT", "appointments"),
        ("GROUP_SESSION", "group-sessions"),
        ("GOOD_MORAL", "good-moral"),
        ("CALL_SLIP", "call-slips"),
        ("GUIDANCE_FOLLOW_UP", "follow-ups"),
        ("ROUTINE_INTERVIEW", "routine-interviews"),
        ("EXIT_INTERVIEW", "exit-interviews"),
        ("COUNSELING_SHARED_SUMMARY", "counseling/summaries"),
        ("E_COUNSELING", "e-counseling"),
    ],
)
def test_record_routes_match_frontend_targets_and_pages(kind, route):
    assert (
        notification_email_route(NotificationEmailTarget(kind, UUID(ID))) == f"/portal/{route}/{ID}"
    )
    root = Path(__file__).resolve().parents[2] / "fe"
    destinations = (root / "src/features/notifications/notification-targets.ts").read_text()
    assert f'"/portal/{route}/"' in destinations
    assert list((root / f"src/app/(portal)/portal/{route}").glob("[[]*]/page.tsx"))


@pytest.mark.parametrize(
    ("kind", "identifier", "route"),
    [
        ("INVENTORY", ID, "/portal/inventory/current"),
        ("INVENTORY", None, "/portal/inventory/current"),
        ("GROUP_SESSION", None, "/portal/group-sessions/my"),
        ("FEEDBACK", None, "/portal/feedback"),
        ("FEEDBACK", ID, f"/portal/feedback?opportunity={ID}"),
    ],
)
def test_recipient_scoped_routes_and_explicit_query(kind, identifier, route):
    assert notification_email_route(NotificationEmailTarget(kind, identifier)) == route


@pytest.mark.parametrize(
    "identifier",
    [
        None,
        "",
        "not-a-uuid",
        "//evil.example",
        "https://evil.example",
        "../secret",
        "%2e%2e%2fsecret",
        f"{ID}?token=secret",
        f"{ID}#secret",
        f"{ID}/../",
        f" {ID}",
        ID.replace("-", ""),
        "{" + ID + "}",
        [ID],
        123,
    ],
)
def test_invalid_identifiers_never_become_routes(identifier):
    assert notification_email_route(NotificationEmailTarget("APPOINTMENT", identifier)) is None


@pytest.mark.parametrize(
    "kind", ["ACCOUNT_SECURITY", "UNKNOWN", "//evil.test", "https://evil.test"]
)
def test_security_and_unapproved_targets_are_excluded(kind):
    assert notification_email_route(NotificationEmailTarget(kind, ID)) is None


@override_settings(COMPASS_PORTAL_ORIGIN="https://portal.example", APP_ENV="live-staging")
def test_request_headers_do_not_affect_absolute_link(rf, settings):
    settings.ALLOWED_HOSTS = ["hostile.example"]
    settings.CORS_ALLOWED_ORIGINS = ["https://hostile.example"]
    settings.CSRF_TRUSTED_ORIGINS = ["https://hostile.example"]
    request = rf.get(
        "/?next=//hostile.example",
        HTTP_HOST="hostile.example",
        HTTP_ORIGIN="https://hostile.example",
        HTTP_X_FORWARDED_HOST="hostile.example",
    )
    assert request.META["HTTP_HOST"] == "hostile.example"
    result = build_notification_email_link(NotificationEmailTarget("APPOINTMENT", ID))
    assert result.reason == EmailLinkReason.AVAILABLE
    assert result.url == f"https://portal.example/portal/appointments/{ID}"
    assert "?" not in result.url and "#" not in result.url
    assert ID not in repr(result)


@pytest.mark.parametrize(
    ("origin", "reason"),
    [
        ("", EmailLinkReason.ORIGIN_MISSING),
        ("http://portal.example", EmailLinkReason.ORIGIN_INVALID),
    ],
)
def test_configuration_limitations_are_explicit(origin, reason, settings):
    settings.APP_ENV = "live-staging"
    settings.COMPASS_PORTAL_ORIGIN = origin
    result = build_notification_email_link(NotificationEmailTarget("APPOINTMENT", ID))
    assert result.reason == reason and result.url is None


def test_untyped_or_unsupported_targets_fail_safely():
    for value in [None, {"target_type": "APPOINTMENT", "target_id": ID}, "https://evil.test"]:
        assert notification_email_route(value) is None
        assert build_notification_email_link(value).reason == EmailLinkReason.TARGET_UNSUPPORTED
    assert build_notification_email_link(NotificationEmailTarget("APPOINTMENT")).reason == (
        EmailLinkReason.TARGET_INVALID
    )
