"""Recipient-aware rendering plans and explicit external-disclosure approval."""

from dataclasses import dataclass, field, replace
from enum import StrEnum

from django.conf import settings

from compass.appointments.email_presentation import (
    APPOINTMENT_EMAIL_EVENTS,
    AppointmentEmailEligibility,
    AppointmentEmailFacts,
    AppointmentEmailField,
    AppointmentEmailRecipient,
    resolve_appointment_email_facts,
    scheduled_appointment_email_access,
)

from .email_links import (
    EmailLinkReason,
    NotificationEmailLink,
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
    RICH_AVAILABLE = "rich_available"
    INVALID_SOURCE = "invalid_source"
    SOURCE_SUPERSEDED = "source_superseded"
    PROVENANCE_UNAVAILABLE = "provenance_unavailable"
    RECIPIENT_MINIMAL = "recipient_minimal"


APPROVED_APPOINTMENT_POLICY = "operational_v1"
_STUDENT_FIELDS = frozenset(
    {
        AppointmentEmailField.REFERENCE,
        AppointmentEmailField.SERVICE,
        AppointmentEmailField.DATE,
        AppointmentEmailField.TIME,
        AppointmentEmailField.PREVIOUS_DATE,
        AppointmentEmailField.PREVIOUS_TIME,
        AppointmentEmailField.UPDATED_DATE,
        AppointmentEmailField.UPDATED_TIME,
        AppointmentEmailField.COUNSELOR,
        AppointmentEmailField.UPDATED_COUNSELOR,
        AppointmentEmailField.MODE,
    }
)
_COUNSELOR_FIELDS = _STUDENT_FIELDS - {
    AppointmentEmailField.COUNSELOR,
    AppointmentEmailField.UPDATED_COUNSELOR,
}
APPOINTMENT_EMAIL_FIELD_POLICY = {
    AppointmentEmailRecipient.STUDENT: _STUDENT_FIELDS,
    AppointmentEmailRecipient.CURRENT_COUNSELOR: _COUNSELOR_FIELDS,
}


def appointment_email_disclosure_policy() -> str:
    configured = settings.APPOINTMENT_EMAIL_DISCLOSURE_POLICY
    return (
        APPROVED_APPOINTMENT_POLICY
        if type(configured) is str and configured == (APPROVED_APPOINTMENT_POLICY)
        else "minimal"
    )


@dataclass(frozen=True, slots=True)
class NotificationEmailPresentation:
    event_code: str
    reason: EmailPresentationReason
    recipient_class: AppointmentEmailRecipient | None = None
    target: NotificationEmailTarget | None = field(default=None, repr=False)
    appointment_facts: AppointmentEmailFacts | None = field(default=None, repr=False)
    disclosure_policy: str = "minimal"
    validated_link: NotificationEmailLink | None = field(default=None, repr=False)

    @property
    def suppress(self) -> bool:
        return self.reason in {
            EmailPresentationReason.SOURCE_STALE,
            EmailPresentationReason.SOURCE_SUPERSEDED,
        }


def _minimal_presentation(notification) -> NotificationEmailPresentation:
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
        event,
        EmailPresentationReason.LINK_AVAILABLE,
        access.recipient_class,
        target,
        validated_link=link,
    )


def resolve_notification_email_presentation(notification) -> NotificationEmailPresentation:
    event = notification.event_code
    if (
        appointment_email_disclosure_policy() != APPROVED_APPOINTMENT_POLICY
        or event not in APPOINTMENT_EMAIL_EVENTS
    ):
        return _minimal_presentation(notification)
    if (
        notification.target_type != NotificationTargetType.APPOINTMENT
        or notification.target_id is None
    ):
        return NotificationEmailPresentation(event, EmailPresentationReason.INVALID_TARGET)
    result = resolve_appointment_email_facts(
        event_code=event,
        source_type=notification.source_type,
        source_id=notification.source_id,
        appointment_id=notification.target_id,
        recipient_id=notification.recipient_id,
    )
    if (
        event == NotificationEvent.APPOINTMENT_SCHEDULED
        and (
            result.link_allowed
            or result.eligibility == AppointmentEmailEligibility.RECIPIENT_MINIMAL
        )
        and result.facts is None
    ):
        return _minimal_presentation(notification)
    if result.eligibility != AppointmentEmailEligibility.ALLOWED:
        return NotificationEmailPresentation(
            event, EmailPresentationReason(result.eligibility), result.recipient_class
        )
    target = NotificationEmailTarget(NotificationTargetType.APPOINTMENT, notification.target_id)
    link = build_notification_email_link(target)
    if link.reason != EmailLinkReason.AVAILABLE:
        reason = {
            EmailLinkReason.ORIGIN_MISSING: EmailPresentationReason.ORIGIN_MISSING,
            EmailLinkReason.ORIGIN_INVALID: EmailPresentationReason.ORIGIN_INVALID,
        }.get(link.reason, EmailPresentationReason.INVALID_TARGET)
        return NotificationEmailPresentation(event, reason)
    fields = APPOINTMENT_EMAIL_FIELD_POLICY.get(result.recipient_class, frozenset())
    facts = replace(
        result.facts, rows=tuple(row for row in result.facts.rows if row.field in fields)
    )
    return NotificationEmailPresentation(
        event,
        EmailPresentationReason.RICH_AVAILABLE,
        result.recipient_class,
        target,
        facts,
        APPROVED_APPOINTMENT_POLICY,
        link,
    )
