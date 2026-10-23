"""Retired resource contracts fail closed; only the canonical resource is active."""

import importlib.util
from uuid import uuid4

import pytest
from django.core.management import get_commands

from compass.counseling import student_session_summary_content as content
from tests.test_student_session_summaries import auth_client, make_user, sync_policy


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["COUNSELOR", "STUDENT", "IT_ADMIN", "GUIDANCE_SERVICES_STAFF"])
def test_legacy_endpoints_are_absent_without_decryption(monkeypatch, role):
    sync_policy()
    actor = make_user(f"old-contract-{role}@example.test", role)

    def forbidden(*args, **kwargs):
        pytest.fail("A retired endpoint must not decrypt summary content.")

    monkeypatch.setattr(content, "decrypt_student_session_summary_content", forbidden)
    client = auth_client(actor)
    eid, sid = uuid4(), uuid4()
    for method, path in (
        ("get", "/api/v1/counseling/me/shared-summaries"),
        ("get", f"/api/v1/counseling/me/shared-summaries/{sid}"),
        ("get", f"/api/v1/counseling/encounters/{eid}/shared-summary"),
        ("put", f"/api/v1/counseling/encounters/{eid}/shared-summary"),
        ("post", f"/api/v1/counseling/encounters/{eid}/shared-summary/publish"),
        ("get", f"/api/v1/counseling/context/APPOINTMENT/{eid}/shared-summaries"),
        ("get", f"/api/v1/counseling/context/APPOINTMENT/{eid}/student-session-summaries"),
    ):
        assert getattr(client, method)(path).status_code == 404


def test_retired_modules_and_rotation_command_are_unavailable():
    for module in ("shared_summaries", "shared_summary_content"):
        assert importlib.util.find_spec(f"compass.counseling.{module}") is None
    assert "rotate_counseling_shared_summary_encryption" not in get_commands()
    assert "rotate_student_session_summary_encryption" in get_commands()
