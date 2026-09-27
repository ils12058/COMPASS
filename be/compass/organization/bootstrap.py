"""Explicit synchronization of the code-owned UCN organization catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from compass.audit.actions import ORGANIZATION_CATALOG_SYNCED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.canonical import CANONICAL_CAMPUSES
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)


class CanonicalOrganizationSyncError(RuntimeError):
    """Persisted Organization state cannot be safely reconciled automatically."""


@dataclass(frozen=True, slots=True)
class CanonicalOrganizationSyncResult:
    campuses_created: int = 0
    campuses_updated: int = 0
    campuses_deactivated: int = 0
    colleges_created: int = 0
    colleges_updated: int = 0
    colleges_deactivated: int = 0
    programs_created: int = 0
    programs_updated: int = 0
    programs_deactivated: int = 0

    @property
    def changed(self) -> bool:
        return any(asdict(self).values())

    def metadata(self) -> dict[str, int]:
        return asdict(self)


def _get_or_create_campus(*, code: str, name: str) -> tuple[Campus, bool]:
    campus = Campus.objects.select_for_update().filter(code=code).first()
    if campus is not None:
        return campus, False
    try:
        with transaction.atomic():
            return Campus.objects.create(code=code, name=name), True
    except IntegrityError:
        return Campus.objects.select_for_update().get(code=code), False


def _get_or_create_college(*, campus: Campus, code: str, name: str) -> tuple[College, bool]:
    college = College.objects.select_for_update().filter(campus=campus, code=code).first()
    if college is not None:
        return college, False
    try:
        with transaction.atomic():
            return College.objects.create(campus=campus, code=code, name=name), True
    except IntegrityError:
        return College.objects.select_for_update().get(campus=campus, code=code), False


def _get_or_create_program(*, college: College, code: str, name: str) -> tuple[Program, bool]:
    program = Program.objects.select_for_update().filter(college=college, code=code).first()
    if program is not None:
        return program, False
    try:
        with transaction.atomic():
            return Program.objects.create(college=college, code=code, name=name), True
    except IntegrityError:
        return Program.objects.select_for_update().get(college=college, code=code), False


def _repair_row(row, *, name: str, active: bool) -> bool:
    changed: list[str] = []
    if row.name != name:
        row.name = name
        changed.append("name")
    if row.is_active != active:
        row.is_active = active
        changed.append("is_active")
    if not changed:
        return False
    row.save(update_fields=[*changed, "updated_at"])
    return True


def _sync_organization_catalog() -> CanonicalOrganizationSyncResult:
    counts = {
        "campuses_created": 0,
        "campuses_updated": 0,
        "campuses_deactivated": 0,
        "colleges_created": 0,
        "colleges_updated": 0,
        "colleges_deactivated": 0,
        "programs_created": 0,
        "programs_updated": 0,
        "programs_deactivated": 0,
    }
    canonical_campus_ids: set[UUID] = set()
    canonical_college_ids: set[UUID] = set()
    canonical_program_ids: set[UUID] = set()

    for campus_definition in CANONICAL_CAMPUSES:
        campus, created = _get_or_create_campus(
            code=campus_definition.code,
            name=campus_definition.name,
        )
        canonical_campus_ids.add(campus.pk)
        if created:
            counts["campuses_created"] += 1
        elif _repair_row(
            campus,
            name=campus_definition.name,
            active=campus_definition.active,
        ):
            counts["campuses_updated"] += 1

        for college_definition in campus_definition.colleges:
            college, college_created = _get_or_create_college(
                campus=campus,
                code=college_definition.code,
                name=college_definition.name,
            )
            canonical_college_ids.add(college.pk)
            if college_created:
                counts["colleges_created"] += 1
            elif _repair_row(
                college,
                name=college_definition.name,
                active=college_definition.active,
            ):
                counts["colleges_updated"] += 1

            for program_definition in college_definition.programs:
                program, program_created = _get_or_create_program(
                    college=college,
                    code=program_definition.code,
                    name=program_definition.name,
                )
                canonical_program_ids.add(program.pk)
                if program_created:
                    counts["programs_created"] += 1
                elif _repair_row(
                    program,
                    name=program_definition.name,
                    active=program_definition.active,
                ):
                    counts["programs_updated"] += 1

    # Programs are safe to retire from new selection without rewriting historical
    # StudentInventory foreign keys.
    legacy_programs = tuple(
        Program.objects.select_for_update(of=("self",))
        .select_related("college__campus")
        .filter(is_active=True)
        .exclude(pk__in=canonical_program_ids)
        .order_by("college__campus__code", "college__code", "code")
    )
    for program in legacy_programs:
        program.is_active = False
        program.save(update_fields=["is_active", "updated_at"])
        counts["programs_deactivated"] += 1

    # Colleges carry live GCO routing. Unknown active rows are only retired when
    # doing so cannot invalidate an existing affiliation or responsibility.
    legacy_colleges = tuple(
        College.objects.select_for_update(of=("self",))
        .select_related("campus")
        .filter(is_active=True)
        .exclude(pk__in=canonical_college_ids)
        .order_by("campus__code", "code")
    )
    for college in legacy_colleges:
        has_affiliations = StudentAffiliation.objects.filter(college=college).exists()
        has_responsibility = CounselorResponsibility.objects.filter(college=college).exists()
        if has_affiliations or has_responsibility:
            raise CanonicalOrganizationSyncError(
                "Cannot deactivate noncanonical College "
                f"{college.campus.code}/{college.code} ({college.pk}) while it has "
                "current Student affiliation or Counselor responsibility relationships. "
                "Reconcile those operational relationships explicitly before retrying."
            )
        if Program.objects.filter(college=college, is_active=True).exists():
            raise CanonicalOrganizationSyncError(
                "Cannot deactivate noncanonical College "
                f"{college.campus.code}/{college.code} ({college.pk}) while it still "
                "contains active Programs."
            )
        college.is_active = False
        college.save(update_fields=["is_active", "updated_at"])
        counts["colleges_deactivated"] += 1

    legacy_campuses = tuple(
        Campus.objects.select_for_update()
        .filter(is_active=True)
        .exclude(pk__in=canonical_campus_ids)
        .order_by("code")
    )
    for campus in legacy_campuses:
        if College.objects.filter(campus=campus, is_active=True).exists():
            raise CanonicalOrganizationSyncError(
                "Cannot deactivate noncanonical Campus "
                f"{campus.code} ({campus.pk}) while it still contains active Colleges. "
                "Reconcile those Colleges and their operational relationships explicitly "
                "before retrying."
            )
        campus.is_active = False
        campus.save(update_fields=["is_active", "updated_at"])
        counts["campuses_deactivated"] += 1

    result = CanonicalOrganizationSyncResult(**counts)
    if result.changed:
        record_event(
            context=AuditContext.system(),
            action=ORGANIZATION_CATALOG_SYNCED,
            outcome=AuditOutcome.SUCCESS,
            metadata=result.metadata(),
        )
    return result


def sync_organization_catalog() -> CanonicalOrganizationSyncResult:
    """Reconcile the canonical UCN catalog while preserving historical identities."""

    try:
        with transaction.atomic():
            return _sync_organization_catalog()
    except CanonicalOrganizationSyncError:
        raise
    except (Campus.DoesNotExist, College.DoesNotExist, Program.DoesNotExist, IntegrityError) as exc:
        raise CanonicalOrganizationSyncError(
            "Canonical Organization catalog could not be synchronized safely. "
            "Inspect existing Campus, College, and Program identities before retrying."
        ) from exc
