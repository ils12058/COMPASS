"""Shared public API schemas and response-contract helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone
from ninja import Schema


class ValidationIssue(Schema):
    """A safe, normalized validation issue returned inside the error envelope."""

    loc: list[str]
    message: str
    type: str


class APIErrorDetail(Schema):
    """The stable error payload shared by all public API domains."""

    code: str
    message: str
    request_id: str | None = None
    details: list[ValidationIssue] | dict[str, Any] | None = None


class APIErrorResponse(Schema):
    """The standard COMPASS JSON error envelope."""

    error: APIErrorDetail


def response_with_errors(
    success_schema: Any,
    *error_statuses: int,
    success_status: int = 200,
) -> dict[int, Any]:
    """Build a response map without duplicating the shared error schema."""

    return {
        success_status: success_schema,
        **{status: APIErrorResponse for status in error_statuses},
    }


def same_timestamp_version(saved: datetime, expected: datetime) -> bool:
    """Compare optimistic-concurrency timestamps across API millisecond truncation.

    Django Ninja's default ``DjangoJSONEncoder`` truncates ``datetime`` fields to
    millisecond precision (3 fractional digits). When a client returns an API-serialized
    ``updated_at`` value (microseconds divisible by 1000), compare at millisecond
    precision; when full microsecond precision is supplied directly, require an exact
    match. Naive datetimes never match.
    """

    if timezone.is_naive(saved) or timezone.is_naive(expected):
        return False
    if expected.microsecond % 1000 == 0:
        return saved.replace(microsecond=saved.microsecond // 1000 * 1000) == expected
    return saved == expected


__all__ = [
    "APIErrorDetail",
    "APIErrorResponse",
    "ValidationIssue",
    "response_with_errors",
    "same_timestamp_version",
]
