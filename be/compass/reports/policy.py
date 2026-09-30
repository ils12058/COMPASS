"""Shared advisory disclosure policy for aggregate reports."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

REPORT_SMALL_POPULATION_WARNING_THRESHOLD = 5

DISCLOSURE_WARNING_MESSAGE = (
    "This report includes results from a small population or category. "
    "Use and share these results carefully because some aggregate results "
    "may be easier to associate with individual respondents."
)


class ReportDisclosureWarningCode(StrEnum):
    SMALL_POPULATION = "SMALL_POPULATION"
    SMALL_CELL = "SMALL_CELL"


def _warning(code: ReportDisclosureWarningCode) -> dict[str, str]:
    return {"code": code.value, "message": DISCLOSURE_WARNING_MESSAGE}


def build_disclosure_warnings(
    *,
    population: int,
    released_counts: Iterable[int],
) -> list[dict[str, str]]:
    """Return one general advisory for the final aggregate result.

    Zero populations and zero-count cells do not create disclosure warnings.
    Exact report values are never changed by this policy.
    """

    if population < 0:
        raise ValueError("Report population cannot be negative.")

    if population == 0:
        return []

    threshold = REPORT_SMALL_POPULATION_WARNING_THRESHOLD
    if population < threshold:
        return [_warning(ReportDisclosureWarningCode.SMALL_POPULATION)]

    for count in released_counts:
        if count < 0:
            raise ValueError("Released aggregate counts cannot be negative.")
        if 0 < count < threshold:
            return [_warning(ReportDisclosureWarningCode.SMALL_CELL)]

    return []


__all__ = [
    "DISCLOSURE_WARNING_MESSAGE",
    "REPORT_SMALL_POPULATION_WARNING_THRESHOLD",
    "ReportDisclosureWarningCode",
    "build_disclosure_warnings",
]
