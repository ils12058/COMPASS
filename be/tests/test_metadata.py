from __future__ import annotations

from pathlib import Path

from django.conf import settings

from compass.api.v1.constants import API_VERSION
from compass.common.build_metadata import read_project_version


def test_metadata_endpoint_is_public_minimal_dependency_free_and_no_store(
    client,
    django_assert_num_queries,
):
    with django_assert_num_queries(0):
        response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert set(body) == {
        "application",
        "version",
        "api_version",
        "build_id",
        "built_at",
        "environment",
    }
    assert body["application"] == "COMPASS"
    assert body["version"] == read_project_version(Path(settings.BASE_DIR) / "pyproject.toml")
    assert body["api_version"] == API_VERSION
    assert body["build_id"] == "local"
    assert body["built_at"] is None
    assert body["environment"] == "local-staging"


def test_api_object_and_metadata_share_the_same_api_version():
    from compass.api.v1.router import api

    assert api.version == API_VERSION
