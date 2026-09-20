"""Transactional Curated Resource use cases and private file access."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    RESOURCE_ARCHIVED,
    RESOURCE_CREATED,
    RESOURCE_FILE_ATTACHED,
    RESOURCE_PUBLISHED,
    RESOURCE_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.integrations.storage import ObjectStorage
from compass.publications import PublicationAudience, PublicationStatus, eligible_audiences_for

from .models import Resource, ResourceCategory, ResourceKind

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_TITLE_LENGTH = 200
MAX_BODY_BYTES = 50 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
PDF_CONTENT_TYPE = "application/pdf"


class ResourceError(RuntimeError):
    pass


class ResourceNotFound(ResourceError):
    pass


class ResourceConflict(ResourceError):
    pass


class ResourceStorageError(ResourceError):
    pass


class InvalidResourceInput(ResourceError):
    pass


@dataclass(frozen=True, slots=True)
class ResourcePage:
    items: tuple[Resource, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class ResourceDownload:
    url: str
    expires_in_seconds: int


def _clean_title(value: str, *, require_nonblank: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidResourceInput("title must be a string")
    normalized = value.strip()
    if require_nonblank and not normalized:
        raise InvalidResourceInput("title is required before publication")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise InvalidResourceInput("title is too long")
    return normalized


def _clean_body(value: str, *, require_nonblank: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidResourceInput("body_markdown must be a string")
    if require_nonblank and not value.strip():
        raise InvalidResourceInput("body_markdown is required before publication")
    if len(value.encode("utf-8")) > MAX_BODY_BYTES:
        raise InvalidResourceInput("body_markdown is too large")
    return value


def _choice(value, choices, field: str) -> str:
    normalized = value.value if hasattr(value, "value") else value
    if normalized not in choices.values:
        raise InvalidResourceInput(f"{field} is invalid")
    return normalized


def _clean_external_url(value: str | None, *, required: bool = False) -> str:
    if value is None:
        normalized = ""
    elif isinstance(value, str):
        normalized = value.strip()
    else:
        raise InvalidResourceInput("external_url must be a string or null")
    if not normalized:
        if required:
            raise InvalidResourceInput("external_url is required for EXTERNAL_LINK Resources")
        return ""
    if len(normalized) > 2048:
        raise InvalidResourceInput("external_url is too long")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidResourceInput("external_url must use http or https")
    if parsed.username or parsed.password:
        raise InvalidResourceInput("external_url must not contain embedded credentials")
    return normalized


def _clean_display_order(value: int) -> int:
    if type(value) is not int:
        raise InvalidResourceInput("display_order must be an integer")
    if not -(2**31) <= value <= 2**31 - 1:
        raise InvalidResourceInput("display_order is outside the supported range")
    return value


def _clean_page(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidResourceInput("page must be at least 1")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidResourceInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _page(queryset, *, page: int, page_size: int) -> ResourcePage:
    page, page_size = _clean_page(page, page_size)
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return ResourcePage(
        items=tuple(rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )


def _visible_queryset(actor: User):
    audiences = eligible_audiences_for(actor)
    if not audiences:
        return Resource.objects.none()
    return Resource.objects.filter(
        status=PublicationStatus.PUBLISHED,
        published_at__lte=timezone.now(),
        audience__in=audiences,
    )


def list_visible_resources(
    *,
    actor: User,
    category: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ResourcePage:
    queryset = _visible_queryset(actor)
    if category is not None:
        queryset = queryset.filter(
            category=_choice(category, ResourceCategory, "category")
        )
    if kind is not None:
        queryset = queryset.filter(kind=_choice(kind, ResourceKind, "kind"))
    return _page(
        queryset.order_by("display_order", "-published_at", "-id"),
        page=page,
        page_size=page_size,
    )


def get_visible_resource(*, actor: User, resource_id: UUID) -> Resource:
    item = _visible_queryset(actor).filter(pk=resource_id).first()
    if item is None:
        raise ResourceNotFound("The requested Resource was not found.")
    return item


def list_managed_resources(
    *,
    status: str | None = None,
    audience: str | None = None,
    category: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ResourcePage:
    queryset = Resource.objects.select_related(
        "created_by", "updated_by", "published_by"
    ).all()
    if status is not None:
        queryset = queryset.filter(
            status=_choice(status, PublicationStatus, "status")
        )
    if audience is not None:
        queryset = queryset.filter(
            audience=_choice(audience, PublicationAudience, "audience")
        )
    if category is not None:
        queryset = queryset.filter(
            category=_choice(category, ResourceCategory, "category")
        )
    if kind is not None:
        queryset = queryset.filter(kind=_choice(kind, ResourceKind, "kind"))
    return _page(
        queryset.order_by("-updated_at", "-id"),
        page=page,
        page_size=page_size,
    )


def get_managed_resource(*, resource_id: UUID) -> Resource:
    item = (
        Resource.objects.select_related("created_by", "updated_by", "published_by")
        .filter(pk=resource_id)
        .first()
    )
    if item is None:
        raise ResourceNotFound("The requested Resource was not found.")
    return item


def _validate_channel_state(item: Resource, *, for_publish: bool) -> None:
    if item.kind == ResourceKind.ARTICLE:
        if item.external_url or item.storage_key:
            raise InvalidResourceInput("ARTICLE Resources cannot have a URL or file")
    elif item.kind == ResourceKind.EXTERNAL_LINK:
        if item.storage_key:
            raise InvalidResourceInput("EXTERNAL_LINK Resources cannot have a file")
        item.external_url = _clean_external_url(item.external_url, required=for_publish)
    elif item.kind == ResourceKind.FILE:
        if item.external_url:
            raise InvalidResourceInput("FILE Resources cannot have an external URL")
        if for_publish and (
            not item.storage_key
            or not item.original_filename
            or item.content_type != PDF_CONTENT_TYPE
            or item.size_bytes <= 0
        ):
            raise InvalidResourceInput("A validated PDF file is required before publication")
    else:
        raise InvalidResourceInput("kind is invalid")


@transaction.atomic
def create_resource(
    *,
    actor: User,
    title: str,
    body_markdown: str,
    category: str,
    kind: str,
    audience: str,
    external_url: str | None,
    display_order: int,
    context: AuditContext,
) -> Resource:
    normalized_kind = _choice(kind, ResourceKind, "kind")
    normalized_external_url = _clean_external_url(external_url)
    if normalized_kind != ResourceKind.EXTERNAL_LINK and normalized_external_url:
        raise InvalidResourceInput("external_url is only valid for EXTERNAL_LINK Resources")
    item = Resource(
        title=_clean_title(title),
        body_markdown=_clean_body(body_markdown),
        category=_choice(category, ResourceCategory, "category"),
        kind=normalized_kind,
        audience=_choice(audience, PublicationAudience, "audience"),
        external_url=normalized_external_url,
        display_order=_clean_display_order(display_order),
        created_by=actor,
        updated_by=actor,
    )
    _validate_channel_state(item, for_publish=False)
    item.save()
    record_event(
        context=context,
        action=RESOURCE_CREATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="resources.resource",
        target_id=item.pk,
        metadata={
            "status": item.status,
            "audience": item.audience,
            "kind": item.kind,
            "category": item.category,
        },
    )
    return item


@transaction.atomic
def update_resource(
    *,
    actor: User,
    resource_id: UUID,
    values: dict[str, object],
    context: AuditContext,
) -> Resource:
    item = Resource.objects.select_for_update().filter(pk=resource_id).first()
    if item is None:
        raise ResourceNotFound("The requested Resource was not found.")
    if item.status == PublicationStatus.ARCHIVED:
        raise ResourceConflict("Archived Resources cannot be edited.")

    allowed = {
        "title",
        "body_markdown",
        "category",
        "kind",
        "audience",
        "external_url",
        "display_order",
    }
    unknown = set(values) - allowed
    if unknown:
        raise InvalidResourceInput(f"unsupported Resource fields: {sorted(unknown)}")

    if "kind" in values:
        new_kind = _choice(values["kind"], ResourceKind, "kind")
        if item.status == PublicationStatus.PUBLISHED and new_kind != item.kind:
            raise ResourceConflict("A published Resource kind cannot be changed.")
        if item.storage_key and new_kind != ResourceKind.FILE:
            raise ResourceConflict("Remove or replace the draft FILE Resource instead of changing kind.")
        item.kind = new_kind

    if "title" in values:
        item.title = _clean_title(values["title"])  # type: ignore[arg-type]
    if "body_markdown" in values:
        item.body_markdown = _clean_body(values["body_markdown"])  # type: ignore[arg-type]
    if "category" in values:
        item.category = _choice(values["category"], ResourceCategory, "category")
    if "audience" in values:
        item.audience = _choice(values["audience"], PublicationAudience, "audience")
    if "external_url" in values:
        item.external_url = _clean_external_url(values["external_url"])  # type: ignore[arg-type]
    if "display_order" in values:
        item.display_order = _clean_display_order(values["display_order"])  # type: ignore[arg-type]

    if item.kind != ResourceKind.EXTERNAL_LINK and item.external_url:
        raise InvalidResourceInput("external_url is only valid for EXTERNAL_LINK Resources")
    _validate_channel_state(item, for_publish=item.status == PublicationStatus.PUBLISHED)

    item.updated_by = actor
    item.save()
    record_event(
        context=context,
        action=RESOURCE_UPDATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="resources.resource",
        target_id=item.pk,
        metadata={
            "status": item.status,
            "audience": item.audience,
            "kind": item.kind,
            "category": item.category,
        },
    )
    return item


def _safe_filename(value: str | None) -> str:
    normalized = (value or "resource.pdf").replace("\\", "/")
    normalized = PurePosixPath(normalized).name.strip()
    if not normalized:
        normalized = "resource.pdf"
    if len(normalized) > 255:
        normalized = normalized[-255:]
    return normalized


def attach_resource_file(
    *,
    actor: User,
    resource_id: UUID,
    uploaded_file,
    context: AuditContext,
    storage: ObjectStorage | None = None,
) -> Resource:
    if uploaded_file is None:
        raise InvalidResourceInput("A PDF file is required.")
    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type != PDF_CONTENT_TYPE:
        raise InvalidResourceInput("Only application/pdf files are supported.")

    data = uploaded_file.read(MAX_FILE_BYTES + 1)
    if not isinstance(data, bytes):
        data = bytes(data)
    if len(data) == 0:
        raise InvalidResourceInput("The PDF file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise InvalidResourceInput("The PDF file exceeds the 10 MiB limit.")
    if not data.startswith(b"%PDF-"):
        raise InvalidResourceInput("The uploaded file is not a valid PDF signature.")

    current = Resource.objects.filter(pk=resource_id).only("status", "kind").first()
    if current is None:
        raise ResourceNotFound("The requested Resource was not found.")
    if current.status != PublicationStatus.DRAFT:
        raise ResourceConflict("Files can only be attached or replaced while Resource is DRAFT.")
    if current.kind != ResourceKind.FILE:
        raise ResourceConflict("A file can only be attached to a FILE Resource.")

    object_storage = storage or ObjectStorage()
    requested_key = f"resources/{resource_id}/{uuid.uuid4().hex}.pdf"
    try:
        saved_key = object_storage.save(requested_key, BytesIO(data))
    except Exception as exc:
        raise ResourceStorageError("The Resource file could not be stored.") from exc

    old_key = ""
    try:
        with transaction.atomic():
            item = Resource.objects.select_for_update().filter(pk=resource_id).first()
            if item is None:
                raise ResourceNotFound("The requested Resource was not found.")
            if item.status != PublicationStatus.DRAFT or item.kind != ResourceKind.FILE:
                raise ResourceConflict(
                    "The Resource changed and no longer accepts a draft file attachment."
                )
            old_key = item.storage_key
            item.storage_key = saved_key
            item.original_filename = _safe_filename(getattr(uploaded_file, "name", None))
            item.content_type = PDF_CONTENT_TYPE
            item.size_bytes = len(data)
            item.updated_by = actor
            item.save(
                update_fields=[
                    "storage_key",
                    "original_filename",
                    "content_type",
                    "size_bytes",
                    "updated_by",
                    "updated_at",
                ]
            )
            record_event(
                context=context,
                action=RESOURCE_FILE_ATTACHED,
                outcome=AuditOutcome.SUCCESS,
                target_type="resources.resource",
                target_id=item.pk,
                metadata={
                    "status": item.status,
                    "audience": item.audience,
                    "kind": item.kind,
                    "category": item.category,
                },
            )
    except Exception:
        try:
            object_storage.delete(saved_key)
        except Exception:
            pass
        raise

    if old_key and old_key != saved_key:
        try:
            object_storage.delete(old_key)
        except Exception:
            pass
    return get_managed_resource(resource_id=resource_id)


@transaction.atomic
def publish_resource(
    *,
    actor: User,
    resource_id: UUID,
    context: AuditContext,
) -> Resource:
    item = Resource.objects.select_for_update().filter(pk=resource_id).first()
    if item is None:
        raise ResourceNotFound("The requested Resource was not found.")
    if item.status != PublicationStatus.DRAFT:
        raise ResourceConflict("Only a draft Resource can be published.")

    item.title = _clean_title(item.title, require_nonblank=True)
    item.body_markdown = _clean_body(item.body_markdown, require_nonblank=True)
    item.category = _choice(item.category, ResourceCategory, "category")
    item.kind = _choice(item.kind, ResourceKind, "kind")
    item.audience = _choice(item.audience, PublicationAudience, "audience")
    _validate_channel_state(item, for_publish=True)

    item.status = PublicationStatus.PUBLISHED
    item.published_at = timezone.now()
    item.published_by = actor
    item.updated_by = actor
    item.save()
    record_event(
        context=context,
        action=RESOURCE_PUBLISHED,
        outcome=AuditOutcome.SUCCESS,
        target_type="resources.resource",
        target_id=item.pk,
        metadata={
            "from_status": PublicationStatus.DRAFT,
            "to_status": PublicationStatus.PUBLISHED,
            "audience": item.audience,
            "kind": item.kind,
            "category": item.category,
        },
    )
    return item


@transaction.atomic
def archive_resource(
    *,
    actor: User,
    resource_id: UUID,
    context: AuditContext,
) -> Resource:
    item = Resource.objects.select_for_update().filter(pk=resource_id).first()
    if item is None:
        raise ResourceNotFound("The requested Resource was not found.")
    if item.status == PublicationStatus.ARCHIVED:
        raise ResourceConflict("The Resource is already archived.")

    previous = item.status
    item.status = PublicationStatus.ARCHIVED
    item.updated_by = actor
    item.save(update_fields=["status", "updated_by", "updated_at"])
    record_event(
        context=context,
        action=RESOURCE_ARCHIVED,
        outcome=AuditOutcome.SUCCESS,
        target_type="resources.resource",
        target_id=item.pk,
        metadata={
            "from_status": previous,
            "to_status": PublicationStatus.ARCHIVED,
            "audience": item.audience,
            "kind": item.kind,
            "category": item.category,
        },
    )
    return item


def create_resource_download(
    *,
    actor: User,
    resource_id: UUID,
    storage: ObjectStorage | None = None,
) -> ResourceDownload:
    item = get_visible_resource(actor=actor, resource_id=resource_id)
    if item.kind != ResourceKind.FILE or not item.storage_key:
        raise ResourceConflict("The requested Resource does not have a downloadable file.")
    object_storage = storage or ObjectStorage()
    ttl = settings.RESOURCE_DOWNLOAD_URL_TTL_SECONDS
    try:
        url = object_storage.private_url(item.storage_key, expires_seconds=ttl)
    except Exception as exc:
        raise ResourceStorageError("Private Resource download access is unavailable.") from exc
    return ResourceDownload(url=url, expires_in_seconds=ttl)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "InvalidResourceInput",
    "MAX_FILE_BYTES",
    "MAX_PAGE_SIZE",
    "PDF_CONTENT_TYPE",
    "ResourceConflict",
    "ResourceDownload",
    "ResourceError",
    "ResourceNotFound",
    "ResourcePage",
    "ResourceStorageError",
    "archive_resource",
    "attach_resource_file",
    "create_resource",
    "create_resource_download",
    "get_managed_resource",
    "get_visible_resource",
    "list_managed_resources",
    "list_visible_resources",
    "publish_resource",
    "update_resource",
]
