import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_rename_reference_capabilities"),
        ("feedback", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeedbackOpportunity",
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
                    "source_type",
                    models.CharField(
                        choices=[
                            ("COUNSELING_ENCOUNTER", "Counseling Encounter"),
                            ("GOOD_MORAL_REQUEST", "Good Moral Request"),
                        ],
                        max_length=32,
                    ),
                ),
                ("source_id", models.UUIDField()),
                (
                    "service_kind",
                    models.CharField(
                        choices=[
                            ("COUNSELING", "Counseling"),
                            ("ADMISSION", "Admission"),
                            ("TESTING", "Testing"),
                            ("EDUCATIONAL_INFORMATION", "Educational Information"),
                            ("REQUEST_FOR_CERTIFICATION", "Request for Certification"),
                            (
                                "APPLICATION_FOR_ADMISSION_TEST",
                                "Application for Admission Test",
                            ),
                            ("OTHER", "Others (please specify)"),
                        ],
                        max_length=40,
                    ),
                ),
                ("service_label_snapshot", models.CharField(max_length=255)),
                ("service_completed_at", models.DateTimeField()),
                ("customer_feedback_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("csm_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="feedback_opportunities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-service_completed_at", "-created_at", "id"),
                "default_permissions": (),
                "indexes": [
                    models.Index(
                        fields=["student", "-service_completed_at"],
                        name="feedback_opp_student_done_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("source_type", "source_id"),
                        name="feedback_opp_source_uniq",
                    )
                ],
            },
        ),
    ]
