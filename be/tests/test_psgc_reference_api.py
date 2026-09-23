from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.authentication.sessions import create_auth_session
from compass.integrations.psgc import PSGCClient, PSGCReference
from compass.reference_data import api as reference_api


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Reference",
        last_name="User",
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


class FakePSGCClient:
    version = "Q2_2026"

    def list_regions(self):
        return (PSGCReference("0500000000", "Region V", reg=5),)

    def list_provinces(self, *, region_code: str):
        PSGCClient.validate_code(region_code, label="region_code")
        return (PSGCReference("0501600000", "Camarines Norte", reg=5, prv=16),)

    def list_cities_municipalities(
        self,
        *,
        region_code: str,
        province_code: str | None = None,
    ):
        PSGCClient.validate_code(region_code, label="region_code")
        if province_code is not None:
            PSGCClient.validate_code(province_code, label="province_code")
        return (PSGCReference("1380600000", "City of Manila", reg=13, mun=806),)

    def list_barangays(self, *, city_municipality_code: str):
        PSGCClient.validate_code(
            city_municipality_code,
            label="city_municipality_code",
        )
        return (PSGCReference("1380601000", "Barangay 1", reg=13, mun=806, bgy=1),)


@pytest.mark.django_db
def test_psgc_reference_routes_require_session_but_no_management_capability(monkeypatch):
    sync_policy()
    student = make_user("reference-student@example.edu", "STUDENT")
    assert not student.has_capability("accounts.manage")
    assert not student.has_capability("organization.manage")
    assert not student.has_capability("institutional_forms.manage")

    fake = FakePSGCClient()
    monkeypatch.setattr(
        reference_api.PSGCClient,
        "from_settings",
        classmethod(lambda cls: fake),
    )

    assert Client().get("/api/v1/reference-data/psgc/regions").status_code == 401

    client = auth_client(student)
    regions = client.get("/api/v1/reference-data/psgc/regions")
    assert regions.status_code == 200
    assert regions.json() == {
        "version": "Q2_2026",
        "items": [{"code": "0500000000", "name": "Region V"}],
    }

    provinces = client.get(
        "/api/v1/reference-data/psgc/provinces",
        {"region_code": "0500000000"},
    )
    assert provinces.status_code == 200
    assert set(provinces.json()) == {"version", "items"}
    assert set(provinces.json()["items"][0]) == {"code", "name"}

    province_optional = client.get(
        "/api/v1/reference-data/psgc/cities-municipalities",
        {"region_code": "1300000000"},
    )
    assert province_optional.status_code == 200

    barangays = client.get(
        "/api/v1/reference-data/psgc/barangays",
        {"city_municipality_code": "1380600000"},
    )
    assert barangays.status_code == 200

    serialized = str(
        {
            "regions": regions.json(),
            "provinces": provinces.json(),
            "cities": province_optional.json(),
            "barangays": barangays.json(),
        }
    )
    assert "token" not in serialized.lower()


@pytest.mark.django_db
def test_psgc_reference_routes_reject_invalid_or_missing_parent_codes(monkeypatch):
    sync_policy()
    student = make_user("reference-invalid@example.edu", "STUDENT")
    fake = FakePSGCClient()
    monkeypatch.setattr(
        reference_api.PSGCClient,
        "from_settings",
        classmethod(lambda cls: fake),
    )
    client = auth_client(student)

    missing = client.get("/api/v1/reference-data/psgc/provinces")
    assert missing.status_code == 422

    malformed = client.get(
        "/api/v1/reference-data/psgc/provinces",
        {"region_code": "not-a-code"},
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "invalid_psgc_reference_request"

    missing_city = client.get("/api/v1/reference-data/psgc/barangays")
    assert missing_city.status_code == 422


@pytest.mark.django_db
@override_settings(
    PSGC_API_TOKEN="",
    PSGC_VERSION="",
)
def test_psgc_reference_routes_fail_cleanly_when_integration_is_unconfigured():
    sync_policy()
    student = make_user("reference-unconfigured@example.edu", "STUDENT")
    response = auth_client(student).get("/api/v1/reference-data/psgc/regions")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "psgc_reference_unavailable"
    assert "token" not in response.content.decode("utf-8").lower()
