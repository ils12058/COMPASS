"""Fail-closed environment boundary for Staging Dataset v1 seeding."""

from __future__ import annotations

from django.conf import settings

# An explicit allowlist: a new or unknown APP_ENV value is refused by default, even if the settings
# module later learns to accept it. "Not production" is never treated as permission.
SEEDING_ENVIRONMENTS = frozenset({"local-staging", "live-staging"})


class StagingSeedingRefused(RuntimeError):
    """The current deployment is not allowed to receive the synthetic staging dataset."""


def ensure_seeding_allowed(*, app_env: object, seeding_enabled: object) -> str:
    """Return the allowed environment name or refuse.

    Both conditions are required: the environment must be one of the explicit staging modes, and
    ``STAGING_SEED_ENABLED`` must be exactly ``True``. The opt-in never widens the allowlist.
    """

    if not isinstance(app_env, str) or app_env not in SEEDING_ENVIRONMENTS:
        raise StagingSeedingRefused(
            f"Staging dataset commands are refused for APP_ENV={app_env!r}. They are allowed only "
            "in local-staging and live-staging."
        )
    if seeding_enabled is not True:
        raise StagingSeedingRefused(
            f"Staging dataset commands are disabled for {app_env}. Set STAGING_SEED_ENABLED=true "
            "for this one-off run deliberately."
        )
    return app_env


def ensure_seeding_allowed_by_settings() -> str:
    return ensure_seeding_allowed(
        app_env=getattr(settings, "APP_ENV", None),
        seeding_enabled=getattr(settings, "STAGING_SEED_ENABLED", False),
    )


__all__ = [
    "SEEDING_ENVIRONMENTS",
    "StagingSeedingRefused",
    "ensure_seeding_allowed",
    "ensure_seeding_allowed_by_settings",
]
