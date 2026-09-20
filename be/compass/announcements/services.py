"""Transactional GCO Announcement use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    ANNOUNCEMENT_ARCHIVED,
    ANNOUNCEMENT_CREATED,
    ANNOUNCEMENT_PUBLISHED,
    ANNOUNCEMENT_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.publications import PublicationAudience, PublicationStatus, eligible_audiences_for

from .models import Announcement

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_TITLE_LENGTH = 200
MAX_BODY_BYTES = 50 * 1024


class AnnouncementError(RuntimeError):
    pass


class AnnouncementNotFound(AnnouncementError):
    pass


class AnnouncementConflict(AnnouncementError):
    pass


class InvalidAnnouncementInput(AnnouncementError):
    pass


@dataclass(frozen=True, slots=True)
class AnnouncementPage:
    items: tuple[Announcement, ...]
    page: int
    page_size: int
    has_next: bool


def _clean_title(value: str, *, require_nonblank: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidAnnouncementInput("title must be a string")
    normalized = value.strip()
    if require_nonblank and not normalized:
        raise InvalidAnnouncementInput("title is required before publication")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise InvalidAnnouncementInput("title is too long")
    return normalized


def _clean_body(value: str, *, require_nonblank: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidAnnouncementInput("body_markdown must be a string")
    if require_nonblank and not value.strip():
        raise InvalidAnnouncementInput("body_markdown is required before publication")
    if len(value.encode("utf-8")) > MAX_BODY_BYTES:
        raise InvalidAnnouncementInput("body_markdown is too large")
    return value


def _clean_audience(value: str | PublicationAudience) -> str:
    normalized = value.value if isinstance(value, PublicationAudience) else value
    if normalized not in PublicationAudience.values:
        raise InvalidAnnouncementInput("audience is invalid")
    return normalized


def _clean_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidAnnouncementInput("expires_at must be a timezone-aware datetime or null")
    return value


def _clean_page(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidAnnouncementInput("page must be at least 1")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidAnnouncementInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _page(queryset, *, page: int, page_size: int) -> AnnouncementPage:
    page, page_size = _clean_page(page, page_size)
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return AnnouncementPage(
        items=tuple(rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )


def _visible_queryset(actor: User, *, now: datetime | None = None):
    audiences = eligible_audiences_for(actor)
    if not audiences:
        return Announcement.objects.none()
    current = now or timezone.now()
    return Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
        published_at__lte=current,
        audience__in=audiences,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=current))


def list_visible_announcements(
    *,
    actor: User,
    pinned: bool | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> AnnouncementPage:
    queryset = _visible_queryset(actor, now=now)
    if pinned is not None:
        queryset = queryset.filter(is_pinned=bool(pinned))
    queryset = queryset.order_by("-is_pinned", "-published_at", "-id")
    return _page(queryset, page=page, page_size=page_size)


def get_visible_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    now: datetime | None = None,
) -> Announcement:
    item = _visible_queryset(actor, now=now).filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("The requested Announcement was not found.")
    return item


def list_managed_announcements(
    *,
    status: str | None = None,
    audience: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AnnouncementPage:
    queryset = Announcement.objects.select_related(
        "created_by", "updated_by", "published_by"
    ).all()
    if status is not None:
        if status not in PublicationStatus.values:
            raise InvalidAnnouncementInput("status is invalid")
        queryset = queryset.filter(status=status)
    if audience is not None:
        queryset = queryset.filter(audience=_clean_audience(audience))
    return _page(
        queryset.order_by("-updated_at", "-id"),
        page=page,
        page_size=page_size,
    )


def get_managed_announcement(*, announcement_id: UUID) -> Announcement:
    item = (
        Announcement.objects.select_related("created_by", "updated_by", "published_by")
        .filter(pk=announcement_id)
        .first()
    )
    if item is None:
        raise AnnouncementNotFound("The requested Announcement was not found.")
    return item


@transaction.atomic
def create_announcement(
    *,
    actor: User,
    title: str,
    body_markdown: str,
    audience: str,
    is_pinned: bool,
    expires_at: datetime | None,
    context: AuditContext,
) -> Announcement:
    if type(is_pinned) is not bool:
        raise InvalidAnnouncementInput("is_pinned must be a boolean")
    item = Announcement.objects.create(
        title=_clean_title(title),
        body_markdown=_clean_body(body_markdown),
        audience=_clean_audience(audience),
        is_pinned=is_pinned,
        expires_at=_clean_expiry(expires_at),
        created_by=actor,
        updated_by=actor,
    )
    record_event(
        context=context,
        action=ANNOUNCEMENT_CREATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "status": item.status,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
        },
    )
    return item


@transaction.atomic
def update_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    values: dict[str, object],
    context: AuditContext,
) -> Announcement:
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("The requested Announcement was not found.")
    if item.status == PublicationStatus.ARCHIVED:
        raise AnnouncementConflict("Archived Announcements cannot be edited.")

    allowed = {"title", "body_markdown", "audience", "is_pinned", "expires_at"}
    unknown = set(values) - allowed
    if unknown:
        raise InvalidAnnouncementInput(f"unsupported Announcement fields: {sorted(unknown)}")

    if "title" in values:
        item.title = _clean_title(values["title"])  # type: ignore[arg-type]
    if "body_markdown" in values:
        item.body_markdown = _clean_body(values["body_markdown"])  # type: ignore[arg-type]
    if "audience" in values:
        item.audience = _clean_audience(values["audience"])  # type: ignore[arg-type]
    if "is_pinned" in values:
        if type(values["is_pinned"]) is not bool:
            raise InvalidAnnouncementInput("is_pinned must be a boolean")
        item.is_pinned = values["is_pinned"]  # type: ignore[assignment]
    if "expires_at" in values:
        item.expires_at = _clean_expiry(values["expires_at"])  # type: ignore[arg-type]

    item.updated_by = actor
    item.save()
    record_event(
        context=context,
        action=ANNOUNCEMENT_UPDATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "status": item.status,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
        },
    )
    return item


@transaction.atomic
def publish_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> Announcement:
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("The requested Announcement was not found.")
    if item.status != PublicationStatus.DRAFT:
        raise AnnouncementConflict("Only a draft Announcement can be published.")

    current = now or timezone.now()
    item.title = _clean_title(item.title, require_nonblank=True)
    item.body_markdown = _clean_body(item.body_markdown, require_nonblank=True)
    item.audience = _clean_audience(item.audience)
    if item.expires_at is not None and item.expires_at <= current:
        raise InvalidAnnouncementInput("expires_at must be in the future at publication")

    item.status = PublicationStatus.PUBLISHED
    item.published_at = current
    item.published_by = actor
    item.updated_by = actor
    item.save()
    record_event(
        context=context,
        action=ANNOUNCEMENT_PUBLISHED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "from_status": PublicationStatus.DRAFT,
            "to_status": PublicationStatus.PUBLISHED,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
        },
    )
    return item


@transaction.atomic
def archive_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    context: AuditContext,
) -> Announcement:
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("The requested Announcement was not found.")
    if item.status == PublicationStatus.ARCHIVED:
        raise AnnouncementConflict("The Announcement is already archived.")

    previous = item.status
    item.status = PublicationStatus.ARCHIVED
    item.updated_by = actor
    item.save(update_fields=["status", "updated_by", "updated_at"])
    record_event(
        context=context,
        action=ANNOUNCEMENT_ARCHIVED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "from_status": previous,
            "to_status": PublicationStatus.ARCHIVED,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
        },
    )
    return item


__all__ = [
    "AnnouncementConflict",
    "AnnouncementError",
    "AnnouncementNotFound",
    "AnnouncementPage",
    "DEFAULT_PAGE_SIZE",
    "InvalidAnnouncementInput",
    "MAX_PAGE_SIZE",
    "archive_announcement",
    "create_announcement",
    "get_managed_announcement",
    "get_visible_announcement",
    "list_managed_announcements",
    "list_visible_announcements",
    "publish_announcement",
    "update_announcement",
]
