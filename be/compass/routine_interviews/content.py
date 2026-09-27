"""Routine Interview section content: schemas, canonical defaults, and explicit accessors.

Student Intake and Counselor Evaluation exist only as ciphertext on ``RoutineInterview``. Resolve
an authorized Routine Interview first, then call ``read_intake``/``read_evaluation``. Nothing here
decrypts implicitly during queryset iteration, ``repr()``, logging, or serialization.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from .crypto import RoutineContentSection, decrypt_section, encrypt_section
from .errors import RoutineContentUnavailable
from .models import RoutineConcern, RoutineInterview

# Student Intake — source Questions 1–7.
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
# Counselor Evaluation — the six source 1–10 adjustment ratings and three text fields.
RATING_FIELDS = (
    "academic_adjustment_rating",
    "physical_adjustment_rating",
    "social_adjustment_rating",
    "spiritual_adjustment_rating",
    "financial_adjustment_rating",
    "emotional_adjustment_rating",
)
EVALUATION_FIELDS = (*RATING_FIELDS, "other_adjustment", "special_concern", "recommendations")
CIPHERTEXT_COLUMNS = {
    RoutineContentSection.STUDENT_INTAKE: "student_intake_ciphertext",
    RoutineContentSection.COUNSELOR_EVALUATION: "counselor_evaluation_ciphertext",
}


class InvalidRoutineContent(ValueError):
    """Section values do not match the section schema. Messages name fields, never values."""


def empty_intake() -> dict[str, object]:
    return {field: [] if field == "concerns" else "" for field in INTAKE_FIELDS}


def empty_evaluation() -> dict[str, object]:
    return {field: None if field in RATING_FIELDS else "" for field in EVALUATION_FIELDS}


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise InvalidRoutineContent(f"{field} must be text.")
    # PostgreSQL text rejected NUL before encryption; keep that input rule, and keep every value
    # encodable so the stored JSON round-trips exactly.
    if "\x00" in value:
        raise InvalidRoutineContent(f"{field} contains an unsupported character.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidRoutineContent(f"{field} contains an unsupported character.") from None
    return str(value)


def _concerns(value: object) -> list[str]:
    if not isinstance(value, list):
        raise InvalidRoutineContent("concerns must be a list of source-backed values.")
    allowed = set(RoutineConcern.values)
    concerns: list[str] = []
    for item in value:
        if not isinstance(item, str) or str(item) not in allowed:
            raise InvalidRoutineContent("concerns contains an unsupported source value.")
        if str(item) in concerns:
            raise InvalidRoutineContent("concerns contains a repeated value.")
        concerns.append(str(item))
    return concerns


def _rating(value: object, field: str) -> int | None:
    if value is not None and (type(value) is not int or not 1 <= value <= 10):
        raise InvalidRoutineContent(f"{field} must be between 1 and 10 when supplied.")
    return value


def validate_intake(values: Mapping[str, object]) -> dict[str, object]:
    """Return a canonical copy of a complete Student Intake, in source order."""

    if not isinstance(values, Mapping) or set(values) != set(INTAKE_FIELDS):
        raise InvalidRoutineContent("The Student Intake does not match its content schema.")
    return {
        field: _concerns(values[field]) if field == "concerns" else _text(values[field], field)
        for field in INTAKE_FIELDS
    }


def validate_evaluation(values: Mapping[str, object]) -> dict[str, object]:
    """Return a canonical copy of a complete Counselor Evaluation, in source order."""

    if not isinstance(values, Mapping) or set(values) != set(EVALUATION_FIELDS):
        raise InvalidRoutineContent("The Counselor Evaluation does not match its content schema.")
    return {
        field: (
            _rating(values[field], field) if field in RATING_FIELDS else _text(values[field], field)
        )
        for field in EVALUATION_FIELDS
    }


_VALIDATORS: dict[RoutineContentSection, Callable[[Mapping[str, object]], dict[str, object]]] = {
    RoutineContentSection.STUDENT_INTAKE: validate_intake,
    RoutineContentSection.COUNSELOR_EVALUATION: validate_evaluation,
}


def read_section(item: RoutineInterview, section: RoutineContentSection) -> dict[str, object]:
    """Decrypt and validate one section of an already authorized Routine Interview.

    Unreadable, rebound, or malformed content raises ``RoutineContentUnavailable``; it is never
    returned as plaintext, as an empty form, or partially.
    """

    payload = decrypt_section(
        getattr(item, CIPHERTEXT_COLUMNS[section]),
        routine_interview_id=item.pk,
        section=section,
    )
    try:
        return _VALIDATORS[section](payload)
    except InvalidRoutineContent:
        raise RoutineContentUnavailable(
            routine_interview_id=item.pk,
            section=section,
            reason="invalid_payload",
        ) from None


def read_intake(item: RoutineInterview) -> dict[str, object]:
    return read_section(item, RoutineContentSection.STUDENT_INTAKE)


def read_evaluation(item: RoutineInterview) -> dict[str, object]:
    return read_section(item, RoutineContentSection.COUNSELOR_EVALUATION)


def write_intake(item: RoutineInterview, values: Mapping[str, object]) -> None:
    """Validate and encrypt a complete Student Intake onto ``item``; the caller saves it."""

    item.student_intake_ciphertext = encrypt_section(
        routine_interview_id=item.pk,
        section=RoutineContentSection.STUDENT_INTAKE,
        payload=validate_intake(values),
    )


def write_evaluation(item: RoutineInterview, values: Mapping[str, object]) -> None:
    """Validate and encrypt a complete Counselor Evaluation onto ``item``; the caller saves it."""

    item.counselor_evaluation_ciphertext = encrypt_section(
        routine_interview_id=item.pk,
        section=RoutineContentSection.COUNSELOR_EVALUATION,
        payload=validate_evaluation(values),
    )


def initial_content(routine_interview_id: UUID) -> dict[str, str]:
    """Encrypted empty sections for a new row, which never has a blank content column."""

    return {
        "student_intake_ciphertext": encrypt_section(
            routine_interview_id=routine_interview_id,
            section=RoutineContentSection.STUDENT_INTAKE,
            payload=empty_intake(),
        ),
        "counselor_evaluation_ciphertext": encrypt_section(
            routine_interview_id=routine_interview_id,
            section=RoutineContentSection.COUNSELOR_EVALUATION,
            payload=empty_evaluation(),
        ),
    }


__all__ = [
    "CIPHERTEXT_COLUMNS",
    "EVALUATION_FIELDS",
    "INTAKE_FIELDS",
    "InvalidRoutineContent",
    "RATING_FIELDS",
    "empty_evaluation",
    "empty_intake",
    "initial_content",
    "read_evaluation",
    "read_intake",
    "read_section",
    "validate_evaluation",
    "validate_intake",
    "write_evaluation",
    "write_intake",
]
