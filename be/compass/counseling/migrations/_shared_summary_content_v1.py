"""Frozen ADR-080 v1 semantics. Never import evolving runtime crypto/content policy here."""

import base64
import binascii
import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

SETTING = "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS"
ENVELOPE_KEYS = {"schema_version", "counseling_shared_summary_id", "encounter_id", "payload"}


def keyring():
    configured = getattr(settings, SETTING, "")
    entries = configured.split(",") if isinstance(configured, str) else configured
    if not isinstance(entries, (list, tuple)) or not entries:
        raise RuntimeError(f"{SETTING} is required for Shared Summary migration")
    keys = []
    seen = set()
    for position, entry in enumerate(entries, start=1):
        key = entry.strip() if isinstance(entry, str) else ""
        try:
            raw = base64.urlsafe_b64decode(key.encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError):
            raw = b""
        if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii") != key:
            raise RuntimeError(f"{SETTING} entry {position} is invalid")
        if raw in seen:
            raise RuntimeError(f"{SETTING} entry {position} repeats an earlier key")
        seen.add(raw)
        keys.append(Fernet(key))
    return MultiFernet(keys)


def failure(summary_id, encounter_id, reason):
    # Callers pass only fixed reasons; never include parser exceptions or content.
    return RuntimeError(
        f"Shared Summary {summary_id} Encounter {encounter_id}: {reason}; migration stopped"
    )


def validate_content(content, summary_id, encounter_id):
    if not isinstance(content, str) or "\x00" in content:
        raise failure(summary_id, encounter_id, "malformed")
    try:
        content.encode("utf-8")
    except UnicodeEncodeError:
        raise failure(summary_id, encounter_id, "malformed") from None
    return content


def encrypt(ring, summary_id, encounter_id, content):
    content = validate_content(content, summary_id, encounter_id)
    envelope = {
        "schema_version": 1,
        "counseling_shared_summary_id": str(summary_id),
        "encounter_id": str(encounter_id),
        "payload": {"content": content},
    }
    plaintext = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return ring.encrypt(plaintext).decode("ascii")


def _reject_constant(_value):
    raise ValueError("Non-finite JSON")


def decrypt(ring, token, summary_id, encounter_id):
    if not isinstance(token, str) or not token:
        raise failure(summary_id, encounter_id, "missing")
    try:
        plaintext = ring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise failure(summary_id, encounter_id, "undecryptable") from None
    try:
        envelope = json.loads(plaintext.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise failure(summary_id, encounter_id, "malformed") from None
    if not isinstance(envelope, dict) or set(envelope) != ENVELOPE_KEYS:
        raise failure(summary_id, encounter_id, "malformed")
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise failure(summary_id, encounter_id, "unsupported_schema")
    if envelope["counseling_shared_summary_id"] != str(summary_id) or envelope[
        "encounter_id"
    ] != str(encounter_id):
        raise failure(summary_id, encounter_id, "binding_mismatch")
    payload = envelope["payload"]
    if not isinstance(payload, dict) or set(payload) != {"content"}:
        raise failure(summary_id, encounter_id, "malformed")
    return validate_content(payload["content"], summary_id, encounter_id)
