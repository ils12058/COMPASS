"""Forward-migration boundaries for routine canonical deployment, never a live database."""

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.db import migrations, models

SPEC = importlib.util.spec_from_file_location(
    "deployment_database_guard",
    Path(__file__).parents[1] / "deploy/staging/database_preflight.py",
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def plan(operation, *, backwards=False, atomic=True):
    return [
        (
            SimpleNamespace(
                app_label="inventory", name="0002_example", atomic=atomic, operations=[operation]
            ),
            backwards,
        )
    ]


@pytest.mark.parametrize(
    "operation",
    [
        migrations.CreateModel("Example", [("id", models.BigAutoField(primary_key=True))]),
        migrations.AddField("example", "note", models.TextField(null=True)),
        migrations.AddIndex("example", models.Index(fields=["id"], name="example_idx")),
    ],
)
def test_additive_forward_operations_pass(operation):
    guard.validate_operations(plan(operation))


@pytest.mark.parametrize(
    "operation",
    [
        migrations.DeleteModel("Example"),
        migrations.RemoveField("example", "note"),
        migrations.RenameField("example", "note", "new_note"),
        migrations.AlterField("example", "note", models.TextField()),
        migrations.AddField("example", "note", models.TextField()),
        migrations.AddField("example", "note", models.TextField(null=True, default="rewrite")),
        migrations.AddConstraint(
            "example",
            models.UniqueConstraint(fields=["id"], name="example_unique"),
        ),
        migrations.RunSQL("SELECT 1"),
        migrations.RunPython(migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(),
    ],
)
def test_data_changing_and_unclassified_operations_require_separate_procedure(operation):
    with pytest.raises(guard.Refused):
        guard.validate_operations(plan(operation))


def test_backward_and_non_atomic_plans_are_refused():
    operation = migrations.AddField("example", "note", models.TextField(null=True))
    for options in [{"backwards": True}, {"atomic": False}]:
        with pytest.raises(guard.Refused):
            guard.validate_operations(plan(operation, **options))


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).parents[1] / "compass").glob("*/migrations/0*.py")),
    ids=lambda path: f"{path.parent.parent.name}.{path.stem}",
)
def test_release_graph_is_refused_for_routine_deployment_even_with_a_digest_pin(path, monkeypatch):
    app_label = path.parent.parent.name
    migration = importlib.import_module(f"compass.{app_label}.migrations.{path.stem}").Migration(
        path.stem, app_label
    )
    monkeypatch.setitem(
        guard.REVIEWED_MIGRATIONS,
        f"{app_label}/{path.stem}",
        guard.hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    with pytest.raises(guard.Refused, match="Phase E staging reset"):
        guard.validate_operations([(migration, False)])


def test_future_reviewed_migration_source_digest_must_match(monkeypatch):
    operation = migrations.AddConstraint(
        "example", models.UniqueConstraint(fields=["id"], name="example_unique")
    )
    migration, _ = plan(operation)[0]
    source = b"synthetic reviewed migration"
    monkeypatch.setattr(guard.Path, "read_bytes", lambda path: source)
    key = f"{migration.app_label}/{migration.name}"
    monkeypatch.setitem(guard.REVIEWED_MIGRATIONS, key, guard.hashlib.sha256(source).hexdigest())
    guard.validate_operations([(migration, False)])
    monkeypatch.setitem(guard.REVIEWED_MIGRATIONS, key, "0" * 64)
    with pytest.raises(guard.Refused, match="source changed"):
        guard.validate_operations([(migration, False)])


@pytest.mark.parametrize(
    "action,applied,receipt,populated,allowed",
    [
        ("check", True, True, True, True),
        ("check", True, True, False, True),
        ("check", True, False, True, False),
        ("check", False, False, True, False),
        ("adopt", False, False, True, True),
        ("seed", False, False, False, True),
        ("seed", False, False, True, False),
        ("adopt", False, False, False, False),
        ("check", False, True, True, False),
        ("INVALID", True, True, True, False),
    ],
)
def test_catalog_preflight_requires_deliberate_matching_plan(
    action, applied, receipt, populated, allowed
):
    kwargs = {"migration_applied": applied, "receipt_exists": receipt, "populated": populated}
    if allowed:
        guard.validate_catalog_initialization(action, **kwargs)
    else:
        with pytest.raises(guard.Refused):
            guard.validate_catalog_initialization(action, **kwargs)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "receipt,action,allowed",
    [
        (True, "check", True),
        (False, "check", False),
        (False, "adopt", True),
    ],
)
def test_catalog_preflight_reads_real_disposable_database_without_adopting(
    receipt, action, allowed, monkeypatch, capsys
):
    from django.test import override_settings

    from compass.organization.bootstrap import initialize_organization_catalog
    from compass.organization.models import Campus, CatalogInitialization
    from tests.test_organization_catalog import _student, _sync_policy

    _sync_policy()
    _student("preflight@synthetic.invalid")
    if receipt:
        initialize_organization_catalog(action="seed")
    else:
        Campus.objects.create(code="OFFICIAL", name="Preserve this catalog")
    before = list(Campus.objects.order_by("pk").values())
    monkeypatch.setenv("ORG_CATALOG_ACTION", action)
    # Simulated destination mode; connection/keyrings remain tests.settings and localhost:56548.
    with override_settings(APP_ENV="live-staging", STAGING_SEED_ENABLED=False):
        if allowed:
            guard.inspect_database()
            assert '"canonical_database": true' in capsys.readouterr().out
        else:
            with pytest.raises(guard.Refused, match="explicitly approved"):
                guard.inspect_database()
    assert list(Campus.objects.order_by("pk").values()) == before
    assert CatalogInitialization.objects.exists() == receipt
