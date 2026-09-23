"""Authenticated COMPASS-owned reference-data facade."""

from __future__ import annotations

from typing import NoReturn

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.integrations.psgc import (
    PSGCClient,
    PSGCConfigurationError,
    PSGCInvalidRequest,
    PSGCInvalidResponse,
    PSGCReference,
    PSGCUnavailable,
)

router = Router(tags=["reference-data"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class PSGCReferenceItem(StrictSchema):
    code: str
    name: str


class PSGCReferenceListResponse(StrictSchema):
    version: str
    items: list[PSGCReferenceItem]


def _raise_psgc(exc: Exception) -> NoReturn:
    if isinstance(exc, PSGCInvalidRequest):
        raise APIError(422, "invalid_psgc_reference_request", str(exc)) from exc
    if isinstance(
        exc,
        (PSGCConfigurationError, PSGCUnavailable, PSGCInvalidResponse),
    ):
        raise APIError(
            503,
            "psgc_reference_unavailable",
            "PSGC reference data is temporarily unavailable.",
        ) from exc
    raise exc


def _payload(client: PSGCClient, rows: tuple[PSGCReference, ...]) -> dict[str, object]:
    return {
        "version": client.version,
        "items": [{"code": row.code, "name": row.name} for row in rows],
    }


@router.get(
    "/regions",
    response=response_with_errors(PSGCReferenceListResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="referenceDataListPSGCRegions",
)
def reference_data_list_psgc_regions(request):
    try:
        client = PSGCClient.from_settings()
        return _payload(client, client.list_regions())
    except (
        PSGCConfigurationError,
        PSGCInvalidRequest,
        PSGCInvalidResponse,
        PSGCUnavailable,
    ) as exc:
        _raise_psgc(exc)


@router.get(
    "/provinces",
    response=response_with_errors(PSGCReferenceListResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="referenceDataListPSGCProvinces",
)
def reference_data_list_psgc_provinces(request, region_code: str):
    try:
        client = PSGCClient.from_settings()
        return _payload(client, client.list_provinces(region_code=region_code))
    except (
        PSGCConfigurationError,
        PSGCInvalidRequest,
        PSGCInvalidResponse,
        PSGCUnavailable,
    ) as exc:
        _raise_psgc(exc)


@router.get(
    "/cities-municipalities",
    response=response_with_errors(PSGCReferenceListResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="referenceDataListPSGCCitiesMunicipalities",
)
def reference_data_list_psgc_cities_municipalities(
    request,
    region_code: str,
    province_code: str | None = None,
):
    try:
        client = PSGCClient.from_settings()
        return _payload(
            client,
            client.list_cities_municipalities(
                region_code=region_code,
                province_code=province_code,
            ),
        )
    except (
        PSGCConfigurationError,
        PSGCInvalidRequest,
        PSGCInvalidResponse,
        PSGCUnavailable,
    ) as exc:
        _raise_psgc(exc)


@router.get(
    "/barangays",
    response=response_with_errors(PSGCReferenceListResponse, 401, 422, 503),
    auth=session_auth,
    operation_id="referenceDataListPSGCBarangays",
)
def reference_data_list_psgc_barangays(request, city_municipality_code: str):
    try:
        client = PSGCClient.from_settings()
        return _payload(
            client,
            client.list_barangays(city_municipality_code=city_municipality_code),
        )
    except (
        PSGCConfigurationError,
        PSGCInvalidRequest,
        PSGCInvalidResponse,
        PSGCUnavailable,
    ) as exc:
        _raise_psgc(exc)
