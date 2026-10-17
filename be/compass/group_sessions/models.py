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
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="facilitated_group_sessions",
    )
    is_lead = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("-is_lead", "counselor__last_name", "counselor__first_name")
        constraints = [
            models.UniqueConstraint(
                fields=["group_session", "counselor"],
                name="grp_facil_session_counselor_uniq",
            ),
        ]

    def __str__(self) -> str:
        lead_flag = " (Lead)" if self.is_lead else ""
        return f"{self.counselor}{lead_flag} @ {self.group_session.title}"


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
