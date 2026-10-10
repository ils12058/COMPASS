"""Authenticated Guidance operational pulse; no records or workflow writes."""

from ninja import Router

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .schemas import GuidanceOperationsResponse
from .services import GuidanceOperationsAccessDenied, get_guidance_operations

router = Router(tags=["guidance-operations"], auth=session_auth)


@router.get(
    "",
    response=response_with_errors(GuidanceOperationsResponse, 401, 403),
    operation_id="guidanceOperationsGet",
)
def guidance_operations_get(request):
    try:
        return get_guidance_operations(actor=request.auth_user)
    except GuidanceOperationsAccessDenied as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc
