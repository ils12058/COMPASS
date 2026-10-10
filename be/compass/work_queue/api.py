"""Authenticated read-only Guidance staff work, derived entirely from source domains."""

from ninja import Query, Router

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .schemas import WorkQueueQuery, WorkQueueResponse
from .services import WorkQueueAccessDenied, list_work

router = Router(tags=["work"], auth=session_auth)


@router.get(
    "",
    response=response_with_errors(WorkQueueResponse, 401, 403, 422),
    operation_id="workQueueList",
)
def work_queue_list(request, query: Query[WorkQueueQuery]):
    try:
        return list_work(actor=request.auth_user, **query.model_dump())
    except WorkQueueAccessDenied as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc
