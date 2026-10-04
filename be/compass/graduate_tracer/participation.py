"""Completion tombstone without a response identifier or an anonymous-record lookup."""

from django.conf import settings
from django.db import models


class GraduateTracerDisposedParticipation(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    instrument_schema_version = models.PositiveSmallIntegerField()
    disposed_on = models.DateField()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("student", "instrument_schema_version"),
                name="tracer_disposed_participation_uniq",
            )
        ]
