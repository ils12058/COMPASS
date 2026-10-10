# Generated for the COMPASS Announcements foundation.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Announcement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("body_markdown", models.TextField()),
                ("audience", models.CharField(choices=[("ALL_AUTHENTICATED", "All authenticated"), ("STUDENTS", "Students"), ("GCO_PERSONNEL", "GCO personnel")], max_length=32)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("ARCHIVED", "Archived")], default="DRAFT", max_length=16)),
                ("is_pinned", models.BooleanField(default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="announcements_created", to=settings.AUTH_USER_MODEL)),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="announcements_published", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="announcements_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-is_pinned", "-published_at", "-id"), "default_permissions": ()},
        ),
        migrations.AddIndex(model_name="announcement", index=models.Index(fields=["status", "-published_at"], name="ann_status_pub_idx")),
        migrations.AddIndex(model_name="announcement", index=models.Index(fields=["status", "expires_at"], name="ann_status_exp_idx")),
        migrations.AddIndex(model_name="announcement", index=models.Index(fields=["is_pinned", "-published_at"], name="ann_pin_pub_idx")),
        migrations.AddConstraint(model_name="announcement", constraint=models.CheckConstraint(condition=models.Q(("status", "PUBLISHED"), _negated=True) | (models.Q(("published_at__isnull", False)) & models.Q(("published_by__isnull", False))), name="ann_published_metadata")),
    ]
