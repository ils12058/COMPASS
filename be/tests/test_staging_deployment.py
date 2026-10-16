"""Forward-migration boundaries for routine canonical deployment, never a live database."""

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
