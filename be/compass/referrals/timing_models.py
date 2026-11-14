"""Append-only COMPASS supplements; the official Referral Slip is unchanged."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .models import Referral, ReferralSubmissionChannel


class ReferralTimingAnswer(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown / needs confirmation"
    KNOWN = "KNOWN", "Known times"


class ReferralTimingVerificationAnswer(models.TextChoices):
    KNOWN = "KNOWN", "Confirmed times"
    NO_SUITABLE_TIME = "NO_SUITABLE_TIME", "No suitable time confirmed"


class ReferralTimingSource(models.TextChoices):
    STUDENT_CONFIRMED = "STUDENT_CONFIRMED", "Student confirmed"
    REFERRER_CONFIRMED = "REFERRER_CONFIRMED", "Referrer confirmed"
    OFFICE_RECORD = "OFFICE_RECORD", "Office record"


class _AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Referral timing records cannot be updated.")

    def delete(self):
        raise ValidationError("Referral timing records cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Referral timing records cannot be updated.")

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        if update_conflicts:
            raise ValidationError("Referral timing records cannot be updated.")
        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )


class _TimingRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    window_count = models.PositiveSmallIntegerField()
    content_ciphertext = models.TextField(editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    author_name_snapshot = models.CharField(max_length=512)
    created_at = models.DateTimeField()
    objects = _AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True
        default_permissions = ()

    def save(self, *args, **kwargs):
        if not self._state.adding or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise ValidationError("Referral timing records cannot be updated.")
        # A fresh Python instance with an existing UUID must not become an UPDATE.
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Referral timing records cannot be deleted.")


class ReferralSchedulingStatement(_TimingRecord):
    referral = models.OneToOneField(
        Referral, on_delete=models.PROTECT, related_name="scheduling_statement"
    )
    answer_kind = models.CharField(max_length=16, choices=ReferralTimingAnswer.choices)
    submission_channel = models.CharField(max_length=24, choices=ReferralSubmissionChannel.choices)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(answer_kind="UNKNOWN", window_count=0)
                | models.Q(answer_kind="KNOWN", window_count__gte=1, window_count__lte=5),
                name="referral_timing_statement_count",
            ),
            models.CheckConstraint(
                condition=models.Q(submission_channel__in=ReferralSubmissionChannel.values),
                name="referral_timing_statement_origin",
            ),
            models.CheckConstraint(
                condition=~models.Q(content_ciphertext=""), name="referral_timing_statement_cipher"
            ),
        ]


class ReferralSchedulingVerification(_TimingRecord):
    referral = models.ForeignKey(
        Referral, on_delete=models.PROTECT, related_name="scheduling_verifications"
    )
    answer_kind = models.CharField(max_length=24, choices=ReferralTimingVerificationAnswer.choices)
    confirmation_source = models.CharField(max_length=24, choices=ReferralTimingSource.choices)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("referral", "-created_at", "-id"), name="referral_timing_verify_latest"
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(answer_kind="NO_SUITABLE_TIME", window_count=0)
                | models.Q(answer_kind="KNOWN", window_count__gte=1, window_count__lte=5),
                name="referral_timing_verification_count",
            ),
            models.CheckConstraint(
                condition=models.Q(confirmation_source__in=ReferralTimingSource.values),
                name="referral_timing_verification_src",
            ),
            models.CheckConstraint(
                condition=~models.Q(content_ciphertext=""), name="referral_timing_verify_cipher"
            ),
        ]
