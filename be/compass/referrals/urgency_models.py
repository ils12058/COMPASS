"""Append-only COMPASS urgency supplement; no official Referral Slip fields."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class _UrgencyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Referral urgency changes cannot be updated.")

    def delete(self):
        raise ValidationError("Referral urgency changes cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Referral urgency changes cannot be updated.")

    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Referral urgency changes cannot be updated.")
        return super().bulk_create(objs, **kwargs)


class ReferralUrgencyChange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(
        "referrals.Referral", on_delete=models.PROTECT, related_name="urgency_changes"
    )
    version = models.PositiveIntegerField()
    is_urgent = models.BooleanField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField()
    objects = _UrgencyQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(
                fields=("referral", "version"), name="referral_urgency_version_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="referral_urgency_positive"
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise ValidationError("Referral urgency changes cannot be updated.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Referral urgency changes cannot be deleted.")
