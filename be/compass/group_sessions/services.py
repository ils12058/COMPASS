"""Transactional service operations for Group Sessions, Registrations, and Attendance."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    GROUP_SESSION_ATTENDANCE_CORRECTED,
    GROUP_SESSION_ATTENDANCE_RECORDED,
    GROUP_SESSION_CANCELLED,
    GROUP_SESSION_COMPLETED,
    GROUP_SESSION_CREATED,
    GROUP_SESSION_PUBLISHED,
    GROUP_SESSION_REGISTERED,
    GROUP_SESSION_REGISTRATION_CANCELLED,
    GROUP_SESSION_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.group_sessions.models import (
    GroupSession,
    GroupSessionAttendance,
    GroupSessionFacilitator,
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.notifications.models import Notification
from compass.realtime.publish import publish_to_user_on_commit
from compass.service_catalog.models import BookingPathwayCode, DeliveryMode, Service
from compass.service_catalog.services import service_counselor_eligible


def sanitize_csv_cell(value: Any) -> str:
    """Protect against spreadsheet formula injection."""
    if value is None:
        return ""
    s = str(value).strip()
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


def is_counselor_qualified(service: Service, counselor_id: uuid.UUID) -> bool:
    """Check if counselor is qualified to facilitate for this service."""
    counselor = (
        User.objects.select_related("role")
        .filter(id=counselor_id, role__code="COUNSELOR", is_active=True)
        .first()
    )
    if not counselor:
        return False
    return service_counselor_eligible(service, counselor)


def _emit_group_notification(
    *,
    recipient: User,
    event_code: str,
    title: str,
    message: str,
    source_type: str,
    source_id: uuid.UUID,
    target_id: uuid.UUID | None = None,
) -> None:
    try:
        Notification.objects.create(
            recipient=recipient,
            event_code=event_code,
            policy="MANDATORY_OPERATIONAL",
            title=title,
            message=message,
            source_type=source_type,
            source_id=source_id,
            target_type="GROUP_SESSION",
            target_id=target_id,
        )
        publish_to_user_on_commit(recipient.id, {"type": "notification.received"})
    except Exception:
        # Notifications should not fail the primary business transaction
        pass


def create_group_session(
    *,
    service_id: uuid.UUID,
    organizer: User,
    title: str,
    description: str = "",
    delivery_mode: str = DeliveryMode.IN_PERSON,
    venue_or_meeting_url: str = "",
    starts_at: datetime,
    ends_at: datetime,
    capacity: int,
    reg_opens_at: datetime | None = None,
    reg_closes_at: datetime | None = None,
    facilitator_ids: list[uuid.UUID] | None = None,
    lead_facilitator_id: uuid.UUID | None = None,
) -> GroupSession:
    """Create a new group session in DRAFT status."""
    service = Service.objects.filter(id=service_id).first()
    if not service:
        raise ValidationError("Service does not exist.")
    if not service.booking_pathways.filter(code=BookingPathwayCode.GROUP_SESSION).exists():
        raise ValidationError("This Service does not have the Group Sessions pathway enabled.")

    if starts_at >= ends_at:
        raise ValidationError("Session start time must be before end time.")
    if capacity < 1:
        raise ValidationError("Capacity must be at least 1.")

    if reg_opens_at and reg_closes_at and reg_opens_at >= reg_closes_at:
        raise ValidationError("Registration open time must be before close time.")
    if reg_closes_at and reg_closes_at > starts_at:
        raise ValidationError("Registration must close on or before session start time.")

    fac_ids = facilitator_ids or []
    if lead_facilitator_id and lead_facilitator_id not in fac_ids:
        fac_ids.append(lead_facilitator_id)

    # Validate facilitators
    for fac_id in fac_ids:
        if not is_counselor_qualified(service, fac_id):
            raise ValidationError(f"Counselor {fac_id} is not qualified for this Service.")

    with transaction.atomic():
        session = GroupSession.objects.create(
            service=service,
            organizer=organizer,
            title=title.strip(),
            description=description.strip(),
            delivery_mode=delivery_mode,
            venue_or_meeting_url=venue_or_meeting_url.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            reg_opens_at=reg_opens_at,
            reg_closes_at=reg_closes_at,
            capacity=capacity,
            status=GroupSessionStatus.DRAFT,
        )

        for fac_id in fac_ids:
            is_lead = fac_id == lead_facilitator_id or (
                len(fac_ids) == 1 and lead_facilitator_id is None
            )
            GroupSessionFacilitator.objects.create(
                group_session=session,
                counselor_id=fac_id,
                is_lead=is_lead,
            )

        record_event(
            context=AuditContext.user(organizer),
            action=GROUP_SESSION_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={
                "title": session.title,
                "service_id": str(service.id),
                "starts_at": session.starts_at.isoformat(),
                "ends_at": session.ends_at.isoformat(),
                "capacity": session.capacity,
                "facilitator_count": len(fac_ids),
            },
        )

    return session


def update_group_session(
    *,
    session_id: uuid.UUID,
    actor: User,
    title: str | None = None,
    description: str | None = None,
    delivery_mode: str | None = None,
    venue_or_meeting_url: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    capacity: int | None = None,
    reg_opens_at: datetime | None = None,
    reg_closes_at: datetime | None = None,
    facilitator_ids: list[uuid.UUID] | None = None,
    lead_facilitator_id: uuid.UUID | None = None,
) -> GroupSession:
    """Update an existing group session."""
    with transaction.atomic():
        session = GroupSession.objects.select_for_update().filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status in (GroupSessionStatus.CANCELLED, GroupSessionStatus.COMPLETED):
            raise ValidationError(
                f"Cannot update a session with status {session.status}."
            )

        if title is not None:
            session.title = title.strip()
        if description is not None:
            session.description = description.strip()
        if delivery_mode is not None:
            session.delivery_mode = delivery_mode
        if venue_or_meeting_url is not None:
            session.venue_or_meeting_url = venue_or_meeting_url.strip()

        new_starts = starts_at if starts_at is not None else session.starts_at
        new_ends = ends_at if ends_at is not None else session.ends_at
        if new_starts >= new_ends:
            raise ValidationError("Session start time must be before end time.")
        session.starts_at = new_starts
        session.ends_at = new_ends

        if reg_opens_at is not None:
            session.reg_opens_at = reg_opens_at
        if reg_closes_at is not None:
            session.reg_closes_at = reg_closes_at

        if (
            session.reg_opens_at
            and session.reg_closes_at
            and session.reg_opens_at >= session.reg_closes_at
        ):
            raise ValidationError("Registration open time must be before close time.")
        if session.reg_closes_at and session.reg_closes_at > session.starts_at:
            raise ValidationError("Registration must close on or before session start time.")

        if capacity is not None:
            if capacity < 1:
                raise ValidationError("Capacity must be at least 1.")
            active_regs = session.registrations.filter(status=RegistrationStatus.REGISTERED).count()
            if capacity < active_regs:
                raise ValidationError(
                    f"Capacity cannot be reduced below current registrations ({active_regs})."
                )
            session.capacity = capacity

        # Update facilitators if specified
        if facilitator_ids is not None:
            fac_ids = list(facilitator_ids)
            if lead_facilitator_id and lead_facilitator_id not in fac_ids:
                fac_ids.append(lead_facilitator_id)
            for fac_id in fac_ids:
                if not is_counselor_qualified(session.service, fac_id):
                    raise ValidationError(f"Counselor {fac_id} is not qualified for this Service.")

            session.facilitators.all().delete()
            for fac_id in fac_ids:
                is_lead = fac_id == lead_facilitator_id or (
                    len(fac_ids) == 1 and lead_facilitator_id is None
                )
                GroupSessionFacilitator.objects.create(
                    group_session=session,
                    counselor_id=fac_id,
                    is_lead=is_lead,
                )

        session.version += 1
        session.save()

        record_event(
            context=AuditContext.user(actor),
            action=GROUP_SESSION_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={
                "title": session.title,
                "version": session.version,
                "status": session.status,
            },
        )

    return session


def publish_group_session(*, session_id: uuid.UUID, actor: User) -> GroupSession:
    """Publish a draft group session."""
    with transaction.atomic():
        session = GroupSession.objects.select_for_update().filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status != GroupSessionStatus.DRAFT:
            raise ValidationError("Only DRAFT sessions can be published.")

        if not session.service.is_active:
            raise ValidationError("Cannot publish a session for an inactive Service.")
        if not session.service.booking_pathways.filter(
            code=BookingPathwayCode.GROUP_SESSION
        ).exists():
            raise ValidationError("Service does not support the Group Session pathway.")

        if session.starts_at <= timezone.now():
            raise ValidationError("Cannot publish a session scheduled in the past.")

        if not session.facilitators.exists():
            raise ValidationError("Session must have at least one facilitator before publishing.")

        session.status = GroupSessionStatus.PUBLISHED
        session.version += 1
        session.save(update_fields=["status", "version", "updated_at"])

        record_event(
            context=AuditContext.user(actor),
            action=GROUP_SESSION_PUBLISHED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={"title": session.title, "starts_at": session.starts_at.isoformat()},
        )

    return session


def cancel_group_session(
    *, session_id: uuid.UUID, actor: User, reason: str
) -> GroupSession:
    """Cancel an active or draft group session and notify registered students."""
    if not reason.strip():
        raise ValidationError("Cancellation reason is required.")

    with transaction.atomic():
        session = GroupSession.objects.select_for_update().filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status in (GroupSessionStatus.CANCELLED, GroupSessionStatus.COMPLETED):
            raise ValidationError(
                f"Cannot cancel a session with status {session.status}."
            )

        now = timezone.now()
        session.status = GroupSessionStatus.CANCELLED
        session.cancellation_reason = reason.strip()
        session.cancelled_at = now
        session.version += 1
        session.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancelled_at",
                "version",
                "updated_at",
            ]
        )

        # Cancel all active student registrations
        active_regs = list(
            session.registrations.filter(status=RegistrationStatus.REGISTERED).select_related(
                "student"
            )
        )
        for reg in active_regs:
            reg.status = RegistrationStatus.CANCELLED
            reg.cancelled_at = now
            reg.cancellation_reason = f"Session cancelled by staff: {reason.strip()}"
            reg.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])

            _emit_group_notification(
                recipient=reg.student,
                event_code="group_session.cancelled",
                title=f"Session Cancelled: {session.title}",
                message=f"The group session '{session.title}' scheduled for {session.starts_at.strftime('%b %d, %Y %I:%M %p')} has been cancelled. Reason: {reason.strip()}",
                source_type="group_session",
                source_id=session.id,
                target_id=session.id,
            )

        record_event(
            context=AuditContext.user(actor),
            action=GROUP_SESSION_CANCELLED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={
                "title": session.title,
                "reason": reason.strip(),
                "cancelled_registrations_count": len(active_regs),
            },
        )

    return session


def complete_group_session(*, session_id: uuid.UUID, actor: User) -> GroupSession:
    """Mark a published group session as COMPLETED."""
    with transaction.atomic():
        session = GroupSession.objects.select_for_update().filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status != GroupSessionStatus.PUBLISHED:
            raise ValidationError("Only PUBLISHED sessions can be completed.")

        session.status = GroupSessionStatus.COMPLETED
        session.version += 1
        session.save(update_fields=["status", "version", "updated_at"])

        record_event(
            context=AuditContext.user(actor),
            action=GROUP_SESSION_COMPLETED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={"title": session.title},
        )

    return session


def delete_group_session(*, session_id: uuid.UUID, actor: User) -> None:
    """Delete a DRAFT group session."""
    with transaction.atomic():
        session = GroupSession.objects.select_for_update().filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status != GroupSessionStatus.DRAFT:
            raise ValidationError("Only DRAFT sessions can be deleted.")

        session_id = session.id
        session_title = session.title
        session.facilitators.all().delete()
        session.delete()

        record_event(
            context=AuditContext.user(actor),
            action="group_session.deleted",
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session_id,
            metadata={"title": session_title},
        )


def register_student(*, session_id: uuid.UUID, student: User) -> GroupSessionRegistration:
    """Register a student for a published group session with transactional capacity guard."""
    now = timezone.now()

    with transaction.atomic():
        session = GroupSession.objects.select_for_update().filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status != GroupSessionStatus.PUBLISHED:
            raise ValidationError("Session is not open for registration.")
        if session.starts_at <= now:
            raise ValidationError("This session has already commenced.")

        if session.reg_opens_at and session.reg_opens_at > now:
            raise ValidationError(
                f"Registration has not opened yet. It opens on {session.reg_opens_at.strftime('%b %d, %Y %I:%M %p')}."
            )
        if session.reg_closes_at and session.reg_closes_at < now:
            raise ValidationError("Registration for this session has closed.")

        # Check existing registration
        existing = session.registrations.filter(
            student=student, status=RegistrationStatus.REGISTERED
        ).first()
        if existing:
            raise ValidationError("You are already registered for this session.")

        active_count = session.registrations.filter(
            status=RegistrationStatus.REGISTERED
        ).count()
        if active_count >= session.capacity:
            raise ValidationError("This session is full. Maximum participant capacity reached.")

        registration = GroupSessionRegistration.objects.create(
            group_session=session,
            student=student,
            status=RegistrationStatus.REGISTERED,
            registered_at=now,
        )

        _emit_group_notification(
            recipient=student,
            event_code="group_session.registered",
            title=f"Registration Confirmed: {session.title}",
            message=f"You are successfully registered for '{session.title}' on {session.starts_at.strftime('%b %d, %Y %I:%M %p')}.",
            source_type="group_session_registration",
            source_id=registration.id,
            target_id=session.id,
        )

        record_event(
            context=AuditContext.user(student),
            action=GROUP_SESSION_REGISTERED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.registration",
            target_id=registration.id,
            metadata={
                "group_id": str(session.id),
                "title": session.title,
                "capacity": session.capacity,
                "current_count": active_count + 1,
            },
        )

    return registration


def cancel_student_registration(
    *, session_id: uuid.UUID, student: User, reason: str = ""
) -> GroupSessionRegistration:
    """Cancel a student's registration for a group session."""
    with transaction.atomic():
        registration = (
            GroupSessionRegistration.objects.select_for_update()
            .filter(
                group_session_id=session_id,
                student=student,
                status=RegistrationStatus.REGISTERED,
            )
            .select_related("group_session")
            .first()
        )
        if not registration:
            raise ValidationError("Active registration not found.")

        now = timezone.now()
        session = registration.group_session
        if session.status in (GroupSessionStatus.CANCELLED, GroupSessionStatus.COMPLETED):
            raise ValidationError("Cannot cancel registration for an ended or cancelled session.")

        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = now
        registration.cancellation_reason = reason.strip() or "Cancelled by student"
        registration.save(
            update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"]
        )

        _emit_group_notification(
            recipient=student,
            event_code="group_session.registration_cancelled",
            title=f"Registration Cancelled: {session.title}",
            message=f"Your registration for '{session.title}' on {session.starts_at.strftime('%b %d, %Y %I:%M %p')} has been cancelled.",
            source_type="group_session_registration",
            source_id=registration.id,
            target_id=session.id,
        )

        record_event(
            context=AuditContext.user(student),
            action=GROUP_SESSION_REGISTRATION_CANCELLED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.registration",
            target_id=registration.id,
            metadata={"group_id": str(session.id), "title": session.title},
        )

    return registration


