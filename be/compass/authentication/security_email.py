"""Code-owned security email sent directly by authentication tasks, outside Notifications."""

from __future__ import annotations

from compass.common.email import RenderedEmail, render_email
from compass.common.institutional_time import institution_timezone_name, to_institution_time

SECURITY_CODE_SUBJECT = "Your COMPASS security code"
EMAIL_CHANGED_SUBJECT = "COMPASS sign-in email changed"


def render_security_code_email(code: str, *, purpose: str | None = None) -> RenderedEmail:
    """Render the transient Email OTP in memory only; never log, store, or link the result."""

    instructions = (
        "Sign in to COMPASS, open Account security, then choose Verify email to finish "
        "changing your sign-in email."
        if purpose == "email_change"
        else "Use this code in COMPASS to continue."
    )

    return render_email(
        SECURITY_CODE_SUBJECT,
        "authentication/email/security_code",
        {"code": code, "instructions": instructions},
    )


def render_email_changed_alert() -> RenderedEmail:
    """Render the previous-address alert; it names neither address nor who made the change."""

    return render_email(EMAIL_CHANGED_SUBJECT, "authentication/email/email_changed")


__all__ = [
    "EMAIL_CHANGED_SUBJECT",
    "SECURITY_CODE_SUBJECT",
    "render_email_changed_alert",
    "render_security_code_email",
]


def render_recovery_link_email(*, url, expires_at, email_change):
    return render_email(
        "Your COMPASS account recovery link",
        "authentication/email/recovery_link",
        {
            "url": url,
            "expiry": to_institution_time(expires_at).strftime("%B %d, %Y at %I:%M %p"),
            "zone": institution_timezone_name(),
            "email_change": email_change,
        },
    )


def render_recovery_completion_email():
    return render_email("COMPASS password updated", "authentication/email/recovery_completed")
