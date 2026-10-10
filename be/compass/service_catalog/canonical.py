"""Stable canonical Service identities shared across backend domains."""

COUNSELING_SERVICE_CODE = "COUNSELING"

# Services COMPASS provisions and requires; they cannot be disabled or lose required eligibility.
SYSTEM_REQUIRED_SERVICE_CODES = frozenset({COUNSELING_SERVICE_CODE})


def is_system_required_service_code(code: str) -> bool:
    return code in SYSTEM_REQUIRED_SERVICE_CODES
