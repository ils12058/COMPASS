"""Derive Redis database URLs from one password, with local-only legacy overrides."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import quote, urlsplit, urlunsplit

from compass.common.config import env, required_env

REDIS_DATABASES = {
    "REDIS_URL": 0,
    "REDIS_CACHE_URL": 1,
    "REDIS_RATE_LIMIT_URL": 2,
    "REDIS_IDEMPOTENCY_URL": 3,
    # Ephemeral realtime tickets and revoked-session markers (ADR-100). Read by the standalone
    # realtime service too, which is why this module stays free of Django imports.
    "REDIS_REALTIME_URL": 4,
}
LEGACY_URL_SETTINGS = (*REDIS_DATABASES, "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")
_PRE_REALTIME_URL_SETTINGS = tuple(name for name in REDIS_DATABASES if name != "REDIS_REALTIME_URL")


def _with_database(url: str, database: int) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, ""))


def redis_urls(*, live_staging: bool) -> dict[str, str]:
    overrides = {name: env(name, "") for name in LEGACY_URL_SETTINGS}
    if live_staging and any(overrides.values()):
        raise ValueError("Redis/Celery URL overrides are not allowed in live-staging")

    urls = {name: overrides[name] for name in REDIS_DATABASES}
    if not urls["REDIS_REALTIME_URL"] and all(urls[name] for name in _PRE_REALTIME_URL_SETTINGS):
        # Local/CI explicit overrides that predate the realtime database keep working: realtime
        # state uses database 4 of the primary Redis server.
        urls["REDIS_REALTIME_URL"] = _with_database(
            urls["REDIS_URL"], REDIS_DATABASES["REDIS_REALTIME_URL"]
        )
    if not all(urls.values()):
        password = required_env("REDIS_PASSWORD")
        if "\x00" in password:
            raise ValueError("REDIS_PASSWORD must not contain NUL")
        host = env("REDIS_HOST", "redis")
        bracketed = host.startswith("[") or host.endswith("]")
        if bracketed and not (host.startswith("[") and host.endswith("]")):
            raise ValueError("REDIS_HOST must be a hostname or IP address")
        try:
            address = ipaddress.ip_address(host.removeprefix("[").removesuffix("]"))
        except ValueError:
            if len(host) > 253 or not all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in host.split(".")
            ):
                raise ValueError("REDIS_HOST must be a hostname or IP address") from None
        else:
            if bracketed and address.version != 6:
                raise ValueError("REDIS_HOST brackets require an IPv6 address")
            host = f"[{address}]" if address.version == 6 else str(address)
        raw_port = env("REDIS_PORT", "6379")
        if not re.fullmatch(r"[0-9]{1,5}", raw_port) or not 1 <= int(raw_port) <= 65535:
            raise ValueError("REDIS_PORT must be between 1 and 65535")
        base = f"redis://:{quote(password, safe='')}@{host}:{int(raw_port)}"
        urls = {name: urls[name] or f"{base}/{db}" for name, db in REDIS_DATABASES.items()}

    urls["CELERY_BROKER_URL"] = overrides["CELERY_BROKER_URL"] or urls["REDIS_URL"]
    urls["CELERY_RESULT_BACKEND"] = overrides["CELERY_RESULT_BACKEND"] or urls["REDIS_CACHE_URL"]
    return urls
