import uuid

from django.db import migrations, models
import django.db.models.deletion


def bootstrap_inventory_revision(apps, schema_editor):
    FormFamily = apps.get_model("institutional_forms", "FormFamily")
    FormRevision = apps.get_model("institutional_forms", "FormRevision")
    family, _ = FormFamily.objects.get_or_create(
        key="individual_inventory",
        defaults={"title": "Individual Inventory"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        internal_schema_version=1,
        defaults={
            "official_code": "CNSC-OP-GCO-01F5",
            "official_revision": "0",
            "status": "ACTIVE",
        },
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FormFamily",
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
                ("key", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("key",), "default_permissions": ()},
        ),
        migrations.CreateModel(
            name="FormRevision",
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
                ("official_code", models.CharField(blank=True, max_length=96, null=True)),
                ("official_revision", models.CharField(blank=True, max_length=32, null=True)),
                ("internal_schema_version", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")],
                        default="INACTIVE",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "family",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="revisions",
                        to="institutional_forms.formfamily",
                    ),
                ),
            ],
            options={
                "ordering": ("family__key", "internal_schema_version", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="formrevision",
            constraint=models.UniqueConstraint(
                fields=("family", "internal_schema_version"),
                name="institutional_forms_family_schema_version_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="formrevision",
            constraint=models.UniqueConstraint(
                condition=(
                    models.Q(("official_code__isnull", False))
                    & models.Q(("official_revision__isnull", False))
                ),
                fields=("family", "official_code", "official_revision"),
                name="institutional_forms_official_identity_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="formrevision",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "ACTIVE")),
                fields=("family",),
                name="institutional_forms_one_active_revision_per_family",
            ),
        ),
        migrations.RunPython(bootstrap_inventory_revision, migrations.RunPython.noop),
    ]
