"""Personal inbound unread state; no body selection/decryption or read-state write."""

from django.db.models import OuterRef, Subquery

from . import policy
from .errors import MessagesPermissionDenied
from .models import GuidanceMessage
from .services import _directory


def unread_threads(*, student, limit):
    try:
        policy.require_actor(student)
        query = _directory(policy.authorized_threads(student, manage=True), student)
    except MessagesPermissionDenied:
        return ()
    oldest = (
        GuidanceMessage.objects.filter(
            thread_id=OuterRef("pk"),
            sequence__gt=OuterRef("own_last_read_sequence"),
        )
        .exclude(sender_id=student.pk)
        .order_by("created_at", "id")
        .values("created_at")[:1]
    )
    return tuple(
        query.select_related(None)
        .filter(own_unread_count__gt=0)
        .annotate(
            action_waiting_since=Subquery(oldest),
        )
        .only("id", "kind")
        .order_by("action_waiting_since", "id")[:limit]
    )
