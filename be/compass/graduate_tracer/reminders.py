"""Civil-date Graduate Tracer reminders, separate from Appointment reminders."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from enum import StrEnum
from uuid import uuid4

from django.db import transaction
from django.db.models import DateField, Exists, F, Func, OuterRef, Q, Subquery
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.common.institutional_time import (
    institution_date,
    institution_day_start,
    institution_today,
)
from compass.common.ordering import parse_ordering
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.notifications.services import create_notification_for_event
from compass.student_academics.models import StudentGraduationRecord

from .models import (
    GraduateTracerReminderKind,
    GraduateTracerReminderOccurrence,
    GraduateTracerResponse,
    GraduateTracerStatus,
)

SCAN_BATCH = 500
FOLLOW_UP_DAYS = 30


class GraduateTracerReminderOrdering(StrEnum):
    EARLIEST_GRADUATION = "EARLIEST_GRADUATION"
    LATEST_GRADUATION = "LATEST_GRADUATION"


class GraduateTracerReminderState(StrEnum):
    UPCOMING = "UPCOMING"
    SENT = "SENT"
    ANSWERED = "ANSWERED"


def six_month_due_date(graduation_date: date) -> date:
    """Calendar-month anniversary; clamp an absent day to the month's last day."""
    month_index = graduation_date.year * 12 + graduation_date.month - 1 + 6
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(graduation_date.day, monthrange(year, month)[1]))


def _records():
    # PostgreSQL's month arithmetic clamps exactly like six_month_due_date.
    occurrences = GraduateTracerReminderOccurrence.objects.filter(
        graduation_record_id=OuterRef("pk")
    )
    submitted = GraduateTracerResponse.objects.filter(
        student_id=OuterRef("student_id"), status=GraduateTracerStatus.SUBMITTED
    )
    return StudentGraduationRecord.objects.annotate(
        six_month_due=Func(
            F("graduation_date"),
            template="(%(expressions)s + INTERVAL '6 months')::date",
            output_field=DateField(),
        ),
        answered=Exists(submitted),
        initial_issued_at=Subquery(
            occurrences.filter(kind=GraduateTracerReminderKind.SIX_MONTH).values("issued_at")[:1]
        ),
        follow_up_issued_at=Subquery(
            occurrences.filter(kind=GraduateTracerReminderKind.FOLLOW_UP).values("issued_at")[:1]
        ),
    )


def _active_graduates(queryset):
    return queryset.filter(
        student__is_active=True,
        student__role__code="STUDENT",
        student__student_lifecycle_status=StudentLifecycleStatus.GRADUATED,
    )


def _answered(student_id) -> bool:
    return GraduateTracerResponse.objects.filter(
        student_id=student_id, status=GraduateTracerStatus.SUBMITTED
    ).exists()


def _issue(record_id, *, at) -> bool:
    with transaction.atomic():
        student_id = (
            StudentGraduationRecord.objects.filter(pk=record_id)
            .values_list("student_id", flat=True)
            .first()
        )
        if student_id is None:
            return False
        # Submission and account lifecycle writers also lock the User first.
        student = (
            User.objects.select_for_update(of=("self",)).select_related("role").get(pk=student_id)
        )
        record = (
            StudentGraduationRecord.objects.select_for_update()
            .filter(pk=record_id, student=student)
            .first()
        )
        if (
            record is None
            or not student.is_active
            or student.role.code != "STUDENT"
            or student.student_lifecycle_status != StudentLifecycleStatus.GRADUATED
            or _answered(student.pk)
        ):
            return False
        today = institution_today(at)
        if six_month_due_date(record.graduation_date) > today:
            return False
        initial = record.tracer_reminder_occurrences.filter(
            kind=GraduateTracerReminderKind.SIX_MONTH
        ).first()
        kind = GraduateTracerReminderKind.SIX_MONTH
        if initial is not None:
            kind = GraduateTracerReminderKind.FOLLOW_UP
            if institution_date(initial.issued_at) + timedelta(days=FOLLOW_UP_DAYS) > today:
                return False
        if record.tracer_reminder_occurrences.filter(kind=kind).exists():
            return False
        occurrence_id = uuid4()
        notification = create_notification_for_event(
            recipient=student,
            event=NotificationEvent.GRADUATE_TRACER_REMINDER,
            source_type="graduate_tracer_reminder",
            source_id=occurrence_id,
            target_type=NotificationTargetType.GRADUATE_TRACER,
            target_id=student.pk,
        )
        GraduateTracerReminderOccurrence.objects.create(
            id=occurrence_id,
            graduation_record=record,
            kind=kind,
            issued_at=at,
            notification=notification,
        )
        return True


