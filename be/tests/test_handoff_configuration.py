"""Isolated configuration parsing only; never reads deployed runtime secrets."""

import os
import runpy
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

SETTINGS = Path(__file__).parents[1] / "config/settings.py"


@pytest.mark.parametrize(
    "domain",
    [
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS",
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "GUIDANCE_MESSAGE_ENCRYPTION_KEYS",
        "ASSESSMENT_RECORD_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS",
    ],
)
def test_handoff_ring_cannot_reuse_any_existing_secret(monkeypatch, domain):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(domain, key)
    monkeypatch.setenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS", key)
    monkeypatch.delenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS_FILE", raising=False)
    with pytest.raises(ValueError, match="COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS") as e:
        runpy.run_path(str(SETTINGS))
    assert key not in str(e.value)


@pytest.mark.parametrize("value", ["bad", ",", None, "duplicate"])
def test_configuration_missing_invalid_and_duplicate(monkeypatch, value):
    monkeypatch.delenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS_FILE", raising=False)
    if value is None:
        monkeypatch.delenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS", raising=False)
        assert runpy.run_path(str(SETTINGS))["COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS"] == ()
    else:
        key = Fernet.generate_key().decode()
        monkeypatch.setenv(
            "COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS",
            key + "," + key if value == "duplicate" else value,
        )
        with pytest.raises(ValueError):
            runpy.run_path(str(SETTINGS))


def test_file_backed_ring_no_conflicting_direct_setting(monkeypatch, tmp_path):
    key = Fernet.generate_key().decode()
    source = tmp_path / "synthetic-handoff"
    source.write_text(key + "\n")
    monkeypatch.delenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS_FILE", str(source))
    assert runpy.run_path(str(SETTINGS))["COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS"] == (key,)
    monkeypatch.setenv("COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS", key)
    with pytest.raises(ValueError, match="cannot both be set"):
        runpy.run_path(str(SETTINGS))
    assert os.environ["COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS"] == key
