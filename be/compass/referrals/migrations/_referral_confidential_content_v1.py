"""Frozen ADR-081 v1. Intentionally independent of evolving runtime code."""

import base64
import binascii
import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

SETTING = "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
LIMITS = {"reason": 10000, "referrer_name": 255, "status_note": 1000, "void_reason": 1000}


def keyring():
    configured = getattr(settings, SETTING, "")
    entries = configured.split(",") if isinstance(configured, str) else configured
    if not isinstance(entries, (list, tuple)) or not entries:
        raise RuntimeError(f"{SETTING} is required for Referral migration")
    keys, seen = [], set()
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


def binding(row, *, action=False):
    result = {"referral_id": str(row.referral_id if action else row.pk)}
    if action:
        result.update(referral_action_id=str(row.pk), action_type=row.action_type)
    return result


def failure(row, reason, *, action=False):
    context = f"Referral {row.referral_id} Action {row.pk}" if action else f"Referral {row.pk}"
    return RuntimeError(f"{context}: {reason}; migration stopped")


def validate(row, payload, *, action=False, check_lifecycle=True):
    limits = {"remarks": 4000} if action else LIMITS
    if not isinstance(payload, dict) or set(payload) != set(limits):
        raise failure(row, "malformed", action=action)
    for name, limit in limits.items():
        value = payload[name]
        if not isinstance(value, str) or "\x00" in value or len(value) > limit:
            raise failure(row, "malformed", action=action)
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise failure(row, "malformed", action=action) from None
        if name in {"reason", "referrer_name"} and not value.strip():
            raise failure(row, "malformed", action=action)
    if not action and payload["void_reason"] and not payload["void_reason"].strip():
        raise failure(row, "malformed")
    if not action and check_lifecycle:
        if row.voided_at is None and payload["void_reason"] != "":
            raise failure(row, "malformed")
        if row.voided_at is not None and not payload["void_reason"].strip():
            raise failure(row, "malformed")
    return payload


def plaintext(row, *, action=False):
    names = {"remarks"} if action else LIMITS
    return validate(row, {name: getattr(row, name) for name in names}, action=action)


def encrypt(ring, row, payload, *, action=False):
    payload = validate(row, payload, action=action)
    envelope = {"schema_version": 1, **binding(row, action=action), "payload": payload}
    raw = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return ring.encrypt(raw).decode("ascii")


def _reject_constant(_value):
    raise ValueError("Non-finite JSON")


def decrypt(ring, row, token, *, action=False, check_lifecycle=True):
    if not isinstance(token, str) or not token:
        raise failure(row, "missing", action=action)
    try:
        raw = ring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise failure(row, "undecryptable", action=action) from None
    try:
        envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise failure(row, "malformed", action=action) from None
    expected = binding(row, action=action)
    if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "payload", *expected}:
        raise failure(row, "malformed", action=action)
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise failure(row, "unsupported_schema", action=action)
    if any(envelope[name] != value for name, value in expected.items()):
        raise failure(row, "binding_mismatch", action=action)
    return validate(row, envelope["payload"], action=action, check_lifecycle=check_lifecycle)
