"""Student-only Appointment reminders. Issuance is atomic; transport remains asynchronous.

A revision is incremented by schedule/assignment edits. An occurrence has its own
UUID as Notification source identity, but the Appointment remains the destination.
Serializing on the Appointment row makes concurrent API and Beat issuers idempotent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import APPOINTMENT_REMINDER_ISSUED, APPOINTMENT_REMINDERS_BULK
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_zone
from compass.common.ordering import parse_ordering
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event

from .access import appointment_management_access_allowed, scope_managed_appointments
from .models import (
    Appointment,
    AppointmentReminderBatch,
    AppointmentReminderKind,
    AppointmentReminderOccurrence,
    AppointmentStatus,
)
from .services import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, AppointmentListOrdering

AUTO_WINDOWS = (
    (AppointmentReminderKind.AUTO_24H, timedelta(hours=24)),
    (AppointmentReminderKind.AUTO_3H, timedelta(hours=3)),
)
LATE_WINDOW = timedelta(minutes=15)
MANUAL_LEAD = timedelta(minutes=15)
MANUAL_COOLDOWN = timedelta(hours=3)
MAX_BULK = 25
SCAN_BATCH = 500


@dataclass(frozen=True, slots=True)
class ReminderDecision:
    appointment_id: UUID
    reference_code: str
    student_name: str
    eligible: bool
    reason: str
    issued_at: object | None = None

    def as_dict(self) -> dict:
        return {
            "appointment_id": str(self.appointment_id),
            "reference_code": self.reference_code,
            "student_name": self.student_name,
            "eligible": self.eligible,
            "reason": self.reason,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
        }


def _revision_since(item: Appointment):
    return item.reminder_revision_started_at or item.created_at


def _base_reason(item: Appointment, at) -> str:
    if item.status != AppointmentStatus.SCHEDULED:
        return "NOT_SCHEDULED"
    if item.starts_at - at < MANUAL_LEAD:
        return "TOO_SOON"
    if not item.student.is_active or item.student.role.code != "STUDENT":
        return "RECIPIENT_INACTIVE"
    return ""


def _cooldown(item: Appointment, at) -> bool:
    """Manual-to-manual anti-spam only (CORR-2A).

    Automatic 24-hour/3-hour occurrences are independently idempotent by
    (appointment, revision, window) and neither count toward nor are suppressed
    by this cooldown. The cooldown spans schedule revisions on purpose: a
    reschedule must not become a way to repeat manual outreach immediately.
    """
    return AppointmentReminderOccurrence.objects.filter(
        appointment=item,
        kind=AppointmentReminderKind.MANUAL,
        issued_at__gt=at - MANUAL_COOLDOWN,
        issued_at__lte=at,
    ).exists()


def _decision(item: Appointment, at, *, cooling: bool | None = None) -> ReminderDecision:
    """The one manual-send rule. ``cooling`` lets list read paths reuse a batched lookup."""

    reason = _base_reason(item, at)
    if not reason and (_cooldown(item, at) if cooling is None else cooling):
        reason = "COOLDOWN"
    return ReminderDecision(
        item.pk,
        item.reference_code,
        item.student.get_full_name(),
        not bool(reason),
        reason or "ELIGIBLE",
    )


def _visible_item(actor: User, appointment_id: UUID):
    item = (
        Appointment.objects.select_related("student__role", "provider__role", "service")
        .filter(pk=appointment_id)
        .first()
    )
    if item is None or not appointment_management_access_allowed(actor, item):
        return None
    return item


def _manager(actor: User) -> bool:
    return bool(
        actor
        and actor.is_active
        and actor.role.code in {"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"}
        and actor.has_capability("appointments.manage")
    )


def preview_reminders(*, actor: User, appointment_ids: list[UUID], now=None) -> list[dict]:
    if not _manager(actor):
        raise PermissionError("Appointment management access is required.")
    if not 1 <= len(appointment_ids) <= MAX_BULK or len(set(appointment_ids)) != len(
        appointment_ids
    ):
        raise ValueError("Choose between 1 and 25 different appointments.")
    at = now or timezone.now()
    results = []
    for appointment_id in appointment_ids:
        item = _visible_item(actor, appointment_id)
        if item is None:
            # Do not disclose even the student's name for inaccessible records.
            results.append(
                {
                    "appointment_id": str(appointment_id),
                    "reference_code": None,
                    "student_name": None,
                    "eligible": False,
                    "reason": "NOT_AVAILABLE",
                    "issued_at": None,
                }
            )
        else:
            results.append(_decision(item, at).as_dict())
    return results


HISTORY_LIMIT = 50
_IN_FLIGHT = {"PENDING", "PROCESSING"}


def _delivery_state(statuses) -> str:
    """Honest roll-up of existing transport rows; never implies recipient receipt.

    ``SENT`` only means the transport accepted the hand-off. A row that is still
    queued or claimed is ``PENDING``; no row at all is ``NOT_REQUESTED``.
    """
    values = set(statuses)
    if not values:
        return "NOT_REQUESTED"
    if values & _IN_FLIGHT:
        return "PENDING"
    if "SENT" in values:
        return "SENT"
    if "FAILED" in values:
        return "FAILED"
    return "CANCELLED"


def _history_rows(occurrences, *, now=None) -> list[dict]:
    """Shared occurrence projection for one Appointment and the managed activity list.

    Reuses occurrence, Notification, EmailDelivery and PushDelivery rows; no notification
    subsystem is added. Transport diagnostics (failure codes, endpoints, claim state),
    read receipts and any other Student's notifications are never selected.
    """
    from compass.notifications.models import EmailDelivery, Notification, PushDelivery

    ids = [row.pk for row in occurrences]
    notifications = {
        (row.source_id, row.recipient_id): row.pk
        for row in Notification.objects.filter(
            source_type="appointment_reminder", source_id__in=ids
        ).only("id", "source_id", "recipient_id")
    }
    notification_ids = list(notifications.values())
    email: dict = {}
    for notification_id, status in EmailDelivery.objects.filter(
        notification_id__in=notification_ids
    ).values_list("notification_id", "status"):
        email.setdefault(notification_id, []).append(status)
    push: dict = {}
    for notification_id, status in PushDelivery.objects.filter(
        notification_id__in=notification_ids
    ).values_list("notification_id", "status"):
        push.setdefault(notification_id, []).append(status)
    current = set(
        current_reminder_occurrences(now=now).filter(pk__in=ids).values_list("pk", flat=True)
    )
    rows = []
    for occurrence in occurrences:
        notification_id = notifications.get((occurrence.pk, occurrence.recipient_id))
        appointment = occurrence.appointment
        rows.append(
            {
                "id": occurrence.pk,
                "appointment_id": appointment.pk,
                "reference_code": appointment.reference_code,
                "student_name": appointment.student.get_full_name(),
                "kind": occurrence.kind,
                "issued_at": occurrence.issued_at,
                "scheduled_start": occurrence.starts_at,
                "issued_by": occurrence.issued_by,
                "is_current": occurrence.pk in current,
                "in_app": "CREATED" if notification_id else "NOT_CREATED",
                "email": _delivery_state(email.get(notification_id, [])),
                "push": _delivery_state(push.get(notification_id, [])),
            }
        )
    return rows


def reminder_history(*, actor: User, appointment_id: UUID, now=None) -> list[dict] | None:
    """Read-only staff history for one authorized Appointment, or ``None`` if unavailable."""

    if not _manager(actor):
        raise PermissionError("Appointment management access is required.")
    item = _visible_item(actor, appointment_id)
    if item is None:
        return None
    occurrences = list(
        AppointmentReminderOccurrence.objects.filter(appointment=item)
        .select_related("issued_by", "appointment__student")
        .order_by("-issued_at", "-pk")[:HISTORY_LIMIT]
    )
    return _history_rows(occurrences, now=now)


DEFAULT_UPCOMING_DAYS = 7
MAX_UPCOMING_DAYS = 30
DELIVERY_STATES = ("NOT_REQUESTED", "PENDING", "SENT", "FAILED", "CANCELLED")


def _page_parameters(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise ValueError("page must be a positive integer.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _institution_date_start(value: date | None) -> datetime | None:
    return (
        datetime.combine(value, time.min, tzinfo=institution_zone()) if value is not None else None
    )


def _institution_date_end(value: date | None) -> datetime | None:
    """Exclusive upper bound: the start of the day after ``value``."""

    return (
        datetime.combine(value + timedelta(days=1), time.min, tzinfo=institution_zone())
        if value is not None
        else None
    )


def _upcoming_bounds(*, from_date, to_date, at) -> tuple[datetime, datetime]:
    zone = institution_zone()
    start_date = from_date or at.astimezone(zone).date()
    end_date = to_date or start_date + timedelta(days=DEFAULT_UPCOMING_DAYS - 1)
    if start_date > end_date:
        raise ValueError("from_date must not be after to_date.")
    if (end_date - start_date).days + 1 > MAX_UPCOMING_DAYS:
        raise ValueError(f"The date window cannot be longer than {MAX_UPCOMING_DAYS} days.")
    lower = datetime.combine(start_date, time.min, tzinfo=zone)
    upper = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
    return max(lower, at), upper


def _cooling_appointment_ids(items, at) -> set:
    ids = [item.pk for item in items]
    if not ids:
        return set()
    return set(
        AppointmentReminderOccurrence.objects.filter(
            appointment_id__in=ids,
            kind=AppointmentReminderKind.MANUAL,
            issued_at__gt=at - MANUAL_COOLDOWN,
            issued_at__lte=at,
        ).values_list("appointment_id", flat=True)
    )


def _next_automatic(item: Appointment, at, *, issued_kinds: set[str]) -> str | None:
    """The next automatic occurrence the dispatcher will still issue, if any.

    Mirrors the dispatcher's per-Appointment conditions: the window must not have
    passed, the current revision must predate it, and automatic sending must be enabled.
    """
    if not settings.APPOINTMENT_AUTO_REMINDERS_ENABLED:
        return None
    if not item.student.is_active or item.student.role.code != "STUDENT":
        return None
    revision_since = _revision_since(item)
    for kind, lead in AUTO_WINDOWS:
        if kind in issued_kinds:
            continue
        due = item.starts_at - lead
        if at >= due + LATE_WINDOW or revision_since > due:
            continue
        return kind
    return None


def _upcoming_ordering_fields(ordering: AppointmentListOrdering) -> tuple[str, str, str]:
    if ordering == AppointmentListOrdering.LATEST_START:
        return "-starts_at", "-reference_code", "-id"
    return "starts_at", "reference_code", "id"


def list_upcoming_reminders(
    *,
    actor: User,
    from_date: date | None = None,
    to_date: date | None = None,
    provider_id: UUID | None = None,
    manual_available: bool | None = None,
    ordering: str | AppointmentListOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now=None,
) -> dict:
    """Scheduled Appointments in the actor's managed scope, with reminder readiness.

    The date window bounds the scan (at most 30 days). Decisions reuse ``_decision``;
    only the manual cooldown is batched so a page does not issue one query per row.
    """
    if not _manager(actor):
        raise PermissionError("Appointment management access is required.")
    page, page_size = _page_parameters(page, page_size)
    at = now or timezone.now()
    lower, upper = _upcoming_bounds(from_date=from_date, to_date=to_date, at=at)
    resolved_ordering = parse_ordering(
        ordering,
        AppointmentListOrdering,
        default=AppointmentListOrdering.EARLIEST_START,
        error=ValueError,
    )
    queryset = scope_managed_appointments(
        Appointment.objects.select_related("student", "student__role", "provider", "service"),
        actor,
    ).filter(
        status=AppointmentStatus.SCHEDULED,
        starts_at__gte=lower,
        starts_at__lt=upper,
    )
    if provider_id is not None:
        queryset = queryset.filter(provider_id=provider_id)
    items = list(queryset.order_by(*_upcoming_ordering_fields(resolved_ordering)))
    cooling = _cooling_appointment_ids(items, at)
    decisions = {item.pk: _decision(item, at, cooling=item.pk in cooling) for item in items}
    if manual_available is not None:
        items = [item for item in items if decisions[item.pk].eligible == manual_available]

    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size + 1]
    has_next = len(page_items) > page_size
    rows = _upcoming_rows(page_items[:page_size], decisions=decisions, at=at)
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "ordering": resolved_ordering,
    }


def _upcoming_rows(items, *, decisions: dict, at) -> list[dict]:
    ids = [item.pk for item in items]
    issued_auto: dict = {}
    if ids:
        for appointment_id, kind, revision in AppointmentReminderOccurrence.objects.filter(
            appointment_id__in=ids,
            kind__in=[AppointmentReminderKind.AUTO_24H, AppointmentReminderKind.AUTO_3H],
        ).values_list("appointment_id", "kind", "revision"):
            issued_auto.setdefault(appointment_id, set()).add((kind, revision))
    last_sent: dict = {}
    if ids:
        for appointment_id, kind, issued_at in (
            AppointmentReminderOccurrence.objects.filter(appointment_id__in=ids)
            .order_by("appointment_id", "-issued_at", "-pk")
            .values_list("appointment_id", "kind", "issued_at")
        ):
            last_sent.setdefault(appointment_id, (kind, issued_at))
    rows = []
    for item in items:
        issued = issued_auto.get(item.pk, set())
        decision = decisions[item.pk]
        last_kind, last_at = last_sent.get(item.pk, (None, None))
        rows.append(
            {
                "appointment_id": item.pk,
                "reference_code": item.reference_code,
                "student_name": item.student.get_full_name(),
                "counselor_id": item.provider_id,
                "counselor_name": item.provider.get_full_name(),
                "service_name": item.service_name_snapshot,
                "starts_at": item.starts_at,
                "next_automatic": _next_automatic(
                    item,
                    at,
                    issued_kinds={
                        kind for kind, revision in issued if revision == item.reminder_revision
                    },
                ),
                "last_reminder_kind": last_kind,
                "last_reminder_at": last_at,
                "manual_available": decision.eligible,
                "manual_reason": decision.reason,
            }
        )
    return rows


def _filter_delivery_state(queryset, state: str):
    """External delivery roll-up: an occurrence matches when either transport does.

    ``NOT_REQUESTED`` means no email or push delivery was requested for the occurrence.
    """
    from compass.notifications.models import Notification

    def notification(**lookup):
        return Notification.objects.filter(
            source_type="appointment_reminder",
            source_id=OuterRef("pk"),
            recipient_id=OuterRef("recipient_id"),
            **lookup,
        )

    email = "email_delivery__status__in"
    push = "pushdelivery__status__in"
    if state == "NOT_REQUESTED":
        return queryset.filter(
            ~Exists(notification(email_delivery__isnull=False))
            & ~Exists(notification(pushdelivery__isnull=False))
        )
    if state == "PENDING":
        return queryset.filter(
            Exists(notification(**{email: _IN_FLIGHT})) | Exists(notification(**{push: _IN_FLIGHT}))
        )
    return queryset.filter(
        Exists(notification(**{email: [state]})) | Exists(notification(**{push: [state]}))
    )


def list_reminder_activity(
    *,
    actor: User,
    kind: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    delivery: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now=None,
) -> dict:
    """Recent reminder occurrences across the actor's managed Appointments, newest first."""
    if not _manager(actor):
        raise PermissionError("Appointment management access is required.")
    page, page_size = _page_parameters(page, page_size)
    if kind is not None and kind not in AppointmentReminderKind.values:
        raise ValueError("kind must be one of " + ", ".join(AppointmentReminderKind.values) + ".")
    if delivery is not None and delivery not in DELIVERY_STATES:
        raise ValueError("delivery must be one of " + ", ".join(DELIVERY_STATES) + ".")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ValueError("from_date must not be after to_date.")

    visible = scope_managed_appointments(Appointment.objects.all(), actor)
    queryset = AppointmentReminderOccurrence.objects.filter(appointment__in=visible).select_related(
        "issued_by", "appointment__student"
    )
    if kind is not None:
        queryset = queryset.filter(kind=kind)
    lower = _institution_date_start(from_date)
    if lower is not None:
        queryset = queryset.filter(issued_at__gte=lower)
    upper = _institution_date_end(to_date)
    if upper is not None:
        queryset = queryset.filter(issued_at__lt=upper)
    if delivery is not None:
        queryset = _filter_delivery_state(queryset, delivery)
    queryset = queryset.order_by("-issued_at", "-pk")

    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return {
        "items": _history_rows(rows[:page_size], now=now),
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }


