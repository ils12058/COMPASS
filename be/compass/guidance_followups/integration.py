"""Read-only work projection and content-free, transactional staff event integration."""

from datetime import timedelta

from django.db.models import Exists, F, OuterRef, Q, Subquery

from compass.accounts.models import User
from compass.realtime.publish import publish_to_user_on_commit

from . import policy
from .errors import FollowUpPermissionDenied
from .models import FollowUpEventType, GuidanceFollowUp, GuidanceFollowUpEvent

# The single definition of "due soon" for Follow-Ups. The Follow-Up report defaults to the same
# horizon, so the number a Counselor sees there matches what My Work treats as time-sensitive.
DUE_SOON_HORIZON_DAYS = 7


def followup_is_time_sensitive(due_at, now) -> bool:
    """Overdue or due within the horizon. Every Follow-Up has a due date, so having one is not
    urgency by itself; only an approaching or passed deadline is."""
    return due_at <= now + timedelta(days=DUE_SOON_HORIZON_DAYS)


def pending_followups(*, actor, limit):
    try:
        actor = policy.current_actor(actor, manage=True)
    except FollowUpPermissionDenied:
        return ()
    return tuple(
        policy.scope(actor, GuidanceFollowUp.objects.filter(status="PENDING"), manage=True)
        .select_related("student")
        .only(
            "id",
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
            "due_at",
            "created_at",
        )
        .order_by("due_at", "id")[:limit]
    )


def material_events():
    return GuidanceFollowUpEvent.objects.filter(
        Q(kind__in=[FollowUpEventType.CREATED, FollowUpEventType.REASSIGNED])
        | (
            Q(kind=FollowUpEventType.UPDATED, old_due_at__isnull=False)
            & ~Q(old_due_at=F("new_due_at"))
        )
    )


def current_events(*, actor):
    try:
        actor = policy.current_actor(actor, manage=True)
    except FollowUpPermissionDenied:
        return GuidanceFollowUpEvent.objects.none()
    authorized = policy.scope(actor, GuidanceFollowUp.objects.filter(status="PENDING"), manage=True)
    latest = (
        material_events()
        .filter(followup_id=OuterRef("followup_id"))
        .order_by("-revision")
        .values("id")[:1]
    )
    return (
        material_events()
        .filter(followup_id__in=authorized.values("pk"))
        .alias(_latest_material_id=Subquery(latest))
        .filter(pk=F("_latest_material_id"))
    )


def followup_notification_is_current(notification):
    actor = User.objects.filter(pk=notification.recipient_id).first()
    return bool(
        actor
        and current_events(actor=actor)
        .filter(pk=notification.source_id, followup_id=notification.target_id)
        .exists()
    )


def scope_current_followup_notifications(queryset, *, actor):
    events = current_events(actor=actor)
    return queryset.alias(
        _current_followup=Exists(
            events.filter(pk=OuterRef("source_id"), followup_id=OuterRef("target_id"))
        )
    ).filter(~Q(source_type="guidance_followup_event") | Q(_current_followup=True))


def event_committed_intent(item, event):
    # Hints carry no record/source identity. Old owners only receive a cache eviction hint.
    recipients = {item.assigned_to_id, event.old_assignee_id} - {None}
    for recipient_id in recipients:
        publish_to_user_on_commit(recipient_id, "followups.changed")
    if not material_events().filter(pk=event.pk).exists():
        return
    from compass.notifications.policy import NotificationEvent
    from compass.notifications.services import create_notification_for_event

    actor = item.assigned_to
    if not current_events(actor=actor).filter(pk=event.pk).exists():
        return
    code = (
        NotificationEvent.FOLLOWUP_ASSIGNED
        if event.kind == FollowUpEventType.CREATED
        else NotificationEvent.FOLLOWUP_REASSIGNED
        if event.kind == FollowUpEventType.REASSIGNED
        else NotificationEvent.FOLLOWUP_DUE_CHANGED
    )
    create_notification_for_event(
        recipient=actor,
        event=code,
        source_type="guidance_followup_event",
        source_id=event.pk,
        target_type="GUIDANCE_FOLLOW_UP",
        target_id=item.pk,
    )
