"""Canonical source-owned institutional and GCO document branding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalDocumentBranding:
    country_line: str
    institution_name: str
    institution_short_name: str
    former_institution_name: str | None
    institution_address: str | None
    institution_website_url: str | None
    institution_contact_email: str | None
    institution_social_url: str | None
    office_parent_unit_name: str | None
    office_name: str
    office_email: str | None
    office_phone: str | None
    office_location: str | None


CANONICAL_DOCUMENT_BRANDING = CanonicalDocumentBranding(
    country_line="Republic of the Philippines",
    institution_name="University of Camarines Norte",
    institution_short_name="UCN",
    former_institution_name="Camarines Norte State College",
    institution_address="F. Pimentel Ave., Brgy. II, Daet, Camarines Norte – 4600, Philippines",
    institution_website_url="https://www.ucn.edu.ph",
    institution_contact_email="president@ucn.edu.ph",
    institution_social_url="https://www.facebook.com/UCNofficial",
    office_parent_unit_name=None,
    office_name="Guidance and Counseling Office",
    office_email="guidance@compass-gco.com",
    office_phone=None,
    office_location=None,
)


def get_document_branding() -> CanonicalDocumentBranding:
    """Return the immutable branding definition used by document rendering."""

    return CANONICAL_DOCUMENT_BRANDING


__all__ = [
    "CANONICAL_DOCUMENT_BRANDING",
    "CanonicalDocumentBranding",
    "get_document_branding",
]
