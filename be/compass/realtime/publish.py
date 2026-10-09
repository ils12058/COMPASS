"""Best-effort, content-free realtime publishing from the Django application (ADR-100).

PostgreSQL commits are authoritative. A hint only tells a browser that something may have
changed; the browser re-reads canonical state over HTTP, and a lost hint is healed by ordinary
polling or the next ``ready``. There is deliberately no outbox. Publishing never raises Redis
errors into a request: failures are logged and dropped.

Session revocation uses the same channel with an internal control message. The revocation itself
is already committed in PostgreSQL; the realtime step only closes sockets sooner and makes tickets
minted before the revocation unusable.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from functools import partial

import redis
from django.conf import settings
from django.db import transaction

from compass.realtime.connection import realtime_redis
from realtime_service import protocol

logger = logging.getLogger("compass.realtime")

_REDIS_ERRORS = (redis.exceptions.RedisError, OSError)


def _publish(channel: str, payload: str) -> bool:
    try:
        realtime_redis().publish(channel, payload)
    except _REDIS_ERRORS as exc:
        logger.warning(
            "realtime hint was not published",
            extra={"event": "realtime_publish_failed", "error_type": type(exc).__name__},
        )
        return False
    return True


def publish_to_user(user_id, event_type: str, fields: Mapping[str, object] | None = None) -> bool:
    """Publish a registered hint to every socket of one user now. Returns whether it was sent.

    The event is validated before anything is sent; an unregistered type or a field that is not
    an opaque identifier raises ``ValueError``, because that is a programming error.
    """

    payload = protocol.encode_event(event_type, fields or {})
    channel = protocol.user_channel(user_id)
    if not settings.REALTIME_ENABLED:
        return False
    return _publish(channel, payload)


def publish_to_user_on_commit(
    user_id, event_type: str, fields: Mapping[str, object] | None = None
) -> None:
    """Publish after the surrounding transaction commits; nothing is sent if it rolls back."""

    payload = protocol.encode_event(event_type, fields or {})
    channel = protocol.user_channel(user_id)
    if settings.REALTIME_ENABLED:
        transaction.on_commit(partial(_publish, channel, payload), robust=True)


def _close_session_sockets(session_id: str) -> bool:
    try:
        # One round trip: mark the session revoked (checked when any ticket is consumed), then
        # tell any open socket for it to close.
        pipeline = realtime_redis().pipeline(transaction=True)
        pipeline.set(
            protocol.revoked_session_key(session_id),
            "1",
            ex=int(settings.REALTIME_REVOCATION_TTL_SECONDS),
        )
        pipeline.publish(
            protocol.session_channel(session_id),
            protocol.encode_control(protocol.CONTROL_SESSION_REVOKED),
        )
        pipeline.execute()
    except _REDIS_ERRORS as exc:
        logger.warning(
            "realtime session revocation was not published",
            extra={
                "event": "realtime_revocation_publish_failed",
                "error_type": type(exc).__name__,
            },
        )
        return False
    return True


def close_session_sockets_on_commit(session_id) -> None:
    """After a revocation commits, close the AuthSession's sockets and void its tickets."""

    if settings.REALTIME_ENABLED:
        canonical = protocol.canonical_uuid(session_id)
        if canonical is None:
            raise ValueError("session_id must be a UUID")
        transaction.on_commit(partial(_close_session_sockets, canonical), robust=True)
