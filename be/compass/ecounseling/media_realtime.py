"""Post-commit, content-free hints for explicit observable media transitions (RT-1B)."""

import logging
from functools import partial
from uuid import UUID

from django.conf import settings
from django.db import transaction

from compass.realtime.publish import publish_to_user_on_commit

from .realtime_recipients import workspace_participant_id

logger = logging.getLogger("compass.realtime")


def _publish_current(appointment_id: UUID) -> None:
    if not settings.REALTIME_ENABLED:
        return
    try:
        sent = set()
        for student in (True, False):
            # Reload each participant immediately before their Redis publication. Workspace
            # viewing does not require consent decisions, media management or file access.
            user_id = workspace_participant_id(appointment_id, student=student)
            if user_id is None or user_id in sent:
                continue
            publish_to_user_on_commit(
                user_id, "ecounseling.media.changed", {"appointment_id": appointment_id}
            )
            sent.add(user_id)
    except Exception as exc:
        logger.warning(
            "media freshness hint was not published",
            extra={"event": "ecounseling_media_hint_failed", "error_type": type(exc).__name__},
        )


def media_changed_on_commit(appointment_id: UUID) -> None:
    if settings.REALTIME_ENABLED:
        transaction.on_commit(partial(_publish_current, appointment_id), robust=True)
