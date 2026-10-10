"""Synthetic startup and least-privilege configuration proofs; no deployment key material."""

import runpy
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

SETTING = "ASSESSMENT_RECORD_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
RINGS = [
    "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
    "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
    "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    "GUIDANCE_MESSAGE_ENCRYPTION_KEYS",
]


def settings():
    return runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))


@pytest.mark.parametrize(
    "source", ["SECRET_KEY", "AUTH_TOTP_ENCRYPTION_KEY", "WEB_PUSH_STORAGE_KEY", *RINGS]
)
@pytest.mark.parametrize("position", [0, 1])
def test_dedicated_key_rejects_every_domain_and_security_secret(monkeypatch, source, position):
    values = {name: Fernet.generate_key().decode() for name in RINGS}
    values.update(
        {
            name: Fernet.generate_key().decode()
            for name in ["SECRET_KEY", "AUTH_TOTP_ENCRYPTION_KEY", "WEB_PUSH_STORAGE_KEY"]
        }
    )
    reused = Fernet.generate_key().decode() if position and source in RINGS else values[source]
    if position and source in RINGS:
        values[source] += "," + reused
    fresh = Fernet.generate_key().decode()
    values[SETTING] = fresh + "," + reused if position else reused + "," + fresh
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError) as caught:
        settings()
    assert SETTING in str(caught.value) and "reuse" in str(caught.value)
    assert reused not in str(caught.value) and fresh not in str(caught.value)


@pytest.mark.parametrize("bad", ["not-a-key", " , ", "bad,,entry", "duplicate"])
def test_invalid_or_duplicate_config_fails_safely(monkeypatch, bad):
    if bad == "duplicate":
        key = Fernet.generate_key().decode()
        bad = key + "," + key
    monkeypatch.setenv(SETTING, bad)
    with pytest.raises(ValueError) as caught:
        settings()
    assert SETTING in str(caught.value) and bad not in str(caught.value)


def test_keyless_nonweb_boot_has_no_fallback(monkeypatch):
    monkeypatch.setenv(SETTING, "")
    monkeypatch.setenv(SETTING + "_FILE", "")
    assert settings()[SETTING] == ()
