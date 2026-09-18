"""Deterministic packaged assets for document rendering; never remote static URLs."""

from __future__ import annotations

import base64
from importlib.resources import files
from pathlib import PurePosixPath

BRANDING_ASSETS = {
    "ucn_logo": "static/documents/branding/ucn-logo.png",
    "bagong_pilipinas_logo": "static/documents/branding/bagong-pilipinas.png",
    "accreditation_footer": "static/documents/branding/footer.png",
}
PRINT_CSS_PATH = "static/documents/css/print.css"


class DocumentAssetError(RuntimeError):
    pass


def _resource(relative_path: str):
    root = files("compass.documents")
    resource = root
    for part in PurePosixPath(relative_path).parts:
        resource = resource.joinpath(part)
    return resource


def get_asset_bytes(asset_key: str) -> bytes:
    relative_path = BRANDING_ASSETS.get(asset_key)
    if relative_path is None:
        raise DocumentAssetError(f"Unknown document asset: {asset_key}.")
    try:
        return _resource(relative_path).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise DocumentAssetError(f"Packaged document asset is unavailable: {asset_key}.") from exc


def get_asset_data_uri(asset_key: str) -> str:
    payload = base64.b64encode(get_asset_bytes(asset_key)).decode("ascii")
    return f"data:image/png;base64,{payload}"


def get_document_assets(*, include_accreditation_footer: bool) -> dict[str, str | None]:
    return {
        "ucn_logo": get_asset_data_uri("ucn_logo"),
        "bagong_pilipinas_logo": get_asset_data_uri("bagong_pilipinas_logo"),
        "accreditation_footer": (
            get_asset_data_uri("accreditation_footer")
            if include_accreditation_footer
            else None
        ),
    }


def get_print_css() -> str:
    try:
        return _resource(PRINT_CSS_PATH).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise DocumentAssetError("Packaged document print CSS is unavailable.") from exc
