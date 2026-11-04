"""Canonical Student academic placement, periods, and graduation."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from compass.organization.models import College, Program


class PlacementVerificationStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    VERIFIED = "VERIFIED", "Verified"


class StudentAcademicProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_academic_profile",
    )
    current_college = models.ForeignKey(
        College,
        on_delete=models.PROTECT,
        related_name="student_academic_profiles",
        null=True,
        blank=True,
    )
    current_program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="student_academic_programs",
        null=True,
        blank=True,
    )
    placement_verification_status = models.CharField(
        max_length=16,
        choices=PlacementVerificationStatus.choices,
        default=PlacementVerificationStatus.UNVERIFIED,
    )
    placement_effective_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("student_id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    placement_verification_status__in=PlacementVerificationStatus.values
                ),
                name="student_academics_verification_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"StudentAcademicProfile({self.student_id})"


class AcademicTerm(models.TextChoices):
    FIRST_SEMESTER = "FIRST_SEMESTER", "First Semester"
    SECOND_SEMESTER = "SECOND_SEMESTER", "Second Semester"


class EnrollmentStatus(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown"
    ENROLLED = "ENROLLED", "Enrolled"
    NOT_ENROLLED = "NOT_ENROLLED", "Not enrolled"


class StudentAcademicPeriodRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="academic_period_records",
    )
    academic_year = models.ForeignKey(
        "organization.AcademicYear",
        on_delete=models.PROTECT,
        related_name="student_academic_period_records",
    )
    term = models.CharField(max_length=16, choices=AcademicTerm.choices)
    college = models.ForeignKey(
        "organization.College",
        on_delete=models.PROTECT,
        related_name="student_academic_period_records",
    )
    # Present for proposal shape, never written in this slice (D-SAR-01 remains College-only).
    program = models.ForeignKey(
        "organization.Program",
        on_delete=models.PROTECT,
        related_name="student_academic_period_records",
        null=True,
        blank=True,
    )
    year_level = models.PositiveSmallIntegerField(null=True, blank=True)
    enrollment_status = models.CharField(
        max_length=16,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.UNKNOWN,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("student_id", "-academic_year__label", "term")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "academic_year", "term"),
                name="student_academics_period_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(term__in=AcademicTerm.values),
                name="student_academics_period_term_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(enrollment_status__in=EnrollmentStatus.values),
                name="student_academics_period_enrollment_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(year_level__isnull=True) | models.Q(year_level__gte=1),
                name="student_academics_period_year_level_positive",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"StudentAcademicPeriodRecord({self.student_id}, {self.academic_year_id}, {self.term})"
        )


class StudentGraduationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="graduation_record",
    )
    graduated_college = models.ForeignKey(
        "organization.College",
        on_delete=models.PROTECT,
        related_name="student_graduation_records",
    )
    # Present for proposal shape, never written in this slice. Always null.
    graduated_program = models.ForeignKey(
        "organization.Program",
        on_delete=models.PROTECT,
        related_name="student_graduation_records",
        null=True,
        blank=True,
    )
    graduation_date = models.DateField()
    verification_source = models.CharField(max_length=200)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("student_id",)

    def __str__(self) -> str:
        return f"StudentGraduationRecord({self.student_id}, {self.graduation_date})"
