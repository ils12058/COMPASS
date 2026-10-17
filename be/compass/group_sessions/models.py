"""Domain models for Group Sessions, Facilitators, Registrations, and Attendance."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from compass.service_catalog.models import DeliveryMode


class GroupSessionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    CANCELLED = "CANCELLED", "Cancelled"
    COMPLETED = "COMPLETED", "Completed"


class GroupSessionFacilitatorKind(models.TextChoices):
    INTERNAL = "INTERNAL", "Internal COMPASS person"
    EXTERNAL = "EXTERNAL", "External guest"


class GroupSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        "service_catalog.Service",
        on_delete=models.PROTECT,
        related_name="group_sessions",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    delivery_mode = models.CharField(
        max_length=32,
        choices=DeliveryMode.choices,
        default=DeliveryMode.IN_PERSON,
    )
    venue_or_meeting_url = models.CharField(max_length=500, blank=True, default="")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reg_opens_at = models.DateTimeField(blank=True, null=True)
    reg_closes_at = models.DateTimeField(blank=True, null=True)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=32,
        choices=GroupSessionStatus.choices,
        default=GroupSessionStatus.DRAFT,
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_group_sessions",
    )
    cancellation_reason = models.TextField(blank=True, default="")
    cancelled_at = models.DateTimeField(blank=True, null=True)
    version = models.PositiveIntegerField(default=1)
    # Advances only when the schedule or delivery details change. Reschedule
    # notifications carry this revision so a later change makes older notices stale.
    schedule_revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("starts_at", "title")
        indexes = [
            models.Index(fields=["status", "starts_at"], name="grp_session_status_starts_idx"),
            models.Index(fields=["service", "status"], name="grp_session_svc_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="grp_session_valid_time_range",
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__gt=0),
                name="grp_session_pos_capacity",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status}) [{self.starts_at}]"


class GroupSessionFacilitator(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_session = models.ForeignKey(
        GroupSession,
        on_delete=models.PROTECT,
        related_name="facilitators",
    )
    internal_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="facilitated_group_sessions",
        db_column="counselor_id",
        null=True,
        blank=True,
    )
    kind = models.CharField(
        max_length=16,
        choices=GroupSessionFacilitatorKind.choices,
        default=GroupSessionFacilitatorKind.INTERNAL,
        db_default=GroupSessionFacilitatorKind.INTERNAL,
    )
    external_display_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_default="",
    )
    display_name_snapshot = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_default="",
    )
    is_lead = models.BooleanField(default=False)
    removed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("-is_lead", "created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind=GroupSessionFacilitatorKind.INTERNAL,
                        internal_user__isnull=False,
                        external_display_name="",
                    )
                    | models.Q(
                        kind=GroupSessionFacilitatorKind.EXTERNAL,
                        internal_user__isnull=True,
                    )
                    & ~models.Q(external_display_name="")
                ),
                name="grp_fac_identity_matches_kind",
            ),
            models.UniqueConstraint(
                fields=["group_session", "internal_user"],
                condition=models.Q(
                    kind=GroupSessionFacilitatorKind.INTERNAL,
                    removed_at__isnull=True,
                ),
                name="grp_fac_active_internal_uniq",
            ),
            models.UniqueConstraint(
                fields=["group_session"],
                condition=models.Q(is_lead=True, removed_at__isnull=True),
                name="grp_fac_active_lead_uniq",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.display_name_snapshot:
            if self.kind == GroupSessionFacilitatorKind.INTERNAL and self.internal_user_id:
                self.display_name_snapshot = self.internal_user.get_full_name().strip()
            elif self.kind == GroupSessionFacilitatorKind.EXTERNAL:
                self.display_name_snapshot = self.external_display_name.strip()
        super().save(*args, **kwargs)

    @property
    def is_current(self) -> bool:
        return self.removed_at is None

    @property
    def display_name(self) -> str:
        return self.display_name_snapshot or self.external_display_name

    def __str__(self) -> str:
        lead_flag = " (Lead)" if self.is_lead else ""
        return f"{self.display_name}{lead_flag} @ {self.group_session.title}"


class RegistrationStatus(models.TextChoices):
    REGISTERED = "REGISTERED", "Registered"
    CANCELLED = "CANCELLED", "Cancelled"


class GroupSessionRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_session = models.ForeignKey(
        GroupSession,
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="group_session_registrations",
    )
    status = models.CharField(
        max_length=32,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.REGISTERED,
    )
    registered_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("registered_at",)
        indexes = [
            models.Index(fields=["group_session", "status"], name="grp_reg_session_status_idx"),
            models.Index(fields=["student", "status"], name="grp_reg_student_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["group_session", "student"],
                condition=models.Q(status="REGISTERED"),
                name="grp_reg_active_student_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} -> {self.group_session.title} ({self.status})"


class GroupSessionAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.OneToOneField(
        GroupSessionRegistration,
        on_delete=models.PROTECT,
        related_name="attendance",
    )
    attended = models.BooleanField(default=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marked_group_attendances",
    )
    marked_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("marked_at",)

    def __str__(self) -> str:
        status = "Present" if self.attended else "Absent"
        return f"{self.registration.student}: {status}"
