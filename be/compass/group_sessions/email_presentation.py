"""Group Session-owned event/participant proof and restrained external display facts."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.common.email_presentation import (
    EmailSourceEligibility,
    email_schedule,
    safe_email_display_text,
    valid_email_interval,
)
from compass.notifications.policy import NotificationEvent

from .models import GroupSession, GroupSessionRegistration, GroupSessionStatus, RegistrationStatus

GROUP_SESSION_EMAIL_EVENTS = frozenset(
    {
        NotificationEvent.GROUP_SESSION_REGISTERED,
        NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED,
        NotificationEvent.GROUP_SESSION_CANCELLED,
        NotificationEvent.GROUP_SESSION_RESCHEDULED,
    }
)


class GroupSessionEmailRecipient(StrEnum):
    STUDENT = "group_session_student"


class GroupSessionEmailField(StrEnum):
    SESSION = "Session"
    STATUS = "Status"
    CURRENT_DATE = "Current date"
    CURRENT_TIME = "Current time"
    UPDATED_DATE = "Updated date"
    UPDATED_TIME = "Updated time"
    MODE = "Delivery mode"


@dataclass(frozen=True, slots=True)
class GroupSessionEmailDetail:
    field: GroupSessionEmailField
    value: str = field(repr=False)

    def __post_init__(self):
        if (
            type(self.field) is not GroupSessionEmailField
            or safe_email_display_text(self.value) is None
        ):
            raise ValueError("invalid group session email detail")

    @property
    def label(self):
        return self.field.value


@dataclass(frozen=True, slots=True, repr=False)
class GroupSessionEmailFacts:
    event_code: str
    source_type: str
    source_id: UUID
    group_session_id: UUID
    recipient_class: GroupSessionEmailRecipient
    registration_id: UUID
    registration_status: str
    registration_cancelled_at: datetime | None
    status: str
    cancelled_at: datetime | None
    schedule_revision: int
    starts_at: datetime
    ends_at: datetime
    rich_allowed: bool
    rows: tuple[GroupSessionEmailDetail, ...]


@dataclass(frozen=True, slots=True)
class GroupSessionEmailResolution:
    eligibility: EmailSourceEligibility
    facts: GroupSessionEmailFacts | None = field(default=None, repr=False)


def resolve_group_session_email_facts(
    *, event_code, source_type, source_id, group_session_id, recipient_id, now=None
):
    at = now or timezone.now()
    recipient = User.objects.select_related("role").filter(pk=recipient_id).first()
    if (
        not recipient
        or not recipient.is_active
        or recipient.role.code != "STUDENT"
        or not recipient.has_capability("appointments.view_self")
    ):
        return GroupSessionEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    if event_code not in GROUP_SESSION_EMAIL_EVENTS:
        return GroupSessionEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
    registration_event = event_code in {
        NotificationEvent.GROUP_SESSION_REGISTERED,
        NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED,
    }
    reg = None
    if registration_event:
        if source_type != "group_session_registration":
            return GroupSessionEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
        reg = GroupSessionRegistration.objects.filter(pk=source_id).first()
        if reg is None:
            return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_MISSING)
        if reg.group_session_id != group_session_id:
            return GroupSessionEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
        if reg.student_id != recipient_id:
            return GroupSessionEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    elif source_id != group_session_id:
        return GroupSessionEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
    elif event_code == NotificationEvent.GROUP_SESSION_CANCELLED and source_type != "group_session":
        return GroupSessionEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
    session = (
        GroupSession.objects.only(
            "status",
            "cancelled_at",
            "schedule_revision",
            "version",
            "starts_at",
            "ends_at",
            "delivery_mode",
        )
        .filter(pk=group_session_id)
        .first()
    )
    if session is None:
        return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_MISSING)
    rich_allowed = True
    if event_code == NotificationEvent.GROUP_SESSION_CANCELLED:
        if session.status != GroupSessionStatus.CANCELLED or session.cancelled_at is None:
            return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        # The producer stamps exactly the same instant on its cancelled participants.
        reg = GroupSessionRegistration.objects.filter(
            group_session_id=session.pk,
            student_id=recipient_id,
            status=RegistrationStatus.CANCELLED,
            cancelled_at=session.cancelled_at,
            registered_at__lte=session.cancelled_at,
        ).first()
        if reg is None:
            return GroupSessionEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
        status = "Session cancelled"
    elif event_code == NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED:
        if (
            reg.status != RegistrationStatus.CANCELLED
            or reg.cancelled_at is None
            or session.status == GroupSessionStatus.DRAFT
        ):
            return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        if (
            GroupSessionRegistration.objects.filter(
                group_session_id=session.pk, student_id=recipient_id
            )
            .exclude(pk=reg.pk)
            .filter(Q(registered_at__gte=reg.cancelled_at) | Q(created_at__gte=reg.created_at))
            .exists()
        ):
            return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_SUPERSEDED)
        status = "Registration cancelled"
    else:
        if session.status != GroupSessionStatus.PUBLISHED or session.starts_at <= at:
            return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        if event_code == NotificationEvent.GROUP_SESSION_RESCHEDULED:
            revision = re.fullmatch(r"group_session_(schedule_)?v([1-9][0-9]{0,8})", source_type)
            if revision is None:
                return GroupSessionEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
            expected = session.schedule_revision if revision[1] else session.version
            if int(revision[2]) != expected:
                return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_SUPERSEDED)
            # Legacy general version is safe for a link, not a certified schedule projection.
            rich_allowed = bool(revision[1])
            reg = GroupSessionRegistration.objects.filter(
                group_session_id=session.pk,
                student_id=recipient_id,
                status=RegistrationStatus.REGISTERED,
            ).first()
            if reg is None:
                return GroupSessionEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
            status = "Session rescheduled"
        else:
            if reg.status != RegistrationStatus.REGISTERED:
                return GroupSessionEmailResolution(EmailSourceEligibility.SOURCE_STALE)
            status = "Registration confirmed"
    # An owned registration grants the same retained detail access as get_session.
    rows = [
        GroupSessionEmailDetail(GroupSessionEmailField.SESSION, "Group Session"),
        GroupSessionEmailDetail(GroupSessionEmailField.STATUS, status),
    ]
    if event_code in {
        NotificationEvent.GROUP_SESSION_REGISTERED,
        NotificationEvent.GROUP_SESSION_RESCHEDULED,
    }:
        if not valid_email_interval(session.starts_at, session.ends_at):
            return GroupSessionEmailResolution(EmailSourceEligibility.PROVENANCE_UNAVAILABLE)
        dates, times = email_schedule(session.starts_at, session.ends_at)
        updated = event_code == NotificationEvent.GROUP_SESSION_RESCHEDULED
        rows.extend(
            (
                GroupSessionEmailDetail(
                    GroupSessionEmailField.UPDATED_DATE
                    if updated
                    else GroupSessionEmailField.CURRENT_DATE,
                    dates,
                ),
                GroupSessionEmailDetail(
                    GroupSessionEmailField.UPDATED_TIME
                    if updated
                    else GroupSessionEmailField.CURRENT_TIME,
                    times,
                ),
            )
        )
        mode = {"IN_PERSON": "In person", "ONLINE": "Online"}.get(session.delivery_mode)
        if mode:
            rows.append(GroupSessionEmailDetail(GroupSessionEmailField.MODE, mode))
    return GroupSessionEmailResolution(
        EmailSourceEligibility.ALLOWED,
        GroupSessionEmailFacts(
            event_code,
            source_type,
            source_id,
            session.pk,
            GroupSessionEmailRecipient.STUDENT,
            reg.pk,
            reg.status,
            reg.cancelled_at,
            session.status,
            session.cancelled_at,
            session.schedule_revision,
            session.starts_at,
            session.ends_at,
            rich_allowed,
            tuple(rows),
        ),
    )
