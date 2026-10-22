"""Appointment-owned eligibility and bounded operational email projections.

The NOTIF-01 content-free pilot remains available independently of rich approval.
No Student identity, private reason or confidential source record is projected.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.common.institutional_time import institution_timezone_name, to_institution_time
from compass.notifications.policy import NotificationEvent

from .models import (
    Appointment,
    AppointmentChangeEvent,
    AppointmentChangeEventType,
    AppointmentReminderKind,
    AppointmentReminderOccurrence,
    AppointmentStatus,
)
from .reminders import reminder_occurrence_is_current
from .services import AppointmentNotFound, get_appointment_for_actor


class AppointmentEmailRecipient(StrEnum):
    STUDENT = "student"
    CURRENT_COUNSELOR = "current_counselor"
    AUTHORIZED_STAFF = "authorized_staff"
    FORMER_COUNSELOR = "former_counselor"


class AppointmentEmailEligibility(StrEnum):
    ALLOWED = "allowed"
    SOURCE_MISSING = "source_missing"
    SOURCE_STALE = "source_stale"
    RECIPIENT_DENIED = "recipient_denied"
    INVALID_SOURCE = "invalid_source"
    SOURCE_SUPERSEDED = "source_superseded"
    PROVENANCE_UNAVAILABLE = "provenance_unavailable"
    RECIPIENT_MINIMAL = "recipient_minimal"


@dataclass(frozen=True, slots=True)
class ScheduledAppointmentEmailAccess:
    eligibility: AppointmentEmailEligibility
    recipient_class: AppointmentEmailRecipient | None = None


def scheduled_appointment_email_access(
    *, appointment_id: UUID, recipient_id: UUID, now=None
) -> ScheduledAppointmentEmailAccess:
    recipient = User.objects.select_related("role").filter(pk=recipient_id).first()
    if recipient is None or not recipient.is_active:
        return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.RECIPIENT_DENIED)
    # This content-free lookup distinguishes legacy/missing and stale sources.
    # Normal detail authorization below remains authoritative for any link.
    source = Appointment.objects.filter(pk=appointment_id).values("status", "starts_at").first()
    if source is None:
        return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.SOURCE_MISSING)
    if source["status"] != AppointmentStatus.SCHEDULED or source["starts_at"] <= (
        now or timezone.now()
    ):
        return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.SOURCE_STALE)
    try:
        item = get_appointment_for_actor(appointment_id=appointment_id, actor=recipient)
    except AppointmentNotFound:
        return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.RECIPIENT_DENIED)
    if item.status != AppointmentStatus.SCHEDULED or item.starts_at <= (now or timezone.now()):
        return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.SOURCE_STALE)
    if item.student_id == recipient.pk and recipient.role.code == "STUDENT":
        kind = AppointmentEmailRecipient.STUDENT
    elif item.provider_id == recipient.pk and recipient.role.code == "COUNSELOR":
        kind = AppointmentEmailRecipient.CURRENT_COUNSELOR
    elif recipient.role.code == "GUIDANCE_SERVICES_STAFF":
        kind = AppointmentEmailRecipient.AUTHORIZED_STAFF
    else:
        # A formerly assigned or unrelated Counselor gets no new link through
        # historical Notification ownership, even if another scope might exist.
        return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.RECIPIENT_DENIED)
    return ScheduledAppointmentEmailAccess(AppointmentEmailEligibility.ALLOWED, kind)


APPOINTMENT_EMAIL_EVENTS = frozenset(
    {
        NotificationEvent.APPOINTMENT_SCHEDULED,
        NotificationEvent.APPOINTMENT_CANCELLED,
        NotificationEvent.APPOINTMENT_RESCHEDULED,
        NotificationEvent.APPOINTMENT_REASSIGNED,
        NotificationEvent.APPOINTMENT_REMINDER_24H,
        NotificationEvent.APPOINTMENT_REMINDER_3H,
        NotificationEvent.APPOINTMENT_REMINDER_MANUAL,
    }
)
_CHANGE_TYPES = {
    NotificationEvent.APPOINTMENT_RESCHEDULED: AppointmentChangeEventType.RESCHEDULED,
    NotificationEvent.APPOINTMENT_REASSIGNED: AppointmentChangeEventType.REASSIGNED,
}
_REMINDER_KINDS = {
    NotificationEvent.APPOINTMENT_REMINDER_24H: AppointmentReminderKind.AUTO_24H,
    NotificationEvent.APPOINTMENT_REMINDER_3H: AppointmentReminderKind.AUTO_3H,
    NotificationEvent.APPOINTMENT_REMINDER_MANUAL: AppointmentReminderKind.MANUAL,
}


class AppointmentEmailField(StrEnum):
    REFERENCE = "Reference"
    SERVICE = "Service"
    DATE = "Date"
    TIME = "Time"
    PREVIOUS_DATE = "Previous date"
    PREVIOUS_TIME = "Previous time"
    UPDATED_DATE = "Updated date"
    UPDATED_TIME = "Updated time"
    COUNSELOR = "Assigned Counselor (current name)"
    UPDATED_COUNSELOR = "Updated Counselor (current name)"
    MODE = "Delivery mode"


_UNSAFE_DISPLAY = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://|\b(?:javascript|data|file|mailto):|www\.|@)", re.I
)


def _display_text(value: object) -> str | None:
    # Plain str only: SafeString/HTML objects must not bypass Django autoescape.
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > 600
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or _UNSAFE_DISPLAY.search(value)
    ):
        return None
    return value.strip()


@dataclass(frozen=True, slots=True)
class AppointmentEmailDetail:
    field: AppointmentEmailField
    value: str = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.field, AppointmentEmailField) or _display_text(self.value) is None:
            raise ValueError("invalid appointment email detail")

    @property
    def label(self) -> str:
        return self.field.value


@dataclass(frozen=True, slots=True, repr=False)
class AppointmentEmailFacts:
    event_code: str
    appointment_id: UUID
    source_id: UUID
    revision: int
    provider_id: UUID
    starts_at: datetime
    ends_at: datetime
    recipient_class: AppointmentEmailRecipient
    rows: tuple[AppointmentEmailDetail, ...]


@dataclass(frozen=True, slots=True)
class AppointmentEmailResolution:
    eligibility: AppointmentEmailEligibility
    recipient_class: AppointmentEmailRecipient | None = None
    link_allowed: bool = False
    facts: AppointmentEmailFacts | None = field(default=None, repr=False)


def _valid_interval(start, end) -> bool:
    return bool(
        isinstance(start, datetime)
        and isinstance(end, datetime)
        and timezone.is_aware(start)
        and timezone.is_aware(end)
        and start < end
    )


def appointment_email_schedule(start: datetime, end: datetime) -> tuple[str, str]:
    if not _valid_interval(start, end):
        raise ValueError("invalid appointment email interval")
    first, last = to_institution_time(start), to_institution_time(end)

    def day(value):
        return f"{value:%A, %B} {value.day}, {value:%Y}"

    def clock(value):
        return f"{value.hour % 12 or 12}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"

    zone = (
        "Philippine Time" if institution_timezone_name() == "Asia/Manila" else str(first.tzname())
    )
    dates = day(first) if first.date() == last.date() else f"{day(first)} – {day(last)}"
    return dates, f"{clock(first)}–{clock(last)} ({zone})"


def _superseded(event: AppointmentChangeEvent) -> bool:
    # No random-UUID chronology. Equal or conflicting clocks fail conservatively.
    return (
        AppointmentChangeEvent.objects.filter(appointment_id=event.appointment_id)
        .exclude(pk=event.pk)
        .filter(Q(occurred_at__gte=event.occurred_at) | Q(created_at__gte=event.created_at))
        .exists()
    )


def resolve_appointment_email_facts(
    *,
    event_code: str,
    source_type: str,
    source_id: UUID,
    appointment_id: UUID,
    recipient_id: UUID,
    now=None,
) -> AppointmentEmailResolution:
    """Only called after Notifications selects an approved disclosure policy."""
    at = now or timezone.now()
    recipient = User.objects.select_related("role").filter(pk=recipient_id).first()
    if recipient is None or not recipient.is_active:
        return AppointmentEmailResolution(AppointmentEmailEligibility.RECIPIENT_DENIED)
    source = None
    if event_code in _CHANGE_TYPES:
        if source_type != "appointment_change_event":
            return AppointmentEmailResolution(AppointmentEmailEligibility.INVALID_SOURCE)
        source = AppointmentChangeEvent.objects.defer("reason").filter(pk=source_id).first()
        if source is None:
            return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_MISSING)
        if (
            source.appointment_id != appointment_id
            or source.event_type != _CHANGE_TYPES[event_code]
        ):
            return AppointmentEmailResolution(AppointmentEmailEligibility.INVALID_SOURCE)
        if (
            event_code == NotificationEvent.APPOINTMENT_REASSIGNED
            and recipient_id == source.previous_provider_id
        ):
            return AppointmentEmailResolution(
                AppointmentEmailEligibility.RECIPIENT_MINIMAL,
                AppointmentEmailRecipient.FORMER_COUNSELOR,
            )
        if _superseded(source):
            return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_SUPERSEDED)
    elif event_code in _REMINDER_KINDS:
        if source_type != "appointment_reminder":
            return AppointmentEmailResolution(AppointmentEmailEligibility.INVALID_SOURCE)
        source = (
            AppointmentReminderOccurrence.objects.select_related("appointment", "recipient__role")
            .filter(pk=source_id)
            .first()
        )
        if source is None:
            return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_MISSING)
        if (
            source.appointment_id != appointment_id
            or source.recipient_id != recipient_id
            or source.kind != _REMINDER_KINDS[event_code]
        ):
            return AppointmentEmailResolution(AppointmentEmailEligibility.INVALID_SOURCE)
        if not reminder_occurrence_is_current(source, recipient_id=recipient_id, now=at):
            return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_STALE)
    elif event_code not in {
        NotificationEvent.APPOINTMENT_SCHEDULED,
        NotificationEvent.APPOINTMENT_CANCELLED,
    }:
        return AppointmentEmailResolution(AppointmentEmailEligibility.INVALID_SOURCE)
    elif source_type != "appointment" or source_id != appointment_id:
        return AppointmentEmailResolution(AppointmentEmailEligibility.INVALID_SOURCE)

    state = Appointment.objects.filter(pk=appointment_id).values("status", "starts_at").first()
    if state is None:
        return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_MISSING)
    # Source state is checked even if the old recipient no longer has record access.
    cancelled = event_code == NotificationEvent.APPOINTMENT_CANCELLED
    if (cancelled and state["status"] != AppointmentStatus.CANCELLED) or (
        not cancelled
        and (state["status"] != AppointmentStatus.SCHEDULED or state["starts_at"] <= at)
    ):
        return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_STALE)
    try:
        item = get_appointment_for_actor(appointment_id=appointment_id, actor=recipient)
    except AppointmentNotFound:
        return AppointmentEmailResolution(AppointmentEmailEligibility.RECIPIENT_DENIED)
    if (cancelled and item.status != AppointmentStatus.CANCELLED) or (
        not cancelled and (item.status != AppointmentStatus.SCHEDULED or item.starts_at <= at)
    ):
        return AppointmentEmailResolution(AppointmentEmailEligibility.SOURCE_STALE)
    if item.student_id == recipient_id and recipient.role.code == "STUDENT":
        kind = AppointmentEmailRecipient.STUDENT
    elif item.provider_id == recipient_id and recipient.role.code == "COUNSELOR":
        kind = AppointmentEmailRecipient.CURRENT_COUNSELOR
    else:
        # No GSS/other rich delivery. Preserve only the existing Scheduled link pilot.
        return AppointmentEmailResolution(AppointmentEmailEligibility.RECIPIENT_MINIMAL)
    if not _valid_interval(item.starts_at, item.ends_at) or not _display_text(item.reference_code):
        return AppointmentEmailResolution(AppointmentEmailEligibility.PROVENANCE_UNAVAILABLE, kind)
    if cancelled and item.cancelled_at is None:
        return AppointmentEmailResolution(AppointmentEmailEligibility.PROVENANCE_UNAVAILABLE, kind)
    if event_code == NotificationEvent.APPOINTMENT_SCHEDULED and (
        item.reminder_revision != 1
        or item.reminder_revision_started_at is not None
        or item.change_events.exists()
    ):
        return AppointmentEmailResolution(
            AppointmentEmailEligibility.PROVENANCE_UNAVAILABLE, kind, link_allowed=True
        )
    if event_code == NotificationEvent.APPOINTMENT_RESCHEDULED:
        if (
            not _valid_interval(source.previous_starts_at, source.previous_ends_at)
            or not _valid_interval(source.new_starts_at, source.new_ends_at)
            or (source.new_starts_at, source.new_ends_at) != (item.starts_at, item.ends_at)
        ):
            return AppointmentEmailResolution(
                AppointmentEmailEligibility.PROVENANCE_UNAVAILABLE, kind
            )
    if event_code == NotificationEvent.APPOINTMENT_REASSIGNED and (
        source.new_provider_id != item.provider_id
        or source.previous_provider_id == source.new_provider_id
    ):
        return AppointmentEmailResolution(AppointmentEmailEligibility.PROVENANCE_UNAVAILABLE, kind)

    rows = [AppointmentEmailDetail(AppointmentEmailField.REFERENCE, item.reference_code)]
    service = _display_text(item.service_name_snapshot)
    if service:
        rows.append(AppointmentEmailDetail(AppointmentEmailField.SERVICE, service))
    if event_code == NotificationEvent.APPOINTMENT_RESCHEDULED:
        old_date, old_time = appointment_email_schedule(
            source.previous_starts_at, source.previous_ends_at
        )
        new_date, new_time = appointment_email_schedule(source.new_starts_at, source.new_ends_at)
        rows.extend(
            AppointmentEmailDetail(key, value)
            for key, value in (
                (AppointmentEmailField.PREVIOUS_DATE, old_date),
                (AppointmentEmailField.PREVIOUS_TIME, old_time),
                (AppointmentEmailField.UPDATED_DATE, new_date),
                (AppointmentEmailField.UPDATED_TIME, new_time),
            )
        )
    else:
        date, times = appointment_email_schedule(item.starts_at, item.ends_at)
        rows.extend(
            (
                AppointmentEmailDetail(AppointmentEmailField.DATE, date),
                AppointmentEmailDetail(AppointmentEmailField.TIME, times),
            )
        )
    name = _display_text(item.provider.get_full_name())
    if name and not cancelled:
        label = (
            AppointmentEmailField.UPDATED_COUNSELOR
            if event_code == NotificationEvent.APPOINTMENT_REASSIGNED
            else AppointmentEmailField.COUNSELOR
        )
        rows.append(AppointmentEmailDetail(label, name))
    mode = {"IN_PERSON": "In person", "ONLINE": "Online"}.get(item.delivery_mode)
    if mode:
        rows.append(AppointmentEmailDetail(AppointmentEmailField.MODE, mode))
    facts = AppointmentEmailFacts(
        event_code,
        item.pk,
        source_id,
        item.reminder_revision,
        item.provider_id,
        item.starts_at,
        item.ends_at,
        kind,
        tuple(rows),
    )
    return AppointmentEmailResolution(AppointmentEmailEligibility.ALLOWED, kind, True, facts)
