"""Code-owned security email sent directly by authentication tasks, outside Notifications."""

from __future__ import annotations

from compass.common.email import RenderedEmail, render_email

SECURITY_CODE_SUBJECT = "Your COMPASS security code"
EMAIL_CHANGED_SUBJECT = "Your COMPASS sign-in email was changed"


def render_security_code_email(code: str) -> RenderedEmail:
    """Render the transient Email OTP in memory only; never log, store, or link the result."""

    return render_email(
        SECURITY_CODE_SUBJECT,
        "authentication/email/security_code",
        {"code": code},
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
