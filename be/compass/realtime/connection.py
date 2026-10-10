"""The Django process's client for the dedicated realtime Redis database (ADR-100)."""

from __future__ import annotations

from functools import lru_cache

import redis
from django.conf import settings


@lru_cache(maxsize=4)
def _client(url: str, timeout: float) -> redis.Redis:
    return redis.Redis.from_url(
        url,
        socket_timeout=timeout,
        socket_connect_timeout=timeout,
        decode_responses=True,
    )


def realtime_redis() -> redis.Redis:
    """One pooled client per process and configuration; every call has a short timeout."""

    return _client(settings.REDIS_REALTIME_URL, float(settings.REDIS_SOCKET_TIMEOUT))
