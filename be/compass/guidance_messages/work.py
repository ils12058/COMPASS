"""Bounded structural reply work; assignment is ownership, never an access grant."""

from django.db.models import F, OuterRef, Q, Subquery

from . import policy
from .errors import MessagesPermissionDenied
from .models import GuidanceMessage, ThreadKind, ThreadStatus


def reply_needed_threads(*, actor, limit):
    try:
        actor = policy.current_actor(actor)
        policy.require_actor(actor, manage=True, staff_only=True)
        rows = policy.authorized_threads(actor, manage=True)
    except MessagesPermissionDenied:
        return ()
    latest_sender = GuidanceMessage.objects.filter(
        thread_id=OuterRef("pk"), sequence=OuterRef("last_sequence")
    ).values("sender_id")[:1]
    return tuple(
        rows.filter(status=ThreadStatus.OPEN)
        .filter(
            Q(kind=ThreadKind.OFFICE, assigned_to_id=actor.pk)
            | Q(kind=ThreadKind.COUNSELING, counselor_id=actor.pk)
        )
        .alias(latest_sender_id=Subquery(latest_sender))
        .filter(latest_sender_id=F("student_id"))
        .select_related("student")
        .only(
            "id",
            "kind",
            "last_message_at",
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by("last_message_at", "id")[:limit]
    )
