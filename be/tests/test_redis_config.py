from __future__ import annotations

import runpy
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from compass.common.redis_config import LEGACY_URL_SETTINGS, redis_urls


@pytest.fixture(autouse=True)
def clean_redis_environment(monkeypatch):
    for name in (*LEGACY_URL_SETTINGS, "REDIS_PASSWORD", "REDIS_HOST", "REDIS_PORT"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)


@pytest.mark.parametrize("file_backed", [False, True])
def test_one_password_routes_all_databases_and_celery(tmp_path, monkeypatch, file_backed):
    password = 'synthetic @:/#% spaces "quotes" \\ backslash\n雪'
    if file_backed:
        secret = tmp_path / "redis_password"
        secret.write_text(password + "\n", encoding="utf-8")
        monkeypatch.setenv("REDIS_PASSWORD_FILE", str(secret))
    else:
        monkeypatch.setenv("REDIS_PASSWORD", password)
    urls = redis_urls(live_staging=True)
    for name, db in zip(LEGACY_URL_SETTINGS[:4], range(4), strict=True):
        parsed = urlsplit(urls[name])
        assert parsed.path == f"/{db}"
        assert unquote(parsed.password) == password
        assert parsed.hostname == "redis"
        assert parsed.port == 6379
        assert password not in urls[name]
    assert urls["CELERY_BROKER_URL"] == urls["REDIS_URL"]
    assert urls["CELERY_RESULT_BACKEND"] == urls["REDIS_CACHE_URL"]
    realtime = urlsplit(urls["REDIS_REALTIME_URL"])
    assert realtime.path == "/4"
    assert unquote(realtime.password) == password
    assert len(set(urls) - {"CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"}) == 5
    assert len({urlsplit(urls[name]).path for name in LEGACY_URL_SETTINGS[:5]}) == 5


@pytest.mark.parametrize(
    "host", ["localhost", "redis.internal", "127.0.0.1", "::1", "[2001:db8::1]"]
)
def test_hosts_and_non_default_port(monkeypatch, host):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic-secret")
    monkeypatch.setenv("REDIS_HOST", host)
    monkeypatch.setenv("REDIS_PORT", "6380")
    parsed = urlsplit(redis_urls(live_staging=False)["REDIS_URL"])
    assert parsed.hostname == host.strip("[]")
    assert parsed.port == 6380


@pytest.mark.parametrize(
    "name,value",
    [
        ("REDIS_HOST", "bad/host"),
        ("REDIS_HOST", "user@host"),
        ("REDIS_HOST", "host:6379"),
        ("REDIS_HOST", "bad host"),
        ("REDIS_HOST", "[localhost]"),
        ("REDIS_HOST", "[::1"),
        ("REDIS_HOST", "[127.0.0.1]"),
        ("REDIS_PORT", "0"),
        ("REDIS_PORT", "65536"),
        ("REDIS_PORT", "6379/path"),
        ("REDIS_PORT", "password-sentinel"),
    ],
)
def test_invalid_connection_parts_never_expose_password(monkeypatch, name, value):
    monkeypatch.setenv("REDIS_PASSWORD", "password-sentinel")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError) as error:
        redis_urls(live_staging=True)
    assert name in str(error.value)
    assert "password-sentinel" not in str(error.value)
    assert error.value.__cause__ is None


def test_missing_password_fails_safely():
    with pytest.raises(ValueError, match="REDIS_PASSWORD is required"):
        redis_urls(live_staging=True)


def test_local_legacy_urls_do_not_require_a_new_password(monkeypatch):
    for name, db in zip(LEGACY_URL_SETTINGS[:4], range(4), strict=True):
        monkeypatch.setenv(name, f"redis://localhost:6379/{db}")
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    urls = redis_urls(live_staging=False)
    assert urls["REDIS_IDEMPOTENCY_URL"].endswith("/3")
    # Overrides that predate the realtime database put realtime state in database 4 of the
    # primary Redis server rather than requiring a new setting.
    assert urls["REDIS_REALTIME_URL"] == "redis://localhost:6379/4"
    monkeypatch.setenv("REDIS_REALTIME_URL", "redis://localhost:6380/9")
    assert redis_urls(live_staging=False)["REDIS_REALTIME_URL"] == "redis://localhost:6380/9"
    assert urls["CELERY_BROKER_URL"] == "memory://"
    assert urls["CELERY_RESULT_BACKEND"] == "cache+memory://"


@pytest.mark.parametrize("name", LEGACY_URL_SETTINGS)
def test_live_staging_rejects_legacy_overrides_without_exposing_them(monkeypatch, name):
    monkeypatch.setenv(name, "redis://:password-sentinel@localhost:6379/0")
    with pytest.raises(ValueError) as error:
        redis_urls(live_staging=True)
    assert "password-sentinel" not in str(error.value)


def test_partial_local_override_preserves_other_derived_databases(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic-secret")
    monkeypatch.setenv("REDIS_CACHE_URL", "redis://localhost:6380/9")
    urls = redis_urls(live_staging=False)
    assert urls["REDIS_CACHE_URL"] == "redis://localhost:6380/9"
    assert urls["REDIS_RATE_LIMIT_URL"].endswith("/2")
    assert urls["CELERY_RESULT_BACKEND"] == urls["REDIS_CACHE_URL"]


def test_django_settings_consumes_derived_urls_and_celery_defaults(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic-secret")
    settings = runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))
    assert settings["REDIS_URL"].endswith("/0")
    assert settings["CACHES"]["default"]["LOCATION"].endswith("/1")
    assert settings["REDIS_RATE_LIMIT_URL"].endswith("/2")
    assert settings["REDIS_IDEMPOTENCY_URL"].endswith("/3")
    assert settings["CELERY_BROKER_URL"] == settings["REDIS_URL"]
    assert settings["CELERY_RESULT_BACKEND"] == settings["REDIS_CACHE_URL"]
