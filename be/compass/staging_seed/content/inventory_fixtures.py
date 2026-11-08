"""Shared typed answer fixtures; validation stays in the owning Inventory service."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}


@dataclass(frozen=True)
class Sibling:
    name: str
    sex: str
    birth_year: int
    # Explicit attainment for adults; school-age siblings derive their grade from age.
    attainment: str = ""
    occupation: str = ""


@dataclass(frozen=True)
class InventoryYear:
    # (year, month, day, hour, minute) of submission, or of the last draft save for a draft.
    saved_at: tuple[int, int, int, int, int]
    fields: dict[str, object]
    organizations: tuple[tuple[str, str, str], ...] = ()
    transportation: tuple[tuple[str, str, str], ...] = ()
    draft: bool = False


@dataclass(frozen=True)
class InventoryProfile:
    base: dict[str, object]
    father: dict[str, object]
    mother: dict[str, object]
    siblings: tuple[Sibling, ...]
    sibling_position: int
    education: tuple[tuple[str, str, str, str], ...]
    support: dict[str, str]
    years: dict[str, InventoryYear] = field(default_factory=dict)


def _hours(**values: str) -> dict[str, Decimal]:
    # ``class_`` avoids the keyword; the Inventory field is ``daily_hours_class``.
    return {f"daily_hours_{name.rstrip('_')}": Decimal(value) for name, value in values.items()}


def _stable_suffix(text: str) -> int:
    # Deterministic without RNG or process-level hashing, so reruns produce identical answers.
    return sum(ord(character) for character in text if character.isalpha()) % 900 + 100


def _parent(
    name: str,
    *,
    attainment: str,
    occupation: str,
    category: str,
    income: str | None,
    religion: str = "Roman Catholic",
    address: str = "Daet, Camarines Norte",
) -> dict[str, object]:
    suffix = _stable_suffix(name)
    return {
        "name": name,
        "date_of_birth": date(1970 + suffix % 15, 6, 15),
        "place_of_birth": "Daet, Camarines Norte",
        "current_address": address,
        "permanent_address": address,
        "contact_number": f"STG-PARENT-{suffix}",
        "email_address": f"parent.{suffix}@example.edu",
        "educational_attainment": attainment,
        "occupation": occupation,
        "occupation_category": category,
        "annual_income_status": "REPORTED" if income else "NONE",
        "annual_income_previous_year": Decimal(income) if income else None,
        "business_address": "Daet public market, Daet, Camarines Norte",
        "business_telephone": f"STG-BUSINESS-{suffix}",
        "languages_spoken": "Bikol, Tagalog",
        "religion_raised_with": religion,
        "current_religion": religion,
    }


_COMMON_BASE = {
    "nationality": "Filipino",
    "civil_status_category": "SINGLE",
    "languages_spoken_at_home": "Bikol, Tagalog",
    "languages_most_fluent": "Tagalog, English",
    "religion_from_birth": "Roman Catholic",
    "current_religion_category": "ROMAN_CATHOLIC",
    "parent_statuses": ["MARRIED_ANNULLED_LEGALLY_SEPARATED"],
    "pwd_status": "NON_PWD",
    "physical_disadvantage": "None",
    "height": "165 cm",
    "weight": "58 kg",
    "room_sharing_people_count": 2,
    "illness_this_year": "None",
    "previous_illness": "None",
    "accidents_experienced": "None",
    "operations_experienced": "None",
    "handedness": "RIGHT",
    "intended_work_field": "TECHNICAL",
    "reading_preferences": "Community newspapers and short stories.",
    "other_skills_hobbies": "Organizing study notes; basic cooking.",
    "inclination_performing_arts": "Enjoys singing at family gatherings.",
    "inclination_sports": "Plays badminton with classmates.",
    "inclination_leadership": "Leads group work when asked.",
    "prior_counseling_experience": False,
}
