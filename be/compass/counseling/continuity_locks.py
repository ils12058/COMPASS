"""PostgreSQL release synchronization limited to the two selected-source reads.

Authority relation SHARE locks prevent phantoms/updates/deletes without changing the
capability engine or every writer. All acquisition after sorted User locks is NOWAIT.
These intentionally conservative short transactions may conflict with unrelated changes.
"""

from contextlib import contextmanager

from django.db import OperationalError, connection, transaction

from compass.counseling.continuity_policy import ContinuityError

# Compile-time identifiers only. Never accept table/model names from a caller.
AUTHORITY_TABLES = (
    "accounts_role",
    "accounts_capability",
    "accounts_designation",
    "accounts_rolecapability",
    "accounts_designationcapability",
    "accounts_userdesignation",
    "accounts_usercapabilityoverride",
    "organization_studentaffiliation",
    "organization_college",
    "organization_campus",
)
# Two-int PostgreSQL advisory namespace, dedicated to continuity policy publication.
POLICY_LOCK_NAMESPACE = 1129270608
POLICY_LOCK_KEY = 2


def _postgres_transaction():
    if connection.vendor != "postgresql" or not connection.in_atomic_block:
        raise ContinuityError("release_coordination_unavailable")
    # A repeatable-read snapshot could retain authority committed before a waited User lock.
    with connection.cursor() as cursor:
        cursor.execute("SHOW transaction_isolation")
        if cursor.fetchone()[0] != "read committed":
            raise ContinuityError("release_coordination_unavailable")


def lock_policy_for_selected_read():
    _postgres_transaction()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_try_advisory_xact_lock_shared(%s, %s)",
            [POLICY_LOCK_NAMESPACE, POLICY_LOCK_KEY],
        )
        if not cursor.fetchone()[0]:
            raise ContinuityError("policy_busy", 409)


@contextmanager
def continuity_policy_change():
    """Required future provider publication/invalidation boundary; no policy writer exists.

    Acquire before changing any provider-visible state, hold through commit. Providers
    must use transactionally visible storage; an in-process fixture is test-only.
    """
    with transaction.atomic():
        _postgres_transaction()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s, %s)", [POLICY_LOCK_NAMESPACE, POLICY_LOCK_KEY]
            )
            if not cursor.fetchone()[0]:
                raise ContinuityError("policy_busy", 409)
        yield


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
