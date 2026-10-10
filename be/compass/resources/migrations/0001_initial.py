# Generated for the COMPASS Curated Resources foundation.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Resource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("body_markdown", models.TextField()),
                ("category", models.CharField(choices=[("GENERAL", "General"), ("COUNSELING", "Counseling"), ("MENTAL_HEALTH", "Mental health"), ("ACADEMIC_SUPPORT", "Academic support"), ("CAREER", "Career"), ("WELLNESS", "Wellness"), ("FORMS_AND_GUIDES", "Forms and guides"), ("OTHER", "Other")], max_length=32)),
                ("kind", models.CharField(choices=[("ARTICLE", "Article"), ("EXTERNAL_LINK", "External link"), ("FILE", "File")], max_length=24)),
                ("audience", models.CharField(choices=[("ALL_AUTHENTICATED", "All authenticated"), ("STUDENTS", "Students"), ("GCO_PERSONNEL", "GCO personnel")], max_length=32)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("ARCHIVED", "Archived")], default="DRAFT", max_length=16)),
                ("external_url", models.URLField(blank=True, default="", max_length=2048)),
                ("storage_key", models.CharField(blank=True, default="", max_length=512)),
                ("original_filename", models.CharField(blank=True, default="", max_length=255)),
                ("content_type", models.CharField(blank=True, default="", max_length=128)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("display_order", models.IntegerField(default=0)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="resources_created", to=settings.AUTH_USER_MODEL)),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="resources_published", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="resources_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("display_order", "-published_at", "-id"), "default_permissions": ()},
        ),
        migrations.AddIndex(model_name="resource", index=models.Index(fields=["status", "display_order"], name="res_status_order_idx")),
        migrations.AddIndex(model_name="resource", index=models.Index(fields=["category", "display_order"], name="res_cat_order_idx")),
        migrations.AddIndex(model_name="resource", index=models.Index(fields=["kind", "display_order"], name="res_kind_order_idx")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=models.Q(("status", "PUBLISHED"), _negated=True) | (models.Q(("published_at__isnull", False)) & models.Q(("published_by__isnull", False))), name="res_published_metadata")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=models.Q(("external_url", ""), ("kind", "ARTICLE"), ("storage_key", "")) | models.Q(("kind", "EXTERNAL_LINK"), ("storage_key", "")) | models.Q(("external_url", ""), ("kind", "FILE")), name="res_kind_channels")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=models.Q(("content_type", ""), ("original_filename", ""), ("size_bytes", 0), ("storage_key", "")) | (~models.Q(("storage_key", "")) & ~models.Q(("original_filename", "")) & ~models.Q(("content_type", "")) & models.Q(("size_bytes__gt", 0))), name="res_file_metadata_complete")),
    ]
