"""Curated GCO Resource persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.publications import PublicationAudience, PublicationStatus


class ResourceKind(models.TextChoices):
    ARTICLE = "ARTICLE", "Article"
    EXTERNAL_LINK = "EXTERNAL_LINK", "External link"
    FILE = "FILE", "File"


class ResourceCategory(models.TextChoices):
    GENERAL = "GENERAL", "General"
    COUNSELING = "COUNSELING", "Counseling"
    MENTAL_HEALTH = "MENTAL_HEALTH", "Mental health"
    ACADEMIC_SUPPORT = "ACADEMIC_SUPPORT", "Academic support"
    CAREER = "CAREER", "Career"
    WELLNESS = "WELLNESS", "Wellness"
    FORMS_AND_GUIDES = "FORMS_AND_GUIDES", "Forms and guides"
    OTHER = "OTHER", "Other"


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    body_markdown = models.TextField()
    category = models.CharField(max_length=32, choices=ResourceCategory.choices)
    kind = models.CharField(max_length=24, choices=ResourceKind.choices)
    audience = models.CharField(max_length=32, choices=PublicationAudience.choices)
    status = models.CharField(
        max_length=16,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    external_url = models.URLField(max_length=2048, blank=True, default="")
    storage_key = models.CharField(max_length=512, blank=True, default="")
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    display_order = models.IntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resources_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resources_updated",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resources_published",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("display_order", "-published_at", "-id")
        indexes = [
            models.Index(fields=("status", "display_order"), name="res_status_order_idx"),
            models.Index(fields=("category", "display_order"), name="res_cat_order_idx"),
            models.Index(fields=("kind", "display_order"), name="res_kind_order_idx"),
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
                name="res_published_metadata",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind=ResourceKind.ARTICLE, external_url="", storage_key="")
                    | models.Q(kind=ResourceKind.EXTERNAL_LINK, storage_key="")
                    | models.Q(kind=ResourceKind.FILE, external_url="")
                ),
                name="res_kind_channels",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        storage_key="",
                        original_filename="",
                        content_type="",
                        size_bytes=0,
                    )
                    | (
                        ~models.Q(storage_key="")
                        & ~models.Q(original_filename="")
                        & ~models.Q(content_type="")
                        & models.Q(size_bytes__gt=0)
                    )
                ),
                name="res_file_metadata_complete",
            ),
        ]


__all__ = ["Resource", "ResourceCategory", "ResourceKind"]
