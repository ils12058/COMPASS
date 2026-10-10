"""Explicit lock-screen policy. Never reuse authenticated Notification text here."""

from enum import StrEnum

from .policy import NotificationEvent


class PushDecision(StrEnum):
    PUSH = "PUSH"
    IN_APP_ONLY = "IN_APP_ONLY"
    POLICY_REVIEW = "POLICY_REVIEW"


PUSH_POLICY: dict[NotificationEvent, tuple[PushDecision, str]] = {
    NotificationEvent.CALL_SLIP_ISSUED: (PushDecision.PUSH, "You have a new Call Slip."),
    NotificationEvent.CALL_SLIP_VOIDED: (PushDecision.PUSH, "You have a Call Slip update."),
    NotificationEvent.APPOINTMENT_SCHEDULED: (PushDecision.PUSH, "You have an appointment update."),
    NotificationEvent.APPOINTMENT_CANCELLED: (PushDecision.PUSH, "You have an appointment update."),
    NotificationEvent.APPOINTMENT_RESCHEDULED: (
        PushDecision.PUSH,
        "You have an appointment update.",
    ),
    NotificationEvent.APPOINTMENT_REASSIGNED: (
        PushDecision.PUSH,
        "You have an appointment update.",
    ),
    NotificationEvent.GOOD_MORAL_ISSUED: (
        PushDecision.PUSH,
        "Your Good Moral request has an update.",
    ),
    NotificationEvent.ECOUNSELING_CONSENT_REQUESTED: (
        PushDecision.PUSH,
        "You have a new request to review in COMPASS.",
    ),
    NotificationEvent.SECURITY_PASSWORD_RESET: (
        PushDecision.PUSH,
        "Your COMPASS account security changed.",
    ),
    NotificationEvent.SECURITY_PASSWORD_CHANGED: (
        PushDecision.PUSH,
        "Your COMPASS account security changed.",
    ),
    NotificationEvent.SECURITY_MFA_DISABLED: (
        PushDecision.PUSH,
        "Your COMPASS account security changed.",
    ),
    NotificationEvent.SECURITY_RECOVERY_CODES_REGENERATED: (
        PushDecision.PUSH,
        "Your COMPASS account security changed.",
    ),
    NotificationEvent.SECURITY_MFA_ADMIN_RESET: (
        PushDecision.PUSH,
        "Your COMPASS account security changed.",
    ),
    NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED: (
        PushDecision.PUSH,
        "Your COMPASS account security changed.",
    ),
    NotificationEvent.EXIT_INTERVIEW_REOPENED: (PushDecision.IN_APP_ONLY, ""),
    NotificationEvent.INVENTORY_REOPENED: (PushDecision.IN_APP_ONLY, ""),
    NotificationEvent.COUNSELING_SHARED_SUMMARY_PUBLISHED: (PushDecision.IN_APP_ONLY, ""),
    NotificationEvent.ROUTINE_INTERVIEW_INTAKE_READY: (PushDecision.IN_APP_ONLY, ""),
    NotificationEvent.FEEDBACK_INVITATION: (PushDecision.IN_APP_ONLY, ""),
}


def push_body_for(event_code: str) -> str | None:
    try:
        decision, body = PUSH_POLICY[NotificationEvent(event_code)]
    except (ValueError, KeyError):
        return None
    return body if decision == PushDecision.PUSH else None
