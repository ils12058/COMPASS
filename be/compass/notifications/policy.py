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
    APPOINTMENT_SCHEDULED = "appointment.scheduled"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_RESCHEDULED = "appointment.rescheduled"
    APPOINTMENT_REASSIGNED = "appointment.reassigned"
    CALL_SLIP_VOIDED = "call_slip.voided"
    GOOD_MORAL_ISSUED = "good_moral.issued"
    EXIT_INTERVIEW_REOPENED = "exit_interview.reopened"
    INVENTORY_REOPENED = "inventory.reopened"
    COUNSELING_SHARED_SUMMARY_PUBLISHED = "counseling.shared_summary.published"
    ECOUNSELING_CONSENT_REQUESTED = "ecounseling.consent.requested"
    FEEDBACK_INVITATION = "feedback.invitation"
    SECURITY_PASSWORD_RESET = "security.password.reset"
    SECURITY_PASSWORD_CHANGED = "security.password.changed"
    SECURITY_MFA_DISABLED = "security.mfa.disabled"
    SECURITY_RECOVERY_CODES_REGENERATED = "security.recovery_codes.regenerated"
    SECURITY_MFA_ADMIN_RESET = "security.mfa.admin_reset"
    SECURITY_ACCOUNT_ACCESS_CHANGED = "security.account_access.changed"


@dataclass(frozen=True, slots=True)
class NotificationEventDefinition:
    event: NotificationEvent
    policy: NotificationPolicy
    channels: frozenset[NotificationChannel]
    title: str
    message: str
    email_subject: str
    email_template: str


_EMAIL_CHANNELS = frozenset({NotificationChannel.IN_APP, NotificationChannel.EMAIL})


