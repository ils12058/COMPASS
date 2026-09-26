"""Row locks stay on the entity being changed instead of shared reference rows."""

from __future__ import annotations

import ast
import threading
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import Client

from compass.accounts.models import Role, User

BACKEND = Path(__file__).resolve().parents[1] / "compass"


def _call_chain(node: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        calls.append(node)
        node = node.func.value
    return calls


def test_every_locking_query_that_joins_related_rows_declares_its_lock_scope():
    unscoped: list[str] = []
    for path in sorted(BACKEND.rglob("*.py")):
        if "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        seen: set[int] = set()
        for node in ast.walk(tree):
            calls = _call_chain(node)
            names = [call.func.attr for call in calls]
            if "select_for_update" not in names or "select_related" not in names:
                continue
            lock = next(call for call in calls if call.func.attr == "select_for_update")
            if lock.lineno in seen:
                continue
            seen.add(lock.lineno)
            if not any(keyword.arg == "of" for keyword in lock.keywords):
                unscoped.append(f"{path.relative_to(BACKEND.parent)}:{lock.lineno}")
    # PostgreSQL FOR UPDATE without OF also locks every joined row, such as shared Role rows.
    assert unscoped == []


@pytest.mark.django_db(transaction=True)
def test_password_login_does_not_hold_the_shared_role_row(monkeypatch):
    call_command("sync_identity_policy", stdout=StringIO())
    student_role = Role.objects.get(code="STUDENT")
    User.objects.create_user(
        email="lock-scope@example.edu",
        password="a-lock-scope-password",
        role=student_role,
        first_name="Lock",
        last_name="Scope",
    )
    from compass.authentication import services as auth_services

    original = auth_services._password_matches
    observed: dict[str, object] = {}

    def probe_role_lock_during_password_check(user, password):
        def other_session():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("BEGIN")
                    try:
                        cursor.execute(
                            "SELECT id FROM accounts_role WHERE id = %s FOR UPDATE NOWAIT",
                            [student_role.pk],
                        )
                        observed["role_lock_available"] = True
                    except Exception as exc:  # pragma: no cover - failure path is the assertion
                        observed["role_lock_available"] = False
                        observed["error"] = type(exc).__name__
                    finally:
                        cursor.execute("ROLLBACK")
            finally:
                # Thread-local connections persist under CONN_MAX_AGE; close explicitly.
                connection.close()

        worker = threading.Thread(target=other_session)
        worker.start()
        worker.join(timeout=10)
        return original(user, password)

    monkeypatch.setattr(auth_services, "_password_matches", probe_role_lock_during_password_check)
    client = Client()
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        data={"email": "lock-scope@example.edu", "password": "a-lock-scope-password"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code in {200, 403}
    assert observed == {"role_lock_available": True}
