"""Strict versioned professional Handoff envelope and independent keyring."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable
from compass.counseling.continuity_policy import ContinuityError

KEYRING_SETTING = "COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS"
MAX_CONTENT_LENGTH = 12000


def validate_content(value):
    if not isinstance(value, str) or len(value) > MAX_CONTENT_LENGTH or "\x00" in value:
        raise ContinuityError("invalid_handoff_content", 422)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ContinuityError("invalid_handoff_content", 422) from None
    return value


def keyring():
    try:
        return crypto.parse_fernet_keyring(
            getattr(settings, KEYRING_SETTING, ()), setting=KEYRING_SETTING
        )
    except ValueError:
        raise ImproperlyConfigured("Counselor Handoff keyring is unavailable.") from None


def binding(item):
    return {
        "counselor_handoff_summary_id": str(item.pk),
        "grant_id": str(item.grant_id),
        "student_id": str(item.student_id),
        "author_id": str(item.author_id),
        "receiving_counselor_id": str(item.receiving_counselor_id),
    }


def encrypt(item, content):
    return crypto.encrypt_bound_json(
        keyring=keyring(),
        schema_version=1,
        binding=binding(item),
        payload={"content": validate_content(content)},
    )


def read(item):
    try:
        payload = crypto.decrypt_bound_json(
            item.content_ciphertext, keyring=keyring(), schema_version=1, binding=binding(item)
        )
        if set(payload) != {"content"}:
            raise ConfidentialDataUnavailable(reason="malformed")
        value = validate_content(payload["content"])
        if item.state == "SUBMITTED" and not value.strip():
            raise ConfidentialDataUnavailable(reason="malformed")
        return value
    except (ConfidentialDataUnavailable, ImproperlyConfigured, ContinuityError):
        raise ContinuityError("handoff_unavailable", 503) from None


def reencrypt(item):
    read(item)
    return crypto.reencrypt_with_primary_key(item.content_ciphertext, keyring=keyring())
