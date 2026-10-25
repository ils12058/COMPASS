"""Synthetic Catalog manager and independent-connection race harness."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic

from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.accounts.services import set_user_capability_override
from compass.audit.context import AuditContext
from compass.authentication.models import TOTPFactor
from compass.authentication.sessions import create_auth_session
from compass.organization.models import Campus, CatalogInitialization, College, Program


def manager(role="IT_ADMIN", grant=True):
    call_command("sync_identity_policy", verbosity=0)
    user = User.objects.create_user(
        email=f"{role}-{User.objects.count()}@synthetic.invalid",
        password=None,
        role=Role.objects.get(code=role),
        first_name="Catalog",
        last_name="Operator",
    )
    if grant:
        set_user_capability_override(
            user=user,
            capability="organization.catalog.manage",
            effect="GRANT",
            reason="Synthetic ORG-2 test authority only",
        )
    TOTPFactor.objects.create(
        user=user, encrypted_secret="synthetic-unused-ciphertext", confirmed_at=timezone.now()
    )
    issued = create_auth_session(user, mfa_verified_at=timezone.now())
    return user, issued


def authority(user, issued):
    return dict(
        actor=user,
        actor_session=issued.session,
        context=AuditContext.user(user),
        basis="Synthetic engineering test; no institutional approval",
    )


def hierarchy(*, active=True, configured=True):
    CatalogInitialization.objects.get_or_create(
        id=1, defaults={"source": "ADOPTED", "reference": "Synthetic"}
    )
    c = Campus.objects.create(code=f"C{Campus.objects.count()}", name="Campus", is_active=active)
    k = College.objects.create(campus=c, code="COL", name="College", is_active=active)
    p = Program.objects.create(
        college=k,
        code="PROG",
        name="Program",
        is_active=active,
        academic_classification="BACHELORS" if configured else None,
        year_level_policy_status="CONFIGURED" if configured else "PENDING_POLICY",
        applicable_year_levels=[1, 2, 3, 4] if configured else None,
    )
    return c, k, p


def client_for(issued, *, csrf=True):
    client = Client(enforce_csrf_checks=csrf)
    client.cookies["compass_session"] = issued.token
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client, {"HTTP_X_CSRFTOKEN": token}


def student():
    return User.objects.create_user(
        email=f"student-{User.objects.count()}@synthetic.invalid",
        password=None,
        role=Role.objects.get(code="STUDENT"),
        first_name="Test",
        last_name="Student",
    )


def run_serialized_race(first, second):
    """First real writer holds outer transaction; assert second PG connection waits on gate.

    The database's ungranted advisory lock is the synchronization signal, not elapsed sleep.
    Return second's committed result or its safe domain conflict; propagate first's errors.
    """
    held, release, entering = Event(), Event(), Event()
    second_pid = []

    def winner():
        close_old_connections()
        try:
            with transaction.atomic():
                result = first()
                held.set()
                assert release.wait(15), "race release timed out"
            return result
        finally:
            connection.close()

    def contender():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                second_pid.append(cursor.fetchone()[0])
            entering.set()
            try:
                return second()
            except Exception as exc:
                return exc
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(winner)
        try:
            assert held.wait(15), "first writer did not reach commit barrier"
            b = pool.submit(contender)
            assert entering.wait(15)
            deadline = monotonic() + 10
            waiting = False
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT EXISTS(SELECT 1 FROM pg_locks "
                        "WHERE pid=%s AND locktype='advisory' AND NOT granted)",
                        [second_pid[0]],
                    )
                    waiting = cursor.fetchone()[0]
                if waiting:
                    break
                if b.done():
                    raise AssertionError(f"Second writer did not wait: {b.result()!r}")
                release.wait(0.005)
            assert waiting, "no actual PostgreSQL advisory wait observed"
        finally:
            release.set()
        return a.result(timeout=15), b.result(timeout=15)