def dispatch_due_reminders(*, now=None) -> int:
    """Issue at most SCAN_BATCH notices; unprocessed due rows remain eligible tomorrow."""
    at = now or timezone.now()
    today = institution_today(at)
    # All of the candidate day's instants fall before the next civil midnight.
    follow_up_before = institution_day_start(today - timedelta(days=FOLLOW_UP_DAYS - 1))
    ids = list(
        _active_graduates(_records())
        .filter(answered=False, six_month_due__lte=today)
        .filter(
            Q(initial_issued_at__isnull=True)
            | Q(initial_issued_at__lt=follow_up_before, follow_up_issued_at__isnull=True)
        )
        .order_by("graduation_date", "id")
        .values_list("pk", flat=True)[:SCAN_BATCH]
    )
    return sum(_issue(record_id, at=at) for record_id in ids)


def reminder_notification_is_current(notification, *, now=None) -> bool:
    """Recheck participation before asynchronous transport without reading survey answers."""
    if (
        notification.event_code != NotificationEvent.GRADUATE_TRACER_REMINDER
        or notification.target_type != NotificationTargetType.GRADUATE_TRACER
        or notification.target_id != notification.recipient_id
    ):
        return False
    return (
        _active_graduates(_records())
        .filter(
            student_id=notification.recipient_id,
            answered=False,
            tracer_reminder_occurrences__pk=notification.source_id,
            tracer_reminder_occurrences__notification_id=notification.pk,
        )
        .exists()
    )


def list_reminders(*, page: int = 1, page_size: int = 20, ordering=None) -> dict:
    """Paginated graduation records with both planned dates and durable issuance state."""
    if page < 1 or not 1 <= page_size <= 50:
        raise ValueError("page must be positive and page_size must be between 1 and 50.")
    resolved = parse_ordering(
        ordering,
        GraduateTracerReminderOrdering,
        default=GraduateTracerReminderOrdering.EARLIEST_GRADUATION,
        error=ValueError,
    )
    fields = (
        ("graduation_date", "id")
        if resolved == GraduateTracerReminderOrdering.EARLIEST_GRADUATION
        else ("-graduation_date", "-id")
    )
    offset = (page - 1) * page_size
    records = list(
        _active_graduates(_records())
        .select_related("student")
        .order_by(*fields)[offset : offset + page_size + 1]
    )
    rows = []
    for record in records[:page_size]:
        initial_due = six_month_due_date(record.graduation_date)
        follow_up_due = (
            institution_date(record.initial_issued_at) if record.initial_issued_at else initial_due
        ) + timedelta(days=FOLLOW_UP_DAYS)
        reminders = []
        for kind, due, issued_at in (
            (GraduateTracerReminderKind.SIX_MONTH, initial_due, record.initial_issued_at),
            (GraduateTracerReminderKind.FOLLOW_UP, follow_up_due, record.follow_up_issued_at),
        ):
            reminders.append(
                {
                    "kind": kind,
                    "due_date": due,
                    "issued_at": issued_at,
                    "state": GraduateTracerReminderState.ANSWERED
                    if record.answered
                    else (
                        GraduateTracerReminderState.SENT
                        if issued_at
                        else GraduateTracerReminderState.UPCOMING
                    ),
                }
            )
        rows.append(
            {
                "graduation_record_id": record.pk,
                "graduate_name": record.student.get_full_name(),
                "graduation_date": record.graduation_date,
                "reminders": reminders,
            }
        )
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "has_next": len(records) > page_size,
        "ordering": resolved,
    }
