"""Fail-closed guard for the reset-only canonical migration baseline (CANON-1C).

The canonical baseline replaced every historical COMPASS migration with one
``0001_canonical_baseline`` per app. It installs only into an empty database. A database that still
records any pre-canonical COMPASS migration (for example a restored backup of the old staging
schema) must never be "upgraded" in place, faked forward or served by this code: its tables, the
retired disposition ledger and old ciphertext history do not match the canonical schema.

A database system check reports the condition at the start of ``migrate`` and in
``manage.py check --database default``; a ``pre_migrate`` receiver enforces it even when checks are
skipped. Both only read ``django_migrations``.
"""

from __future__ import annotations

from django.apps import apps
from django.core import checks
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.loader import MigrationLoader

CHECK_ID = "compass.E001"


def _compass_labels() -> set[str]:
    return {config.label for config in apps.get_app_configs() if config.name.startswith("compass.")}


def pre_canonical_history(connection) -> list[str]:
    """COMPASS migrations recorded in the database that the current code does not define."""

    if "django_migrations" not in connection.introspection.table_names():
        return []
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    labels = _compass_labels()
    return sorted(
        f"{app}.{name}"
        for app, name in loader.applied_migrations
        if app in labels and (app, name) not in loader.disk_migrations
    )


@checks.register(checks.Tags.database)
def check_canonical_migration_history(app_configs=None, databases=None, **kwargs):
    errors = []
    for alias in databases or ():
        if alias != DEFAULT_DB_ALIAS:
            continue
        unknown = pre_canonical_history(connections[alias])
        if unknown:
            errors.append(
                checks.Error(
                    "This database records COMPASS migrations that the canonical baseline does not "
                    f"define ({len(unknown)}, for example {unknown[0]}). The canonical baseline is "
                    "reset-only and installs only into an empty database.",
                    hint=(
                        "Do not migrate, fake or restore pre-canonical history into this runtime. "
                        "Follow the reviewed clean-rebuild runbook."
                    ),
                    id=CHECK_ID,
                )
            )
    return errors


def refuse_pre_canonical_migrate(sender, using=DEFAULT_DB_ALIAS, **kwargs):
    """``pre_migrate`` receiver: never apply the canonical baseline over pre-canonical history."""

    unknown = pre_canonical_history(connections[using])
    if unknown:
        raise CommandError(
            f"Refusing to migrate: the database records {len(unknown)} pre-canonical COMPASS "
            f"migrations (for example {unknown[0]}). The canonical baseline is reset-only."
        )


__all__ = [
    "CHECK_ID",
    "check_canonical_migration_history",
    "pre_canonical_history",
    "refuse_pre_canonical_migrate",
]
