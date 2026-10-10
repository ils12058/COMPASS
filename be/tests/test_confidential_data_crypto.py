"""Synthetic security and format contracts for the shared primitive (ADR-079)."""

from __future__ import annotations

import base64
import json
import subprocess
import sys

import pytest
from cryptography.fernet import Fernet, InvalidToken

from compass.confidential_data.crypto import (
    decrypt_bound_json,
    encrypt_bound_json,
    encrypted_with_primary_key,
    keyring_reuses_secret,
    parse_fernet_keyring,
    reencrypt_with_primary_key,
)
from compass.confidential_data.errors import ConfidentialDataUnavailable

# Fixed, public, synthetic keys. Never configure these outside tests.
K1 = base64.urlsafe_b64encode(b"1" * 32).decode("ascii")
K2 = base64.urlsafe_b64encode(b"2" * 32).decode("ascii")
SETTING = "SYNTHETIC_DOMAIN_KEYS"
BINDING = {"record_id": "synthetic-record-1", "section": "notes"}
CONTEXT = {"schema_version": 7, "binding": BINDING}
PAYLOAD = {"text": "Línea — café, 日本語, 🌱", "nested": {"items": [1, None, True, "ñ"]}}


def _encrypt(payload=PAYLOAD, *, keyring=(K1,), **context):
    return encrypt_bound_json(keyring=keyring, payload=payload, **{**CONTEXT, **context})


def _decrypt(token, *, keyring=(K1,), **context):
    return decrypt_bound_json(token, keyring=keyring, **{**CONTEXT, **context})


def _tampered(token):
    index = len(token) // 2
    return token[:index] + ("A" if token[index] != "A" else "B") + token[index + 1 :]


def _assert_safe(error, *inputs):
    exposed = str(error) + repr(error) + repr(error.args)
    for value in (K1, K2, *inputs):
        assert value not in exposed
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__


def test_keyring_accepts_config_and_split_sequences_in_exact_order():
    for configured in (f" {K2} ,\n{K1}\n", [K2, K1], (K2, K1)):
        assert parse_fernet_keyring(configured, setting=SETTING) == (K2, K1)
    assert parse_fernet_keyring(K1, setting=SETTING) == (K1,)


def _noncanonical(key):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    return key[:42] + alphabet[alphabet.index(key[42]) ^ 1] + key[43:]


@pytest.mark.parametrize(
    ("configured", "message"),
    [
        ("", "is required"),
        ((), "is required"),
        (None, "is required"),
        (" , ", "is required"),
        (f"{K1},,{K2}", "entry 2 is empty"),
        ((K1, 42), "entry 2 is empty"),
        ((K1, None), "entry 2 is empty"),
        ("not-a-key", "entry 1 is not a valid Fernet key"),
        ("🔒", "entry 1 is not a valid Fernet key"),
        (base64.urlsafe_b64encode(b"x" * 16).decode(), "entry 1 is not a valid Fernet key"),
        (_noncanonical(K1), "entry 1 is not a valid Fernet key"),
        (f"{K1},{K2},{K1}", "entry 3 repeats an earlier key"),
    ],
)
def test_keyring_rejects_unsafe_inputs_without_revealing_keys(configured, message):
    with pytest.raises(ValueError, match=message) as caught:
        parse_fernet_keyring(configured, setting=SETTING)
    assert SETTING in str(caught.value)
    _assert_safe(caught.value)


def test_key_reuse_detects_decoded_equivalents_and_ignores_unrelated_values():
    assert keyring_reuses_secret((K2, K1), "other-secret", K1)
    assert keyring_reuses_secret((K1,), f" {K1}\n")
    assert keyring_reuses_secret((K1,), _noncanonical(K1))
    assert not keyring_reuses_secret((K1,), "", "other-secret", K2)


