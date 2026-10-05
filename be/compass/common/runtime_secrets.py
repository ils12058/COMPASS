"""File delivery contract, independent of the operator's secret store."""

import os

from compass.common.config import env

RUNTIME_SECRET_FILES = {
    "SECRET_KEY": "django_secret_key",
    "POSTGRES_PASSWORD": "postgres_password",
    "REDIS_PASSWORD": "redis_password",
    "S3_ACCESS_KEY_ID": "s3_access_key_id",
    "S3_SECRET_ACCESS_KEY": "s3_secret_access_key",
    "SMTP_USERNAME": "smtp_username",
    "SMTP_PASSWORD": "smtp_password",
    "TURNSTILE_SECRET_KEY": "turnstile_secret_key",
    "DAILY_API_KEY": "daily_api_key",
    "DAILY_WEBHOOK_HMAC": "daily_webhook_hmac",
    "PSGC_API_TOKEN": "psgc_api_token",
    "AUTH_TOTP_ENCRYPTION_KEY": "auth_totp_encryption_key",
    "ROUTINE_INTERVIEW_ENCRYPTION_KEYS": "routine_interview_encryption_keys",
    "WEB_PUSH_PRIVATE_KEY": "web_push_private_key",
    "WEB_PUSH_STORAGE_KEY": "web_push_storage_key",
}
LEGACY_CONNECTION_SETTINGS = (
    "REDIS_URL",
    "REDIS_CACHE_URL",
    "REDIS_RATE_LIMIT_URL",
    "REDIS_IDEMPOTENCY_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
)


def validate_runtime_secret_sources() -> None:
    """Staging Compose forces files mode; local/CI retain the existing env contract."""
    mode = env("RUNTIME_SECRETS_MODE", "environment")
    if mode not in {"environment", "files"}:
        raise ValueError("RUNTIME_SECRETS_MODE must be environment or files")
    if mode != "files":
        return
    for name, filename in RUNTIME_SECRET_FILES.items():
        if os.environ.get(name):
            raise ValueError(f"{name} must use file delivery in files mode")
        if os.environ.get(f"{name}_FILE") != f"/run/secrets/compass/{filename}":
            raise ValueError(f"{name}_FILE must use the runtime secret mount in files mode")
    for name in LEGACY_CONNECTION_SETTINGS:
        if os.environ.get(name) or os.environ.get(f"{name}_FILE"):
            raise ValueError(f"{name} overrides are not allowed in files mode")
