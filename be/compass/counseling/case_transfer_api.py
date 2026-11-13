"""Case transfer commands and narrow reviews, independent of the case-management API."""

from uuid import UUID

from ninja import Router, Status

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.guidance_followups.errors import FollowUpError

from .case_continuity_rules import CaseContinuityError
from .case_services import CounselingCaseError
from .case_transfer_projections import lookup_cases, transfer_context, transfer_detail
from .case_transfer_schemas import (
    CaseContinuityLookupPage,
    CaseContinuityReason,
    CaseTransferContextResponse,
    CaseTransferDecisionRequest,
    CaseTransferDetailResponse,
    CaseTransferPrepareRequest,
    CaseTransferPurpose,
    CaseTransferUpdateRequest,
    CaseTransferVersionRequest,
    CounselingCaseStatus,
)
from .case_transfer_services import decide_transfer, get_transfer, prepare_transfer, submit_transfer

router = Router(tags=["counseling"])


def invoke(operation, request, **values):
    try:
        return operation(actor=request.auth_user, **values)
    except CaseContinuityError as exc:
        raise APIError(exc.status, exc.code, str(exc)) from None
    except CounselingCaseError as exc:
        raise APIError(exc.status, exc.code, str(exc)) from None
    except FollowUpError as exc:
        from compass.guidance_followups.api import _raise

        _raise(exc)


def context(request):
    return AuditContext.from_request(request, actor=request.auth_user)


ERRORS = (401, 403, 404, 409, 422, 503)


@router.get(
    "/office-cases",
    response=response_with_errors(CaseContinuityLookupPage, *ERRORS),
    auth=session_auth,
    operation_id="counselingListContinuityOfficeCases",
)
def office_cases(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    status: CounselingCaseStatus = CounselingCaseStatus.ACTIVE,
):
    return invoke(
        lookup_cases, request, search=search, page=page, page_size=page_size, status=status
    )


@router.get(
    "/cases/{case_id}/transfer-context",
    response=response_with_errors(CaseTransferContextResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingGetCaseTransferContext",
)
def get_context(
    request,
    case_id: UUID,
    reason: CaseContinuityReason = CaseContinuityReason.SERVICE_RESPONSIBILITY_CHANGE,
    purpose: CaseTransferPurpose | None = None,
):
    return invoke(transfer_context, request, case_id=case_id, reason=reason, purpose=purpose)


@router.post(
    "/cases/{case_id}/transfers",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS, success_status=201),
    auth=session_auth,
    operation_id="counselingPrepareCaseTransfer",
)
def prepare(request, case_id: UUID, payload: CaseTransferPrepareRequest):
    item = invoke(
        prepare_transfer,
        request,
        case_id=case_id,
        values=payload.model_dump(),
        context=context(request),
    )
    return Status(201, invoke(transfer_detail_for_actor, request, item=item))


def transfer_detail_for_actor(*, actor, item):
    return transfer_detail(item, actor)


@router.get(
    "/transfers/{transfer_id}",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingGetCaseTransfer",
)
def get_review(request, transfer_id: UUID):
    item = invoke(get_transfer, request, transfer_id=transfer_id)
    return invoke(transfer_detail_for_actor, request, item=item)


@router.put(
    "/transfers/{transfer_id}",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingUpdateCaseTransfer",
)
def update(request, transfer_id: UUID, payload: CaseTransferUpdateRequest):
    existing = invoke(get_transfer, request, transfer_id=transfer_id)
    item = invoke(
        prepare_transfer,
        request,
        case_id=existing.case_id,
        transfer_id=transfer_id,
        expected_version=payload.expected_version,
        values=payload.model_dump(exclude={"expected_version"}),
        context=context(request),
    )
    return invoke(transfer_detail_for_actor, request, item=item)


@router.post(
    "/transfers/{transfer_id}/submit",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingSubmitCaseTransfer",
)
def submit(request, transfer_id: UUID, payload: CaseTransferVersionRequest):
    item = invoke(
        submit_transfer,
        request,
        transfer_id=transfer_id,
        expected_version=payload.expected_version,
        context=context(request),
    )
    return invoke(transfer_detail_for_actor, request, item=item)


@router.post(
    "/transfers/{transfer_id}/authorize",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingAuthorizeCaseTransfer",
)
def authorize(request, transfer_id: UUID, payload: CaseTransferVersionRequest):
    item = invoke(
        decide_transfer,
        request,
        transfer_id=transfer_id,
        expected_version=payload.expected_version,
        action="authorize",
        context=context(request),
    )
    return invoke(transfer_detail_for_actor, request, item=item)


@router.post(
    "/transfers/{transfer_id}/accept",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingAcceptCaseTransfer",
)
def accept(request, transfer_id: UUID, payload: CaseTransferVersionRequest):
    item = invoke(
        decide_transfer,
        request,
        transfer_id=transfer_id,
        expected_version=payload.expected_version,
        action="accept",
        context=context(request),
    )
    return invoke(transfer_detail_for_actor, request, item=item)


@router.post(
    "/transfers/{transfer_id}/decline",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingDeclineCaseTransfer",
)
def decline(request, transfer_id: UUID, payload: CaseTransferDecisionRequest):
    item = invoke(
        decide_transfer,
        request,
        transfer_id=transfer_id,
        expected_version=payload.expected_version,
        action="decline",
        reason=payload.reason,
        context=context(request),
    )
    return invoke(transfer_detail_for_actor, request, item=item)


@router.post(
    "/transfers/{transfer_id}/cancel",
    response=response_with_errors(CaseTransferDetailResponse, *ERRORS),
    auth=session_auth,
    operation_id="counselingCancelCaseTransfer",
)
def cancel(request, transfer_id: UUID, payload: CaseTransferDecisionRequest):
    item = invoke(
        decide_transfer,
        request,
        transfer_id=transfer_id,
        expected_version=payload.expected_version,
        action="cancel",
        reason=payload.reason,
        context=context(request),
    )
    return invoke(transfer_detail_for_actor, request, item=item)
