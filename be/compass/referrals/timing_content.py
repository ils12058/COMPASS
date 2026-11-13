"""Bound v1 scheduling envelopes under the existing Referral content keyring."""

from datetime import UTC

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .confidential_content import ReferralConfidentialContentUnavailable, _keyring
from .errors import InvalidReferralInput
from .timing_models import ReferralSchedulingVerification
from .timing_rules import validate_timing_content

TIMING_SCHEMA_VERSION = 1


def _binding(row):
    verification = isinstance(row, ReferralSchedulingVerification)
    return {
        "envelope_type": "referral_scheduling_verification"
        if verification
        else "referral_scheduling_statement",
        "referral_id": str(row.referral_id),
        "timing_record_id": str(row.pk),
        "answer_kind": row.answer_kind,
        "window_count": str(row.window_count),
        "author_id": str(row.author_id),
        "created_at": row.created_at.astimezone(UTC).isoformat(),
        "provenance_code": row.confirmation_source if verification else row.submission_channel,
    }


def write_timing_content(row, payload):
    if not row._state.adding:
        raise InvalidReferralInput("Referral timing records cannot be updated.")
    row.content_ciphertext = crypto.encrypt_bound_json(
        keyring=_keyring(),
        schema_version=TIMING_SCHEMA_VERSION,
        binding=_binding(row),
        payload=payload,
    )


def read_timing_content(row):
    try:
        payload = crypto.decrypt_bound_json(
            row.content_ciphertext,
            keyring=_keyring(),
            schema_version=TIMING_SCHEMA_VERSION,
            binding=_binding(row),
        )
        if not isinstance(payload, dict) or set(payload) != {"windows", "note"}:
            raise InvalidReferralInput("Invalid timing envelope.")
        content = validate_timing_content(
            answer_kind=row.answer_kind,
            windows=payload["windows"],
            note=payload["note"],
            verification=isinstance(row, ReferralSchedulingVerification),
            historical=True,
        )
        if row.window_count != len(content["windows"]):
            raise InvalidReferralInput("Invalid timing envelope count.")
        return content
    except (ConfidentialDataUnavailable, InvalidReferralInput) as exc:
        raise ReferralConfidentialContentUnavailable(
            referral_id=row.referral_id,
            reason=exc.reason if isinstance(exc, ConfidentialDataUnavailable) else "malformed",
        ) from None
