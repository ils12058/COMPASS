import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
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
                ("event_code", models.CharField(max_length=128)),
                (
                    "policy",
                    models.CharField(
                        choices=[
                            ("MANDATORY_SECURITY", "MANDATORY_SECURITY"),
                            ("MANDATORY_OPERATIONAL", "MANDATORY_OPERATIONAL"),
                            ("OPTIONAL_INFORMATIONAL", "OPTIONAL_INFORMATIONAL"),
                        ],
                        max_length=32,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("source_type", models.CharField(max_length=64)),
                ("source_id", models.UUIDField()),
                ("target_type", models.CharField(blank=True, default="", max_length=64)),
                ("target_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="notification_preference",
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("optional_email_enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="EmailDelivery",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                (
                    "next_attempt_at",
                    models.DateTimeField(
                        blank=True,
                        default=django.utils.timezone.now,
                        null=True,
                    ),
                ),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, default="", max_length=64)),
                ("claim_token", models.UUIDField(blank=True, editable=False, null=True)),
                ("claim_expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "notification",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_delivery",
                        to="notifications.notification",
                    ),
                ),
            ],
            options={
                "default_permissions": (),
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "read_at", "created_at"],
                name="notif_recipient_read_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                fields=("recipient", "event_code", "source_type", "source_id"),
                name="notif_logical_event_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="emaildelivery",
            index=models.Index(
                fields=["status", "next_attempt_at"],
                name="email_delivery_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="emaildelivery",
            index=models.Index(
                fields=["status", "claim_expires_at"],
                name="email_delivery_claim_idx",
            ),
        ),
    ]
