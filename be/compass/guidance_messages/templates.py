"""Shared reusable staff wording for Guidance Messages (ADR-104).

A template only prepares editable composer text. Nothing here sends a Message, publishes a realtime
hint or links a template to a Message: a Message written from a template is an ordinary Message.
Template text is generic office wording, not Student content, so it is stored as plain text and
never audited.
"""

import unicodedata
from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.utils import timezone

from compass.audit.actions import (
    GUIDANCE_MESSAGES_TEMPLATE_ARCHIVED,
    GUIDANCE_MESSAGES_TEMPLATE_CREATED,
    GUIDANCE_MESSAGES_TEMPLATE_RESTORED,
    GUIDANCE_MESSAGES_TEMPLATE_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from . import content, policy
from .errors import (
    InvalidMessageInput,
    MessagesConflict,
    MessagesPermissionDenied,
    TemplateNameTaken,
    TemplateNotFound,
)
from .models import GuidanceMessageTemplate, TemplateStatus

MANAGE_CAPABILITY = "guidance_messages.templates.manage"
NAME_LIMIT = 120
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_LENGTH = NAME_LIMIT


def _user(actor):
    """Any active Guidance staff member who can write operational Messages may use templates."""
    actor = policy.current_actor(actor)
    policy.require_actor(actor, manage=True, staff_only=True)
    return actor


def can_manage(actor) -> bool:
    return actor.has_capability(MANAGE_CAPABILITY)


def _manager(actor, *, lock=False):
    actor = policy.current_actor(actor, lock=lock)
    policy.require_actor(actor, manage=True, staff_only=True)
    if not can_manage(actor):
        raise MessagesPermissionDenied()
    return actor


def validate_name(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidMessageInput("Template name must be text.")
    name = value.strip()
    if not name or len(name) > NAME_LIMIT:
        raise InvalidMessageInput(f"Template name must contain 1 to {NAME_LIMIT} characters.")
    # One visible line: no NUL, line breaks or other control characters.
    if any(unicodedata.category(character) == "Cc" for character in name):
        raise InvalidMessageInput("Template name contains an unsupported character.")
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidMessageInput("Template name contains an unsupported character.") from None
    return name


def validate_body(value: object) -> str:
    return content.validate_text(value, label="Template text")


def _audit(actor, action, template, *, context=None, **metadata):
    # Structural only: never the template text, its before/after values or the request.
    record_event(
        context=context or AuditContext.user(actor),
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="guidance.messages.template",
        target_id=template.pk,
        metadata={"template_id": str(template.pk), "status": template.status, **metadata},
    )


def _pagination(page, page_size):
    if (
        type(page) is not int
        or page < 1
        or type(page_size) is not int
        or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        raise InvalidMessageInput("Use a positive page and page_size between 1 and 50.")


def list_templates(
    *, actor, status=TemplateStatus.ACTIVE, search=None, page=1, page_size=DEFAULT_PAGE_SIZE
):
    """Active templates for staff composers; archived ones only for template managers."""
    _pagination(page, page_size)
    if status not in TemplateStatus.values:
        raise InvalidMessageInput("status must be ACTIVE or ARCHIVED.")
    if search is not None and not isinstance(search, str):
        raise InvalidMessageInput("search must be text.")
    term = (search or "").strip()
    if len(term) > MAX_SEARCH_LENGTH:
        raise InvalidMessageInput(f"search must be at most {MAX_SEARCH_LENGTH} characters.")
    actor = _manager(actor) if status == TemplateStatus.ARCHIVED else _user(actor)
    query = GuidanceMessageTemplate.objects.filter(status=status)
    if term:
        query = query.filter(name__icontains=term)
    query = query.order_by(Lower("name"), "id")
    offset = (page - 1) * page_size
    rows = list(query[offset : offset + page_size + 1])
    return rows[:page_size], len(rows) > page_size


def _name_taken(name, *, exclude=None):
    query = GuidanceMessageTemplate.objects.filter(name__iexact=name)
    if exclude is not None:
        query = query.exclude(pk=exclude)
    return query.exists()


def _save(template, **kwargs):
    # The case-insensitive unique constraint is the final guard against a concurrent duplicate.
    try:
        with transaction.atomic():
            template.save(**kwargs)
    except IntegrityError:
        if _name_taken(template.name, exclude=template.pk):
            raise TemplateNameTaken() from None
        raise


@transaction.atomic
def create_template(*, actor, name, body, context=None):
    actor = _manager(actor, lock=True)
    name, body = validate_name(name), validate_body(body)
    if _name_taken(name):
        raise TemplateNameTaken()
    template = GuidanceMessageTemplate(name=name, body=body, created_by=actor, updated_by=actor)
    _save(template, force_insert=True)
    _audit(actor, GUIDANCE_MESSAGES_TEMPLATE_CREATED, template, context=context)
    return template


def _locked(template_id):
    template = GuidanceMessageTemplate.objects.select_for_update().filter(pk=template_id).first()
    if template is None:
        raise TemplateNotFound()
    return template


def _same_version(saved: datetime, expected: datetime) -> bool:
    if timezone.is_naive(expected):
        return False
    return saved == expected


@transaction.atomic
def update_template(
    *, actor, template_id, name=None, body=None, expected_updated_at=None, context=None
):
    """Edit an active template. Only future insertions change; sent Messages never do."""
    actor = _manager(actor, lock=True)
    if name is None and body is None:
        raise InvalidMessageInput("Provide a template name or text to change.")
    changes = {}
    if name is not None:
        changes["name"] = validate_name(name)
    if body is not None:
        changes["body"] = validate_body(body)
    template = _locked(template_id)
    if expected_updated_at is not None and not _same_version(
        template.updated_at, expected_updated_at
    ):
        raise MessagesConflict("This Message template changed after it was opened.")
    if template.status != TemplateStatus.ACTIVE:
        raise MessagesConflict("Restore this Message template before editing it.")
    changed = sorted(field for field, value in changes.items() if getattr(template, field) != value)
    if not changed:
        return template
    if "name" in changed and _name_taken(changes["name"], exclude=template.pk):
        raise TemplateNameTaken()
    for field in changed:
        setattr(template, field, changes[field])
    template.updated_by = actor
    _save(template, update_fields=(*changed, "updated_by", "updated_at"))
    _audit(
        actor,
        GUIDANCE_MESSAGES_TEMPLATE_UPDATED,
        template,
        context=context,
        changed_fields=changed,
    )
    return template


@transaction.atomic
def set_template_status(*, actor, template_id, archived, context=None):
    """Archive or restore. Repeating the current state changes nothing and records nothing."""
    actor = _manager(actor, lock=True)
    template = _locked(template_id)
    status = TemplateStatus.ARCHIVED if archived else TemplateStatus.ACTIVE
    if template.status == status:
        return template
    template.status = status
    template.archived_by = actor if archived else None
    template.archived_at = timezone.now() if archived else None
    template.updated_by = actor
    template.save(
        update_fields=("status", "archived_by", "archived_at", "updated_by", "updated_at")
    )
    action = (
        GUIDANCE_MESSAGES_TEMPLATE_ARCHIVED if archived else GUIDANCE_MESSAGES_TEMPLATE_RESTORED
    )
    _audit(actor, action, template, context=context)
    return template
