"""Source-faithful persistence for the fixed institutional Exit Interview."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from compass.inventory.models import StudentInventory
from compass.organization.models import AcademicYear


class ExitInterviewStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"


class ProgramCompletion(models.TextChoices):
    ACCORDING_TO_SCHEDULE = "ACCORDING_TO_SCHEDULE", "According to schedule"
    WITH_SOME_DELAY = "WITH_SOME_DELAY", "With some delay"


class DelayReason(models.TextChoices):
    TRANSFEREE = "TRANSFEREE", "Transferee"
    ACADEMIC_FAILURES = "ACADEMIC_FAILURES", "Academic Failures"
    OTHER = "OTHER", "Others (pls. specify)"


class SignificantLearningExperience(models.TextChoices):
    INDEPENDENCE = "INDEPENDENCE", "Independence"
    INTERPERSONAL_RELATIONS = "INTERPERSONAL_RELATIONS", "Interpersonal Relations"
    INTELLECTUAL_GROWTH = "INTELLECTUAL_GROWTH", "Intellectual Growth"
    SPIRITUAL_GROWTH = "SPIRITUAL_GROWTH", "Spiritual Growth"
    RESPONSIBILITY = "RESPONSIBILITY", "Responsibility"
    WORKING_UNDER_PRESSURE = "WORKING_UNDER_PRESSURE", "Working under pressure"
    TIME_MANAGEMENT = "TIME_MANAGEMENT", "Time Management"
    SETTING_PRIORITIES = "SETTING_PRIORITIES", "Setting priorities"
    OTHER = "OTHER", "Others, pls. specify"


class CareerMode(models.TextChoices):
    WORK = "WORK", "Work"
    STUDY = "STUDY", "Study"


class WorkCareerChoice(models.TextChoices):
    RELATED_FIELD = "RELATED_FIELD", "in a field related to my course"
    UNRELATED_FIELD = "UNRELATED_FIELD", "in a field unrelated to my course"
    FAMILY_BUSINESS = "FAMILY_BUSINESS", "work in a family business"
    OWN_BUSINESS = "OWN_BUSINESS", "set up my own business"
    WORK_ABROAD = "WORK_ABROAD", "work abroad"
    NO_DEFINITE_PLAN = "NO_DEFINITE_PLAN", "no definite career plan yet"


class StudyCareerChoice(models.TextChoices):
    RELATED_FIELD = "RELATED_FIELD", "in a field related to my course"
    UNRELATED_FIELD = "UNRELATED_FIELD", "in a field unrelated to my course"


class SelfAssessmentItem(models.TextChoices):
    PRIDE_CONFIDENCE_CNSC = "PRIDE_CONFIDENCE_CNSC", "Pride and confidence in being from CNSC"
    ACADEMIC_RECREATION_BALANCE = (
        "ACADEMIC_RECREATION_BALANCE",
        "Ability to maintain balance between academics & recreational activities",
    )
    HOLISTIC_PERSONAL_WELL_BEING = (
        "HOLISTIC_PERSONAL_WELL_BEING",
        "Awareness of the importance of holistic personal well-being",
    )
    INTEGRATE_KNOWLEDGE_EXPERIENCE = (
        "INTEGRATE_KNOWLEDGE_EXPERIENCE",
        "Ability to integrate knowledge with experience",
    )
    CAREER_GOAL_CLARITY = "CAREER_GOAL_CLARITY", "Clarity of career goals"
    SELF_ESTEEM = "SELF_ESTEEM", "Self Esteem"
    SELF_AWARENESS = "SELF_AWARENESS", "Self-Awareness"
    COPE_WITH_PRESSURES = "COPE_WITH_PRESSURES", "Ability to cope with pressures"
    DEAL_WITH_DIFFERENT_WALKS = (
        "DEAL_WITH_DIFFERENT_WALKS",
        "Ability to deal comfortably with people from different walks of life",
    )
    LEADERSHIP = "LEADERSHIP", "Leadership"
    COMMUNICATION_SKILLS = "COMMUNICATION_SKILLS", "Communication Skills"
    CIVIC_MINDEDNESS = "CIVIC_MINDEDNESS", "Civic Mindedness"
    INITIATIVE = "INITIATIVE", "Initiative"
    DECISION_MAKING = "DECISION_MAKING", "Decision Making"
    RELATIONSHIP_WITH_GOD = "RELATIONSHIP_WITH_GOD", "Relationship with God"


class CollegeFeedbackItem(models.TextChoices):
    DEAN_AVAILABILITY = "DEAN_AVAILABILITY", "DEAN — Availability"
    DEAN_OPEN_MINDEDNESS = "DEAN_OPEN_MINDEDNESS", "DEAN — Open Mindedness"
    DEAN_CONCERN_FOR_STUDENTS = (
        "DEAN_CONCERN_FOR_STUDENTS",
        "DEAN — Concern for Students",
    )
    DEAN_COMMITMENT = "DEAN_COMMITMENT", "DEAN — Commitment"
    DEAN_APPROACHABILITY = "DEAN_APPROACHABILITY", "DEAN — Approachability"

    PROGRAM_CHAIR_AVAILABILITY = (
        "PROGRAM_CHAIR_AVAILABILITY",
        "PROG CHAIR — Availability",
    )
    PROGRAM_CHAIR_APPROACHABILITY = (
        "PROGRAM_CHAIR_APPROACHABILITY",
        "PROG CHAIR — Approachability",
    )
    PROGRAM_CHAIR_CONCERN_FOR_STUDENTS = (
        "PROGRAM_CHAIR_CONCERN_FOR_STUDENTS",
        "PROG CHAIR — Concern for Students",
    )

    FACULTY_AVAILABILITY = "FACULTY_AVAILABILITY", "FACULTY — Availability"
    FACULTY_APPROACHABILITY = "FACULTY_APPROACHABILITY", "FACULTY — Approachability"
    FACULTY_KNOWLEDGE_SUBJECT_MATTER = (
        "FACULTY_KNOWLEDGE_SUBJECT_MATTER",
        "FACULTY — Knowledge of subject matter",
    )
    FACULTY_TEACHING_SKILLS = "FACULTY_TEACHING_SKILLS", "FACULTY — Teaching Skills"

    CURRICULUM_RELEVANCE_SUBJECTS = (
        "CURRICULUM_RELEVANCE_SUBJECTS",
        "CURRICULUM — Relevance of subjects",
    )
    CURRICULUM_SYSTEMATIC_SEQUENCING = (
        "CURRICULUM_SYSTEMATIC_SEQUENCING",
        "CURRICULUM — Systematic Sequencing of Subjects",
    )
    CURRICULUM_COMPLETENESS = "CURRICULUM_COMPLETENESS", "CURRICULUM — Completeness"

    GUIDANCE_COUNSELOR_AVAILABILITY = (
        "GUIDANCE_COUNSELOR_AVAILABILITY",
        "GUIDANCE COUNSELOR — Availability",
    )
    GUIDANCE_COUNSELOR_APPROACHABILITY = (
        "GUIDANCE_COUNSELOR_APPROACHABILITY",
        "GUIDANCE COUNSELOR — Approachability",
    )
    GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS = (
        "GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS",
        "GUIDANCE COUNSELOR — Concern for Students",
    )
    GUIDANCE_COUNSELOR_EFFICIENCY = (
        "GUIDANCE_COUNSELOR_EFFICIENCY",
        "GUIDANCE COUNSELOR — Efficiency",
    )

    OFFICE_STAFF_SERVICE_ORIENTED = (
        "OFFICE_STAFF_SERVICE_ORIENTED",
        "OFFICE STAFF — Service Oriented",
    )
    OFFICE_STAFF_AVAILABILITY = "OFFICE_STAFF_AVAILABILITY", "OFFICE STAFF — Availability"
    OFFICE_STAFF_CONCERN_FOR_STUDENTS = (
        "OFFICE_STAFF_CONCERN_FOR_STUDENTS",
        "OFFICE STAFF — Concern for Students",
    )
    OFFICE_STAFF_APPROACHABILITY = (
        "OFFICE_STAFF_APPROACHABILITY",
        "OFFICE STAFF — Approachability",
    )

    FACILITIES_MAINTENANCE_CONDITION = (
        "FACILITIES_MAINTENANCE_CONDITION",
        "FACILITIES — Maintenance and Condition",
    )
    FACILITIES_AVAILABILITY = "FACILITIES_AVAILABILITY", "FACILITIES — Availability"
    FACILITIES_COMPLETENESS = "FACILITIES_COMPLETENESS", "FACILITIES — Completeness"


class ExitInterview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exit_interviews",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="exit_interviews",
    )
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.PROTECT,
        related_name="exit_interviews",
    )
    status = models.CharField(
        max_length=16,
        choices=ExitInterviewStatus.choices,
        default=ExitInterviewStatus.DRAFT,
    )

    student_name_snapshot = models.CharField(max_length=200, blank=True, default="")
    age_snapshot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(150)],
    )
    civil_status_snapshot = models.CharField(max_length=80, blank=True, default="")
    course_snapshot = models.CharField(max_length=180, blank=True, default="")
    major_snapshot = models.CharField(max_length=180, blank=True, default="")
    email_snapshot = models.EmailField(max_length=320, blank=True, default="")
    home_address_snapshot = models.TextField(blank=True, default="")
    contact_number_snapshot = models.CharField(max_length=64, blank=True, default="")

    program_completion = models.CharField(
        max_length=32,
        choices=ProgramCompletion.choices,
        blank=True,
        default="",
    )
    extra_terms_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    delay_reasons = ArrayField(
        models.CharField(max_length=32, choices=DelayReason.choices),
        default=list,
        blank=True,
    )
    delay_other = models.TextField(blank=True, default="")

    significant_learning_experiences = ArrayField(
        models.CharField(max_length=40, choices=SignificantLearningExperience.choices),
        default=list,
        blank=True,
    )
    significant_learning_other = models.TextField(blank=True, default="")

    career_modes = ArrayField(
        models.CharField(max_length=16, choices=CareerMode.choices),
        default=list,
        blank=True,
    )
    work_choices = ArrayField(
        models.CharField(max_length=32, choices=WorkCareerChoice.choices),
        default=list,
        blank=True,
    )
    study_choices = ArrayField(
        models.CharField(max_length=32, choices=StudyCareerChoice.choices),
        default=list,
        blank=True,
    )

    dean_comments = models.TextField(blank=True, default="")
    program_chair_comments = models.TextField(blank=True, default="")
    faculty_comments = models.TextField(blank=True, default="")
    curriculum_comments = models.TextField(blank=True, default="")
    guidance_counselor_comments = models.TextField(blank=True, default="")
    office_staff_comments = models.TextField(blank=True, default="")
    facilities_comments = models.TextField(blank=True, default="")
    suggestions_recommendations = models.TextField(blank=True, default="")

    first_submitted_at = models.DateTimeField(null=True, blank=True)
    last_submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-academic_year__label", "-created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "academic_year"),
                name="exit_interview_student_year_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ExitInterviewStatus.values),
                name="exit_interview_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(age_snapshot__isnull=True)
                    | models.Q(age_snapshot__gte=0, age_snapshot__lte=150)
                ),
                name="exit_interview_age_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(extra_terms_count__isnull=True)
                    | models.Q(extra_terms_count__gte=1)
                ),
                name="exit_interview_extra_terms_positive",
            ),
        ]


class ExitInterviewSelfAssessmentRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exit_interview = models.ForeignKey(
        ExitInterview,
        on_delete=models.CASCADE,
        related_name="self_assessment_ratings",
    )
    item_code = models.CharField(max_length=48, choices=SelfAssessmentItem.choices)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        default_permissions = ()
        ordering = ("item_code",)
        constraints = [
            models.UniqueConstraint(
                fields=("exit_interview", "item_code"),
                name="exit_interview_self_item_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(item_code__in=SelfAssessmentItem.values),
                name="exit_interview_self_item_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="exit_interview_self_rating_range",
            ),
        ]


class ExitInterviewCollegeFeedbackRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exit_interview = models.ForeignKey(
        ExitInterview,
        on_delete=models.CASCADE,
        related_name="college_feedback_ratings",
    )
    item_code = models.CharField(max_length=64, choices=CollegeFeedbackItem.choices)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    class Meta:
        default_permissions = ()
        ordering = ("item_code",)
        constraints = [
            models.UniqueConstraint(
                fields=("exit_interview", "item_code"),
                name="exit_interview_feedback_item_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(item_code__in=CollegeFeedbackItem.values),
                name="exit_interview_feedback_item_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=0, rating__lte=5),
                name="exit_interview_feedback_rating_range",
            ),
        ]


class ExitInterviewReopenEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exit_interview = models.ForeignKey(
        ExitInterview,
        on_delete=models.CASCADE,
        related_name="reopen_events",
    )
    reopened_at = models.DateTimeField()
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exit_interview_reopen_events",
    )
    reason = models.TextField(max_length=1000)

    class Meta:
        default_permissions = ()
        ordering = ("reopened_at", "id")
