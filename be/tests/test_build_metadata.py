from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings

from compass.common.build_metadata import (
    read_project_version,
    validate_runtime_build_identity,
)


def test_project_version_is_read_from_canonical_pyproject():
    assert read_project_version(Path(settings.BASE_DIR) / "pyproject.toml") == "0.1.0"


def test_local_staging_allows_local_identity_without_timestamp():
    build_id, built_at = validate_runtime_build_identity(
        app_env="local-staging",
        build_id="local",
        build_time="",
    )
    assert build_id == "local"
    assert built_at is None


def test_live_staging_accepts_full_sha_and_utc_build_timestamp():
    build_id, built_at = validate_runtime_build_identity(
        app_env="live-staging",
        build_id="a" * 40,
        build_time="2026-09-20T07:15:42Z",
    )
    assert build_id == "a" * 40
    assert built_at is not None
    assert built_at.isoformat() == "2026-09-20T07:15:42+00:00"


@pytest.mark.parametrize(
    "build_id",
    [
        "",
        "abc1234",
        "g" * 40,
        "A" * 40,
    ],
)
def test_live_staging_rejects_missing_short_malformed_or_noncanonical_sha(build_id):
    with pytest.raises(ValueError, match="COMPASS_BUILD_ID"):
        validate_runtime_build_identity(
            app_env="live-staging",
            build_id=build_id,
            build_time="2026-09-20T07:15:42Z",
        )


@pytest.mark.parametrize("build_time", ["", "not-a-time", "2026-09-20T15:15:42+08:00"])
def test_live_staging_rejects_missing_malformed_or_non_utc_build_timestamp(build_time):
    with pytest.raises(ValueError, match="COMPASS_BUILD_TIME"):
        validate_runtime_build_identity(
            app_env="live-staging",
            build_id="a" * 40,
            build_time=build_time,
        )