def test_unicode_nested_json_and_exact_canonical_plaintext_round_trip(caplog):
    token = _encrypt(keyring=(K2, K1))
    expected = {"schema_version": 7, **BINDING, "payload": PAYLOAD}
    plaintext = Fernet(K2).decrypt(token.encode("ascii"))
    assert plaintext == json.dumps(
        expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    assert _decrypt(token, keyring=(K2, K1)) == PAYLOAD
    assert _encrypt(keyring=(K2, K1)) != token
    with pytest.raises(InvalidToken):
        Fernet(K1).decrypt(token.encode("ascii"))
    assert caplog.records == []


@pytest.mark.parametrize(
    "binding", [{**BINDING, "record_id": "other"}, {**BINDING, "section": "other"}]
)
def test_authenticated_token_cannot_move_between_contexts(binding):
    token = _encrypt()
    with pytest.raises(ConfidentialDataUnavailable) as caught:
        _decrypt(token, binding=binding)
    assert caught.value.reason == "binding_mismatch"
    _assert_safe(caught.value, token, BINDING["record_id"], PAYLOAD["text"])


@pytest.mark.parametrize("token", [None, "", b"unexpected-bytes", 42])
def test_missing_or_non_string_token_fails_closed(token):
    with pytest.raises(ConfidentialDataUnavailable) as caught:
        _decrypt(token)
    assert caught.value.reason == "missing"
    _assert_safe(caught.value)


@pytest.mark.parametrize(
    "damage", ["tampered", "truncated", "not-fernet", "non-ascii", "wrong-key"]
)
def test_untrusted_tokens_fail_without_content_or_parser_details(damage):
    valid = _encrypt()
    token = {
        "tampered": _tampered(valid),
        "truncated": valid[:-12],
        "not-fernet": "synthetic-non-fernet-token",
        "non-ascii": "synthetic-🔒-token",
        "wrong-key": _encrypt(keyring=(K2,)),
    }[damage]
    with pytest.raises(ConfidentialDataUnavailable) as caught:
        _decrypt(token)
    assert caught.value.reason == "undecryptable"
    _assert_safe(caught.value, token)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"remove": "schema_version"}, "malformed"),
        ({"remove": "payload"}, "malformed"),
        ({"remove": "record_id"}, "malformed"),
        ({"extra": "synthetic-plaintext"}, "malformed"),
        ({"schema_version": True}, "unsupported_schema"),
        ({"schema_version": "7"}, "unsupported_schema"),
        ({"schema_version": 7.0}, "unsupported_schema"),
        ({"schema_version": 8}, "unsupported_schema"),
        ({"payload": []}, "malformed"),
        ({"payload": None}, "malformed"),
        ({"record_id": {"nested": "wrong"}}, "binding_mismatch"),
    ],
)
def test_authentic_but_malformed_or_unsupported_envelope_fails_closed(change, reason):
    envelope = {"schema_version": 7, **BINDING, "payload": PAYLOAD}
    change = dict(change)
    removed = change.pop("remove", None)
    if removed:
        envelope.pop(removed)
    envelope.update(change)
    token = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode("ascii")
    with pytest.raises(ConfidentialDataUnavailable) as caught:
        _decrypt(token)
    assert caught.value.reason == reason
    _assert_safe(caught.value, token, "synthetic-plaintext", PAYLOAD["text"])


@pytest.mark.parametrize(
    "plaintext",
    [
        b"synthetic-private-not-json",
        b"\xff\xfe",
        b'["synthetic-private-list"]',
        b"null",
        b'{"payload":{"private":NaN},"schema_version":7,"record_id":"x","section":"notes"}',
        b"[" * 2000 + b"0" + b"]" * 2000,
    ],
)
def test_invalid_utf8_json_and_non_object_plaintext_is_safe(plaintext):
    token = Fernet(K1).encrypt(plaintext).decode("ascii")
    with pytest.raises(ConfidentialDataUnavailable) as caught:
        _decrypt(token)
    assert caught.value.reason == "malformed"
    _assert_safe(caught.value, token, "synthetic-private")


@pytest.mark.parametrize("reserved", ["schema_version", "payload"])
def test_binding_cannot_override_reserved_envelope_fields(reserved):
    binding = {reserved: "synthetic-private-context"}
    for operation in (
        lambda: _encrypt(binding=binding),
        lambda: _decrypt(_encrypt(), binding=binding),
    ):
        with pytest.raises(ValueError, match="reserved key") as caught:
            operation()
        _assert_safe(caught.value, "synthetic-private-context")


