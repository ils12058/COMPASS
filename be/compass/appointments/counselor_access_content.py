"""Encrypted envelope for a Student's confidential counselor-change reason (ADR-120).

Uses the established web-only Counselor Handoff keyring with a distinct document kind and
row-specific binding. Workers never hold this keyring and never read this field.
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable
from compass.counseling.handoff_content import keyring

MAX_REASON_LENGTH = 2000


class CounselorBookingReasonError(RuntimeError):
    pass


class CounselorBookingReasonInvalid(CounselorBookingReasonError):
    pass


class CounselorBookingReasonUnavailable(CounselorBookingReasonError):
    pass


def validate_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    if not isinstance(reason, str) or len(reason) > MAX_REASON_LENGTH or "\x00" in reason:
        raise CounselorBookingReasonInvalid(
            f"The reason must be plain text of at most {MAX_REASON_LENGTH} characters."
        )
    try:
        reason.encode("utf-8")
    except UnicodeEncodeError:
        raise CounselorBookingReasonInvalid("Review the reason text and try again.") from None
    cleaned = reason.strip()
    return cleaned if cleaned else None


def binding(item) -> dict[str, str]:
    return {
        "document_kind": "COUNSELOR_BOOKING_REQUEST_REASON_V1",
        "request_id": str(item.pk),
        "student_id": str(item.student_id),
    }


def encrypt_reason(item, reason: str | None) -> str | None:
    cleaned = validate_reason(reason)
    if cleaned is None:
        return None
    try:
        return crypto.encrypt_bound_json(
            keyring=keyring(),
            schema_version=1,
            binding=binding(item),
            payload={"reason": cleaned},
        )
    except (ConfidentialDataUnavailable, ImproperlyConfigured, ValueError):
        raise CounselorBookingReasonUnavailable(
            "Protected request text is temporarily unavailable. Try again later."
        ) from None


def read_reason(item) -> str | None:
    if item.reason_ciphertext is None:
        return None
    try:
        payload = crypto.decrypt_bound_json(
            item.reason_ciphertext,
            keyring=keyring(),
            schema_version=1,
            binding=binding(item),
        )
        if set(payload) != {"reason"} or not isinstance(payload["reason"], str):
            raise ConfidentialDataUnavailable(reason="malformed")
        return validate_reason(payload["reason"])
    except (
        ConfidentialDataUnavailable,
        ImproperlyConfigured,
        CounselorBookingReasonInvalid,
        ValueError,
    ):
        raise CounselorBookingReasonUnavailable(
            "The protected reason for this request is unavailable right now."
        ) from None
