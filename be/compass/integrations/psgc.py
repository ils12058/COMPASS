"""Official PSA Philippine Standard Geographic Code integration boundary."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("compass.psgc")

_CODE_RE = re.compile(r"^\d{10}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PAGE_SIZE = 1000
_MAX_PAGES = 100


class PSGCError(RuntimeError):
    """Base class for sanitized PSGC integration failures."""


class PSGCConfigurationError(PSGCError):
    pass


class PSGCUnavailable(PSGCError):
    pass


class PSGCInvalidResponse(PSGCError):
    pass


class PSGCInvalidRequest(PSGCError):
    pass


class PSGCReferenceNotFound(PSGCError):
    pass


@dataclass(frozen=True, slots=True)
class PSGCReference:
    code: str
    name: str
    geographic_level: str = ""
    reg: int = 0
    prv: int = 0
    mun: int = 0
    bgy: int = 0


class PSGCClient:
    def __init__(
        self,
        token: str,
        *,
        version: str,
        base_url: str,
        timeout_seconds: float,
        cache_ttl_seconds: int,
    ) -> None:
        if not token:
            raise PSGCConfigurationError("PSGC API token is not configured.")
        if not version or not _VERSION_RE.fullmatch(version):
            raise PSGCConfigurationError("PSGC version is not configured correctly.")
        if not base_url:
            raise PSGCConfigurationError("PSGC API base URL is not configured.")
        if timeout_seconds <= 0:
            raise PSGCConfigurationError("PSGC HTTP timeout must be positive.")
        if cache_ttl_seconds <= 0:
            raise PSGCConfigurationError("PSGC cache TTL must be positive.")
        self.token = token
        self.version = version
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.cache_ttl_seconds = int(cache_ttl_seconds)

    @classmethod
    def from_settings(cls) -> PSGCClient:
        return cls(
            settings.PSGC_API_TOKEN,
            version=settings.PSGC_VERSION,
            base_url=settings.PSGC_API_BASE_URL,
            timeout_seconds=settings.PSGC_HTTP_TIMEOUT_SECONDS,
            cache_ttl_seconds=settings.PSGC_CACHE_TTL_SECONDS,
        )

    @staticmethod
    def validate_code(code: str, *, label: str = "PSGC code") -> str:
        if not isinstance(code, str):
            raise PSGCInvalidRequest(f"{label} must be text.")
        normalized = code.strip()
        if not _CODE_RE.fullmatch(normalized):
            raise PSGCInvalidRequest(f"{label} must be a 10-digit PSGC code.")
        return normalized

    @staticmethod
    def _safe_int(value: object) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return 0

    def _cache_key(self, level: str, filters: dict[str, int]) -> str:
        parts = [self.version, level]
        parts.extend(f"{key}-{filters[key]}" for key in sorted(filters))
        return "psgc:" + ":".join(parts)

    def _request_page(
        self,
        *,
        level: str,
        filters: dict[str, int],
        page: int,
    ) -> tuple[PSGCReference, ...]:
        query: dict[str, object] = {
            "token": self.token,
            "page": page,
            "page_size": _PAGE_SIZE,
        }
        query.update(filters)
        url = (
            f"{self.base_url}/{quote(self.version, safe='')}/{quote(level, safe='')}"
            f"?{urlencode(query)}"
        )
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            logger.warning(
                "PSGC upstream HTTP failure",
                extra={
                    "event": "psgc_http_failure",
                    "operation": level,
                    "version": self.version,
                    "status_code": int(exc.code),
                },
            )
            raise PSGCUnavailable("PSGC reference service is temporarily unavailable.") from None
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "PSGC transport failure",
                extra={
                    "event": "psgc_transport_failure",
                    "operation": level,
                    "version": self.version,
                },
            )
            raise PSGCUnavailable("PSGC reference service is temporarily unavailable.") from exc

        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise PSGCInvalidResponse("PSGC reference service returned invalid JSON.") from exc
        rows = self._extract_rows(payload)
        return tuple(self._normalize_row(row) for row in rows)

    @staticmethod
    def _extract_rows(payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, dict):
            raise PSGCInvalidResponse("PSGC reference service returned an invalid response shape.")
        results = payload.get("results")
        rows: object = None
        if isinstance(results, dict):
            rows = results.get("psgc_data")
        elif isinstance(results, list):
            rows = results
        if rows is None:
            rows = payload.get("psgc_data")
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise PSGCInvalidResponse("PSGC reference service returned an invalid response shape.")
        return rows

    def _normalize_row(self, row: dict[str, object]) -> PSGCReference:
        code = row.get("psgc_code")
        name = row.get("area_name")
        if not isinstance(code, str) or not _CODE_RE.fullmatch(code.strip()):
            raise PSGCInvalidResponse("PSGC reference service returned an invalid code.")
        if not isinstance(name, str) or not name.strip():
            raise PSGCInvalidResponse("PSGC reference service returned an invalid name.")
        geographic_level = row.get("geographic_level")
        return PSGCReference(
            code=code.strip(),
            name=name.strip(),
            geographic_level=(
                geographic_level.strip() if isinstance(geographic_level, str) else ""
            ),
            reg=self._safe_int(row.get("reg")),
            prv=self._safe_int(row.get("prv")),
            mun=self._safe_int(row.get("mun")),
            bgy=self._safe_int(row.get("bgy")),
        )

    def _list(self, level: str, **filters: int) -> tuple[PSGCReference, ...]:
        clean_filters = {
            key: int(value)
            for key, value in filters.items()
            if key in {"reg", "prv", "mun", "bgy"} and int(value) > 0
        }
        cache_key = self._cache_key(level, clean_filters)
        cached = cache.get(cache_key)
        if isinstance(cached, list):
            try:
                return tuple(PSGCReference(**item) for item in cached)
            except (TypeError, ValueError):
                cache.delete(cache_key)

        collected: list[PSGCReference] = []
        for page in range(1, _MAX_PAGES + 1):
            rows = self._request_page(level=level, filters=clean_filters, page=page)
            collected.extend(rows)
            if len(rows) < _PAGE_SIZE:
                break
        else:
            raise PSGCInvalidResponse("PSGC reference pagination exceeded the safety limit.")

        normalized = tuple(sorted(collected, key=lambda item: (item.name.casefold(), item.code)))
        cache.set(
            cache_key,
            [asdict(item) for item in normalized],
            timeout=self.cache_ttl_seconds,
        )
        return normalized

    @staticmethod
    def _find(
        rows: tuple[PSGCReference, ...],
        code: str,
    ) -> PSGCReference | None:
        return next((row for row in rows if row.code == code), None)

    @staticmethod
    def _component(code: str, start: int, end: int) -> int:
        value = code[start:end]
        return int(value) if value.isdigit() else 0

    def list_regions(self) -> tuple[PSGCReference, ...]:
        return self._list("regions")

    def list_provinces(self, *, region_code: str) -> tuple[PSGCReference, ...]:
        region_code = self.validate_code(region_code, label="region_code")
        region = self._find(self.list_regions(), region_code)
        if region is None:
            return ()
        reg = region.reg or self._component(region.code, 0, 2)
        return self._list("provinces", reg=reg)

    def list_cities_municipalities(
        self,
        *,
        region_code: str,
        province_code: str | None = None,
    ) -> tuple[PSGCReference, ...]:
        region_code = self.validate_code(region_code, label="region_code")
        region = self._find(self.list_regions(), region_code)
        if region is None:
            return ()
        filters = {"reg": region.reg or self._component(region.code, 0, 2)}
        if province_code:
            province_code = self.validate_code(province_code, label="province_code")
            province = self._find(self.list_provinces(region_code=region_code), province_code)
            if province is None:
                return ()
            filters["prv"] = province.prv or self._component(province.code, 2, 5)
        return self._list("municipalities", **filters)

    def list_barangays(
        self,
        *,
        city_municipality_code: str,
    ) -> tuple[PSGCReference, ...]:
        city_code = self.validate_code(
            city_municipality_code,
            label="city_municipality_code",
        )
        region_code = f"{city_code[:2]}00000000"
        city = self._find(
            self.list_cities_municipalities(region_code=region_code),
            city_code,
        )
        if city is None:
            return ()
        filters = {"reg": city.reg or self._component(city.code, 0, 2)}
        prv = city.prv or self._component(city.code, 2, 5)
        mun = city.mun or self._component(city.code, 5, 7)
        if prv:
            filters["prv"] = prv
        if mun:
            filters["mun"] = mun
        return self._list("barangays", **filters)

    def require_region(self, code: str) -> PSGCReference:
        normalized = self.validate_code(code, label="region_psgc_code")
        row = self._find(self.list_regions(), normalized)
        if row is None:
            raise PSGCReferenceNotFound("The selected PSGC Region was not found.")
        return row

    def require_province(self, *, region_code: str, province_code: str) -> PSGCReference:
        normalized = self.validate_code(province_code, label="province_psgc_code")
        row = self._find(self.list_provinces(region_code=region_code), normalized)
        if row is None:
            raise PSGCReferenceNotFound(
                "The selected PSGC Province does not belong to the selected Region."
            )
        return row

    def require_city_municipality(
        self,
        *,
        region_code: str,
        province_code: str | None,
        city_municipality_code: str,
    ) -> PSGCReference:
        normalized = self.validate_code(
            city_municipality_code,
            label="city_municipality_psgc_code",
        )
        row = self._find(
            self.list_cities_municipalities(
                region_code=region_code,
                province_code=province_code or None,
            ),
            normalized,
        )
        if row is None:
            raise PSGCReferenceNotFound(
                "The selected PSGC City/Municipality does not belong to the selected hierarchy."
            )
        return row

    def require_barangay(
        self,
        *,
        city_municipality_code: str,
        barangay_code: str,
    ) -> PSGCReference:
        normalized = self.validate_code(barangay_code, label="barangay_psgc_code")
        row = self._find(
            self.list_barangays(city_municipality_code=city_municipality_code),
            normalized,
        )
        if row is None:
            raise PSGCReferenceNotFound(
                "The selected PSGC Barangay does not belong to the selected City/Municipality."
            )
        return row
