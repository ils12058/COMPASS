"""Transactional retention and notice governance; no retention execution or consent inference."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import (
    PrivacyNotice,
    PrivacyNoticeAcknowledgment,
    PrivacyNoticeRevision,
    PrivacyNoticeRevisionStatus,
    ProcessingActivity,
    RetentionPolicy,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    PrivacyConflict,
    PrivacyConflictCode,
    PrivacyInputError,
    PrivacyRecordNotFound,
    _changed_fields,
    _clean_code,
    _clean_optional,
    _clean_required,
    _validate_model,
    _validate_page,
)

AUDIENCES = frozenset({"PUBLIC", "STUDENT", "STAFF"})
MAX_SEARCH_LENGTH = 160
RETENTION_FIELDS = {
    "name": (160, True),
    "scope_summary": (2000, True),
    "retention_trigger_summary": (2000, True),
    "retention_period_summary": (1000, True),
    "disposition_summary": (2000, True),
    "policy_reference": (255, False),
}
REVISION_FIELDS = {
    "title",
    "audiences",
    "summary",
    "body",
    "requires_acknowledgment",
    "effective_on",
}


class NoticePublishBlocker(StrEnum):
    """Server-owned reasons a notice revision cannot be published right now."""

    NOTICE_RETIRED = "NOTICE_RETIRED"
    REVISION_NOT_DRAFT = "REVISION_NOT_DRAFT"
    EFFECTIVE_DATE_MISSING = "EFFECTIVE_DATE_MISSING"
    EFFECTIVE_DATE_IN_FUTURE = "EFFECTIVE_DATE_IN_FUTURE"


@dataclass(frozen=True, slots=True)
class NoticePublishReadiness:
    ready: bool
    blocker: NoticePublishBlocker | None


def notice_publish_blocker(
    *,
    notice_active: bool,
    status: str,
    effective_on: date | None,
    today: date,
) -> NoticePublishBlocker | None:
    """Evaluate the same ordered publication rules that ``publish_revision`` enforces."""

    if not notice_active:
        return NoticePublishBlocker.NOTICE_RETIRED
    if status != PrivacyNoticeRevisionStatus.DRAFT:
        return NoticePublishBlocker.REVISION_NOT_DRAFT
    if effective_on is None:
        return NoticePublishBlocker.EFFECTIVE_DATE_MISSING
    if effective_on > today:
        return NoticePublishBlocker.EFFECTIVE_DATE_IN_FUTURE
    return None


def notice_publish_readiness(
    revision: PrivacyNoticeRevision, *, today: date | None = None
) -> NoticePublishReadiness:
    """Advisory, read-time projection; publication revalidates under row locks."""

    blocker = notice_publish_blocker(
        notice_active=revision.notice.is_active,
        status=revision.status,
        effective_on=revision.effective_on,
        today=today or timezone.localdate(),
    )
    return NoticePublishReadiness(ready=blocker is None, blocker=blocker)


_OPEN_REVISION_STATUSES = (
    PrivacyNoticeRevisionStatus.DRAFT,
    PrivacyNoticeRevisionStatus.PUBLISHED,
)


def notice_queryset():
    """Notices with their bounded draft/current revision summaries in one extra query."""

    return PrivacyNotice.objects.prefetch_related(
        Prefetch(
            "revisions",
            queryset=PrivacyNoticeRevision.objects.filter(status__in=_OPEN_REVISION_STATUSES).only(
                "id",
                "notice_id",
                "revision_number",
                "status",
                "effective_on",
                "published_at",
            ),
            to_attr="open_revisions",
        )
    )


def notice_open_revisions(
    notice: PrivacyNotice,
) -> tuple[PrivacyNoticeRevision | None, PrivacyNoticeRevision | None]:
    """Return ``(current_published, draft)`` using prefetched rows when available."""

    rows = getattr(notice, "open_revisions", None)
    if rows is None:
        rows = list(notice.revisions.filter(status__in=_OPEN_REVISION_STATUSES))
    current = next(
        (row for row in rows if row.status == PrivacyNoticeRevisionStatus.PUBLISHED), None
    )
    draft = next((row for row in rows if row.status == PrivacyNoticeRevisionStatus.DRAFT), None)
    return current, draft


def page(queryset, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE):
    page, page_size = _validate_page(page=page, page_size=page_size)
    records = list(queryset[(page - 1) * page_size : page * page_size + 1])
    return {
        "items": records[:page_size],
        "page": page,
        "page_size": page_size,
        "has_next": len(records) > page_size,
    }


def _audit(
    context: AuditContext, action: str, target_type: str, target_id: UUID, metadata: dict[str, Any]
):
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )


def _retention_values(values: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for field, value in values.items():
        if field in RETENTION_FIELDS:
            maximum, required = RETENTION_FIELDS[field]
            cleaner = _clean_required if required else _clean_optional
            cleaned[field] = cleaner(value, label=field, maximum=maximum)
        elif field in {"effective_on", "review_due_on"}:
            if value is not None and not isinstance(value, date):
                raise PrivacyInputError(f"{field} must be a date")
            cleaned[field] = value
        else:
            raise PrivacyInputError("retention policy contains unsupported fields")
    return cleaned


def get_retention(policy_id: UUID):
    item = RetentionPolicy.objects.filter(pk=policy_id).first()
    if item is None:
        raise PrivacyRecordNotFound("retention policy was not found")
    return item


def list_retention(
    *,
    is_active: bool | None = None,
    search: str | None = None,
    page_number: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    queryset = RetentionPolicy.objects.order_by("code", "id")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search is not None:
        if not isinstance(search, str):
            raise PrivacyInputError("search must be text")
        term = search.strip()
        if len(term) > MAX_SEARCH_LENGTH:
            raise PrivacyInputError(f"search must be at most {MAX_SEARCH_LENGTH} characters")
        if term:
            queryset = queryset.filter(Q(code__icontains=term) | Q(name__icontains=term))
    return page(queryset, page=page_number, page_size=page_size)


def create_retention(*, code: str, context: AuditContext, **values):
    cleaned = _retention_values(values)
    normalized = _clean_code(code)
    with transaction.atomic():
        if RetentionPolicy.objects.filter(code=normalized).exists():
            raise PrivacyConflict(
                "retention policy code already exists", code=PrivacyConflictCode.CODE_IN_USE
            )
        item = RetentionPolicy(code=normalized, **cleaned)
        try:
            _validate_model(item)
        except PrivacyInputError:
            if RetentionPolicy.objects.filter(code=normalized).exists():
                raise PrivacyConflict(
                    "retention policy code already exists",
                    code=PrivacyConflictCode.CODE_IN_USE,
                ) from None
            raise
        try:
            with transaction.atomic():
                item.save()
        except IntegrityError as exc:
            raise PrivacyConflict(
                "retention policy code already exists", code=PrivacyConflictCode.CODE_IN_USE
            ) from exc
        _audit(
            context,
            actions.PRIVACY_RETENTION_CREATED,
            "privacy.retention",
            item.pk,
            {"code": item.code},
        )
    return item


def update_retention(*, policy_id: UUID, context: AuditContext, changes: dict[str, Any]):
    cleaned = _retention_values(changes)
    with transaction.atomic():
        item = RetentionPolicy.objects.select_for_update().filter(pk=policy_id).first()
        if item is None:
            raise PrivacyRecordNotFound("retention policy was not found")
        if not cleaned:
            return item
        if not item.is_active:
            raise PrivacyConflict(
                "retired retention policy cannot be edited",
                code=PrivacyConflictCode.RETENTION_POLICY_RETIRED,
            )
        for key, value in cleaned.items():
            setattr(item, key, value)
        _validate_model(item)
        item.save(update_fields=[*cleaned, "updated_at"])
        _audit(
            context,
            actions.PRIVACY_RETENTION_UPDATED,
            "privacy.retention",
            item.pk,
            {"changed_fields": _changed_fields(cleaned)},
        )
    return item


def retire_retention(*, policy_id: UUID, context: AuditContext):
    with transaction.atomic():
        item = RetentionPolicy.objects.select_for_update().filter(pk=policy_id).first()
        if item is None:
            raise PrivacyRecordNotFound("retention policy was not found")
        if not item.is_active:
            return item
        if ProcessingActivity.objects.filter(retention_policy=item, is_active=True).exists():
            raise PrivacyConflict(
                "active processing activities must be reassigned before retirement",
                code=PrivacyConflictCode.RETENTION_POLICY_IN_USE,
            )
        item.is_active = False
        item.save(update_fields=["is_active", "updated_at"])
        _audit(
            context,
            actions.PRIVACY_RETENTION_RETIRED,
            "privacy.retention",
            item.pk,
            {"from_active": True, "to_active": False},
        )
    return item


def _audiences(value: Any):
    if not isinstance(value, list) or not value or len(value) > len(AUDIENCES):
        raise PrivacyInputError("audiences must be a nonempty bounded list")
    if any(not isinstance(audience, str) or audience not in AUDIENCES for audience in value):
        raise PrivacyInputError("audiences must use PUBLIC, STUDENT, or STAFF")
    if len(set(value)) != len(value):
        raise PrivacyInputError("audiences must not contain duplicates")
    return value


def _revision_values(values: dict[str, Any]):
    cleaned = {}
    for field, value in values.items():
        if field == "title":
            cleaned[field] = _clean_required(value, label=field, maximum=200)
        elif field == "summary":
            cleaned[field] = _clean_required(value, label=field, maximum=2000)
        elif field == "body":
            cleaned[field] = _clean_required(value, label=field, maximum=20000)
        elif field == "audiences":
            cleaned[field] = _audiences(value)
        elif field == "requires_acknowledgment":
            if type(value) is not bool:
                raise PrivacyInputError("requires_acknowledgment must be boolean")
            cleaned[field] = value
        elif field == "effective_on":
            if value is not None and not isinstance(value, date):
                raise PrivacyInputError("effective_on must be a date")
            cleaned[field] = value
        else:
            raise PrivacyInputError("notice revision contains unsupported fields")
    return cleaned


def get_notice(notice_id: UUID):
    item = notice_queryset().filter(pk=notice_id).first()
    if item is None:
        raise PrivacyRecordNotFound("privacy notice was not found")
    return item


def list_notices(
    *, is_active: bool | None = None, page_number: int = 1, page_size: int = DEFAULT_PAGE_SIZE
):
    queryset = notice_queryset().order_by("code")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return page(queryset, page=page_number, page_size=page_size)


def create_notice(*, actor: User, context: AuditContext, code: str, name: str, **revision_values):
    cleaned = _revision_values(revision_values)
    normalized = _clean_code(code)
    name = _clean_required(name, label="name", maximum=160)
    with transaction.atomic():
        if PrivacyNotice.objects.filter(code=normalized).exists():
            raise PrivacyConflict(
                "privacy notice code already exists", code=PrivacyConflictCode.CODE_IN_USE
            )
        notice = PrivacyNotice(code=normalized, name=name)
        try:
            _validate_model(notice)
        except PrivacyInputError:
            if PrivacyNotice.objects.filter(code=normalized).exists():
                raise PrivacyConflict(
                    "privacy notice code already exists",
                    code=PrivacyConflictCode.CODE_IN_USE,
                ) from None
            raise
        try:
            with transaction.atomic():
                notice.save()
        except IntegrityError as exc:
            raise PrivacyConflict(
                "privacy notice code already exists", code=PrivacyConflictCode.CODE_IN_USE
            ) from exc
        revision = PrivacyNoticeRevision(
            notice=notice, revision_number=1, created_by=actor, **cleaned
        )
        _validate_model(revision)
        revision.save()
        _audit(
            context,
            actions.PRIVACY_NOTICE_CREATED,
            "privacy.notice",
            notice.pk,
            {"code": notice.code, "revision_number": 1},
        )
    return notice


def update_notice(*, notice_id: UUID, context: AuditContext, name: str | None = None):
    with transaction.atomic():
        notice = PrivacyNotice.objects.select_for_update().filter(pk=notice_id).first()
        if notice is None:
            raise PrivacyRecordNotFound("privacy notice was not found")
        if not notice.is_active:
            raise PrivacyConflict(
                "retired privacy notice cannot be edited",
                code=PrivacyConflictCode.NOTICE_RETIRED,
            )
        if name is None:
            return notice
        notice.name = _clean_required(name, label="name", maximum=160)
        _validate_model(notice)
        notice.save(update_fields=["name", "updated_at"])
        _audit(
            context,
            actions.PRIVACY_NOTICE_UPDATED,
            "privacy.notice",
            notice.pk,
            {"changed_fields": ["name"]},
        )
    return notice


def retire_notice(*, notice_id: UUID, context: AuditContext):
    with transaction.atomic():
        notice = PrivacyNotice.objects.select_for_update().filter(pk=notice_id).first()
        if notice is None:
            raise PrivacyRecordNotFound("privacy notice was not found")
        if not notice.is_active:
            return notice
        notice.is_active = False
        notice.save(update_fields=["is_active", "updated_at"])
        _audit(
            context,
            actions.PRIVACY_NOTICE_RETIRED,
            "privacy.notice",
            notice.pk,
            {"from_active": True, "to_active": False},
        )
    return notice


def get_revision(revision_id: UUID):
    item = PrivacyNoticeRevision.objects.select_related("notice").filter(pk=revision_id).first()
    if item is None:
        raise PrivacyRecordNotFound("privacy notice revision was not found")
    return item


def list_revisions(*, notice_id: UUID, page_number: int = 1, page_size: int = DEFAULT_PAGE_SIZE):
    if not PrivacyNotice.objects.filter(pk=notice_id).exists():
        raise PrivacyRecordNotFound("privacy notice was not found")
    return page(
        PrivacyNoticeRevision.objects.select_related("notice")
        .filter(notice_id=notice_id)
        .order_by("-revision_number"),
        page=page_number,
        page_size=page_size,
    )


def create_revision(*, notice_id: UUID, actor: User, context: AuditContext, **values):
    cleaned = _revision_values(values)
    with transaction.atomic():
        notice = PrivacyNotice.objects.select_for_update().filter(pk=notice_id).first()
        if notice is None:
            raise PrivacyRecordNotFound("privacy notice was not found")
        if not notice.is_active:
            raise PrivacyConflict(
                "retired privacy notice cannot receive revisions",
                code=PrivacyConflictCode.NOTICE_RETIRED,
            )
        if notice.revisions.filter(status=PrivacyNoticeRevisionStatus.DRAFT).exists():
            raise PrivacyConflict(
                "privacy notice already has a draft",
                code=PrivacyConflictCode.NOTICE_DRAFT_EXISTS,
            )
        latest = notice.revisions.order_by("-revision_number").first()
        revision = PrivacyNoticeRevision(
            notice=notice,
            revision_number=latest.revision_number + 1 if latest else 1,
            created_by=actor,
            **cleaned,
        )
        _validate_model(revision)
        revision.save()
        _audit(
            context,
            actions.PRIVACY_NOTICE_REVISION_CREATED,
            "privacy.notice.revision",
            revision.pk,
            {"notice_id": str(notice.pk), "revision_number": revision.revision_number},
        )
    return revision


def update_revision(*, revision_id: UUID, context: AuditContext, changes: dict[str, Any]):
    cleaned = _revision_values(changes)
    with transaction.atomic():
        candidate = get_revision(revision_id)
        notice = PrivacyNotice.objects.select_for_update().get(pk=candidate.notice_id)
        revision = PrivacyNoticeRevision.objects.select_for_update().get(pk=revision_id)
        if not notice.is_active:
            raise PrivacyConflict(
                "only a draft of an active privacy notice can be edited",
                code=PrivacyConflictCode.NOTICE_RETIRED,
            )
        if revision.status != PrivacyNoticeRevisionStatus.DRAFT:
            raise PrivacyConflict(
                "only a draft of an active privacy notice can be edited",
                code=PrivacyConflictCode.NOTICE_REVISION_IMMUTABLE,
            )
        if not cleaned:
            return revision
        for key, value in cleaned.items():
            setattr(revision, key, value)
        _validate_model(revision)
        revision.save(update_fields=[*cleaned, "updated_at"])
        _audit(
            context,
            actions.PRIVACY_NOTICE_REVISION_UPDATED,
            "privacy.notice.revision",
            revision.pk,
            {
                "revision_number": revision.revision_number,
                "changed_fields": _changed_fields(cleaned),
            },
        )
    return revision


def publish_revision(*, revision_id: UUID, actor: User, context: AuditContext):
    with transaction.atomic():
        candidate = get_revision(revision_id)
        notice = PrivacyNotice.objects.select_for_update().get(pk=candidate.notice_id)
        revision = PrivacyNoticeRevision.objects.select_for_update().get(pk=revision_id)
        blocker = notice_publish_blocker(
            notice_active=notice.is_active,
            status=revision.status,
            effective_on=revision.effective_on,
            today=timezone.localdate(),
        )
        if blocker == NoticePublishBlocker.NOTICE_RETIRED:
            raise PrivacyConflict(
                "only a draft of an active notice can be published",
                code=PrivacyConflictCode.NOTICE_RETIRED,
            )
        if blocker == NoticePublishBlocker.REVISION_NOT_DRAFT:
            raise PrivacyConflict(
                "only a draft of an active notice can be published",
                code=PrivacyConflictCode.NOTICE_REVISION_IMMUTABLE,
            )
        if blocker is not None:
            raise PrivacyConflict(
                "notice effective date must be today or earlier",
                code=PrivacyConflictCode.NOTICE_NOT_YET_EFFECTIVE,
            )
        _revision_values({field: getattr(revision, field) for field in REVISION_FIELDS})
        _validate_model(revision)
        current = (
            notice.revisions.select_for_update()
            .filter(status=PrivacyNoticeRevisionStatus.PUBLISHED)
            .first()
        )
        if current is not None:
            current.status = PrivacyNoticeRevisionStatus.SUPERSEDED
            current.save(update_fields=["status", "updated_at"])
        revision.status = PrivacyNoticeRevisionStatus.PUBLISHED
        revision.published_by = actor
        revision.published_at = timezone.now()
        _validate_model(revision)
        revision.save(update_fields=["status", "published_by", "published_at", "updated_at"])
        _audit(
            context,
            actions.PRIVACY_NOTICE_REVISION_PUBLISHED,
            "privacy.notice.revision",
            revision.pk,
            {
                "notice_id": str(notice.pk),
                "revision_number": revision.revision_number,
                "superseded_revision_number": current.revision_number if current else None,
            },
        )
    return revision


def current_revisions(audience: str | None = None):
    queryset = PrivacyNoticeRevision.objects.select_related("notice").filter(
        notice__is_active=True,
        status=PrivacyNoticeRevisionStatus.PUBLISHED,
    )
    if audience is not None:
        queryset = queryset.filter(audiences__contains=[audience])
    return queryset.order_by("notice__code")


def applicable_revisions(actor: User):
    audience = "STUDENT" if actor.role.code == "STUDENT" else "STAFF"
    return current_revisions().filter(
        Q(audiences__contains=["PUBLIC"]) | Q(audiences__contains=[audience])
    )


def acknowledge_revision(*, revision_id: UUID, actor: User, context: AuditContext):
    with transaction.atomic():
        candidate = get_revision(revision_id)
        PrivacyNotice.objects.select_for_update().get(pk=candidate.notice_id)
        revision = get_revision(revision_id)
        if (
            revision.status != PrivacyNoticeRevisionStatus.PUBLISHED
            or not revision.notice.is_active
        ):
            raise PrivacyConflict(
                "notice revision is no longer current; refresh notices",
                code=PrivacyConflictCode.NOTICE_REVISION_NOT_CURRENT,
            )
        if not revision.requires_acknowledgment:
            raise PrivacyConflict(
                "notice revision does not require acknowledgment",
                code=PrivacyConflictCode.NOTICE_ACKNOWLEDGMENT_NOT_APPLICABLE,
            )
        audience = "STUDENT" if actor.role.code == "STUDENT" else "STAFF"
        if not set(revision.audiences).intersection({"PUBLIC", audience}):
            raise PrivacyConflict(
                "notice revision is not applicable to this account",
                code=PrivacyConflictCode.NOTICE_ACKNOWLEDGMENT_NOT_APPLICABLE,
            )
        acknowledgment, created = PrivacyNoticeAcknowledgment.objects.get_or_create(
            user=actor, revision=revision
        )
        if created:
            _audit(
                context,
                actions.PRIVACY_NOTICE_ACKNOWLEDGED,
                "privacy.notice.revision",
                revision.pk,
                {"revision_number": revision.revision_number},
            )
    return acknowledgment
