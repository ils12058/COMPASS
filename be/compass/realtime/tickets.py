"""One-time realtime WebSocket tickets for the current authenticated session (ADR-100).

A ticket is 256 random bits handed to the browser once. Redis stores only its SHA-256 digest,
mapped to the minimum identity the realtime service needs (user and AuthSession IDs), and expires
it quickly. The realtime service consumes it atomically, so a ticket authenticates one socket.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import redis
from django.conf import settings

from compass.realtime.connection import realtime_redis
from realtime_service import protocol


class RealtimeUnavailable(RuntimeError):
    """Realtime Redis could not store a ticket; ordinary HTTP is unaffected."""


@dataclass(frozen=True, slots=True)
class IssuedRealtimeTicket:
    ticket: str
    expires_in_seconds: int

    def __repr__(self) -> str:
        return f"IssuedRealtimeTicket(expires_in_seconds={self.expires_in_seconds})"


def issue_ticket(*, user_id, session_id) -> IssuedRealtimeTicket:
    """Store a new ticket for this exact user and AuthSession. Never persists the raw ticket."""

    ttl = int(settings.REALTIME_TICKET_TTL_SECONDS)
    identity = protocol.SocketIdentity(user_id=str(user_id), session_id=str(session_id))
    client = realtime_redis()
    # SET NX makes creation explicit: an existing digest is never overwritten. A collision of
    # 256-bit values does not happen in practice; one retry keeps the rule simple and total.
    for _ in range(2):
        ticket = secrets.token_urlsafe(protocol.TICKET_BYTES)
        metadata = protocol.encode_ticket_metadata(identity, expires_at=int(time.time()) + ttl)
        try:
            created = client.set(protocol.ticket_key(ticket), metadata, nx=True, ex=ttl)
        except (redis.exceptions.RedisError, OSError) as exc:
            raise RealtimeUnavailable("realtime ticket store is unavailable") from exc
        if created:
            return IssuedRealtimeTicket(ticket=ticket, expires_in_seconds=ttl)
    raise RealtimeUnavailable("realtime ticket could not be stored")
