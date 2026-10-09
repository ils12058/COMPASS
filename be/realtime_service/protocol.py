"""The realtime wire contract shared by Django and the standalone realtime service (ADR-100).

Standard library only. Django mints tickets and publishes hints with these helpers; the realtime
process consumes tickets and forwards hints with the same helpers, so both sides agree on Redis key
names, channel names, frame shapes, and validation without either importing the other.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from types import MappingProxyType
from uuid import UUID

PROTOCOL_VERSION = 1

SOCKET_PATH = "/api/realtime/v1/socket"
HEALTH_LIVE_PATH = "/api/realtime/v1/health/live"
HEALTH_READY_PATH = "/api/realtime/v1/health/ready"

# Keys live in the dedicated realtime Redis database. Pub/Sub channels are server-wide in Redis
# (not per database), so the shared prefix is what keeps realtime channels apart from Celery's.
KEY_PREFIX = "compass:realtime"

# ``secrets.token_urlsafe(32)``: 256 random bits, always 43 URL-safe characters.
TICKET_BYTES = 32
_TICKET = re.compile(r"[A-Za-z0-9_-]{43}")

# The authentication frame is about 80 characters; anything much larger is not ours.
MAX_CLIENT_FRAME_CHARS = 256
# Hints are content-free: a type and at most a few opaque identifiers.
MAX_EVENT_CHARS = 512

CONTROL_SESSION_REVOKED = "session_revoked"
_CONTROLS = frozenset({CONTROL_SESSION_REVOKED})

_EVENT_TYPE = re.compile(r"[a-z][a-z_]*(?:\.[a-z][a-z_]*)+")
_FIELD_NAME = re.compile(r"[a-z][a-z_]*")

# Public server-to-client hints form a closed registry. Notification freshness (ADR-101)
# carries no fields: the server-derived user channel already identifies the recipient.
PUBLIC_EVENT_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {"notifications.changed": frozenset()}
)


class CloseCode(IntEnum):
    """WebSocket close codes the realtime service sends.

    4000-4999 are reserved for applications by RFC 6455. Clients reconnect with a fresh ticket
    after every code; they back off for all of them except ``RECONNECT``.
    """

    POLICY_VIOLATION = 1008
    TRY_AGAIN_LATER = 1013
    RECONNECT = 4000
    AUTHENTICATION_FAILED = 4401
    SESSION_REVOKED = 4403
    AUTHENTICATION_TIMEOUT = 4408


READY_FRAME = json.dumps({"v": PROTOCOL_VERSION, "type": "ready"}, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class SocketIdentity:
    """The only identity the realtime process learns: who, and through which AuthSession."""

    user_id: str
    session_id: str


class TicketRejected(Exception):
    """A presented ticket cannot authenticate a socket. ``reason`` is a closed log code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ChannelMessage:
    """A decoded Redis channel message: an internal control or a public frame to forward."""

    control: str | None = None
    frame: str | None = None


def _is_version(value: object) -> bool:
    return type(value) is int and value == PROTOCOL_VERSION


def canonical_uuid(value: object) -> str | None:
    """Return the canonical lowercase UUID string, or ``None`` for anything else."""

    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str) or len(value) != 36:
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return str(parsed) if str(parsed) == value else None


def _require_uuid(value: object, name: str) -> str:
    canonical = canonical_uuid(value)
    if canonical is None:
        raise ValueError(f"{name} must be a UUID")
    return canonical


def is_ticket(value: object) -> bool:
    return isinstance(value, str) and _TICKET.fullmatch(value) is not None


def ticket_key(ticket: str) -> str:
    """The Redis key for a ticket: only the SHA-256 digest of the raw ticket is ever stored."""

    if not is_ticket(ticket):
        raise ValueError("realtime ticket is malformed")
    digest = hashlib.sha256(ticket.encode("ascii")).hexdigest()
    return f"{KEY_PREFIX}:ticket:{digest}"


def revoked_session_key(session_id: object) -> str:
    return f"{KEY_PREFIX}:revoked-session:{_require_uuid(session_id, 'session_id')}"


def user_channel(user_id: object) -> str:
    return f"{KEY_PREFIX}:user:{_require_uuid(user_id, 'user_id')}"


def session_channel(session_id: object) -> str:
    return f"{KEY_PREFIX}:session:{_require_uuid(session_id, 'session_id')}"


