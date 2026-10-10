"""Explicit confidential accessors for an already authorized record (ADR-108 / ADR-079)."""

from dataclasses import asdict, dataclass

from django.conf import settings

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .errors import AssessmentRecordError, InvalidAssessmentRecordInput

KEYRING_SETTING = "ASSESSMENT_RECORD_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
SCHEMA_VERSION = 1
CONTENT_LIMITS = {"score": 500, "result": 4000, "interpretation": 8000, "remarks": 4000}


@dataclass(frozen=True, slots=True)
class AssessmentRecordConfidentialContent:
    score: str = ""
    result: str = ""
    interpretation: str = ""
    remarks: str = ""


class AssessmentRecordConfidentialContentUnavailable(AssessmentRecordError):
    def __init__(self, *, reason):
        super().__init__("The Assessment Record confidential content is unavailable.")
        self.reason = ConfidentialDataUnavailable(reason=reason).reason


def validate_text(value, field, maximum):
    if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
        raise InvalidAssessmentRecordInput(f"{field} contains invalid text or is too long.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidAssessmentRecordInput(f"{field} contains invalid text.") from None
    return value


def project_confidential_input(values):
    if not isinstance(values, dict) or set(values) != set(CONTENT_LIMITS):
        raise InvalidAssessmentRecordInput("The confidential payload has an invalid shape.")
    for field, maximum in CONTENT_LIMITS.items():
        validate_text(values[field], field, maximum)
    if not any(value.strip() for value in values.values()):
        raise InvalidAssessmentRecordInput("At least one assessment result field is required.")
    return AssessmentRecordConfidentialContent(**values)


def _keyring():
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING
        )
    except ValueError:
        raise AssessmentRecordConfidentialContentUnavailable(reason="missing") from None


def _binding(item):
    return {
        "assessment_record_id": str(item.pk),
        "student_id": str(item.student_id),
        "assessment_type_id": str(item.assessment_type_id),
    }


def write_confidential_content(item, content):
    payload = asdict(content)
    project_confidential_input(payload)
    item.confidential_content_ciphertext = crypto.encrypt_bound_json(
        keyring=_keyring(), schema_version=SCHEMA_VERSION, binding=_binding(item), payload=payload
    )


def read_confidential_content(item):
    try:
        payload = crypto.decrypt_bound_json(
            item.confidential_content_ciphertext,
            keyring=_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=_binding(item),
        )
        return project_confidential_input(payload)
    except ConfidentialDataUnavailable as exc:
        raise AssessmentRecordConfidentialContentUnavailable(reason=exc.reason) from None
    except InvalidAssessmentRecordInput:
        raise AssessmentRecordConfidentialContentUnavailable(reason="malformed") from None


def encrypted_with_primary_key(token):
    return crypto.encrypted_with_primary_key(token, keyring=_keyring())


def reencrypt_confidential_content(item):
    read_confidential_content(item)
    return crypto.reencrypt_with_primary_key(
        item.confidential_content_ciphertext, keyring=_keyring()
    )
