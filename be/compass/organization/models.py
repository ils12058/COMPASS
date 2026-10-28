"""Explicit organizational structure and responsibility relationships for COMPASS."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from compass.organization.program_policy import (
    AcademicClassification,
    YearLevelPolicyStatus,
    validate_program_policy,
)


def normalize_code(value: str) -> str:
    return value.strip().upper()


class AcademicYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=32, unique=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-label",)
        constraints = [
            models.UniqueConstraint(
                fields=("is_current",),
                condition=models.Q(is_current=True),
                name="organization_one_current_academic_year",
            ),
        ]

    def save(self, *args, **kwargs):
        self.label = self.label.strip()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.label


class Campus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    resource_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resource_version__gte=1),
                name="organization_campus_version_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = normalize_code(self.code)
        self.name = self.name.strip()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.code


class College(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name="colleges")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    resource_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("campus__code", "code")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resource_version__gte=1),
                name="organization_college_version_positive",
            ),
            models.UniqueConstraint(
                fields=("campus", "code"), name="organization_college_code_uniq"
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = normalize_code(self.code)
        self.name = self.name.strip()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.campus.code}/{self.code}"


class Program(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.PROTECT, related_name="programs")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    resource_version = models.PositiveIntegerField(default=1)
    academic_classification = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        choices=[(value.value, value.value) for value in AcademicClassification],
    )
    year_level_policy_status = models.CharField(
        max_length=16,
        default=YearLevelPolicyStatus.PENDING_POLICY.value,
        choices=[(value.value, value.value) for value in YearLevelPolicyStatus],
    )
    applicable_year_levels = ArrayField(models.SmallIntegerField(), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("college__campus__code", "college__code", "code")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resource_version__gte=1),
                name="organization_program_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(academic_classification__isnull=True)
                | models.Q(academic_classification__in=[v.value for v in AcademicClassification]),
                name="organization_program_classification_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    year_level_policy_status__in=[v.value for v in YearLevelPolicyStatus]
                ),
                name="organization_program_policy_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        year_level_policy_status="PENDING_POLICY",
                        applicable_year_levels__isnull=True,
                    )
                    | (
                        models.Q(
                            year_level_policy_status="CONFIGURED",
                            academic_classification__isnull=False,
                            applicable_year_levels__isnull=False,
                        )
                        & models.Func(
                            models.F("applicable_year_levels"),
                            function="organization_valid_year_levels_v1",
                            output_field=models.BooleanField(),
                        )
                    )
                ),
                name="organization_program_policy_consistent",
            ),
            models.UniqueConstraint(
                fields=("college", "code"),
                name="organization_program_code_uniq",
            ),
        ]

    def clean_fields(self, exclude=None):
        # ArrayField/SmallIntegerField otherwise coerce True and 1.5 into integer 1.
        validate_program_policy(
            self.academic_classification, self.year_level_policy_status, self.applicable_year_levels
        )
        return super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        validate_program_policy(
            self.academic_classification, self.year_level_policy_status, self.applicable_year_levels
        )

    def save(self, *args, **kwargs):
        self.code = normalize_code(self.code)
        self.name = self.name.strip()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.college}/{self.code}"


class StudentAffiliation(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_student_affiliation",
        primary_key=True,
    )
    college = models.ForeignKey(
        College, on_delete=models.PROTECT, related_name="student_affiliations"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_student_affiliations",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class CounselorResponsibility(models.Model):
    college = models.OneToOneField(
        College,
        on_delete=models.PROTECT,
        related_name="counselor_responsibility",
        primary_key=True,
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_counselor_responsibilities",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_counselor_responsibilities",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class StaffSupervision(models.Model):
    staff = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_staff_supervision",
        primary_key=True,
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_supervised_staff",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_staff_supervisions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class CatalogInitializationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError("Catalog initialization receipts are immutable.")

    def delete(self):
        raise TypeError(
            "Catalog initialization receipts cannot be removed by application operations."
        )


class CatalogInitialization(models.Model):
    """Installation/adoption receipt, never an authority-mode switch or old-writer fence."""

    class Source(models.TextChoices):
        SEEDED = "SEEDED", "Seeded"
        ADOPTED = "ADOPTED", "Adopted"

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    source = models.CharField(max_length=8, choices=Source.choices)
    initialized_at = models.DateTimeField(default=timezone.now, editable=False)
    baseline_version = models.CharField(max_length=32, null=True, blank=True)
    reference = models.CharField(max_length=160, blank=True, default="")
    objects = CatalogInitializationQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="organization_catalog_singleton"),
            models.CheckConstraint(
                condition=(
                    models.Q(source="SEEDED", baseline_version__isnull=False)
                    & ~models.Q(baseline_version="")
                )
                | models.Q(source="ADOPTED", baseline_version__isnull=True),
                name="organization_catalog_receipt_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("Catalog initialization receipts are immutable.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError(
            "Catalog initialization receipts cannot be removed by application operations."
        )
