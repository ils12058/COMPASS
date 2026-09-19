"""Transactional Privacy Governance services with bounded governance text."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    PRIVACY_INCIDENT_CREATED,
    PRIVACY_INCIDENT_RESOLVED,
    PRIVACY_INCIDENT_UPDATED,
    PRIVACY_PROCESSING_CREATED,
    PRIVACY_PROCESSING_RETIRED,
    PRIVACY_PROCESSING_UPDATED,
    PRIVACY_REVIEW_CREATED,
    PRIVACY_REVIEW_RESOLVED,
    PRIVACY_REVIEW_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import (
    PrivacyIncident,
    PrivacyIncidentStatus,
    PrivacyNotificationAssessment,
    PrivacyReview,
    PrivacyReviewStatus,
    PrivacyReviewType,
    ProcessingActivity,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000
MAX_CATEGORY_ITEMS = 32
MAX_CATEGORY_LENGTH = 80
PROCESSING_TARGET = "privacy.processing"
REVIEW_TARGET = "privacy.review"
INCIDENT_TARGET = "privacy.incident"

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{1,63}$", re.ASCII)
_STATUS_RANK = {
    PrivacyIncidentStatus.OPEN: 0,
    PrivacyIncidentStatus.ASSESSING: 1,
    PrivacyIncidentStatus.CONTAINED: 2,
    PrivacyIncidentStatus.RESOLVED: 3,
}


class PrivacyGovernanceError(RuntimeError):
    pass


class PrivacyRecordNotFound(PrivacyGovernanceError):
    pass


class PrivacyConflict(PrivacyGovernanceError):
    pass


class PrivacyInputError(PrivacyGovernanceError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessingPage:
    items: tuple[ProcessingActivity, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class ReviewPage:
    items: tuple[PrivacyReview, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class IncidentPage:
    items: tuple[PrivacyIncident, ...]
    page: int
    page_size: int
    has_next: bool


def _validate_page(*, page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1 or page > MAX_PAGE_NUMBER:
        raise PrivacyInputError(f"page must be between 1 and {MAX_PAGE_NUMBER}")
    if type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise PrivacyInputError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _clean_required(value: object, *, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrivacyInputError(f"{label} is required")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise PrivacyInputError(f"{label} must be at most {maximum} characters")
    return cleaned


def _clean_optional(value: object, *, label: str, maximum: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PrivacyInputError(f"{label} must be text")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise PrivacyInputError(f"{label} must be at most {maximum} characters")
    return cleaned


def _clean_code(value: object) -> str:
    code = _clean_required(value, label="code", maximum=64).upper()
    if not _CODE_RE.fullmatch(code):
        raise PrivacyInputError(
            "code must contain only uppercase letters, digits, dot, underscore, or hyphen"
        )
    return code


def _clean_categories(value: object, *, label: str) -> list[str]:
    if not isinstance(value, list):
        raise PrivacyInputError(f"{label} must be a list of short strings")
    if len(value) > MAX_CATEGORY_ITEMS:
        raise PrivacyInputError(f"{label} may contain at most {MAX_CATEGORY_ITEMS} items")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PrivacyInputError(f"{label} must contain only nonblank strings")
        normalized = item.strip()
        if len(normalized) > MAX_CATEGORY_LENGTH:
            raise PrivacyInputError(
                f"{label} items must be at most {MAX_CATEGORY_LENGTH} characters"
            )
        key = normalized.casefold()
        if key in seen:
            raise PrivacyInputError(f"{label} must not contain duplicate items")
        seen.add(key)
        cleaned.append(normalized)
    return cleaned


def _validate_model(item) -> None:
    try:
        item.full_clean()
    except ValidationError as exc:
        raise PrivacyInputError("privacy governance record is invalid") from exc


def _changed_fields(changes: Mapping[str, object]) -> list[str]:
    return sorted(str(field) for field in changes)


def get_processing_activity(processing_id: UUID) -> ProcessingActivity:
    item = ProcessingActivity.objects.filter(pk=processing_id).first()
    if item is None:
        raise PrivacyRecordNotFound("processing activity was not found")
    return item


def list_processing_activities(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    is_active: bool | None = None,
) -> ProcessingPage:
    page, page_size = _validate_page(page=page, page_size=page_size)
    queryset = ProcessingActivity.objects.order_by("code")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    offset = (page - 1) * page_size
    records = list(queryset[offset : offset + page_size + 1])
    return ProcessingPage(
        items=tuple(records[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(records) > page_size,
    )


def create_processing_activity(
    *,
    actor: User,
    context: AuditContext,
    code: object,
    name: object,
    purpose: object,
    data_subject_categories: object,
    personal_data_categories: object,
    authorized_access_summary: object,
    safeguards_summary: object,
    retention_policy_reference: object = "",
    policy_basis_reference: object = "",
) -> ProcessingActivity:
    cleaned_code = _clean_code(code)
    with transaction.atomic():
        item = ProcessingActivity(
            code=cleaned_code,
            name=_clean_required(name, label="name", maximum=160),
            purpose=_clean_required(purpose, label="purpose", maximum=2_000),
            data_subject_categories=_clean_categories(
                data_subject_categories, label="data_subject_categories"
            ),
            personal_data_categories=_clean_categories(
                personal_data_categories, label="personal_data_categories"
            ),
            authorized_access_summary=_clean_required(
                authorized_access_summary,
                label="authorized_access_summary",
                maximum=2_000,
            ),
            safeguards_summary=_clean_required(
                safeguards_summary,
                label="safeguards_summary",
                maximum=2_000,
            ),
            retention_policy_reference=_clean_optional(
                retention_policy_reference,
                label="retention_policy_reference",
                maximum=255,
            ),
            policy_basis_reference=_clean_optional(
                policy_basis_reference,
                label="policy_basis_reference",
                maximum=255,
            ),
        )
        _validate_model(item)
        try:
            item.save()
        except IntegrityError as exc:
            raise PrivacyConflict("processing activity code already exists") from exc
        record_event(
            context=context,
            action=PRIVACY_PROCESSING_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type=PROCESSING_TARGET,
            target_id=item.pk,
            metadata={"active": True},
        )
    return item


def update_processing_activity(
    *,
    processing_id: UUID,
    context: AuditContext,
    changes: Mapping[str, object],
) -> ProcessingActivity:
    allowed = {
        "name",
        "purpose",
        "data_subject_categories",
        "personal_data_categories",
        "authorized_access_summary",
        "safeguards_summary",
        "retention_policy_reference",
        "policy_basis_reference",
    }
    unexpected = set(changes) - allowed
    if unexpected:
        raise PrivacyInputError("processing activity update contains unsupported fields")
    if not changes:
        return get_processing_activity(processing_id)

    with transaction.atomic():
        item = ProcessingActivity.objects.select_for_update().filter(pk=processing_id).first()
        if item is None:
            raise PrivacyRecordNotFound("processing activity was not found")

        cleaned: dict[str, object] = {}
        for field, value in changes.items():
            if field == "name":
                cleaned[field] = _clean_required(value, label=field, maximum=160)
            elif field in {
                "purpose",
                "authorized_access_summary",
                "safeguards_summary",
            }:
                cleaned[field] = _clean_required(value, label=field, maximum=2_000)
            elif field in {"data_subject_categories", "personal_data_categories"}:
                cleaned[field] = _clean_categories(value, label=field)
            else:
                cleaned[field] = _clean_optional(value, label=field, maximum=255)

        for field, value in cleaned.items():
            setattr(item, field, value)
        _validate_model(item)
        item.save(update_fields=[*cleaned.keys(), "updated_at"])
        record_event(
            context=context,
            action=PRIVACY_PROCESSING_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type=PROCESSING_TARGET,
            target_id=item.pk,
            metadata={"changed_fields": _changed_fields(cleaned)},
        )
    return item


def retire_processing_activity(
    *,
    processing_id: UUID,
    context: AuditContext,
) -> ProcessingActivity:
    with transaction.atomic():
        item = ProcessingActivity.objects.select_for_update().filter(pk=processing_id).first()
        if item is None:
            raise PrivacyRecordNotFound("processing activity was not found")
        if not item.is_active:
            return item
        item.is_active = False
        item.save(update_fields=["is_active", "updated_at"])
        record_event(
            context=context,
            action=PRIVACY_PROCESSING_RETIRED,
            outcome=AuditOutcome.SUCCESS,
            target_type=PROCESSING_TARGET,
            target_id=item.pk,
            metadata={"from_active": True, "to_active": False},
        )
    return item


def get_privacy_review(review_id: UUID) -> PrivacyReview:
    item = (
        PrivacyReview.objects.select_related("processing_activity", "reviewed_by")
        .filter(pk=review_id)
        .first()
    )
    if item is None:
        raise PrivacyRecordNotFound("privacy review was not found")
    return item


def list_privacy_reviews(
    *,
    processing_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ReviewPage:
    get_processing_activity(processing_id)
    page, page_size = _validate_page(page=page, page_size=page_size)
    queryset = (
        PrivacyReview.objects.select_related("processing_activity", "reviewed_by")
        .filter(processing_activity_id=processing_id)
        .order_by("-created_at", "-id")
    )
    offset = (page - 1) * page_size
    records = list(queryset[offset : offset + page_size + 1])
    return ReviewPage(
        items=tuple(records[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(records) > page_size,
    )


def create_privacy_review(
    *,
    actor: User,
    context: AuditContext,
    processing_id: UUID,
    review_type: object,
    scope_summary: object,
    findings_summary: object = "",
    recommendations_summary: object = "",
) -> PrivacyReview:
    review_type_value = str(review_type)
    if review_type_value not in PrivacyReviewType.values:
        raise PrivacyInputError("review_type is not supported")
    scope = _clean_required(scope_summary, label="scope_summary", maximum=2_000)
    findings = _clean_optional(findings_summary, label="findings_summary", maximum=4_000)
    recommendations = _clean_optional(
        recommendations_summary,
        label="recommendations_summary",
        maximum=4_000,
    )

    with transaction.atomic():
        processing = ProcessingActivity.objects.select_for_update().filter(pk=processing_id).first()
        if processing is None:
            raise PrivacyRecordNotFound("processing activity was not found")
        item = PrivacyReview(
            processing_activity=processing,
            review_type=review_type_value,
            scope_summary=scope,
            findings_summary=findings,
            recommendations_summary=recommendations,
            reviewed_by=actor,
        )
        _validate_model(item)
        item.save()
        record_event(
            context=context,
            action=PRIVACY_REVIEW_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type=REVIEW_TARGET,
            target_id=item.pk,
            metadata={
                "review_type": item.review_type,
                "status": item.status,
            },
        )
    return item


def update_privacy_review(
    *,
    review_id: UUID,
    context: AuditContext,
    changes: Mapping[str, object],
) -> PrivacyReview:
    allowed = {"scope_summary", "findings_summary", "recommendations_summary"}
    if set(changes) - allowed:
        raise PrivacyInputError("privacy review update contains unsupported fields")
    if not changes:
        return get_privacy_review(review_id)

    with transaction.atomic():
        item = (
            PrivacyReview.objects.select_for_update()
            .select_related("processing_activity", "reviewed_by")
            .filter(pk=review_id)
            .first()
        )
        if item is None:
            raise PrivacyRecordNotFound("privacy review was not found")
        if item.status == PrivacyReviewStatus.RESOLVED:
            raise PrivacyConflict("resolved privacy reviews cannot be edited")

        cleaned: dict[str, object] = {}
        for field, value in changes.items():
            maximum = 2_000 if field == "scope_summary" else 4_000
            cleaner = _clean_required if field == "scope_summary" else _clean_optional
            cleaned[field] = cleaner(value, label=field, maximum=maximum)
        for field, value in cleaned.items():
            setattr(item, field, value)
        _validate_model(item)
        item.save(update_fields=[*cleaned.keys(), "updated_at"])
        record_event(
            context=context,
            action=PRIVACY_REVIEW_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type=REVIEW_TARGET,
            target_id=item.pk,
            metadata={
                "review_type": item.review_type,
                "changed_fields": _changed_fields(cleaned),
            },
        )
    return item


def resolve_privacy_review(
    *,
    review_id: UUID,
    context: AuditContext,
    resolution_summary: object,
    now: datetime | None = None,
) -> PrivacyReview:
    resolution = _clean_required(
        resolution_summary,
        label="resolution_summary",
        maximum=4_000,
    )
    current = now or timezone.now()
    with transaction.atomic():
        item = (
            PrivacyReview.objects.select_for_update()
            .select_related("processing_activity", "reviewed_by")
            .filter(pk=review_id)
            .first()
        )
        if item is None:
            raise PrivacyRecordNotFound("privacy review was not found")
        if item.status == PrivacyReviewStatus.RESOLVED:
            raise PrivacyConflict("privacy review is already resolved")
        item.status = PrivacyReviewStatus.RESOLVED
        item.resolution_summary = resolution
        item.resolved_at = current
        _validate_model(item)
        item.save(
            update_fields=[
                "status",
                "resolution_summary",
                "resolved_at",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=PRIVACY_REVIEW_RESOLVED,
            outcome=AuditOutcome.SUCCESS,
            target_type=REVIEW_TARGET,
            target_id=item.pk,
            metadata={
                "review_type": item.review_type,
                "from_status": PrivacyReviewStatus.OPEN,
                "to_status": PrivacyReviewStatus.RESOLVED,
            },
        )
    return item


def _incident_reference(incident_id: UUID) -> str:
    return f"PRI-{incident_id.hex[:12].upper()}"


def get_privacy_incident(incident_id: UUID) -> PrivacyIncident:
    item = PrivacyIncident.objects.filter(pk=incident_id).first()
    if item is None:
        raise PrivacyRecordNotFound("privacy incident was not found")
    return item


def list_privacy_incidents(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: str | None = None,
) -> IncidentPage:
    page, page_size = _validate_page(page=page, page_size=page_size)
    queryset = PrivacyIncident.objects.order_by("-created_at", "-id")
    if status is not None:
        normalized = str(status).strip().upper()
        if normalized not in PrivacyIncidentStatus.values:
            raise PrivacyInputError("incident status is not supported")
        queryset = queryset.filter(status=normalized)
    offset = (page - 1) * page_size
    records = list(queryset[offset : offset + page_size + 1])
    return IncidentPage(
        items=tuple(records[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(records) > page_size,
    )


def create_privacy_incident(
    *,
    context: AuditContext,
    title: object,
    summary: object,
    affected_area: object,
    personal_data_categories: object,
    discovered_at: datetime,
    occurred_at: datetime | None = None,
    estimated_affected_subjects: int | None = None,
    assessment_summary: object = "",
    containment_summary: object = "",
    notification_assessment: object = PrivacyNotificationAssessment.NOT_ASSESSED,
    notification_reference: object = "",
) -> PrivacyIncident:
    if estimated_affected_subjects is not None and (
        type(estimated_affected_subjects) is not int or estimated_affected_subjects < 0
    ):
        raise PrivacyInputError("estimated_affected_subjects must be a nonnegative integer")
    notification_value = str(notification_assessment)
    if notification_value not in PrivacyNotificationAssessment.values:
        raise PrivacyInputError("notification_assessment is not supported")

    incident_id = uuid.uuid4()
    with transaction.atomic():
        item = PrivacyIncident(
            id=incident_id,
            reference_code=_incident_reference(incident_id),
            title=_clean_required(title, label="title", maximum=200),
            summary=_clean_required(summary, label="summary", maximum=3_000),
            affected_area=_clean_required(
                affected_area,
                label="affected_area",
                maximum=255,
            ),
            personal_data_categories=_clean_categories(
                personal_data_categories,
                label="personal_data_categories",
            ),
            occurred_at=occurred_at,
            discovered_at=discovered_at,
            estimated_affected_subjects=estimated_affected_subjects,
            assessment_summary=_clean_optional(
                assessment_summary,
                label="assessment_summary",
                maximum=4_000,
            ),
            containment_summary=_clean_optional(
                containment_summary,
                label="containment_summary",
                maximum=4_000,
            ),
            notification_assessment=notification_value,
            notification_reference=_clean_optional(
                notification_reference,
                label="notification_reference",
                maximum=255,
            ),
        )
        _validate_model(item)
        item.save()
        record_event(
            context=context,
            action=PRIVACY_INCIDENT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type=INCIDENT_TARGET,
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "status": item.status,
            },
        )
    return item


def _validate_incident_status_transition(current: str, requested: str) -> None:
    if requested not in PrivacyIncidentStatus.values:
        raise PrivacyInputError("incident status is not supported")
    if requested == PrivacyIncidentStatus.RESOLVED:
        raise PrivacyConflict("use the resolve operation to resolve a privacy incident")
    if _STATUS_RANK[requested] < _STATUS_RANK[current]:
        raise PrivacyConflict("privacy incident status cannot move backward")


def update_privacy_incident(
    *,
    incident_id: UUID,
    context: AuditContext,
    changes: Mapping[str, object],
) -> PrivacyIncident:
    allowed = {
        "title",
        "summary",
        "affected_area",
        "personal_data_categories",
        "status",
        "occurred_at",
        "discovered_at",
        "estimated_affected_subjects",
        "assessment_summary",
        "containment_summary",
        "notification_assessment",
        "notification_reference",
    }
    if set(changes) - allowed:
        raise PrivacyInputError("privacy incident update contains unsupported fields")
    if not changes:
        return get_privacy_incident(incident_id)

    with transaction.atomic():
        item = PrivacyIncident.objects.select_for_update().filter(pk=incident_id).first()
        if item is None:
            raise PrivacyRecordNotFound("privacy incident was not found")
        if item.status == PrivacyIncidentStatus.RESOLVED:
            raise PrivacyConflict("resolved privacy incidents cannot be edited")

        cleaned: dict[str, object] = {}
        for field, value in changes.items():
            if field == "title":
                cleaned[field] = _clean_required(value, label=field, maximum=200)
            elif field == "summary":
                cleaned[field] = _clean_required(value, label=field, maximum=3_000)
            elif field == "affected_area":
                cleaned[field] = _clean_required(value, label=field, maximum=255)
            elif field == "personal_data_categories":
                cleaned[field] = _clean_categories(value, label=field)
            elif field == "status":
                requested = str(value).strip().upper()
                _validate_incident_status_transition(item.status, requested)
                cleaned[field] = requested
            elif field == "estimated_affected_subjects":
                if value is not None and (type(value) is not int or value < 0):
                    raise PrivacyInputError(
                        "estimated_affected_subjects must be a nonnegative integer"
                    )
                cleaned[field] = value
            elif field in {"assessment_summary", "containment_summary"}:
                cleaned[field] = _clean_optional(value, label=field, maximum=4_000)
            elif field == "notification_assessment":
                requested = str(value).strip().upper()
                if requested not in PrivacyNotificationAssessment.values:
                    raise PrivacyInputError("notification_assessment is not supported")
                cleaned[field] = requested
            elif field == "notification_reference":
                cleaned[field] = _clean_optional(value, label=field, maximum=255)
            else:
                if value is not None and not isinstance(value, datetime):
                    raise PrivacyInputError(f"{field} must be a datetime or null")
                cleaned[field] = value

        from_status = item.status
        for field, value in cleaned.items():
            setattr(item, field, value)
        _validate_model(item)
        item.save(update_fields=[*cleaned.keys(), "updated_at"])
        metadata: dict[str, object] = {
            "reference_code": item.reference_code,
            "changed_fields": _changed_fields(cleaned),
        }
        if item.status != from_status:
            metadata["from_status"] = from_status
            metadata["to_status"] = item.status
        record_event(
            context=context,
            action=PRIVACY_INCIDENT_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type=INCIDENT_TARGET,
            target_id=item.pk,
            metadata=metadata,
        )
    return item


def resolve_privacy_incident(
    *,
    incident_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> PrivacyIncident:
    current = now or timezone.now()
    with transaction.atomic():
        item = PrivacyIncident.objects.select_for_update().filter(pk=incident_id).first()
        if item is None:
            raise PrivacyRecordNotFound("privacy incident was not found")
        if item.status == PrivacyIncidentStatus.RESOLVED:
            raise PrivacyConflict("privacy incident is already resolved")
        from_status = item.status
        item.status = PrivacyIncidentStatus.RESOLVED
        item.resolved_at = current
        _validate_model(item)
        item.save(update_fields=["status", "resolved_at", "updated_at"])
        record_event(
            context=context,
            action=PRIVACY_INCIDENT_RESOLVED,
            outcome=AuditOutcome.SUCCESS,
            target_type=INCIDENT_TARGET,
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "from_status": from_status,
                "to_status": PrivacyIncidentStatus.RESOLVED,
            },
        )
    return item


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "INCIDENT_TARGET",
    "MAX_CATEGORY_ITEMS",
    "MAX_PAGE_SIZE",
    "PROCESSING_TARGET",
    "PrivacyConflict",
    "PrivacyGovernanceError",
    "PrivacyInputError",
    "PrivacyRecordNotFound",
    "REVIEW_TARGET",
    "create_privacy_incident",
    "create_privacy_review",
    "create_processing_activity",
    "get_privacy_incident",
    "get_privacy_review",
    "get_processing_activity",
    "list_privacy_incidents",
    "list_privacy_reviews",
    "list_processing_activities",
    "resolve_privacy_incident",
    "resolve_privacy_review",
    "retire_processing_activity",
    "update_privacy_incident",
    "update_privacy_review",
    "update_processing_activity",
]
