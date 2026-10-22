"""One version selector and explicit candidate event/recipient admission.

operational_v1 covers the complete four-family bundle, not Appointment-only
approval. No source facts or arbitrary model/field access are centralized here.
"""

from django.conf import settings

from compass.appointments.email_presentation import (
    APPOINTMENT_EMAIL_EVENTS,
    AppointmentEmailField,
    AppointmentEmailRecipient,
)
from compass.call_slips.email_presentation import (
    CALL_SLIP_EMAIL_EVENTS,
    CallSlipEmailField,
)
from compass.good_moral.email_presentation import (
    GOOD_MORAL_EMAIL_EVENTS,
    GoodMoralEmailField,
)
from compass.group_sessions.email_presentation import (
    GROUP_SESSION_EMAIL_EVENTS,
    GroupSessionEmailField,
)

from .policy import NotificationEvent, NotificationTargetType

APPROVED_OPERATIONAL_POLICY = "operational_v1"

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
APPOINTMENT_EMAIL_FIELD_POLICY = {
    AppointmentEmailRecipient.STUDENT: _STUDENT_FIELDS,
    AppointmentEmailRecipient.CURRENT_COUNSELOR: _STUDENT_FIELDS
    - {
        AppointmentEmailField.COUNSELOR,
        AppointmentEmailField.UPDATED_COUNSELOR,
    },
}
_GROUP_STATUS_FIELDS = frozenset({GroupSessionEmailField.SESSION, GroupSessionEmailField.STATUS})
GROUP_SESSION_EMAIL_FIELD_POLICY = {
    NotificationEvent.GROUP_SESSION_REGISTERED: _GROUP_STATUS_FIELDS
    | {
        GroupSessionEmailField.CURRENT_DATE,
        GroupSessionEmailField.CURRENT_TIME,
        GroupSessionEmailField.MODE,
    },
    NotificationEvent.GROUP_SESSION_RESCHEDULED: _GROUP_STATUS_FIELDS
    | {
        GroupSessionEmailField.UPDATED_DATE,
        GroupSessionEmailField.UPDATED_TIME,
        GroupSessionEmailField.MODE,
    },
    NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED: _GROUP_STATUS_FIELDS,
    NotificationEvent.GROUP_SESSION_CANCELLED: _GROUP_STATUS_FIELDS,
}
GOOD_MORAL_EMAIL_FIELD_POLICY = {
    NotificationEvent.GOOD_MORAL_REQUEST_INITIATED: frozenset(
        {GoodMoralEmailField.REQUEST, GoodMoralEmailField.STATUS}
    ),
    NotificationEvent.GOOD_MORAL_ISSUED: frozenset(
        {GoodMoralEmailField.REQUEST, GoodMoralEmailField.STATUS, GoodMoralEmailField.ISSUED_DATE}
    ),
}
CALL_SLIP_EMAIL_FIELD_POLICY = {
    event: frozenset({CallSlipEmailField.STATUS}) for event in CALL_SLIP_EMAIL_EVENTS
}

OPERATIONAL_EMAIL_EVENTS = (
    GROUP_SESSION_EMAIL_EVENTS | GOOD_MORAL_EMAIL_EVENTS | CALL_SLIP_EMAIL_EVENTS
)
OPERATIONAL_EMAIL_TARGETS = {
    **dict.fromkeys(GROUP_SESSION_EMAIL_EVENTS, NotificationTargetType.GROUP_SESSION),
    **dict.fromkeys(GOOD_MORAL_EMAIL_EVENTS, NotificationTargetType.GOOD_MORAL),
    **dict.fromkeys(CALL_SLIP_EMAIL_EVENTS, NotificationTargetType.CALL_SLIP),
}
APPROVED_EMAIL_EVENTS = APPOINTMENT_EMAIL_EVENTS | OPERATIONAL_EMAIL_EVENTS


def email_disclosure_policy() -> str:
    configured = settings.COMPASS_EMAIL_DISCLOSURE_POLICY
    return (
        APPROVED_OPERATIONAL_POLICY
        if type(configured) is str and configured == APPROVED_OPERATIONAL_POLICY
        else "minimal"
    )
