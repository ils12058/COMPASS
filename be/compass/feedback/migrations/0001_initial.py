import uuid

import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("institutional_forms", "0007_customer_feedback_family"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientSatisfactionResponse",
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
                    "instrument_schema_version",
                    models.PositiveSmallIntegerField(default=1, editable=False),
                ),
                (
                    "client_type",
                    models.CharField(
                        choices=[
                            ("CITIZEN", "Citizen"),
                            ("BUSINESS", "Business"),
                            ("GOVERNMENT", "Government (Employee or another agency)"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "sex",
                    models.CharField(
                        choices=[("MALE", "Male"), ("FEMALE", "Female")],
                        max_length=8,
                    ),
                ),
                (
                    "age",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(150),
                        ]
                    ),
                ),
                ("region_of_residence", models.CharField(max_length=160)),
                ("service_availed", models.CharField(max_length=255)),
                (
                    "cc1",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Knows Citizen's Charter and saw this office's Charter"),
                            (2, "Knows Citizen's Charter but did not see this office's Charter"),
                            (
                                3,
                                "Learned of Citizen's Charter when seeing this office's Charter",
                            ),
                            (
                                4,
                                "Does not know Citizen's Charter and did not see one in this office",
                            ),
                        ]
                    ),
                ),
                (
                    "cc2",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Easy to see"),
                            (2, "Somewhat easy to see"),
                            (3, "Difficult to see"),
                            (4, "Not visible at all"),
                            (5, "N/A"),
                        ]
                    ),
                ),
                (
                    "cc3",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Helped very much"),
                            (2, "Somewhat helped"),
                            (3, "Did not help"),
                            (4, "N/A"),
                        ]
                    ),
                ),
                (
                    "sqd0",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd1",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd2",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd3",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd4",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd5",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd6",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd7",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                (
                    "sqd8",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Not Applicable"),
                            (1, "Strongly Disagree"),
                            (2, "Disagree"),
                            (3, "Neither Agree nor Disagree"),
                            (4, "Agree"),
                            (5, "Strongly Agree"),
                        ]
                    ),
                ),
                ("suggestions", models.TextField(blank=True, default="")),
                ("email", models.EmailField(blank=True, default="", max_length=320)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-submitted_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="CustomerFeedbackResponse",
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
                    "services_received",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
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
                        default=list,
                        size=None,
                    ),
                ),
                ("other_service", models.CharField(blank=True, default="", max_length=255)),
                ("talked_to_guidance_counselor", models.BooleanField()),
                (
                    "accommodated_by",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("STUDENT_ASSISTANT", "Student Assistant"),
                            ("CLERK_PERSONNEL", "Clerk / Personnel"),
                        ],
                        default="",
                        max_length=24,
                    ),
                ),
                (
                    "office_visit_count",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10000),
                        ]
                    ),
                ),
                (
                    "personnel_accommodating_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "personnel_job_knowledge_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "personnel_flexibility_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "personnel_information_accuracy_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "personnel_appearance_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "personnel_commitment_delivery_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                ("transaction_duration", models.CharField(max_length=200)),
                (
                    "office_location_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "office_cleanliness_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "office_environment_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "office_hours_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "personnel_availability_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                (
                    "overall_satisfaction_rating",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Poor"),
                            (2, "Fair"),
                            (3, "Good"),
                            (4, "Very Good"),
                            (5, "Excellent"),
                        ]
                    ),
                ),
                ("additional_feedback", models.TextField(blank=True, default="")),
                ("future_service_improvement", models.TextField(blank=True, default="")),
                ("respondent_name_snapshot", models.CharField(max_length=200)),
                ("course_year_snapshot", models.CharField(max_length=160)),
                ("address_snapshot", models.TextField(blank=True, default="")),
                (
                    "mobile_number_snapshot",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "form_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="customer_feedback_responses",
                        to="institutional_forms.formrevision",
                    ),
                ),
            ],
            options={
                "ordering": ("-submitted_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddIndex(
            model_name="clientsatisfactionresponse",
            index=models.Index(fields=["submitted_at"], name="feedback_csm_submitted_idx"),
        ),
        migrations.AddIndex(
            model_name="customerfeedbackresponse",
            index=models.Index(fields=["submitted_at"], name="feedback_f14_submitted_idx"),
        ),
        migrations.AddConstraint(
            model_name="clientsatisfactionresponse",
            constraint=models.CheckConstraint(
                condition=models.Q(instrument_schema_version=1),
                name="feedback_csm_schema_version_one",
            ),
        ),
        migrations.AddConstraint(
            model_name="clientsatisfactionresponse",
            constraint=models.CheckConstraint(
                condition=models.Q(age__gte=0, age__lte=150),
                name="feedback_csm_age_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="clientsatisfactionresponse",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(client_type__in=["CITIZEN", "BUSINESS", "GOVERNMENT"])
                    & models.Q(sex__in=["MALE", "FEMALE"])
                ),
                name="feedback_csm_demographic_choices",
            ),
        ),
        migrations.AddConstraint(
            model_name="clientsatisfactionresponse",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(cc1=4, cc2=5, cc3=4)
                    | (
                        models.Q(cc1__in=[1, 2, 3])
                        & models.Q(cc2__in=[1, 2, 3, 4])
                        & models.Q(cc3__in=[1, 2, 3])
                    )
                ),
                name="feedback_csm_cc_conditional_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="clientsatisfactionresponse",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(sqd0__gte=0, sqd0__lte=5)
                    & models.Q(sqd1__gte=0, sqd1__lte=5)
                    & models.Q(sqd2__gte=0, sqd2__lte=5)
                    & models.Q(sqd3__gte=0, sqd3__lte=5)
                    & models.Q(sqd4__gte=0, sqd4__lte=5)
                    & models.Q(sqd5__gte=0, sqd5__lte=5)
                    & models.Q(sqd6__gte=0, sqd6__lte=5)
                    & models.Q(sqd7__gte=0, sqd7__lte=5)
                    & models.Q(sqd8__gte=0, sqd8__lte=5)
                ),
                name="feedback_csm_sqd_ranges",
            ),
        ),
        migrations.AddConstraint(
            model_name="customerfeedbackresponse",
            constraint=models.CheckConstraint(
                condition=models.Q(office_visit_count__gte=1, office_visit_count__lte=10000),
                name="feedback_f14_visit_count_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="customerfeedbackresponse",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(talked_to_guidance_counselor=True, accommodated_by="")
                    | (
                        models.Q(talked_to_guidance_counselor=False)
                        & models.Q(accommodated_by__in=["STUDENT_ASSISTANT", "CLERK_PERSONNEL"])
                    )
                ),
                name="feedback_f14_accommodation_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="customerfeedbackresponse",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(personnel_accommodating_rating__gte=1, personnel_accommodating_rating__lte=5)
                    & models.Q(personnel_job_knowledge_rating__gte=1, personnel_job_knowledge_rating__lte=5)
                    & models.Q(personnel_flexibility_rating__gte=1, personnel_flexibility_rating__lte=5)
                    & models.Q(personnel_information_accuracy_rating__gte=1, personnel_information_accuracy_rating__lte=5)
                    & models.Q(personnel_appearance_rating__gte=1, personnel_appearance_rating__lte=5)
                    & models.Q(personnel_commitment_delivery_rating__gte=1, personnel_commitment_delivery_rating__lte=5)
                    & models.Q(office_location_rating__gte=1, office_location_rating__lte=5)
                    & models.Q(office_cleanliness_rating__gte=1, office_cleanliness_rating__lte=5)
                    & models.Q(office_environment_rating__gte=1, office_environment_rating__lte=5)
                    & models.Q(office_hours_rating__gte=1, office_hours_rating__lte=5)
                    & models.Q(personnel_availability_rating__gte=1, personnel_availability_rating__lte=5)
                    & models.Q(overall_satisfaction_rating__gte=1, overall_satisfaction_rating__lte=5)
                ),
                name="feedback_f14_rating_ranges",
            ),
        ),
    ]
