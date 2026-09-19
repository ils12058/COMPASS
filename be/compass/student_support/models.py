"""Supplemental annual Student support/profile facts outside the controlled F5 form."""

from __future__ import annotations

import uuid

from django.db import models

from compass.inventory.models import StudentInventory


class FourPsStatus(models.TextChoices):
    BENEFICIARY = "BENEFICIARY", "4Ps household beneficiary"
    NOT_BENEFICIARY = "NOT_BENEFICIARY", "Not a 4Ps household beneficiary"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class IndigenousPeoplesStatus(models.TextChoices):
    MEMBER = "MEMBER", "Indigenous Peoples member"
    NOT_MEMBER = "NOT_MEMBER", "Not an Indigenous Peoples member"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class ParentLifeStatus(models.TextChoices):
    LIVING = "LIVING", "Living"
    DECEASED = "DECEASED", "Deceased"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class StudentSupportProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.OneToOneField(
        StudentInventory,
        on_delete=models.CASCADE,
        related_name="support_profile",
    )
    four_ps_status = models.CharField(
        max_length=24,
        choices=FourPsStatus.choices,
        null=True,
        blank=True,
    )
    indigenous_peoples_status = models.CharField(
        max_length=24,
        choices=IndigenousPeoplesStatus.choices,
        null=True,
        blank=True,
    )
    mother_life_status = models.CharField(
        max_length=24,
        choices=ParentLifeStatus.choices,
        null=True,
        blank=True,
    )
    father_life_status = models.CharField(
        max_length=24,
        choices=ParentLifeStatus.choices,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
