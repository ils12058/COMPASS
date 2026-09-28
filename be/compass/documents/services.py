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
    institution_address=None,
    institution_website_url=None,
    institution_contact_email=None,
    institution_social_url=None,
    office_parent_unit_name=None,
    office_name="Guidance and Counseling Office",
    office_email=None,
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
