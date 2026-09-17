"""Operational Academic Year configuration for COMPASS."""

from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction

from compass.audit.actions import ACADEMIC_YEAR_CREATED, ACADEMIC_YEAR_CURRENT_CHANGED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.models import AcademicYear


class AcademicYearError(RuntimeError):
    pass


class AcademicYearNotFound(AcademicYearError):
    pass


class InvalidAcademicYearInput(AcademicYearError):
    pass


class AcademicYearConflict(AcademicYearError):
    pass


def normalize_academic_year_label(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidAcademicYearInput("label is required")
    label = value.strip()
    if len(label) > 32:
        raise InvalidAcademicYearInput("label is too long")
    return label


def list_academic_years() -> tuple[AcademicYear, ...]:
    return tuple(AcademicYear.objects.all().order_by("-label", "id"))


def get_current_academic_year() -> AcademicYear | None:
    return AcademicYear.objects.filter(is_current=True).first()


def require_current_academic_year() -> AcademicYear:
    current = get_current_academic_year()
    if current is None:
        raise AcademicYearConflict("No current Academic Year is configured.")
    return current


def create_academic_year(*, label: str, context: AuditContext) -> AcademicYear:
    normalized = normalize_academic_year_label(label)
    with transaction.atomic():
        try:
            item = AcademicYear.objects.create(label=normalized)
        except IntegrityError as exc:
            raise AcademicYearConflict("An Academic Year with this label already exists.") from exc
        record_event(
            context=context,
            action=ACADEMIC_YEAR_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="organization.academicyear",
            target_id=item.pk,
            metadata={"label": item.label},
        )
        return item


def set_current_academic_year(
    *, academic_year_id: UUID, context: AuditContext
) -> AcademicYear:
    with transaction.atomic():
        rows = list(AcademicYear.objects.select_for_update().order_by("id"))
        by_id = {row.pk: row for row in rows}
        target = by_id.get(academic_year_id)
        if target is None:
            raise AcademicYearNotFound("The requested Academic Year was not found.")
        current = next((row for row in rows if row.is_current), None)
        if current is not None and current.pk == target.pk:
            return target
        old_label = current.label if current is not None else None
        if current is not None:
            current.is_current = False
            current.save(update_fields=["is_current", "updated_at"])
        target.is_current = True
        try:
            target.save(update_fields=["is_current", "updated_at"])
        except IntegrityError as exc:
            raise AcademicYearConflict(
                "Another Academic Year became current concurrently; retry the operation."
            ) from exc
        record_event(
            context=context,
            action=ACADEMIC_YEAR_CURRENT_CHANGED,
            outcome=AuditOutcome.SUCCESS,
            target_type="organization.academicyear",
            target_id=target.pk,
            metadata={"old_label": old_label, "new_label": target.label},
        )
        return target