def record_attendance(
    *,
    session_id: uuid.UUID,
    actor: User,
    records: list[dict[str, Any]],
) -> list[GroupSessionAttendance]:
    """Record or correct participant attendance for a session."""
    with transaction.atomic():
        session = GroupSession.objects.filter(id=session_id).first()
        if not session:
            raise ValidationError("Group session not found.")
        if session.status not in (GroupSessionStatus.PUBLISHED, GroupSessionStatus.COMPLETED):
            raise ValidationError(
                "Attendance can only be recorded for PUBLISHED or COMPLETED sessions."
            )

        updated_attendances = []
        is_correction = False

        for item in records:
            reg_id = item.get("registration_id")
            attended = bool(item.get("attended", True))
            notes = str(item.get("notes", "")).strip()

            registration = session.registrations.filter(id=reg_id).first()
            if not registration:
                raise ValidationError(f"Registration {reg_id} not found in this session.")

            attendance, created = GroupSessionAttendance.objects.get_or_create(
                registration=registration,
                defaults={
                    "attended": attended,
                    "marked_by": actor,
                    "notes": notes,
                },
            )
            if not created:
                is_correction = True
                attendance.attended = attended
                attendance.marked_by = actor
                attendance.notes = notes
                attendance.save(update_fields=["attended", "marked_by", "notes", "updated_at"])

            updated_attendances.append(attendance)

        audit_action = (
            GROUP_SESSION_ATTENDANCE_CORRECTED
            if is_correction
            else GROUP_SESSION_ATTENDANCE_RECORDED
        )
        record_event(
            context=AuditContext.user(actor),
            action=audit_action,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.attendance",
            target_id=session.id,
            metadata={
                "group_id": str(session.id),
                "records_count": len(updated_attendances),
                "is_correction": is_correction,
            },
        )

    return updated_attendances


