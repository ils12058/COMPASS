"""Public, dependency-free COMPASS build and release metadata."""

from __future__ import annotations

from datetime import datetime

from django.http import JsonResponse
from ninja import Schema
from pydantic import ConfigDict

from compass.common.build_metadata import get_build_metadata


class SystemMetadataResponse(Schema):
    model_config = ConfigDict(extra="forbid")

    application: str
    version: str
    api_version: str
    build_id: str
    built_at: datetime | None
    environment: str


def system_metadata(request):
    metadata = get_build_metadata()
    payload = SystemMetadataResponse(
        application=metadata.application,
        version=metadata.version,
        api_version=metadata.api_version,
        build_id=metadata.build_id,
        built_at=metadata.built_at,
        environment=metadata.environment,
    )
    response = JsonResponse(payload.model_dump(mode="json"))
    response["Cache-Control"] = "no-store"
    return response


__all__ = ["SystemMetadataResponse", "system_metadata"]
