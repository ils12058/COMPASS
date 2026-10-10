"""Bounded structural reply work; assignment is ownership, never an access grant."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, F, Min, OuterRef, Q, Subquery

from . import policy
from .errors import MessagesPermissionDenied
from .models import GuidanceMessage, ThreadKind, ThreadStatus


@dataclass(frozen=True, slots=True)
class ReplyNeededSummary:
    count: int
    oldest_waiting_since: datetime | None


def _reply_needed_queryset(actor):
    try:
        actor = policy.current_actor(actor)
        policy.require_actor(actor, manage=True, staff_only=True)
        rows = policy.authorized_threads(actor, manage=True)
    except MessagesPermissionDenied:
        return None
    latest_sender = GuidanceMessage.objects.filter(
        thread_id=OuterRef("pk"), sequence=OuterRef("last_sequence")
    ).values("sender_id")[:1]
    return (
        rows.filter(status=ThreadStatus.OPEN)
        .filter(
            Q(kind=ThreadKind.OFFICE, assigned_to_id=actor.pk)
            | Q(kind=ThreadKind.COUNSELING, counselor_id=actor.pk)
        )
        .alias(latest_sender_id=Subquery(latest_sender))
        .filter(latest_sender_id=F("student_id"))
    )


def reply_needed_summary(*, actor) -> ReplyNeededSummary | None:
    rows = _reply_needed_queryset(actor)
    if rows is None:
        return None
    return ReplyNeededSummary(
        **rows.aggregate(count=Count("pk"), oldest_waiting_since=Min("last_message_at"))
    )


def reply_needed_threads(*, actor, limit):
    rows = _reply_needed_queryset(actor)
    if rows is None:
        return ()
    return tuple(
        rows.select_related("student")
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
