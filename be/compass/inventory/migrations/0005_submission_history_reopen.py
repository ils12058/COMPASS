from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def backfill_submission_history(apps, schema_editor):
    StudentInventory = apps.get_model("inventory", "StudentInventory")
    for item in StudentInventory.objects.filter(submitted_at__isnull=False).iterator():
        StudentInventory.objects.filter(pk=item.pk).update(
            first_submitted_at=item.submitted_at,
            last_submitted_at=item.submitted_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_student_support_profile_context"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="studentinventory",
            name="first_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studentinventory",
            name="last_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="InventoryReopenEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("reopened_at", models.DateTimeField()),
                ("reason", models.TextField(max_length=1000)),
                (
                    "inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reopen_events",
                        to="inventory.studentinventory",
                    ),
                ),
                (
                    "reopened_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inventory_reopen_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("reopened_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.RunPython(backfill_submission_history, migrations.RunPython.noop),
    ]
