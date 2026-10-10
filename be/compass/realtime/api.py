"""HTTP bridge from the cookie session to the realtime WebSocket service (ADR-100)."""

from __future__ import annotations

import logging
from uuid import UUID

from django.conf import settings
from django.http import HttpResponse
from ninja import Router, Schema

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.realtime.tickets import RealtimeUnavailable, issue_ticket

logger = logging.getLogger("compass.realtime")
router = Router(tags=["realtime"])

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class RealtimeTicketResponse(Schema):
    ticket: str
    expires_in_seconds: int
    user_id: UUID


@router.post(
    "/tickets",
    response=response_with_errors(RealtimeTicketResponse, 401, 403, 503),
    auth=session_auth,
    operation_id="realtimeIssueTicket",
    summary="Issue a one-time realtime connection ticket",
    description=(
        "Mints a single-use ticket for the current session. The client sends it as the first "
        "WebSocket frame to the realtime service and never places it in a URL. The ticket "
        "expires within seconds and authenticates at most one socket. `user_id` is the "
        "account the ticket belongs to. Returns 503 `realtime_disabled` when realtime is "
        "turned off and 503 `realtime_unavailable` when it is temporarily unavailable."
    ),
)
def issue_realtime_ticket(request, response: HttpResponse):
    for name, value in _NO_STORE.items():
        response[name] = value
    if not settings.REALTIME_ENABLED:
        raise APIError(
            503, "realtime_disabled", "Realtime updates are not enabled.", headers=dict(_NO_STORE)
        )
    try:
        issued = issue_ticket(user_id=request.auth_user.pk, session_id=request.auth_session.pk)
    except RealtimeUnavailable as exc:
        logger.warning(
            "realtime ticket was not issued",
            extra={
                "event": "realtime_ticket_unavailable",
                "error_type": type(exc.__cause__ or exc).__name__,
            },
        )
        raise APIError(
            503,
            "realtime_unavailable",
            "Realtime updates are temporarily unavailable.",
            headers=dict(_NO_STORE),
        ) from None
    return {
        "ticket": issued.ticket,
        "expires_in_seconds": issued.expires_in_seconds,
        "user_id": request.auth_user.pk,
    }
