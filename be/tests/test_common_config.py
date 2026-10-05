from __future__ import annotations

import pytest

from compass.common.config import env, required_env


def test_env_reads_a_file_and_removes_only_trailing_line_endings(tmp_path, monkeypatch):
    secret_path = tmp_path / "secret"
    secret_path.write_text("  file-backed-secret  \r\n", encoding="utf-8")
    monkeypatch.delenv("COMPASS_TEST_SECRET", raising=False)
    monkeypatch.setenv("COMPASS_TEST_SECRET_FILE", str(secret_path))

    assert env("COMPASS_TEST_SECRET") == "  file-backed-secret  "


def test_env_keeps_existing_environment_values_working(tmp_path, monkeypatch):
    secret_path = tmp_path / "secret"
    secret_path.write_text("file-secret", encoding="utf-8")
    monkeypatch.setenv("COMPASS_TEST_SECRET", "environment-secret")
    monkeypatch.delenv("COMPASS_TEST_SECRET_FILE", raising=False)

    assert env("COMPASS_TEST_SECRET") == "environment-secret"


def test_env_rejects_duplicate_non_empty_sources_without_exposing_values(
    tmp_path,
    monkeypatch,
):
    secret_path = tmp_path / "secret"
    secret_path.write_text("file-secret", encoding="utf-8")
    monkeypatch.setenv("COMPASS_TEST_SECRET", "environment-secret")
    monkeypatch.setenv("COMPASS_TEST_SECRET_FILE", str(secret_path))

    with pytest.raises(ValueError) as exc:
        env("COMPASS_TEST_SECRET")

    assert "COMPASS_TEST_SECRET" in str(exc.value)
    assert "environment-secret" not in str(exc.value)
    assert "file-secret" not in str(exc.value)


def test_required_env_rejects_an_unreadable_secret_file_without_exposing_path(
    tmp_path,
    monkeypatch,
):
    secret_path = tmp_path / "missing-secret-file"
    monkeypatch.delenv("COMPASS_TEST_SECRET", raising=False)
    monkeypatch.setenv("COMPASS_TEST_SECRET_FILE", str(secret_path))

    with pytest.raises(ValueError, match="COMPASS_TEST_SECRET_FILE could not be read") as exc:
        required_env("COMPASS_TEST_SECRET")

    assert str(secret_path) not in str(exc.value)
