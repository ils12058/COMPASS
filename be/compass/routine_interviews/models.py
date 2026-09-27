"""Interaction-specific Routine Interview persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
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

    # Student Intake (source Questions 1–7) and Counselor Evaluation (after the source's "No
    # writing beyond this point") are stored only as authenticated ciphertext bound to this record
    # and section (ADR-066). Read and write them through ``content`` after authorizing the actor;
    # queues, summaries, and counts use the plaintext metadata above and never decrypt.
    student_intake_ciphertext = models.TextField(editable=False)
    counselor_evaluation_ciphertext = models.TextField(editable=False)

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
            # Every row carries both sections, even when empty, so a blank column can never be
            # mistaken for an empty form. Rating ranges are enforced by the API and services.
            models.CheckConstraint(
                condition=~models.Q(student_intake_ciphertext=""),
                name="routine_intake_ciphertext_present",
            ),
            models.CheckConstraint(
                condition=~models.Q(counselor_evaluation_ciphertext=""),
                name="routine_evaluation_ciphertext_present",
            ),
        ]
