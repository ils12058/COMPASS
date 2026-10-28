"""Strict adapters for three explicit domain variants, never arbitrary source data."""

from compass.call_slips.email_presentation import (
    CALL_SLIP_EMAIL_EVENTS,
    CallSlipEmailDetail,
    CallSlipEmailFacts,
    CallSlipEmailRecipient,
)
from compass.good_moral.email_presentation import (
    GOOD_MORAL_EMAIL_EVENTS,
    GoodMoralEmailDetail,
    GoodMoralEmailFacts,
    GoodMoralEmailRecipient,
)
from compass.group_sessions.email_presentation import (
    GROUP_SESSION_EMAIL_EVENTS,
    GroupSessionEmailDetail,
    GroupSessionEmailFacts,
    GroupSessionEmailRecipient,
)

from .email_disclosure import (
    APPROVED_OPERATIONAL_POLICY,
    CALL_SLIP_EMAIL_FIELD_POLICY,
    GOOD_MORAL_EMAIL_FIELD_POLICY,
    GROUP_SESSION_EMAIL_FIELD_POLICY,
    OPERATIONAL_EMAIL_EVENTS,
    email_disclosure_policy,
)
from .email_links import EmailLinkReason, NotificationEmailLink
from .policy import NotificationEvent

_GROUP_COPY = {
    NotificationEvent.GROUP_SESSION_REGISTERED: (
        "Group Session registration confirmed",
        "Your Group Session registration is confirmed.",
    ),
    NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED: (
        "Group Session registration cancelled",
        "Your Group Session registration has been cancelled.",
    ),
    NotificationEvent.GROUP_SESSION_CANCELLED: (
        "Group Session cancelled",
        "The Group Session has been cancelled. "
        "There is no active attendance instruction for this session.",
    ),
    NotificationEvent.GROUP_SESSION_RESCHEDULED: (
        "Group Session rescheduled",
        "Your Group Session has been rescheduled. Review the latest schedule in COMPASS.",
    ),
}


def operational_email_context(event_code, presentation):
    variants = (
        presentation.group_session_facts,
        presentation.good_moral_facts,
        presentation.call_slip_facts,
    )
    if event_code not in OPERATIONAL_EMAIL_EVENTS:
        if any(facts is not None for facts in variants):
            raise ValueError("unsupported operational email facts")
        return {}
    if presentation.target is None:
        if any(facts is not None for facts in variants):
            raise ValueError("operational facts require an authorized action")
        return {}
    if (
        sum(facts is not None for facts in variants) != 1
        or presentation.appointment_facts is not None
    ):
        raise ValueError("invalid operational email variant")
    if event_code in GROUP_SESSION_EMAIL_EVENTS:
        facts = presentation.group_session_facts
        if type(facts) is not GroupSessionEmailFacts:
            raise ValueError("invalid group session email facts")
        identifier, recipient, detail_type = (
            facts.group_session_id,
            GroupSessionEmailRecipient.STUDENT,
            GroupSessionEmailDetail,
        )
        fields, action = (
            GROUP_SESSION_EMAIL_FIELD_POLICY[event_code],
            "View Group Session in COMPASS",
        )
    elif event_code in GOOD_MORAL_EMAIL_EVENTS:
        facts = presentation.good_moral_facts
        if type(facts) is not GoodMoralEmailFacts:
            raise ValueError("invalid good moral email facts")
        identifier, recipient, detail_type = (
            facts.request_id,
            GoodMoralEmailRecipient.STUDENT,
            GoodMoralEmailDetail,
        )
        fields, action = (
            GOOD_MORAL_EMAIL_FIELD_POLICY[event_code],
            "View Good Moral request in COMPASS",
        )
    elif event_code in CALL_SLIP_EMAIL_EVENTS:
        facts = presentation.call_slip_facts
        if type(facts) is not CallSlipEmailFacts:
            raise ValueError("invalid call slip email facts")
        identifier, recipient, detail_type = (
            facts.call_slip_id,
            CallSlipEmailRecipient.STUDENT,
            CallSlipEmailDetail,
        )
        fields, action = CALL_SLIP_EMAIL_FIELD_POLICY[event_code], "View Call Slip in COMPASS"
    rich = presentation.reason == "rich_available"
    if (
        facts.event_code != event_code
        or identifier != presentation.target.target_id
        or type(presentation.recipient_class) is not type(recipient)
        or presentation.recipient_class != recipient
        or type(facts.recipient_class) is not type(recipient)
        or facts.recipient_class != recipient
        or type(presentation.validated_link) is not NotificationEmailLink
        or presentation.validated_link.reason != EmailLinkReason.AVAILABLE
        or presentation.validated_link.url is None
        or type(facts.rows) is not tuple
        or any(type(row) is not detail_type or row.field not in fields for row in facts.rows)
        or len({row.field for row in facts.rows}) != len(facts.rows)
        or (
            rich
            and (
                not facts.rows
                or not facts.rich_allowed
                or presentation.disclosure_policy != APPROVED_OPERATIONAL_POLICY
                or email_disclosure_policy() != APPROVED_OPERATIONAL_POLICY
            )
        )
        or (not rich and (presentation.reason != "link_available" or facts.rows))
        or presentation.disclosure_policy != email_disclosure_policy()
    ):
        raise ValueError("unapproved operational email facts")
    # Code-owned copy only; the link itself was independently rebuilt by delivery.
    context = {"action_label": action}
    if event_code in _GROUP_COPY:
        context["operational_heading"], context["operational_intro"] = _GROUP_COPY[event_code]
    if rich:
        context["email_details"] = facts.rows
    return context
