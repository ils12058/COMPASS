"""Institutional and GCO identity used by code-owned document presentation."""

from __future__ import annotations

import uuid

from django.db import models


class DocumentBrandingProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=32, unique=True, default="default")

    country_line = models.CharField(max_length=128)
    institution_name = models.CharField(max_length=255)
    institution_short_name = models.CharField(max_length=64)
    former_institution_name = models.CharField(max_length=255, null=True, blank=True)

    institution_address = models.CharField(max_length=500, null=True, blank=True)
    institution_website_url = models.URLField(max_length=500, null=True, blank=True)
    institution_contact_email = models.EmailField(max_length=320, null=True, blank=True)
    institution_social_url = models.URLField(max_length=500, null=True, blank=True)

    office_parent_unit_name = models.CharField(max_length=255, null=True, blank=True)
    office_name = models.CharField(max_length=255)
    office_email = models.EmailField(max_length=320, null=True, blank=True)
    office_phone = models.CharField(max_length=64, null=True, blank=True)
    office_location = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(key="default"),
                name="document_branding_supported_key",
            )
        ]
