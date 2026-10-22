"""Recipient-aware, allowlisted rendering plan. No raw domain values reach mail."""

from dataclasses import dataclass, field
from enum import StrEnum

from compass.appointments.email_presentation import (
    AppointmentEmailEligibility,
    AppointmentEmailRecipient,
    scheduled_appointment_email_access,
)

from .email_links import (
    EmailLinkReason,
    NotificationEmailTarget,
    build_notification_email_link,
)
from .policy import NotificationEvent, NotificationTargetType


class EmailPresentationReason(StrEnum):
    GENERIC_EVENT = "generic_event"
    INVALID_TARGET = "invalid_target"
    SOURCE_MISSING = "source_missing"
    SOURCE_STALE = "source_stale"
    RECIPIENT_DENIED = "recipient_denied"
    ORIGIN_MISSING = "origin_missing"
    ORIGIN_INVALID = "origin_invalid"
    LINK_AVAILABLE = "link_available"


@dataclass(frozen=True, slots=True)
class NotificationEmailPresentation:
    event_code: str
    reason: EmailPresentationReason
    recipient_class: AppointmentEmailRecipient | None = None
    target: NotificationEmailTarget | None = field(default=None, repr=False)

    @property
    def suppress(self) -> bool:
        return self.reason == EmailPresentationReason.SOURCE_STALE


def resolve_notification_email_presentation(notification) -> NotificationEmailPresentation:
    event = notification.event_code
    if event != NotificationEvent.APPOINTMENT_SCHEDULED:
        return NotificationEmailPresentation(event, EmailPresentationReason.GENERIC_EVENT)
    target = NotificationEmailTarget(notification.target_type, notification.target_id)
    if (
        notification.source_type != "appointment"
        or notification.source_id != notification.target_id
        or notification.target_id is None
        or notification.target_type != NotificationTargetType.APPOINTMENT
    ):
        return NotificationEmailPresentation(event, EmailPresentationReason.INVALID_TARGET)
    access = scheduled_appointment_email_access(
        appointment_id=notification.source_id, recipient_id=notification.recipient_id
    )
    if access.eligibility != AppointmentEmailEligibility.ALLOWED:
        return NotificationEmailPresentation(event, EmailPresentationReason(access.eligibility))
    link = build_notification_email_link(target)
    if link.reason != EmailLinkReason.AVAILABLE:
        reason = {
            EmailLinkReason.ORIGIN_MISSING: EmailPresentationReason.ORIGIN_MISSING,
            EmailLinkReason.ORIGIN_INVALID: EmailPresentationReason.ORIGIN_INVALID,
        }.get(link.reason, EmailPresentationReason.INVALID_TARGET)
        return NotificationEmailPresentation(event, reason)
    return NotificationEmailPresentation(
        event, EmailPresentationReason.LINK_AVAILABLE, access.recipient_class, target
    )
