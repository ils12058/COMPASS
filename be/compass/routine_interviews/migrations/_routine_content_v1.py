"""Frozen version-1 Routine Interview content helpers for migrations 0002 and 0003 (ADR-066).

Migrations must keep producing exactly the format they were written for, so these helpers
deliberately copy the v1 field lists, concern values, and envelope instead of importing application
code that may evolve. Do not change their behavior; a new payload schema needs its own helpers.
The leading underscore keeps Django's migration loader from treating this module as a migration.

Errors name only the Routine Interview UUID, the section, and a safe reason; they never contain
plaintext, ciphertext, or key material.
"""

import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

SCHEMA_VERSION = 1
STUDENT_INTAKE = "student_intake"
COUNSELOR_EVALUATION = "counselor_evaluation"
INTAKE_FIELDS = (
    "coping_with_college_challenges",
    "coping_remarks",
    "college_experience",
    "reason_for_choosing_institution",
    "difficulties_encountered",
    "stress_anxiety_causes",
    "stress_anxiety_management",
    "family_description",
    "concerns",
    "other_concern_specification",
    "concerns_explanation",
    "college_adjustment_and_peer_group",
    "academic_goals",
    "career_goals",
)
RATING_FIELDS = (
    "academic_adjustment_rating",
    "physical_adjustment_rating",
    "social_adjustment_rating",
    "spiritual_adjustment_rating",
    "financial_adjustment_rating",
    "emotional_adjustment_rating",
)
EVALUATION_FIELDS = (*RATING_FIELDS, "other_adjustment", "special_concern", "recommendations")
SECTION_FIELDS = {STUDENT_INTAKE: INTAKE_FIELDS, COUNSELOR_EVALUATION: EVALUATION_FIELDS}
LEGACY_COLUMNS = (*INTAKE_FIELDS, *EVALUATION_FIELDS)
CIPHERTEXT_COLUMNS = {
    STUDENT_INTAKE: "student_intake_ciphertext",
    COUNSELOR_EVALUATION: "counselor_evaluation_ciphertext",
}
CONCERN_VALUES = frozenset(
    {
        "FAMILY",
        "FINANCIAL",
        "ACADEMIC",
        "FRIENDS",
        "CLASSMATES",
        "VICES",
        "LOVE_LIFE",
        "SLEEPING_PROBLEMS",
        "SUICIDAL_THOUGHT_TENDENCY",
        "DORM_BOARDING_HOUSE",
        "PAST_PAINFUL_EXPERIENCE",
        "OTHER",
    }
)


class ContentMigrationError(RuntimeError):
    """Routine Interview content could not be migrated safely; the migration rolls back."""


def failure(routine_interview_id, section, reason):
    return ContentMigrationError(
        f"Routine Interview {routine_interview_id} {section} could not be migrated: {reason}."
    )


def keyring():
    configured = getattr(settings, "ROUTINE_INTERVIEW_ENCRYPTION_KEYS", ())
    if isinstance(configured, str):
        configured = [entry.strip() for entry in configured.split(",") if entry.strip()]
    try:
        fernets = [Fernet(key) for key in configured]
    except (TypeError, ValueError):
        fernets = []
    if not fernets:
        raise ContentMigrationError(
            "ROUTINE_INTERVIEW_ENCRYPTION_KEYS must be a valid Fernet keyring before Routine "
            "Interview content can be migrated; no content was changed."
        )
    return MultiFernet(fernets)


def legacy_payloads(row):
    """The exact v1 section payloads held in a row's legacy plaintext columns."""

    intake = {field: getattr(row, field) for field in INTAKE_FIELDS}
    evaluation = {field: getattr(row, field) for field in EVALUATION_FIELDS}
    concerns = intake["concerns"]
    if (
        not isinstance(concerns, list)
        or any(value not in CONCERN_VALUES for value in concerns)
        or len(set(concerns)) != len(concerns)
    ):
        raise failure(row.pk, STUDENT_INTAKE, "unsupported or repeated concern value")
    for section, payload in ((STUDENT_INTAKE, intake), (COUNSELOR_EVALUATION, evaluation)):
        for field, value in payload.items():
            if field == "concerns":
                continue
            if field in RATING_FIELDS:
                if value is not None and (type(value) is not int or not 1 <= value <= 10):
                    raise failure(row.pk, section, f"{field} is outside 1-10")
            elif not isinstance(value, str):
                raise failure(row.pk, section, f"{field} is not text")
    return {STUDENT_INTAKE: intake, COUNSELOR_EVALUATION: evaluation}


def encrypt(ring, routine_interview_id, section, payload):
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "routine_interview_id": str(routine_interview_id),
        "section": section,
        "payload": payload,
    }
    plaintext = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return ring.encrypt(plaintext).decode("ascii")


def decrypt(ring, token, routine_interview_id, section):
    """The v1 payload bound to this row and section, or ``None`` when it cannot be verified."""

    if not isinstance(token, str) or not token:
        return None
    try:
        envelope = json.loads(ring.decrypt(token.encode("ascii")).decode("utf-8"))
    except (InvalidToken, UnicodeError, ValueError):
        return None
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema_version", "routine_interview_id", "section", "payload"}
        or type(envelope["schema_version"]) is not int
        or envelope["schema_version"] != SCHEMA_VERSION
        or envelope["routine_interview_id"] != str(routine_interview_id)
        or envelope["section"] != section
        or not isinstance(envelope["payload"], dict)
        or set(envelope["payload"]) != set(SECTION_FIELDS[section])
    ):
        return None
    return envelope["payload"]
