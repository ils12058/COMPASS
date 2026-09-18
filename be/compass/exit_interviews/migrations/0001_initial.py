import uuid

import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0002_user_reusable_profile_fields"),
        ("inventory", "0001_initial"),
        ("organization", "0002_academic_year"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExitInterview",
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
                        choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted")],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("student_name_snapshot", models.CharField(blank=True, default="", max_length=200)),
                (
                    "age_snapshot",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(150),
                        ],
                    ),
                ),
                ("civil_status_snapshot", models.CharField(blank=True, default="", max_length=80)),
                ("course_snapshot", models.CharField(blank=True, default="", max_length=180)),
                ("major_snapshot", models.CharField(blank=True, default="", max_length=180)),
                ("email_snapshot", models.EmailField(blank=True, default="", max_length=320)),
                ("home_address_snapshot", models.TextField(blank=True, default="")),
                ("contact_number_snapshot", models.CharField(blank=True, default="", max_length=64)),
                (
                    "program_completion",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("ACCORDING_TO_SCHEDULE", "According to schedule"),
                            ("WITH_SOME_DELAY", "With some delay"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                (
                    "extra_terms_count",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "delay_reasons",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("TRANSFEREE", "Transferee"),
                                ("ACADEMIC_FAILURES", "Academic Failures"),
                                ("OTHER", "Others (pls. specify)"),
                            ],
                            max_length=32,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("delay_other", models.TextField(blank=True, default="")),
                (
                    "significant_learning_experiences",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("INDEPENDENCE", "Independence"),
                                ("INTERPERSONAL_RELATIONS", "Interpersonal Relations"),
                                ("INTELLECTUAL_GROWTH", "Intellectual Growth"),
                                ("SPIRITUAL_GROWTH", "Spiritual Growth"),
                                ("RESPONSIBILITY", "Responsibility"),
                                ("WORKING_UNDER_PRESSURE", "Working under pressure"),
                                ("TIME_MANAGEMENT", "Time Management"),
                                ("SETTING_PRIORITIES", "Setting priorities"),
                                ("OTHER", "Others, pls. specify"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("significant_learning_other", models.TextField(blank=True, default="")),
                (
                    "career_modes",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[("WORK", "Work"), ("STUDY", "Study")],
                            max_length=16,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "work_choices",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("RELATED_FIELD", "in a field related to my course"),
                                ("UNRELATED_FIELD", "in a field unrelated to my course"),
                                ("FAMILY_BUSINESS", "work in a family business"),
                                ("OWN_BUSINESS", "set up my own business"),
                                ("WORK_ABROAD", "work abroad"),
                                ("NO_DEFINITE_PLAN", "no definite career plan yet"),
                            ],
                            max_length=32,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "study_choices",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("RELATED_FIELD", "in a field related to my course"),
                                ("UNRELATED_FIELD", "in a field unrelated to my course"),
                            ],
                            max_length=32,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("dean_comments", models.TextField(blank=True, default="")),
                ("program_chair_comments", models.TextField(blank=True, default="")),
                ("faculty_comments", models.TextField(blank=True, default="")),
                ("curriculum_comments", models.TextField(blank=True, default="")),
                ("guidance_counselor_comments", models.TextField(blank=True, default="")),
                ("office_staff_comments", models.TextField(blank=True, default="")),
                ("facilities_comments", models.TextField(blank=True, default="")),
                ("suggestions_recommendations", models.TextField(blank=True, default="")),
                ("first_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("last_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exit_interviews",
                        to="organization.academicyear",
                    ),
                ),
                (
                    "inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exit_interviews",
                        to="inventory.studentinventory",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exit_interviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-academic_year__label", "-created_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="ExitInterviewCollegeFeedbackRating",
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
                    "item_code",
                    models.CharField(
                        choices=[
                            ("DEAN_AVAILABILITY", "DEAN — Availability"),
                            ("DEAN_OPEN_MINDEDNESS", "DEAN — Open Mindedness"),
                            ("DEAN_CONCERN_FOR_STUDENTS", "DEAN — Concern for Students"),
                            ("DEAN_COMMITMENT", "DEAN — Commitment"),
                            ("DEAN_APPROACHABILITY", "DEAN — Approachability"),
                            ("PROGRAM_CHAIR_AVAILABILITY", "PROG CHAIR — Availability"),
                            ("PROGRAM_CHAIR_APPROACHABILITY", "PROG CHAIR — Approachability"),
                            (
                                "PROGRAM_CHAIR_CONCERN_FOR_STUDENTS",
                                "PROG CHAIR — Concern for Students",
                            ),
                            ("FACULTY_AVAILABILITY", "FACULTY — Availability"),
                            ("FACULTY_APPROACHABILITY", "FACULTY — Approachability"),
                            (
                                "FACULTY_KNOWLEDGE_SUBJECT_MATTER",
                                "FACULTY — Knowledge of subject matter",
                            ),
                            ("FACULTY_TEACHING_SKILLS", "FACULTY — Teaching Skills"),
                            (
                                "CURRICULUM_RELEVANCE_SUBJECTS",
                                "CURRICULUM — Relevance of subjects",
                            ),
                            (
                                "CURRICULUM_SYSTEMATIC_SEQUENCING",
                                "CURRICULUM — Systematic Sequencing of Subjects",
                            ),
                            ("CURRICULUM_COMPLETENESS", "CURRICULUM — Completeness"),
                            (
                                "GUIDANCE_COUNSELOR_AVAILABILITY",
                                "GUIDANCE COUNSELOR — Availability",
                            ),
                            (
                                "GUIDANCE_COUNSELOR_APPROACHABILITY",
                                "GUIDANCE COUNSELOR — Approachability",
                            ),
                            (
                                "GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS",
                                "GUIDANCE COUNSELOR — Concern for Students",
                            ),
                            (
                                "GUIDANCE_COUNSELOR_EFFICIENCY",
                                "GUIDANCE COUNSELOR — Efficiency",
                            ),
                            ("OFFICE_STAFF_SERVICE_ORIENTED", "OFFICE STAFF — Service Oriented"),
                            ("OFFICE_STAFF_AVAILABILITY", "OFFICE STAFF — Availability"),
                            (
                                "OFFICE_STAFF_CONCERN_FOR_STUDENTS",
                                "OFFICE STAFF — Concern for Students",
                            ),
                            ("OFFICE_STAFF_APPROACHABILITY", "OFFICE STAFF — Approachability"),
                            (
                                "FACILITIES_MAINTENANCE_CONDITION",
                                "FACILITIES — Maintenance and Condition",
                            ),
                            ("FACILITIES_AVAILABILITY", "FACILITIES — Availability"),
                            ("FACILITIES_COMPLETENESS", "FACILITIES — Completeness"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                (
                    "exit_interview",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="college_feedback_ratings",
                        to="exit_interviews.exitinterview",
                    ),
                ),
            ],
            options={"ordering": ("item_code",), "default_permissions": ()},
        ),
        migrations.CreateModel(
            name="ExitInterviewReopenEvent",
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
                ("reopened_at", models.DateTimeField()),
                ("reason", models.TextField(max_length=1000)),
                (
                    "exit_interview",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reopen_events",
                        to="exit_interviews.exitinterview",
                    ),
                ),
                (
                    "reopened_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exit_interview_reopen_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("reopened_at", "id"), "default_permissions": ()},
        ),
        migrations.CreateModel(
            name="ExitInterviewSelfAssessmentRating",
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
                    "item_code",
                    models.CharField(
                        choices=[
                            ("PRIDE_CONFIDENCE_CNSC", "Pride and confidence in being from CNSC"),
                            (
                                "ACADEMIC_RECREATION_BALANCE",
                                "Ability to maintain balance between academics & recreational activities",
                            ),
                            (
                                "HOLISTIC_PERSONAL_WELL_BEING",
                                "Awareness of the importance of holistic personal well-being",
                            ),
                            (
                                "INTEGRATE_KNOWLEDGE_EXPERIENCE",
                                "Ability to integrate knowledge with experience",
                            ),
                            ("CAREER_GOAL_CLARITY", "Clarity of career goals"),
                            ("SELF_ESTEEM", "Self Esteem"),
                            ("SELF_AWARENESS", "Self-Awareness"),
                            ("COPE_WITH_PRESSURES", "Ability to cope with pressures"),
                            (
                                "DEAL_WITH_DIFFERENT_WALKS",
                                "Ability to deal comfortably with people from different walks of life",
                            ),
                            ("LEADERSHIP", "Leadership"),
                            ("COMMUNICATION_SKILLS", "Communication Skills"),
                            ("CIVIC_MINDEDNESS", "Civic Mindedness"),
                            ("INITIATIVE", "Initiative"),
                            ("DECISION_MAKING", "Decision Making"),
                            ("RELATIONSHIP_WITH_GOD", "Relationship with God"),
                        ],
                        max_length=48,
                    ),
                ),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                (
                    "exit_interview",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="self_assessment_ratings",
                        to="exit_interviews.exitinterview",
                    ),
                ),
            ],
            options={"ordering": ("item_code",), "default_permissions": ()},
        ),
        migrations.AddConstraint(
            model_name="exitinterview",
            constraint=models.UniqueConstraint(
                fields=("student", "academic_year"),
                name="exit_interview_student_year_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterview",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["DRAFT", "SUBMITTED"]),
                name="exit_interview_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterview",
            constraint=models.CheckConstraint(
                condition=models.Q(age_snapshot__isnull=True)
                | models.Q(age_snapshot__gte=0, age_snapshot__lte=150),
                name="exit_interview_age_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterview",
            constraint=models.CheckConstraint(
                condition=models.Q(extra_terms_count__isnull=True)
                | models.Q(extra_terms_count__gte=1),
                name="exit_interview_extra_terms_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterviewcollegefeedbackrating",
            constraint=models.UniqueConstraint(
                fields=("exit_interview", "item_code"),
                name="exit_interview_feedback_item_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterviewcollegefeedbackrating",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    item_code__in=[
                        "DEAN_AVAILABILITY",
                        "DEAN_OPEN_MINDEDNESS",
                        "DEAN_CONCERN_FOR_STUDENTS",
                        "DEAN_COMMITMENT",
                        "DEAN_APPROACHABILITY",
                        "PROGRAM_CHAIR_AVAILABILITY",
                        "PROGRAM_CHAIR_APPROACHABILITY",
                        "PROGRAM_CHAIR_CONCERN_FOR_STUDENTS",
                        "FACULTY_AVAILABILITY",
                        "FACULTY_APPROACHABILITY",
                        "FACULTY_KNOWLEDGE_SUBJECT_MATTER",
                        "FACULTY_TEACHING_SKILLS",
                        "CURRICULUM_RELEVANCE_SUBJECTS",
                        "CURRICULUM_SYSTEMATIC_SEQUENCING",
                        "CURRICULUM_COMPLETENESS",
                        "GUIDANCE_COUNSELOR_AVAILABILITY",
                        "GUIDANCE_COUNSELOR_APPROACHABILITY",
                        "GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS",
                        "GUIDANCE_COUNSELOR_EFFICIENCY",
                        "OFFICE_STAFF_SERVICE_ORIENTED",
                        "OFFICE_STAFF_AVAILABILITY",
                        "OFFICE_STAFF_CONCERN_FOR_STUDENTS",
                        "OFFICE_STAFF_APPROACHABILITY",
                        "FACILITIES_MAINTENANCE_CONDITION",
                        "FACILITIES_AVAILABILITY",
                        "FACILITIES_COMPLETENESS",
                    ]
                ),
                name="exit_interview_feedback_item_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterviewcollegefeedbackrating",
            constraint=models.CheckConstraint(
                condition=models.Q(rating__gte=0, rating__lte=5),
                name="exit_interview_feedback_rating_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterviewselfassessmentrating",
            constraint=models.UniqueConstraint(
                fields=("exit_interview", "item_code"),
                name="exit_interview_self_item_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterviewselfassessmentrating",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    item_code__in=[
                        "PRIDE_CONFIDENCE_CNSC",
                        "ACADEMIC_RECREATION_BALANCE",
                        "HOLISTIC_PERSONAL_WELL_BEING",
                        "INTEGRATE_KNOWLEDGE_EXPERIENCE",
                        "CAREER_GOAL_CLARITY",
                        "SELF_ESTEEM",
                        "SELF_AWARENESS",
                        "COPE_WITH_PRESSURES",
                        "DEAL_WITH_DIFFERENT_WALKS",
                        "LEADERSHIP",
                        "COMMUNICATION_SKILLS",
                        "CIVIC_MINDEDNESS",
                        "INITIATIVE",
                        "DECISION_MAKING",
                        "RELATIONSHIP_WITH_GOD",
                    ]
                ),
                name="exit_interview_self_item_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="exitinterviewselfassessmentrating",
            constraint=models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="exit_interview_self_rating_range",
            ),
        ),
    ]
