"""Fail-closed environment boundary for demo seeding."""

from __future__ import annotations

from django.conf import settings

# An explicit allowlist: a new or unknown APP_ENV value is refused by default, even if the settings
# module later learns to accept it.
DEMO_SEEDING_ENVIRONMENTS = frozenset({"local-staging", "live-staging"})


class DemoSeedingRefused(RuntimeError):
    """The current deployment is not allowed to receive the synthetic demo dataset."""


def ensure_demo_seeding_allowed(*, app_env: object, seeding_enabled: object) -> str:
    """Return the allowed environment name or refuse.

    Both conditions are required: the environment must be one of the explicit staging modes, and
    ``DEMO_SEEDING_ENABLED`` must be exactly ``True``. The opt-in never widens the allowlist.
    """

    if not isinstance(app_env, str) or app_env not in DEMO_SEEDING_ENVIRONMENTS:
        raise DemoSeedingRefused(
            f"Demo seeding is refused for APP_ENV={app_env!r}. It is allowed only in "
            "local-staging and live-staging."
        )
    if seeding_enabled is not True:
        raise DemoSeedingRefused(
            f"Demo seeding is disabled for {app_env}. Set DEMO_SEEDING_ENABLED=true for this "
            "deployment deliberately before seeding the synthetic demo dataset."
        )
    return app_env


def ensure_demo_seeding_allowed_by_settings() -> str:
    return ensure_demo_seeding_allowed(
        app_env=getattr(settings, "APP_ENV", None),
        seeding_enabled=getattr(settings, "DEMO_SEEDING_ENABLED", False),
    )


__all__ = [
    "DEMO_SEEDING_ENVIRONMENTS",
    "DemoSeedingRefused",
    "ensure_demo_seeding_allowed",
    "ensure_demo_seeding_allowed_by_settings",
]
