"""Content-free consent hints to current appointment participants, after commit (RT-1A)."""

from __future__ import annotations

import logging
from functools import partial
from uuid import UUID

from django.conf import settings
from django.db import transaction

from compass.realtime.publish import publish_to_user_on_commit

from .services import (
    ECounselingError,
    ECounselingNotPermitted,
    _load_workspace_appointment,
    _require_counselor_relationship,
    _require_student_relationship,
)

logger = logging.getLogger("compass.realtime")


def _recipient_id(appointment_id: UUID, *, student: bool) -> UUID | None:
    # The same eligibility/relationship gates as the canonical read APIs, with both the
    # workspace and consent-list capabilities. Reload at commit; never trust the mutator's
    # earlier assignment or user objects. Historical rooms retain their existing read policy.
    try:
        appointment = _load_workspace_appointment(appointment_id)
    except ECounselingError:
        return None
    actor = appointment.student if student else appointment.provider
    check = _require_student_relationship if student else _require_counselor_relationship
    capabilities = (
        ("ecounseling.view_self", "ecounseling.consent_self")
        if student
        else ("ecounseling.view_assigned", "ecounseling.manage_media_assigned")
    )
    try:
        for capability in capabilities:
            check(actor=actor, appointment=appointment, capability=capability)
    except ECounselingNotPermitted:
        return None
    return actor.pk


def _publish_current(appointment_id: UUID) -> None:
    if not settings.REALTIME_ENABLED:
        return
    try:
        sent = set()
        for student in (True, False):
            # Resolve immediately before each publication. A reassignment during the first
            # recipient's Redis round trip must not preserve the previous Counselor snapshot.
            user_id = _recipient_id(appointment_id, student=student)
            if user_id is None or user_id in sent:
                continue
            publish_to_user_on_commit(
                user_id, "ecounseling.consent.changed", {"appointment_id": appointment_id}
            )
            sent.add(user_id)
    except Exception as exc:
        # A post-commit lookup/programming failure cannot fail an already durable consent
        # operation. Do not log the exception text, recipient, appointment or consent values.
        logger.warning(
            "consent freshness hint was not published",
            extra={"event": "ecounseling_consent_hint_failed", "error_type": type(exc).__name__},
        )


def consent_changed_on_commit(appointment_id: UUID) -> None:
    """One best-effort hint per current recipient, discarded by any enclosing rollback."""

    if settings.REALTIME_ENABLED:
        transaction.on_commit(partial(_publish_current, appointment_id), robust=True)
