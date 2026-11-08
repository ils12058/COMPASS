"""Test fixtures mirror the explicit post-migration deployment synchronization."""

import pytest


@pytest.fixture(autouse=True)
def synchronized_institutional_forms(request):
    if request.node.get_closest_marker("django_db") is None and not {
        "db",
        "transactional_db",
    }.intersection(request.fixturenames):
        return
    request.getfixturevalue("_django_db_helper")
    from compass.institutional_forms.bootstrap import sync_institutional_forms

    sync_institutional_forms()


@pytest.fixture
def inventory_psgc(monkeypatch):
    """Canonical PSGC responses for tests that submit a complete Individual Inventory."""

    from compass.integrations.psgc import PSGCReference, PSGCReferenceNotFound
    from compass.inventory import services

    class CanonicalInventoryPSGC:
        def require_region(self, code: str):
            if code != "1300000000":
                raise PSGCReferenceNotFound("The selected PSGC Region was not found.")
            return PSGCReference(code, "National Capital Region")

        def require_province(self, *, region_code: str, province_code: str):
            raise PSGCReferenceNotFound(
                "The selected PSGC Province does not belong to the selected Region."
            )

        def require_city_municipality(
            self,
            *,
            region_code: str,
            province_code: str | None,
            city_municipality_code: str,
        ):
            if (
                region_code != "1300000000"
                or province_code is not None
                or city_municipality_code != "1380600000"
            ):
                raise PSGCReferenceNotFound(
                    "The selected PSGC City/Municipality does not belong to the selected hierarchy."
                )
            return PSGCReference(city_municipality_code, "City of Manila")

        def require_barangay(self, *, city_municipality_code: str, barangay_code: str):
            raise PSGCReferenceNotFound(
                "The selected PSGC Barangay does not belong to the selected City/Municipality."
            )

    monkeypatch.setattr(
        services.PSGCClient,
        "from_settings",
        classmethod(lambda cls: CanonicalInventoryPSGC()),
    )
