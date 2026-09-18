import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("institutional_forms", "0004_referral_slip_family"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferralReferenceCounter",
            fields=[
                ("year", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("next_value", models.PositiveIntegerField(default=1)),
            ],
            options={"default_permissions": ()},
        ),
        migrations.CreateModel(
            name="Referral",
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
                ("reference_code", models.CharField(max_length=32, unique=True)),
                ("student_name_snapshot", models.CharField(max_length=512)),
                ("course_year_block_snapshot", models.CharField(max_length=255)),
                ("reason", models.TextField()),
                ("referrer_name", models.CharField(max_length=255)),
                ("referred_on", models.DateField()),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("status_note", models.TextField(blank=True, default="")),
                (
                    "creation_key_digest",
                    models.CharField(blank=True, max_length=64, null=True, unique=True),
                ),
                (
                    "creation_request_fingerprint",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "form_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="referrals",
                        to="institutional_forms.formrevision",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recorded_referrals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student_referrals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "reference_code", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="ReferralAction",
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
                    "action_type",
                    models.CharField(
                        choices=[
                            ("CALL_PARENT_GUARDIAN", "Call the Parent/Guardian"),
                            (
                                "SEND_PARENT_NOTIFICATION_LETTER",
                                'Send "Parent Notification Letter"',
                            ),
                            (
                                "SEND_CALL_SLIP_INTERVIEW_PERMIT",
                                'Send "Call Slip/Interview Permit"',
                            ),
                        ],
                        max_length=48,
                    ),
                ),
                ("occurred_at", models.DateTimeField()),
                ("remarks", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recorded_referral_actions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "referral",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="actions",
                        to="referrals.referral",
                    ),
                ),
            ],
            options={
                "ordering": ("occurred_at", "created_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="referralreferencecounter",
            constraint=models.CheckConstraint(
                condition=models.Q(("next_value__gte", 1)),
                name="referral_counter_next_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="referral",
            index=models.Index(
                fields=["student", "created_at"],
                name="referral_student_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="referral",
            index=models.Index(
                fields=["referred_on", "created_at"],
                name="referral_referred_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="referralaction",
            constraint=models.UniqueConstraint(
                fields=("referral", "action_type"),
                name="referral_action_type_uniq",
            ),
        ),
    ]
