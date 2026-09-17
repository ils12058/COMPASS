import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("counseling", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CounselingSharedSummary",
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
                ("content", models.TextField(blank=True, default="")),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "encounter",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="shared_summary",
                        to="counseling.counselingencounter",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "id"),
                "default_permissions": (),
            },
        ),
    ]
