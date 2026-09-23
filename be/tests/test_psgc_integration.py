from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import cache

from compass.integrations import psgc
from compass.integrations.psgc import (
    PSGCClient,
    PSGCInvalidResponse,
    PSGCUnavailable,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def clear_psgc_cache():
    cache.clear()
    yield
    cache.clear()


def client(*, token: str = "test-psa-token") -> PSGCClient:
    return PSGCClient(
        token,
        version="Q2_2026",
        base_url="https://classification.psa.gov.ph/psgc",
        timeout_seconds=3,
        cache_ttl_seconds=300,
    )


def row(
    code: str,
    name: str,
    *,
    level: str,
    reg: int,
    prv: int = 0,
    mun: int = 0,
    bgy: int = 0,
) -> dict[str, object]:
    return {
        "psgc_code": code,
        "area_name": name,
        "geographic_level": level,
        "reg": reg,
        "prv": prv,
        "mun": mun,
        "bgy": bgy,
    }


def envelope(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"results": {"psgc_data": rows}}


def test_psgc_client_uses_configured_version_token_and_parses_reference_levels(monkeypatch):
    calls: list[tuple[str, dict[str, list[str]], float]] = []

    region = row("0500000000", "Region V", level="Reg", reg=5)
    province = row("0501600000", "Camarines Norte", level="Prov", reg=5, prv=16)
    locality = row("0501607000", "Daet", level="Mun", reg=5, prv=16, mun=7)
    barangay = row(
        "0501607001",
        "Barangay I",
        level="Bgy",
        reg=5,
        prv=16,
        mun=7,
        bgy=1,
    )

    def fake_urlopen(request, timeout):
        split = urlsplit(request.full_url)
        query = parse_qs(split.query)
        calls.append((split.path, query, timeout))
        if split.path.endswith("/regions"):
            return FakeResponse(envelope([region]))
        if split.path.endswith("/provinces"):
            return FakeResponse(envelope([province]))
        if split.path.endswith("/municipalities"):
            return FakeResponse(envelope([locality]))
        if split.path.endswith("/barangays"):
            return FakeResponse(envelope([barangay]))
        raise AssertionError(split.path)

    monkeypatch.setattr(psgc, "urlopen", fake_urlopen)
    service = client()

    assert [(item.code, item.name) for item in service.list_regions()] == [
        ("0500000000", "Region V")
    ]
    assert [(item.code, item.name) for item in service.list_provinces(region_code="0500000000")] == [
        ("0501600000", "Camarines Norte")
    ]
    assert [
        (item.code, item.name)
        for item in service.list_cities_municipalities(
            region_code="0500000000",
            province_code="0501600000",
        )
    ] == [("0501607000", "Daet")]
    assert [
        (item.code, item.name)
        for item in service.list_barangays(city_municipality_code="0501607000")
    ] == [("0501607001", "Barangay I")]

    assert calls
    assert all("/Q2_2026/" in path for path, _, _ in calls)
    assert all(query["token"] == ["test-psa-token"] for _, query, _ in calls)
    assert all(timeout == 3 for _, _, timeout in calls)
    province_query = next(query for path, query, _ in calls if path.endswith("/provinces"))
    locality_query = next(query for path, query, _ in calls if path.endswith("/municipalities"))
    barangay_query = next(query for path, query, _ in calls if path.endswith("/barangays"))
    assert province_query["reg"] == ["5"]
    assert locality_query["reg"] == ["5"]
    assert locality_query["prv"] == ["16"]
    assert barangay_query["reg"] == ["5"]
    assert barangay_query["prv"] == ["16"]
    assert barangay_query["mun"] == ["7"]


def test_psgc_client_handles_pagination_and_cache_without_token_in_cache_key(monkeypatch):
    monkeypatch.setattr(psgc, "_PAGE_SIZE", 2)
    calls: list[str] = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        rows = (
            [
                row("0100000000", "Region A", level="Reg", reg=1),
                row("0200000000", "Region B", level="Reg", reg=2),
            ]
            if page == 1
            else [row("0300000000", "Region C", level="Reg", reg=3)]
        )
        return FakeResponse(envelope(rows))

    monkeypatch.setattr(psgc, "urlopen", fake_urlopen)
    service = client(token="do-not-cache-this-token")

    first = service.list_regions()
    second = service.list_regions()

    assert [item.code for item in first] == ["0100000000", "0200000000", "0300000000"]
    assert second == first
    assert len(calls) == 2
    assert "do-not-cache-this-token" not in service._cache_key("regions", {})


def test_psgc_transport_and_invalid_payload_errors_are_sanitized(monkeypatch):
    service = client(token="super-secret-token")

    def fail_network(request, timeout):
        raise URLError("network contains super-secret-token")

    monkeypatch.setattr(psgc, "urlopen", fail_network)
    with pytest.raises(PSGCUnavailable) as unavailable:
        service.list_regions()
    assert "super-secret-token" not in str(unavailable.value)

    cache.clear()

    def malformed(request, timeout):
        return FakeResponse({"unexpected": {"token": "super-secret-token"}})

    monkeypatch.setattr(psgc, "urlopen", malformed)
    with pytest.raises(PSGCInvalidResponse) as invalid:
        service.list_regions()
    assert "super-secret-token" not in str(invalid.value)


def test_psgc_http_error_does_not_expose_upstream_body_or_token(monkeypatch):
    service = client(token="super-secret-token")

    def fail_http(request, timeout):
        raise HTTPError(
            request.full_url,
            500,
            "upstream says super-secret-token",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(psgc, "urlopen", fail_http)
    with pytest.raises(PSGCUnavailable) as exc:
        service.list_regions()

    assert "super-secret-token" not in str(exc.value)
    assert "upstream says" not in str(exc.value)
