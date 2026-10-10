"""Privacy-safe names for record-specific institutional PDF downloads."""

from __future__ import annotations

from uuid import UUID

_PDF_PREFIXES = {
    "individual_inventory": "individual-inventory",
    "exit_interview": "exit-interview",
    "good_moral": "good-moral",
    "referral_slip": "referral-slip",
    "call_slip": "call-slip",
}


def institutional_pdf_filename(kind: str, record_id: UUID) -> str:
    return f"{_PDF_PREFIXES[kind]}-{record_id}.pdf"


def institutional_pdf_content_disposition(kind: str, record_id: UUID) -> str:
    return f'attachment; filename="{institutional_pdf_filename(kind, record_id)}"'