def _issue_locked(
    item: Appointment, *, kind: str, at, context: AuditContext | None
) -> AppointmentReminderOccurrence:
    # Called only with the Appointment row locked, after all eligibility checks.
    occurrence = AppointmentReminderOccurrence.objects.create(
        appointment=item,
        recipient=item.student,
        kind=kind,
        revision=item.reminder_revision,
        starts_at=item.starts_at,
        issued_at=at,
        issued_by=(context.actor if context and context.actor_type == "USER" else None),
    )
    event = (
        NotificationEvent.APPOINTMENT_REMINDER_24H
        if kind == AppointmentReminderKind.AUTO_24H
        else NotificationEvent.APPOINTMENT_REMINDER_3H
        if kind == AppointmentReminderKind.AUTO_3H
        else NotificationEvent.APPOINTMENT_REMINDER_MANUAL
    )
    create_notification_for_event(
        recipient=item.student,
        event=event,
        source_type="appointment_reminder",
        source_id=occurrence.pk,
        target_type="APPOINTMENT",
        target_id=item.pk,
    )
    record_event(
        context=context or AuditContext.system(),
        action=APPOINTMENT_REMINDER_ISSUED,
        outcome=AuditOutcome.SUCCESS,
        target_type="appointments.appointment",
        target_id=item.pk,
        metadata={
            "occurrence_id": str(occurrence.pk),
            "kind": kind,
            "revision": item.reminder_revision,
        },
    )
    return occurrence


