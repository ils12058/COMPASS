"""PostgreSQL fences for selected-source reads, Handoffs and scoped coverage selection.

Authority relation SHARE locks prevent phantoms/updates/deletes without changing the
capability engine or every writer. All acquisition after sorted User locks is NOWAIT.
These intentionally conservative short transactions may conflict with unrelated changes.
"""

import time

from django.db import OperationalError, connection, transaction

from compass.counseling.continuity_rules import ContinuityError

# Compile-time identifiers only. Never accept table/model names from a caller.
AUTHORITY_TABLES = (
    "accounts_role",
    "accounts_capability",
    "accounts_designation",
    "accounts_rolecapability",
    "accounts_designationcapability",
    "accounts_userdesignation",
    "accounts_usercapabilityoverride",
    "student_academics_studentacademicprofile",
    "organization_counselorresponsibility",
    "organization_staffsupervision",
    "organization_college",
    "organization_campus",
)


def _postgres_transaction():
    if connection.vendor != "postgresql" or not connection.in_atomic_block:
        raise ContinuityError("release_coordination_unavailable")
    # A repeatable-read snapshot could retain authority committed before a waited User lock.
    with connection.cursor() as cursor:
        cursor.execute("SHOW transaction_isolation")
        if cursor.fetchone()[0] != "read committed":
            raise ContinuityError("release_coordination_unavailable")


# Lock modes that conflict with SHARE. A writer's ROW EXCLUSIVE is the real authority change;
# autovacuum/autoanalyze hold SHARE UPDATE EXCLUSIVE while maintaining these small tables.
_SHARE_CONFLICTS = (
    "RowExclusiveLock",
    "ShareUpdateExclusiveLock",
    "ShareRowExclusiveLock",
    "ExclusiveLock",
    "AccessExclusiveLock",
)
# A few NOWAIT attempts absorb brief contention without waiting behind any writer.
LOCK_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.5)
# PostgreSQL cancels an ordinary autovacuum that blocks a *waiting* lock request after
# deadlock_timeout (1 s by default). A NOWAIT request never waits, so it would never trigger
# that cancellation; waiting this long is enough for it, and it still ends instead of hanging.
AUTOVACUUM_WAIT = "5s"


def _blocked_only_by_maintenance(cursor) -> bool:
    """True when every conflicting holder on the authority tables is an autovacuum worker."""
    cursor.execute(
        """
        SELECT activity.backend_type
        FROM pg_locks AS lock
        JOIN pg_stat_activity AS activity ON activity.pid = lock.pid
        WHERE lock.locktype = 'relation'
          AND lock.granted
          AND lock.pid <> pg_backend_pid()
          AND lock.relation = ANY(%s::regclass[])
          AND lock.mode = ANY(%s)
        """,
        [list(AUTHORITY_TABLES), list(_SHARE_CONFLICTS)],
    )
    holders = [row[0] for row in cursor.fetchall()]
    return bool(holders) and all(holder == "autovacuum worker" for holder in holders)


def _wait_behind_maintenance(tables: str) -> bool:
    """Wait briefly for the lock, which makes PostgreSQL cancel the blocking autovacuum.

    Only autovacuum blocks at this point, and autovacuum never waits on our locks, so the wait
    cannot form a lock-order cycle with application writers. lock_timeout is restored afterwards
    because SET LOCAL would otherwise outlive this savepoint for the rest of the transaction.
    """
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            previous = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('lock_timeout', %s, true)", [AUTOVACUUM_WAIT])
            cursor.execute(f"LOCK TABLE {tables} IN SHARE MODE")
            cursor.execute("SELECT set_config('lock_timeout', %s, true)", [previous])
        return True
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
            return False
        raise


def lock_authority_relations():
    _postgres_transaction()
    # NOWAIT avoids inversions with existing User -> organization/capability writers.
    tables = ", ".join(connection.ops.quote_name(name) for name in AUTHORITY_TABLES)
    for delay in (*LOCK_RETRY_DELAYS_SECONDS, None):
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f"LOCK TABLE {tables} IN SHARE MODE NOWAIT")
            return
        except OperationalError as exc:
            if getattr(exc.__cause__, "sqlstate", None) != "55P03":
                raise
        with connection.cursor() as cursor:
            maintenance = _blocked_only_by_maintenance(cursor)
        if maintenance and _wait_behind_maintenance(tables):
            return
        if delay is None:
            raise ContinuityError("authority_busy", 409)
        time.sleep(delay)
