"""Persistent institutional controlled-form identity metadata."""

from __future__ import annotations

import uuid

from django.db import models


class FormRevisionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class FormFamily(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("key",)

    def __str__(self) -> str:
        return self.key


class FormRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey(
        FormFamily,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    official_code = models.CharField(max_length=96, null=True, blank=True)
    official_revision = models.CharField(max_length=32, null=True, blank=True)
    internal_schema_version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=FormRevisionStatus.choices,
        default=FormRevisionStatus.INACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("family__key", "internal_schema_version", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("family", "internal_schema_version"),
                name="institutional_forms_family_schema_version_uniq",
            ),
            models.UniqueConstraint(
                fields=("family", "official_code", "official_revision"),
                condition=(
                    models.Q(official_code__isnull=False)
                    & models.Q(official_revision__isnull=False)
                ),
                name="institutional_forms_official_identity_uniq",
            ),
            models.UniqueConstraint(
                fields=("family",),
                condition=models.Q(status=FormRevisionStatus.ACTIVE),
                name="institutional_forms_one_active_revision_per_family",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.family.key}:{self.official_code or '-'}:{self.official_revision or '-'}"
