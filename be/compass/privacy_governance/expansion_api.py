"""DPO governance management and narrowly scoped privacy notice readership."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from . import expansion as service
from .api import _context, _raise, _require
from .expansion import NoticePublishBlocker
from .models import PrivacyNoticeAcknowledgment
from .services import PrivacyGovernanceError

router = Router(tags=["privacy-governance"])
public_router = Router(tags=["privacy-governance"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class EmptyRequest(StrictSchema):
    pass


class AudienceValue(StrEnum):
    PUBLIC = "PUBLIC"
    STUDENT = "STUDENT"
    STAFF = "STAFF"


class RevisionStatusValue(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"


class RetentionResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    scope_summary: str
    retention_trigger_summary: str
    retention_period_summary: str
    disposition_summary: str
    policy_reference: str
    effective_on: date | None
    review_due_on: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RetentionPage(StrictSchema):
    items: list[RetentionResponse]
    page: int
    page_size: int
    has_next: bool


class RetentionCreate(StrictSchema):
    code: str
    name: str
    scope_summary: str
    retention_trigger_summary: str
    retention_period_summary: str
    disposition_summary: str
    policy_reference: str = ""
    effective_on: date | None = None
    review_due_on: date | None = None


class RetentionUpdate(StrictSchema):
    name: str | None = None
    scope_summary: str | None = None
    retention_trigger_summary: str | None = None
    retention_period_summary: str | None = None
    disposition_summary: str | None = None
    policy_reference: str | None = None
    effective_on: date | None = None
    review_due_on: date | None = None


def _retention(item):
    return {
        field: getattr(item, field) for field in RetentionResponse.model_fields if field != "id"
    } | {"id": item.pk}


def _page(result, projector):
    return {
        "items": [projector(item) for item in result["items"]],
        "page": result["page"],
        "page_size": result["page_size"],
        "has_next": result["has_next"],
    }


@router.get(
    "/retention-policies",
    response=response_with_errors(RetentionPage, 401, 403, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListRetentionPolicies",
)
def retention_list(
    request,
    page: int = 1,
    page_size: int = service.DEFAULT_PAGE_SIZE,
    is_active: bool | None = None,
    search: str | None = None,
):
    _require(request, "privacy_governance.view")
    try:
        return _page(
            service.list_retention(
                is_active=is_active,
                search=search,
                page_number=page,
                page_size=page_size,
            ),
            _retention,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.post(
    "/retention-policies",
    response=response_with_errors(RetentionResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="privacyGovernanceCreateRetentionPolicy",
)
def retention_create(request, payload: RetentionCreate):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        item = service.create_retention(context=_context(request), **payload.model_dump())
        return Status(201, _retention(item))
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.get(
    "/retention-policies/{policy_id}",
    response=response_with_errors(RetentionResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceGetRetentionPolicy",
)
def retention_get(request, policy_id: UUID):
    _require(request, "privacy_governance.view")
    try:
        return _retention(service.get_retention(policy_id))
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.patch(
    "/retention-policies/{policy_id}",
    response=response_with_errors(RetentionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceUpdateRetentionPolicy",
)
def retention_update(request, policy_id: UUID, payload: RetentionUpdate):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return _retention(
            service.update_retention(
                policy_id=policy_id,
                context=_context(request),
                changes=payload.model_dump(exclude_unset=True),
            )
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.post(
    "/retention-policies/{policy_id}/retire",
    response=response_with_errors(RetentionResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="privacyGovernanceRetireRetentionPolicy",
)
def retention_retire(request, policy_id: UUID):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return _retention(service.retire_retention(policy_id=policy_id, context=_context(request)))
    except PrivacyGovernanceError as exc:
        _raise(exc)


class NoticeRevisionSummary(StrictSchema):
    id: UUID
    revision_number: int
    effective_on: date | None
    published_at: datetime | None


class NoticeResponse(StrictSchema):
    id: UUID
    code: str
    name: str
    is_active: bool
    current_revision: NoticeRevisionSummary | None
    draft_revision: NoticeRevisionSummary | None
    created_at: datetime
    updated_at: datetime


class NoticePage(StrictSchema):
    items: list[NoticeResponse]
    page: int
    page_size: int
    has_next: bool


class NoticePublishReadinessResponse(StrictSchema):
    ready: bool
    blocker: NoticePublishBlocker | None


class RevisionResponse(StrictSchema):
    id: UUID
    notice_id: UUID
    revision_number: int
    status: RevisionStatusValue
    title: str
    audiences: list[AudienceValue]
    summary: str
    body: str
    requires_acknowledgment: bool
    effective_on: date | None
    publish_readiness: NoticePublishReadinessResponse
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class RevisionPage(StrictSchema):
    items: list[RevisionResponse]
    page: int
    page_size: int
    has_next: bool


class RevisionCreate(StrictSchema):
    title: str
    audiences: list[AudienceValue]
    summary: str
    body: str
    requires_acknowledgment: bool = False
    effective_on: date | None = None


class NoticeCreate(RevisionCreate):
    code: str
    name: str


class NoticeUpdate(StrictSchema):
    name: str | None = None


class RevisionUpdate(StrictSchema):
    title: str | None = None
    audiences: list[AudienceValue] | None = None
    summary: str | None = None
    body: str | None = None
    requires_acknowledgment: bool | None = None
    effective_on: date | None = None


def _revision_summary(item):
    if item is None:
        return None
    return {
        "id": item.pk,
        "revision_number": item.revision_number,
        "effective_on": item.effective_on,
        "published_at": item.published_at,
    }


def _notice(item):
    current, draft = service.notice_open_revisions(item)
    return {
        "id": item.pk,
        "code": item.code,
        "name": item.name,
        "is_active": item.is_active,
        "current_revision": _revision_summary(current),
        "draft_revision": _revision_summary(draft),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _revision(item):
    readiness = service.notice_publish_readiness(item)
    return {
        "id": item.pk,
        "notice_id": item.notice_id,
        "revision_number": item.revision_number,
        "status": item.status,
        "title": item.title,
        "audiences": item.audiences,
        "summary": item.summary,
        "body": item.body,
        "requires_acknowledgment": item.requires_acknowledgment,
        "effective_on": item.effective_on,
        "publish_readiness": {"ready": readiness.ready, "blocker": readiness.blocker},
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "published_at": item.published_at,
    }


@router.get(
    "/notices",
    response=response_with_errors(NoticePage, 401, 403, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListNotices",
)
def notice_list(
    request,
    page: int = 1,
    page_size: int = service.DEFAULT_PAGE_SIZE,
    is_active: bool | None = None,
):
    _require(request, "privacy_governance.view")
    try:
        return _page(
            service.list_notices(is_active=is_active, page_number=page, page_size=page_size),
            _notice,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.post(
    "/notices",
    response=response_with_errors(NoticeResponse, 401, 403, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="privacyGovernanceCreateNotice",
)
def notice_create(request, payload: NoticeCreate):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return Status(
            201,
            _notice(
                service.create_notice(
                    actor=request.auth_user, context=_context(request), **payload.model_dump()
                )
            ),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.get(
    "/notices/{notice_id}",
    response=response_with_errors(NoticeResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceGetNotice",
)
def notice_get(request, notice_id: UUID):
    _require(request, "privacy_governance.view")
    try:
        return _notice(service.get_notice(notice_id))
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.patch(
    "/notices/{notice_id}",
    response=response_with_errors(NoticeResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceUpdateNotice",
)
def notice_update(request, notice_id: UUID, payload: NoticeUpdate):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return _notice(
            service.update_notice(
                notice_id=notice_id,
                context=_context(request),
                **payload.model_dump(exclude_unset=True),
            )
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.post(
    "/notices/{notice_id}/retire",
    response=response_with_errors(NoticeResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceRetireNotice",
)
def notice_retire(request, notice_id: UUID):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return _notice(service.retire_notice(notice_id=notice_id, context=_context(request)))
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.get(
    "/notices/{notice_id}/revisions",
    response=response_with_errors(RevisionPage, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListNoticeRevisions",
)
def revision_list(
    request, notice_id: UUID, page: int = 1, page_size: int = service.DEFAULT_PAGE_SIZE
):
    _require(request, "privacy_governance.view")
    try:
        return _page(
            service.list_revisions(notice_id=notice_id, page_number=page, page_size=page_size),
            _revision,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.post(
    "/notices/{notice_id}/revisions",
    response=response_with_errors(RevisionResponse, 401, 403, 404, 409, 422, success_status=201),
    auth=session_auth,
    operation_id="privacyGovernanceCreateNoticeRevision",
)
def revision_create(request, notice_id: UUID, payload: RevisionCreate):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return Status(
            201,
            _revision(
                service.create_revision(
                    notice_id=notice_id,
                    actor=request.auth_user,
                    context=_context(request),
                    **payload.model_dump(),
                )
            ),
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.get(
    "/notice-revisions/{revision_id}",
    response=response_with_errors(RevisionResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="privacyGovernanceGetNoticeRevision",
)
def revision_get(request, revision_id: UUID):
    _require(request, "privacy_governance.view")
    try:
        return _revision(service.get_revision(revision_id))
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.patch(
    "/notice-revisions/{revision_id}",
    response=response_with_errors(RevisionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceUpdateNoticeRevision",
)
def revision_update(request, revision_id: UUID, payload: RevisionUpdate):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return _revision(
            service.update_revision(
                revision_id=revision_id,
                context=_context(request),
                changes=payload.model_dump(exclude_unset=True),
            )
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.post(
    "/notice-revisions/{revision_id}/publish",
    response=response_with_errors(RevisionResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernancePublishNoticeRevision",
)
def revision_publish(request, revision_id: UUID):
    _require(request, "privacy_governance.manage", recent_mfa=True)
    try:
        return _revision(
            service.publish_revision(
                revision_id=revision_id, actor=request.auth_user, context=_context(request)
            )
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


class CurrentNoticeResponse(StrictSchema):
    notice_id: UUID
    code: str
    name: str
    revision_id: UUID
    revision_number: int
    title: str
    audiences: list[AudienceValue]
    summary: str
    body: str
    effective_on: date
    requires_acknowledgment: bool


class MyNoticeResponse(CurrentNoticeResponse):
    acknowledged: bool
    acknowledged_at: datetime | None


class CurrentNoticePage(StrictSchema):
    items: list[CurrentNoticeResponse]
    page: int
    page_size: int
    has_next: bool


class MyNoticePage(StrictSchema):
    items: list[MyNoticeResponse]
    page: int
    page_size: int
    has_next: bool


class AcknowledgmentResponse(StrictSchema):
    notice_id: UUID
    revision_id: UUID
    revision_number: int
    acknowledged: bool
    acknowledged_at: datetime


def _current(item):
    return {
        "notice_id": item.notice_id,
        "code": item.notice.code,
        "name": item.notice.name,
        "revision_id": item.pk,
        "revision_number": item.revision_number,
        "title": item.title,
        "audiences": item.audiences,
        "summary": item.summary,
        "body": item.body,
        "effective_on": item.effective_on,
        "requires_acknowledgment": item.requires_acknowledgment,
    }


@public_router.get(
    "/public-notices",
    response=response_with_errors(CurrentNoticePage, 422),
    operation_id="privacyGovernanceListPublicNotices",
)
def public_notices(request, page: int = 1, page_size: int = service.DEFAULT_PAGE_SIZE):
    try:
        return _page(
            service.page(service.current_revisions("PUBLIC"), page=page, page_size=page_size),
            _current,
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)


@router.get(
    "/my-notices",
    response=response_with_errors(MyNoticePage, 401, 403, 422),
    auth=session_auth,
    operation_id="privacyGovernanceListMyNotices",
)
def my_notices(request, page: int = 1, page_size: int = service.DEFAULT_PAGE_SIZE):
    actor = request.auth_user
    if not actor.is_active:
        raise APIError(403, "permission_denied", "An active account is required.")
    try:
        result = service.page(service.applicable_revisions(actor), page=page, page_size=page_size)
    except PrivacyGovernanceError as exc:
        _raise(exc)
    ids = [item.pk for item in result["items"]]
    acknowledgments = {
        item.revision_id: item.acknowledged_at
        for item in PrivacyNoticeAcknowledgment.objects.filter(user=actor, revision_id__in=ids)
    }
    return _page(
        result,
        lambda item: (
            _current(item)
            | {
                "acknowledged": item.pk in acknowledgments,
                "acknowledged_at": acknowledgments.get(item.pk),
            }
        ),
    )


@router.post(
    "/my-notices/{revision_id}/acknowledge",
    response=response_with_errors(AcknowledgmentResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="privacyGovernanceAcknowledgeMyNotice",
)
def my_notice_acknowledge(request, revision_id: UUID, payload: EmptyRequest):
    actor = request.auth_user
    if not actor.is_active:
        raise APIError(403, "permission_denied", "An active account is required.")
    try:
        acknowledgment = service.acknowledge_revision(
            revision_id=revision_id, actor=actor, context=_context(request)
        )
    except PrivacyGovernanceError as exc:
        _raise(exc)
    return {
        "notice_id": acknowledgment.revision.notice_id,
        "revision_id": acknowledgment.revision_id,
        "revision_number": acknowledgment.revision.revision_number,
        "acknowledged": True,
        "acknowledged_at": acknowledgment.acknowledged_at,
    }
