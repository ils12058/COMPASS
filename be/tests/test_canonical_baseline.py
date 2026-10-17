"""The reset-only canonical migration baseline (CANON-1C) and its fail-closed history guard."""

import ast
import hashlib
import json
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from compass.common.canonical_baseline import (
    CHECK_ID,
    check_canonical_migration_history,
    pre_canonical_history,
    refuse_pre_canonical_migrate,
)

COMPASS = Path(__file__).resolve().parents[1] / "compass"
BASELINE = "0001_canonical_baseline"


def compass_apps():
    return [config for config in apps.get_app_configs() if config.name.startswith("compass.")]


def registered_migrations():
    manifest = json.loads((COMPASS / "common/canonical_migrations.json").read_text())
    baselines = {name.removeprefix("compass/") for name in manifest["baseline_sha256"]}
    additions = set(manifest["additive_migrations"])
    for name, digest in manifest["baseline_sha256"].items():
        assert hashlib.sha256((COMPASS.parent / name).read_bytes()).hexdigest() == digest, name
    assert not baselines.intersection(additions)
    return baselines | additions


def test_registered_migrations_preserve_immutable_schema_only_baselines():
    with_models = {config.label for config in compass_apps() if list(config.get_models())}
    migration_files = {
        path.parent.parent.name: sorted(p.name for p in path.parent.glob("0*.py"))
        for path in COMPASS.glob("*/migrations/__init__.py")
    }
    labels = {config.name.split(".")[1]: config.label for config in compass_apps()}
    present = {labels[name]: files for name, files in migration_files.items() if files}
    assert set(present) == with_models
    actual = {str(path.relative_to(COMPASS)) for path in COMPASS.glob("*/migrations/0*.py")}
    assert actual == registered_migrations()
    for name in actual:
        assert name.endswith(f"{BASELINE}.py") or name in registered_migrations()
    for path in COMPASS.glob(f"*/migrations/{BASELINE}.py"):
        tree = ast.parse(path.read_text())
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        # Configuration and synthetic data come from explicit synchronizers, never migrations.
        assert calls.isdisjoint({"RunPython", "RunSQL", "SeparateDatabaseAndState"}), path
    # Frozen historical codecs are test oracles now, not migration modules.
    assert [p for p in COMPASS.glob("*/migrations/_*.py") if p.name != "__init__.py"] == []


@pytest.mark.django_db
def test_the_graph_has_one_leaf_per_app_and_no_model_drift():
    loader = MigrationLoader(None, ignore_no_migrations=True)
    leaves = loader.graph.leaf_nodes()
    compass_labels = {config.label for config in compass_apps()}
    compass_leaves = [app for app, _ in leaves if app in compass_labels]
    assert len(compass_leaves) == len(set(compass_leaves))
    for app, name in leaves:
        if app in compass_labels:
            config = apps.get_app_config(app)
            directory = config.name.split(".")[1]
            assert f"{directory}/migrations/{name}.py" in registered_migrations()
            if (COMPASS / directory / "migrations" / f"{BASELINE}.py").exists():
                assert (app, BASELINE) in loader.graph.forwards_plan((app, name))
    out = StringIO()
    call_command("makemigrations", check=True, dry_run=True, stdout=out)
    assert "No changes detected" in out.getvalue()


@pytest.mark.django_db
def test_every_declared_constraint_and_index_exists_in_postgresql():
    missing = []
    with connection.cursor() as cursor:
        for config in compass_apps():
            for model in config.get_models():
                table = model._meta.db_table
                present = set(connection.introspection.get_constraints(cursor, table))
                for item in (*model._meta.constraints, *model._meta.indexes):
                    if item.name not in present:
                        missing.append(f"{table}.{item.name}")
    assert missing == []


@pytest.mark.django_db
def test_a_fresh_database_passes_the_history_guard():
    assert pre_canonical_history(connection) == []
    assert check_canonical_migration_history(databases=["default"]) == []
    refuse_pre_canonical_migrate(sender=None, using="default")


@pytest.mark.django_db
def test_pre_canonical_history_is_refused_by_check_and_migrate():
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, now())",
            ["accounts", "0008_remove_plaintext_confidential_content"],
        )
    assert pre_canonical_history(connection) == [
        "accounts.0008_remove_plaintext_confidential_content"
    ]
    errors = check_canonical_migration_history(databases=["default"])
    assert [error.id for error in errors] == [CHECK_ID]
    assert "reset-only" in errors[0].msg
    with pytest.raises(CommandError, match="pre-canonical"):
        refuse_pre_canonical_migrate(sender=None, using="default")
