from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("organization", "0002_academic_year"),
    ]

    operations = [
        migrations.CreateModel(
            name="Program",
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
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "college",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="programs",
                        to="organization.college",
                    ),
                ),
            ],
            options={
                "ordering": ("college__campus__code", "college__code", "code"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="program",
            constraint=models.UniqueConstraint(
                fields=("college", "code"),
                name="organization_program_code_uniq",
            ),
        ),
    ]
