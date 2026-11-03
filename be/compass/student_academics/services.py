"""The only runtime writer of StudentAcademicProfile; affiliation remains authoritative."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q

from compass.accounts.models import User
from compass.organization.models import College, StudentAffiliation
from compass.student_academics.models import (
    PlacementVerificationStatus,
    StudentAcademicProfile,
)


def sync_enabled() -> bool:
    return bool(getattr(settings, "STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED", False))


def sync_profile_from_affiliation(
    *, student: User, college: College, updated_by: User | None
) -> StudentAcademicProfile | None:
    """Mirror one affiliation write; returns None when the gate is off."""
    if not sync_enabled():
        return None
    profile, _ = StudentAcademicProfile.objects.update_or_create(
        student=student,
        defaults={
            "current_college": college,
            "current_program": None,
            "placement_verification_status": PlacementVerificationStatus.UNVERIFIED,
            "placement_effective_at": None,
            "updated_by": updated_by,
        },
    )
    return profile


def clear_profile_for_removed_affiliation(*, student_id: UUID, updated_by: User | None) -> bool:
    """Preserve the profile row and record that no current placement is known."""
    if not sync_enabled():
        return False
    profile = (
        StudentAcademicProfile.objects.select_for_update().filter(student_id=student_id).first()
    )
    if profile is None:
        return False
    profile.current_college = None
    profile.current_program = None
    profile.placement_verification_status = PlacementVerificationStatus.UNVERIFIED
    profile.placement_effective_at = None
    profile.updated_by = updated_by
    profile.save(
        update_fields=[
            "current_college",
            "current_program",
            "placement_verification_status",
            "placement_effective_at",
            "updated_by",
            "updated_at",
        ]
    )
    return True


@dataclass(frozen=True, slots=True)
class BackfillReport:
    affiliations_total: int
    eligible: int
    missing_profiles: int
    existing_profiles: int
    inactive_student_accounts: int
    non_student_role_rows: int
    inactive_college_rows: int
    created: int = 0


def _student_affiliations():
    return StudentAffiliation.objects.select_related("student__role", "college__campus")


def backfill_student_academic_profiles(*, dry_run: bool, batch_size: int) -> BackfillReport:
    """Create only missing profiles for Student-role affiliations; never overwrite."""
    affiliations = _student_affiliations()
    eligible = affiliations.filter(student__role__code="STUDENT")
    affiliations_total = affiliations.count()
    eligible_total = eligible.count()
    existing_profiles = StudentAcademicProfile.objects.filter(
        student__organization_student_affiliation__isnull=False,
        student__role__code="STUDENT",
    ).count()
    report = BackfillReport(
        affiliations_total=affiliations_total,
        eligible=eligible_total,
        missing_profiles=max(eligible_total - existing_profiles, 0),
        existing_profiles=existing_profiles,
        inactive_student_accounts=eligible.filter(student__is_active=False).count(),
        non_student_role_rows=affiliations_total - eligible_total,
        inactive_college_rows=affiliations.filter(
            Q(college__is_active=False) | Q(college__campus__is_active=False)
        ).count(),
    )
    if dry_run:
        return report

    created = 0
    last_student_id: UUID | None = None
    while True:
        batch_query = eligible.order_by("student_id")
        if last_student_id is not None:
            batch_query = batch_query.filter(student_id__gt=last_student_id)
        batch = list(batch_query[:batch_size])
        if not batch:
            break
        existing_ids = set(
            StudentAcademicProfile.objects.filter(
                student_id__in=[item.student_id for item in batch]
            ).values_list("student_id", flat=True)
        )
        pending = [item for item in batch if item.student_id not in existing_ids]
        if pending:
            with transaction.atomic():
                StudentAcademicProfile.objects.bulk_create(
                    [
                        StudentAcademicProfile(
                            student_id=item.student_id,
                            current_college_id=item.college_id,
                            current_program=None,
                            placement_verification_status=(PlacementVerificationStatus.UNVERIFIED),
                            placement_effective_at=None,
                            updated_by_id=item.assigned_by_id,
                        )
                        for item in pending
                    ],
                    ignore_conflicts=True,
                )
            created += len(pending)
        last_student_id = batch[-1].student_id

    return BackfillReport(
        affiliations_total=report.affiliations_total,
        eligible=report.eligible,
        missing_profiles=report.missing_profiles,
        existing_profiles=report.existing_profiles,
        inactive_student_accounts=report.inactive_student_accounts,
        non_student_role_rows=report.non_student_role_rows,
        inactive_college_rows=report.inactive_college_rows,
        created=created,
    )


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    affiliations_without_profile: int
    profile_college_drift: int
    profile_program_present: int
    profile_effective_at_present: int
    profile_verified: int
    profiles_without_affiliation: int
    non_student_profiles: int
    inactive_student_profiles: int

    @property
    def blocking_total(self) -> int:
        return (
            self.affiliations_without_profile
            + self.profile_college_drift
            + self.profile_program_present
            + self.profile_effective_at_present
            + self.profile_verified
            + self.profiles_without_affiliation
        )


def reconcile_student_academic_profiles() -> ReconciliationReport:
    profiles = StudentAcademicProfile.objects.all()
    profiles_with_affiliation = profiles.filter(
        student__organization_student_affiliation__isnull=False
    )
    return ReconciliationReport(
        affiliations_without_profile=StudentAffiliation.objects.filter(
            student__role__code="STUDENT",
            student__student_academic_profile__isnull=True,
        ).count(),
        profile_college_drift=profiles_with_affiliation.filter(
            Q(current_college__isnull=True)
            | ~Q(current_college_id=F("student__organization_student_affiliation__college_id"))
        ).count(),
        profile_program_present=profiles.filter(current_program__isnull=False).count(),
        profile_effective_at_present=profiles.filter(placement_effective_at__isnull=False).count(),
        profile_verified=profiles.filter(
            placement_verification_status=PlacementVerificationStatus.VERIFIED
        ).count(),
        profiles_without_affiliation=profiles.filter(
            student__organization_student_affiliation__isnull=True
        ).count(),
        non_student_profiles=profiles.exclude(student__role__code="STUDENT").count(),
        inactive_student_profiles=profiles.filter(
            student__role__code="STUDENT", student__is_active=False
        ).count(),
    )
