"""Bounded retrieval mechanics for explicitly presented activity, never raw audit search."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import islice

from compass.common.institutional_time import institution_zone

MAX_TEXT_LENGTH = 100
MAX_CANDIDATES = 100_000
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000


class ActivityRetrievalError(ValueError):
    pass


def normalized_text(value: str | None, label: str = "search") -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
        raise ActivityRetrievalError(f"{label} must contain at most {MAX_TEXT_LENGTH} characters.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ActivityRetrievalError(f"{label} must not contain control characters.")
    return " ".join(value.split()).casefold()


def matches_text(needle: str, values) -> bool:
    return not needle or any(
        needle in " ".join(str(value).split()).casefold() for value in values if value is not None
    )


@dataclass(frozen=True, slots=True)
class ActivityCriteria:
    search: str = ""
    actor: str = ""
    date_from: date | None = None
    date_to: date | None = None

    @classmethod
    def build(cls, *, search=None, actor=None, date_from=None, date_to=None):
        for value in (date_from, date_to):
            if value is not None and type(value) is not date:
                raise ActivityRetrievalError("Date bounds must be calendar dates.")
        if date_from and date_to and date_from > date_to:
            raise ActivityRetrievalError("Date from must not be after Date to.")
        if date_to == date.max:
            raise ActivityRetrievalError("Date to is outside the supported range.")
        return cls(normalized_text(search), normalized_text(actor, "actor"), date_from, date_to)

    def apply_dates(self, queryset):
        zone = institution_zone()
        if self.date_from:
            queryset = queryset.filter(
                occurred_at__gte=datetime.combine(self.date_from, time.min, tzinfo=zone)
            )
        if self.date_to:
            queryset = queryset.filter(
                occurred_at__lt=datetime.combine(
                    self.date_to + timedelta(days=1), time.min, tzinfo=zone
                )
            )
        return queryset


def validate_page(page: int, page_size: int) -> None:
    if type(page) is not int or not 1 <= page <= MAX_PAGE_NUMBER:
        raise ActivityRetrievalError(f"page must be between 1 and {MAX_PAGE_NUMBER}.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ActivityRetrievalError(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")


def bounded_candidates(queryset):
    # One ordered SQL cursor, bounded application work and memory even for sparse/malformed feeds.
    for index, candidate in enumerate(queryset.iterator(chunk_size=256)):
        if index >= MAX_CANDIDATES:
            raise ActivityRetrievalError(
                "Too much activity to scan. Narrow the date or type filters."
            )
        yield candidate


def page_items(items, *, page: int, page_size: int):
    validate_page(page, page_size)
    offset = (page - 1) * page_size
    selected = tuple(islice(items, offset, offset + page_size + 1))
    return selected[:page_size], len(selected) > page_size
