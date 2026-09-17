"""Transactional Shared Summary workflows with strict Counseling resource boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import COUNSELING_SHARED_SUMMARY_PUBLISHED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import CounselingEncounter, CounselingSharedSummary
from .services import DEFAULT_PAGE_SIZE, CounselingError, _validate_page


class CounselingSharedSummaryNotFound(CounselingError):
    pass


class CounselingSharedSummaryAlreadyPublished(CounselingError):
    pass


class CounselingSharedSummaryEmpty(CounselingError):
    pass


@dataclass(frozen=True, slots=True)
class CounselingSharedSummaryPage:
    items: tuple[CounselingSharedSummary, ...]
    page: int
    page_size: int
    has_next: bool


def _summary_queryset():
    return CounselingSharedSummary.objects.select_related(
        "encounter",
        "encounter__student",
        "encounter__student__role",
        "encounter__counselor",
        "encounter__counselor__role",
    )


def _validate_counselor(counselor: User) -> None:
    if not counselor.is_active or counselor.role.code != "COUNSELOR":
        raise CounselingSharedSummaryNotFound(
            "The requested Counseling Shared Summary was not found."
        )


def _validate_student(student: User) -> None:
    if not student.is_active or student.role.code != "STUDENT":
        raise CounselingSharedSummaryNotFound(
            "The requested Counseling Shared Summary was not found."
        )


def _lock_assigned_encounter(*, encounter_id: UUID, counselor: User) -> CounselingEncounter:
    _validate_counselor(counselor)
    encounter = (
        CounselingEncounter.objects.select_for_update()
        .filter(pk=encounter_id, counselor_id=counselor.pk)
        .first()
    )
    if encounter is None:
        raise CounselingSharedSummaryNotFound(
            "The requested Counseling Shared Summary was not found."
        )
    return encounter


def get_assigned_shared_summary(*, encounter_id: UUID, counselor: User) -> CounselingSharedSummary:
    _validate_counselor(counselor)
    item = (
        _summary_queryset()
        .filter(encounter_id=encounter_id, encounter__counselor_id=counselor.pk)
        .first()
    )
    if item is None:
        raise CounselingSharedSummaryNotFound(
            "The requested Counseling Shared Summary was not found."
        )
    return item


def put_assigned_shared_summary(
    *, encounter_id: UUID, counselor: User, content: str
) -> CounselingSharedSummary:
    if not isinstance(content, str):
        raise TypeError("content must be a string")

    with transaction.atomic():
        encounter = _lock_assigned_encounter(encounter_id=encounter_id, counselor=counselor)
        item = (
            CounselingSharedSummary.objects.select_for_update()
            .filter(encounter_id=encounter.pk)
            .first()
        )
        if item is None:
            item = CounselingSharedSummary.objects.create(encounter=encounter, content=content)
        else:
            if item.published_at is not None:
                raise CounselingSharedSummaryAlreadyPublished(
                    "A published Counseling Shared Summary is locked from ordinary editing."
                )
            item.content = content
            item.save(update_fields=["content", "updated_at"])
        return _summary_queryset().get(pk=item.pk)


def publish_assigned_shared_summary(
    *, encounter_id: UUID, counselor: User, context: AuditContext
) -> CounselingSharedSummary:
    with transaction.atomic():
        encounter = _lock_assigned_encounter(encounter_id=encounter_id, counselor=counselor)
        item = (
            CounselingSharedSummary.objects.select_for_update()
            .filter(encounter_id=encounter.pk)
            .first()
        )
        if item is None:
            raise CounselingSharedSummaryNotFound(
                "The requested Counseling Shared Summary was not found."
            )
        if item.published_at is not None:
            return _summary_queryset().get(pk=item.pk)
        if not item.content.strip():
            raise CounselingSharedSummaryEmpty(
                "Counseling Shared Summary content must not be empty when published."
            )

        item.published_at = timezone.now()
        item.save(update_fields=["published_at", "updated_at"])
        record_event(
            context=context,
            action=COUNSELING_SHARED_SUMMARY_PUBLISHED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.sharedsummary",
            target_id=item.pk,
            metadata={"counseling_encounter_id": str(encounter.pk)},
        )
        return _summary_queryset().get(pk=item.pk)


def list_my_shared_summaries(
    *,
    student: User,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CounselingSharedSummaryPage:
    _validate_student(student)
    page, page_size = _validate_page(page, page_size)
    queryset = _summary_queryset().filter(
        encounter__student_id=student.pk,
        published_at__isnull=False,
    )
    offset = (page - 1) * page_size
    rows = list(queryset.order_by("-published_at", "id")[offset : offset + page_size + 1])
    return CounselingSharedSummaryPage(
        items=tuple(rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )


def get_my_shared_summary(*, student: User, summary_id: UUID) -> CounselingSharedSummary:
    _validate_student(student)
    item = (
        _summary_queryset()
        .filter(
            pk=summary_id,
            encounter__student_id=student.pk,
            published_at__isnull=False,
        )
        .first()
    )
    if item is None:
        raise CounselingSharedSummaryNotFound(
            "The requested Counseling Shared Summary was not found."
        )
    return item