def issue_manual_reminder(
    *, actor: User, appointment_id: UUID, request_key: UUID, context: AuditContext, now=None
) -> dict:
    return issue_bulk_reminders(
        actor=actor,
        appointment_ids=[appointment_id],
        request_key=request_key,
        context=context,
        now=now,
    )["items"][0]


def _replay_result(actor, result):
    # Never persist names or return earlier access after a scope/role change.
    rows = []
    for row in result["items"]:
        item = _visible_item(actor, row["appointment_id"])
        if item is None:
            rows.append(
                {
                    "appointment_id": row["appointment_id"],
                    "reference_code": None,
                    "student_name": None,
                    "eligible": False,
                    "accepted": False,
                    "reason": "NOT_AVAILABLE",
                    "issued_at": None,
                }
            )
        else:
            rows.append(
                {
                    **row,
                    "reference_code": item.reference_code,
                    "student_name": item.student.get_full_name(),
                }
            )
    return {
        "items": rows,
        "accepted": sum(bool(x["accepted"]) for x in rows),
        "skipped": sum(not x["accepted"] for x in rows),
    }


def issue_bulk_reminders(
    *, actor: User, appointment_ids: list[UUID], request_key: UUID, context: AuditContext, now=None
) -> dict:
    if not _manager(actor):
        raise PermissionError("Appointment management access is required.")
    if not 1 <= len(appointment_ids) <= MAX_BULK or len(set(appointment_ids)) != len(
        appointment_ids
    ):
        raise ValueError("Choose between 1 and 25 different appointments.")
    # The token is a durable logical submission identity. It cannot be reused
    # with a different selection, even after the 3-hour manual cooldown.
    fingerprint = hashlib.sha256(
        json.dumps(sorted(str(x) for x in appointment_ids)).encode()
    ).hexdigest()
    at = now or timezone.now()
    with transaction.atomic():
        # Serialize same-actor batches before checking the durable replay token.
        actor = User.objects.select_for_update(of=("self",)).select_related("role").get(pk=actor.pk)
        if not _manager(actor):
            raise PermissionError("Appointment management access is required.")
        previous = AppointmentReminderBatch.objects.filter(
            actor=actor, request_key=request_key
        ).first()
        if previous:
            if previous.selection_digest != fingerprint:
                raise ValueError("This confirmation was already used for another selection.")
            return _replay_result(actor, previous.result)
        results_by_id = {}
        # Deterministic lock order also prevents overlapping concurrent bulk deadlocks.
        for appointment_id in sorted(appointment_ids, key=str):
            item = (
                Appointment.objects.select_for_update(of=("self",))
                .select_related("student__role", "provider__role", "service")
                .filter(pk=appointment_id)
                .first()
            )
            if item is None or not appointment_management_access_allowed(actor, item):
                results_by_id[str(appointment_id)] = {
                    "appointment_id": str(appointment_id),
                    "reference_code": None,
                    "student_name": None,
                    "eligible": False,
                    "reason": "NOT_AVAILABLE",
                    "accepted": False,
                    "issued_at": None,
                }
                continue
            decision = _decision(item, at)
            if decision.eligible:
                occurrence = _issue_locked(
                    item, kind=AppointmentReminderKind.MANUAL, at=at, context=context
                )
                results_by_id[str(appointment_id)] = {
                    **decision.as_dict(),
                    "accepted": True,
                    "reason": "QUEUED",
                    "issued_at": occurrence.issued_at.isoformat(),
                }
            else:
                results_by_id[str(appointment_id)] = {**decision.as_dict(), "accepted": False}
        results = [results_by_id[str(x)] for x in appointment_ids]
        response = {
            "items": results,
            "accepted": sum(int(x["accepted"]) for x in results),
            "skipped": sum(int(not x["accepted"]) for x in results),
        }
        AppointmentReminderBatch.objects.create(
            actor=actor,
            request_key=request_key,
            selection_digest=fingerprint,
            result={
                **response,
                "items": [
                    {k: v for k, v in row.items() if k not in {"student_name", "reference_code"}}
                    for row in results
                ],
            },
        )
        record_event(
            context=context,
            action=APPOINTMENT_REMINDERS_BULK,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.reminderbatch",
            target_id=str(request_key),
            metadata={
                "accepted": response["accepted"],
                "skipped": response["skipped"],
                "request_key": str(request_key),
            },
        )
        return response


