"""Authenticated encryption boundary for Routine Interview content (ADR-066).

Each section is a Fernet token over deterministic, versioned JSON that also names the Routine
Interview and section it belongs to, so a valid token copied onto another record or section is
rejected instead of read. The keyring is ordered: the first key encrypts and every key may decrypt.
Nothing here logs or raises with plaintext, ciphertext, or key material.

Settings imports this module to validate the keyring at startup, so it must not import models.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .errors import RoutineContentUnavailable

KEYRING_SETTING = "ROUTINE_INTERVIEW_ENCRYPTION_KEYS"
# The payload format version. It is independent of which key encrypted the payload.
PAYLOAD_SCHEMA_VERSION = 1
_ENVELOPE_KEYS = frozenset({"schema_version", "routine_interview_id", "section", "payload"})


class RoutineContentSection(StrEnum):
    STUDENT_INTAKE = "student_intake"
    COUNSELOR_EVALUATION = "counselor_evaluation"


def _key_bytes(value: str) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return None
    return raw if len(raw) == 32 else None


def parse_keyring(value: str | Sequence[str], *, setting: str = KEYRING_SETTING) -> tuple[str, ...]:
    """Validate an ordered keyring without ever echoing key material.

    ``value`` is the configured comma-separated string or an already split sequence. Whitespace
    around entries is ignored. An empty keyring, an empty entry, anything other than a canonical
    ``Fernet.generate_key()`` value, and a repeated key are all rejected, so a typo cannot silently
    change which keys are trusted.
    """

    if isinstance(value, str):
        entries: list[object] = list(value.split(","))
    elif isinstance(value, Sequence):
        entries = list(value)
    else:
        entries = []
    if not any(isinstance(entry, str) and entry.strip() for entry in entries):
        raise ValueError(f"{setting} is required")

    keys: list[str] = []
    seen: set[bytes] = set()
    for position, entry in enumerate(entries, start=1):
        key = entry.strip() if isinstance(entry, str) else ""
        if not key:
            raise ValueError(f"{setting} entry {position} is empty")
        raw = _key_bytes(key)
        if raw is None or base64.urlsafe_b64encode(raw).decode("ascii") != key:
            raise ValueError(f"{setting} entry {position} is not a valid Fernet key")
        if raw in seen:
            raise ValueError(f"{setting} entry {position} repeats an earlier key")
        seen.add(raw)
        keys.append(key)
    return tuple(keys)


def keyring_reuses_secret(keys: Sequence[str], *secrets: str) -> bool:
    """Whether a Routine key is also another configured secret, such as the TOTP key."""

    routine = {_key_bytes(key) for key in keys}
    return any(
        isinstance(secret, str) and secret.strip() and _key_bytes(secret.strip()) in routine
        for secret in secrets
    )


def _fernets() -> tuple[Fernet, MultiFernet]:
    try:
        keys = parse_keyring(getattr(settings, KEYRING_SETTING, ""))
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None
    fernets = [Fernet(key) for key in keys]
    return fernets[0], MultiFernet(fernets)


def _serialize(envelope: Mapping[str, object]) -> bytes:
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def encrypt_section(
    *,
    routine_interview_id: UUID,
    section: RoutineContentSection,
    payload: Mapping[str, object],
) -> str:
    """Encrypt a validated section payload under the primary key, bound to its record."""

    envelope = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "routine_interview_id": str(routine_interview_id),
        "section": RoutineContentSection(section).value,
        "payload": dict(payload),
    }
    _primary, keyring = _fernets()
    return keyring.encrypt(_serialize(envelope)).decode("ascii")


def decrypt_section(
    token: str | None,
    *,
    routine_interview_id: UUID,
    section: RoutineContentSection,
) -> dict[str, object]:
    """Return the payload bound to this record and section, or fail closed.

    The caller must already have authorized the actor for this section of this Routine Interview,
    and must still validate the payload against the section schema.
    """

    section = RoutineContentSection(section)

    def unavailable(reason: str) -> RoutineContentUnavailable:
        return RoutineContentUnavailable(
            routine_interview_id=routine_interview_id,
            section=section,
            reason=reason,
        )

    if not isinstance(token, str) or not token:
        raise unavailable("missing")
    _primary, keyring = _fernets()
    try:
        plaintext = keyring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise unavailable("undecryptable") from None
    try:
        envelope = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise unavailable("malformed") from None
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
        raise unavailable("malformed")
    version = envelope["schema_version"]
    if type(version) is not int or version != PAYLOAD_SCHEMA_VERSION:
        raise unavailable("unsupported_schema")
    if (
        envelope["routine_interview_id"] != str(routine_interview_id)
        or envelope["section"] != section.value
    ):
        raise unavailable("binding_mismatch")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise unavailable("malformed")
    return payload


def encrypted_with_primary_key(token: str) -> bool:
    """Whether ``token`` is already encrypted under the current primary key."""

    primary, _keyring = _fernets()
    try:
        primary.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        return False
    return True


def reencrypt_with_primary_key(token: str) -> str:
    """Re-encrypt a readable token under the primary key; its plaintext is unchanged."""

    _primary, keyring = _fernets()
    return keyring.rotate(token.encode("ascii")).decode("ascii")


__all__ = [
    "KEYRING_SETTING",
    "PAYLOAD_SCHEMA_VERSION",
    "RoutineContentSection",
    "decrypt_section",
    "encrypt_section",
    "encrypted_with_primary_key",
    "keyring_reuses_secret",
    "parse_keyring",
    "reencrypt_with_primary_key",
]
