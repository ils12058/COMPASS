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
    "module_name",
    [
        "compass.appointments.migrations.0002_appointment_reminders",
        "compass.guidance_followups.migrations.0001_initial",
        "compass.guidance_followups.migrations.0002_guidancefollowupmutation",
        "compass.group_sessions.migrations.0001_initial",
        "compass.service_catalog.migrations.0002_booking_pathways",
        "compass.service_catalog.migrations.0003_fixed_date_slots",
        "compass.group_sessions.migrations.0002_alter_groupsessionfacilitator_group_session",
        "compass.group_sessions.migrations.0003_group_session_scheduling_and_external_facilitators",
        "compass.service_catalog.migrations.0004_serviceappointmentslot_withdrawn_at_and_more",
    ],
)
def test_exact_reviewed_migration_sources_allow_their_pinned_operations(module_name):
    app_label = module_name.split(".")[1]
    migration_name = module_name.rsplit(".", 1)[1]
    migration = importlib.import_module(module_name).Migration(migration_name, app_label)
    guard.validate_operations([(migration, False)])


def test_reviewed_migration_source_digest_must_match(monkeypatch):
    migration = importlib.import_module(
        "compass.service_catalog.migrations.0002_booking_pathways"
    ).Migration("0002_booking_pathways", "service_catalog")
    key = f"{migration.app_label}/{migration.name}"
    monkeypatch.setitem(guard.REVIEWED_MIGRATIONS, key, "0" * 64)
    with pytest.raises(guard.Refused):
        guard.validate_operations([(migration, False)])


@pytest.mark.parametrize(
    "module_name",
    [
        "compass.group_sessions.migrations.0002_alter_groupsessionfacilitator_group_session",
        "compass.group_sessions.migrations.0003_group_session_scheduling_and_external_facilitators",
        "compass.service_catalog.migrations.0004_serviceappointmentslot_withdrawn_at_and_more",
    ],
)
def test_corr_lifecycle_migrations_are_refused_without_their_reviewed_pin(module_name, monkeypatch):
    app_label = module_name.split(".")[1]
    migration_name = module_name.rsplit(".", 1)[1]
    migration = importlib.import_module(module_name).Migration(migration_name, app_label)
    monkeypatch.delitem(guard.REVIEWED_MIGRATIONS, f"{app_label}/{migration_name}")
    with pytest.raises(guard.Refused):
        guard.validate_operations([(migration, False)])
