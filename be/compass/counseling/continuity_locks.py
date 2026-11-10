"""PostgreSQL fences for selected-source reads, Handoffs and scoped coverage selection.

Authority relation SHARE locks prevent phantoms/updates/deletes without changing the
capability engine or every writer. All acquisition after sorted User locks is NOWAIT.
These intentionally conservative short transactions may conflict with unrelated changes.
"""

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


def lock_authority_relations():
    _postgres_transaction()
    # NOWAIT avoids inversions with existing User -> organization/capability writers.
    tables = ", ".join(connection.ops.quote_name(name) for name in AUTHORITY_TABLES)
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"LOCK TABLE {tables} IN SHARE MODE NOWAIT")
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) == "55P03":
            raise ContinuityError("authority_busy", 409) from exc
        raise
