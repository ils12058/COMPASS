"""Closed list orderings (ADR-090).

Each domain owns its ordering enum, the default for the population its filters select, and what
each value means in SQL, always ending in a unique tie-breaker so pages never overlap. This module
only parses a requested value against that closed enum; it never turns a field name into an ORDER
BY.
"""

from __future__ import annotations

from enum import StrEnum


def parse_ordering[E: StrEnum](
    value: object,
    choices: type[E],
    *,
    default: E,
    error: type[Exception],
) -> E:
    """Return ``value`` as a member of ``choices``, or ``default`` when none was requested."""

    if value is None:
        return default
    raw = value.value if isinstance(value, StrEnum) else value
    try:
        return choices(raw)
    except (TypeError, ValueError):
        allowed = ", ".join(member.value for member in choices)
        raise error(f"ordering must be one of {allowed}.") from None
