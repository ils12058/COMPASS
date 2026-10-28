"""Independent confidential professional Handoff, never Student publication."""

import uuid

from django.conf import settings
from django.db import models


class CounselorHandoffSummary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant = models.OneToOneField(
        "counseling.CounselorCaseContinuityGrant", on_delete=models.PROTECT, related_name="handoff"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="professional_handoffs"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_handoffs"
    )
    receiving_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_handoffs"
    )
    content_ciphertext = models.TextField(editable=False)
    state = models.CharField(
        max_length=16, choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted")], default="DRAFT"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(content_ciphertext=""), name="handoff_ciphertext_present"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0), name="handoff_version_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(state="DRAFT", submitted_at__isnull=True)
                    | models.Q(state="SUBMITTED", submitted_at__isnull=False)
                ),
                name="handoff_state_timestamp",
            ),
            models.CheckConstraint(
                condition=~models.Q(author=models.F("receiving_counselor")),
                name="handoff_author_not_receiver",
            ),
        ]
