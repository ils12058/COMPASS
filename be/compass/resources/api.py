"""Authenticated reader and capability-authorized Curated Resource API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import File, Router, Schema, Status, UploadedFile
from pydantic import ConfigDict

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError
from compass.publications import PublicationAudience, PublicationStatus

from .models import ResourceCategory, ResourceKind
from .services import (
    DEFAULT_PAGE_SIZE,
    InvalidResourceInput,
    ResourceConflict,
    ResourceError,
    ResourceNotFound,
    ResourceStorageError,
    archive_resource,
    attach_resource_file,
    create_resource,
    create_resource_download,
    get_managed_resource,
    get_visible_resource,
    list_managed_resources,
    list_visible_resources,
    publish_resource,
    update_resource,
)

router = Router(tags=["resources"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class ResourceAudienceValue(StrEnum):
    ALL_AUTHENTICATED = PublicationAudience.ALL_AUTHENTICATED
    STUDENTS = PublicationAudience.STUDENTS
    GCO_PERSONNEL = PublicationAudience.GCO_PERSONNEL


class ResourceStatusValue(StrEnum):
    DRAFT = PublicationStatus.DRAFT
    PUBLISHED = PublicationStatus.PUBLISHED
    ARCHIVED = PublicationStatus.ARCHIVED


class ResourceKindValue(StrEnum):
    ARTICLE = ResourceKind.ARTICLE
    EXTERNAL_LINK = ResourceKind.EXTERNAL_LINK
    FILE = ResourceKind.FILE


class ResourceCategoryValue(StrEnum):
    GENERAL = ResourceCategory.GENERAL
    COUNSELING = ResourceCategory.COUNSELING
    MENTAL_HEALTH = ResourceCategory.MENTAL_HEALTH
    ACADEMIC_SUPPORT = ResourceCategory.ACADEMIC_SUPPORT
    CAREER = ResourceCategory.CAREER
    WELLNESS = ResourceCategory.WELLNESS
    FORMS_AND_GUIDES = ResourceCategory.FORMS_AND_GUIDES
    OTHER = ResourceCategory.OTHER


class PersonSummary(StrictSchema):
    id: UUID
    display_name: str


class ResourceReaderResponse(StrictSchema):
    id: UUID
    title: str
    body_markdown: str
    category: ResourceCategoryValue
    kind: ResourceKindValue
    external_url: str | None
    published_at: datetime


class ResourceManagementResponse(StrictSchema):
    id: UUID
    title: str
    body_markdown: str
    category: ResourceCategoryValue
    kind: ResourceKindValue
    audience: ResourceAudienceValue
    status: ResourceStatusValue
    external_url: str | None
    original_filename: str | None
    content_type: str | None
    size_bytes: int
    has_file: bool
    display_order: int
    published_at: datetime | None
    created_by: PersonSummary
    updated_by: PersonSummary
    published_by: PersonSummary | None
    created_at: datetime
    updated_at: datetime


class ResourceReaderPageResponse(StrictSchema):
    items: list[ResourceReaderResponse]
    page: int
    page_size: int
    has_next: bool


class ResourceManagementPageResponse(StrictSchema):
    items: list[ResourceManagementResponse]
    page: int
    page_size: int
    has_next: bool


class ResourceDownloadResponse(StrictSchema):
    url: str
    expires_in_seconds: int


class ResourceCreateRequest(StrictSchema):
    title: str
    body_markdown: str
    category: ResourceCategoryValue
    kind: ResourceKindValue
    audience: ResourceAudienceValue
    external_url: str | None = None
    display_order: int = 0


class ResourceUpdateRequest(StrictSchema):
    title: str | None = None
    body_markdown: str | None = None
    category: ResourceCategoryValue | None = None
    kind: ResourceKindValue | None = None
    audience: ResourceAudienceValue | None = None
    external_url: str | None = None
    display_order: int | None = None


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_manager(request) -> None:
    user = request.auth_user
    if not user.is_active or not user.has_capability("resources.manage"):
        raise APIError(403, "permission_denied", "The resources.manage capability is required.")


def _raise(exc: ResourceError) -> NoReturn:
    if isinstance(exc, ResourceNotFound):
        raise APIError(404, "resource_not_found", str(exc)) from exc
    if isinstance(exc, ResourceConflict):
        raise APIError(409, "resource_conflict", str(exc)) from exc
    if isinstance(exc, InvalidResourceInput):
        raise APIError(422, "invalid_resource_input", str(exc)) from exc
    if isinstance(exc, ResourceStorageError):
        raise APIError(503, "resource_storage_unavailable", str(exc)) from exc
    raise APIError(500, "internal_error", "The Resource operation could not be completed.") from exc


def _person(user) -> PersonSummary:
    return PersonSummary(id=user.pk, display_name=user.get_full_name())


def _reader(item) -> ResourceReaderResponse:
    return ResourceReaderResponse(
        id=item.pk,
        title=item.title,
        body_markdown=item.body_markdown,
        category=item.category,
        kind=item.kind,
        external_url=item.external_url or None,
        published_at=item.published_at,
    )


def _managed(item) -> ResourceManagementResponse:
    return ResourceManagementResponse(
        id=item.pk,
        title=item.title,
        body_markdown=item.body_markdown,
        category=item.category,
        kind=item.kind,
        audience=item.audience,
        status=item.status,
        external_url=item.external_url or None,
        original_filename=item.original_filename or None,
        content_type=item.content_type or None,
        size_bytes=item.size_bytes,
        has_file=bool(item.storage_key),
        display_order=item.display_order,
        published_at=item.published_at,
        created_by=_person(item.created_by),
        updated_by=_person(item.updated_by),
        published_by=_person(item.published_by) if item.published_by_id else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# Static management routes are intentionally registered before UUID reader routes.


@router.get(
    "/management",
    response=response_with_errors(ResourceManagementPageResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="resourcesListManaged",
)
def resources_list_managed(
    request,
    status: ResourceStatusValue | None = None,
    audience: ResourceAudienceValue | None = None,
    category: ResourceCategoryValue | None = None,
    kind: ResourceKindValue | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    _require_manager(request)
    try:
        result = list_managed_resources(
            status=status.value if status is not None else None,
            audience=audience.value if audience is not None else None,
            category=category.value if category is not None else None,
            kind=kind.value if kind is not None else None,
            page=page,
            page_size=page_size,
        )
    except ResourceError as exc:
        _raise(exc)
    return ResourceManagementPageResponse(
        items=[_managed(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.post(
    "/management",
    response=response_with_errors(
        ResourceManagementResponse,
        401,
        403,
        422,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="resourcesCreateDraft",
)
def resources_create_draft(request, payload: ResourceCreateRequest):
    _require_manager(request)
    try:
        item = create_resource(
            actor=request.auth_user,
            title=payload.title,
            body_markdown=payload.body_markdown,
            category=payload.category.value,
            kind=payload.kind.value,
            audience=payload.audience.value,
            external_url=payload.external_url,
            display_order=payload.display_order,
            context=_context(request),
        )
    except ResourceError as exc:
        _raise(exc)
    return Status(201, _managed(item))


@router.get(
    "/management/{resource_id}",
    response=response_with_errors(ResourceManagementResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="resourcesGetManaged",
)
def resources_get_managed(request, resource_id: UUID):
    _require_manager(request)
    try:
        item = get_managed_resource(resource_id=resource_id)
    except ResourceError as exc:
        _raise(exc)
    return _managed(item)


@router.patch(
    "/management/{resource_id}",
    response=response_with_errors(ResourceManagementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="resourcesUpdate",
)
def resources_update(request, resource_id: UUID, payload: ResourceUpdateRequest):
    _require_manager(request)
    values = payload.model_dump(exclude_unset=True)
    for field in ("category", "kind", "audience"):
        if field in values and values[field] is not None:
            values[field] = values[field].value
    try:
        item = update_resource(
            actor=request.auth_user,
            resource_id=resource_id,
            values=values,
            context=_context(request),
        )
    except ResourceError as exc:
        _raise(exc)
    return _managed(item)


@router.post(
    "/management/{resource_id}/file",
    response=response_with_errors(ResourceManagementResponse, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="resourcesAttachDraftFile",
)
def resources_attach_draft_file(
    request,
    resource_id: UUID,
    file: File[UploadedFile],
):
    _require_manager(request)
    try:
        item = attach_resource_file(
            actor=request.auth_user,
            resource_id=resource_id,
            uploaded_file=file,
            context=_context(request),
        )
    except ResourceError as exc:
        _raise(exc)
    return _managed(item)


@router.post(
    "/management/{resource_id}/publish",
    response=response_with_errors(ResourceManagementResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="resourcesPublish",
)
def resources_publish(request, resource_id: UUID):
    _require_manager(request)
    try:
        item = publish_resource(
            actor=request.auth_user,
            resource_id=resource_id,
            context=_context(request),
        )
    except ResourceError as exc:
        _raise(exc)
    return _managed(item)


@router.post(
    "/management/{resource_id}/archive",
    response=response_with_errors(ResourceManagementResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="resourcesArchive",
)
def resources_archive(request, resource_id: UUID):
    _require_manager(request)
    try:
        item = archive_resource(
            actor=request.auth_user,
            resource_id=resource_id,
            context=_context(request),
        )
    except ResourceError as exc:
        _raise(exc)
    return _managed(item)


@router.get(
    "",
    response=response_with_errors(ResourceReaderPageResponse, 401, 422),
    auth=session_auth,
    operation_id="resourcesListVisible",
)
def resources_list_visible(
    request,
    category: ResourceCategoryValue | None = None,
    kind: ResourceKindValue | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    try:
        result = list_visible_resources(
            actor=request.auth_user,
            category=category.value if category is not None else None,
            kind=kind.value if kind is not None else None,
            page=page,
            page_size=page_size,
        )
    except ResourceError as exc:
        _raise(exc)
    return ResourceReaderPageResponse(
        items=[_reader(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
    )


@router.get(
    "/{resource_id}/download",
    response=response_with_errors(ResourceDownloadResponse, 401, 404, 409, 503),
    auth=session_auth,
    operation_id="resourcesDownloadVisibleFile",
)
def resources_download_visible_file(request, resource_id: UUID):
    try:
        result = create_resource_download(actor=request.auth_user, resource_id=resource_id)
    except ResourceError as exc:
        _raise(exc)
    return ResourceDownloadResponse(
        url=result.url,
        expires_in_seconds=result.expires_in_seconds,
    )


@router.get(
    "/{resource_id}",
    response=response_with_errors(ResourceReaderResponse, 401, 404),
    auth=session_auth,
    operation_id="resourcesGetVisible",
)
def resources_get_visible(request, resource_id: UUID):
    try:
        item = get_visible_resource(actor=request.auth_user, resource_id=resource_id)
    except ResourceError as exc:
        _raise(exc)
    return _reader(item)


__all__ = ["router"]
