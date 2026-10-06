"""Explicit ADR-082 projections; authorization belongs to the selecting service/API."""

from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .errors import ExitInterviewError, InvalidExitInterviewInput
from .models import ExitInterview, ExitInterviewOpportunity, ExitInterviewReopenEvent

KEYRING_SETTING = "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
SCHEMA_VERSION = 1
CONTENT_LIMITS = {
    "email_snapshot": 320,
    "home_address_snapshot": 2000,
    "contact_number_snapshot": 64,
    "delay_other": 1000,
    "significant_learning_other": 1000,
    "dean_comments": 4000,
    "program_chair_comments": 4000,
    "faculty_comments": 4000,
    "curriculum_comments": 4000,
    "guidance_counselor_comments": 4000,
    "office_staff_comments": 4000,
    "facilities_comments": 4000,
    "suggestions_recommendations": 4000,
}


@dataclass(frozen=True, slots=True)
class ExitInterviewConfidentialContent:
    email_snapshot: str = ""
    home_address_snapshot: str = ""
    contact_number_snapshot: str = ""
    delay_other: str = ""
    significant_learning_other: str = ""
    dean_comments: str = ""
    program_chair_comments: str = ""
    faculty_comments: str = ""
    curriculum_comments: str = ""
    guidance_counselor_comments: str = ""
    office_staff_comments: str = ""
    facilities_comments: str = ""
    suggestions_recommendations: str = ""


@dataclass(frozen=True, slots=True)
class OpportunityNote:
    note: str


@dataclass(frozen=True, slots=True)
class ReopenReason:
    reason: str


class ExitInterviewConfidentialContentUnavailable(ExitInterviewError):
    def __init__(self, item, *, reason):
        super().__init__("The Exit Interview confidential content is unavailable.")
        # These are identifiers from typed model columns, never envelope content.
        self.exit_interview_id = (
            item.pk if isinstance(item, ExitInterview) else getattr(item, "exit_interview_id", None)
        )
        self.opportunity_id = item.pk if isinstance(item, ExitInterviewOpportunity) else None
        self.reopen_event_id = item.pk if isinstance(item, ExitInterviewReopenEvent) else None
        self.reason = ConfidentialDataUnavailable(reason=reason).reason


def validate_text(value, name, maximum, *, required=False):
    if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
        raise InvalidExitInterviewInput(f"{name} contains invalid text or is too long.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidExitInterviewInput(f"{name} contains invalid text.") from None
    if required and not value.strip():
        raise InvalidExitInterviewInput(f"{name} is required.")
    return value


def _keyring():
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING
        )
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None


def _shape(item):
    if isinstance(item, ExitInterview):
        return (
            {"exit_interview_id": str(item.pk)},
            CONTENT_LIMITS,
            "confidential_content_ciphertext",
            ExitInterviewConfidentialContent,
        )
    if isinstance(item, ExitInterviewOpportunity):
        return (
            {
                "opportunity_id": str(item.pk),
                "student_id": str(item.student_id),
                "academic_year_id": str(item.academic_year_id),
            },
            {"note": 1000},
            "note_ciphertext",
            OpportunityNote,
        )
    if isinstance(item, ExitInterviewReopenEvent):
        return (
            {"exit_interview_id": str(item.exit_interview_id), "reopen_event_id": str(item.pk)},
            {"reason": 1000},
            "reason_ciphertext",
            ReopenReason,
        )
    raise TypeError("Unsupported Exit Interview confidential record")


def _validate(item, payload):
    _binding, limits, _column, projection = _shape(item)
    if not isinstance(payload, dict) or set(payload) != set(limits):
        raise InvalidExitInterviewInput("The confidential payload has an invalid shape.")
    for name, maximum in limits.items():
        validate_text(payload[name], name, maximum, required=name == "reason")
    if projection is ExitInterviewConfidentialContent:
        if payload["email_snapshot"]:
            try:
                validate_email(payload["email_snapshot"])
            except ValidationError:
                raise InvalidExitInterviewInput("email_address is invalid.") from None
        _validate_other_consistency(item, payload)
    return projection(**payload)


def _validate_other_consistency(item, payload):
    delay = payload["delay_other"]
    if item.program_completion == "ACCORDING_TO_SCHEDULE":
        if item.extra_terms_count is not None or item.delay_reasons or delay:
            raise InvalidExitInterviewInput("Delay details must be empty for scheduled completion.")
    elif item.program_completion == "WITH_SOME_DELAY":
        if item.extra_terms_count is None:
            raise InvalidExitInterviewInput("Delayed completion requires extra terms.")
    elif item.extra_terms_count is not None or item.delay_reasons or delay:
        raise InvalidExitInterviewInput("Delay details require a completion selection.")
    if ("OTHER" in item.delay_reasons) != bool(delay):
        raise InvalidExitInterviewInput("Delay OTHER selection and text must agree.")
    if ("OTHER" in item.significant_learning_experiences) != bool(
        payload["significant_learning_other"]
    ):
        raise InvalidExitInterviewInput("Learning OTHER selection and text must agree.")


def _read(item):
    binding, _limits, column, _projection = _shape(item)
    try:
        payload = crypto.decrypt_bound_json(
            getattr(item, column),
            keyring=_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=binding,
        )
        return _validate(item, payload)
    except ConfidentialDataUnavailable as exc:
        raise ExitInterviewConfidentialContentUnavailable(item, reason=exc.reason) from None
    except InvalidExitInterviewInput:
        raise ExitInterviewConfidentialContentUnavailable(item, reason="malformed") from None


def _write(item, projection):
    binding, _limits, column, _projection = _shape(item)
    payload = asdict(projection)
    _validate(item, payload)
    setattr(
        item,
        column,
        crypto.encrypt_bound_json(
            keyring=_keyring(), schema_version=SCHEMA_VERSION, binding=binding, payload=payload
        ),
    )


def read_exit_interview_confidential_content(item) -> ExitInterviewConfidentialContent:
    return _read(item)


def write_exit_interview_confidential_content(item, content: ExitInterviewConfidentialContent):
    _write(item, content)


def read_opportunity_note(item) -> str:
    return _read(item).note


def write_opportunity_note(item, note: str):
    _write(item, OpportunityNote(note))


def read_reopen_reason(item) -> str:
    return _read(item).reason


def write_reopen_reason(item, reason: str):
    _write(item, ReopenReason(reason))


def encrypted_with_primary_key(token):
    return crypto.encrypted_with_primary_key(token, keyring=_keyring())


def reencrypt_confidential_content(item):
    _read(item)  # Verify every domain/binding field before using the generic rewrap helper.
    _binding, _limits, column, _projection = _shape(item)
    return crypto.reencrypt_with_primary_key(getattr(item, column), keyring=_keyring())
