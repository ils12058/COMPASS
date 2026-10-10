"""Longitudinal institutional facts; confidential results have no plaintext columns."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class AssessmentType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="assessment_type_name_unique"),
            models.CheckConstraint(
                condition=~models.Q(name=""), name="assessment_type_name_nonblank"
            ),
        ]


class StudentAssessmentRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessment_records"
    )
    assessment_type = models.ForeignKey(
        AssessmentType, on_delete=models.PROTECT, related_name="records"
    )
    administered_on = models.DateField()
    confidential_content_ciphertext = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_assessment_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-administered_on", "id")
        indexes = [
            models.Index(fields=("student", "-administered_on")),
            models.Index(fields=("assessment_type", "-administered_on")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(confidential_content_ciphertext=""),
                name="assessment_record_ciphertext_nonblank",
            )
        ]
