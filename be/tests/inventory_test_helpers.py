from __future__ import annotations

from datetime import date
from uuid import UUID


def ensure_inventory_form_revision() -> None:
    """Restore the migration-seeded Individual Inventory revision after transactional flushes."""

    from compass.institutional_forms.models import FormFamily, FormRevision

    family, _ = FormFamily.objects.get_or_create(
        key="individual_inventory",
        defaults={"title": "Individual Inventory"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        internal_schema_version=1,
        defaults={
            "official_code": "CNSC-OP-GCO-01F5",
            "official_revision": "0",
            "status": "ACTIVE",
        },
    )


def minimum_normalized_inventory_values(
    *,
    program_id: UUID,
    year_level: int = 1,
) -> dict[str, object]:
    """Small explicit submission baseline for tests after profiling normalization."""

    return {
        "program_id": program_id,
        "year_level": year_level,
        "sex": "MALE",
        "date_of_birth": date(2007, 1, 1),
        "civil_status_category": "NOT_SPECIFIED",
        "current_religion_category": "NOT_SPECIFIED",
        "pwd_status": "NOT_SPECIFIED",
        "parent_status_category": "NOT_SPECIFIED",
        "living_arrangement": "OWN_HOUSE",
        "family_members": [
            {
                "kind": "FATHER",
                "occupation_category": "NOT_SPECIFIED",
                "annual_income_status": "NOT_SPECIFIED",
            },
            {
                "kind": "MOTHER",
                "occupation_category": "NOT_SPECIFIED",
                "annual_income_status": "NOT_SPECIFIED",
            },
        ],
        "siblings": [],
        "education_entries": [],
        "organization_memberships": [],
        "transportation_entries": [],
        "support_profile": {
            "four_ps_status": "NOT_SPECIFIED",
            "indigenous_peoples_status": "NOT_SPECIFIED",
            "mother_life_status": "NOT_SPECIFIED",
            "father_life_status": "NOT_SPECIFIED",
        },
        "geographic_locations": [
            {
                "kind": "CURRENT",
                "not_specified": True,
            }
        ],
    }
