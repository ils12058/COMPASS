"""Operator-supplied demo configuration, read only while ``seed_demo_staging`` runs.

Nothing here is imported by settings, so application startup never depends on these values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from compass.common.config import env

# RFC 6761 reserves ``.test``: nothing outside the local Mailpit capture can ever receive it.
LOCAL_STAGING_DEFAULT_EMAIL_DOMAIN = "compass-demo.test"
MAX_EMAIL_DOMAIN_LENGTH = 200


class DemoConfigurationError(RuntimeError):
    """Demo configuration is missing or unusable; messages never contain secret values."""


@dataclass(frozen=True, slots=True)
class DemoConfig:
    email_domain: str
    onboarding_email: str | None
    password: str = field(repr=False)

    def __repr__(self) -> str:
        return (
            f"DemoConfig(email_domain={self.email_domain!r}, "
            f"onboarding_email={self.onboarding_email!r}, password=<configured>)"
        )


def _read(name: str) -> str | None:
    try:
        value = env(name, None)
    except ValueError as exc:
        # compass.common.config messages name the variable, never its value.
        raise DemoConfigurationError(str(exc)) from None
    if value is None:
        return None
    return str(value)


def _validate_address(value: str, *, label: str) -> str:
    try:
        EmailValidator()(value)
    except ValidationError:
        raise DemoConfigurationError(f"{label} must produce a valid email address.") from None
    return value


def _email_domain(app_env: str) -> str:
    raw = _read("DEMO_EMAIL_DOMAIN")
    if raw is None or not raw.strip():
        if app_env == "local-staging":
            return LOCAL_STAGING_DEFAULT_EMAIL_DOMAIN
        raise DemoConfigurationError(
            "DEMO_EMAIL_DOMAIN is required in live-staging. Use a domain whose demo mailboxes "
            "the operator controls."
        )
    domain = raw.strip().lower()
    if "@" in domain or len(domain) > MAX_EMAIL_DOMAIN_LENGTH:
        raise DemoConfigurationError("DEMO_EMAIL_DOMAIN must be a bare email domain.")
    _validate_address(f"demo-probe@{domain}", label="DEMO_EMAIL_DOMAIN")
    return domain


def _onboarding_email() -> str | None:
    raw = _read("DEMO_ONBOARDING_EMAIL")
    if raw is None or not raw.strip():
        return None
    return _validate_address(raw.strip().lower(), label="DEMO_ONBOARDING_EMAIL")


def _password() -> str:
    password = _read("DEMO_ACCOUNT_PASSWORD")
    if not password:
        raise DemoConfigurationError(
            "DEMO_ACCOUNT_PASSWORD or DEMO_ACCOUNT_PASSWORD_FILE is required. It is the shared "
            "password for ready demo accounts and is never displayed."
        )
    return password


def load_demo_config(*, app_env: str) -> DemoConfig:
    return DemoConfig(
        email_domain=_email_domain(app_env),
        onboarding_email=_onboarding_email(),
        password=_password(),
    )


__all__ = [
    "DemoConfig",
    "DemoConfigurationError",
    "LOCAL_STAGING_DEFAULT_EMAIL_DOMAIN",
    "load_demo_config",
]
