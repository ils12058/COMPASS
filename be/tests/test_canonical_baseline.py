"""The reset-only release migration baseline (ADR-117) and its fail-closed history guard."""

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
BASELINE = "0001_release_baseline"


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
    manifest = json.loads((COMPASS / "common/canonical_migrations.json").read_text())
    immutable = {name.removeprefix("compass/") for name in manifest["baseline_sha256"]}
    loader = MigrationLoader(None, ignore_no_migrations=True)
    for path in COMPASS.glob("*/migrations/0*.py"):
        relative = str(path.relative_to(COMPASS))
        tree = ast.parse(path.read_text())
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "RunPython" not in calls, path
        if relative not in immutable:
            continue
        label = labels[path.parent.parent.name]
        migration = loader.disk_migrations[(label, path.stem)]
        types = {type(operation).__name__ for operation in migration.operations}
        if path.stem == "0002_database_guards":
            assert types <= {"RunSQL", "AddConstraint", "AddIndex"}, path
            assert "RunSQL" in types, path
        else:
            assert path.stem in {BASELINE, "0002_release_baseline_links"}, path
            assert calls.isdisjoint({"RunPython", "RunSQL", "SeparateDatabaseAndState"}), path
        for app, name in migration.dependencies:
            assert name in {BASELINE, "0002_release_baseline_links", "__first__"}, (path, app, name)
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
@pytest.mark.parametrize(
    "old_name", ["0008_remove_plaintext_confidential_content", "0001_canonical_baseline"]
)
def test_pre_canonical_history_is_refused_by_check_and_migrate(old_name):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, now())",
            ["accounts", old_name],
        )
    assert pre_canonical_history(connection) == [f"accounts.{old_name}"]
    errors = check_canonical_migration_history(databases=["default"])
    assert [error.id for error in errors] == [CHECK_ID]
    assert "reset-only" in errors[0].msg
    with pytest.raises(CommandError, match="pre-canonical"):
        refuse_pre_canonical_migrate(sender=None, using="default")
    # Exercise the actual command; skip_checks proves the receiver cannot be bypassed.
    with pytest.raises(CommandError, match="pre-canonical"):
        call_command("migrate", skip_checks=True, stdout=StringIO(), verbosity=0)
    with pytest.raises(CommandError, match="reset-only"):
        call_command("check", databases=["default"], stdout=StringIO())


# Canonical catalog from Phase D's reference schema, independent of migration contents.
# A future squash must preserve these objects even though Django's model state omits them.
DATABASE_FUNCTIONS = (
    "compass_group_session_facilitator_preserve_delete",
    "compass_group_session_prevent_delete",
    "compass_service_slot_booking_prevent_delete",
    "compass_service_slot_prevent_delete",
    "compass_service_slot_record_booking_history",
    "gm_inspection_eligibility_guard",
    "gm_inspection_request_guard",
    "gm_or_key",
    "gm_receipt_assignment_guard",
    "gm_receipt_closure_successor",
    "gm_receipt_identity_claim",
    "gm_receipt_identity_guard",
    "gm_receipt_mutation_guard",
    "gm_receipt_projection_guard",
    "gm_receipt_request_guard",
    "gm_receipt_verification_guard",
    "organization_valid_year_levels_v1",
    "referrals_administration_immutable",
    "referrals_submission_origin_immutable",
)
DATABASE_TRIGGERS = (
    ("good_moral_goodmoralreceiptassignment", "gm_inspection_assignment"),
    ("good_moral_goodmoralreceiptassignment", "gm_receipt_assignment_guard"),
    ("good_moral_goodmoralreceiptassignment", "gm_receipt_closure_successor"),
    ("good_moral_goodmoralreceiptassignment", "gm_receipt_projection_revision"),
    ("good_moral_goodmoralreceiptidentity", "gm_receipt_identity_claim"),
    ("good_moral_goodmoralreceiptidentity", "gm_receipt_identity_guard"),
    ("good_moral_goodmoralreceiptmutation", "gm_receipt_mutation_guard"),
    ("good_moral_goodmoralreceiptverification", "gm_inspection_verification"),
    ("good_moral_goodmoralreceiptverification", "gm_receipt_verification_guard"),
    ("good_moral_goodmoralrequest", "gm_inspection_request"),
    ("good_moral_goodmoralrequest", "gm_inspection_request_guard"),
    ("good_moral_goodmoralrequest", "gm_receipt_projection_request"),
    ("good_moral_goodmoralrequest", "gm_receipt_request_guard"),
    ("group_sessions_groupsession", "compass_group_session_prevent_delete"),
    ("group_sessions_groupsessionfacilitator", "compass_group_session_facilitator_preserve_delete"),
    ("referrals_referral", "referrals_administration_guard"),
    ("referrals_referral", "referrals_submission_origin_guard"),
    ("service_catalog_serviceappointmentslot", "compass_service_slot_prevent_delete"),
    ("service_catalog_serviceappointmentslot", "compass_service_slot_record_booking_history"),
    (
        "service_catalog_serviceappointmentslotbooking",
        "compass_service_slot_booking_prevent_delete",
    ),
)


@pytest.mark.django_db
def test_every_canonical_function_and_trigger_exists_in_postgresql():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public'"
        )
        functions = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            "SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND NOT t.tgisinternal"
        )
        triggers = set(cursor.fetchall())
    assert set(DATABASE_FUNCTIONS) <= functions
    assert set(DATABASE_TRIGGERS) <= triggers
