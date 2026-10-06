"""Frozen ADR-082 v1: independent of all evolving runtime crypto/domain code."""

import base64
import binascii
import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

SETTING = "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
LIMITS = {
    "email_snapshot": 320,
    "home_address_snapshot": 2000,
    "contact_number_snapshot": 64,
    "delay_other": 1000,
    "significant_learning_other": 1000,
    "dean_comments": 4000,
    "program_chair_comments": 4000,
    "faculty_comments": 4000,
    "curriculum_comments": 4000,
    "guidance_counselor_comments": 4000,
    "office_staff_comments": 4000,
    "facilities_comments": 4000,
    "suggestions_recommendations": 4000,
}
# Deterministic table order, used before any verification/update in Phase B/reverse.
FAMILIES = (
    ("ExitInterview", "confidential_content_ciphertext", "response"),
    ("ExitInterviewOpportunity", "note_ciphertext", "opportunity"),
    ("ExitInterviewReopenEvent", "reason_ciphertext", "reopen"),
)


def keyring():
    configured = getattr(settings, SETTING, "")
    entries = configured.split(",") if isinstance(configured, str) else configured
    if not isinstance(entries, (list, tuple)) or not entries:
        raise RuntimeError(f"{SETTING} is required for Exit Interview migration")
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


def binding(row, kind):
    if kind == "response":
        return {"exit_interview_id": str(row.pk)}
    if kind == "opportunity":
        return {
            "opportunity_id": str(row.pk),
            "student_id": str(row.student_id),
            "academic_year_id": str(row.academic_year_id),
        }
    return {
        "exit_interview_id": str(row.exit_interview_id),
        "reopen_event_id": str(row.pk),
    }


def failure(row, reason, kind):
    return RuntimeError(f"Exit Interview {kind} {row.pk}: {reason}; migration stopped")


def validate(row, payload, kind, *, check_consistency=True):
    limits = LIMITS if kind == "response" else {"note" if kind == "opportunity" else "reason": 1000}
    if not isinstance(payload, dict) or set(payload) != set(limits):
        raise failure(row, "malformed", kind)
    for name, maximum in limits.items():
        value = payload[name]
        if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
            raise failure(row, "malformed", kind)
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise failure(row, "malformed", kind) from None
        if name == "reason" and not value.strip():
            raise failure(row, "malformed", kind)
    if kind == "response":
        if payload["email_snapshot"]:
            try:
                validate_email(payload["email_snapshot"])
            except ValidationError:
                raise failure(row, "malformed", kind) from None
        if check_consistency:
            delay = payload["delay_other"]
            if row.program_completion == "ACCORDING_TO_SCHEDULE":
                if row.extra_terms_count is not None or row.delay_reasons or delay:
                    raise failure(row, "malformed", kind)
            elif row.program_completion == "WITH_SOME_DELAY":
                if row.extra_terms_count is None:
                    raise failure(row, "malformed", kind)
            elif row.extra_terms_count is not None or row.delay_reasons or delay:
                raise failure(row, "malformed", kind)
            if ("OTHER" in row.delay_reasons) != bool(delay):
                raise failure(row, "malformed", kind)
            if ("OTHER" in row.significant_learning_experiences) != bool(
                payload["significant_learning_other"]
            ):
                raise failure(row, "malformed", kind)
    return payload


def plaintext(row, kind):
    names = LIMITS if kind == "response" else {"note" if kind == "opportunity" else "reason"}
    return validate(row, {name: getattr(row, name) for name in names}, kind)


def encrypt(ring, row, payload, kind):
    payload = validate(row, payload, kind)
    envelope = {"schema_version": 1, **binding(row, kind), "payload": payload}
    raw = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return ring.encrypt(raw).decode("ascii")


def _reject_constant(_value):
    raise ValueError("Non-finite JSON")


def decrypt(ring, row, token, kind, *, check_consistency=True):
    if not isinstance(token, str) or not token:
        raise failure(row, "missing", kind)
    try:
        raw = ring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise failure(row, "undecryptable", kind) from None
    try:
        envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise failure(row, "malformed", kind) from None
    expected = binding(row, kind)
    if not isinstance(envelope, dict) or set(envelope) != {
        "schema_version",
        "payload",
        *expected,
    }:
        raise failure(row, "malformed", kind)
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise failure(row, "unsupported_schema", kind)
    if any(envelope[name] != value for name, value in expected.items()):
        raise failure(row, "binding_mismatch", kind)
    return validate(row, envelope["payload"], kind, check_consistency=check_consistency)
