"""Authority relation fence: brief maintenance is waited out, real writers still refuse.

PostgreSQL autovacuum holds SHARE UPDATE EXCLUSIVE on the small authority tables and yields only
to a waiting request. These tests use a second connection as the stand-in holder, because a real
autovacuum worker cannot be scheduled from a test.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection, transaction

from compass.counseling import continuity_locks
from compass.counseling.continuity_rules import ContinuityError

pytestmark = pytest.mark.django_db(transaction=True)


def hold(mode: str, ready: threading.Event, release: threading.Event):
    """Hold `mode` on accounts_role from another connection until released."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"LOCK TABLE accounts_role IN {mode} MODE")
            ready.set()
            release.wait(timeout=10)
    finally:
        connection.close()


def lock_timeout() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SHOW lock_timeout")
        return cursor.fetchone()[0]


@pytest.fixture
def fast_retries(monkeypatch):
    monkeypatch.setattr(continuity_locks, "LOCK_RETRY_DELAYS_SECONDS", (0.01, 0.01))


def test_maintenance_holder_is_waited_out_and_lock_timeout_is_restored(monkeypatch, fast_retries):
    # Stand in for autovacuum: the classifier says maintenance, the holder releases after 0.5 s.
    monkeypatch.setattr(continuity_locks, "_blocked_only_by_maintenance", lambda cursor: True)
    ready, release = threading.Event(), threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        holder = pool.submit(hold, "SHARE UPDATE EXCLUSIVE", ready, release)
        assert ready.wait(timeout=5)
        threading.Timer(0.5, release.set).start()
        with transaction.atomic():
            before = lock_timeout()
            continuity_locks.lock_authority_relations()
            assert lock_timeout() == before
        holder.result(timeout=10)


def test_application_session_is_never_classified_as_maintenance():
    ready, release = threading.Event(), threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        holder = pool.submit(hold, "SHARE UPDATE EXCLUSIVE", ready, release)
        assert ready.wait(timeout=5)
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                assert continuity_locks._blocked_only_by_maintenance(cursor) is False
        finally:
            release.set()
        holder.result(timeout=10)


def test_real_authority_writer_still_refuses_without_waiting(fast_retries):
    ready, release = threading.Event(), threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        holder = pool.submit(hold, "ROW EXCLUSIVE", ready, release)
        assert ready.wait(timeout=5)
        try:
            with pytest.raises(ContinuityError) as refused, transaction.atomic():
                continuity_locks.lock_authority_relations()
            assert refused.value.code == "continuity_authority_busy"
        finally:
            release.set()
        holder.result(timeout=10)


def test_no_holder_takes_the_fence_immediately():
    with transaction.atomic(), connection.cursor() as cursor:
        assert continuity_locks._blocked_only_by_maintenance(cursor) is False
        continuity_locks.lock_authority_relations()
