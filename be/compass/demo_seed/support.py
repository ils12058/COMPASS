"""Shared seed-run state and the few narrow, documented seed-only writes.

Everything the seeder creates goes through domain services. The only direct model writes are:

* ``align_timestamps`` — services stamp wall-clock time; back-entered records get their business
  timestamps (created, submitted, published, ...) moved onto the demo timeline. Only allowlisted
  timestamp columns can change; relationships, status, and content never do. Audit events are
  never rewritten and keep the real seed-run time.
* ``settle_notifications`` — services create in-app Notifications plus an EmailDelivery intent.
  Seeding keeps the in-app Notification (timestamped with its event) and removes the not-yet-
  committed, never-attempted EmailDelivery rows it caused, so a bulk seed never emails anyone.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from django.db import models
from django.utils import timezone

from compass.accounts.models import User
from compass.announcements.models import Announcement
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.call_slips.models import CallSlip
from compass.counseling.models import CounselingEncounter, CounselingSharedSummary
from compass.exit_interviews.models import ExitInterview, ExitInterviewOpportunity
from compass.feedback.models import ClientSatisfactionResponse, CustomerFeedbackResponse
from compass.good_moral.models import GoodMoralRequest
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
from compass.privacy_governance.models import (
    PrivacyNotice,
    PrivacyNoticeRevision,
)
from compass.referrals.models import Referral, ReferralAction
from compass.resources.models import Resource
from compass.routine_interviews.models import RoutineInterview

from .timeline import DemoTimeline

IDEMPOTENCY_KEY_PREFIX = "demo-seed-v1"

# The complete set of columns seeding may move onto the demo timeline.
ALIGNABLE_TIMESTAMPS: dict[type[models.Model], frozenset[str]] = {
    StudentInventory: frozenset(
        {"created_at", "updated_at", "submitted_at", "first_submitted_at", "last_submitted_at"}
    ),
    ExitInterview: frozenset({"created_at", "updated_at"}),
    ExitInterviewOpportunity: frozenset({"created_at", "updated_at", "opened_at"}),
    Appointment: frozenset({"created_at", "updated_at"}),
    CounselingEncounter: frozenset({"created_at", "updated_at"}),
    CounselingSharedSummary: frozenset({"created_at", "updated_at", "published_at"}),
    RoutineInterview: frozenset(
        {"created_at", "updated_at", "intake_submitted_at", "evaluation_finalized_at"}
    ),
    Referral: frozenset({"created_at", "updated_at"}),
    ReferralAction: frozenset({"created_at"}),
    CallSlip: frozenset({"created_at", "updated_at"}),
    GoodMoralRequest: frozenset({"created_at", "updated_at"}),
    GraduateTracerResponse: frozenset({"created_at", "updated_at"}),
    CustomerFeedbackResponse: frozenset({"submitted_at"}),
    ClientSatisfactionResponse: frozenset({"submitted_at"}),
    Announcement: frozenset({"created_at", "updated_at"}),
    Resource: frozenset({"created_at", "updated_at", "published_at"}),
    PrivacyNotice: frozenset({"created_at", "updated_at"}),
    PrivacyNoticeRevision: frozenset({"created_at", "updated_at", "published_at"}),
    Notification: frozenset({"created_at", "read_at"}),
}


class DemoSeedError(RuntimeError):
    """A seed unit could not complete; the message names the unit, never form content."""


class DemoSeedConflict(DemoSeedError):
    """Existing data is incompatible with the demo dataset; nothing is overwritten."""


def align_timestamps(instance: models.Model, **values: datetime) -> None:
    allowed = ALIGNABLE_TIMESTAMPS.get(type(instance), frozenset())
    unknown = set(values) - allowed
    if unknown:
        raise DemoSeedError(
            f"{type(instance).__name__} timestamps cannot be aligned: {sorted(unknown)}"
        )
    for name, value in values.items():
        if not isinstance(value, datetime) or timezone.is_naive(value):
            raise DemoSeedError(f"{name} must be a timezone-aware datetime")
        if value > timezone.now():
            raise DemoSeedError(f"{type(instance).__name__}.{name} cannot be in the future")
    type(instance).objects.filter(pk=instance.pk).update(**values)
    for name, value in values.items():
        setattr(instance, name, value)


def settle_notifications(
    *,
    source_id: UUID,
    occurred_at: datetime,
    event_code: str | None = None,
) -> int:
    """Timestamp a seeded event's Notifications and drop their unsent email intents."""

    notifications = Notification.objects.filter(source_id=source_id)
    if event_code is not None:
        notifications = notifications.filter(event_code=event_code)
    notification_ids = list(notifications.values_list("pk", flat=True))
    if not notification_ids:
        return 0
    Notification.objects.filter(pk__in=notification_ids).update(created_at=occurred_at)
    EmailDelivery.objects.filter(
        notification_id__in=notification_ids,
        status=EmailDeliveryStatus.PENDING,
        attempt_count=0,
    ).delete()
    return len(notification_ids)


def idempotency_key(*parts: str) -> str:
    return ":".join((IDEMPOTENCY_KEY_PREFIX, *parts))


def request_fingerprint(**values: object) -> str:
    canonical = json.dumps(values, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class SeedSession:
    """State shared by one seed run."""

    timeline: DemoTimeline
    app_env: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # The one real "now" of a run: when accounts are provisioned and a live Call Slip is issued.
    started_at: datetime = field(default_factory=lambda: timezone.now().replace(microsecond=0))
    users: dict[str, User] = field(default_factory=dict)
    emails: dict[str, str] = field(default_factory=dict)
    created: Counter = field(default_factory=Counter)
    existing: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)

    def system(self) -> AuditContext:
        return AuditContext.system(request_id=self.run_id)

    def as_user(self, key: str) -> AuditContext:
        return AuditContext.user(self.user(key), request_id=self.run_id)

    def user(self, key: str) -> User:
        user = self.users[key]
        user.refresh_from_db()
        return user

    def record(self, domain: str, *, created: bool, count: int = 1) -> None:
        (self.created if created else self.existing)[domain] += count


__all__ = [
    "ALIGNABLE_TIMESTAMPS",
    "DemoSeedConflict",
    "DemoSeedError",
    "IDEMPOTENCY_KEY_PREFIX",
    "SeedSession",
    "align_timestamps",
    "idempotency_key",
    "request_fingerprint",
    "settle_notifications",
]
