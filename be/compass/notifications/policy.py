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


class NotificationTargetType(StrEnum):
    """Closed set of in-app destinations a Notification may point at."""

    GUIDANCE_FOLLOW_UP = "GUIDANCE_FOLLOW_UP"
    CASE_TRANSFER = "CASE_TRANSFER"
    CASE_COVERAGE = "CASE_COVERAGE"
    SESSION_PROPOSAL = "SESSION_PROPOSAL"
    COUNSELING_CASE = "COUNSELING_CASE"
    ACCOUNT_SECURITY = "ACCOUNT_SECURITY"
    APPOINTMENT = "APPOINTMENT"
    CALL_SLIP = "CALL_SLIP"
    STUDENT_SESSION_SUMMARY = "STUDENT_SESSION_SUMMARY"
    E_COUNSELING = "E_COUNSELING"
    EXIT_INTERVIEW = "EXIT_INTERVIEW"
    FEEDBACK = "FEEDBACK"
    GOOD_MORAL = "GOOD_MORAL"
    GROUP_SESSION = "GROUP_SESSION"
    GRADUATE_TRACER = "GRADUATE_TRACER"
    INVENTORY = "INVENTORY"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW"
    FACULTY_REFERRAL = "FACULTY_REFERRAL"


class NotificationEvent(StrEnum):
    CASE_TRANSFER_REVIEW = "counseling.case_transfer.review"
    CASE_COVERAGE_REVIEW = "counseling.case_coverage.review"
    SESSION_PROPOSAL_RECEIVED = "counseling.session_proposal.received"
    SESSION_PROPOSAL_DECIDED = "counseling.session_proposal.decided"
    FACULTY_REFERRAL_RECEIVED = "referral.received_by_guidance_office"
    FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED = "referral.administratively_closed"
    FOLLOWUP_ASSIGNED = "guidance_followup.assigned"
    FOLLOWUP_REASSIGNED = "guidance_followup.reassigned"
    FOLLOWUP_DUE_CHANGED = "guidance_followup.due_changed"
    CALL_SLIP_ISSUED = "call_slip.issued"
    APPOINTMENT_SCHEDULED = "appointment.scheduled"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_RESCHEDULED = "appointment.rescheduled"
    APPOINTMENT_REASSIGNED = "appointment.reassigned"
    APPOINTMENT_REMINDER_24H = "appointment.reminder_24h"
    APPOINTMENT_REMINDER_3H = "appointment.reminder_3h"
    APPOINTMENT_REMINDER_MANUAL = "appointment.reminder_manual"
    GROUP_SESSION_REGISTERED = "group_session.registered"
    GROUP_SESSION_REGISTRATION_CANCELLED = "group_session.registration_cancelled"
    GROUP_SESSION_CANCELLED = "group_session.cancelled"
    GROUP_SESSION_RESCHEDULED = "group_session.rescheduled"
    CALL_SLIP_VOIDED = "call_slip.voided"
    GOOD_MORAL_REQUEST_INITIATED = "good_moral.request_initiated"
    GOOD_MORAL_ISSUED = "good_moral.issued"
    EXIT_INTERVIEW_REOPENED = "exit_interview.reopened"
    INVENTORY_REOPENED = "inventory.reopened"
    STUDENT_SESSION_SUMMARY_PUBLISHED = "counseling.student_session_summary.published"
    ROUTINE_INTERVIEW_INTAKE_READY = "routine_interview.intake_ready"
    ECOUNSELING_CONSENT_REQUESTED = "ecounseling.consent.requested"
    GRADUATE_TRACER_REMINDER = "graduate_tracer.reminder"
    FEEDBACK_INVITATION = "feedback.invitation"
    SECURITY_PASSWORD_RESET = "security.password.reset"
    SECURITY_PASSWORD_CHANGED = "security.password.changed"
    SECURITY_MFA_DISABLED = "security.mfa.disabled"
    SECURITY_RECOVERY_CODES_REGENERATED = "security.recovery_codes.regenerated"
    SECURITY_MFA_ADMIN_RESET = "security.mfa.admin_reset"
    SECURITY_ACCOUNT_ACCESS_CHANGED = "security.account_access.changed"


FACULTY_REFERRAL_NOTICE_EVENTS = frozenset(
    {
        NotificationEvent.FACULTY_REFERRAL_RECEIVED,
        NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED,
    }
)


@dataclass(frozen=True, slots=True)
class NotificationEventDefinition:
    event: NotificationEvent
    policy: NotificationPolicy
    channels: frozenset[NotificationChannel]
    title: str
    message: str
    email_subject: str
    email_template: str


