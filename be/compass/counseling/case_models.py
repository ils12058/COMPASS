"""Counseling cases: one continuing episode of support for one Student (CW-1).

A case connects records that already exist. It never copies an Encounter, Appointment or Routine
Interview, and it never rewrites who authored them. Membership, responsibility and lifecycle are
separate facts: a session link is one row, the responsible Counselor is one column, and every
change is one append-only event.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CounselingCaseStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    CLOSED = "CLOSED", "Closed"


class CounselingCaseOrigin(models.TextChoices):
    """The authorized context a Counselor opened the case from."""

    INTAKE = "INTAKE", "Counseling intake"
    APPOINTMENT = "APPOINTMENT", "Appointment"
    ENCOUNTER = "ENCOUNTER", "Recorded session"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW", "Routine Interview"


class CounselingCaseSessionRemovalReason(models.TextChoices):
    """Why a session link was corrected. A closed list keeps history free of narrative."""

    BELONGS_TO_ANOTHER_CASE = "BELONGS_TO_ANOTHER_CASE", "Belongs to another case"
    NOT_PART_OF_THIS_CASE = "NOT_PART_OF_THIS_CASE", "Not part of this case"
    LINKED_BY_MISTAKE = "LINKED_BY_MISTAKE", "Linked by mistake"


class CounselingCaseEventKind(models.TextChoices):
    OPENED = "OPENED", "Case opened"
    SESSION_LINKED = "SESSION_LINKED", "Session linked"
    SESSION_UNLINKED = "SESSION_UNLINKED", "Session link corrected"


class CounselingCaseReferenceCounter(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(next_value__gte=1),
                name="counseling_case_reference_counter_positive",
            ),
        ]


class CounselingCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=32, unique=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_counseling_cases",
    )
    # Exactly one Counselor is responsible for a case. Only an accepted transfer (CW-3) changes it;
    # College assignment, session authorship and Appointment provider are different facts.
    primary_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="primary_counseling_cases",
    )
    status = models.CharField(
        max_length=16,
        choices=CounselingCaseStatus.choices,
        default=CounselingCaseStatus.ACTIVE,
    )
    origin = models.CharField(max_length=24, choices=CounselingCaseOrigin.choices)
    # Provenance of the opening context. It is never rewritten, including when the originating
    # session link is later corrected.
    origin_appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="originated_counseling_cases",
        null=True,
        blank=True,
    )
    origin_encounter = models.ForeignKey(
        "counseling.CounselingEncounter",
        on_delete=models.PROTECT,
        related_name="originated_counseling_cases",
        null=True,
        blank=True,
    )
    origin_routine_interview = models.ForeignKey(
        "routine_interviews.RoutineInterview",
        on_delete=models.PROTECT,
        related_name="originated_counseling_cases",
        null=True,
        blank=True,
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_counseling_cases",
    )
    opened_at = models.DateTimeField(default=timezone.now)
    # Incremented by every change to the case or its session links (optimistic concurrency).
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-opened_at", "id")
        indexes = [
            models.Index(
                fields=("primary_counselor", "status", "opened_at"),
                name="counseling_case_owner_idx",
            ),
            models.Index(
                fields=("student", "status"),
                name="counseling_case_student_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="counseling_case_version_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(student=models.F("primary_counselor")),
                name="counseling_case_counselor_not_student",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        origin=CounselingCaseOrigin.INTAKE,
                        origin_appointment__isnull=True,
                        origin_encounter__isnull=True,
                        origin_routine_interview__isnull=True,
                    )
                    | models.Q(
                        origin=CounselingCaseOrigin.APPOINTMENT,
                        origin_appointment__isnull=False,
                        origin_encounter__isnull=True,
                        origin_routine_interview__isnull=True,
                    )
                    | models.Q(
                        origin=CounselingCaseOrigin.ENCOUNTER,
                        origin_appointment__isnull=True,
                        origin_encounter__isnull=False,
                        origin_routine_interview__isnull=True,
                    )
                    | models.Q(
                        origin=CounselingCaseOrigin.ROUTINE_INTERVIEW,
                        origin_appointment__isnull=True,
                        origin_encounter__isnull=True,
                        origin_routine_interview__isnull=False,
                    )
                ),
                name="counseling_case_origin_matches_source",
            ),
        ]


class CounselingCaseSession(models.Model):
    """One completed Encounter's membership in one case.

    A corrected link is kept as a removed row. At most one row per Encounter is current, so a
    session is counted in at most one case and never twice.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        CounselingCase,
        on_delete=models.PROTECT,
        related_name="session_links",
    )
    encounter = models.ForeignKey(
        "counseling.CounselingEncounter",
        on_delete=models.PROTECT,
        related_name="case_links",
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="linked_counseling_case_sessions",
    )
    linked_at = models.DateTimeField(default=timezone.now)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="removed_counseling_case_sessions",
        null=True,
        blank=True,
    )
    removed_at = models.DateTimeField(null=True, blank=True)
    removal_reason = models.CharField(
        max_length=32,
        choices=CounselingCaseSessionRemovalReason.choices,
        blank=True,
        default="",
    )

    class Meta:
        default_permissions = ()
        ordering = ("-linked_at", "id")
        indexes = [
            models.Index(
                fields=("case", "removed_at"),
                name="counseling_case_session_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("encounter",),
                condition=models.Q(removed_at__isnull=True),
                name="counseling_case_session_one_current_case",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(removed_at__isnull=True, removed_by__isnull=True, removal_reason="")
                    | (
                        models.Q(removed_at__isnull=False, removed_by__isnull=False)
                        & ~models.Q(removal_reason="")
                    )
                ),
                name="counseling_case_session_removal_complete",
            ),
        ]


class CounselingCaseEvent(models.Model):
    """Append-only chronology of a case's responsibility, lifecycle and session links.

    Events hold identifiers and closed codes only. Each one records who was responsible for the
    case at that moment, so later transfers never rewrite earlier history.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        CounselingCase,
        on_delete=models.PROTECT,
        related_name="events",
    )
    # Position in this case's history, assigned while the case is locked. Events that share a
    # timestamp, such as an opening and its first session link, still have one order.
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=24, choices=CounselingCaseEventKind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="counseling_case_events",
    )
    primary_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="responsible_counseling_case_events",
    )
    encounter = models.ForeignKey(
        "counseling.CounselingEncounter",
        on_delete=models.PROTECT,
        related_name="case_events",
        null=True,
        blank=True,
    )
    # A closed code for the event: the origin of an opening, or the reason for a correction.
    detail_code = models.CharField(max_length=32, blank=True, default="")
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        ordering = ("case", "-sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("case", "sequence"),
                name="counseling_case_event_sequence_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gt=0),
                name="counseling_case_event_sequence_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind=CounselingCaseEventKind.OPENED)
                    | models.Q(encounter__isnull=False)
                ),
                name="counseling_case_event_session_named",
            ),
        ]


__all__ = [
    "CounselingCase",
    "CounselingCaseEvent",
    "CounselingCaseEventKind",
    "CounselingCaseOrigin",
    "CounselingCaseReferenceCounter",
    "CounselingCaseSession",
    "CounselingCaseSessionRemovalReason",
    "CounselingCaseStatus",
]
