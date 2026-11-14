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


# A SHARE lock also conflicts with autovacuum/autoanalyze (SHARE UPDATE EXCLUSIVE), which
# yields only to a *waiting* request. NOWAIT never waits, so a brief maintenance pass on one
# of these small tables would refuse a valid operation. Retry a few NOWAIT attempts instead of
# waiting, which keeps the no-inversion property; a real authority writer still ends in busy.
LOCK_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.5)


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
            if delay is None:
                raise ContinuityError("authority_busy", 409) from exc
            time.sleep(delay)