_EVENT_CATALOG = {
    NotificationEvent.CALL_SLIP_ISSUED: NotificationEventDefinition(
        event=NotificationEvent.CALL_SLIP_ISSUED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="New Call Slip",
        message="A Call Slip has been issued to you. Open COMPASS to review the details.",
        email_subject="New COMPASS Call Slip",
        email_template="call_slip_issued",
    ),
    NotificationEvent.APPOINTMENT_SCHEDULED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_SCHEDULED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment Scheduled",
        message=(
            "A COMPASS Appointment has been scheduled. Sign in to COMPASS to review the details."
        ),
        email_subject="COMPASS Appointment Scheduled",
        email_template="appointment_scheduled",
    ),
    NotificationEvent.APPOINTMENT_CANCELLED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_CANCELLED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment Cancelled",
        message=(
            "A COMPASS Appointment has been cancelled. Sign in to COMPASS to review the details."
        ),
        email_subject="COMPASS Appointment Cancelled",
        email_template="appointment_cancelled",
    ),
    NotificationEvent.APPOINTMENT_RESCHEDULED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_RESCHEDULED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment Rescheduled",
        message=(
            "A COMPASS Appointment has been rescheduled. "
            "Sign in to COMPASS to review the updated schedule."
        ),
        email_subject="COMPASS Appointment Rescheduled",
        email_template="appointment_rescheduled",
    ),
    NotificationEvent.APPOINTMENT_REASSIGNED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_REASSIGNED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment Assignment Updated",
        message=(
            "A COMPASS Appointment assignment has changed. "
            "Sign in to COMPASS to review the current details."
        ),
        email_subject="COMPASS Appointment Assignment Updated",
        email_template="appointment_reassigned",
    ),
    NotificationEvent.CALL_SLIP_VOIDED: NotificationEventDefinition(
        event=NotificationEvent.CALL_SLIP_VOIDED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Call Slip Withdrawn",
        message=(
            "A COMPASS Call Slip issued to you has been withdrawn. "
            "Sign in to COMPASS to review the current record."
        ),
        email_subject="COMPASS Call Slip Withdrawn",
        email_template="call_slip_voided",
    ),
    NotificationEvent.GOOD_MORAL_ISSUED: NotificationEventDefinition(
        event=NotificationEvent.GOOD_MORAL_ISSUED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Good Moral Certificate Issued",
        message=(
            "Your Good Moral certificate has been issued in COMPASS. "
            "Sign in to COMPASS to review it."
        ),
        email_subject="COMPASS Good Moral Certificate Issued",
        email_template="good_moral_issued",
    ),
    NotificationEvent.EXIT_INTERVIEW_REOPENED: NotificationEventDefinition(
        event=NotificationEvent.EXIT_INTERVIEW_REOPENED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Exit Interview Reopened",
        message=(
            "Your Exit Interview has been reopened for correction. Sign in to COMPASS to review it."
        ),
        email_subject="COMPASS Exit Interview Reopened",
        email_template="exit_interview_reopened",
    ),
    NotificationEvent.INVENTORY_REOPENED: NotificationEventDefinition(
        event=NotificationEvent.INVENTORY_REOPENED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Individual Inventory Reopened",
        message=(
            "Your annual Individual Inventory has been reopened for correction. "
            "You may edit and resubmit it in COMPASS."
        ),
        email_subject="COMPASS Individual Inventory Reopened",
        email_template="inventory_reopened",
    ),
    NotificationEvent.COUNSELING_SHARED_SUMMARY_PUBLISHED: NotificationEventDefinition(
        event=NotificationEvent.COUNSELING_SHARED_SUMMARY_PUBLISHED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Counseling Shared Summary Available",
        message="A Counseling Shared Summary is now available in COMPASS. Sign in to review it.",
        email_subject="COMPASS Counseling Shared Summary Available",
        email_template="counseling_shared_summary_published",
    ),
    NotificationEvent.ECOUNSELING_CONSENT_REQUESTED: NotificationEventDefinition(
        event=NotificationEvent.ECOUNSELING_CONSENT_REQUESTED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="E-Counseling Consent Review Required",
        message="One or more E-Counseling consent decisions require your review in COMPASS.",
        email_subject="COMPASS E-Counseling Consent Review Required",
        email_template="ecounseling_consent_requested",
    ),
    NotificationEvent.FEEDBACK_INVITATION: NotificationEventDefinition(
        event=NotificationEvent.FEEDBACK_INVITATION,
        policy=NotificationPolicy.OPTIONAL_INFORMATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Feedback Invitation",
        message=(
            "Your recent GCO service has been completed. "
            "You may submit the appropriate Feedback/CSM form in COMPASS."
        ),
        email_subject="COMPASS Feedback Invitation",
        email_template="feedback_invitation",
    ),
    NotificationEvent.SECURITY_PASSWORD_RESET: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_PASSWORD_RESET,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Password Reset",
        message=(
            "Your COMPASS password was reset. If you did not perform this action, "
            "contact the appropriate university office immediately."
        ),
        email_subject="COMPASS Password Reset",
        email_template="security_password_reset",
    ),
    NotificationEvent.SECURITY_PASSWORD_CHANGED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_PASSWORD_CHANGED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Password Changed",
        message=(
            "Your COMPASS password was changed. If you did not perform this action, "
            "contact the appropriate university office immediately."
        ),
        email_subject="COMPASS Password Changed",
        email_template="security_password_changed",
    ),
    NotificationEvent.SECURITY_MFA_DISABLED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_MFA_DISABLED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Multi-Factor Authentication Disabled",
        message=(
            "Multi-factor authentication was disabled on your COMPASS account. "
            "If you did not perform this action, contact the appropriate university "
            "office immediately."
        ),
        email_subject="COMPASS Multi-Factor Authentication Disabled",
        email_template="security_mfa_disabled",
    ),
    NotificationEvent.SECURITY_RECOVERY_CODES_REGENERATED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_RECOVERY_CODES_REGENERATED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="MFA Recovery Codes Regenerated",
        message=(
            "New MFA recovery codes were generated for your COMPASS account. "
            "If you did not perform this action, review your account security."
        ),
        email_subject="COMPASS MFA Recovery Codes Regenerated",
        email_template="security_recovery_codes_regenerated",
    ),
    NotificationEvent.SECURITY_MFA_ADMIN_RESET: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_MFA_ADMIN_RESET,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Multi-Factor Authentication Reset",
        message=(
            "Multi-factor authentication was reset for your COMPASS account by an administrator. "
            "You may need to configure MFA again."
        ),
        email_subject="COMPASS Multi-Factor Authentication Reset",
        email_template="security_mfa_admin_reset",
    ),
    NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Account Access Changed",
        message=(
            "Your COMPASS account access or permissions were changed by an administrator. "
            "Sign in to review your account and contact the appropriate office if this change "
            "is unexpected."
        ),
        email_subject="COMPASS Account Access Changed",
        email_template="security_account_access_changed",
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
