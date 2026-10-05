"""Redis routing from non-secret coordinates and the existing env/_FILE helper."""

from ipaddress import IPv6Address
from urllib.parse import quote

from compass.common.config import env, env_int, required_env

REDIS_DATABASES = {
    "REDIS_URL": 0,
    "REDIS_CACHE_URL": 1,
    "REDIS_RATE_LIMIT_URL": 2,
    "REDIS_IDEMPOTENCY_URL": 3,
}


def redis_connection_urls() -> dict[str, str]:
    # Explicit URLs are compatibility for local/CI or a pre-cutover deployment. In files mode
    # runtime_secrets rejects them before this helper runs. Never include URL values in errors.
    urls = {name: env(name, "") for name in REDIS_DATABASES}
    if all(urls.values()):
        return urls
    password = required_env("REDIS_PASSWORD")
    host = env("REDIS_HOST", "redis")
    if not host or any(char in host for char in "/@?#% \t\r\n"):
        raise ValueError("REDIS_HOST must be a hostname or IP address")
    if any(char in host for char in ":[]"):
        try:
            address = IPv6Address(
                host[1:-1] if host.startswith("[") and host.endswith("]") else host
            )
        except ValueError:
            raise ValueError("REDIS_HOST must be a hostname or IP address") from None
        host = f"[{address}]"
    port = env_int("REDIS_PORT", 6379)
    if not 1 <= port <= 65535:
        raise ValueError("REDIS_PORT must be between 1 and 65535")
    authority = f":{quote(password, safe='')}@{host}:{port}"
    return {name: urls[name] or f"redis://{authority}/{db}" for name, db in REDIS_DATABASES.items()}
