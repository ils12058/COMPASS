"""Frozen ADR-083 v1: independent of evolving runtime/domain adapters.

Owns historical exact field limits, bindings, canonical JSON, keyring parsing and consistency.
Legacy NULL normalized categories remain NULL and their source text is retained exactly.
"""

import base64
import binascii
import json
from datetime import date

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

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


def keyring():
    configured = getattr(settings, SETTING, "")
    entries = configured.split(",") if isinstance(configured, str) else configured
    if not isinstance(entries, (list, tuple)) or not entries:
        raise RuntimeError(f"{SETTING} is required for Inventory migration")
    keys, seen = [], set()
    for position, entry in enumerate(entries, start=1):
        key = entry.strip() if isinstance(entry, str) else ""
        try:
            raw = base64.urlsafe_b64decode(key.encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError):
            raw = b""
        if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii") != key:
            raise RuntimeError(f"{SETTING} entry {position} is invalid")
        if raw in seen:
            raise RuntimeError(f"{SETTING} entry {position} repeats an earlier key")
        seen.add(raw)
        keys.append(Fernet(key))
    return MultiFernet(keys)


def binding(row, family):
    return {key: str(getattr(row, attribute)) for key, attribute in BINDINGS[family].items()}


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


def failure(row, reason, family):
    return RuntimeError(f"Inventory {family} {row.pk}: {reason}; migration stopped")


CIVIL_LABELS = {
    "SINGLE": "Single",
    "MARRIED": "Married",
    "SOLO_PARENT": "Solo Parent",
    "OTHER": "Other",
    "NOT_SPECIFIED": "Not specified",
}
RELIGION_LABELS = {
    "ROMAN_CATHOLIC": "Roman Catholic",
    "BORN_AGAIN": "Born Again",
    "IGLESIA_NI_CRISTO": "Iglesia Ni Cristo",
    "MORMON": "Mormon",
    "JEHOVAHS_WITNESS": "Jehovah's Witness",
    "SEVENTH_DAY_ADVENTIST": "Seventh Day Adventist",
    "CHURCH_OF_CHRIST": "Church Of Christ",
    "EVANGELICAL_CHRISTIAN": "Evangelical Christian",
    "MGCI": "MGCI",
    "BAPTIST": "Baptist",
    "PMCC": "PMCC",
    "NONE": "None",
    "OTHER": "Other",
    "NOT_SPECIFIED": "Not specified",
}


def consistency(row, payload, family):
    if family == "StudentInventory":
        if payload["prior_counseling_experience"] is False and any(
            payload[name].strip()
            for name in ("prior_counselor_name", "prior_counseling_when", "prior_counseling_where")
        ):
            raise ValueError("Invalid prior counseling")
        if row.living_arrangement != "BOARDING_HOUSE" and (
            row.boarding_exclusive is not None
            or payload["boarding_landlord_name"].strip()
            or payload["boarding_address"].strip()
        ):
            raise ValueError("Invalid boarding details")
        # Nullable pre-normalization controls intentionally preserve legacy source answers.
        for category, detail, labels in (
            (row.civil_status_category, payload["civil_status"], CIVIL_LABELS),
            (row.current_religion_category, payload["current_religion"], RELIGION_LABELS),
        ):
            if category == "OTHER" and not detail.strip():
                raise ValueError("Missing other detail")
            if category == "NOT_SPECIFIED" and detail:
                raise ValueError("Unexpected not-specified detail")
            if category in labels and category not in {"OTHER", "NOT_SPECIFIED"}:
                if detail != labels[category]:
                    raise ValueError("Invalid normalized source snapshot")
        if row.pwd_status == "PWD" and not payload["physical_disadvantage"].strip():
            raise ValueError("Missing PWD detail")
        if row.pwd_status in {"NON_PWD", "NOT_SPECIFIED"} and payload["physical_disadvantage"]:
            raise ValueError("Unexpected PWD detail")
        # Submission-only completeness rules must not reject legitimate partial drafts.
        if row.submitted_at is not None:
            if "OTHER" in payload["immunizations"] and not payload["immunization_other"].strip():
                raise ValueError("Missing immunization detail")
            if "OTHER" in row.course_choice_reasons and not payload["course_choice_other"].strip():
                raise ValueError("Missing course detail")
            if row.intended_work_field == "OTHER" and not payload["intended_work_other"].strip():
                raise ValueError("Missing intended work detail")
    elif family == "InventoryFamilyMember":
        if row.occupation_category == "OTHER" and not payload["occupation"].strip():
            raise ValueError("Missing occupation detail")
        if row.occupation_category in {"NONE", "NOT_SPECIFIED"} and payload["occupation"]:
            raise ValueError("Unexpected occupation detail")
    elif family == "InventoryTransportationEntry":
        if row.frequency_category == "OTHER" and not payload["frequency"].strip():
            raise ValueError("Missing frequency detail")
        labels = {
            "DAILY": "Daily",
            "SEVERAL_TIMES_A_WEEK": "Several times a week",
            "WEEKLY": "Weekly",
            "OCCASIONAL": "Occasional",
            "NOT_SPECIFIED": "",
        }
        if (
            row.frequency_category in labels
            and payload["frequency"] != labels[row.frequency_category]
        ):
            raise ValueError("Invalid normalized frequency")


def validate(row, payload, family, *, check_consistency=True):
    try:
        validate_payload(payload, family)
        if check_consistency:
            consistency(row, payload, family)
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise failure(row, "malformed", family) from None
    return payload


def plaintext(row, family):
    payload = {name: getattr(row, name) for name in FIELDS[family]}
    if "date_of_birth" in payload and payload["date_of_birth"] is not None:
        payload["date_of_birth"] = payload["date_of_birth"].isoformat()
    return validate(row, payload, family)


def encrypt(ring, row, payload, family):
    validate(row, payload, family)
    envelope = {"schema_version": 1, **binding(row, family), "payload": payload}
    raw = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return ring.encrypt(raw).decode("ascii")


def _reject_constant(_value):
    raise ValueError("Non-finite JSON")


def decrypt(ring, row, token, family, *, check_consistency=True):
    if not isinstance(token, str) or not token:
        raise failure(row, "missing", family)
    try:
        raw = ring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise failure(row, "undecryptable", family) from None
    try:
        envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise failure(row, "malformed", family) from None
    expected = binding(row, family)
    if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "payload", *expected}:
        raise failure(row, "malformed", family)
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise failure(row, "unsupported_schema", family)
    if any(envelope[name] != value for name, value in expected.items()):
        raise failure(row, "binding_mismatch", family)
    return validate(row, envelope["payload"], family, check_consistency=check_consistency)
