"""Authenticated Portal Overview summary API."""

from __future__ import annotations

from ninja import Router

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .schemas import OverviewSummaryResponse
from .services import OverviewAccessDenied, build_overview_summary

router = Router(tags=["overview"])


@router.get(
    "",
    response=response_with_errors(OverviewSummaryResponse, 401, 403),
    auth=session_auth,
    operation_id="overviewGetSummary",
)
def overview_get_summary(request):
    try:
        summary = build_overview_summary(request.auth_user)
    except OverviewAccessDenied as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc

    return {
        "generated_at": summary.generated_at,
        "student": summary.student,
        "guidance": summary.guidance,
        "platform": summary.platform,
        "privacy": summary.privacy,
    }
