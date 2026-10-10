"""Routine v1 compatibility oracle and startup policy, using synthetic inputs only."""

from __future__ import annotations

import base64
import json
import runpy
from pathlib import Path
from uuid import UUID

import pytest
from cryptography.fernet import Fernet, MultiFernet
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from compass.routine_interviews.content import empty_evaluation, empty_intake
from compass.routine_interviews.crypto import (
    RoutineContentSection,
    decrypt_section,
    encrypt_section,
    encrypted_with_primary_key,
    reencrypt_with_primary_key,
)
from compass.routine_interviews.errors import RoutineContentUnavailable
from compass.routine_interviews.migrations import _routine_content_v1 as frozen

K1 = base64.urlsafe_b64encode(b"1" * 32).decode("ascii")
K2 = base64.urlsafe_b64encode(b"2" * 32).decode("ascii")
K3 = base64.urlsafe_b64encode(b"3" * 32).decode("ascii")
RECORD_ID = UUID("11111111-2222-4333-8444-555555555555")
SETTING = "ROUTINE_INTERVIEW_ENCRYPTION_KEYS"


@pytest.mark.parametrize("section", list(RoutineContentSection))
@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2, K1))
def test_frozen_v1_and_new_adapter_read_each_other_with_exact_envelope(section):
    payload = (
        {**empty_intake(), "career_goals": "Synthetic résumé 🌱"}
        if section == RoutineContentSection.STUDENT_INTAKE
        else {**empty_evaluation(), "academic_adjustment_rating": 8, "recommendations": "ñ"}
    )
    old_ring = MultiFernet([Fernet(K1)])
    old = frozen.encrypt(old_ring, RECORD_ID, section.value, payload)
    assert decrypt_section(old, routine_interview_id=RECORD_ID, section=section) == payload
    assert not encrypted_with_primary_key(old)

    new = encrypt_section(routine_interview_id=RECORD_ID, section=section, payload=payload)
    ring = frozen.keyring()
    assert frozen.decrypt(ring, new, RECORD_ID, section.value) == payload
    assert encrypted_with_primary_key(new)
    plaintext = Fernet(K2).decrypt(new.encode("ascii"))
    expected = {
        "schema_version": 1,
        "routine_interview_id": str(RECORD_ID),
        "section": section.value,
        "payload": payload,
    }
    assert json.loads(plaintext) == expected
    assert set(json.loads(plaintext)) == {
        "schema_version",
        "routine_interview_id",
        "section",
        "payload",
    }
    assert plaintext == json.dumps(
        expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    assert plaintext == Fernet(K1).decrypt(old.encode("ascii"))
    rotated = reencrypt_with_primary_key(old)
    assert encrypted_with_primary_key(rotated)
    assert Fernet(K2).decrypt(rotated.encode("ascii")) == plaintext
    assert frozen.decrypt(ring, rotated, RECORD_ID, section.value) == payload


def test_stable_pre_extraction_fixture_remains_readable_without_rewriting_it():
    fixture = json.loads((Path(__file__).parent / "fixtures/routine-content-v1.json").read_text())
    record_id = UUID(fixture["routine_interview_id"])
    section = RoutineContentSection(fixture["section"])
    assert fixture["key"] == K1
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2, K1)):
        assert (
            decrypt_section(fixture["token"], routine_interview_id=record_id, section=section)
            == (fixture["payload"])
        )
        assert (
            frozen.decrypt(frozen.keyring(), fixture["token"], record_id, section.value)
            == (fixture["payload"])
        )


@pytest.mark.parametrize(
    ("record_id", "section"),
    [
        (UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"), RoutineContentSection.STUDENT_INTAKE),
        (RECORD_ID, RoutineContentSection.COUNSELOR_EVALUATION),
    ],
)
@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
def test_legacy_token_rebinding_maps_to_unchanged_safe_routine_error(record_id, section):
    fixture = json.loads((Path(__file__).parent / "fixtures/routine-content-v1.json").read_text())
    with pytest.raises(RoutineContentUnavailable) as caught:
        decrypt_section(fixture["token"], routine_interview_id=record_id, section=section)
    assert caught.value.reason == "binding_mismatch"
    assert caught.value.routine_interview_id == record_id
    assert caught.value.section == section.value
    assert str(caught.value) == "The Routine Interview content is unavailable."
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=())
def test_adapter_preserves_missing_content_and_invalid_configuration_results():
    with pytest.raises(RoutineContentUnavailable) as caught:
        decrypt_section(
            None, routine_interview_id=RECORD_ID, section=RoutineContentSection.STUDENT_INTAKE
        )
    assert caught.value.reason == "missing"
    with pytest.raises(ImproperlyConfigured, match=SETTING):
        encrypt_section(
            routine_interview_id=RECORD_ID, section=RoutineContentSection.STUDENT_INTAKE, payload={}
        )


@pytest.fixture
def settings_env(monkeypatch):
    for name in (SETTING, "SECRET_KEY", "AUTH_TOTP_ENCRYPTION_KEY"):
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    monkeypatch.setenv(SETTING, K1)
    monkeypatch.setenv("SECRET_KEY", "synthetic-unrelated-django-secret")
    monkeypatch.setenv("AUTH_TOTP_ENCRYPTION_KEY", K3)


def _load_settings():
    return runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))


@pytest.mark.parametrize("value", [None, "", "synthetic-invalid-key", f"{K1},,{K2}", f"{K1},{K1}"])
def test_startup_still_rejects_missing_invalid_and_duplicate_routine_keys(
    settings_env, monkeypatch, value
):
    if value is None:
        monkeypatch.delenv(SETTING)
    else:
        monkeypatch.setenv(SETTING, value)
    with pytest.raises(ValueError, match=SETTING) as caught:
        _load_settings()
    assert K1 not in str(caught.value)
    assert K2 not in str(caught.value)
    assert "synthetic-invalid-key" not in str(caught.value)


@pytest.mark.parametrize("other_setting", ["SECRET_KEY", "AUTH_TOTP_ENCRYPTION_KEY"])
def test_startup_still_rejects_reuse_of_django_or_totp_key(
    settings_env, monkeypatch, other_setting
):
    monkeypatch.setenv(other_setting, K1)
    with pytest.raises(
        ValueError, match="must not reuse SECRET_KEY or AUTH_TOTP_ENCRYPTION_KEY"
    ) as caught:
        _load_settings()
    assert K1 not in str(caught.value)


def test_startup_keeps_exact_order_and_file_backed_keyring(settings_env, monkeypatch, tmp_path):
    monkeypatch.setenv(SETTING, f" {K2} ,\n{K1}\n")
    assert _load_settings()[SETTING] == (K2, K1)
    key_file = tmp_path / "synthetic-keyring"
    key_file.write_text(f" {K2} ,\n{K1}\n")
    monkeypatch.delenv(SETTING)
    monkeypatch.setenv(f"{SETTING}_FILE", str(key_file))
    assert _load_settings()[SETTING] == (K2, K1)
