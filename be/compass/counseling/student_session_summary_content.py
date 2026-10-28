"""Explicit Student Session Summary content policy and accessors (CONT-1B).

Select an authorized Summary before reading. ORM access never decrypts implicitly. This
dedicated keyring protects student-disclosable summaries, not future private Counseling notes.
"""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable, UnavailableReason

from .models import StudentSessionSummary
from .services import CounselingError, InvalidCounselingInput

KEYRING_SETTING = "STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS"
PAYLOAD_SCHEMA_VERSION = 1


class InvalidStudentSessionSummaryContent(InvalidCounselingInput):
    """Invalid input; messages never include submitted text."""


class StudentSessionSummaryContentUnavailable(CounselingError):
    def __init__(self, *, summary_id: UUID, encounter_id: UUID, reason: UnavailableReason) -> None:
        # Validate the bounded reason without retaining any confidential exception input.
        safe = ConfidentialDataUnavailable(reason=reason)
        super().__init__("The Student Session Summary content is unavailable.")
        self.summary_id = summary_id
        self.encounter_id = encounter_id
        self.reason = safe.reason


def validate_content(content: object) -> str:
    if not isinstance(content, str):
        raise InvalidStudentSessionSummaryContent("Student Session Summary content must be text.")
    if "\x00" in content:
        raise InvalidStudentSessionSummaryContent(
            "Student Session Summary content contains an unsupported character."
        )
    try:
        content.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidStudentSessionSummaryContent(
            "Student Session Summary content contains an unsupported character."
        ) from None
    return str(content)


def _configured_keyring() -> tuple[str, ...]:
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING
        )
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None


def _binding(summary_id: UUID, encounter_id: UUID) -> dict[str, str]:
    return {"student_session_summary_id": str(summary_id), "encounter_id": str(encounter_id)}


def encrypt_student_session_summary_content(
    *, summary_id: UUID, encounter_id: UUID, content: str
) -> str:
    return crypto.encrypt_bound_json(
        keyring=_configured_keyring(),
        schema_version=PAYLOAD_SCHEMA_VERSION,
        binding=_binding(summary_id, encounter_id),
        payload={"content": validate_content(content)},
    )


def decrypt_student_session_summary_content(
    token: str | None, *, summary_id: UUID, encounter_id: UUID
) -> str:
    try:
        if not isinstance(token, str) or not token:
            raise ConfidentialDataUnavailable(reason="missing")
        payload = crypto.decrypt_bound_json(
            token,
            keyring=_configured_keyring(),
            schema_version=PAYLOAD_SCHEMA_VERSION,
            binding=_binding(summary_id, encounter_id),
        )
        if set(payload) != {"content"}:
            raise ConfidentialDataUnavailable(reason="malformed")
        try:
            return validate_content(payload["content"])
        except InvalidStudentSessionSummaryContent:
            raise ConfidentialDataUnavailable(reason="malformed") from None
    except ConfidentialDataUnavailable as exc:
        raise StudentSessionSummaryContentUnavailable(
            summary_id=summary_id, encounter_id=encounter_id, reason=exc.reason
        ) from None


def read_student_session_summary_content(summary: StudentSessionSummary) -> str:
    """Read the complete body of an already authorized Summary, or fail closed."""
    return decrypt_student_session_summary_content(
        summary.content_ciphertext, summary_id=summary.pk, encounter_id=summary.encounter_id
    )


def write_student_session_summary_content(summary: StudentSessionSummary, content: str) -> None:
    """Replace the complete encrypted body in memory; the caller owns authorization/save."""
    summary.content_ciphertext = encrypt_student_session_summary_content(
        summary_id=summary.pk, encounter_id=summary.encounter_id, content=content
    )


def encrypted_with_primary_key(token: str) -> bool:
    return crypto.encrypted_with_primary_key(token, keyring=_configured_keyring())


def reencrypt_student_session_summary_content(summary: StudentSessionSummary) -> str:
    """Verify context/payload before rewrapping; preserve the original Fernet timestamp."""
    read_student_session_summary_content(summary)
    return crypto.reencrypt_with_primary_key(
        summary.content_ciphertext, keyring=_configured_keyring()
    )