def export_roster_csv(*, session_id: uuid.UUID, actor: User) -> str:
    """Generate participant roster CSV with formula injection defense."""
    session = (
        GroupSession.objects.filter(id=session_id)
        .select_related("service")
        .prefetch_related(
            "registrations__student",
            "registrations__attendance",
        )
        .first()
    )
    if not session:
        raise ValidationError("Group session not found.")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "Student Name",
            "Institutional ID",
            "Email",
            "Registration Status",
            "Registration Time",
            "Attendance",
            "Attendance Notes",
        ]
    )

    for reg in session.registrations.all().order_by("registered_at"):
        student = reg.student
        student_id = getattr(student, "institutional_id", "") or ""
        email = student.email or ""
        name = f"{student.last_name}, {student.first_name}"
        status = reg.status
        reg_time = reg.registered_at.strftime("%Y-%m-%d %H:%M:%S")

        attendance_status = "Not Marked"
        notes = ""
        if hasattr(reg, "attendance") and reg.attendance:
            attendance_status = "Present" if reg.attendance.attended else "Absent"
            notes = reg.attendance.notes

        writer.writerow(
            [
                sanitize_csv_cell(name),
                sanitize_csv_cell(student_id),
                sanitize_csv_cell(email),
                sanitize_csv_cell(status),
                sanitize_csv_cell(reg_time),
                sanitize_csv_cell(attendance_status),
                sanitize_csv_cell(notes),
            ]
        )

    record_event(
        context=AuditContext.user(actor),
        action="report.export_released",
        outcome=AuditOutcome.SUCCESS,
        target_type="service.group.roster",
        target_id=session.id,
        metadata={"title": session.title},
    )

    return output.getvalue()


