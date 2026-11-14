"""Protected case handoff endpoints; the Head's transfer projection stays metadata-only."""

from uuid import UUID

from ninja import Router

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from . import case_handoff_services as services
from .case_continuity_rules import CaseContinuityError
from .case_handoff_models import CounselingCaseHandoff
from .case_handoff_schemas import (
    CaseHandoffAddendumRequest,
    CaseHandoffBodyResponse,
    CaseHandoffExceptionRequest,
    CaseHandoffSaveRequest,
    CaseHandoffSubmitRequest,
)
from .case_transfer_schemas import CaseTransferDetailResponse

router = Router(tags=["counseling"])
ERRORS = (401, 403, 404, 409, 422, 503)


def invoke(request, **values):
    try:
        return services.operate(
            actor=request.auth_user,
            context=AuditContext.from_request(request, actor=request.auth_user),
            actor_session_id=request.auth_session.pk,
            actor_session_digest=request.auth_session.token_digest,
            **values,
        )
    except CaseContinuityError as exc:
        raise APIError(exc.status, exc.code, str(exc)) from None


def transfer_for_handoff(handoff_id):
    row = (
        CounselingCaseHandoff.objects.filter(pk=handoff_id)
        .values_list("transfer_id", flat=True)
        .first()
    )
    if row is None:
        raise APIError(
            404, "case_continuity_handoff_not_found", "The protected handoff is unavailable."
        )
    return row


@router.put(
    "/transfers/{transfer_id}/handoff",
    auth=session_auth,
    response=response_with_errors(CaseHandoffBodyResponse, *ERRORS),
    operation_id="counselingSaveCaseHandoff",
)
def save(request, transfer_id: UUID, payload: CaseHandoffSaveRequest):
    return invoke(request, transfer_id=transfer_id, operation="save", **payload.model_dump())


@router.post(
    "/transfers/{transfer_id}/handoff/submit",
    auth=session_auth,
    response=response_with_errors(CaseHandoffBodyResponse, *ERRORS),
    operation_id="counselingSubmitCaseHandoff",
)
def submit(request, transfer_id: UUID, payload: CaseHandoffSubmitRequest):
    return invoke(request, transfer_id=transfer_id, operation="submit", **payload.model_dump())


@router.get(
    "/handoffs/{handoff_id}",
    auth=session_auth,
    response=response_with_errors(CaseHandoffBodyResponse, *ERRORS),
    operation_id="counselingGetCaseHandoff",
)
def read(request, handoff_id: UUID, addenda_page: int = 1):
    return invoke(
        request,
        transfer_id=transfer_for_handoff(handoff_id),
        handoff_id=handoff_id,
        operation="read",
        addenda_page=addenda_page,
    )


@router.post(
    "/handoffs/{handoff_id}/addenda",
    auth=session_auth,
    response=response_with_errors(CaseHandoffBodyResponse, *ERRORS),
    operation_id="counselingAddCaseHandoffAddendum",
)
def addendum(request, handoff_id: UUID, payload: CaseHandoffAddendumRequest):
    return invoke(
        request,
        transfer_id=transfer_for_handoff(handoff_id),
        handoff_id=handoff_id,
        operation="addendum",
        expected_transfer_version=payload.expected_transfer_version,
        addendum=payload.content,
    )


@router.post(
    "/transfers/{transfer_id}/handoff-unavailable",
    auth=session_auth,
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    operation_id="counselingRecordCaseHandoffUnavailable",
)
def exception(request, transfer_id: UUID, payload: CaseHandoffExceptionRequest):
    invoke(
        request,
        transfer_id=transfer_id,
        operation="exception",
        expected_transfer_version=payload.expected_transfer_version,
        exception_reason=payload.reason,
    )
    from .case_transfer_projections import transfer_detail
    from .case_transfer_services import transfers

    return transfer_detail(transfers().get(pk=transfer_id), request.auth_user)
