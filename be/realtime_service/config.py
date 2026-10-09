"""Environment configuration for the standalone realtime service (ADR-100).

The service needs only Redis connection settings and the exact browser Origins it accepts. It
reuses the backend's Django-free environment and Redis URL helpers so ``_FILE`` secrets and the
database layout behave exactly as they do for the web application.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import urlsplit

from compass.common.config import env, env_csv, env_float, env_int
from compass.common.redis_config import redis_urls

APP_ENVIRONMENTS = frozenset({"local-staging", "live-staging"})


@dataclass(frozen=True, slots=True)
class RealtimeConfig:
    redis_url: str
    allowed_origins: frozenset[str]
    # A new socket must authenticate this quickly or it is closed.
    auth_timeout_seconds: float = 5.0
    # Authenticated sockets are closed after this long so authentication is re-established
    # through the session-checked HTTP ticket endpoint. Jitter spreads reconnects after a restart.
    connection_max_seconds: float = 900.0
    connection_jitter_seconds: float = 60.0
    max_connections: int = 1000
    redis_timeout_seconds: float = 2.0
    # Liveness of each socket's Redis subscription: an idle subscription is pinged this often and
    # treated as lost when the reply takes longer than the Redis timeout.
    redis_ping_interval_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.allowed_origins:
            raise ValueError("REALTIME_ALLOWED_ORIGINS must list at least one exact origin")
        durations = (
            self.auth_timeout_seconds,
            self.connection_max_seconds,
            self.redis_timeout_seconds,
            self.redis_ping_interval_seconds,
        )
        if not all(math.isfinite(value) and value > 0 for value in durations):
            raise ValueError("realtime timeouts and lifetimes must be positive")
        if not 0 <= self.connection_jitter_seconds <= self.connection_max_seconds / 2:
            raise ValueError("connection jitter must be at most half the connection lifetime")
        if self.max_connections < 1:
            raise ValueError("REALTIME_MAX_CONNECTIONS must be positive")


def _bounded(value: float, low: float, high: float, name: str) -> float:
    if not (math.isfinite(value) and low <= value <= high):
        raise ValueError(f"{name} must be between {low:g} and {high:g}")
    return value


def parse_allowed_origins(raw: list[str], *, allow_http: bool) -> frozenset[str]:
    """Accept only exact, canonical browser Origins: no wildcards, paths, or credentials.

    Browsers serialize Origin as lowercase ``scheme://host[:port]`` without a default port, so
    a configured value must already be in that form to be compared byte-for-byte.
    """

    origins = set()
    for value in raw:
        parts = urlsplit(value)
        schemes = {"https", "http"} if allow_http else {"https"}
        try:
            port = parts.port
        except ValueError:
            port = -1
        default_port = {"https": 443, "http": 80}.get(parts.scheme)
        if (
            parts.scheme not in schemes
            or not parts.hostname
            or "*" in value
            or parts.username is not None
            or parts.password is not None
            or parts.path
            or parts.query
            or parts.fragment
            or port == -1
            or port == default_port
            or value != value.lower()
            or value != f"{parts.scheme}://{parts.netloc}"
        ):
            raise ValueError(
                "REALTIME_ALLOWED_ORIGINS entries must be exact origins such as "
                "https://staging.compass-gco.com"
            )
        origins.add(value)
    return frozenset(origins)


def load_config() -> RealtimeConfig:
    app_env = env("APP_ENV", "local-staging")
    if app_env not in APP_ENVIRONMENTS:
        raise ValueError("APP_ENV must be either local-staging or live-staging")
    live = app_env == "live-staging"
    # Outside live-staging an explicit realtime URL is enough; live-staging derives every Redis
    # URL from REDIS_PASSWORD(_FILE), REDIS_HOST, and REDIS_PORT and rejects URL overrides.
    override = "" if live else env("REDIS_REALTIME_URL", "")
    connection_max_seconds = _bounded(
        env_float("REALTIME_CONNECTION_MAX_SECONDS", 900.0),
        60,
        3600,
        "REALTIME_CONNECTION_MAX_SECONDS",
    )
    return RealtimeConfig(
        redis_url=override or redis_urls(live_staging=live)["REDIS_REALTIME_URL"],
        allowed_origins=parse_allowed_origins(
            env_csv("REALTIME_ALLOWED_ORIGINS", []), allow_http=not live
        ),
        auth_timeout_seconds=_bounded(
            env_float("REALTIME_AUTH_TIMEOUT_SECONDS", 5.0), 1, 30, "REALTIME_AUTH_TIMEOUT_SECONDS"
        ),
        connection_max_seconds=connection_max_seconds,
        connection_jitter_seconds=min(60.0, connection_max_seconds / 10),
        max_connections=int(
            _bounded(
                env_int("REALTIME_MAX_CONNECTIONS", 1000), 1, 100_000, "REALTIME_MAX_CONNECTIONS"
            )
        ),
        redis_timeout_seconds=_bounded(
            env_float("REDIS_SOCKET_TIMEOUT", 2.0), 0.1, 30, "REDIS_SOCKET_TIMEOUT"
        ),
    )
