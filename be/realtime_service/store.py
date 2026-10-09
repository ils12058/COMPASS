"""Redis access for the realtime service: one-time ticket consumption and revocation markers.

Redis is transport and ephemeral state only. Nothing here reads PostgreSQL or decides what a user
may see; the HTTP application already did that when it minted the ticket or published a hint.
"""

from __future__ import annotations

import time

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from realtime_service import protocol
from realtime_service.config import RealtimeConfig

# Errors that mean Redis is unreachable or misbehaving rather than that a ticket is bad.
REDIS_ERRORS = (RedisError, OSError)


def create_client(config: RealtimeConfig) -> aioredis.Redis:
    # No transparent retries, whatever the installed redis-py's default is: a lost subscription
    # must surface so its socket closes (1013) instead of silently resubscribing and missing a
    # revocation published in between.
    return aioredis.Redis.from_url(
        config.redis_url,
        socket_timeout=config.redis_timeout_seconds,
        socket_connect_timeout=config.redis_timeout_seconds,
        decode_responses=True,
        retry=Retry(NoBackoff(), 0),
        health_check_interval=0,
    )


async def consume_ticket(client: aioredis.Redis, ticket: str) -> protocol.SocketIdentity:
    """Atomically take a ticket out of Redis and return its identity.

    ``GETDEL`` makes consumption single-use even when two sockets present the same ticket at the
    same moment: exactly one of them receives the metadata. Raises ``TicketRejected`` or a Redis
    error.
    """

    if not protocol.is_ticket(ticket):
        raise protocol.TicketRejected("ticket_malformed")
    raw = await client.getdel(protocol.ticket_key(ticket))
    if raw is None:
        raise protocol.TicketRejected("ticket_unknown")
    identity = protocol.decode_ticket_metadata(raw, now=time.time())
    if await session_revoked(client, identity.session_id):
        raise protocol.TicketRejected("session_revoked")
    return identity


async def session_revoked(client: aioredis.Redis, session_id: str) -> bool:
    return bool(await client.exists(protocol.revoked_session_key(session_id)))
