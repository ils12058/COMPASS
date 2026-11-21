"""Transactional GCO Announcement use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    ANNOUNCEMENT_ARCHIVED,
    ANNOUNCEMENT_CREATED,
    ANNOUNCEMENT_PUBLISHED,
    ANNOUNCEMENT_RETURNED,
    ANNOUNCEMENT_SUBMITTED_FOR_APPROVAL,
    ANNOUNCEMENT_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.ordering import parse_ordering
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.models import StaffSupervision
from compass.publications import (
    ALL_PUBLICATION_STATUSES,
    PENDING_APPROVAL_STATUS,
    PublicationAudience,
    PublicationStatus,
    eligible_audiences_for,
)

from .models import Announcement
from .validation import ISSUES, issue_details

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_TITLE_LENGTH = 200
MAX_BODY_BYTES = 50 * 1024


class AnnouncementError(RuntimeError):
    pass


class AnnouncementNotFound(AnnouncementError):
    pass


class AnnouncementNotPermitted(AnnouncementError):
    pass


class AnnouncementConflict(AnnouncementError):
    def __init__(self, identifier: str) -> None:
        super().__init__(ISSUES[identifier][1])
        self.details = issue_details(identifier)


class AnnouncementPublicationConsequenceReviewRequired(AnnouncementConflict):
    def __init__(self, fields: tuple[str, ...]) -> None:
        AnnouncementError.__init__(
            self, "Review how these changes affect the published Announcement before saving."
        )
        self.fields = fields


class InvalidAnnouncementInput(AnnouncementError):
    def __init__(self, identifier: str) -> None:
        super().__init__(ISSUES[identifier][1])
        self.details = issue_details(identifier)


class AnnouncementOrderingInputError(InvalidAnnouncementInput):
    def __init__(self, message: str) -> None:
        super().__init__("ordering_invalid")


class AnnouncementOrdering(StrEnum):
    """Closed reader orderings (ADR-090).

    RECOMMENDED is the editorial order: pinned first, then the newest published. The other values
    let a reader browse the full index in another order; Overview always uses RECOMMENDED.
    """

    RECOMMENDED = "RECOMMENDED"
    NEWEST = "NEWEST"
    OLDEST = "OLDEST"
    TITLE_ASC = "TITLE_ASC"
    TITLE_DESC = "TITLE_DESC"


class AnnouncementManagementOrdering(StrEnum):
    """Closed orderings for Announcement management (ADR-090); recent edits come first."""

    RECENTLY_UPDATED = "RECENTLY_UPDATED"
    OLDEST_UPDATED = "OLDEST_UPDATED"
    NEWEST_PUBLISHED = "NEWEST_PUBLISHED"
    OLDEST_PUBLISHED = "OLDEST_PUBLISHED"
    TITLE_ASC = "TITLE_ASC"
    TITLE_DESC = "TITLE_DESC"


_READER_ORDER_BY: dict[AnnouncementOrdering, tuple] = {
    AnnouncementOrdering.RECOMMENDED: ("-is_pinned", "-published_at", "-id"),
    AnnouncementOrdering.NEWEST: ("-published_at", "-id"),
    AnnouncementOrdering.OLDEST: ("published_at", "id"),
    AnnouncementOrdering.TITLE_ASC: (Lower("title"), "-published_at", "id"),
    AnnouncementOrdering.TITLE_DESC: (Lower("title").desc(), "-published_at", "-id"),
}

_MANAGEMENT_ORDER_BY: dict[AnnouncementManagementOrdering, tuple] = {
    AnnouncementManagementOrdering.RECENTLY_UPDATED: ("-updated_at", "-id"),
    AnnouncementManagementOrdering.OLDEST_UPDATED: ("updated_at", "id"),
    # Drafts have no publication time and follow the published Announcements.
    AnnouncementManagementOrdering.NEWEST_PUBLISHED: (
        F("published_at").desc(nulls_last=True),
        "-updated_at",
        "-id",
    ),
    AnnouncementManagementOrdering.OLDEST_PUBLISHED: (
        F("published_at").asc(nulls_last=True),
        "updated_at",
        "id",
    ),
    AnnouncementManagementOrdering.TITLE_ASC: (Lower("title"), "-updated_at", "id"),
    AnnouncementManagementOrdering.TITLE_DESC: (Lower("title").desc(), "-updated_at", "-id"),
}


def _reader_ordering(value: str | AnnouncementOrdering | None) -> AnnouncementOrdering:
    return parse_ordering(
        value,
        AnnouncementOrdering,
        default=AnnouncementOrdering.RECOMMENDED,
        error=AnnouncementOrderingInputError,
    )


@dataclass(frozen=True, slots=True)
class AnnouncementPage:
    items: tuple[Announcement, ...]
    page: int
    page_size: int
    has_next: bool
    ordering: AnnouncementOrdering | AnnouncementManagementOrdering | None = None


def _clean_title(value: str, *, require_nonblank: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidAnnouncementInput("title_text_required")
    normalized = value.strip()
    if require_nonblank and not normalized:
        raise InvalidAnnouncementInput("title_required")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise InvalidAnnouncementInput("title_too_long")
    return normalized


def _clean_body(value: str, *, require_nonblank: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidAnnouncementInput("body_text_required")
    if require_nonblank and not value.strip():
        raise InvalidAnnouncementInput("body_required")
    if len(value.encode("utf-8")) > MAX_BODY_BYTES:
        raise InvalidAnnouncementInput("body_too_large")
    return value


def _clean_audience(value: str | PublicationAudience) -> str:
    normalized = value.value if isinstance(value, PublicationAudience) else value
    if normalized not in PublicationAudience.values:
        raise InvalidAnnouncementInput("audience_invalid")
    return normalized


def _clean_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidAnnouncementInput("expiry_invalid")
    return value


def _validate_published_announcement_state(
    item: Announcement,
    *,
    now: datetime,
) -> None:
    item.title = _clean_title(item.title, require_nonblank=True)
    item.body_markdown = _clean_body(item.body_markdown, require_nonblank=True)
    item.audience = _clean_audience(item.audience)
    item.expires_at = _clean_expiry(item.expires_at)
    if item.expires_at is not None and item.expires_at <= now:
        raise InvalidAnnouncementInput("expiry_not_future")


def _clean_page(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidAnnouncementInput("page_invalid")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidAnnouncementInput("page_size_invalid")
    return page, page_size


def _normalize_search(search: str | None) -> str:
    return search.strip() if search is not None else ""


def _apply_search(queryset, search: str | None):
    term = _normalize_search(search)
    if not term:
        return queryset
    return queryset.filter(Q(title__icontains=term) | Q(body_markdown__icontains=term))


def _page(
    queryset,
    *,
    page: int,
    page_size: int,
    ordering: AnnouncementOrdering | AnnouncementManagementOrdering | None = None,
) -> AnnouncementPage:
    page, page_size = _clean_page(page, page_size)
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return AnnouncementPage(
        items=tuple(rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
        ordering=ordering,
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


def _public_queryset(*, now: datetime | None = None):
    current = now or timezone.now()
    return Announcement.objects.filter(
        status=PublicationStatus.PUBLISHED,
        published_at__lte=current,
        audience=PublicationAudience.PUBLIC,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=current))


def list_public_announcements(
    *,
    pinned: bool | None = None,
    search: str | None = None,
    ordering: str | AnnouncementOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> AnnouncementPage:
    resolved = _reader_ordering(ordering)
    queryset = _public_queryset(now=now)
    if pinned is not None:
        queryset = queryset.filter(is_pinned=bool(pinned))
    queryset = _apply_search(queryset, search)
    return _page(
        queryset.order_by(*_READER_ORDER_BY[resolved]),
        page=page,
        page_size=page_size,
        ordering=resolved,
    )


def get_public_announcement(
    *,
    announcement_id: UUID,
    now: datetime | None = None,
) -> Announcement:
    item = _public_queryset(now=now).filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    return item


def list_visible_announcements(
    *,
    actor: User,
    pinned: bool | None = None,
    search: str | None = None,
    ordering: str | AnnouncementOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> AnnouncementPage:
    resolved = _reader_ordering(ordering)
    queryset = _visible_queryset(actor, now=now)
    if pinned is not None:
        queryset = queryset.filter(is_pinned=bool(pinned))
    queryset = _apply_search(queryset, search)
    queryset = queryset.order_by(*_READER_ORDER_BY[resolved])
    return _page(queryset, page=page, page_size=page_size, ordering=resolved)


def get_visible_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    now: datetime | None = None,
) -> Announcement:
    item = _visible_queryset(actor, now=now).filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    return item


def list_managed_announcements(
    *,
    status: str | None = None,
    audience: str | None = None,
    search: str | None = None,
    ordering: str | AnnouncementManagementOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AnnouncementPage:
    resolved = parse_ordering(
        ordering,
        AnnouncementManagementOrdering,
        default=AnnouncementManagementOrdering.RECENTLY_UPDATED,
        error=AnnouncementOrderingInputError,
    )
    queryset = Announcement.objects.select_related(
        "created_by",
        "updated_by",
        "published_by",
        "prepared_by",
        "returned_by",
    ).all()
    if status is not None:
        if status not in ALL_PUBLICATION_STATUSES:
            raise InvalidAnnouncementInput("status_invalid")
        queryset = queryset.filter(status=status)
    if audience is not None:
        queryset = queryset.filter(audience=_clean_audience(audience))
    queryset = _apply_search(queryset, search)
    return _page(
        queryset.order_by(*_MANAGEMENT_ORDER_BY[resolved]),
        page=page,
        page_size=page_size,
        ordering=resolved,
    )


def get_managed_announcement(*, announcement_id: UUID) -> Announcement:
    item = (
        Announcement.objects.select_related(
            "created_by",
            "updated_by",
            "published_by",
            "prepared_by",
            "returned_by",
        )
        .filter(pk=announcement_id)
        .first()
    )
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    return item


def _resolve_goa_supervising_counselor_locked(actor: User) -> User:
    supervision = StaffSupervision.objects.select_for_update().filter(staff_id=actor.pk).first()
    if supervision is None:
        raise AnnouncementNotPermitted(
            "Guidance Office Assistant requires a current supervising Counselor."
        )
    supervisor = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=supervision.supervisor_id)
        .first()
    )
    if supervisor is None or not supervisor.is_active or supervisor.role.code != "COUNSELOR":
        raise AnnouncementNotPermitted(
            "Guidance Office Assistant requires an active supervising Counselor."
        )
    return supervisor


def _require_supervising_counselor_for_prepared_item_locked(
    *, actor: User, prepared_by_id: UUID | None
) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or prepared_by_id is None
    ):
        raise AnnouncementNotPermitted(
            "Only the Guidance Office Assistant's supervising Counselor can decide "
            "this Announcement."
        )
    supervision = (
        StaffSupervision.objects.select_for_update()
        .filter(staff_id=prepared_by_id, supervisor_id=actor.pk)
        .first()
    )
    if supervision is None:
        raise AnnouncementNotPermitted(
            "Only the Guidance Office Assistant's current supervising Counselor can decide "
            "this Announcement."
        )


def _clean_return_note(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidAnnouncementInput("return_note_required")
    cleaned = value.strip()
    if len(cleaned) > 1000:
        raise InvalidAnnouncementInput("return_note_too_long")
    return cleaned


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
        raise InvalidAnnouncementInput("pin_invalid")
    item = Announcement.objects.create(
        title=_clean_title(title),
        body_markdown=_clean_body(body_markdown),
        audience=_clean_audience(audience),
        is_pinned=is_pinned,
        expires_at=_clean_expiry(expires_at),
        created_by=actor,
        updated_by=actor,
        prepared_by=actor,
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
    acknowledge_publication_consequences: bool = False,
    now: datetime | None = None,
) -> Announcement:
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    if item.status == PublicationStatus.ARCHIVED:
        raise AnnouncementConflict("announcement_archived")
    if actor.role.code == "GUIDANCE_OFFICE_ASSISTANT":
        if item.status == PublicationStatus.PUBLISHED:
            raise AnnouncementNotPermitted(
                "A Guidance Office Assistant cannot edit a published Announcement."
            )
        if item.status == PENDING_APPROVAL_STATUS:
            raise AnnouncementConflict("announcement_pending_approval")

    before_audience = item.audience
    before_expiry = item.expires_at

    allowed = {"title", "body_markdown", "audience", "is_pinned", "expires_at"}
    unknown = set(values) - allowed
    if unknown:
        raise InvalidAnnouncementInput("unsupported_fields")

    if "title" in values:
        item.title = _clean_title(values["title"])  # type: ignore[arg-type]
    if "body_markdown" in values:
        item.body_markdown = _clean_body(values["body_markdown"])  # type: ignore[arg-type]
    if "audience" in values:
        item.audience = _clean_audience(values["audience"])  # type: ignore[arg-type]
    if "is_pinned" in values:
        if type(values["is_pinned"]) is not bool:
            raise InvalidAnnouncementInput("pin_invalid")
        item.is_pinned = values["is_pinned"]  # type: ignore[assignment]
    if "expires_at" in values:
        item.expires_at = _clean_expiry(values["expires_at"])  # type: ignore[arg-type]

    publication_consequences: dict[str, object] = {}
    if item.status == PublicationStatus.PUBLISHED:
        consequential_fields: list[str] = []
        if item.audience != before_audience:
            consequential_fields.append("audience")
            publication_consequences["audience"] = {
                "before": before_audience,
                "after": item.audience,
            }
        if item.expires_at != before_expiry:
            consequential_fields.append("expires_at")
            publication_consequences["expires_at"] = {
                "before": before_expiry.isoformat() if before_expiry is not None else None,
                "after": item.expires_at.isoformat() if item.expires_at is not None else None,
            }
        if consequential_fields and acknowledge_publication_consequences is not True:
            raise AnnouncementPublicationConsequenceReviewRequired(tuple(consequential_fields))
        _validate_published_announcement_state(item, now=now or timezone.now())

    if actor.role.code == "GUIDANCE_OFFICE_ASSISTANT":
        item.prepared_by = actor
    item.updated_by = actor
    item.save()
    metadata: dict[str, object] = {
        "status": item.status,
        "audience": item.audience,
        "is_pinned": item.is_pinned,
    }
    if publication_consequences:
        metadata["publication_consequences"] = publication_consequences
    record_event(
        context=context,
        action=ANNOUNCEMENT_UPDATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata=metadata,
    )
    return item


@transaction.atomic
def submit_announcement_for_approval(
    *,
    actor: User,
    announcement_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> Announcement:
    if actor.role.code != "GUIDANCE_OFFICE_ASSISTANT":
        raise AnnouncementNotPermitted(
            "Counselors publish Announcements directly and do not submit them for approval."
        )
    supervisor = _resolve_goa_supervising_counselor_locked(actor)
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    if item.status != PublicationStatus.DRAFT:
        raise AnnouncementConflict("submission_requires_draft")

    current = now or timezone.now()
    _validate_published_announcement_state(item, now=current)

    item.status = PENDING_APPROVAL_STATUS
    item.prepared_by = actor
    item.submitted_for_approval_at = current
    item.return_note = None
    item.updated_by = actor
    item.save()
    record_event(
        context=context,
        action=ANNOUNCEMENT_SUBMITTED_FOR_APPROVAL,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "from_status": PublicationStatus.DRAFT,
            "to_status": PENDING_APPROVAL_STATUS,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
            "supervisor_id": str(supervisor.pk),
        },
    )
    create_notification_for_event(
        recipient=supervisor,
        event=NotificationEvent.ANNOUNCEMENT_APPROVAL_REQUESTED,
        source_type=f"announcement_approval:{current.isoformat()}",
        source_id=item.pk,
        target_type="ANNOUNCEMENT",
        target_id=item.pk,
    )
    return get_managed_announcement(announcement_id=item.pk)


@transaction.atomic
def return_announcement_draft(
    *,
    actor: User,
    announcement_id: UUID,
    note: str,
    context: AuditContext,
    now: datetime | None = None,
) -> Announcement:
    if actor.role.code != "COUNSELOR":
        raise AnnouncementNotPermitted("Only a supervising Counselor can return an Announcement.")
    cleaned_note = _clean_return_note(note)
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    if item.status != PENDING_APPROVAL_STATUS:
        raise AnnouncementConflict("return_requires_pending_approval")
    _require_supervising_counselor_for_prepared_item_locked(
        actor=actor, prepared_by_id=item.prepared_by_id or item.created_by_id
    )

    current = now or timezone.now()
    item.status = PublicationStatus.DRAFT
    item.returned_by = actor
    item.returned_at = current
    item.return_note = cleaned_note
    item.updated_by = actor
    item.save(
        update_fields=[
            "status",
            "returned_by",
            "returned_at",
            "return_note",
            "updated_by",
            "updated_at",
        ]
    )
    record_event(
        context=context,
        action=ANNOUNCEMENT_RETURNED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "from_status": PENDING_APPROVAL_STATUS,
            "to_status": PublicationStatus.DRAFT,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
        },
    )
    prepared_by = item.prepared_by or item.created_by
    if prepared_by is not None and prepared_by.is_active:
        create_notification_for_event(
            recipient=prepared_by,
            event=NotificationEvent.ANNOUNCEMENT_RETURNED,
            source_type=f"announcement_returned:{current.isoformat()}",
            source_id=item.pk,
            target_type="ANNOUNCEMENT",
            target_id=item.pk,
        )
    return get_managed_announcement(announcement_id=item.pk)


@transaction.atomic
def publish_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> Announcement:
    if actor.role.code == "GUIDANCE_OFFICE_ASSISTANT":
        raise AnnouncementNotPermitted(
            "A Guidance Office Assistant cannot publish directly. "
            "Submit this draft for your supervising Counselor's approval."
        )
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    if item.status not in {PublicationStatus.DRAFT, PENDING_APPROVAL_STATUS}:
        raise AnnouncementConflict("publication_requires_draft")
    if item.status == PENDING_APPROVAL_STATUS:
        _require_supervising_counselor_for_prepared_item_locked(
            actor=actor,
            prepared_by_id=item.prepared_by_id or item.created_by_id,
        )

    previous_status = item.status
    current = now or timezone.now()
    _validate_published_announcement_state(item, now=current)

    if item.prepared_by_id is None:
        item.prepared_by_id = item.created_by_id
    item.status = PublicationStatus.PUBLISHED
    item.published_at = current
    item.published_by = actor
    item.return_note = None
    item.updated_by = actor
    item.save()
    record_event(
        context=context,
        action=ANNOUNCEMENT_PUBLISHED,
        outcome=AuditOutcome.SUCCESS,
        target_type="announcements.announcement",
        target_id=item.pk,
        metadata={
            "from_status": previous_status,
            "to_status": PublicationStatus.PUBLISHED,
            "audience": item.audience,
            "is_pinned": item.is_pinned,
        },
    )
    return get_managed_announcement(announcement_id=item.pk)


@transaction.atomic
def archive_announcement(
    *,
    actor: User,
    announcement_id: UUID,
    context: AuditContext,
) -> Announcement:
    item = Announcement.objects.select_for_update().filter(pk=announcement_id).first()
    if item is None:
        raise AnnouncementNotFound("Couldn't find this Announcement.")
    if item.status == PublicationStatus.ARCHIVED:
        raise AnnouncementConflict("announcement_already_archived")
    if (
        actor.role.code == "GUIDANCE_OFFICE_ASSISTANT"
        and item.status == PublicationStatus.PUBLISHED
    ):
        raise AnnouncementNotPermitted(
            "A Guidance Office Assistant cannot archive a published Announcement."
        )

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


def pending_announcement_approvals(*, actor: User, limit: int) -> tuple[Announcement, ...]:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("announcements.manage")
    ):
        return ()
    supervised_staff_ids = StaffSupervision.objects.filter(
        supervisor_id=actor.pk,
        supervisor__is_active=True,
        supervisor__role__code="COUNSELOR",
    ).values("staff_id")
    return tuple(
        Announcement.objects.filter(
            status=PENDING_APPROVAL_STATUS,
            prepared_by_id__in=supervised_staff_ids,
        )
        .select_related("prepared_by")
        .only(
            "id",
            "title",
            "prepared_by_id",
            "submitted_for_approval_at",
            "updated_at",
        )
        .order_by("submitted_for_approval_at", "updated_at", "id")[:limit]
    )


__all__ = [
    "AnnouncementConflict",
    "AnnouncementError",
    "AnnouncementNotFound",
    "AnnouncementNotPermitted",
    "AnnouncementPage",
    "AnnouncementPublicationConsequenceReviewRequired",
    "DEFAULT_PAGE_SIZE",
    "InvalidAnnouncementInput",
    "MAX_PAGE_SIZE",
    "archive_announcement",
    "create_announcement",
    "get_managed_announcement",
    "get_public_announcement",
    "get_visible_announcement",
    "list_managed_announcements",
    "list_public_announcements",
    "list_visible_announcements",
    "pending_announcement_approvals",
    "publish_announcement",
    "return_announcement_draft",
    "submit_announcement_for_approval",
    "update_announcement",
]
