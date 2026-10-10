"""Minimized DPO governance projections; no source IDs or protected answers."""

from datetime import date, datetime, timedelta
from uuid import UUID

from django.utils import timezone
from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field, field_validator

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from . import retention
from .api import _context, _require
from .retention_models import (
    DispositionAction,
    DispositionBlocker,
    DispositionCase,
    DispositionState,
    OperationalRetentionRule,
    RetentionCategory,
    RetentionContractVersion,
    RetentionRuleStatus,
    RetentionTrigger,
)
from .services import PrivacyInputError, _validate_page

router = Router(tags=["privacy-governance"], auth=session_auth)
VIEW = "privacy_governance.retention.view"
MANAGE = "privacy_governance.retention.manage"
APPROVE = "privacy_governance.retention.approve"


class RetentionStrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class RetentionCategoryResponse(RetentionStrictSchema):
    contract_version: RetentionContractVersion
    category: RetentionCategory
    label: str
    trigger: RetentionTrigger
    action: DispositionAction


class RetentionRuleValues(RetentionStrictSchema):
    label: str = Field(min_length=1, max_length=160)
    contract_version: RetentionContractVersion = RetentionContractVersion.V1
    category: RetentionCategory
    trigger: RetentionTrigger
    duration_days: int = Field(ge=1, le=365000, strict=True)
    action: DispositionAction
    policy_reference: str = Field(min_length=1, max_length=500)
    effective_on: date

    @field_validator("contract_version", mode="before")
    @classmethod
    def require_integer_contract(cls, value):
        if type(value) is not int and not isinstance(value, RetentionContractVersion):
            raise ValueError("contract_version must be 1 or 2")
        return value


class RetentionRuleCreate(RetentionRuleValues):
    code: str = Field(min_length=1, max_length=64)


class RetentionRevisionRequest(RetentionStrictSchema):
    expected_revision: int = Field(ge=1)


class RetentionRuleUpdate(RetentionRuleValues):
    expected_revision: int = Field(ge=1)


class RetentionRuleResponse(RetentionRuleCreate):
    contract_version: RetentionContractVersion
    id: UUID
    status: RetentionRuleStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None


class RetentionRulePage(RetentionStrictSchema):
    items: list[RetentionRuleResponse]
    page: int
    page_size: int
    has_next: bool


class DispositionHoldRequest(RetentionRevisionRequest):
    reason: str = Field(min_length=1, max_length=240)


class DispositionHoldResponse(RetentionStrictSchema):
    id: UUID
    reason: str
    placed_at: datetime
    released_at: datetime | None


class DispositionCaseResponse(RetentionStrictSchema):
    id: UUID
    rule_id: UUID
    rule_code: str
    rule_revision: int
    contract_version: RetentionContractVersion
    category: RetentionCategory
    action: DispositionAction
    affected_count: int
    eligible_at: datetime
    state: DispositionState
    blocker: DispositionBlocker | None
    revision: int
    approved_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    attempts: int
    manual_retries: int
    holds: list[DispositionHoldResponse]


class DispositionCasePage(RetentionStrictSchema):
    items: list[DispositionCaseResponse]
    page: int
    page_size: int
    has_next: bool


class RetentionCategorySummary(RetentionCategoryResponse):
    ready_count: int
    held_count: int
    blocked_count: int


class RetentionSummaryResponse(RetentionStrictSchema):
    needs_review: int
    on_hold: int
    processing: int
    recently_completed: int
    categories: list[RetentionCategorySummary]


def project_rule(item):
    return {key: getattr(item, key) for key in RetentionRuleResponse.model_fields}


def project_case(item):
    return {
        "id": item.pk,
        "rule_id": item.rule_id,
        "rule_code": item.rule.code,
        "rule_revision": item.rule_revision,
        "category": item.category,
        "contract_version": item.contract_version,
        "action": item.rule.action,
        "affected_count": 1,
        "eligible_at": item.eligible_at,
        "state": item.state,
        "blocker": item.blocker,
        "revision": item.revision,
        "approved_at": item.approved_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "attempts": item.attempts,
        "manual_retries": item.manual_retries,
        "holds": [
            {
                "id": hold.pk,
                "reason": hold.reason,
                "placed_at": hold.placed_at,
                "released_at": hold.released_at,
            }
            for hold in item.holds.all()
        ],
    }


