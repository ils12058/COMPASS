"""Shared disposable PostgreSQL setup for additive Organization migration tests."""

import copy
import uuid

import pytest
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor

BASE = ("organization", "0001_canonical_baseline")
REFERRALS_BASE = ("referrals", "0001_canonical_baseline")


def _blocked_for_baseline(node: tuple[str, str]) -> bool:
    app, _name = node
    return (
        (app == "organization" and node != BASE)
        or (app == "referrals" and node != REFERRALS_BASE)
        or app == "student_academics"
    )


@pytest.fixture
def upgrade_database(django_db_blocker):
    """Create an isolated database at the Organization baseline migration."""
    name = "org1_upgrade_" + uuid.uuid4().hex
    alias = name
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}"')
        config = copy.deepcopy(connection.settings_dict)
        config["NAME"] = name
        connections.databases[alias] = config
        db = connections[alias]
        try:
            executor = MigrationExecutor(db)
            targets = []
            for node in executor.loader.graph.leaf_nodes():
                if node[0] in {"organization", "referrals", "student_academics"}:
                    continue
                if any(
                    _blocked_for_baseline(dependency)
                    for dependency in executor.loader.graph.forwards_plan(node)
                ):
                    continue
                targets.append(node)
            # FAC-2 Referral provenance depends on current Organization. Rehearsing
            # old Organization deliberately keeps Referral at its pre-FAC schema.
            targets.append(REFERRALS_BASE)
            targets.append(BASE)
            executor.migrate(targets)
            yield db, executor.loader.project_state(targets).apps
        finally:
            db.close()
            del connections[alias]
            del connections.databases[alias]
            with connection.cursor() as cursor:
                cursor.execute(f'DROP DATABASE "{name}"')