def dispatch_due_reminders(*, now=None) -> int:
    """Beat discovery: bounded windows, no backfill, and no sends unless enabled."""
    if not settings.APPOINTMENT_AUTO_REMINDERS_ENABLED:
        return 0
    at = now or timezone.now()
    # Restrict the scan to candidate starts; no perpetual all-appointment sweep.
    count = 0
    for kind, lead in AUTO_WINDOWS:
        earliest = at + lead - LATE_WINDOW
        latest = at + lead
        candidates = list(
            Appointment.objects.alias(
                revision_started=Coalesce("reminder_revision_started_at", "created_at"),
                already_issued=Exists(
                    AppointmentReminderOccurrence.objects.filter(
                        appointment_id=OuterRef("pk"),
                        revision=OuterRef("reminder_revision"),
                        kind=kind,
                    )
                ),
            )
            .filter(
                revision_started__lte=F("starts_at") - lead,
                already_issued=False,
                student__is_active=True,
                student__role__code="STUDENT",
                status=AppointmentStatus.SCHEDULED,
                starts_at__gte=earliest,
                starts_at__lte=latest,
            )
            .order_by("starts_at", "pk")
            .values_list("pk", flat=True)[:SCAN_BATCH]
        )
        for appointment_id in candidates:
            with transaction.atomic():
                item = (
                    Appointment.objects.select_for_update(of=("self",))
                    .select_related("student__role")
                    .filter(pk=appointment_id)
                    .first()
                )
                if item is None or item.status != AppointmentStatus.SCHEDULED:
                    continue
                due = item.starts_at - lead
                # Booking/rescheduling after the target reminder time forfeits that window.
                if not due <= at < due + LATE_WINDOW or not _revision_since(item) <= due:
                    continue
                if not item.student.is_active or item.student.role.code != "STUDENT":
                    continue
                # Idempotent per (appointment, revision, window); never a manual cooldown.
                if AppointmentReminderOccurrence.objects.filter(
                    appointment=item,
                    revision=item.reminder_revision,
                    kind=kind,
                ).exists():
                    continue
                _issue_locked(item, kind=kind, at=at, context=None)
                count += 1
    return count


