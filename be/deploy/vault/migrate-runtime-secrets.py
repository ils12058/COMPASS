"""Operator-only export/comparison. No Vault access, settings import, or credential output.

Run export inside the CURRENT application image before changing its environment; files must be
kept in a root-owned tmpfs directory. Import the domain JSON files with the operator Vault CLI.
"""

import argparse
import hmac
import json
import os
from pathlib import Path

SECRETS = {
    "SECRET_KEY": ("core", "secret_key", "django_secret_key"),
    "POSTGRES_PASSWORD": ("database/postgres", "password", "postgres_password"),
    "REDIS_PASSWORD": ("database/redis", "password", "redis_password"),
    "S3_ACCESS_KEY_ID": ("storage/s3", "access_key_id", "s3_access_key_id"),
    "S3_SECRET_ACCESS_KEY": ("storage/s3", "secret_access_key", "s3_secret_access_key"),
    "SMTP_USERNAME": ("mail/smtp", "username", "smtp_username"),
    "SMTP_PASSWORD": ("mail/smtp", "password", "smtp_password"),
    "TURNSTILE_SECRET_KEY": ("integrations/turnstile", "secret_key", "turnstile_secret_key"),
    "DAILY_API_KEY": ("integrations/daily", "api_key", "daily_api_key"),
    "DAILY_WEBHOOK_HMAC": ("integrations/daily", "webhook_hmac", "daily_webhook_hmac"),
    "PSGC_API_TOKEN": ("integrations/psgc", "api_token", "psgc_api_token"),
    "AUTH_TOTP_ENCRYPTION_KEY": (
        "authentication/totp",
        "encryption_key",
        "auth_totp_encryption_key",
    ),
    "ROUTINE_INTERVIEW_ENCRYPTION_KEYS": (
        "confidential-data/routine-interview",
        "encryption_keys",
        "routine_interview_encryption_keys",
    ),
    "WEB_PUSH_PRIVATE_KEY": ("notifications/web-push", "private_key", "web_push_private_key"),
    "WEB_PUSH_STORAGE_KEY": ("notifications/web-push", "storage_key", "web_push_storage_key"),
}
REQUIRED = {
    "SECRET_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "AUTH_TOTP_ENCRYPTION_KEY",
    "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
}


def export_current(destination: Path) -> None:
    from compass.common.config import env, required_env

    records: dict[str, dict[str, str]] = {}
    for setting, (domain, field, _filename) in SECRETS.items():
        value = required_env(setting) if setting in REQUIRED else env(setting, "")
        if "\x00" in value or "\r" in value or value.endswith("\n"):
            raise ValueError(f"{setting} cannot be preserved by the runtime file contract")
        records.setdefault(domain, {})[field] = value
    for domain, values in records.items():
        path = destination / f"{domain}.json"
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Exclusive creation prevents overwriting a previous migration or following symlinks.
        with path.open("x", encoding="utf-8") as output:
            json.dump(values, output, ensure_ascii=False)
        path.chmod(0o600)


def compare_rendered(source: Path, rendered: Path) -> None:
    for setting, (domain, field, filename) in SECRETS.items():
        record = json.loads((source / f"{domain}.json").read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"{setting} migration source is invalid")
        original = record[field]
        if not isinstance(original, str):
            raise ValueError(f"{setting} migration source is invalid")
        delivered = (rendered / filename).read_bytes().decode("utf-8")
        if not hmac.compare_digest(original.encode("utf-8"), delivered.encode("utf-8")):
            raise ValueError(f"{setting} migration comparison failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "compare"))
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--rendered-dir", type=Path, default=Path("/run/compass-secrets"))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action == "export":
            export_current(args.source_dir)
        else:
            compare_rendered(args.source_dir, args.rendered_dir)
    except (OSError, KeyError, UnicodeError, json.JSONDecodeError):
        raise SystemExit("Migration files are unavailable or invalid") from None
    except ValueError as exc:
        # Environment helper errors and our comparison errors contain setting names only.
        raise SystemExit(str(exc)) from None
    print("Runtime secret migration operation succeeded")


if __name__ == "__main__":
    main()
