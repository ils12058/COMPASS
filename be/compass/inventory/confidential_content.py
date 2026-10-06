"""Explicit Inventory private projections and bound ADR-079 envelopes (ADR-083).

Call only after domain authorization. Models never decrypt or retain logical private fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from types import MappingProxyType
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from compass.confidential_data.crypto import (
    decrypt_bound_json,
    encrypt_bound_json,
    parse_fernet_keyring,
    reencrypt_with_primary_key,
)
from compass.confidential_data.crypto import (
    encrypted_with_primary_key as _is_primary,
)
from compass.confidential_data.errors import ConfidentialDataUnavailable, UnavailableReason

from .errors import InvalidInventoryInput, InventoryError

SETTING = "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
IMMUNIZATIONS = frozenset(
    {
        "CHICKEN_POX",
        "BOOSTER",
        "MEASLES_MMR",
        "HEPATITIS_B",
        "MUMPS",
        "INFLUENZA",
        "SMALL_POX",
        "OTHER",
    }
)
FIELDS = {
    "StudentInventory": {
        "nickname": 100,
        "place_of_birth": 160,
        "nationality": 100,
        "birth_order_among_siblings": 64,
        "civil_status": 80,
        "current_address": None,
        "permanent_address": None,
        "contact_number": 64,
        "email_address": 254,
        "languages_spoken_at_home": None,
        "languages_most_fluent": None,
        "religion_from_birth": 120,
        "current_religion": 120,
        "guardian_name": 160,
        "guardian_relationship": 120,
        "guardian_address": None,
        "guardian_contact_number": 64,
        "emergency_contact_name": 160,
        "emergency_contact_number": 64,
        "friends_in_school": None,
        "friends_outside_school": None,
        "special_interest": None,
        "special_skills_talents": None,
        "hobbies_recreation": None,
        "ambition_goal": None,
        "characteristics": None,
        "boarding_landlord_name": 160,
        "boarding_address": None,
        "accidents_experienced": None,
        "accidents_effect": None,
        "operations_experienced": None,
        "operations_effect": None,
        "immunizations": None,
        "immunization_other": 160,
        "height": 64,
        "weight": 64,
        "physical_disadvantage": None,
        "illness_this_year": None,
        "previous_illness": None,
        "schedule_satisfaction_reason": None,
        "course_choice_other": None,
        "lowest_subjects_grades": None,
        "highest_subjects_grades": None,
        "inclination_performing_arts": None,
        "inclination_sports": None,
        "inclination_leadership": None,
        "other_skills_hobbies": None,
        "desired_extracurricular_activities": None,
        "reading_preferences": None,
        "intended_work_other": 160,
        "prior_counseling_experience": None,
        "prior_counselor_name": 160,
        "prior_counseling_when": 120,
        "prior_counseling_where": 200,
        "current_concerns": None,
        "current_fears": None,
    },
    "InventoryFamilyMember": {
        "name": 160,
        "date_of_birth": None,
        "place_of_birth": 160,
        "current_address": None,
        "permanent_address": None,
        "contact_number": 64,
        "email_address": 254,
        "educational_attainment": 160,
        "occupation": 160,
        "business_address": None,
        "business_telephone": 64,
        "languages_spoken": None,
        "religion_raised_with": 120,
        "current_religion": 120,
    },
    "InventorySibling": {
        "name": 160,
        "sex": 16,
        "age": None,
        "educational_attainment": 160,
        "occupation": 160,
    },
    "InventoryEducationEntry": {
        "school_attended_address": None,
        "inclusive_years": 100,
        "awards_received": None,
    },
    "InventoryOrganizationMembership": {"organization_name": 180, "position_title": 160},
    "InventoryTransportationEntry": {"frequency": 100},
    "InventoryReopenEvent": {"reason": 1000},
}

BINDINGS = {
    "StudentInventory": {"inventory_id": "pk"},
    "InventoryFamilyMember": {
        "inventory_id": "inventory_id",
        "family_member_id": "pk",
        "kind": "kind",
    },
    "InventorySibling": {
        "inventory_id": "inventory_id",
        "sibling_id": "pk",
        "sort_order": "sort_order",
    },
    "InventoryEducationEntry": {
        "inventory_id": "inventory_id",
        "education_entry_id": "pk",
        "level": "level",
    },
    "InventoryOrganizationMembership": {
        "inventory_id": "inventory_id",
        "organization_membership_id": "pk",
        "scope": "scope",
        "sort_order": "sort_order",
    },
    "InventoryTransportationEntry": {
        "inventory_id": "inventory_id",
        "transportation_entry_id": "pk",
        "mode": "mode",
    },
    "InventoryReopenEvent": {"inventory_id": "inventory_id", "reopen_event_id": "pk"},
}

FAMILIES = (
    ("StudentInventory", "confidential_content_ciphertext", None),
    ("InventoryFamilyMember", "confidential_content_ciphertext", "family_members"),
    ("InventorySibling", "confidential_content_ciphertext", "siblings"),
    ("InventoryEducationEntry", "confidential_content_ciphertext", "education_entries"),
    (
        "InventoryOrganizationMembership",
        "confidential_content_ciphertext",
        "organization_memberships",
    ),
    ("InventoryTransportationEntry", "confidential_content_ciphertext", "transportation_entries"),
    ("InventoryReopenEvent", "reason_ciphertext", "reopen_events"),
)


def validate_payload(payload, family):
    fields = FIELDS[family]
    if not isinstance(payload, dict) or set(payload) != set(fields):
        raise ValueError("Invalid Inventory confidential payload")
    for name, maximum in fields.items():
        value = payload[name]
        if name == "prior_counseling_experience":
            if value is not None and type(value) is not bool:
                raise ValueError("Invalid optional boolean")
        elif name == "date_of_birth":
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("Invalid date")
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError("Invalid canonical date")
        elif name == "age":
            if value is not None and (type(value) is not int or not 0 <= value <= 32767):
                raise ValueError("Invalid optional age")
        elif name == "immunizations":
            if not isinstance(value, list) or any(
                not isinstance(entry, str) or entry not in IMMUNIZATIONS for entry in value
            ):
                raise ValueError("Invalid immunizations")
        else:
            if not isinstance(value, str) or "\x00" in value:
                raise ValueError("Invalid text")
            value.encode("utf-8")
            if maximum is not None and len(value) > maximum:
                raise ValueError("Text exceeds its source-field limit")
            if name in {"email_address"} and value:
                validate_email(value)
            if (
                family == "InventorySibling"
                and name == "sex"
                and value not in {"", "MALE", "FEMALE"}
            ):
                raise ValueError("Invalid sex")
            if name == "reason" and not value.strip():
                raise ValueError("Reason is required")
    return payload


def binding(row, family):
    return {key: str(getattr(row, attribute)) for key, attribute in BINDINGS[family].items()}


@dataclass(frozen=True, slots=True)
class InventoryConfidentialContent:
    nickname: str = ""
    place_of_birth: str = ""
    nationality: str = ""
    birth_order_among_siblings: str = ""
    civil_status: str = ""
    current_address: str = ""
    permanent_address: str = ""
    contact_number: str = ""
    email_address: str = ""
    languages_spoken_at_home: str = ""
    languages_most_fluent: str = ""
    religion_from_birth: str = ""
    current_religion: str = ""
    guardian_name: str = ""
    guardian_relationship: str = ""
    guardian_address: str = ""
    guardian_contact_number: str = ""
    emergency_contact_name: str = ""
    emergency_contact_number: str = ""
    friends_in_school: str = ""
    friends_outside_school: str = ""
    special_interest: str = ""
    special_skills_talents: str = ""
    hobbies_recreation: str = ""
    ambition_goal: str = ""
    characteristics: str = ""
    boarding_landlord_name: str = ""
    boarding_address: str = ""
    accidents_experienced: str = ""
    accidents_effect: str = ""
    operations_experienced: str = ""
    operations_effect: str = ""
    immunizations: tuple[str, ...] = ()
    immunization_other: str = ""
    height: str = ""
    weight: str = ""
    physical_disadvantage: str = ""
    illness_this_year: str = ""
    previous_illness: str = ""
    schedule_satisfaction_reason: str = ""
    course_choice_other: str = ""
    lowest_subjects_grades: str = ""
    highest_subjects_grades: str = ""
    inclination_performing_arts: str = ""
    inclination_sports: str = ""
    inclination_leadership: str = ""
    other_skills_hobbies: str = ""
    desired_extracurricular_activities: str = ""
    reading_preferences: str = ""
    intended_work_other: str = ""
    prior_counseling_experience: bool | None = None
    prior_counselor_name: str = ""
    prior_counseling_when: str = ""
    prior_counseling_where: str = ""
    current_concerns: str = ""
    current_fears: str = ""

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        values["immunizations"] = list(self.immunizations)
        return values


@dataclass(frozen=True, slots=True)
class InventoryFamilyMemberConfidentialContent:
    name: str = ""
    date_of_birth: date | None = None
    place_of_birth: str = ""
    current_address: str = ""
    permanent_address: str = ""
    contact_number: str = ""
    email_address: str = ""
    educational_attainment: str = ""
    occupation: str = ""
    business_address: str = ""
    business_telephone: str = ""
    languages_spoken: str = ""
    religion_raised_with: str = ""
    current_religion: str = ""

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        values["date_of_birth"] = self.date_of_birth.isoformat() if self.date_of_birth else None
        return values


@dataclass(frozen=True, slots=True)
class InventorySiblingConfidentialContent:
    name: str = ""
    sex: str = ""
    age: int | None = None
    educational_attainment: str = ""
    occupation: str = ""

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        return values


@dataclass(frozen=True, slots=True)
class InventoryEducationEntryConfidentialContent:
    school_attended_address: str = ""
    inclusive_years: str = ""
    awards_received: str = ""

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        return values


@dataclass(frozen=True, slots=True)
class InventoryOrganizationMembershipConfidentialContent:
    organization_name: str = ""
    position_title: str = ""

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        return values


@dataclass(frozen=True, slots=True)
class InventoryTransportationConfidentialContent:
    frequency: str = ""

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        return values


@dataclass(frozen=True, slots=True)
class InventoryReopenReason:
    reason: str

    def payload(self) -> dict[str, object]:
        values = asdict(self)
        return values


PROJECTIONS = {
    "StudentInventory": InventoryConfidentialContent,
    "InventoryFamilyMember": InventoryFamilyMemberConfidentialContent,
    "InventorySibling": InventorySiblingConfidentialContent,
    "InventoryEducationEntry": InventoryEducationEntryConfidentialContent,
    "InventoryOrganizationMembership": InventoryOrganizationMembershipConfidentialContent,
    "InventoryTransportationEntry": InventoryTransportationConfidentialContent,
    "InventoryReopenEvent": InventoryReopenReason,
}


class InventoryConfidentialContentUnavailable(InventoryError):
    """Only typed structural context and a bounded ADR-079 reason; never content."""

    def __init__(self, row, *, reason: UnavailableReason) -> None:
        self.inventory_id = row.pk if type(row).__name__ == "StudentInventory" else row.inventory_id
        self.object_id = row.pk
        self.family = type(row).__name__
        if self.family not in FIELDS or reason not in {
            "missing",
            "undecryptable",
            "malformed",
            "unsupported_schema",
            "binding_mismatch",
        }:
            raise ValueError("Invalid Inventory failure context")
        self.reason = reason
        super().__init__("The Individual Inventory confidential content is unavailable.")


def keyring():
    return parse_fernet_keyring(getattr(settings, SETTING, ""), setting=SETTING)


def _column(family):
    return (
        "reason_ciphertext"
        if family == "InventoryReopenEvent"
        else "confidential_content_ciphertext"
    )


def _payload(values, family):
    payload = dict(values)
    if "date_of_birth" in payload and type(payload["date_of_birth"]) is date:
        payload["date_of_birth"] = payload["date_of_birth"].isoformat()
    if "immunizations" in payload and isinstance(payload["immunizations"], tuple):
        payload["immunizations"] = list(payload["immunizations"])
    return validate_payload(payload, family)


def project_confidential_input(values, family):
    """Validate logical input before encryption and return a frozen typed projection."""
    if hasattr(values, "payload"):
        values = values.payload()
    try:
        payload = _payload(values, family)
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise InvalidInventoryInput(
            "The Inventory confidential content contains invalid values."
        ) from None
    return _projection(payload, family)


def _projection(payload, family):
    payload = dict(payload)
    if "date_of_birth" in payload and payload["date_of_birth"] is not None:
        payload["date_of_birth"] = date.fromisoformat(payload["date_of_birth"])
    if "immunizations" in payload:
        payload["immunizations"] = tuple(payload["immunizations"])
    return PROJECTIONS[family](**payload)


def write_confidential_content(row, values) -> None:
    family = type(row).__name__
    projection = project_confidential_input(values, family)
    token = encrypt_bound_json(
        keyring=keyring(),
        schema_version=1,
        binding=binding(row, family),
        payload=projection.payload(),
    )
    setattr(row, _column(family), token)


def initial_confidential_content(row) -> None:
    write_confidential_content(row, PROJECTIONS[type(row).__name__]())


def read_confidential_content(row):
    family = type(row).__name__
    try:
        payload = decrypt_bound_json(
            getattr(row, _column(family)),
            keyring=keyring(),
            schema_version=1,
            binding=binding(row, family),
        )
        try:
            validate_payload(payload, family)
        except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
            raise ConfidentialDataUnavailable(reason="malformed") from None
    except ConfidentialDataUnavailable as exc:
        raise InventoryConfidentialContentUnavailable(row, reason=exc.reason) from None
    return _projection(payload, family)


@dataclass(frozen=True, slots=True)
class InventoryPrivateProjection:
    root: InventoryConfidentialContent
    children: Mapping[UUID, object]


def read_inventory_private_projection(item) -> InventoryPrivateProjection:
    root = read_confidential_content(item)
    children = {
        row.pk: read_confidential_content(row)
        for _name, _column_name, relation in FAMILIES[1:-1]
        for row in getattr(item, relation).all()
    }
    return InventoryPrivateProjection(root, MappingProxyType(children))


def read_reopen_reason(event) -> str:
    return read_confidential_content(event).reason


def encrypted_with_primary_key(token) -> bool:
    return _is_primary(token, keyring=keyring())


def reencrypt_confidential_content(row) -> str:
    read_confidential_content(row)
    return reencrypt_with_primary_key(getattr(row, _column(type(row).__name__)), keyring=keyring())
