"""Explicit private Feedback prose/contact envelopes (ADR-086)."""

from dataclasses import asdict, dataclass
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable, UnavailableReason

KEYRING_SETTING = "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
COLUMN = "confidential_content_ciphertext"
FAMILIES = ("CustomerFeedbackResponse", "ClientSatisfactionResponse")
FIELDS = {
    "CustomerFeedbackResponse": {
        "other_service": 255,
        "additional_feedback": 4000,
        "future_service_improvement": 4000,
        "address_snapshot": 2000,
        "mobile_number_snapshot": 64,
    },
    "ClientSatisfactionResponse": {"suggestions": 4000, "email": 320},
}


@dataclass(frozen=True, slots=True)
class CustomerFeedbackConfidentialContent:
    other_service: str = ""
    additional_feedback: str = ""
    future_service_improvement: str = ""
    address_snapshot: str = ""
    mobile_number_snapshot: str = ""


@dataclass(frozen=True, slots=True)
class ClientSatisfactionConfidentialContent:
    suggestions: str = ""
    email: str = ""


class FeedbackConfidentialContentUnavailable(RuntimeError):
    def __init__(self, *, object_id: UUID, family: str, reason: UnavailableReason):
        ConfidentialDataUnavailable(reason=reason)
        if family not in FAMILIES:
            raise ValueError("Invalid Feedback family.")
        super().__init__("The Feedback confidential content is unavailable.")
        self.object_id, self.family, self.reason = object_id, family, reason


def _keyring():
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING
        )
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None


def _family(item):
    return item._meta.object_name


def _binding(item):
    if _family(item) == FAMILIES[0]:
        return {
            "customer_feedback_response_id": str(item.pk),
            "form_revision_id": str(item.form_revision_id),
        }
    # ADR-079 bindings are strings; authenticate the canonical decimal representation.
    return {
        "client_satisfaction_response_id": str(item.pk),
        "instrument_schema_version": str(item.instrument_schema_version),
    }


def _content(payload, family):
    if set(payload) != set(FIELDS[family]):
        raise ValueError("Invalid Feedback payload.")
    for name, limit in FIELDS[family].items():
        value = payload[name]
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise ValueError("Invalid Feedback text.")
        value.encode("utf-8")
    if family == FAMILIES[1] and payload["email"]:
        validate_email(payload["email"])
    cls = (
        CustomerFeedbackConfidentialContent
        if family == FAMILIES[0]
        else ClientSatisfactionConfidentialContent
    )
    return cls(**payload)


def read_feedback_confidential_content(item):
    family = _family(item)
    try:
        payload = crypto.decrypt_bound_json(
            getattr(item, COLUMN), keyring=_keyring(), schema_version=1, binding=_binding(item)
        )
        result = _content(payload, family)
        _validate_other(item, payload)
        return result
    except ConfidentialDataUnavailable as exc:
        raise FeedbackConfidentialContentUnavailable(
            object_id=item.pk, family=family, reason=exc.reason
        ) from None
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise FeedbackConfidentialContentUnavailable(
            object_id=item.pk, family=family, reason="malformed"
        ) from None


def write_feedback_confidential_content(item, content):
    payload = asdict(content)
    _content(payload, _family(item))
    _validate_other(item, payload)
    setattr(
        item,
        COLUMN,
        crypto.encrypt_bound_json(
            keyring=_keyring(), schema_version=1, binding=_binding(item), payload=payload
        ),
    )


def encrypted_with_primary_key(token):
    return crypto.encrypted_with_primary_key(token, keyring=_keyring())


def reencrypt_feedback_confidential_content(item):
    read_feedback_confidential_content(item)
    return crypto.reencrypt_with_primary_key(getattr(item, COLUMN), keyring=_keyring())


def _validate_other(item, payload):
    if _family(item) == FAMILIES[0]:
        if ("OTHER" in item.services_received) != bool(payload["other_service"].strip()):
            raise ValueError("Invalid Other service content.")