def encode_ticket_metadata(identity: SocketIdentity, *, expires_at: int) -> str:
    return json.dumps(
        {
            "v": PROTOCOL_VERSION,
            "user_id": _require_uuid(identity.user_id, "user_id"),
            "session_id": _require_uuid(identity.session_id, "session_id"),
            "expires_at": int(expires_at),
        },
        separators=(",", ":"),
    )


def decode_ticket_metadata(raw: object, *, now: float) -> SocketIdentity:
    """Validate stored ticket metadata. Raises ``TicketRejected`` when it cannot authenticate."""

    if not isinstance(raw, str) or len(raw) > MAX_EVENT_CHARS:
        raise TicketRejected("ticket_invalid")
    try:
        data = json.loads(raw)
    except ValueError:
        raise TicketRejected("ticket_invalid") from None
    if not isinstance(data, dict) or set(data) != {"v", "user_id", "session_id", "expires_at"}:
        raise TicketRejected("ticket_invalid")
    user_id = canonical_uuid(data["user_id"])
    session_id = canonical_uuid(data["session_id"])
    expires_at = data["expires_at"]
    if (
        not _is_version(data["v"])
        or user_id is None
        or session_id is None
        or type(expires_at) is not int
    ):
        raise TicketRejected("ticket_invalid")
    # Redis expiry is the primary bound; the stored expiry guards against a missing TTL.
    if expires_at <= now:
        raise TicketRejected("ticket_expired")
    return SocketIdentity(user_id=user_id, session_id=session_id)


def parse_authenticate_frame(message: Mapping[str, object]) -> str | None:
    """Return the ticket from the one allowed client frame, or ``None`` if it is malformed.

    The value is returned unvalidated; ``is_ticket`` decides whether it can be looked up.
    """

    text = message.get("text")
    if message.get("type") != "websocket.receive" or not isinstance(text, str):
        return None
    if len(text) > MAX_CLIENT_FRAME_CHARS:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or set(data) != {"type", "ticket"}:
        return None
    if data["type"] != "authenticate" or not isinstance(data["ticket"], str):
        return None
    return data["ticket"]


def _event_payload(event_type: object, fields: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(event_type, str) or not _EVENT_TYPE.fullmatch(event_type):
        raise ValueError("realtime event type is malformed")
    allowed = PUBLIC_EVENT_FIELDS.get(event_type)
    if allowed is None:
        raise ValueError("realtime event type is not registered")
    if set(fields) != set(allowed):
        raise ValueError("realtime event fields do not match the registered type")
    payload: dict[str, object] = {"v": PROTOCOL_VERSION, "type": event_type}
    for name in sorted(fields):
        if not _FIELD_NAME.fullmatch(name):
            raise ValueError("realtime event field name is malformed")
        # Only opaque identifiers travel; never names, titles, bodies, or other content.
        payload[name] = _require_uuid(fields[name], name)
    return payload


def encode_event(event_type: str, fields: Mapping[str, object] | None = None) -> str:
    """Serialize a registered, content-free public hint. Raises ``ValueError`` otherwise."""

    text = json.dumps(_event_payload(event_type, fields or {}), separators=(",", ":"))
    if len(text) > MAX_EVENT_CHARS:
        raise ValueError("realtime event is too large")
    return text


def encode_control(control: str) -> str:
    if control not in _CONTROLS:
        raise ValueError("unknown realtime control")
    return json.dumps({"v": PROTOCOL_VERSION, "control": control}, separators=(",", ":"))


def decode_channel_message(data: object) -> ChannelMessage | None:
    """Decode a Redis channel message; ``None`` means drop it.

    A public frame is re-validated against the registry and re-serialized, so the realtime
    process forwards only what the registry allows even if something else reached Redis.
    """

    if not isinstance(data, str) or len(data) > MAX_EVENT_CHARS:
        return None
    try:
        payload = json.loads(data)
    except ValueError:
        return None
    if not isinstance(payload, dict) or not _is_version(payload.get("v")):
        return None
    if "control" in payload:
        if set(payload) == {"v", "control"} and payload["control"] in _CONTROLS:
            return ChannelMessage(control=payload["control"])
        return None
    event_type = payload.pop("type", None)
    payload.pop("v")
    try:
        return ChannelMessage(frame=encode_event(event_type, payload))
    except ValueError:
        return None
