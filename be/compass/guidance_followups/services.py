"""Domain-owned transactional Follow-Up lifecycle. Never mutates source-domain rows."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from . import policy
from .content import decrypt_text, encrypt_text
from .errors import FollowUpConflict, FollowUpInvalid, FollowUpNotFound
from .models import (
    FollowUpEventType,
    FollowUpStatus,
    FollowUpVisibility,
    GuidanceFollowUp,
    GuidanceFollowUpEvent,
)

MAX_PAGE = 100
MAX_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class FollowUpPage:
    items: tuple[GuidanceFollowUp, ...]
    page: int
    page_size: int
    has_next: bool


def _due(value: datetime, *, now):
    if not isinstance(value, datetime) or timezone.is_naive(value) or value <= now:
        raise FollowUpInvalid("Choose a future date and time.")
    return value


def _fingerprint(value: str):
    if not isinstance(value, str) or len(value) != 64:
        raise FollowUpInvalid("The request fingerprint is invalid.")
    try:
        int(value, 16)
    except ValueError:
        raise FollowUpInvalid("The request fingerprint is invalid.") from None
    return value.lower()


def _creation_key(actor, key):
    if not isinstance(key, str) or not 12 <= len(key) <= 128 or not key.isascii():
        raise FollowUpInvalid("A valid Idempotency-Key is required.")
    return hashlib.sha256(f"{actor.pk}\0{key}".encode()).hexdigest()


def _load(followup_id, *, lock=False):
    qs = GuidanceFollowUp.objects.select_related(
        "student__role",
        "assigned_to",
        "created_by",
    )
    if lock:
        qs = qs.select_for_update(of=("self",))
    row = qs.filter(pk=followup_id).first()
    if row is None:
        raise FollowUpNotFound("The Guidance Follow-Up was not found.")
    return row


def _event(
    item,
    *,
    actor,
    kind,
    remarks=None,
    old_assignee=None,
    new_assignee=None,
    old_due=None,
    new_due=None,
):
    event = GuidanceFollowUpEvent(
        followup=item,
        actor=actor,
        kind=kind,
        revision=item.version,
        old_assignee=old_assignee,
        new_assignee=new_assignee,
        old_due_at=old_due,
        new_due_at=new_due,
    )
    if remarks is not None:
        event.remarks_ciphertext = encrypt_text(
            item.pk,
            "remarks",
            remarks,
            event_id=event.pk,
            required=True,
        )
    event.save(force_insert=True)
    return event


def _audit(context, action, item, *, metadata=None):
    record_event(
        context=context,
        action=f"guidance_followup.{action}",
        outcome=AuditOutcome.SUCCESS,
        target_type="guidancefollowups.guidancefollowup",
        target_id=item.pk,
        metadata={"version": item.version, **(metadata or {})},
    )


def create_followup(
    *,
    actor: User,
    student_id: UUID,
    assigned_to_id: UUID,
    category: str,
    due_at: datetime,
    source_kind: str | None,
    source_id: UUID | None,
    description: str | None,
    visibility: str | None,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
    now=None,
) -> GuidanceFollowUp:
    at = now or timezone.now()
    actor = policy.current_actor(actor, manage=True)
    key = _creation_key(actor, idempotency_key)
    fingerprint = _fingerprint(request_fingerprint)
    if (source_kind is None) != (source_id is None):
        raise FollowUpInvalid("Choose a complete related-record reference or none.")
    classification = policy.classify(source_kind=source_kind, category=category)
    if visibility is not None and visibility != classification:
        raise FollowUpInvalid("The confidentiality of this follow-up cannot be changed.")
    with transaction.atomic():
        # Serializing the actor row also makes same-key retry safe under concurrent requests.
        actor = policy.current_actor(actor, manage=True, lock=True)
        existing = GuidanceFollowUp.objects.filter(creation_key_digest=key).first()
        if existing is not None:
            if existing.creation_request_fingerprint != fingerprint:
                raise FollowUpConflict("This confirmation was already used for another request.")
            if existing.assigned_to_id == actor.pk:
                policy.require_followup(actor, existing, manage=True)
            elif (
                existing.visibility != FollowUpVisibility.OPERATIONAL
                or not policy.in_operational_scope(actor, existing.student_id)
            ):
                raise FollowUpNotFound("The Follow-Up is unavailable.")
            policy.valid_student(existing.student_id)
            return existing
        _due(due_at, now=at)
        student = policy.valid_student(student_id, lock=True)
        if source_kind:
            policy.require_source(
                actor,
                kind=source_kind,
                source_id=source_id,
                student_id=student.pk,
                manage=True,
            )
        elif not policy.in_operational_scope(actor, student.pk):
            raise FollowUpNotFound("The Student is not available for Follow-Ups.")
        assignee = policy.require_assignee(
            assigned_to_id,
            student_id=student.pk,
            visibility=classification,
            source_kind=source_kind,
            source_id=source_id,
        )
        if classification == FollowUpVisibility.COUNSELOR_CONFIDENTIAL and assignee.pk != actor.pk:
            raise FollowUpInvalid("Only the linked Counselor may own this follow-up.")
        item = GuidanceFollowUp(
            student=student,
            assigned_to=assignee,
            category=category,
            visibility=classification,
            due_at=due_at,
            source_kind=source_kind,
            source_id=source_id,
            created_by=actor,
            creation_key_digest=key,
            creation_request_fingerprint=fingerprint,
        )
        if description is not None:
            item.description_ciphertext = encrypt_text(item.pk, "description", description)
        item.save(force_insert=True)
        _event(
            item, actor=actor, kind=FollowUpEventType.CREATED, new_assignee=assignee, new_due=due_at
        )
        _audit(context, "created", item, metadata={"category": category})
        return item


def get_followup(*, actor, followup_id):
    actor = policy.current_actor(actor)
    return policy.require_followup(actor, _load(followup_id))


def list_followups(
    *,
    actor,
    status=None,
    student_id=None,
    assigned_to_id=None,
    source_kind=None,
    source_id=None,
    due_window=None,
    ordering="EARLIEST_DUE",
    page=1,
    page_size=20,
    now=None,
) -> FollowUpPage:
    actor = policy.current_actor(actor)
    if type(page) is not int or not 1 <= page <= MAX_PAGE:
        raise FollowUpInvalid("The requested page is unavailable.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise FollowUpInvalid("Choose between 1 and 50 items per page.")
    if status is not None and status not in FollowUpStatus.values:
        raise FollowUpInvalid("The follow-up status is invalid.")
    qs = policy.scope(actor, GuidanceFollowUp.objects.select_related("student", "assigned_to"))
    if status is not None:
        qs = qs.filter(status=status)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if assigned_to_id is not None:
        qs = qs.filter(assigned_to_id=assigned_to_id)
    if source_kind is not None or source_id is not None:
        from .workspace import source_context

        source_context(actor=actor, source_kind=source_kind, source_id=source_id)
        qs = qs.filter(source_kind=source_kind, source_id=source_id)
    if due_window == "OVERDUE":
        qs = qs.filter(status="PENDING", due_at__lt=now or timezone.now())
    elif due_window == "UPCOMING":
        qs = qs.filter(status="PENDING", due_at__gte=now or timezone.now())
    elif due_window is not None:
        raise FollowUpInvalid("The due-date filter is unsupported.")
    ordering = ordering or "EARLIEST_DUE"
    if ordering not in {"EARLIEST_DUE", "LATEST_DUE"}:
        raise FollowUpInvalid("The requested order is unsupported.")
    # SQL scope precedes pagination; one fixed-size page plus its has_next proof.
    offset = (page - 1) * page_size
    rows = list(
        qs.order_by("-due_at" if ordering == "LATEST_DUE" else "due_at", "id")[
            offset : offset + page_size + 1
        ]
    )
    return FollowUpPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def _lock_for_mutation(*, actor, followup_id, expected_version):
    if type(expected_version) is not int or expected_version < 1:
        raise FollowUpInvalid("An expected version is required.")
    item = _load(followup_id, lock=True)
    policy.require_followup(actor, item, manage=True)
    if item.version != expected_version:
        raise FollowUpConflict("This follow-up changed. Review the latest details.")
    if item.status != FollowUpStatus.PENDING:
        raise FollowUpConflict("This follow-up is no longer pending.")
    return item


def update_followup(
    *,
    actor,
    followup_id,
    expected_version,
    context,
    due_at=None,
    category=None,
    description=None,
    now=None,
):
    at = now or timezone.now()
    with transaction.atomic():
        actor = policy.current_actor(actor, manage=True, lock=True)
        item = _lock_for_mutation(
            actor=actor,
            followup_id=followup_id,
            expected_version=expected_version,
        )
        changed = []
        old_due = item.due_at
        if due_at is not None:
            _due(due_at, now=at)
            if due_at != old_due:
                item.due_at = due_at
                changed.append("due_at")
        if category is not None:
            if policy.classify(source_kind=item.source_kind, category=category) != item.visibility:
                raise FollowUpInvalid("This category cannot change confidentiality.")
            if category != item.category:
                item.category = category
                changed.append("category")
        if description is not None:
            encrypted = encrypt_text(item.pk, "description", description)
            item.description_ciphertext = encrypted
            changed.append("description")
        if not changed:
            return item
        item.version += 1
        item.save(
            update_fields=["due_at", "category", "description_ciphertext", "version", "updated_at"]
        )
        _event(
            item, actor=actor, kind=FollowUpEventType.UPDATED, old_due=old_due, new_due=item.due_at
        )
        _audit(context, "updated", item, metadata={"fields": changed})
        return item


def reassign_followup(*, actor, followup_id, expected_version, assigned_to_id, context):
    with transaction.atomic():
        actor = policy.current_actor(actor, manage=True, lock=True)
        item = _lock_for_mutation(
            actor=actor,
            followup_id=followup_id,
            expected_version=expected_version,
        )
        new = policy.require_assignee(
            assigned_to_id,
            student_id=item.student_id,
            visibility=item.visibility,
            source_kind=item.source_kind,
            source_id=item.source_id,
        )
        if new.pk == item.assigned_to_id:
            return item
        previous = item.assigned_to
        item.assigned_to = new
        item.version += 1
        item.save(update_fields=["assigned_to", "version", "updated_at"])
        _event(
            item,
            actor=actor,
            kind=FollowUpEventType.REASSIGNED,
            old_assignee=previous,
            new_assignee=new,
        )
        _audit(context, "reassigned", item, metadata={"assigned_to_id": str(new.pk)})
        return item


def record_activity(*, actor, followup_id, expected_version, remarks, context):
    with transaction.atomic():
        actor = policy.current_actor(actor, manage=True, lock=True)
        item = _lock_for_mutation(
            actor=actor,
            followup_id=followup_id,
            expected_version=expected_version,
        )
        item.version += 1
        event = _event(item, actor=actor, kind=FollowUpEventType.ACTIVITY_RECORDED, remarks=remarks)
        item.save(update_fields=["version", "updated_at"])
        _audit(context, "activity_recorded", item)
        return item, event


def complete_followup(*, actor, followup_id, expected_version, outcome, context, now=None):
    at = now or timezone.now()
    with transaction.atomic():
        actor = policy.current_actor(actor, manage=True, lock=True)
        item = _lock_for_mutation(
            actor=actor,
            followup_id=followup_id,
            expected_version=expected_version,
        )
        item.outcome_ciphertext = encrypt_text(item.pk, "outcome", outcome, required=True)
        item.status = FollowUpStatus.COMPLETED
        item.completed_at = at
        item.completed_by = actor
        item.version += 1
        item.save(
            update_fields=[
                "outcome_ciphertext",
                "status",
                "completed_at",
                "completed_by",
                "version",
                "updated_at",
            ]
        )
        _event(item, actor=actor, kind=FollowUpEventType.COMPLETED)
        _audit(context, "completed", item)
        return item


def cancel_followup(*, actor, followup_id, expected_version, reason, context, now=None):
    at = now or timezone.now()
    with transaction.atomic():
        actor = policy.current_actor(actor, manage=True, lock=True)
        item = _lock_for_mutation(
            actor=actor,
            followup_id=followup_id,
            expected_version=expected_version,
        )
        item.status = FollowUpStatus.CANCELLED
        item.cancelled_at = at
        item.cancelled_by = actor
        item.version += 1
        # Encrypt reason before changing the row, so missing key fails closed.
        event = GuidanceFollowUpEvent(
            followup=item,
            actor=actor,
            kind=FollowUpEventType.CANCELLED,
            revision=item.version,
        )
        event.remarks_ciphertext = encrypt_text(
            item.pk,
            "remarks",
            reason,
            event_id=event.pk,
            required=True,
        )
        item.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "version",
                "updated_at",
            ]
        )
        event.save(force_insert=True)
        _audit(context, "cancelled", item)
        return item


def followup_detail(*, actor, item, history_page=1):
    actor = policy.current_actor(actor)
    policy.require_followup(actor, item)
    if type(history_page) is not int or not 1 <= history_page <= MAX_PAGE:
        raise FollowUpInvalid("The history page is unavailable.")
    offset = (history_page - 1) * 20
    rows = list(item.events.select_related("actor").order_by("revision")[offset : offset + 21])
    events = []
    for event in rows[:20]:
        events.append(
            {
                "id": event.pk,
                "kind": event.kind,
                "revision": event.revision,
                "actor_id": event.actor_id,
                "actor_name": event.actor.get_full_name(),
                "created_at": event.created_at,
                "old_assignee_id": event.old_assignee_id,
                "new_assignee_id": event.new_assignee_id,
                "old_due_at": event.old_due_at,
                "new_due_at": event.new_due_at,
                "remarks": (
                    decrypt_text(item.pk, "remarks", event.remarks_ciphertext, event_id=event.pk)
                    if event.remarks_ciphertext
                    else None
                ),
            }
        )
    return {
        "description": (
            decrypt_text(item.pk, "description", item.description_ciphertext)
            if item.description_ciphertext
            else None
        ),
        "outcome": (
            decrypt_text(item.pk, "outcome", item.outcome_ciphertext)
            if item.outcome_ciphertext
            else None
        ),
        "source": policy.visible_source(actor, item),
        "events": events,
        "events_has_next": len(rows) > 20,
    }
