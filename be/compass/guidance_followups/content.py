"""Explicit, authenticated Follow-Up content; decryption never happens in ORM access."""

from __future__ import annotations

from django.conf import settings

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable

from .errors import FollowUpContentUnavailable, FollowUpInvalid

SCHEMA_VERSION = 1
MAX_DESCRIPTION = 4000
MAX_REMARKS = 4000
MAX_OUTCOME = 4000


def _keyring():
    value = getattr(settings, "GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS", ())
    if not value:
        raise FollowUpContentUnavailable("Protected Follow-Up content is unavailable.")
    try:
        return crypto.parse_fernet_keyring(value, setting="GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS")
    except ValueError:
        raise FollowUpContentUnavailable("Protected Follow-Up content is unavailable.") from None


def _text(value, label, limit, *, required=False):
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise FollowUpInvalid(f"{label} contains unsupported text.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise FollowUpInvalid(f"{label} contains unsupported text.") from None
    if required and not value.strip():
        raise FollowUpInvalid(f"{label} is required.")
    return value


def _binding(followup_id, section, event_id=None):
    values = {"followup_id": str(followup_id), "section": section}
    if event_id is not None:
        values["event_id"] = str(event_id)
    return values


def encrypt_text(followup_id, section, text, *, event_id=None, required=False):
    limit = (
        MAX_DESCRIPTION
        if section == "description"
        else MAX_OUTCOME
        if section == "outcome"
        else MAX_REMARKS
    )
    validated = _text(text, section, limit, required=required)
    try:
        return crypto.encrypt_bound_json(
            keyring=_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=_binding(followup_id, section, event_id),
            payload={"text": validated},
        )
    except ConfidentialDataUnavailable:
        raise FollowUpContentUnavailable("Protected Follow-Up content is unavailable.") from None


def decrypt_text(followup_id, section, token, *, event_id=None):
    try:
        payload = crypto.decrypt_bound_json(
            token,
            keyring=_keyring(),
            schema_version=SCHEMA_VERSION,
            binding=_binding(followup_id, section, event_id),
        )
        if set(payload) != {"text"}:
            raise FollowUpContentUnavailable("Protected Follow-Up content is unavailable.")
        limit = (
            MAX_DESCRIPTION
            if section == "description"
            else MAX_OUTCOME
            if section == "outcome"
            else MAX_REMARKS
        )
        return _text(payload["text"], section, limit)
    except (ConfidentialDataUnavailable, FollowUpInvalid, UnicodeError):
        raise FollowUpContentUnavailable("Protected Follow-Up content is unavailable.") from None


def rotate_text(followup_id, section, token, *, event_id=None):
    decrypt_text(followup_id, section, token, event_id=event_id)
    return crypto.reencrypt_with_primary_key(token, keyring=_keyring())
