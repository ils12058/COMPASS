"""Recipient-aware rendering plans and explicit external-disclosure approval."""

from dataclasses import dataclass, field, replace
from enum import StrEnum

from compass.appointments.email_presentation import (
    APPOINTMENT_EMAIL_EVENTS,
    AppointmentEmailEligibility,
    AppointmentEmailFacts,
    AppointmentEmailRecipient,
    resolve_appointment_email_facts,
    scheduled_appointment_email_access,
)
from compass.call_slips.email_presentation import (
    CallSlipEmailFacts,
    CallSlipEmailRecipient,
    resolve_call_slip_email_facts,
)
from compass.good_moral.email_presentation import (
    GOOD_MORAL_EMAIL_EVENTS,
    GoodMoralEmailFacts,
    GoodMoralEmailRecipient,
    resolve_good_moral_email_facts,
)
from compass.group_sessions.email_presentation import (
    GROUP_SESSION_EMAIL_EVENTS,
    GroupSessionEmailFacts,
    GroupSessionEmailRecipient,
    resolve_group_session_email_facts,
)

from .email_disclosure import (
    APPOINTMENT_EMAIL_FIELD_POLICY,
    APPROVED_OPERATIONAL_POLICY,
    CALL_SLIP_EMAIL_FIELD_POLICY,
    GOOD_MORAL_EMAIL_FIELD_POLICY,
    GROUP_SESSION_EMAIL_FIELD_POLICY,
    OPERATIONAL_EMAIL_EVENTS,
    OPERATIONAL_EMAIL_TARGETS,
    email_disclosure_policy,
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


@dataclass(frozen=True, slots=True)
class NotificationEmailPresentation:
    event_code: str
    reason: EmailPresentationReason
    recipient_class: (
        AppointmentEmailRecipient
        | GroupSessionEmailRecipient
        | GoodMoralEmailRecipient
        | CallSlipEmailRecipient
        | None
    ) = None
    target: NotificationEmailTarget | None = field(default=None, repr=False)
    appointment_facts: AppointmentEmailFacts | None = field(default=None, repr=False)
    disclosure_policy: str = "minimal"
    validated_link: NotificationEmailLink | None = field(default=None, repr=False)

    group_session_facts: GroupSessionEmailFacts | None = field(default=None, repr=False)
    good_moral_facts: GoodMoralEmailFacts | None = field(default=None, repr=False)
    call_slip_facts: CallSlipEmailFacts | None = field(default=None, repr=False)

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
    if event in OPERATIONAL_EMAIL_EVENTS:
        return _operational_presentation(notification)
    if (
        email_disclosure_policy() != APPROVED_OPERATIONAL_POLICY
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
        APPROVED_OPERATIONAL_POLICY,
        link,
    )


def _operational_presentation(notification) -> NotificationEmailPresentation:
    event = notification.event_code
    if (
        notification.target_type != OPERATIONAL_EMAIL_TARGETS[event]
        or notification.target_id is None
    ):
        return NotificationEmailPresentation(event, EmailPresentationReason.INVALID_TARGET)
    if event in GROUP_SESSION_EMAIL_EVENTS:
        result = resolve_group_session_email_facts(
            event_code=event,
            source_type=notification.source_type,
            source_id=notification.source_id,
            group_session_id=notification.target_id,
            recipient_id=notification.recipient_id,
        )
        fields = GROUP_SESSION_EMAIL_FIELD_POLICY[event]
    elif event in GOOD_MORAL_EMAIL_EVENTS:
        result = resolve_good_moral_email_facts(
            event_code=event,
            source_type=notification.source_type,
            source_id=notification.source_id,
            request_id=notification.target_id,
            recipient_id=notification.recipient_id,
        )
        fields = GOOD_MORAL_EMAIL_FIELD_POLICY[event]
    else:
        result = resolve_call_slip_email_facts(
            event_code=event,
            source_type=notification.source_type,
            source_id=notification.source_id,
            call_slip_id=notification.target_id,
            recipient_id=notification.recipient_id,
        )
        fields = CALL_SLIP_EMAIL_FIELD_POLICY[event]
    if result.eligibility != "allowed":
        return NotificationEmailPresentation(event, EmailPresentationReason(result.eligibility))
    target = NotificationEmailTarget(notification.target_type, notification.target_id)
    link = build_notification_email_link(target)
    if link.reason != EmailLinkReason.AVAILABLE:
        reason = {
            EmailLinkReason.ORIGIN_MISSING: EmailPresentationReason.ORIGIN_MISSING,
            EmailLinkReason.ORIGIN_INVALID: EmailPresentationReason.ORIGIN_INVALID,
        }.get(link.reason, EmailPresentationReason.INVALID_TARGET)
        return NotificationEmailPresentation(event, reason)
    policy = email_disclosure_policy()
    rich = policy == APPROVED_OPERATIONAL_POLICY and result.facts.rich_allowed
    # Minimal plans retain typed source guards for final equality, but no display rows.
    facts = replace(
        result.facts,
        rows=tuple(row for row in result.facts.rows if row.field in fields) if rich else (),
    )
    plan = NotificationEmailPresentation(
        event,
        EmailPresentationReason.RICH_AVAILABLE if rich else EmailPresentationReason.LINK_AVAILABLE,
        facts.recipient_class,
        target,
        disclosure_policy=policy,
        validated_link=link,
    )
    if type(facts) is GroupSessionEmailFacts:
        return replace(plan, group_session_facts=facts)
    if type(facts) is GoodMoralEmailFacts:
        return replace(plan, good_moral_facts=facts)
    return replace(plan, call_slip_facts=facts)
