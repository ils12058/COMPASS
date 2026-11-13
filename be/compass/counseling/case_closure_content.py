"""Closure-note envelope using the established Handoff keyring and a distinct row binding."""

from datetime import UTC

from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable
from compass.counseling.handoff_content import keyring

from .case_services import CounselingCaseError, CounselingCaseInvalid

MAX_NOTE = 4000


class ClosureContentUnavailable(CounselingCaseError):
    code = "counseling_case_closure_note_unavailable"
    status = 503


def validate_note(note):
    if note is None:
        return None
    if not isinstance(note, str) or len(note) > MAX_NOTE or "\x00" in note:
        raise CounselingCaseInvalid(
            "The closure note must be plain text of at most 4,000 characters."
        )
    try:
        note.encode("utf-8")
    except UnicodeEncodeError:
        raise CounselingCaseInvalid("Review the closure note text.") from None
    return note if note.strip() else None


def binding(item):
    return {
        "document_kind": "COUNSELING_CASE_CLOSURE_NOTE_V1",
        "closure_id": str(item.pk),
        "case_id": str(item.case_id),
        "closed_by_id": str(item.closed_by_id),
        "closed_at": item.closed_at.astimezone(UTC).isoformat(),
        "reason": item.reason,
        "outcome": item.outcome,
    }


def encrypt(item, note):
    try:
        return crypto.encrypt_bound_json(
            keyring=keyring(),
            schema_version=1,
            binding=binding(item),
            payload={"note": validate_note(note)},
        )
    except (ConfidentialDataUnavailable, ImproperlyConfigured, ValueError):
        raise ClosureContentUnavailable("The protected closure note is unavailable.") from None


def read(item):
    if item.content_ciphertext is None:
        return None
    try:
        payload = crypto.decrypt_bound_json(
            item.content_ciphertext, keyring=keyring(), schema_version=1, binding=binding(item)
        )
        if set(payload) != {"note"} or not isinstance(payload["note"], str):
            raise ConfidentialDataUnavailable(reason="malformed")
        return validate_note(payload["note"])
    except (ConfidentialDataUnavailable, ImproperlyConfigured, CounselingCaseInvalid, ValueError):
        raise ClosureContentUnavailable("The protected closure note is unavailable.") from None
