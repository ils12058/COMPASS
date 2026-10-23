"""Closed portal routes and optional, deployment-owned email origins.

No request, source text, meeting URL or authentication credential is an input.
Route support does not activate an event's email link or authorize disclosure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from django.conf import settings

from .policy import NotificationTargetType


@dataclass(frozen=True, slots=True)
class NotificationEmailTarget:
    target_type: NotificationTargetType
    target_id: UUID | str | None = field(default=None, repr=False)


class EmailLinkReason(StrEnum):
    AVAILABLE = "available"
    ORIGIN_MISSING = "origin_missing"
    ORIGIN_INVALID = "origin_invalid"
    TARGET_INVALID = "target_invalid"
    TARGET_UNSUPPORTED = "target_unsupported"


@dataclass(frozen=True, slots=True)
class NotificationEmailLink:
    reason: EmailLinkReason
    url: str | None = field(default=None, repr=False)


_RECORD_ROUTES = {
    NotificationTargetType.APPOINTMENT: "appointments",
    NotificationTargetType.GROUP_SESSION: "group-sessions",
    NotificationTargetType.GOOD_MORAL: "good-moral",
    NotificationTargetType.CALL_SLIP: "call-slips",
    NotificationTargetType.GUIDANCE_FOLLOW_UP: "follow-ups",
    NotificationTargetType.ROUTINE_INTERVIEW: "routine-interviews",
    NotificationTargetType.EXIT_INTERVIEW: "exit-interviews",
    NotificationTargetType.STUDENT_SESSION_SUMMARY: "counseling/student-session-summaries",
    # Appointment UUID, never a room URL or join credential.
    NotificationTargetType.E_COUNSELING: "e-counseling",
}
_UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_LOOPBACKS = {"localhost", "127.0.0.1", "::1"}


def validated_portal_origin(value: str, *, app_env: str) -> str | None:
    """Accept canonical ASCII DNS HTTPS origins; HTTP is local-loopback-only.

    Configuration ownership establishes which DNS name is trusted. This does not
    discover deployments or use Host, CORS, CSRF, DEBUG or ALLOWED_HOSTS.
    """
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 300
        or app_env not in {"local-staging", "live-staging"}
        or any(ord(char) <= 32 or ord(char) >= 127 for char in value)
        or any(char in value for char in "\\%@?#")
    ):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.path not in {"", "/"}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.netloc
        or (port is not None and not 1 <= port <= 65535)
    ):
        return None
    authority = f"[{host}]" if ":" in host else host
    if port is not None:
        authority += f":{port}"
    # Reject normalization surprises (case, empty ports, leading zeros, etc.).
    if value not in {f"{parsed.scheme}://{authority}", f"{parsed.scheme}://{authority}/"}:
        return None
    if host in _LOOPBACKS:
        if app_env != "local-staging":
            return None
    elif (
        parsed.scheme != "https"
        or port not in {None, 443}
        or len(host) > 253
        or "." not in host
        or host.endswith(".localhost")
        or not re.fullmatch(r"[a-z]{2,63}", host.rsplit(".", 1)[-1])
        or any(not _DNS_LABEL.fullmatch(label) for label in host.split("."))
    ):
        return None
    return f"{parsed.scheme}://{authority}"


def notification_email_route(target: NotificationEmailTarget) -> str | None:
    """Return a closed internal destination; never interpret an input as a path."""
    if not isinstance(target, NotificationEmailTarget):
        return None
    try:
        kind = NotificationTargetType(target.target_type)
    except (TypeError, ValueError):
        return None
    if kind == NotificationTargetType.ACCOUNT_SECURITY:
        return None
    identifier = target.target_id
    if identifier is not None:
        if not isinstance(identifier, (UUID, str)) or not _UUID.fullmatch(str(identifier)):
            return None
        identifier = str(UUID(str(identifier)))
    if kind == NotificationTargetType.INVENTORY:
        return "/portal/inventory/current"
    if kind == NotificationTargetType.FEEDBACK:
        return f"/portal/feedback?opportunity={identifier}" if identifier else "/portal/feedback"
    if kind == NotificationTargetType.GROUP_SESSION and identifier is None:
        return "/portal/group-sessions/my"
    if identifier is None or kind not in _RECORD_ROUTES:
        return None
    return f"/portal/{_RECORD_ROUTES[kind]}/{identifier}"


def build_notification_email_link(target: NotificationEmailTarget) -> NotificationEmailLink:
    route = notification_email_route(target)
    if route is None:
        try:
            kind = NotificationTargetType(target.target_type)
        except (AttributeError, TypeError, ValueError):
            kind = None
        return NotificationEmailLink(
            EmailLinkReason.TARGET_UNSUPPORTED
            if kind in {None, NotificationTargetType.ACCOUNT_SECURITY}
            else EmailLinkReason.TARGET_INVALID
        )
    configured = settings.COMPASS_PORTAL_ORIGIN
    if not configured:
        return NotificationEmailLink(EmailLinkReason.ORIGIN_MISSING)
    origin = validated_portal_origin(configured, app_env=settings.APP_ENV)
    if origin is None:
        return NotificationEmailLink(EmailLinkReason.ORIGIN_INVALID)
    return NotificationEmailLink(EmailLinkReason.AVAILABLE, f"{origin}{route}")
