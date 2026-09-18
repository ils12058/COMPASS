"""Source-faithful Customer Feedback and CSM response models."""

from __future__ import annotations

import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from compass.institutional_forms.models import FormRevision


class CustomerFeedbackService(models.TextChoices):
    COUNSELING = "COUNSELING", "Counseling"
    ADMISSION = "ADMISSION", "Admission"
    TESTING = "TESTING", "Testing"
    EDUCATIONAL_INFORMATION = "EDUCATIONAL_INFORMATION", "Educational Information"
    REQUEST_FOR_CERTIFICATION = "REQUEST_FOR_CERTIFICATION", "Request for Certification"
    APPLICATION_FOR_ADMISSION_TEST = (
        "APPLICATION_FOR_ADMISSION_TEST",
        "Application for Admission Test",
    )
    OTHER = "OTHER", "Others (please specify)"


class CustomerFeedbackAccommodatedBy(models.TextChoices):
    STUDENT_ASSISTANT = "STUDENT_ASSISTANT", "Student Assistant"
    CLERK_PERSONNEL = "CLERK_PERSONNEL", "Clerk / Personnel"


class CustomerFeedbackRating(models.IntegerChoices):
    POOR = 1, "Poor"
    FAIR = 2, "Fair"
    GOOD = 3, "Good"
    VERY_GOOD = 4, "Very Good"
    EXCELLENT = 5, "Excellent"


class CSMClientType(models.TextChoices):
    CITIZEN = "CITIZEN", "Citizen"
    BUSINESS = "BUSINESS", "Business"
    GOVERNMENT = "GOVERNMENT", "Government (Employee or another agency)"


class CSMSex(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"


class CSMCC1(models.IntegerChoices):
    KNOWS_AND_SAW = 1, "Knows Citizen's Charter and saw this office's Charter"
    KNOWS_NOT_SEEN = 2, "Knows Citizen's Charter but did not see this office's Charter"
    LEARNED_WHEN_SEEN = 3, "Learned of Citizen's Charter when seeing this office's Charter"
    DOES_NOT_KNOW = 4, "Does not know Citizen's Charter and did not see one in this office"


class CSMCC2(models.IntegerChoices):
    EASY_TO_SEE = 1, "Easy to see"
    SOMEWHAT_EASY_TO_SEE = 2, "Somewhat easy to see"
    DIFFICULT_TO_SEE = 3, "Difficult to see"
    NOT_VISIBLE = 4, "Not visible at all"
    NOT_APPLICABLE = 5, "N/A"


class CSMCC3(models.IntegerChoices):
    HELPED_VERY_MUCH = 1, "Helped very much"
    SOMEWHAT_HELPED = 2, "Somewhat helped"
    DID_NOT_HELP = 3, "Did not help"
    NOT_APPLICABLE = 4, "N/A"


class CSMRating(models.IntegerChoices):
    NOT_APPLICABLE = 0, "Not Applicable"
    STRONGLY_DISAGREE = 1, "Strongly Disagree"
    DISAGREE = 2, "Disagree"
    NEITHER_AGREE_NOR_DISAGREE = 3, "Neither Agree nor Disagree"
    AGREE = 4, "Agree"
    STRONGLY_AGREE = 5, "Strongly Agree"


class CustomerFeedbackResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="customer_feedback_responses",
    )
    services_received = ArrayField(
        models.CharField(max_length=40, choices=CustomerFeedbackService.choices),
        default=list,
    )
    other_service = models.CharField(max_length=255, blank=True, default="")
    talked_to_guidance_counselor = models.BooleanField()
    accommodated_by = models.CharField(
        max_length=24,
        choices=CustomerFeedbackAccommodatedBy.choices,
        blank=True,
        default="",
    )
    office_visit_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )

    personnel_accommodating_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    personnel_job_knowledge_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    personnel_flexibility_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    personnel_information_accuracy_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    personnel_appearance_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    personnel_commitment_delivery_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    transaction_duration = models.CharField(max_length=200)

    office_location_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    office_cleanliness_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    office_environment_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    office_hours_rating = models.PositiveSmallIntegerField(choices=CustomerFeedbackRating.choices)
    personnel_availability_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )
    overall_satisfaction_rating = models.PositiveSmallIntegerField(
        choices=CustomerFeedbackRating.choices
    )

    additional_feedback = models.TextField(blank=True, default="")
    future_service_improvement = models.TextField(blank=True, default="")
    respondent_name_snapshot = models.CharField(max_length=200)
    course_year_snapshot = models.CharField(max_length=160)
    address_snapshot = models.TextField(blank=True, default="")
    mobile_number_snapshot = models.CharField(max_length=64, blank=True, default="")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("-submitted_at", "id")
        indexes = [models.Index(fields=("submitted_at",), name="feedback_f14_submitted_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(office_visit_count__gte=1, office_visit_count__lte=10000),
                name="feedback_f14_visit_count_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(talked_to_guidance_counselor=True, accommodated_by="")
                    | (
                        models.Q(talked_to_guidance_counselor=False)
                        & models.Q(accommodated_by__in=CustomerFeedbackAccommodatedBy.values)
                    )
                ),
                name="feedback_f14_accommodation_shape",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        personnel_accommodating_rating__gte=1, personnel_accommodating_rating__lte=5
                    )
                    & models.Q(
                        personnel_job_knowledge_rating__gte=1, personnel_job_knowledge_rating__lte=5
                    )
                    & models.Q(
                        personnel_flexibility_rating__gte=1, personnel_flexibility_rating__lte=5
                    )
                    & models.Q(
                        personnel_information_accuracy_rating__gte=1,
                        personnel_information_accuracy_rating__lte=5,
                    )
                    & models.Q(
                        personnel_appearance_rating__gte=1, personnel_appearance_rating__lte=5
                    )
                    & models.Q(
                        personnel_commitment_delivery_rating__gte=1,
                        personnel_commitment_delivery_rating__lte=5,
                    )
                    & models.Q(office_location_rating__gte=1, office_location_rating__lte=5)
                    & models.Q(office_cleanliness_rating__gte=1, office_cleanliness_rating__lte=5)
                    & models.Q(office_environment_rating__gte=1, office_environment_rating__lte=5)
                    & models.Q(office_hours_rating__gte=1, office_hours_rating__lte=5)
                    & models.Q(
                        personnel_availability_rating__gte=1, personnel_availability_rating__lte=5
                    )
                    & models.Q(
                        overall_satisfaction_rating__gte=1, overall_satisfaction_rating__lte=5
                    )
                ),
                name="feedback_f14_rating_ranges",
            ),
        ]


class ClientSatisfactionResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument_schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    client_type = models.CharField(max_length=16, choices=CSMClientType.choices)
    sex = models.CharField(max_length=8, choices=CSMSex.choices)
    age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(150)]
    )
    region_of_residence = models.CharField(max_length=160)
    service_availed = models.CharField(max_length=255)
    cc1 = models.PositiveSmallIntegerField(choices=CSMCC1.choices)
    cc2 = models.PositiveSmallIntegerField(choices=CSMCC2.choices)
    cc3 = models.PositiveSmallIntegerField(choices=CSMCC3.choices)
    sqd0 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd1 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd2 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd3 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd4 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd5 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd6 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd7 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    sqd8 = models.PositiveSmallIntegerField(choices=CSMRating.choices)
    suggestions = models.TextField(blank=True, default="")
    email = models.EmailField(max_length=320, blank=True, default="")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("-submitted_at", "id")
        indexes = [models.Index(fields=("submitted_at",), name="feedback_csm_submitted_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(instrument_schema_version=1),
                name="feedback_csm_schema_version_one",
            ),
            models.CheckConstraint(
                condition=models.Q(age__gte=0, age__lte=150),
                name="feedback_csm_age_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(client_type__in=CSMClientType.values) & models.Q(sex__in=CSMSex.values)
                ),
                name="feedback_csm_demographic_choices",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        cc1=CSMCC1.DOES_NOT_KNOW,
                        cc2=CSMCC2.NOT_APPLICABLE,
                        cc3=CSMCC3.NOT_APPLICABLE,
                    )
                    | (
                        models.Q(cc1__in=[1, 2, 3])
                        & models.Q(cc2__in=[1, 2, 3, 4])
                        & models.Q(cc3__in=[1, 2, 3])
                    )
                ),
                name="feedback_csm_cc_conditional_shape",
            ),
            models.CheckConstraint(
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
        ]
