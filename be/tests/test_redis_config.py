from __future__ import annotations

import runpy
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from compass.common.redis_config import REDIS_DATABASES, redis_connection_urls
from compass.common.runtime_secrets import (
    LEGACY_CONNECTION_SETTINGS,
    RUNTIME_SECRET_FILES,
    validate_runtime_secret_sources,
)


@pytest.fixture
def derived_redis(monkeypatch):
    for name in (*LEGACY_CONNECTION_SETTINGS, "REDIS_PASSWORD", "REDIS_HOST", "REDIS_PORT"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_PORT", "6380")


def test_redis_file_password_and_database_separation(tmp_path, monkeypatch, derived_redis):
    password = 'synthetic@:/#%\\" space'
    secret = tmp_path / "redis-password"
    secret.write_text(password, encoding="utf-8")
    monkeypatch.setenv("REDIS_PASSWORD_FILE", str(secret))
    urls = redis_connection_urls()
    for name, db in REDIS_DATABASES.items():
        parsed = urlsplit(urls[name])
        assert parsed.hostname == "redis.internal"
        assert parsed.port == 6380
        assert parsed.path == f"/{db}"
        assert parsed.fragment == ""
        assert unquote(parsed.password) == password
        assert password not in urls[name]


def test_redis_requires_credential_before_deriving_urls(monkeypatch, derived_redis):
    with pytest.raises(ValueError, match="^REDIS_PASSWORD is required$"):
        redis_connection_urls()


def test_redis_rejects_both_password_sources(tmp_path, monkeypatch, derived_redis):
    secret = tmp_path / "secret"
    secret.write_text("synthetic-file", encoding="utf-8")
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic-env")
    monkeypatch.setenv("REDIS_PASSWORD_FILE", str(secret))
    with pytest.raises(ValueError, match="REDIS_PASSWORD and REDIS_PASSWORD_FILE cannot both"):
        redis_connection_urls()


def test_explicit_local_urls_work_without_password(monkeypatch, derived_redis):
    expected = {name: f"redis://localhost:6379/{db}" for name, db in REDIS_DATABASES.items()}
    for name, value in expected.items():
        monkeypatch.setenv(name, value)
    assert redis_connection_urls() == expected


def test_partial_local_override_retains_other_derived_routes(monkeypatch, derived_redis):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    monkeypatch.setenv("REDIS_CACHE_URL", "redis://localhost:6379/9")
    urls = redis_connection_urls()
    assert urls["REDIS_CACHE_URL"] == "redis://localhost:6379/9"
    assert urlsplit(urls["REDIS_IDEMPOTENCY_URL"]).path == "/3"


@pytest.mark.parametrize("host", ["localhost", "::1", "[::1]"])
def test_redis_host_and_ipv6(host, monkeypatch, derived_redis):
    monkeypatch.setenv("REDIS_HOST", host)
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    assert urlsplit(redis_connection_urls()["REDIS_URL"]).hostname == host.strip("[]")


@pytest.mark.parametrize("host", ["redis:6380", "user@redis", "redis/path", "redis#fragment"])
def test_redis_rejects_authority_injection(host, monkeypatch, derived_redis):
    monkeypatch.setenv("REDIS_HOST", host)
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    with pytest.raises(ValueError, match="^REDIS_HOST must be a hostname or IP address$"):
        redis_connection_urls()


@pytest.mark.parametrize("port", ["0", "65536"])
def test_invalid_port_does_not_echo_credentials(port, monkeypatch, derived_redis):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic-do-not-echo")
    monkeypatch.setenv("REDIS_PORT", port)
    with pytest.raises(ValueError, match="^REDIS_PORT must be between 1 and 65535$"):
        redis_connection_urls()


def test_settings_use_derived_cache_rate_idempotency_and_celery(monkeypatch, derived_redis):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    loaded = runpy.run_path(str(Path(__file__).parents[1] / "config" / "settings.py"))
    assert urlsplit(loaded["CACHES"]["default"]["LOCATION"]).path == "/1"
    assert urlsplit(loaded["REDIS_RATE_LIMIT_URL"]).path == "/2"
    assert urlsplit(loaded["REDIS_IDEMPOTENCY_URL"]).path == "/3"
    assert loaded["CELERY_BROKER_URL"] == loaded["REDIS_URL"]
    assert loaded["CELERY_RESULT_BACKEND"] == loaded["REDIS_CACHE_URL"]


@pytest.fixture
def file_sources(monkeypatch):
    monkeypatch.setenv("RUNTIME_SECRETS_MODE", "files")
    for name, filename in RUNTIME_SECRET_FILES.items():
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv(f"{name}_FILE", f"/run/secrets/compass/{filename}")
    for name in LEGACY_CONNECTION_SETTINGS:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)


def test_file_mode_accepts_only_runtime_pointers(file_sources):
    validate_runtime_secret_sources()


@pytest.mark.parametrize("name", list(RUNTIME_SECRET_FILES))
def test_file_mode_rejects_plaintext_and_missing_pointers(name, monkeypatch, file_sources):
    monkeypatch.setenv(name, "synthetic-do-not-echo")
    with pytest.raises(ValueError, match=f"^{name} must use file delivery in files mode$"):
        validate_runtime_secret_sources()
    monkeypatch.delenv(name)
    monkeypatch.delenv(f"{name}_FILE")
    with pytest.raises(ValueError, match=f"^{name}_FILE must use the runtime secret mount"):
        validate_runtime_secret_sources()


@pytest.mark.parametrize("name", LEGACY_CONNECTION_SETTINGS)
def test_file_mode_rejects_legacy_url_sources(name, monkeypatch, file_sources):
    monkeypatch.setenv(name, "redis://:synthetic@redis:6379/0")
    with pytest.raises(ValueError, match=f"^{name} overrides are not allowed in files mode$"):
        validate_runtime_secret_sources()
