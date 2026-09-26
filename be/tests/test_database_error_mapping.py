"""Database rejections of client data map to stable 4xx errors instead of generic 500s."""

from __future__ import annotations

import psycopg
import pytest
from django.db import IntegrityError

from compass.privacy_governance import expansion
from tests.test_privacy_governance import auth_client, make_dpo, post_json, sync_policy
from tests.test_privacy_governance_expansion import retention_payload


def _integrity_error(cause: Exception) -> IntegrityError:
    error = IntegrityError(str(cause))
    error.__cause__ = cause
    return error


@pytest.mark.django_db
def test_value_the_database_cannot_store_is_a_validation_error():
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
    response = post_json(
        dpo,
        "/api/v1/privacy/retention-policies",
        retention_payload() | {"name": "Contains a NUL\u0000byte"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request_value"
    assert "NUL" not in response.json()["error"]["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cause", "status", "code"),
    [
        (psycopg.errors.UniqueViolation(), 409, "request_conflict"),
        (psycopg.errors.ForeignKeyViolation(), 409, "request_conflict"),
        (psycopg.errors.CheckViolation(), 422, "invalid_request_value"),
        (psycopg.errors.NotNullViolation(), 500, "internal_error"),
    ],
)
def test_uncaught_integrity_errors_are_classified_by_sqlstate(monkeypatch, cause, status, code):
    sync_policy()
    dpo = auth_client(make_dpo())
    dpo.raise_request_exception = False

    def reject(**kwargs):
        raise _integrity_error(cause)

    monkeypatch.setattr(expansion, "list_retention", reject)
    response = dpo.get("/api/v1/privacy/retention-policies")

    assert response.status_code == status
    body = response.json()["error"]
    assert body["code"] == code
    assert "Violation" not in body["message"]