def reminder_notification_is_current(notification, *, now=None) -> bool:
    """Evaluate a pending external transport against the canonical appointment."""
    if notification.source_type != "appointment_reminder":
        return True
    at = now or timezone.now()
    occurrence = (
        AppointmentReminderOccurrence.objects.select_related(
            "appointment", "recipient__role", "appointment__student"
        )
        .filter(pk=notification.source_id)
        .first()
    )
    if occurrence is None:
        return False
    return reminder_occurrence_is_current(
        occurrence, recipient_id=notification.recipient_id, now=at
    )


def reminder_occurrence_is_current(occurrence, *, recipient_id, now=None) -> bool:
    """Canonical content-free occurrence predicate shared with email projections."""
    at = now or timezone.now()
    item = occurrence.appointment
    return bool(
        item.status == AppointmentStatus.SCHEDULED
        and item.starts_at > at
        and item.starts_at == occurrence.starts_at
        and item.reminder_revision == occurrence.revision
        and item.student_id == occurrence.recipient_id == recipient_id
        and occurrence.recipient.is_active
        and occurrence.recipient.role.code == "STUDENT"
    )


def current_reminder_occurrences(*, now=None):
    return AppointmentReminderOccurrence.objects.filter(
        appointment__status=AppointmentStatus.SCHEDULED,
        appointment__starts_at__gt=now or timezone.now(),
        appointment__starts_at=F("starts_at"),
        appointment__reminder_revision=F("revision"),
        appointment__student_id=F("recipient_id"),
        recipient__is_active=True,
        recipient__role__code="STUDENT",
    )


def scope_current_reminder_notifications(queryset):
    return queryset.alias(
        current_reminder=Exists(
            current_reminder_occurrences().filter(
                pk=OuterRef("source_id"),
                recipient_id=OuterRef("recipient_id"),
            )
        )
    ).filter(~Q(source_type="appointment_reminder") | Q(current_reminder=True))
