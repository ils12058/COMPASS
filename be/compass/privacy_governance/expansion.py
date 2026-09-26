"""Transactional retention and notice governance; no retention execution or consent inference."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q
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
    *, is_active: bool | None = None, page_number: int = 1, page_size: int = DEFAULT_PAGE_SIZE
):
    queryset = RetentionPolicy.objects.order_by("code")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return page(queryset, page=page_number, page_size=page_size)


def create_retention(*, code: str, context: AuditContext, **values):
    cleaned = _retention_values(values)
    normalized = _clean_code(code)
    with transaction.atomic():
        if RetentionPolicy.objects.filter(code=normalized).exists():
            raise PrivacyConflict("retention policy code already exists")
        item = RetentionPolicy(code=normalized, **cleaned)
        try:
            _validate_model(item)
        except PrivacyInputError:
            if RetentionPolicy.objects.filter(code=normalized).exists():
                raise PrivacyConflict("retention policy code already exists") from None
            raise
        try:
            with transaction.atomic():
                item.save()
        except IntegrityError as exc:
            raise PrivacyConflict("retention policy code already exists") from exc
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
            raise PrivacyConflict("retired retention policy cannot be edited")
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
                "active processing activities must be reassigned before retirement"
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
    item = PrivacyNotice.objects.filter(pk=notice_id).first()
    if item is None:
        raise PrivacyRecordNotFound("privacy notice was not found")
    return item


def list_notices(
    *, is_active: bool | None = None, page_number: int = 1, page_size: int = DEFAULT_PAGE_SIZE
):
    queryset = PrivacyNotice.objects.order_by("code")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return page(queryset, page=page_number, page_size=page_size)


def create_notice(*, actor: User, context: AuditContext, code: str, name: str, **revision_values):
    cleaned = _revision_values(revision_values)
    normalized = _clean_code(code)
    name = _clean_required(name, label="name", maximum=160)
    with transaction.atomic():
        if PrivacyNotice.objects.filter(code=normalized).exists():
            raise PrivacyConflict("privacy notice code already exists")
        notice = PrivacyNotice(code=normalized, name=name)
        try:
            _validate_model(notice)
        except PrivacyInputError:
            if PrivacyNotice.objects.filter(code=normalized).exists():
                raise PrivacyConflict("privacy notice code already exists") from None
            raise
        try:
            with transaction.atomic():
                notice.save()
        except IntegrityError as exc:
            raise PrivacyConflict("privacy notice code already exists") from exc
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
            raise PrivacyConflict("retired privacy notice cannot be edited")
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
    get_notice(notice_id)
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
            raise PrivacyConflict("retired privacy notice cannot receive revisions")
        if notice.revisions.filter(status=PrivacyNoticeRevisionStatus.DRAFT).exists():
            raise PrivacyConflict("privacy notice already has a draft")
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
        if not notice.is_active or revision.status != PrivacyNoticeRevisionStatus.DRAFT:
            raise PrivacyConflict("only a draft of an active privacy notice can be edited")
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
        if not notice.is_active or revision.status != PrivacyNoticeRevisionStatus.DRAFT:
            raise PrivacyConflict("only a draft of an active notice can be published")
        if revision.effective_on is None or revision.effective_on > timezone.localdate():
            raise PrivacyConflict("notice effective date must be today or earlier")
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
            raise PrivacyConflict("notice revision is no longer current; refresh notices")
        if not revision.requires_acknowledgment:
            raise PrivacyConflict("notice revision does not require acknowledgment")
        audience = "STUDENT" if actor.role.code == "STUDENT" else "STAFF"
        if not set(revision.audiences).intersection({"PUBLIC", audience}):
            raise PrivacyConflict("notice revision is not applicable to this account")
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
