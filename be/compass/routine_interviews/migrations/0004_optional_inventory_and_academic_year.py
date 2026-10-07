"""ADR-088: Inventory becomes optional initiation provenance; Academic Year becomes explicit.

Every existing Routine Interview keeps its Inventory link, and its Academic Year is copied from
that Inventory, the only year the record can prove. Nothing else is rewritten.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_academic_year(apps, schema_editor):
    RoutineInterview = apps.get_model("routine_interviews", "RoutineInterview")
    StudentInventory = apps.get_model("inventory", "StudentInventory")
    table = schema_editor.quote_name(RoutineInterview._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        # Writers still running the previous release wait until the backfill commits.
        cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
    RoutineInterview.objects.filter(
        academic_year__isnull=True,
        inventory__isnull=False,
    ).update(
        academic_year_id=Subquery(
            StudentInventory.objects.filter(pk=OuterRef("inventory_id")).values(
                "academic_year_id"
            )[:1]
        )
    )


def refuse_unbound_rows(apps, schema_editor):
    RoutineInterview = apps.get_model("routine_interviews", "RoutineInterview")
    if RoutineInterview.objects.filter(inventory__isnull=True).exists():
        raise RuntimeError(
            "Routine Interviews created without an Individual Inventory exist; the previous "
            "schema cannot represent them, so this migration cannot be reversed."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_remove_plaintext_confidential_content"),
        ("organization", "0003_program"),
        ("routine_interviews", "0003_remove_plaintext_routine_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="routineinterview",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="routine_interviews",
                to="organization.academicyear",
            ),
        ),
        migrations.AlterField(
            model_name="routineinterview",
            name="inventory",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="routine_interviews",
                to="inventory.studentinventory",
            ),
        ),
        # Reversed before the column becomes NOT NULL again.
        migrations.RunPython(migrations.RunPython.noop, refuse_unbound_rows),
        migrations.RunPython(backfill_academic_year, migrations.RunPython.noop),
    ]
