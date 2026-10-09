"""Encrypted immutable messages, institutional threads, and private read cursors."""

import uuid

from django.conf import settings
from django.db import models


class ThreadKind(models.TextChoices):
    OFFICE = "OFFICE", "Guidance Office"
    COUNSELING = "COUNSELING", "Counseling"


class ThreadStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"


class GuidanceThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=ThreadKind.choices)
    status = models.CharField(
        max_length=16, choices=ThreadStatus.choices, default=ThreadStatus.OPEN
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="guidance_threads"
    )
    routing_college = models.ForeignKey(
        "organization.College", on_delete=models.PROTECT, null=True, blank=True
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="counselor_guidance_threads",
    )
    relationship_appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="guidance_thread",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_guidance_threads",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_guidance_threads"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_sequence = models.PositiveBigIntegerField(default=0)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_guidance_threads",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ("-last_message_at", "-id")
        indexes = [
            models.Index(
                fields=("routing_college", "-last_message_at", "-id"),
                name="gm_office_directory_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind="OFFICE",
                        routing_college__isnull=False,
                        counselor__isnull=True,
                        relationship_appointment__isnull=True,
                    )
                    | models.Q(
                        kind="COUNSELING",
                        routing_college__isnull=True,
                        counselor__isnull=False,
                        relationship_appointment__isnull=False,
                        assigned_to__isnull=True,
                    )
                ),
                name="gm_thread_family_shape",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="OPEN", resolved_at__isnull=True, resolved_by__isnull=True)
                    | models.Q(
                        status="RESOLVED", resolved_at__isnull=False, resolved_by__isnull=False
                    )
                ),
                name="gm_thread_resolution_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(last_sequence__gte=0), name="gm_thread_sequence_nonnegative"
            ),
            models.UniqueConstraint(
                fields=("student",),
                condition=models.Q(kind="OFFICE", status="OPEN"),
                name="gm_one_open_office_per_student",
            ),
        ]


class GuidanceMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(GuidanceThread, on_delete=models.PROTECT, related_name="messages")
    sequence = models.PositiveBigIntegerField()
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_guidance_messages"
    )
    client_message_id = models.UUIDField()
    body_ciphertext = models.TextField()
    body_schema_version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("thread", "sequence"), name="gm_message_thread_sequence_unique"
            ),
            models.UniqueConstraint(
                fields=("sender", "client_message_id"), name="gm_message_sender_client_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gte=1), name="gm_message_sequence_positive"
            ),
        ]


class GuidanceThreadReadState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(GuidanceThread, on_delete=models.PROTECT, related_name="read_states")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="guidance_read_states"
    )
    last_read_sequence = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("thread", "user"), name="gm_read_thread_user_unique"),
            models.CheckConstraint(
                condition=models.Q(last_read_sequence__gte=0), name="gm_read_sequence_nonnegative"
            ),
        ]
