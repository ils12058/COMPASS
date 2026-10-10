"""Shared validation and error primitives for retained Privacy Governance workflows."""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum

from django.core.exceptions import ValidationError

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{1,63}$", re.ASCII)


class PrivacyGovernanceError(RuntimeError):
    pass


class PrivacyRecordNotFound(PrivacyGovernanceError):
    pass


class PrivacyConflictCode(StrEnum):
    """Stable conflict classes for retained Privacy Governance recoveries."""

    GENERAL = "privacy_governance_conflict"
    CODE_IN_USE = "privacy_code_in_use"
    NOTICE_RETIRED = "privacy_notice_retired"
    NOTICE_DRAFT_EXISTS = "privacy_notice_draft_exists"
    NOTICE_REVISION_IMMUTABLE = "privacy_notice_revision_immutable"
    NOTICE_NOT_YET_EFFECTIVE = "privacy_notice_not_yet_effective"
    NOTICE_REVISION_NOT_CURRENT = "privacy_notice_revision_not_current"
    NOTICE_REVISION_CHANGED = "privacy_notice_revision_changed"
    NOTICE_ACKNOWLEDGMENT_NOT_APPLICABLE = "privacy_notice_acknowledgment_not_applicable"


class PrivacyConflict(PrivacyGovernanceError):
    def __init__(
        self,
        message: str,
        *,
        code: PrivacyConflictCode = PrivacyConflictCode.GENERAL,
    ) -> None:
        super().__init__(message)
        self.code = code


class PrivacyInputError(PrivacyGovernanceError):
    pass


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


def _validate_model(item) -> None:
    try:
        item.full_clean()
    except ValidationError as exc:
        raise PrivacyInputError("privacy governance record is invalid") from exc


def _changed_fields(changes: Mapping[str, object]) -> list[str]:
    return sorted(str(field) for field in changes)
