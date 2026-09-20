"""GCO Announcement persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.publications import PublicationAudience, PublicationStatus


class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    body_markdown = models.TextField()
    audience = models.CharField(max_length=32, choices=PublicationAudience.choices)
    status = models.CharField(
        max_length=16,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements_updated",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements_published",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-is_pinned", "-published_at", "-id")
        indexes = [
            models.Index(fields=("status", "-published_at"), name="ann_status_pub_idx"),
            models.Index(fields=("status", "expires_at"), name="ann_status_exp_idx"),
            models.Index(fields=("is_pinned", "-published_at"), name="ann_pin_pub_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(status=PublicationStatus.PUBLISHED)
                    | (
                        models.Q(published_at__isnull=False)
                        & models.Q(published_by__isnull=False)
                    )
                ),
                name="ann_published_metadata",
            ),
        ]


__all__ = ["Announcement"]
