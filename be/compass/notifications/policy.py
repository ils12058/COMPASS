"""Code-owned Notification policy and event catalog."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NotificationPolicy(StrEnum):
    MANDATORY_SECURITY = "MANDATORY_SECURITY"
    MANDATORY_OPERATIONAL = "MANDATORY_OPERATIONAL"
    OPTIONAL_INFORMATIONAL = "OPTIONAL_INFORMATIONAL"

    @classmethod
    def choices(cls) -> tuple[tuple[str, str], ...]:
        return tuple((item.value, item.value) for item in cls)


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"


class NotificationEvent(StrEnum):
    CALL_SLIP_ISSUED = "call_slip.issued"


@dataclass(frozen=True, slots=True)
class NotificationEventDefinition:
    event: NotificationEvent
    policy: NotificationPolicy
    channels: frozenset[NotificationChannel]
    title: str
    message: str
    email_subject: str
    email_template: str


_EVENT_CATALOG = {
    NotificationEvent.CALL_SLIP_ISSUED: NotificationEventDefinition(
        event=NotificationEvent.CALL_SLIP_ISSUED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=frozenset({NotificationChannel.IN_APP, NotificationChannel.EMAIL}),
        title="New Call Slip",
        message="A Call Slip has been issued to you. Open COMPASS to review the details.",
        email_subject="New COMPASS Call Slip",
        email_template="call_slip_issued",
    ),
}


def get_event_definition(
    event: NotificationEvent | str,
) -> NotificationEventDefinition:
    try:
        normalized = event if isinstance(event, NotificationEvent) else NotificationEvent(event)
        return _EVENT_CATALOG[normalized]
    except (ValueError, KeyError) as exc:
        raise ValueError("unsupported notification event") from exc


def email_allowed_for_policy(
    policy: NotificationPolicy | str,
    *,
    optional_email_enabled: bool,
) -> bool:
    normalized = policy if isinstance(policy, NotificationPolicy) else NotificationPolicy(policy)
    if normalized in {
        NotificationPolicy.MANDATORY_SECURITY,
        NotificationPolicy.MANDATORY_OPERATIONAL,
    }:
        return True
    return optional_email_enabled


__all__ = [
    "NotificationChannel",
    "NotificationEvent",
    "NotificationEventDefinition",
    "NotificationPolicy",
    "email_allowed_for_policy",
    "get_event_definition",
]
