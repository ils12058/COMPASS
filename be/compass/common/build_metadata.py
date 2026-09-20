"""Immutable COMPASS application and container build identity."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_FULL_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    application: str
    version: str
    api_version: str
    build_id: str
    built_at: datetime | None
    environment: str


def read_project_version(pyproject_path: Path) -> str:
    """Read the canonical semantic application version from pyproject.toml."""

    try:
        with pyproject_path.open("rb") as handle:
            project = tomllib.load(handle).get("project", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Could not resolve COMPASS application version: {exc}") from exc

    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("pyproject.toml [project].version must be a non-empty string")
    return version.strip()


def parse_build_time(value: str | None) -> datetime | None:
    """Parse a build timestamp and require an explicit UTC offset."""

    raw = (value or "").strip()
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("COMPASS_BUILD_TIME must be a valid RFC3339/ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("COMPASS_BUILD_TIME must be an explicit UTC timestamp")
    return parsed.astimezone(timezone.utc)


def validate_runtime_build_identity(
    *,
    app_env: str,
    build_id: str | None,
    build_time: str | None,
) -> tuple[str, datetime | None]:
    """Validate environment-owned container identity without burdening local development."""

    resolved_id = (build_id or "").strip()
    if app_env == "live-staging":
        if not _FULL_GIT_SHA.fullmatch(resolved_id):
            raise ValueError(
                "COMPASS_BUILD_ID must be a full 40-character hexadecimal Git SHA in live-staging"
            )
        resolved_time = parse_build_time(build_time)
        if resolved_time is None:
            raise ValueError("COMPASS_BUILD_TIME is required in live-staging")
        return resolved_id.lower(), resolved_time

    if not resolved_id:
        resolved_id = "local"
    return resolved_id, parse_build_time(build_time)


def get_build_metadata() -> BuildMetadata:
    """Return the already validated identity of the running COMPASS process."""

    from django.conf import settings

    from compass.api.v1.constants import API_VERSION

    built_at = settings.COMPASS_BUILD_TIME
    if isinstance(built_at, str):
        built_at = parse_build_time(built_at)
    return BuildMetadata(
        application="COMPASS",
        version=settings.APPLICATION_VERSION,
        api_version=API_VERSION,
        build_id=settings.COMPASS_BUILD_ID,
        built_at=built_at,
        environment=settings.APP_ENV,
    )


__all__ = [
    "BuildMetadata",
    "get_build_metadata",
    "parse_build_time",
    "read_project_version",
    "validate_runtime_build_identity",
]
