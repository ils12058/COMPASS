"""Render both Compose contracts using temporary synthetic sources, without a daemon."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).parents[1]
SECRET_NAMES = {
    "django_secret_key",
    "postgres_password",
    "redis_password",
    "s3_access_key_id",
    "s3_secret_access_key",
    "smtp_username",
    "smtp_password",
    "turnstile_secret_key",
    "daily_api_key",
    "daily_webhook_hmac",
    "psgc_api_token",
    "auth_totp_encryption_key",
    "routine_interview_encryption_keys",
    "counseling_shared_summary_encryption_keys",
    "referral_confidential_content_encryption_keys",
    "web_push_private_key",
    "web_push_storage_key",
}


@pytest.mark.parametrize("manifest", ["compose.staging.yaml", "compose.yaml"])
def test_compose_delivery_contract_with_synthetic_sources(tmp_path, manifest):
    executable = shutil.which("docker-compose") or shutil.which("docker")
    if not executable:
        pytest.skip("Docker Compose CLI not installed; no host secrets required")
    command = [executable] if Path(executable).name == "docker-compose" else [executable, "compose"]
    secrets = tmp_path / "secrets"
    secrets.mkdir(mode=0o700)
    for name in SECRET_NAMES:
        file = secrets / name
        file.write_text("synthetic-file-value-never-in-config")
        file.chmod(0o444)
    shutil.copyfile(BACKEND / manifest, tmp_path / manifest)
    if manifest == "compose.staging.yaml":
        content = (BACKEND / "deploy/runtime-secrets/runtime.env.example").read_text()
        content = content.replace(
            "COMPASS_SECRETS_DIR=/opt/compass/secrets", f"COMPASS_SECRETS_DIR={secrets}"
        )
    else:
        content = (BACKEND / ".env.example").read_text()
    (tmp_path / ".env").write_text(content)
    result = subprocess.run(
        [
            *command,
            "--env-file",
            str(tmp_path / ".env"),
            "-f",
            str(tmp_path / manifest),
            "config",
            "--format",
            "json",
        ],
        env={
            "PATH": os.environ["PATH"],
            "COMPASS_IMAGE": "example.invalid/compass:synthetic",
            "CADDY_ADDRESS": "synthetic.invalid",
            "CADDY_HEALTH_HOST": "synthetic.invalid",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    config = json.loads(result.stdout)
    if manifest == "compose.yaml":
        assert not config.get("secrets")
        assert not config["services"]["web"].get("secrets")
        assert (
            config["services"]["web"]["environment"]["REDIS_PASSWORD"] == "dev-only-redis-password"
        )
        return
    assert len(SECRET_NAMES) == 17
    assert set(config["secrets"]) == SECRET_NAMES
    for name, source in config["secrets"].items():
        assert source["file"] == str(secrets / name)
    for service in ("web", "worker", "beat"):
        app = config["services"][service]
        assert {grant["source"] for grant in app["secrets"]} == SECRET_NAMES
        # Compose v2 reports the short target; v5 normalizes it to the absolute path.
        assert all(
            grant["target"] in {grant["source"], f"/run/secrets/{grant['source']}"}
            for grant in app["secrets"]
        )
        assert "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS" not in app["environment"]
        assert app["environment"]["COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS_FILE"] == (
            "/run/secrets/counseling_shared_summary_encryption_keys"
        )
        assert "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS" not in app["environment"]
        assert app["environment"]["REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE"] == (
            "/run/secrets/referral_confidential_content_encryption_keys"
        )
        assert "SECRET_KEY" not in app["environment"]
        assert "REDIS_PASSWORD" not in app["environment"]
        assert "REDIS_URL" not in app["environment"]
        assert "CELERY_BROKER_URL" not in app["environment"]
        assert "DEMO_ACCOUNT_PASSWORD_FILE" not in app["environment"]
        assert app["environment"]["SECRET_KEY_FILE"] == "/run/secrets/django_secret_key"
    postgres = config["services"]["postgres"]
    assert [grant["source"] for grant in postgres["secrets"]] == ["postgres_password"]
    assert postgres["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/postgres_password"
    assert "POSTGRES_PASSWORD" not in postgres["environment"]
    redis = config["services"]["redis"]
    assert [grant["source"] for grant in redis["secrets"]] == ["redis_password"]
    assert not redis.get("environment")
    assert redis["entrypoint"] == ["sh", "/usr/local/bin/compass-redis-start"]
    assert redis["healthcheck"]["test"][-1] == "healthcheck"
    assert any(mount.startswith("/run/redis-config:") for mount in redis["tmpfs"])
    assert not config["services"]["proxy"].get("secrets")
    assert "synthetic-file-value-never-in-config" not in result.stdout
