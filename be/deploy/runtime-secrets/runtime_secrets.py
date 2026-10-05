"""Deployment-only inventory and metadata checks; never read secret contents."""

from __future__ import annotations

import stat
from pathlib import Path

SECRET_FILES = {
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
REQUIRED_SECRETS = {
    "SECRET_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "AUTH_TOTP_ENCRYPTION_KEY",
    "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
}
URL_SETTINGS = (
    "REDIS_URL",
    "REDIS_CACHE_URL",
    "REDIS_RATE_LIMIT_URL",
    "REDIS_IDEMPOTENCY_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
)


class SecretCheckError(ValueError):
    """A safe error containing only a known setting/filename and reason."""


def check_directory(directory: Path, owner_uid: int) -> None:
    try:
        info = directory.lstat()
    except OSError:
        raise SecretCheckError("secret directory: missing or inaccessible") from None
    if not stat.S_ISDIR(info.st_mode):
        raise SecretCheckError("secret directory: must be a real directory, not a symlink")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SecretCheckError("secret directory: mode must be 0700")
    if info.st_uid != owner_uid:
        raise SecretCheckError("secret directory: unexpected owner")


def check_file(directory: Path, setting: str, owner_uid: int) -> None:
    filename = SECRET_FILES[setting]
    try:
        info = (directory / filename).lstat()
    except OSError:
        raise SecretCheckError(f"{filename}: missing or inaccessible") from None
    if not stat.S_ISREG(info.st_mode):
        raise SecretCheckError(f"{filename}: must be a regular file, not a symlink")
    if stat.S_IMODE(info.st_mode) != 0o444:
        raise SecretCheckError(f"{filename}: mode must be 0444")
    if info.st_uid != owner_uid:
        raise SecretCheckError(f"{filename}: unexpected owner")
    if setting in REQUIRED_SECRETS and info.st_size == 0:
        raise SecretCheckError(f"{filename}: must not be empty")
