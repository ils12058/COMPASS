"""Retirement preserves existing scope; new references still require active ancestry."""

from django.db.models import Q


def existing_college_q(prefix=""):
    return (Q(**{f"{prefix}is_active": True}) | Q(**{f"{prefix}is_retired": True})) & (
        Q(**{f"{prefix}campus__is_active": True}) | Q(**{f"{prefix}campus__is_retired": True})
    )


def college_available_for_existing_records(college):
    return bool(
        college
        and (college.is_active or college.is_retired)
        and (college.campus.is_active or college.campus.is_retired)
    )
