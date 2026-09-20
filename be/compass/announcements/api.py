"""Authenticated reader and capability-authorized Announcement API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema, Status
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.publications import PublicationAudience, PublicationStatus

from .services import (
    DEFAULT_PAGE_SIZE,
    AnnouncementConflict,
    AnnouncementError,
    AnnouncementNotFound,
    InvalidAnnouncementInput,
    archive_announcement,
    create_announcement,
    get_managed_announcement,
    get_visible_announcement,
    list_managed_announcements,
    list_visible_announcements,
    publish_announcement,
    update_announcement,
)

router = Router(tags=["announcements"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AnnouncementAudienceValue(StrEnum):
    ALL_AUTHENTICATED = PublicationAudience.ALL_AUTHENTICATED
    STUDENTS = PublicationAudience.STUDENTS
    GCO_PERSONNEL = PublicationAudience.GCO_PERSONNEL


class AnnouncementStatusValue(StrEnum):
    DRAFT = PublicationStatus.DRAFT
    PUBLISHED = PublicationStatus.PUBLISHED
    ARCHIVED = PublicationStatus.ARCHIVED


class PersonSummary(StrictSchema):
    id: UUID
    display_name: str


class AnnouncementReaderResponse(StrictSchema):
    id: UUID
    title: str
    body_markdown: str
    is_pinned: bool
    published_at: datetime
    expires_at: datetime | None


class AnnouncementManagementResponse(StrictSchema):
    id: UUID
    title: str
    body_markdown: str
    audience: AnnouncementAudienceValue
    status: AnnouncementStatusValue
    is_pinned: bool
    published_at: datetime | None
    expires_at: datetime | None
    created_by: PersonSummary
    updated_by: PersonSummary
    published_by: PersonSummary | None
    created_at: datetime
    updated_at: datetime


class AnnouncementReaderPageResponse(StrictSchema):
    items: list[AnnouncementReaderResponse]
    page: int
    page_size: int
    has_next: bool


class AnnouncementManagementPageResponse(StrictSchema):
    items: list[AnnouncementManagementResponse]
    page: int
    page_size: int
    has_next: bool


class AnnouncementCreateRequest(StrictSchema):
    title: str
    body_markdown: str
    audience: AnnouncementAudienceValue
    is_pinned: bool = False
    expires_at: datetime | None = None


class AnnouncementUpdateRequest(StrictSchema):
    title: str | None = None
    body_markdown: str | None = None
    audience: AnnouncementAudienceValue | None = None
    is_pinned: bool | None = None
    expires_at: datetime | None = None


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_manager(request) -> None:
    user = request.auth_user
    if not user.is_active or not user.has_capability("announcements.manage"):
        raise APIError(403, "permission_denied", "The announcements.manage capability is required.")


def _raise(exc: AnnouncementError) -> NoReturn:
    if isinstance(exc, AnnouncementNotFound):
        raise APIError(404, "announcement_not_found", str(exc)) from exc
    if isinstance(exc, AnnouncementConflict):
        raise APIError(409, "announcement_not_editable", str(exc)) from exc
    if isinstance(exc, InvalidAnnouncementInput):
        raise APIError(422, "invalid_announcement_input", str(exc)) from exc
    raise APIError(500, "internal_error", "The Announcement operation could not be completed.") from exc


def _person(user) -> PersonSummary:
    return PersonSummary(id=user.pk, display_name=user.get_full_name())


def _reader(item) -> AnnouncementReaderResponse:
    return AnnouncementReaderResponse(
        id=item.pk,
        title=item.title,
        body_markdown=item.body_markdown,
        is_pinned=item.is_pinned,
        published_at=item.published_at,
        expires_at=item.expires_at,
    )


def _managed(item) -> AnnouncementManagementResponse:
    return AnnouncementManagementResponse(
        id=item.pk,
        title=item.title,
        body_markdown=item.body_markdown,
        audience=item.audience,
        status=item.status,
        is_pinned=item.is_pinned,
        published_at=item.published_at,
        expires_at=item.expires_at,
        created_by=_person(item.created_by),
        updated_by=_person(item.updated_by),
        published_by=_person(item.published_by) if item.published_by_id else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# Static management routes are intentionally registered before UUID reader routes.


@router.get(
    "/management",
    response=response_with_errors(AnnouncementManagementPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="announcementsListManaged",
)
def announcements_list_managed(
    request,
    status: AnnouncementStatusValue | None = None,
    audience: AnnouncementAudienceValue | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_manager(request)
    try:
        result = list_managed_announcements(
            status=status.value if status is not None else None,
            audience=audience.value if audience is not None else None,
            page=page,
            page_size=page_size,
        )
    except AnnouncementError as exc:
        _raise(exc)
    return AnnouncementManagementPageResponse(
        items=[_managed(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.post(
    "/management",
    response=response_with_errors(
        AnnouncementManagementResponse,
        401,
        403,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="announcementsCreateDraft",
)
def announcements_create_draft(request, payload: AnnouncementCreateRequest):
    _require_manager(request)
    try:
        item = create_announcement(
            actor=request.auth_user,
            title=payload.title,
            body_markdown=payload.body_markdown,
            audience=payload.audience.value,
            is_pinned=payload.is_pinned,
            expires_at=payload.expires_at,
            context=_context(request),
        )
    except AnnouncementError as exc:
        _raise(exc)
    return Status(201, _managed(item))


@router.get(
    "/management/{announcement_id}",
    response=response_with_errors(AnnouncementManagementResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="announcementsGetManaged",
)
def announcements_get_managed(request, announcement_id: UUID):
    _require_manager(request)
    try:
        item = get_managed_announcement(announcement_id=announcement_id)
    except AnnouncementError as exc:
        _raise(exc)
    return _managed(item)


@router.patch(
    "/management/{announcement_id}",
    response=response_with_errors(AnnouncementManagementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="announcementsUpdate",
)
def announcements_update(
    request,
    announcement_id: UUID,
    payload: AnnouncementUpdateRequest,
):
    _require_manager(request)
    values = payload.model_dump(exclude_unset=True)
    if "audience" in values and values["audience"] is not None:
        values["audience"] = values["audience"].value
    try:
        item = update_announcement(
            actor=request.auth_user,
            announcement_id=announcement_id,
            values=values,
            context=_context(request),
        )
    except AnnouncementError as exc:
        _raise(exc)
    return _managed(item)


@router.post(
    "/management/{announcement_id}/publish",
    response=response_with_errors(AnnouncementManagementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="announcementsPublish",
)
def announcements_publish(request, announcement_id: UUID):
    _require_manager(request)
    try:
        item = publish_announcement(
            actor=request.auth_user,
            announcement_id=announcement_id,
            context=_context(request),
        )
    except AnnouncementError as exc:
        _raise(exc)
    return _managed(item)


@router.post(
    "/management/{announcement_id}/archive",
    response=response_with_errors(AnnouncementManagementResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="announcementsArchive",
)
def announcements_archive(request, announcement_id: UUID):
    _require_manager(request)
    try:
        item = archive_announcement(
            actor=request.auth_user,
            announcement_id=announcement_id,
            context=_context(request),
        )
    except AnnouncementError as exc:
        _raise(exc)
    return _managed(item)


@router.get(
    "",
    response=response_with_errors(AnnouncementReaderPageResponse, 401, 422),
    auth=session_auth,
    operation_id="announcementsListVisible",
)
def announcements_list_visible(
    request,
    pinned: bool | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    try:
        result = list_visible_announcements(
            actor=request.auth_user,
            pinned=pinned,
            page=page,
            page_size=page_size,
        )
    except AnnouncementError as exc:
        _raise(exc)
    return AnnouncementReaderPageResponse(
        items=[_reader(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.get(
    "/{announcement_id}",
    response=response_with_errors(AnnouncementReaderResponse, 401, 404),
    auth=session_auth,
    operation_id="announcementsGetVisible",
)
def announcements_get_visible(request, announcement_id: UUID):
    try:
        item = get_visible_announcement(
            actor=request.auth_user,
            announcement_id=announcement_id,
        )
    except AnnouncementError as exc:
        _raise(exc)
    return _reader(item)


__all__ = ["router"]
