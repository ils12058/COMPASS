"""Durable Notification intent, email delivery state, and user preference."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .policy import NotificationPolicy


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    event_code = models.CharField(max_length=128)
    policy = models.CharField(max_length=32, choices=NotificationPolicy.choices())
    title = models.CharField(max_length=255)
    message = models.TextField()
    source_type = models.CharField(max_length=64)
    source_id = models.UUIDField()
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("recipient", "read_at", "created_at"),
                name="notif_recipient_read_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("recipient", "event_code", "source_type", "source_id"),
                name="notif_logical_event_uniq",
            ),
        ]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class EmailDeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class EmailDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.OneToOneField(
        Notification,
        on_delete=models.CASCADE,
        related_name="email_delivery",
    )
    status = models.CharField(
        max_length=16,
        choices=EmailDeliveryStatus.choices,
        default=EmailDeliveryStatus.PENDING,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    failure_code = models.CharField(max_length=64, blank=True, default="")
    claim_token = models.UUIDField(blank=True, null=True, editable=False)
    claim_expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        indexes = [
            models.Index(
                fields=("status", "next_attempt_at"),
                name="email_delivery_due_idx",
            ),
            models.Index(
                fields=("status", "claim_expires_at"),
                name="email_delivery_claim_idx",
            ),
        ]


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="notification_preference",
    )
    optional_email_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class PushSubscription(models.Model):
    """One browser push endpoint, bound to the session that enabled it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey("authentication.AuthSession", on_delete=models.CASCADE)
    endpoint_digest = models.CharField(max_length=64, unique=True)
    encrypted_endpoint = models.TextField()
    encrypted_p256dh = models.TextField()
    encrypted_auth = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        indexes = [models.Index(fields=("user", "active"), name="push_sub_user_active_idx")]


class PushDeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class PushDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    subscription = models.ForeignKey(PushSubscription, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=16, choices=PushDeliveryStatus.choices, default=PushDeliveryStatus.PENDING
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    claim_token = models.UUIDField(null=True, blank=True, editable=False)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("notification", "subscription"), name="push_delivery_once_uniq"
            )
        ]
        indexes = [models.Index(fields=("status", "next_attempt_at"), name="push_delivery_due_idx")]


__all__ = [
    "EmailDelivery",
    "EmailDeliveryStatus",
    "Notification",
    "NotificationPreference",
    "PushSubscription",
    "PushDelivery",
    "PushDeliveryStatus",
]
