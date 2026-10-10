"""Explicit authorized access only; no implicit ORM decryption or plaintext replay store."""

from django.conf import settings

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .errors import GuidanceMessageContentUnavailable, InvalidMessageInput

BODY_LIMIT = 4000
SCHEMA_VERSION = 1


def validate_text(value: object, *, label: str) -> str:
    """Plain UTF-8 text kept exactly as written: line breaks and spacing are never normalized."""
    if not isinstance(value, str) or not value.strip() or len(value) > BODY_LIMIT:
        raise InvalidMessageInput(f"{label} must contain 1 to 4000 characters of nonblank text.")
    if "\x00" in value:
        raise InvalidMessageInput(f"{label} contains an unsupported character.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidMessageInput(f"{label} contains an unsupported character.") from None
    return value


def validate_body(body: object) -> str:
    return validate_text(body, label="Message body")


def encryption_keyring():
    try:
        return crypto.parse_fernet_keyring(
            settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS, setting="GUIDANCE_MESSAGE_ENCRYPTION_KEYS"
        )
    except ValueError:
        raise GuidanceMessageContentUnavailable() from None


def _binding(message):
    return {
        "guidance_thread_id": str(message.thread_id),
        "guidance_message_id": str(message.pk),
        "sequence": str(message.sequence),
        "sender_id": str(message.sender_id),
    }


def encrypt_body(message, body: str) -> str:
    try:
        return crypto.encrypt_bound_json(
            keyring=encryption_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=_binding(message),
            payload={"body": validate_body(body)},
        )
    except ConfidentialDataUnavailable:
        raise GuidanceMessageContentUnavailable() from None


def read_body(message) -> str:
    """Caller must select and authorize the thread before invoking this accessor."""
    try:
        if message.body_schema_version != SCHEMA_VERSION:
            raise GuidanceMessageContentUnavailable()
        payload = crypto.decrypt_bound_json(
            message.body_ciphertext,
            keyring=encryption_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=_binding(message),
        )
        if set(payload) != {"body"}:
            raise GuidanceMessageContentUnavailable()
        return validate_body(payload["body"])
    except (ConfidentialDataUnavailable, InvalidMessageInput):
        raise GuidanceMessageContentUnavailable() from None
