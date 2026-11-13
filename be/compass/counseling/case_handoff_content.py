"""Strict case-specific envelopes using the existing Handoff keyring, with no legacy alias."""

from django.core.exceptions import ImproperlyConfigured

from compass.confidential_data import crypto
from compass.confidential_data.errors import ConfidentialDataUnavailable
from compass.counseling.handoff_content import keyring

from .case_continuity_rules import CaseContinuityError, fail

MAX_NARRATIVE = 12000
SECTIONS = (
    "context_and_purpose",
    "support_and_progress",
    "continuing_considerations",
    "receiver_next_steps",
)


def validate_sections(values, *, submitted=False):
    if not isinstance(values, dict) or set(values) != set(SECTIONS):
        fail("handoff_content_invalid", "Use the four structured handoff sections.", 422)
    for value in values.values():
        if not isinstance(value, str) or "\x00" in value:
            fail("handoff_content_invalid", "Review the handoff text.", 422)
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            fail("handoff_content_invalid", "Review the handoff text.", 422)
    if sum(map(len, values.values())) > MAX_NARRATIVE:
        fail(
            "handoff_content_invalid",
            "The handoff narrative may contain at most 12,000 characters.",
            422,
        )
    if submitted and (
        not values["context_and_purpose"].strip() or not values["receiver_next_steps"].strip()
    ):
        fail(
            "handoff_content_required",
            "Include the concern and purpose, and what the receiver should do next.",
            422,
        )
    return values


def binding(item):
    return {
        "document_kind": "COUNSELING_CASE_HANDOFF_V1",
        "case_handoff_id": str(item.pk),
        "transfer_id": str(item.transfer_id),
        "case_id": str(item.case_id),
        "student_id": str(item.student_id),
        "author_id": str(item.author_id),
        "receiving_counselor_id": str(item.receiving_counselor_id),
        "plan_digest": item.plan_digest,
    }


def encrypt(item, sections, work):
    try:
        return crypto.encrypt_bound_json(
            keyring=keyring(),
            schema_version=1,
            binding=binding(item),
            payload={"sections": validate_sections(sections), "work": work},
        )
    except (ConfidentialDataUnavailable, ImproperlyConfigured, ValueError):
        fail(
            "handoff_unavailable",
            "The protected handoff is unavailable. Try again when access is restored.",
            503,
        )


def read(item):
    try:
        payload = crypto.decrypt_bound_json(
            item.content_ciphertext, keyring=keyring(), schema_version=1, binding=binding(item)
        )
        if set(payload) != {"sections", "work"} or not isinstance(payload["work"], dict):
            raise ConfidentialDataUnavailable(reason="malformed")
        validate_sections(payload["sections"], submitted=item.state == "SUBMITTED")
        if set(payload["work"]) != {"tasks", "appointments"}:
            raise ConfidentialDataUnavailable(reason="malformed")
        from .case_handoff_schemas import CaseHandoffWork

        CaseHandoffWork.model_validate(payload["work"])
        return payload
    except (ConfidentialDataUnavailable, ImproperlyConfigured, CaseContinuityError, ValueError):
        fail(
            "handoff_unavailable",
            "The protected handoff is unavailable. Try again when access is restored.",
            503,
        )


def addendum_binding(item):
    return {
        "document_kind": "COUNSELING_CASE_HANDOFF_ADDENDUM_V1",
        "case_handoff_addendum_id": str(item.pk),
        "case_handoff_id": str(item.handoff_id),
        "author_id": str(item.author_id),
    }


def validate_addendum(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_NARRATIVE
        or "\x00" in value
    ):
        fail(
            "handoff_content_invalid",
            "Give the addendum meaningful text, at most 12,000 characters.",
            422,
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        fail("handoff_content_invalid", "Review the addendum text.", 422)
    return value


def encrypt_addendum(item, value):
    try:
        return crypto.encrypt_bound_json(
            keyring=keyring(),
            schema_version=1,
            binding=addendum_binding(item),
            payload={"content": validate_addendum(value)},
        )
    except (ConfidentialDataUnavailable, ImproperlyConfigured, ValueError):
        fail("handoff_unavailable", "The protected addendum is unavailable.", 503)


def read_addendum(item):
    try:
        payload = crypto.decrypt_bound_json(
            item.content_ciphertext,
            keyring=keyring(),
            schema_version=1,
            binding=addendum_binding(item),
        )
        if set(payload) != {"content"}:
            raise ConfidentialDataUnavailable(reason="malformed")
        return validate_addendum(payload["content"])
    except (ConfidentialDataUnavailable, ImproperlyConfigured, CaseContinuityError, ValueError):
        fail("handoff_unavailable", "The protected addendum is unavailable.", 503)
