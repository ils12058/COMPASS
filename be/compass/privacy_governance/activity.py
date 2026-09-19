"""Closed DPO privacy/security activity projection over the shared Audit Trail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from django.db.models import Q

from compass.accounts.policy import CAPABILITY_CODES, DESIGNATION_CODES, ROLE_CODES
from compass.audit.actions import (
    ACCOUNT_CAPABILITY_OVERRIDE_REMOVED,
    ACCOUNT_CAPABILITY_OVERRIDE_SET,
    ACCOUNT_DESIGNATION_ASSIGNED,
    ACCOUNT_DESIGNATION_REMOVED,
    ACCOUNT_DISABLED,
    ACCOUNT_ENABLED,
    ACCOUNT_MFA_RESET,
    ACCOUNT_ROLE_CHANGED,
    DOCUMENT_DOWNLOAD_RELEASED,
    PRIVACY_INCIDENT_CREATED,
    PRIVACY_INCIDENT_RESOLVED,
    PRIVACY_INCIDENT_UPDATED,
    PRIVACY_PROCESSING_CREATED,
    PRIVACY_PROCESSING_RETIRED,
    PRIVACY_PROCESSING_UPDATED,
    PRIVACY_REVIEW_CREATED,
    PRIVACY_REVIEW_RESOLVED,
    PRIVACY_REVIEW_UPDATED,
    REPORT_EXPORT_RELEASED,
)
from compass.audit.models import AuditActorType, AuditEvent, AuditOutcome
from compass.authentication.actions import (
    AUTH_LOGIN_FAILED,
    AUTH_MFA_RECOVERY_CODE_USED,
    AUTH_MFA_TOTP_DISABLED,
    AUTH_MFA_TOTP_FAILED,
    AUTH_PASSWORD_RESET,
)

from .releases import (
    GOOD_MORAL_TARGET_TYPE,
    GRADUATE_TRACER_TARGET_TYPE,
    STUDENT_PROFILING_TARGET_TYPE,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000


class PrivacyActivityCategory(StrEnum):
    DATA_RELEASE = "DATA_RELEASE"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    ACCOUNT_SECURITY = "ACCOUNT_SECURITY"
    PRIVACY_GOVERNANCE = "PRIVACY_GOVERNANCE"


class PrivacyActivityPaginationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PrivacyActivityItem:
    id: UUID
    category: PrivacyActivityCategory
    type: str
    title: str
    description: str
    occurred_at: datetime
    actor_display_name: str | None
    artifact_type: str | None
    artifact_format: str | None
    scope: str | None
    resource_reference: str | None


@dataclass(frozen=True, slots=True)
class PrivacyActivityPage:
    items: tuple[PrivacyActivityItem, ...]
    page: int
    page_size: int
    has_next: bool


def _uuid_string(value: object) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


def _safe_actor(event: AuditEvent, *, proven: bool) -> str | None:
    if not proven:
        return None
    if event.actor_type != AuditActorType.USER or event.actor_user is None:
        return None
    return event.actor_user.get_full_name().strip() or "COMPASS operator"


def _base(
    event: AuditEvent,
    *,
    category: PrivacyActivityCategory,
    title: str,
    description: str,
    actor_proven: bool = True,
    artifact_type: str | None = None,
    artifact_format: str | None = None,
    scope: str | None = None,
    resource_reference: str | None = None,
) -> PrivacyActivityItem:
    return PrivacyActivityItem(
        id=event.pk,
        category=category,
        type=event.action,
        title=title,
        description=description,
        occurred_at=event.occurred_at,
        actor_display_name=_safe_actor(event, proven=actor_proven),
        artifact_type=artifact_type,
        artifact_format=artifact_format,
        scope=scope,
        resource_reference=resource_reference,
    )


def _safe_iso_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("invalid bounded ISO date")
    return date.fromisoformat(value)


def _graduate_tracer_report_release(event: AuditEvent) -> PrivacyActivityItem | None:
    if event.target_type != GRADUATE_TRACER_TARGET_TYPE:
        return None
    metadata = event.metadata
    if metadata.get("report_type") != "graduate_tracer":
        return None
    if metadata.get("format") != "XLSX":
        return None
    schema_version = metadata.get("instrument_schema_version")
    if type(schema_version) is not int or schema_version != 1:
        return None
    if str(event.target_id) != str(schema_version):
        return None
    try:
        submitted_from = _safe_iso_date(metadata.get("submitted_from"))
        submitted_to = _safe_iso_date(metadata.get("submitted_to"))
    except (TypeError, ValueError):
        return None
    if submitted_from is not None and submitted_to is not None:
        if submitted_from > submitted_to:
            return None

    scope_parts = [f"Schema version {schema_version}"]
    if submitted_from is not None:
        scope_parts.append(f"Submitted from {submitted_from.isoformat()}")
    if submitted_to is not None:
        scope_parts.append(f"Submitted to {submitted_to.isoformat()}")
    return _base(
        event,
        category=PrivacyActivityCategory.DATA_RELEASE,
        title="Graduate Tracer XLSX released",
        description=(
            "COMPASS authorized and prepared an aggregate Graduate Tracer report response."
        ),
        artifact_type="graduate_tracer",
        artifact_format="XLSX",
        scope="; ".join(scope_parts),
        resource_reference=f"schema-v{schema_version}",
    )


def _report_release(event: AuditEvent) -> PrivacyActivityItem | None:
    if event.target_type == GRADUATE_TRACER_TARGET_TYPE:
        return _graduate_tracer_report_release(event)
    if event.target_type != STUDENT_PROFILING_TARGET_TYPE:
        return None
    resource = _uuid_string(event.target_id)
    if resource is None:
        return None
    metadata = event.metadata
    if metadata.get("report_type") != "student_profiling":
        return None
    artifact_format = metadata.get("format")
    if artifact_format not in {"PDF", "XLSX"}:
        return None

    label = metadata.get("academic_year_label")
    if not isinstance(label, str) or not label or len(label) > 128:
        return None
    scope_parts = [f"Academic Year {label}"]
    for key, display in (
        ("campus_code", "Campus"),
        ("college_code", "College"),
        ("program_code", "Program"),
    ):
        value = metadata.get(key)
        if value is not None:
            if not isinstance(value, str) or len(value) > 64:
                return None
            scope_parts.append(f"{display} {value}")
    year_level = metadata.get("year_level")
    if year_level is not None:
        if type(year_level) is not int or not 1 <= year_level <= 10:
            return None
        scope_parts.append(f"Year Level {year_level}")

    return _base(
        event,
        category=PrivacyActivityCategory.DATA_RELEASE,
        title=f"Student Profiling {artifact_format} released",
        description=("COMPASS authorized and prepared a Student Profiling artifact response."),
        artifact_type="student_profiling",
        artifact_format=str(artifact_format),
        scope="; ".join(scope_parts),
        resource_reference=resource,
    )


def _document_release(event: AuditEvent) -> PrivacyActivityItem | None:
    if event.target_type != GOOD_MORAL_TARGET_TYPE:
        return None
    resource = _uuid_string(event.target_id)
    if resource is None:
        return None
    metadata = event.metadata
    if metadata.get("document_type") != "good_moral_certificate":
        return None
    access_mode = metadata.get("access_mode")
    variant = metadata.get("variant")
    if access_mode not in {"SELF", "GCO"}:
        return None
    if not isinstance(variant, str) or len(variant) > 64:
        return None
    return _base(
        event,
        category=PrivacyActivityCategory.DATA_RELEASE,
        title="Good Moral certificate released",
        description="COMPASS authorized and prepared a Good Moral certificate response.",
        artifact_type="good_moral_certificate",
        artifact_format="PDF",
        scope=f"Access {access_mode}; Variant {variant}",
        resource_reference=resource,
    )


def _access_control(event: AuditEvent) -> PrivacyActivityItem | None:
    if event.target_type != "accounts.user":
        return None
    resource = _uuid_string(event.target_id)
    if resource is None:
        return None

    metadata = event.metadata
    if event.action == ACCOUNT_ENABLED:
        title, description = "Account enabled", "An account was enabled."
    elif event.action == ACCOUNT_DISABLED:
        title, description = "Account disabled", "An account was disabled."
    elif event.action == ACCOUNT_MFA_RESET:
        title, description = (
            "Account MFA reset",
            "Administrative MFA state was reset for an account.",
        )
    elif event.action == ACCOUNT_ROLE_CHANGED:
        from_role = metadata.get("from_role")
        to_role = metadata.get("to_role")
        if from_role not in ROLE_CODES or to_role not in ROLE_CODES:
            return None
        title = "Account role changed"
        description = f"Account role changed from {from_role} to {to_role}."
    elif event.action in {ACCOUNT_DESIGNATION_ASSIGNED, ACCOUNT_DESIGNATION_REMOVED}:
        designation = metadata.get("designation")
        if designation not in DESIGNATION_CODES:
            return None
        assigned = event.action == ACCOUNT_DESIGNATION_ASSIGNED
        title = (
            "Institutional designation assigned"
            if assigned
            else "Institutional designation removed"
        )
        verb = "assigned to" if assigned else "removed from"
        description = f"{designation} was {verb} an account."
    elif event.action in {
        ACCOUNT_CAPABILITY_OVERRIDE_SET,
        ACCOUNT_CAPABILITY_OVERRIDE_REMOVED,
    }:
        capability = metadata.get("capability")
        if capability not in CAPABILITY_CODES:
            return None
        if event.action == ACCOUNT_CAPABILITY_OVERRIDE_SET:
            effect = metadata.get("effect")
            if effect not in {"GRANT", "REVOKE"}:
                return None
            title = "Capability override set"
            description = f"{effect} override set for {capability}."
        else:
            title = "Capability override removed"
            description = f"Capability override removed for {capability}."
    else:
        return None

    return _base(
        event,
        category=PrivacyActivityCategory.ACCESS_CONTROL,
        title=title,
        description=description,
        resource_reference=resource,
    )


def _account_security(event: AuditEvent) -> PrivacyActivityItem | None:
    if event.action == AUTH_LOGIN_FAILED:
        if event.target_type not in {None, "", "accounts.user"}:
            return None
        resource = _uuid_string(event.target_id) if event.target_id is not None else None
        if event.target_id is not None and resource is None:
            return None
        return _base(
            event,
            category=PrivacyActivityCategory.ACCOUNT_SECURITY,
            title="Failed login attempt",
            description="Failed login attempt for an account.",
            actor_proven=False,
            resource_reference=resource,
        )

    if event.action == AUTH_MFA_TOTP_FAILED:
        if event.target_type not in {None, "", "auth.totpfactor"}:
            return None
        return _base(
            event,
            category=PrivacyActivityCategory.ACCOUNT_SECURITY,
            title="MFA verification failed",
            description="MFA verification failed for an account.",
            actor_proven=False,
        )

    if event.action == AUTH_MFA_TOTP_DISABLED:
        if event.target_type != "auth.totpfactor" or _uuid_string(event.target_id) is None:
            return None
        return _base(
            event,
            category=PrivacyActivityCategory.ACCOUNT_SECURITY,
            title="MFA disabled",
            description="TOTP MFA was disabled for an account.",
        )

    if event.action == AUTH_MFA_RECOVERY_CODE_USED:
        if event.target_type != "auth.recoverycode" or _uuid_string(event.target_id) is None:
            return None
        return _base(
            event,
            category=PrivacyActivityCategory.ACCOUNT_SECURITY,
            title="MFA recovery code used",
            description="A recovery code was used to complete MFA for an account.",
        )

    if event.action == AUTH_PASSWORD_RESET:
        if event.target_type != "accounts.user":
            return None
        resource = _uuid_string(event.target_id)
        if resource is None:
            return None
        return _base(
            event,
            category=PrivacyActivityCategory.ACCOUNT_SECURITY,
            title="Password reset completed",
            description="A password reset was completed for an account.",
            resource_reference=resource,
        )
    return None


_GOVERNANCE_PRESENTATION = {
    PRIVACY_PROCESSING_CREATED: (
        "Processing activity created",
        "A Privacy Processing Register entry was created.",
        "privacy.processing",
    ),
    PRIVACY_PROCESSING_UPDATED: (
        "Processing activity updated",
        "A Privacy Processing Register entry was updated.",
        "privacy.processing",
    ),
    PRIVACY_PROCESSING_RETIRED: (
        "Processing activity retired",
        "A Privacy Processing Register entry was retired.",
        "privacy.processing",
    ),
    PRIVACY_REVIEW_CREATED: (
        "Privacy review created",
        "A privacy review record was created.",
        "privacy.review",
    ),
    PRIVACY_REVIEW_UPDATED: (
        "Privacy review updated",
        "An open privacy review record was updated.",
        "privacy.review",
    ),
    PRIVACY_REVIEW_RESOLVED: (
        "Privacy review resolved",
        "A privacy review record was resolved.",
        "privacy.review",
    ),
    PRIVACY_INCIDENT_CREATED: (
        "Privacy incident recorded",
        "A privacy incident governance record was created.",
        "privacy.incident",
    ),
    PRIVACY_INCIDENT_UPDATED: (
        "Privacy incident updated",
        "A privacy incident governance record was updated.",
        "privacy.incident",
    ),
    PRIVACY_INCIDENT_RESOLVED: (
        "Privacy incident resolved",
        "A privacy incident governance record was resolved.",
        "privacy.incident",
    ),
}


def _privacy_governance(event: AuditEvent) -> PrivacyActivityItem | None:
    presentation = _GOVERNANCE_PRESENTATION.get(event.action)
    if presentation is None:
        return None
    title, description, target_type = presentation
    if event.target_type != target_type:
        return None
    resource = _uuid_string(event.target_id)
    if resource is None:
        return None
    return _base(
        event,
        category=PrivacyActivityCategory.PRIVACY_GOVERNANCE,
        title=title,
        description=description,
        resource_reference=resource,
    )


_DATA_RELEASE_ACTIONS = frozenset({REPORT_EXPORT_RELEASED, DOCUMENT_DOWNLOAD_RELEASED})
_ACCESS_CONTROL_ACTIONS = frozenset(
    {
        ACCOUNT_ENABLED,
        ACCOUNT_DISABLED,
        ACCOUNT_ROLE_CHANGED,
        ACCOUNT_DESIGNATION_ASSIGNED,
        ACCOUNT_DESIGNATION_REMOVED,
        ACCOUNT_CAPABILITY_OVERRIDE_SET,
        ACCOUNT_CAPABILITY_OVERRIDE_REMOVED,
        ACCOUNT_MFA_RESET,
    }
)
_ACCOUNT_SECURITY_ACTIONS = frozenset(
    {
        AUTH_LOGIN_FAILED,
        AUTH_MFA_TOTP_FAILED,
        AUTH_MFA_TOTP_DISABLED,
        AUTH_MFA_RECOVERY_CODE_USED,
        AUTH_PASSWORD_RESET,
    }
)
_PRIVACY_GOVERNANCE_ACTIONS = frozenset(_GOVERNANCE_PRESENTATION)
_ALL_ACTIONS = (
    _DATA_RELEASE_ACTIONS
    | _ACCESS_CONTROL_ACTIONS
    | _ACCOUNT_SECURITY_ACTIONS
    | _PRIVACY_GOVERNANCE_ACTIONS
)


def _present(event: AuditEvent) -> PrivacyActivityItem | None:
    if event.action == REPORT_EXPORT_RELEASED:
        return _report_release(event)
    if event.action == DOCUMENT_DOWNLOAD_RELEASED:
        return _document_release(event)
    if event.action in _ACCESS_CONTROL_ACTIONS:
        return _access_control(event)
    if event.action in _ACCOUNT_SECURITY_ACTIONS:
        return _account_security(event)
    if event.action in _PRIVACY_GOVERNANCE_ACTIONS:
        return _privacy_governance(event)
    return None


def _validate_page(*, page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1 or page > MAX_PAGE_NUMBER:
        raise PrivacyActivityPaginationError(
            f"page must be an integer between 1 and {MAX_PAGE_NUMBER}"
        )
    if type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise PrivacyActivityPaginationError(
            f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}"
        )
    return page, page_size


def list_privacy_activity(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    category: PrivacyActivityCategory | str | None = None,
) -> PrivacyActivityPage:
    page, page_size = _validate_page(page=page, page_size=page_size)
    selected_category = None
    if category is not None:
        try:
            selected_category = PrivacyActivityCategory(str(category))
        except ValueError as exc:
            raise PrivacyActivityPaginationError("privacy activity category is invalid") from exc

    actions = _ALL_ACTIONS
    if selected_category == PrivacyActivityCategory.DATA_RELEASE:
        actions = _DATA_RELEASE_ACTIONS
    elif selected_category == PrivacyActivityCategory.ACCESS_CONTROL:
        actions = _ACCESS_CONTROL_ACTIONS
    elif selected_category == PrivacyActivityCategory.ACCOUNT_SECURITY:
        actions = _ACCOUNT_SECURITY_ACTIONS
    elif selected_category == PrivacyActivityCategory.PRIVACY_GOVERNANCE:
        actions = _PRIVACY_GOVERNANCE_ACTIONS

    queryset = (
        AuditEvent.objects.select_related("actor_user")
        .filter(action__in=actions)
        .filter(
            Q(outcome=AuditOutcome.SUCCESS)
            | Q(
                action__in={AUTH_LOGIN_FAILED, AUTH_MFA_TOTP_FAILED},
                outcome=AuditOutcome.DENIED,
            )
        )
        .order_by("-occurred_at", "-id")
    )

    offset = (page - 1) * page_size
    # Pull a bounded overfetch because malformed allowlisted rows fail closed.
    candidates = list(queryset[offset : offset + page_size * 2 + 1])
    items: list[PrivacyActivityItem] = []
    consumed = 0
    for event in candidates:
        consumed += 1
        item = _present(event)
        if item is not None:
            items.append(item)
        if len(items) >= page_size + 1:
            break

    has_next = len(items) > page_size or (
        consumed == len(candidates) and len(candidates) > page_size * 2
    )
    return PrivacyActivityPage(
        items=tuple(items[:page_size]),
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "PrivacyActivityCategory",
    "PrivacyActivityItem",
    "PrivacyActivityPage",
    "PrivacyActivityPaginationError",
    "list_privacy_activity",
]