def get_group_session_metrics(
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    service_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Calculate operational reporting metrics for group sessions."""
    qs = GroupSession.objects.all()
    if service_id:
        qs = qs.filter(service_id=service_id)
    if from_date:
        qs = qs.filter(starts_at__gte=from_date)
    if to_date:
        qs = qs.filter(ends_at__lte=to_date)

    total_sessions = qs.count()
    published_count = qs.filter(status=GroupSessionStatus.PUBLISHED).count()
    completed_count = qs.filter(status=GroupSessionStatus.COMPLETED).count()
    cancelled_count = qs.filter(status=GroupSessionStatus.CANCELLED).count()

    # Registrations across these sessions
    regs = GroupSessionRegistration.objects.filter(group_session__in=qs)
    total_registrations = regs.filter(status=RegistrationStatus.REGISTERED).count()
    cancelled_registrations = regs.filter(status=RegistrationStatus.CANCELLED).count()

    total_capacity = sum(qs.values_list("capacity", flat=True)) or 0
    utilization_rate = (
        round((total_registrations / total_capacity) * 100, 1)
        if total_capacity > 0
        else 0.0
    )

    # Attendance
    attendances = GroupSessionAttendance.objects.filter(registration__group_session__in=qs)
    attended_count = attendances.filter(attended=True).count()
    absent_count = attendances.filter(attended=False).count()
    attendance_rate = (
        round((attended_count / (attended_count + absent_count)) * 100, 1)
        if (attended_count + absent_count) > 0
        else 0.0
    )

    return {
        "total_sessions": total_sessions,
        "published_sessions": published_count,
        "completed_sessions": completed_count,
        "cancelled_sessions": cancelled_count,
        "total_capacity": total_capacity,
        "total_registrations": total_registrations,
        "cancelled_registrations": cancelled_registrations,
        "capacity_utilization_percent": utilization_rate,
        "attended_count": attended_count,
        "absent_count": absent_count,
        "attendance_rate_percent": attendance_rate,
    }
