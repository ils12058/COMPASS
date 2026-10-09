"""Explicit authorized access only; no implicit ORM decryption or plaintext replay store."""

from django.conf import settings

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .errors import GuidanceMessageContentUnavailable, InvalidMessageInput

BODY_LIMIT = 4000
SCHEMA_VERSION = 1


def validate_body(body: object) -> str:
    if not isinstance(body, str) or not body.strip() or len(body) > BODY_LIMIT:
        raise InvalidMessageInput(
            "Message body must contain 1 to 4000 characters of nonblank text."
        )
    if "\x00" in body:
        raise InvalidMessageInput("Message body contains an unsupported character.")
    try:
        body.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidMessageInput("Message body contains an unsupported character.") from None
    return body


def _keyring():
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
            keyring=_keyring(),
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
            keyring=_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=_binding(message),
        )
        if set(payload) != {"body"}:
            raise GuidanceMessageContentUnavailable()
        return validate_body(payload["body"])
    except (ConfidentialDataUnavailable, InvalidMessageInput):
        raise GuidanceMessageContentUnavailable() from None