_IN_APP_ONLY = frozenset({NotificationChannel.IN_APP})
_EMAIL_CHANNELS = frozenset({NotificationChannel.IN_APP, NotificationChannel.EMAIL})


_EVENT_CATALOG = {
    # NS-1 D4: content-free. No case, purpose, Counselor note or time appears in the notice.
    NotificationEvent.SESSION_PROPOSAL_RECEIVED: NotificationEventDefinition(
        event=NotificationEvent.SESSION_PROPOSAL_RECEIVED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_IN_APP_ONLY,
        title="Session time proposed",
        message="Your Counselor proposed a session time. Please choose one.",
        email_subject="",
        email_template="",
    ),
    NotificationEvent.SESSION_PROPOSAL_DECIDED: NotificationEventDefinition(
        event=NotificationEvent.SESSION_PROPOSAL_DECIDED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_IN_APP_ONLY,
        title="Session proposal answered",
        message="A Student answered your session proposal. Open COMPASS to review it.",
        email_subject="",
        email_template="",
    ),
    NotificationEvent.CASE_COVERAGE_REVIEW: NotificationEventDefinition(
        event=NotificationEvent.CASE_COVERAGE_REVIEW,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_IN_APP_ONLY,
        title="Case coverage review",
        message=(
            "A temporary case coverage arrangement needs your review. Open COMPASS to review it."
        ),
        email_subject="",
        email_template="",
    ),
    NotificationEvent.CASE_TRANSFER_REVIEW: NotificationEventDefinition(
        event=NotificationEvent.CASE_TRANSFER_REVIEW,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_IN_APP_ONLY,
        title="Case transfer review",
        message="A case transfer needs your review. Open COMPASS to review the arrangement.",
        email_subject="",
        email_template="",
    ),
    NotificationEvent.GRADUATE_TRACER_REMINDER: NotificationEventDefinition(
        event=NotificationEvent.GRADUATE_TRACER_REMINDER,
        policy=NotificationPolicy.OPTIONAL_INFORMATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Graduate Tracer reminder",
        message="Tell the Guidance Office how you're doing in the Graduate Tracer survey.",
        email_subject="COMPASS Graduate Tracer reminder",
        email_template="graduate_tracer_reminder",
    ),
    NotificationEvent.FACULTY_REFERRAL_RECEIVED: NotificationEventDefinition(
        event=NotificationEvent.FACULTY_REFERRAL_RECEIVED,
        policy=NotificationPolicy.OPTIONAL_INFORMATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Referral received",
        message="The Guidance Office received your Referral. Open COMPASS to review it.",
        email_subject="COMPASS Referral received by the Guidance and Counseling Office",
        email_template="faculty_referral_received",
    ),
    NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED: NotificationEventDefinition(
        event=NotificationEvent.FACULTY_REFERRAL_ADMINISTRATIVELY_CLOSED,
        policy=NotificationPolicy.OPTIONAL_INFORMATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Referral administratively closed",
        message="The Guidance Office closed your Referral record. Open COMPASS to review it.",
        email_subject="COMPASS Referral administratively closed",
        email_template="faculty_referral_administratively_closed",
    ),
    **{
        event: NotificationEventDefinition(
            event=event,
            policy=NotificationPolicy.MANDATORY_OPERATIONAL,
            channels=_EMAIL_CHANNELS,
            title="Guidance Follow-Up update",
            message=("Your Guidance Follow-Up has an update. Sign in to review it."),
            email_subject="COMPASS Guidance Follow-Up update",
            email_template="guidance_followup",
        )
        for event in (
            NotificationEvent.FOLLOWUP_ASSIGNED,
            NotificationEvent.FOLLOWUP_REASSIGNED,
            NotificationEvent.FOLLOWUP_DUE_CHANGED,
        )
    },
    NotificationEvent.CALL_SLIP_ISSUED: NotificationEventDefinition(
        event=NotificationEvent.CALL_SLIP_ISSUED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="New Call Slip",
        message="You have a new Call Slip. Open COMPASS to review it.",
        email_subject="New COMPASS Call Slip",
        email_template="call_slip_issued",
    ),
    NotificationEvent.APPOINTMENT_SCHEDULED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_SCHEDULED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment scheduled",
        message=("Your Appointment is booked. Sign in to review the details."),
        email_subject="COMPASS Appointment scheduled",
        email_template="appointment_scheduled",
    ),
    NotificationEvent.APPOINTMENT_CANCELLED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_CANCELLED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment cancelled",
        message=("Your Appointment is cancelled. Sign in to check your next steps."),
        email_subject="COMPASS Appointment cancelled",
        email_template="appointment_cancelled",
    ),
    NotificationEvent.APPOINTMENT_RESCHEDULED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_RESCHEDULED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment rescheduled",
        message=("Your Appointment time changed. Sign in to check the new schedule."),
        email_subject="COMPASS Appointment rescheduled",
        email_template="appointment_rescheduled",
    ),
    NotificationEvent.APPOINTMENT_REASSIGNED: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_REASSIGNED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment assignment updated",
        message=("Your Appointment assignment changed. Sign in to check the details."),
        email_subject="COMPASS Appointment assignment updated",
        email_template="appointment_reassigned",
    ),
    NotificationEvent.APPOINTMENT_REMINDER_24H: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_REMINDER_24H,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment reminder",
        message="You have an upcoming Appointment. Sign in to check the details.",
        email_subject="COMPASS Appointment reminder",
        email_template="appointment_reminder",
    ),
    NotificationEvent.APPOINTMENT_REMINDER_3H: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_REMINDER_3H,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment reminder",
        message="You have an upcoming Appointment. Sign in to check the details.",
        email_subject="COMPASS Appointment reminder",
        email_template="appointment_reminder",
    ),
    NotificationEvent.APPOINTMENT_REMINDER_MANUAL: NotificationEventDefinition(
        event=NotificationEvent.APPOINTMENT_REMINDER_MANUAL,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Appointment reminder",
        message="You have an upcoming Appointment. Sign in to check the details.",
        email_subject="COMPASS Appointment reminder",
        email_template="appointment_reminder",
    ),
    NotificationEvent.GROUP_SESSION_REGISTERED: NotificationEventDefinition(
        event=NotificationEvent.GROUP_SESSION_REGISTERED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Group Session registration confirmed",
        message=("You're registered for a Group Session. Sign in to check the details."),
        email_subject="COMPASS Group Session registration confirmed",
        email_template="group_session_update",
    ),
    NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED: NotificationEventDefinition(
        event=NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Group Session registration cancelled",
        message=("Your Group Session registration is cancelled. Sign in to check the details."),
        email_subject="COMPASS Group Session registration cancelled",
        email_template="group_session_update",
    ),
    NotificationEvent.GROUP_SESSION_CANCELLED: NotificationEventDefinition(
        event=NotificationEvent.GROUP_SESSION_CANCELLED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Group Session cancelled",
        message=("Your Group Session is cancelled. Sign in to check the details."),
        email_subject="COMPASS Group Session cancelled",
        email_template="group_session_update",
    ),
    NotificationEvent.GROUP_SESSION_RESCHEDULED: NotificationEventDefinition(
        event=NotificationEvent.GROUP_SESSION_RESCHEDULED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Group Session updated",
        message=("Your Group Session has changed. Sign in to check the new schedule."),
        email_subject="COMPASS Group Session updated",
        email_template="group_session_update",
    ),
    NotificationEvent.CALL_SLIP_VOIDED: NotificationEventDefinition(
        event=NotificationEvent.CALL_SLIP_VOIDED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Call Slip withdrawn",
        message=("You no longer need to act on this Call Slip. Sign in to check the record."),
        email_subject="COMPASS Call Slip withdrawn",
        email_template="call_slip_voided",
    ),
    NotificationEvent.GOOD_MORAL_REQUEST_INITIATED: NotificationEventDefinition(
        event=NotificationEvent.GOOD_MORAL_REQUEST_INITIATED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Good Moral Certificate request started",
        message=(
            "The Guidance Office started your Good Moral Certificate request. Sign in to "
            "check the details."
        ),
        email_subject="COMPASS Good Moral Certificate request started",
        email_template="good_moral_request_initiated",
    ),
    NotificationEvent.GOOD_MORAL_ISSUED: NotificationEventDefinition(
        event=NotificationEvent.GOOD_MORAL_ISSUED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Good Moral Certificate issued",
        message=("You can now review your Good Moral Certificate. Sign in to check it."),
        email_subject="COMPASS Good Moral Certificate issued",
        email_template="good_moral_issued",
    ),
    NotificationEvent.EXIT_INTERVIEW_REOPENED: NotificationEventDefinition(
        event=NotificationEvent.EXIT_INTERVIEW_REOPENED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Exit Interview reopened",
        message=("You can now correct your Exit Interview. Sign in to review it."),
        email_subject="COMPASS Exit Interview reopened",
        email_template="exit_interview_reopened",
    ),
    NotificationEvent.INVENTORY_REOPENED: NotificationEventDefinition(
        event=NotificationEvent.INVENTORY_REOPENED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Individual Inventory reopened",
        message=(
            "You can now correct your annual Individual Inventory. Sign in to edit and resubmit it."
        ),
        email_subject="COMPASS Individual Inventory reopened",
        email_template="inventory_reopened",
    ),
    NotificationEvent.STUDENT_SESSION_SUMMARY_PUBLISHED: NotificationEventDefinition(
        event=NotificationEvent.STUDENT_SESSION_SUMMARY_PUBLISHED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Student Session Summary available",
        message="You have a Student Session Summary to review. Sign in to check it.",
        email_subject="COMPASS Student Session Summary available",
        email_template="student_session_summary_published",
    ),
    NotificationEvent.ROUTINE_INTERVIEW_INTAKE_READY: NotificationEventDefinition(
        event=NotificationEvent.ROUTINE_INTERVIEW_INTAKE_READY,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_IN_APP_ONLY,
        title="Routine Interview intake ready",
        message=("Complete your Routine Interview intake in COMPASS before continuing."),
        email_subject="",
        email_template="",
    ),
    NotificationEvent.ECOUNSELING_CONSENT_REQUESTED: NotificationEventDefinition(
        event=NotificationEvent.ECOUNSELING_CONSENT_REQUESTED,
        policy=NotificationPolicy.MANDATORY_OPERATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Review E-Counseling consent",
        message=(
            "You have an E-Counseling consent request to review. Sign in to record your decision."
        ),
        email_subject="COMPASS Review E-Counseling consent",
        email_template="ecounseling_consent_requested",
    ),
    NotificationEvent.FEEDBACK_INVITATION: NotificationEventDefinition(
        event=NotificationEvent.FEEDBACK_INVITATION,
        policy=NotificationPolicy.OPTIONAL_INFORMATIONAL,
        channels=_EMAIL_CHANNELS,
        title="Feedback invitation",
        message=(
            "You can now give feedback on your recent Guidance Office Service. Sign in to "
            "complete the feedback or Client Satisfaction Measurement form."
        ),
        email_subject="COMPASS Feedback invitation",
        email_template="feedback_invitation",
    ),
    NotificationEvent.SECURITY_PASSWORD_RESET: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_PASSWORD_RESET,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Password reset",
        message=(
            "Your COMPASS password was reset. Didn't expect this change? Contact your IT "
            "Administrator."
        ),
        email_subject="COMPASS Password reset",
        email_template="security_password_reset",
    ),
    NotificationEvent.SECURITY_PASSWORD_CHANGED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_PASSWORD_CHANGED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Password changed",
        message=(
            "Your COMPASS password was changed. Didn't expect this change? Contact your "
            "IT Administrator."
        ),
        email_subject="COMPASS Password changed",
        email_template="security_password_changed",
    ),
    NotificationEvent.SECURITY_MFA_DISABLED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_MFA_DISABLED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Multi-factor authentication disabled",
        message=(
            "Multi-factor authentication was disabled on your COMPASS account. Didn't "
            "expect this change? Contact your IT Administrator."
        ),
        email_subject="COMPASS Multi-factor authentication disabled",
        email_template="security_mfa_disabled",
    ),
    NotificationEvent.SECURITY_RECOVERY_CODES_REGENERATED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_RECOVERY_CODES_REGENERATED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="New recovery codes",
        message=(
            "New multi-factor authentication recovery codes were generated for your "
            "COMPASS account. Didn't expect this change? Contact your IT Administrator."
        ),
        email_subject="COMPASS New recovery codes",
        email_template="security_recovery_codes_regenerated",
    ),
    NotificationEvent.SECURITY_MFA_ADMIN_RESET: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_MFA_ADMIN_RESET,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Multi-factor authentication reset",
        message=(
            "Multi-factor authentication was reset for your COMPASS account by an "
            "administrator. You may need to set it up again."
        ),
        email_subject="COMPASS Multi-factor authentication reset",
        email_template="security_mfa_admin_reset",
    ),
    NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED: NotificationEventDefinition(
        event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        policy=NotificationPolicy.MANDATORY_SECURITY,
        channels=_EMAIL_CHANNELS,
        title="Account access changed",
        message=(
            "Your COMPASS account access or permissions were changed by an administrator. "
            "Didn't expect this change? Contact your IT Administrator."
        ),
        email_subject="COMPASS Account access changed",
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
