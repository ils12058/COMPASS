from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailotpchallenge",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("email_verification", "Email verification"),
                    ("recovery", "Recovery"),
                    ("security_challenge", "Security challenge"),
                    ("email_change", "Email change"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="EmailChangeRequest",
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
                ("current_email_snapshot", models.EmailField(max_length=254)),
                ("new_email", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("expires_at", models.DateTimeField()),
                ("current_email_authorized_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("old_email_alert_sent_at", models.DateTimeField(blank=True, null=True)),
                ("old_email_alert_attempt_count", models.PositiveSmallIntegerField(default=0)),
                (
                    "email_otp_challenge",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="email_change_request",
                        to="authentication.emailotpchallenge",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="initiated_email_change_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_change_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "default_permissions": (),
                "indexes": [
                    models.Index(
                        fields=["user", "confirmed_at", "cancelled_at", "expires_at"],
                        name="auth_email_change_user_idx",
                    ),
                    models.Index(fields=["expires_at"], name="auth_email_change_expiry_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("cancelled_at__isnull", True),
                            ("confirmed_at__isnull", True),
                        ),
                        fields=("user",),
                        name="auth_one_pending_email_change_per_user",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("expires_at__gt", models.F("created_at"))),
                        name="auth_email_change_expiry_after_creation",
                    ),
                ],
            },
        ),
    ]
