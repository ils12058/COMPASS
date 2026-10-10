"""Frozen v1 historical mechanics and policy. Never import evolving domain adapters."""

from typing import Literal

UnavailableReason = Literal[
    "missing", "undecryptable", "malformed", "unsupported_schema", "binding_mismatch"
]


class ConfidentialDataUnavailable(RuntimeError):
    """Confidential content could not be authenticated and verified in full."""

    def __init__(self, *, reason: UnavailableReason) -> None:
        if reason not in {
            "missing",
            "undecryptable",
            "malformed",
            "unsupported_schema",
            "binding_mismatch",
        }:
            raise ValueError("Unsupported confidential-data failure reason")
        super().__init__("The confidential data is unavailable.")
        self.reason = reason


import base64
import binascii
import json
from collections.abc import Mapping, Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


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


from datetime import date
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

KEYRING_SETTING = "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
COLUMN = "profile_confidential_content_ciphertext"
FAMILIES = ("User",)
FIELDS = {
    "User": {
        "date_of_birth": None,
        "civil_status": 80,
        "contact_number": 64,
        "current_address": 2000,
        "permanent_address": 2000,
    }
}


def keyring():
    return parse_fernet_keyring(getattr(settings, KEYRING_SETTING, ""), setting=KEYRING_SETTING)


def failure(row, reason, family):
    ConfidentialDataUnavailable(reason=reason)
    return RuntimeError(f"{family} {row.pk}: confidential content unavailable ({reason})")


def binding(row, family):
    return {"user_id": str(row.pk)}


def validate(payload, family):
    if not isinstance(payload, dict) or set(payload) != set(FIELDS[family]):
        raise ValueError("Invalid confidential payload.")
    for name, limit in FIELDS[family].items():
        value = payload[name]
        if name == "date_of_birth":
            if value is not None:
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError("Invalid confidential date.")
            continue
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise ValueError("Invalid confidential text.")
        value.encode("utf-8")
    if family == "ClientSatisfactionResponse" and payload["email"]:
        validate_email(payload["email"])
    return payload


def plaintext(row, family):
    payload = {name: getattr(row, name) for name in FIELDS[family]}
    if "date_of_birth" in payload and payload["date_of_birth"] is not None:
        payload["date_of_birth"] = payload["date_of_birth"].isoformat()
    try:
        return validate(payload, family)
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise failure(row, "malformed", family) from None


def encrypt(ring, row, payload, family):
    return encrypt_bound_json(
        keyring=ring,
        schema_version=1,
        binding=binding(row, family),
        payload=validate(payload, family),
    )


def decrypt(ring, row, token, family):
    try:
        return validate(
            decrypt_bound_json(token, keyring=ring, schema_version=1, binding=binding(row, family)),
            family,
        )
    except ConfidentialDataUnavailable as exc:
        raise failure(row, exc.reason, family) from None
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise failure(row, "malformed", family) from None
