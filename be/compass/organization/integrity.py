"""Cooperative catalog gate. Take before user/domain locks; held until outer commit.

Old binaries, unrestricted ORM writes and privileged SQL do not participate. No gate
upgrade is permitted: a dependent writer must never invoke a catalog mutation.
"""

from contextlib import contextmanager
from functools import wraps

from django.db import connection, transaction

CATALOG_INTEGRITY_LOCK = 477580715032


@contextmanager
def catalog_gate(*, exclusive=False):
    with transaction.atomic():
        function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {function}(%s)", [CATALOG_INTEGRITY_LOCK])
        yield


def catalog_dependent_write(function):
    @wraps(function)
    def coordinated(*args, **kwargs):
        with catalog_gate():
            return function(*args, **kwargs)

    return coordinated
