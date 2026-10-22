"""Appointment-owned, content-free eligibility for the NOTIF-01 link pilot.

No schedule, name, service text or confidential field crosses this boundary.
NOTIF-2 must add separately reviewed event-time fact projections here.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from django.utils import timezone

from compass.accounts.models import User

from .models import Appointment, AppointmentStatus
from .services import AppointmentNotFound, get_appointment_for_actor


class AppointmentEmailRecipient(StrEnum):
    STUDENT = "student"
    CURRENT_COUNSELOR = "current_counselor"
    AUTHORIZED_STAFF = "authorized_staff"


class AppointmentEmailEligibility(StrEnum):
    ALLOWED = "allowed"
    SOURCE_MISSING = "source_missing"
    SOURCE_STALE = "source_stale"
    RECIPIENT_DENIED = "recipient_denied"


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
