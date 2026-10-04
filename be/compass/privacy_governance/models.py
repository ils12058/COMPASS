"""Privacy-governance records without underlying confidential domain content."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from .retention_models import (  # noqa: F401
    DispositionCase,
    DispositionHold,
    OperationalRetentionRule,
)


class PrivacyNotice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)


class PrivacyNoticeRevisionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class PrivacyNoticeRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notice = models.ForeignKey(PrivacyNotice, on_delete=models.PROTECT, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=PrivacyNoticeRevisionStatus.choices,
        default=PrivacyNoticeRevisionStatus.DRAFT,
    )
    title = models.CharField(max_length=200)
    audiences = models.JSONField(default=list)
    summary = models.TextField(max_length=2_000)
    body = models.TextField(max_length=20_000)
    requires_acknowledgment = models.BooleanField(default=False)
    effective_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_privacy_notice_revisions",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_privacy_notice_revisions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ("notice_id", "-revision_number")
        constraints = [
            models.UniqueConstraint(
                fields=("notice", "revision_number"), name="unique_notice_revision_number"
            ),
            models.UniqueConstraint(
                fields=("notice",), condition=Q(status="DRAFT"), name="one_notice_draft"
            ),
            models.UniqueConstraint(
                fields=("notice",), condition=Q(status="PUBLISHED"), name="one_notice_published"
            ),
        ]


class PrivacyNoticeAcknowledgment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="privacy_notice_acknowledgments",
    )
    revision = models.ForeignKey(
        PrivacyNoticeRevision, on_delete=models.PROTECT, related_name="acknowledgments"
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("user", "revision"), name="unique_notice_acknowledgment"
            )
        ]


__all__ = [
    "PrivacyNotice",
    "PrivacyNoticeRevision",
    "PrivacyNoticeRevisionStatus",
    "PrivacyNoticeAcknowledgment",
]
