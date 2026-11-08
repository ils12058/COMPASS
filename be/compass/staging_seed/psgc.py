"""Deterministic PSGC answers for seeded Inventories; seeding never calls the live PSA service.

The answers are the canonical codes for the Bicol Region, Camarines Norte, and Daet that the
seeded home addresses use. Production validation is untouched: only the seeder swaps the client,
and unknown codes fail exactly like the live boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from compass.integrations.psgc import PSGCReference, PSGCReferenceNotFound
from compass.inventory import services

_REGIONS = {"0500000000": "Bicol Region"}
_PROVINCES = {("0500000000", "0501600000"): "Camarines Norte"}
_CITIES = {("0500000000", "0501600000", "0501607000"): "Daet"}
_BARANGAYS = {("0501607000", "0501607001"): "Barangay I"}


class SeededPSGC:
    def require_region(self, code: str) -> PSGCReference:
        name = _REGIONS.get(code)
        if name is None:
            raise PSGCReferenceNotFound("The selected PSGC Region was not found.")
        return PSGCReference(code, name)

    def require_province(self, *, region_code: str, province_code: str) -> PSGCReference:
        name = _PROVINCES.get((region_code, province_code))
        if name is None:
            raise PSGCReferenceNotFound(
                "The selected PSGC Province does not belong to the selected Region."
            )
        return PSGCReference(province_code, name)

    def require_city_municipality(
        self,
        *,
        region_code: str,
        province_code: str | None,
        city_municipality_code: str,
    ) -> PSGCReference:
        name = _CITIES.get((region_code, province_code or "", city_municipality_code))
        if name is None:
            raise PSGCReferenceNotFound(
                "The selected PSGC City/Municipality does not belong to the selected hierarchy."
            )
        return PSGCReference(city_municipality_code, name)

    def require_barangay(self, *, city_municipality_code: str, barangay_code: str) -> PSGCReference:
        name = _BARANGAYS.get((city_municipality_code, barangay_code))
        if name is None:
            raise PSGCReferenceNotFound(
                "The selected PSGC Barangay does not belong to the selected City/Municipality."
            )
        return PSGCReference(barangay_code, name)


@contextmanager
def seeded_psgc():
    with patch.object(
        services.PSGCClient,
        "from_settings",
        classmethod(lambda cls: SeededPSGC()),
    ):
        yield


__all__ = ["SeededPSGC", "seeded_psgc"]
