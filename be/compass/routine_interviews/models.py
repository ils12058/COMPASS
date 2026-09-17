"""Interaction-specific Routine Interview persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from compass.appointments.models import Appointment
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.institutional_forms.models import FormRevision
from compass.inventory.models import StudentInventory
from compass.service_catalog.models import DeliveryMode


class RoutineConcern(models.TextChoices):
    FAMILY = "FAMILY", "Family"
    FINANCIAL = "FINANCIAL", "Financial"
    ACADEMIC = "ACADEMIC", "Academic"
    FRIENDS = "FRIENDS", "Friends"
    CLASSMATES = "CLASSMATES", "Classmates"
    VICES = "VICES", "Vices"
    LOVE_LIFE = "LOVE_LIFE", "Love life"
    SLEEPING_PROBLEMS = "SLEEPING_PROBLEMS", "Sleeping problems"
    SUICIDAL_THOUGHT_TENDENCY = "SUICIDAL_THOUGHT_TENDENCY", "Suicidal thought/tendency"
    DORM_BOARDING_HOUSE = "DORM_BOARDING_HOUSE", "Dorm / boarding house"
    PAST_PAINFUL_EXPERIENCE = "PAST_PAINFUL_EXPERIENCE", "Past painful experience"
    OTHER = "OTHER", "Other"


class RoutineInterview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_routine_interviews",
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="counselor_routine_interviews",
    )
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.PROTECT,
        related_name="routine_interviews",
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        related_name="routine_interview",
        null=True,
        blank=True,
    )
    counseling_encounter = models.OneToOneField(
        CounselingEncounter,
        on_delete=models.PROTECT,
        related_name="routine_interview",
        null=True,
        blank=True,
    )
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="routine_interviews",
        null=True,
        blank=True,
    )
    entry_mode = models.CharField(max_length=16, choices=CounselingEntryMode.choices)
    delivery_mode = models.CharField(max_length=16, choices=DeliveryMode.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_routine_interviews",
        null=True,
        blank=True,
    )
    intake_submitted_at = models.DateTimeField(null=True, blank=True)
    evaluation_finalized_at = models.DateTimeField(null=True, blank=True)

    # Student Intake — source Questions 1–7.
    coping_with_college_challenges = models.TextField(blank=True, default="")
    coping_remarks = models.TextField(blank=True, default="")
    college_experience = models.TextField(blank=True, default="")
    reason_for_choosing_institution = models.TextField(blank=True, default="")
    difficulties_encountered = models.TextField(blank=True, default="")
    stress_anxiety_causes = models.TextField(blank=True, default="")
    stress_anxiety_management = models.TextField(blank=True, default="")
    family_description = models.TextField(blank=True, default="")
    concerns = ArrayField(
        models.CharField(max_length=40, choices=RoutineConcern.choices),
        default=list,
        blank=True,
    )
    other_concern_specification = models.TextField(blank=True, default="")
    concerns_explanation = models.TextField(blank=True, default="")
    college_adjustment_and_peer_group = models.TextField(blank=True, default="")
    academic_goals = models.TextField(blank=True, default="")
    career_goals = models.TextField(blank=True, default="")

    # Counselor Evaluation — explicitly separated by the source "No writing beyond this point".
    academic_adjustment_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    physical_adjustment_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    social_adjustment_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    spiritual_adjustment_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    financial_adjustment_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    emotional_adjustment_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    other_adjustment = models.TextField(blank=True, default="")
    special_concern = models.TextField(blank=True, default="")
    recommendations = models.TextField(blank=True, default="")

    # Direct creation retries use a persistent, actor-scoped digest rather than response replay.
    direct_creation_key_digest = models.CharField(max_length=64, null=True, blank=True, unique=True)
    direct_request_fingerprint = models.CharField(max_length=64, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(
                fields=("student", "created_at"),
                name="routine_student_created_idx",
            ),
            models.Index(
                fields=("counselor", "created_at"),
                name="routine_counselor_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        entry_mode=CounselingEntryMode.APPOINTMENT,
                        appointment__isnull=False,
                    )
                    | (
                        ~models.Q(entry_mode=CounselingEntryMode.APPOINTMENT)
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
            *[
                models.CheckConstraint(
                    condition=(
                        models.Q(**{f"{field}__isnull": True})
                        | (models.Q(**{f"{field}__gte": 1}) & models.Q(**{f"{field}__lte": 10}))
                    ),
                    name=f"routine_{prefix}_rating_range",
                )
                for field, prefix in (
                    ("academic_adjustment_rating", "academic"),
                    ("physical_adjustment_rating", "physical"),
                    ("social_adjustment_rating", "social"),
                    ("spiritual_adjustment_rating", "spiritual"),
                    ("financial_adjustment_rating", "financial"),
                    ("emotional_adjustment_rating", "emotional"),
                )
            ],
        ]
