"""Operator-supplied Staging Dataset v1 configuration, read only while the command runs.

Nothing here is imported by settings, so application startup never depends on these values.
No credential is configured here: seeding never sets a password (see ``credentials``).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from compass.common.config import env

# RFC 6761 reserves ``.test``: nothing outside the local Mailpit capture can ever receive it.
LOCAL_STAGING_DEFAULT_EMAIL_DOMAIN = "compass-staging.test"
MAX_EMAIL_DOMAIN_LENGTH = 200


class StagingSeedConfigurationError(RuntimeError):
    """Configuration is missing or unusable; messages never contain secret values."""


@dataclass(frozen=True, slots=True)
class StagingSeedConfig:
    email_domain: str
    onboarding_email: str | None


def _read(name: str) -> str | None:
    try:
        value = env(name, None)
    except ValueError as exc:
        # compass.common.config messages name the variable, never its value.
        raise StagingSeedConfigurationError(str(exc)) from None
    if value is None:
        return None
    return str(value)


def _validate_address(value: str, *, label: str) -> str:
    try:
        EmailValidator()(value)
    except ValidationError:
        raise StagingSeedConfigurationError(
            f"{label} must produce a valid email address."
        ) from None
    return value


def _email_domain(app_env: str) -> str:
    raw = _read("STAGING_SEED_EMAIL_DOMAIN")
    if raw is None or not raw.strip():
        if app_env == "local-staging":
            return LOCAL_STAGING_DEFAULT_EMAIL_DOMAIN
        raise StagingSeedConfigurationError(
            "STAGING_SEED_EMAIL_DOMAIN is required in live-staging. Use a domain whose dataset "
            "mailboxes the operator controls."
        )
    domain = raw.strip().lower()
    if "@" in domain or len(domain) > MAX_EMAIL_DOMAIN_LENGTH:
        raise StagingSeedConfigurationError("STAGING_SEED_EMAIL_DOMAIN must be a bare domain.")
    _validate_address(f"stg-probe@{domain}", label="STAGING_SEED_EMAIL_DOMAIN")
    return domain


def _onboarding_email() -> str | None:
    raw = _read("STAGING_SEED_ONBOARDING_EMAIL")
    if raw is None or not raw.strip():
        return None
    return _validate_address(raw.strip().lower(), label="STAGING_SEED_ONBOARDING_EMAIL")


def load_config(*, app_env: str) -> StagingSeedConfig:
    return StagingSeedConfig(
        email_domain=_email_domain(app_env), onboarding_email=_onboarding_email()
    )


__all__ = [
    "LOCAL_STAGING_DEFAULT_EMAIL_DOMAIN",
    "StagingSeedConfig",
    "StagingSeedConfigurationError",
    "load_config",
]
