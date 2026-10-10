import uuid

import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appointments", "0001_initial"),
        ("counseling", "0001_initial"),
        ("institutional_forms", "0002_routine_interview_family"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoutineInterview",
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
                    "entry_mode",
                    models.CharField(
                        choices=[
                            ("APPOINTMENT", "Appointment"),
                            ("WALK_IN", "Walk in"),
                            ("CALLED_IN", "Called in"),
                            ("REFERRED", "Referred"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "delivery_mode",
                    models.CharField(
                        choices=[("IN_PERSON", "In person"), ("ONLINE", "Online")],
                        max_length=16,
                    ),
                ),
                ("intake_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("evaluation_finalized_at", models.DateTimeField(blank=True, null=True)),
                ("coping_with_college_challenges", models.TextField(blank=True, default="")),
                ("coping_remarks", models.TextField(blank=True, default="")),
                ("college_experience", models.TextField(blank=True, default="")),
                ("reason_for_choosing_institution", models.TextField(blank=True, default="")),
                ("difficulties_encountered", models.TextField(blank=True, default="")),
                ("stress_anxiety_causes", models.TextField(blank=True, default="")),
                ("stress_anxiety_management", models.TextField(blank=True, default="")),
                ("family_description", models.TextField(blank=True, default="")),
                (
                    "concerns",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("FAMILY", "Family"),
                                ("FINANCIAL", "Financial"),
                                ("ACADEMIC", "Academic"),
                                ("FRIENDS", "Friends"),
                                ("CLASSMATES", "Classmates"),
                                ("VICES", "Vices"),
                                ("LOVE_LIFE", "Love life"),
                                ("SLEEPING_PROBLEMS", "Sleeping problems"),
                                (
                                    "SUICIDAL_THOUGHT_TENDENCY",
                                    "Suicidal thought/tendency",
                                ),
                                ("DORM_BOARDING_HOUSE", "Dorm / boarding house"),
                                (
                                    "PAST_PAINFUL_EXPERIENCE",
                                    "Past painful experience",
                                ),
                                ("OTHER", "Other"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("other_concern_specification", models.TextField(blank=True, default="")),
                ("concerns_explanation", models.TextField(blank=True, default="")),
                (
                    "college_adjustment_and_peer_group",
                    models.TextField(blank=True, default=""),
                ),
                ("academic_goals", models.TextField(blank=True, default="")),
                ("career_goals", models.TextField(blank=True, default="")),
                (
                    "academic_adjustment_rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                (
                    "physical_adjustment_rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                (
                    "social_adjustment_rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                (
                    "spiritual_adjustment_rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                (
                    "financial_adjustment_rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                (
                    "emotional_adjustment_rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                ("other_adjustment", models.TextField(blank=True, default="")),
                ("special_concern", models.TextField(blank=True, default="")),
                ("recommendations", models.TextField(blank=True, default="")),
                (
                    "direct_creation_key_digest",
                    models.CharField(blank=True, max_length=64, null=True, unique=True),
                ),
                (
                    "direct_request_fingerprint",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appointment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="routine_interview",
                        to="appointments.appointment",
                    ),
                ),
                (
                    "counseling_encounter",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="routine_interview",
                        to="counseling.counselingencounter",
                    ),
                ),
                (
                    "counselor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counselor_routine_interviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_routine_interviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "form_revision",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="routine_interviews",
                        to="institutional_forms.formrevision",
                    ),
                ),
                (
                    "inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="routine_interviews",
                        to="inventory.studentinventory",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student_routine_interviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "id"),
                "default_permissions": (),
                "indexes": [
                    models.Index(
                        fields=["student", "created_at"],
                        name="routine_student_created_idx",
                    ),
                    models.Index(
                        fields=["counselor", "created_at"],
                        name="routine_counselor_created_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(entry_mode="APPOINTMENT", appointment__isnull=False)
                            | (
                                ~models.Q(entry_mode="APPOINTMENT")
                                & models.Q(appointment__isnull=True)
                            )
                        ),
                        name="routine_entry_appointment_consistent",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(evaluation_finalized_at__isnull=True)
                            | models.Q(counseling_encounter__isnull=False)
                        ),
                        name="routine_finalized_requires_encounter",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(academic_adjustment_rating__isnull=True)
                            | (
                                models.Q(academic_adjustment_rating__gte=1)
                                & models.Q(academic_adjustment_rating__lte=10)
                            )
                        ),
                        name="routine_academic_rating_range",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(physical_adjustment_rating__isnull=True)
                            | (
                                models.Q(physical_adjustment_rating__gte=1)
                                & models.Q(physical_adjustment_rating__lte=10)
                            )
                        ),
                        name="routine_physical_rating_range",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(social_adjustment_rating__isnull=True)
                            | (
                                models.Q(social_adjustment_rating__gte=1)
                                & models.Q(social_adjustment_rating__lte=10)
                            )
                        ),
                        name="routine_social_rating_range",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(spiritual_adjustment_rating__isnull=True)
                            | (
                                models.Q(spiritual_adjustment_rating__gte=1)
                                & models.Q(spiritual_adjustment_rating__lte=10)
                            )
                        ),
                        name="routine_spiritual_rating_range",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(financial_adjustment_rating__isnull=True)
                            | (
                                models.Q(financial_adjustment_rating__gte=1)
                                & models.Q(financial_adjustment_rating__lte=10)
                            )
                        ),
                        name="routine_financial_rating_range",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(emotional_adjustment_rating__isnull=True)
                            | (
                                models.Q(emotional_adjustment_rating__gte=1)
                                & models.Q(emotional_adjustment_rating__lte=10)
                            )
                        ),
                        name="routine_emotional_rating_range",
                    ),
                ],
            },
        ),
    ]
