"""Fernet mechanics for bound, versioned JSON envelopes (ADR-079).

Callers supply their own ordered keyring, schema version, and simple string binding. Binding
fields are part of the authenticated plaintext, not external AAD. This module knows nothing
about Django, authorization, domain payload schemas, configuration sources, or logging.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping, Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from .errors import ConfidentialDataUnavailable

_RESERVED_KEYS = frozenset({"schema_version", "payload"})


def _key_bytes(value: str) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return None
    return raw if len(raw) == 32 else None


def parse_fernet_keyring(value: str | Sequence[str], *, setting: str) -> tuple[str, ...]:
    """Keep configured order and reject empty, noncanonical, or duplicate keys safely."""

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
    """Detect reuse by decoded key bytes, without logging or exposing either input."""

    decoded = {_key_bytes(key) for key in keys} - {None}
    return any(
        isinstance(secret, str) and secret.strip() and _key_bytes(secret.strip()) in decoded
        for secret in secrets
    )


def _fernets(keyring: Sequence[str]) -> tuple[Fernet, MultiFernet]:
    keys = parse_fernet_keyring(keyring, setting="Fernet keyring")
    fernets = [Fernet(key) for key in keys]
    return fernets[0], MultiFernet(fernets)


def _validate_context(schema_version: int, binding: Mapping[str, str]) -> None:
    if type(schema_version) is not int:
        raise ValueError("The envelope schema version must be an integer")
    if not isinstance(binding, Mapping) or any(
        not isinstance(key, str) or not key or not isinstance(value, str)
        for key, value in binding.items()
    ):
        raise ValueError("Envelope binding requires non-empty string keys and string values")
    if _RESERVED_KEYS.intersection(binding):
        raise ValueError("Envelope binding uses a reserved key")


def encrypt_bound_json(
    *,
    keyring: Sequence[str],
    schema_version: int,
    binding: Mapping[str, str],
    payload: Mapping[str, object],
) -> str:
    """Encrypt canonical JSON under the first key, with a flat authenticated binding.

    Invalid context/keyring configuration raises a safe ValueError; unserializable content
    raises ConfidentialDataUnavailable. Payload field/schema policy belongs to the caller.
    """

    _validate_context(schema_version, binding)
    _primary, ring = _fernets(keyring)
    if not isinstance(payload, Mapping):
        raise ConfidentialDataUnavailable(reason="malformed")
    envelope = {"schema_version": schema_version, **binding, "payload": dict(payload)}
    try:
        plaintext = json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        raise ConfidentialDataUnavailable(reason="malformed") from None
    return ring.encrypt(plaintext).decode("ascii")


def _reject_json_constant(_value: str) -> None:
    raise ValueError("Non-finite JSON value")


def decrypt_bound_json(
    token: str | None,
    *,
    keyring: Sequence[str],
    schema_version: int,
    binding: Mapping[str, str],
) -> dict[str, object]:
    """Return content only after authentication and exact envelope/context validation."""

    _validate_context(schema_version, binding)
    if not isinstance(token, str) or not token:
        raise ConfidentialDataUnavailable(reason="missing")
    _primary, ring = _fernets(keyring)
    try:
        plaintext = ring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise ConfidentialDataUnavailable(reason="undecryptable") from None
    try:
        envelope = json.loads(plaintext.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ConfidentialDataUnavailable(reason="malformed") from None
    if not isinstance(envelope, dict) or set(envelope) != _RESERVED_KEYS.union(binding):
        raise ConfidentialDataUnavailable(reason="malformed")
    version = envelope["schema_version"]
    if type(version) is not int or version != schema_version:
        raise ConfidentialDataUnavailable(reason="unsupported_schema")
    if any(envelope[key] != value for key, value in binding.items()):
        raise ConfidentialDataUnavailable(reason="binding_mismatch")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise ConfidentialDataUnavailable(reason="malformed")
    return payload


def encrypted_with_primary_key(token: str, *, keyring: Sequence[str]) -> bool:
    """Whether the first key alone authenticates the token; malformed tokens return False."""

    primary, _ring = _fernets(keyring)
    if not isinstance(token, str):
        return False
    try:
        primary.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        return False
    return True


def reencrypt_with_primary_key(token: str, *, keyring: Sequence[str]) -> str:
    """Use MultiFernet.rotate, preserving plaintext bytes and the original token timestamp.

    This only rewraps a token. The domain must verify its binding/payload before rotating it.
    Invalid tokens raise the library's content-free InvalidToken error.
    """

    _primary, ring = _fernets(keyring)
    if not isinstance(token, str):
        raise InvalidToken
    try:
        return ring.rotate(token.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeEncodeError):
        raise InvalidToken from None
