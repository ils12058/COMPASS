"""Authenticated read-only Student Actions projection."""

from ninja import Query, Router

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .schemas import StudentActionsQuery, StudentActionsResponse
from .services import StudentActionsAccessDenied, list_actions

router = Router(tags=["student-actions"], auth=session_auth)


@router.get(
    "",
    response=response_with_errors(StudentActionsResponse, 401, 403, 422),
    operation_id="studentActionsList",
)
def student_actions_list(request, query: Query[StudentActionsQuery]):
    try:
        return list_actions(actor=request.auth_user, **query.model_dump())
    except StudentActionsAccessDenied as exc:
        raise APIError(403, "permission_denied", str(exc)) from exc