def page_of(qs, page, page_size, projector):
    try:
        _validate_page(page=page, page_size=page_size)
    except PrivacyInputError as exc:
        raise APIError(422, "invalid_retention_request", str(exc)) from exc
    offset = (page - 1) * page_size
    items = list(qs[offset : offset + page_size + 1])
    return {
        "items": [projector(item) for item in items[:page_size]],
        "page": page,
        "page_size": page_size,
        "has_next": len(items) > page_size,
    }


def category_projection(category, contract_version=1):
    trigger, action = retention.SUPPORTED_CONTRACTS[(category, contract_version)]
    return {
        "category": category,
        "contract_version": contract_version,
        "label": RetentionCategory(category).label,
        "trigger": trigger,
        "action": action,
    }


@router.get(
    "/retention/categories",
    response=response_with_errors(list[RetentionCategoryResponse], 401, 403),
    operation_id="privacyGovernanceRetentionCategories",
)
def categories(request):
    _require(request, VIEW)
    return [
        category_projection(category, version)
        for category, version in retention.SUPPORTED_CONTRACTS
    ]


@router.get(
    "/retention/rules",
    response=response_with_errors(RetentionRulePage, 401, 403, 422),
    operation_id="privacyGovernanceListRetentionRules",
)
def rules(request, page: int = 1, page_size: int = 20):
    _require(request, VIEW)
    return page_of(OperationalRetentionRule.objects.all(), page, page_size, project_rule)


@router.post(
    "/retention/rules",
    response=response_with_errors(RetentionRuleResponse, 401, 403, 409, 422, success_status=201),
    operation_id="privacyGovernanceCreateRetentionRule",
)
def create_rule(request, payload: RetentionRuleCreate):
    _require(request, MANAGE)
    return Status(
        201,
        project_rule(
            retention.create_rule(
                actor=request.auth_user,
                values=payload.model_dump(mode="python")
                | {"contract_version": int(payload.contract_version)},
                context=_context(request),
            )
        ),
    )


@router.get(
    "/retention/rules/{rule_id}",
    response=response_with_errors(RetentionRuleResponse, 401, 403, 404),
    operation_id="privacyGovernanceGetRetentionRule",
)
def rule(request, rule_id: UUID):
    _require(request, VIEW)
    return project_rule(retention.get_rule(rule_id))


@router.patch(
    "/retention/rules/{rule_id}",
    response=response_with_errors(RetentionRuleResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernanceUpdateRetentionRule",
)
def update_rule(request, rule_id: UUID, payload: RetentionRuleUpdate):
    _require(request, MANAGE)
    return project_rule(
        retention.update_rule(
            actor=request.auth_user,
            rule_id=rule_id,
            expected_revision=payload.expected_revision,
            values=payload.model_dump(exclude={"expected_revision"})
            | {"contract_version": int(payload.contract_version)},
            context=_context(request),
        )
    )


@router.post(
    "/retention/rules/{rule_id}/activate",
    response=response_with_errors(RetentionRuleResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernanceActivateRetentionRule",
)
def activate_rule(request, rule_id: UUID, payload: RetentionRevisionRequest):
    _require(request, MANAGE, recent_mfa=True)
    return project_rule(
        retention.transition_rule(
            actor=request.auth_user,
            rule_id=rule_id,
            expected_revision=payload.expected_revision,
            activate=True,
            context=_context(request),
        )
    )


@router.post(
    "/retention/rules/{rule_id}/retire",
    response=response_with_errors(RetentionRuleResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernanceRetireRetentionRule",
)
def retire_rule(request, rule_id: UUID, payload: RetentionRevisionRequest):
    _require(request, MANAGE, recent_mfa=True)
    return project_rule(
        retention.transition_rule(
            actor=request.auth_user,
            rule_id=rule_id,
            expected_revision=payload.expected_revision,
            activate=False,
            context=_context(request),
        )
    )


@router.get(
    "/retention/summary",
    response=response_with_errors(RetentionSummaryResponse, 401, 403),
    operation_id="privacyGovernanceRetentionSummary",
)
def summary(request):
    _require(request, VIEW)
    qs = DispositionCase.objects.all()
    return {
        "needs_review": qs.filter(state="READY").count(),
        "on_hold": qs.filter(state="ON_HOLD").count(),
        "processing": qs.filter(state__in=("QUEUED", "PROCESSING", "APPROVED")).count(),
        "recently_completed": qs.filter(
            state="COMPLETED", completed_at__gte=timezone.now() - timedelta(days=30)
        ).count(),
        "categories": [
            category_projection(category, version)
            | {
                "ready_count": qs.filter(
                    category=category, contract_version=version, state="READY"
                ).count(),
                "held_count": qs.filter(
                    category=category, contract_version=version, state="ON_HOLD"
                ).count(),
                "blocked_count": qs.filter(
                    category=category,
                    contract_version=version,
                    state__in=(
                        "BLOCKED",
                        "FAILED",
                        "RECONCILIATION_REQUIRED",
                        "NO_LONGER_ELIGIBLE",
                    ),
                ).count(),
            }
            for category, version in retention.SUPPORTED_CONTRACTS
        ],
    }


@router.get(
    "/retention/cases",
    response=response_with_errors(DispositionCasePage, 401, 403, 422),
    operation_id="privacyGovernanceListDispositionCases",
)
def cases(
    request,
    page: int = 1,
    page_size: int = 20,
    contract_version: RetentionContractVersion | None = None,
    category: RetentionCategory | None = None,
    state: DispositionState | None = None,
):
    _require(request, VIEW)
    qs = DispositionCase.objects.select_related("rule").prefetch_related("holds")
    if category:
        qs = qs.filter(category=category)
    if contract_version:
        qs = qs.filter(contract_version=contract_version)
    if state:
        qs = qs.filter(state=state)
    return page_of(qs, page, page_size, project_case)


@router.get(
    "/retention/cases/{case_id}",
    response=response_with_errors(DispositionCaseResponse, 401, 403, 404),
    operation_id="privacyGovernanceGetDispositionCase",
)
def case(request, case_id: UUID):
    _require(request, VIEW)
    return project_case(retention.get_case(case_id))


@router.post(
    "/retention/cases/{case_id}/hold",
    response=response_with_errors(DispositionCaseResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernancePlaceDispositionHold",
)
def hold(request, case_id: UUID, payload: DispositionHoldRequest):
    _require(request, MANAGE)
    return project_case(
        retention.change_hold(
            actor=request.auth_user,
            case_id=case_id,
            expected_revision=payload.expected_revision,
            reason=payload.reason,
            release=False,
            context=_context(request),
        )
    )


@router.post(
    "/retention/cases/{case_id}/release-hold",
    response=response_with_errors(DispositionCaseResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernanceReleaseDispositionHold",
)
def release_hold(request, case_id: UUID, payload: RetentionRevisionRequest):
    _require(request, MANAGE)
    return project_case(
        retention.change_hold(
            actor=request.auth_user,
            case_id=case_id,
            expected_revision=payload.expected_revision,
            reason=None,
            release=True,
            context=_context(request),
        )
    )


@router.post(
    "/retention/cases/{case_id}/approve",
    response=response_with_errors(DispositionCaseResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernanceApproveDispositionCase",
)
def approve(request, case_id: UUID, payload: RetentionRevisionRequest):
    _require(request, APPROVE, recent_mfa=True)
    return project_case(
        retention.approve_case(
            actor=request.auth_user,
            case_id=case_id,
            expected_revision=payload.expected_revision,
            context=_context(request),
        )
    )


@router.post(
    "/retention/cases/{case_id}/retry",
    response=response_with_errors(DispositionCaseResponse, 401, 403, 404, 409, 422),
    operation_id="privacyGovernanceRetryDispositionCase",
)
def retry(request, case_id: UUID, payload: RetentionRevisionRequest):
    _require(request, APPROVE, recent_mfa=True)
    return project_case(
        retention.approve_case(
            actor=request.auth_user,
            case_id=case_id,
            expected_revision=payload.expected_revision,
            context=_context(request),
            retry=True,
        )
    )
