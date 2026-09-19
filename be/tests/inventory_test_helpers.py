from __future__ import annotations

from datetime import date
from uuid import UUID


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
        "physical_disadvantage_status": "NOT_SPECIFIED",
        "parent_status_category": "NOT_SPECIFIED",
        "living_arrangement": "OWN_HOUSE",
        "family_members": [
            {
                "kind": "FATHER",
                "life_status": "NOT_SPECIFIED",
                "occupation_category": "NOT_SPECIFIED",
                "annual_income_status": "NOT_SPECIFIED",
            },
            {
                "kind": "MOTHER",
                "life_status": "NOT_SPECIFIED",
                "occupation_category": "NOT_SPECIFIED",
                "annual_income_status": "NOT_SPECIFIED",
            },
        ],
        "siblings": [],
        "education_entries": [],
        "organization_memberships": [],
        "transportation_entries": [],
        "geographic_locations": [
            {
                "kind": "CURRENT",
                "not_specified": True,
            }
        ],
    }
