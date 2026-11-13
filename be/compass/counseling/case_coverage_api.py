"""Temporary case coverage commands; acceptance never changes primary responsibility."""

from uuid import UUID

from ninja import Router, Status

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors

from .case_coverage_projections import coverage_context, coverage_detail
from .case_coverage_schemas import (
    CaseCoverageContextResponse,
    CaseCoverageDecisionRequest,
    CaseCoverageDetailResponse,
    CaseCoveragePrepareRequest,
    CaseCoverageUpdateRequest,
    CaseCoverageVersionRequest,
)
from .case_coverage_services import decide_coverage, get_coverage, prepare_coverage, submit_coverage
from .case_transfer_api import context, invoke

router = Router(tags=["counseling"], auth=session_auth)
ERRORS = (401, 403, 404, 409, 422, 503)
DETAIL = response_with_errors(CaseCoverageDetailResponse, *ERRORS)


@router.get(
    "/cases/{case_id}/coverage-context",
    response=response_with_errors(CaseCoverageContextResponse, *ERRORS),
    operation_id="counselingGetCaseCoverageContext",
)
def get_context(request, case_id: UUID):
    return invoke(coverage_context, request, case_id=case_id)


@router.post(
    "/cases/{case_id}/coverages",
    response=response_with_errors(CaseCoverageDetailResponse, *ERRORS, success_status=201),
    operation_id="counselingPrepareCaseCoverage",
)
def prepare(request, case_id: UUID, payload: CaseCoveragePrepareRequest):
    item = invoke(
        prepare_coverage,
        request,
        case_id=case_id,
        values=payload.model_dump(),
        context=context(request),
    )
    return Status(201, invoke(coverage_detail, request, coverage_id=item.pk))


@router.get("/coverages/{coverage_id}", response=DETAIL, operation_id="counselingGetCaseCoverage")
def get_review(request, coverage_id: UUID):
    return invoke(coverage_detail, request, coverage_id=coverage_id)


@router.put(
    "/coverages/{coverage_id}", response=DETAIL, operation_id="counselingUpdateCaseCoverage"
)
def update(request, coverage_id: UUID, payload: CaseCoverageUpdateRequest):
    existing = invoke(get_coverage, request, coverage_id=coverage_id)
    item = invoke(
        prepare_coverage,
        request,
        case_id=existing.case_id,
        coverage_id=coverage_id,
        expected_version=payload.expected_version,
        values=payload.model_dump(exclude={"expected_version"}),
        context=context(request),
    )
    return invoke(coverage_detail, request, coverage_id=item.pk)


@router.post(
    "/coverages/{coverage_id}/submit", response=DETAIL, operation_id="counselingSubmitCaseCoverage"
)
def submit(request, coverage_id: UUID, payload: CaseCoverageVersionRequest):
    item = invoke(
        submit_coverage,
        request,
        coverage_id=coverage_id,
        expected_version=payload.expected_version,
        context=context(request),
    )
    return invoke(coverage_detail, request, coverage_id=item.pk)


def _decide(request, coverage_id, payload, action):
    item = invoke(
        decide_coverage,
        request,
        coverage_id=coverage_id,
        expected_version=payload.expected_version,
        action=action,
        reason=getattr(payload, "reason", None),
        context=context(request),
    )
    return invoke(coverage_detail, request, coverage_id=item.pk)


@router.post(
    "/coverages/{coverage_id}/authorize",
    response=DETAIL,
    operation_id="counselingAuthorizeCaseCoverage",
)
def authorize(request, coverage_id: UUID, payload: CaseCoverageVersionRequest):
    return _decide(request, coverage_id, payload, "authorize")


@router.post(
    "/coverages/{coverage_id}/accept", response=DETAIL, operation_id="counselingAcceptCaseCoverage"
)
def accept(request, coverage_id: UUID, payload: CaseCoverageVersionRequest):
    return _decide(request, coverage_id, payload, "accept")


@router.post(
    "/coverages/{coverage_id}/decline",
    response=DETAIL,
    operation_id="counselingDeclineCaseCoverage",
)
def decline(request, coverage_id: UUID, payload: CaseCoverageDecisionRequest):
    return _decide(request, coverage_id, payload, "decline")


@router.post(
    "/coverages/{coverage_id}/cancel", response=DETAIL, operation_id="counselingCancelCaseCoverage"
)
def cancel(request, coverage_id: UUID, payload: CaseCoverageDecisionRequest):
    return _decide(request, coverage_id, payload, "cancel")


@router.post(
    "/coverages/{coverage_id}/revoke", response=DETAIL, operation_id="counselingRevokeCaseCoverage"
)
def revoke(request, coverage_id: UUID, payload: CaseCoverageDecisionRequest):
    return _decide(request, coverage_id, payload, "revoke")
