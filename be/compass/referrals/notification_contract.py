"""Faculty receipt/closure notices through the existing Notification lifecycle.

Only canonical transition facts and the current Faculty owner are admitted.
The catalog owns generic copy; this module never projects confidential source content.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from compass.accounts.models import User
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.referrals.faculty_rules import active_colleges, faculty_can_track
from compass.referrals.models import Referral

SOURCE_TYPE = "faculty_referral_administration"
_NOTICE_EVENTS = {
    "RECEIVED_BY_GCO": NotificationEvent.FACULTY_REFERRAL_RECEIVED,
    "ADMINISTRATIVELY_CLOSED": NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED,
}


@dataclass(frozen=True)
class FacultyAdministrativeNoticeIntent:
    recipient_id: UUID
    referral_id: UUID
    reference_code: str
    event: str
    event_at: datetime
    route: str
    deduplication_key: str


def _admitted_referrals(recipient, now):
    if not faculty_can_track(recipient):
        return Referral.objects.none()
    return Referral.objects.filter(
        submission_channel="FACULTY_PORTAL",
        submitted_by=recipient,
        student_college_at_submission_id__in=active_colleges().values("pk"),
        voided_at__isnull=True,
        acknowledged_by__isnull=False,
        received_at__gte=F("submitted_at"),
        received_at__lte=now,
    )


def _for_event(queryset, event, now):
    if event == "RECEIVED_BY_GCO":
        return queryset.filter(administratively_closed_at__isnull=True)
    if event == "ADMINISTRATIVELY_CLOSED":
        return queryset.filter(
            administratively_closed_by__isnull=False,
            administratively_closed_at__gte=F("received_at"),
            administratively_closed_at__lte=now,
        )
    return queryset.none()


def prepare_candidate_intent(*, referral_id, event, now=None):
    """Re-resolve current ownership, access and the exact transition."""
    if event not in _NOTICE_EVENTS:
        return None
    at = now or timezone.now()
    identity = Referral.objects.filter(pk=referral_id).values("submitted_by_id").first()
    if identity is None:
        return None
    recipient = User.objects.select_related("role").filter(pk=identity["submitted_by_id"]).first()
    item = _for_event(_admitted_referrals(recipient, at), event, at).filter(pk=referral_id).first()
    if item is None:
        return None
    event_at = item.received_at if event == "RECEIVED_BY_GCO" else item.administratively_closed_at
    return FacultyAdministrativeNoticeIntent(
        recipient_id=recipient.pk,
        referral_id=item.pk,
        reference_code=item.reference_code,
        event=event,
        event_at=event_at,
        route=f"/portal/faculty/referrals/{item.pk}",
        deduplication_key=f"faculty-referral:{item.pk}:{event}:{event_at.isoformat()}",
    )


def create_faculty_notice(*, referral_id, event):
    """Called inside the successful transition transaction; kicks run on commit."""
    from compass.notifications.services import create_notification_for_event

    intent = prepare_candidate_intent(referral_id=referral_id, event=event)
    if intent is None:
        return None
    # Each transition is immutable and happens once; the catalog event + Referral UUID
    # is its stable per-recipient logical identity under notif_logical_event_uniq.
    return create_notification_for_event(
        recipient=User.objects.get(pk=intent.recipient_id),
        event=_NOTICE_EVENTS[intent.event],
        source_type=SOURCE_TYPE,
        source_id=intent.referral_id,
        target_type=NotificationTargetType.FACULTY_REFERRAL,
        target_id=intent.referral_id,
    )


def faculty_notice_is_current(notification, *, now=None):
    event = next(
        (name for name, code in _NOTICE_EVENTS.items() if code == notification.event_code), None
    )
    if (
        event is None
        or notification.source_type != SOURCE_TYPE
        or notification.target_type != NotificationTargetType.FACULTY_REFERRAL
        or notification.target_id is None
        or notification.source_id != notification.target_id
    ):
        return False
    intent = prepare_candidate_intent(referral_id=notification.source_id, event=event, now=now)
    return intent is not None and intent.recipient_id == notification.recipient_id


def scope_current_faculty_notice_notifications(queryset, *, actor):
    """Keep pagination/counts truthful with source-owned SQL, without per-row reads."""
    if not queryset.filter(recipient=actor, source_type=SOURCE_TYPE).exists():
        return queryset
    now = timezone.now()
    recipient = User.objects.select_related("role").filter(pk=actor.pk).first()
    admitted = _admitted_referrals(recipient, now)
    allowed = Q()
    for event, code in _NOTICE_EVENTS.items():
        allowed |= Q(
            event_code=code,
            target_type=NotificationTargetType.FACULTY_REFERRAL,
            target_id=F("source_id"),
            source_id__in=_for_event(admitted, event, now).values("pk"),
        )
    return queryset.filter(~Q(source_type=SOURCE_TYPE) | allowed)


URGENT_SOURCE_TYPE = "referral_urgency"


def create_urgent_notices(*, referral_id):
    """Synchronous in-app/outbox insert; existing workers are kicked on commit."""
    from compass.notifications.services import create_notification_for_event
    from compass.referrals.urgency import pending_urgent_referrals

    recipients = User.objects.select_related("role").filter(
        is_active=True, role__code__in={"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"}
    )
    for recipient in recipients:
        item = pending_urgent_referrals(actor=recipient).filter(pk=referral_id).first()
        if item is not None:
            create_notification_for_event(
                recipient=recipient,
                event=NotificationEvent.REFERRAL_URGENT,
                source_type=URGENT_SOURCE_TYPE,
                source_id=item.urgency_change_id,
                target_type=NotificationTargetType.REFERRAL,
                target_id=item.pk,
            )


def urgent_notice_is_current(notification):
    from compass.referrals.urgency import pending_urgent_referrals

    return (
        notification.source_type == URGENT_SOURCE_TYPE
        and notification.event_code == NotificationEvent.REFERRAL_URGENT
        and notification.target_type == NotificationTargetType.REFERRAL
        and pending_urgent_referrals(actor=notification.recipient)
        .filter(pk=notification.target_id, urgency_change_id=notification.source_id)
        .exists()
    )


def scope_current_urgent_notifications(queryset, *, actor):
    from compass.referrals.urgency import pending_urgent_referrals

    admitted = pending_urgent_referrals(actor=actor).filter(
        pk=OuterRef("target_id"), urgency_change_id=OuterRef("source_id")
    )
    return queryset.annotate(current_urgent_referral=Exists(admitted)).filter(
        ~Q(source_type=URGENT_SOURCE_TYPE)
        | Q(
            current_urgent_referral=True,
            event_code=NotificationEvent.REFERRAL_URGENT,
            target_type=NotificationTargetType.REFERRAL,
        )
    )
