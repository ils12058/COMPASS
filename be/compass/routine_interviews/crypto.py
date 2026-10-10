"""Routine Interview policy adapter for confidential-data mechanics (ADR-066, ADR-079).

The dedicated setting, v1 envelope binding, section names, and domain errors remain Routine-owned.
Payload validation and authorization remain in the content and service layers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .errors import RoutineContentUnavailable

KEYRING_SETTING = "ROUTINE_INTERVIEW_ENCRYPTION_KEYS"
# The payload format version. It is independent of which key encrypted the payload.
PAYLOAD_SCHEMA_VERSION = 1


class RoutineContentSection(StrEnum):
    STUDENT_INTAKE = "student_intake"
    COUNSELOR_EVALUATION = "counselor_evaluation"


def parse_keyring(value: str | Sequence[str], *, setting: str = KEYRING_SETTING) -> tuple[str, ...]:
    """Compatibility boundary for existing Routine keyring callers."""

    return crypto.parse_fernet_keyring(value, setting=setting)


def keyring_reuses_secret(keys: Sequence[str], *secrets: str) -> bool:
    """Compatibility boundary for existing Routine key-reuse checks."""

    return crypto.keyring_reuses_secret(keys, *secrets)


def _configured_keyring() -> tuple[str, ...]:
    try:
        return parse_keyring(getattr(settings, KEYRING_SETTING, ""))
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None


def _binding(routine_interview_id: UUID, section: RoutineContentSection) -> dict[str, str]:
    return {
        "routine_interview_id": str(routine_interview_id),
        "section": RoutineContentSection(section).value,
    }


def encrypt_section(
    *,
    routine_interview_id: UUID,
    section: RoutineContentSection,
    payload: Mapping[str, object],
) -> str:
    """Encrypt a validated section payload under the primary key, bound to its record."""

    binding = _binding(routine_interview_id, section)
    return crypto.encrypt_bound_json(
        keyring=_configured_keyring(),
        schema_version=PAYLOAD_SCHEMA_VERSION,
        binding=binding,
        payload=payload,
    )


def decrypt_section(
    token: str | None,
    *,
    routine_interview_id: UUID,
    section: RoutineContentSection,
) -> dict[str, object]:
    """Decrypt an already authorized section; the caller still validates its payload schema."""

    section = RoutineContentSection(section)
    try:
        # Preserve the existing missing-content result before consulting runtime configuration.
        if not isinstance(token, str) or not token:
            raise ConfidentialDataUnavailable(reason="missing")
        return crypto.decrypt_bound_json(
            token,
            keyring=_configured_keyring(),
            schema_version=PAYLOAD_SCHEMA_VERSION,
            binding=_binding(routine_interview_id, section),
        )
    except ConfidentialDataUnavailable as exc:
        raise RoutineContentUnavailable(
            routine_interview_id=routine_interview_id,
            section=section,
            reason=exc.reason,
        ) from None


def encrypted_with_primary_key(token: str) -> bool:
    """Whether this token authenticates under Routine's current primary key."""

    return crypto.encrypted_with_primary_key(token, keyring=_configured_keyring())


def reencrypt_with_primary_key(token: str) -> str:
    """Rewrap verified Routine content; rotation policy remains in the Routine command."""

    return crypto.reencrypt_with_primary_key(token, keyring=_configured_keyring())


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
