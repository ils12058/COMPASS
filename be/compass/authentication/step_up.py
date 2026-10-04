"""One public translation for recent-MFA (step-up) requirements.

Every API that keeps a recent-MFA boundary reports the account's real state:

* ``mfa_setup_required``: the account has no active authenticator, so no step-up code exists;
  the person must set one up from Account Security first.
* ``recent_mfa_required``: an authenticator is active but was not verified recently; the person
  can verify a current code and try again.
"""

from __future__ import annotations

from compass.authentication.sessions import (
    MFASetupRequired,
    RecentMFARequired,
    require_recent_mfa,
)
from compass.common.errors import APIError


def step_up_api_error(exc: RecentMFARequired) -> APIError:
    if isinstance(exc, MFASetupRequired):
        return APIError(
            403,
            "mfa_setup_required",
            "An authenticator must be set up before this action can be completed.",
        )
    return APIError(403, "recent_mfa_required", "Recent MFA is required.")


def require_recent_mfa_for_request(request) -> None:
    try:
        require_recent_mfa(request.auth_session)
    except RecentMFARequired as exc:
        raise step_up_api_error(exc) from exc


__all__ = ["require_recent_mfa_for_request", "step_up_api_error"]