@pytest.mark.parametrize("binding", [{"": "context"}, {42: "context"}, {"id": []}, []])
def test_binding_requires_simple_string_identifiers(binding):
    with pytest.raises(ValueError, match="string"):
        _encrypt(binding=binding)


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_caller_schema_version_must_be_an_actual_integer(version):
    with pytest.raises(ValueError, match="integer"):
        _encrypt(schema_version=version)


@pytest.mark.parametrize(
    "payload",
    [
        {"private": float("nan")},
        {"private": float("inf")},
        {"private": float("-inf")},
        {"private": {"not-json-safe"}},
        {"private": object()},
        {"private": b"synthetic-private-bytes"},
        {"private": "synthetic-private-\ud800"},
        [],
        None,
    ],
)
def test_unserializable_content_raises_only_a_safe_error(payload):
    with pytest.raises(ConfidentialDataUnavailable) as caught:
        _encrypt(payload)
    assert caught.value.reason == "malformed"
    _assert_safe(caught.value, "synthetic-private")


def test_all_token_operations_validate_the_supplied_keyring():
    token = _encrypt()
    for operation in (
        lambda: _encrypt(keyring=(K1, K1)),
        lambda: _decrypt(token, keyring=()),
        lambda: encrypted_with_primary_key(token, keyring=(K1, "invalid")),
        lambda: reencrypt_with_primary_key(token, keyring=(K1, K1)),
    ):
        with pytest.raises(ValueError) as caught:
            operation()
        _assert_safe(caught.value, token)


def test_previous_key_reads_and_rotation_preserves_exact_bytes_and_timestamp():
    plaintext = b'  {"synthetic":"private","spacing":"unchanged"}  '
    timestamp = 1_234_567_890
    old = Fernet(K1).encrypt_at_time(plaintext, timestamp).decode("ascii")
    assert encrypted_with_primary_key(old, keyring=(K1,))
    assert not encrypted_with_primary_key(old, keyring=(K2, K1))
    rotated = reencrypt_with_primary_key(old, keyring=(K2, K1))
    assert encrypted_with_primary_key(rotated, keyring=(K2, K1))
    assert Fernet(K2).decrypt(rotated.encode()) == plaintext
    assert Fernet(K2).extract_timestamp(rotated.encode()) == timestamp
    with pytest.raises(InvalidToken):
        Fernet(K1).decrypt(rotated.encode())
    # Rewrapping alone does not pretend to validate a domain envelope.
    with pytest.raises(ConfidentialDataUnavailable, match="unavailable"):
        _decrypt(rotated, keyring=(K2, K1))
    assert _decrypt(_encrypt(), keyring=(K2, K1)) == PAYLOAD


@pytest.mark.parametrize("token", ["", "synthetic-invalid-token", "🔒", None])
def test_primary_key_check_returns_false_and_rotation_errors_are_content_free(token):
    assert not encrypted_with_primary_key(token, keyring=(K1,))
    with pytest.raises(InvalidToken) as caught:
        reencrypt_with_primary_key(token, keyring=(K1,))
    assert caught.value.args == ()
    if isinstance(token, str) and token:
        _assert_safe(caught.value, token)


def test_safe_error_rejects_unbounded_reason_text():
    with pytest.raises(ValueError) as caught:
        ConfidentialDataUnavailable(reason="synthetic-private-reason")
    _assert_safe(caught.value, "synthetic-private-reason")


def test_shared_primitive_runs_without_loading_django_or_domain_modules():
    script = f"""
import sys
from compass.confidential_data.crypto import encrypt_bound_json, decrypt_bound_json
kwargs = dict(keyring=({K1!r},), schema_version=9, binding={{'id': 'synthetic'}})
token = encrypt_bound_json(payload={{'text': 'synthetic'}}, **kwargs)
assert decrypt_bound_json(token, **kwargs) == {{'text': 'synthetic'}}
assert not any(name == 'django' or name.startswith('django.') for name in sys.modules)
assert not any(name.startswith('compass.routine_interviews') for name in sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
