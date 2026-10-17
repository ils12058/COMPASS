"""Transactional service operations for Group Sessions, Registrations, and Attendance."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
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
    GROUP_SESSION_WITHDRAWN,
    REPORT_EXPORT_RELEASED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.group_sessions.access import (
    current_group_session_staff,
    require_group_session_access,
    scope_group_sessions,
    supervised_counselor,
)
from compass.group_sessions.models import (
    GroupSession,
    GroupSessionAttendance,
    GroupSessionFacilitator,
    GroupSessionFacilitatorKind,
    GroupSessionRegistration,
    GroupSessionStatus,
    RegistrationStatus,
)
from compass.notifications.models import Notification
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.notifications.services import create_notification_for_event
from compass.service_catalog.models import BookingPathwayCode, DeliveryMode, Service
from compass.service_catalog.scheduling import (
    lock_schedule_users,
    providers_with_schedule_conflicts,
    student_schedule_conflict,
    students_with_schedule_conflicts,
)
from compass.service_catalog.services import (
    service_supports_delivery_mode,
)

INTERNAL_FACILITATOR_ROLE_CODES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})


def _normalize_facilitator_assignments(
    *,
    assignments: list[dict[str, Any]] | None,
    legacy_facilitator_ids: list[uuid.UUID] | None,
    lead_facilitator_id: uuid.UUID | None,
) -> list[dict[str, Any]] | None:
    """Normalize the mixed identity request and keep the legacy Counselor input compatible."""

    if assignments is None:
        if legacy_facilitator_ids is not None and not isinstance(legacy_facilitator_ids, list):
            raise ValidationError("Facilitator IDs must be a list.")
        if legacy_facilitator_ids is None:
            return None
        normalized = [
            {
                "kind": GroupSessionFacilitatorKind.INTERNAL,
                "internal_user_id": user_id,
                "external_display_name": "",
                "is_lead": False,
            }
            for user_id in legacy_facilitator_ids
        ]
    else:
        if not isinstance(assignments, list) or not all(
            isinstance(raw, dict) for raw in assignments
        ):
            raise ValidationError("Facilitators must be provided as a list.")
        if legacy_facilitator_ids:
            raise ValidationError("Use either facilitators or facilitator_ids, not both.")
        normalized = []
        for raw in assignments:
            kind = raw.get("kind")
            if kind not in GroupSessionFacilitatorKind.values:
                raise ValidationError("Each facilitator must be INTERNAL or EXTERNAL.")
            internal_user_id = raw.get("internal_user_id")
            raw_external_name = raw.get("external_display_name", "")
            if not isinstance(raw_external_name, str):
                raise ValidationError("External facilitator names must be text.")
            external_name = raw_external_name.strip()
            is_lead = raw.get("is_lead", False)
            if type(is_lead) is not bool:
                raise ValidationError("Facilitator lead status must be a boolean.")
            if kind == GroupSessionFacilitatorKind.INTERNAL:
                if not isinstance(internal_user_id, uuid.UUID):
                    raise ValidationError("Select an internal facilitator account.")
                if external_name:
                    raise ValidationError(
                        "An internal facilitator cannot include an external name."
                    )
            else:
                if internal_user_id is not None:
                    raise ValidationError(
                        "An external guest cannot be linked to a COMPASS account."
                    )
                if not external_name or len(external_name) > 255:
                    raise ValidationError(
                        "Enter an external facilitator name up to 255 characters."
                    )
            normalized.append(
                {
                    "kind": kind,
                    "internal_user_id": internal_user_id,
                    "external_display_name": external_name,
                    "is_lead": is_lead,
                }
            )

    seen_internal: set[uuid.UUID] = set()
    seen_external: set[str] = set()
    for item in normalized:
        if item["kind"] == GroupSessionFacilitatorKind.INTERNAL:
            user_id = item["internal_user_id"]
            if user_id in seen_internal:
                raise ValidationError("An internal facilitator may be assigned only once.")
            seen_internal.add(user_id)
        else:
            identity = item["external_display_name"].casefold()
            if identity in seen_external:
                raise ValidationError("An external facilitator may be assigned only once.")
            seen_external.add(identity)

    if lead_facilitator_id is not None:
        matching = [
            item
            for item in normalized
            if item["kind"] == GroupSessionFacilitatorKind.INTERNAL
            and item["internal_user_id"] == lead_facilitator_id
        ]
        if not matching:
            raise ValidationError("The lead facilitator must be one of the assigned facilitators.")
        for item in normalized:
            item["is_lead"] = item is matching[0]

    leads = [item for item in normalized if item["is_lead"]]
    if len(leads) > 1:
        raise ValidationError("Choose only one lead facilitator.")
    if normalized and not leads:
        # The first listed facilitator is the lead unless the organizer selects another.
        normalized[0]["is_lead"] = True
    return normalized


def _active_facilitator_identity(item: GroupSessionFacilitator) -> tuple[str, object]:
    if item.kind == GroupSessionFacilitatorKind.INTERNAL:
        return (item.kind, item.internal_user_id)
    return (item.kind, item.external_display_name.casefold())


def _assignment_identity(item: dict[str, Any]) -> tuple[str, object]:
    if item["kind"] == GroupSessionFacilitatorKind.INTERNAL:
        return (item["kind"], item["internal_user_id"])
    return (item["kind"], item["external_display_name"].casefold())


def _validate_internal_facilitators(
    assignments: list[dict[str, Any]], users: dict[uuid.UUID, User], *, actor: User
) -> None:
    in_scope_ids = {item.pk for item in list_group_facilitator_candidates(actor=actor)}
    for item in assignments:
        if item["kind"] != GroupSessionFacilitatorKind.INTERNAL:
            continue
        person = users.get(item["internal_user_id"])
        if (
            person is None
            or person.pk not in in_scope_ids
            or not person.is_active
            or person.role.code not in INTERNAL_FACILITATOR_ROLE_CODES
            or not person.has_capability("appointments.manage")
        ):
            raise ValidationError("The selected internal facilitator is not currently eligible.")


def _write_facilitator_assignments(
    *,
    session: GroupSession,
    assignments: list[dict[str, Any]],
    users: dict[uuid.UUID, User],
    now: datetime,
) -> bool:
    """Version assignment changes by ending old rows, never deleting facilitator history."""

    active = list(
        GroupSessionFacilitator.objects.select_for_update(of=("self",)).filter(
            group_session=session,
            removed_at__isnull=True,
        )
    )
    desired = {_assignment_identity(item): item for item in assignments}
    current = {_active_facilitator_identity(item): item for item in active}
    changed = False
    for identity, record in current.items():
        target = desired.get(identity)
        if target is None or target["is_lead"] != record.is_lead:
            record.removed_at = now
            record.save(update_fields=["removed_at"])
            changed = True
    for identity, item in desired.items():
        existing = current.get(identity)
        if existing is not None and existing.is_lead == item["is_lead"]:
            continue
        GroupSessionFacilitator.objects.create(
            group_session=session,
            kind=item["kind"],
            internal_user=(
                users.get(item["internal_user_id"])
                if item["kind"] == GroupSessionFacilitatorKind.INTERNAL
                else None
            ),
            external_display_name=item["external_display_name"],
            is_lead=item["is_lead"],
        )
        changed = True
    return changed


def _actor_schedule_lock_ids(actor: User) -> tuple[uuid.UUID, ...]:
    current = current_group_session_staff(actor)
    if current is None:
        raise ValidationError("Group session not found.")
    ids = {current.pk}
    if current.role.code == "GUIDANCE_SERVICES_STAFF":
        supervisor = supervised_counselor(current)
        if supervisor is None:
            raise ValidationError("Group session not found.")
        ids.add(supervisor.pk)
    return tuple(ids)


def _schedule_context_snapshot(session_id: uuid.UUID):
    session = GroupSession.objects.filter(pk=session_id).first()
    if session is None:
        raise ValidationError("Group session not found.")
    facilitator_ids = tuple(
        GroupSessionFacilitator.objects.filter(
            group_session_id=session_id,
            kind=GroupSessionFacilitatorKind.INTERNAL,
            removed_at__isnull=True,
        ).values_list("internal_user_id", flat=True)
    )
    student_ids = tuple(
        GroupSessionRegistration.objects.filter(
            group_session_id=session_id,
            status=RegistrationStatus.REGISTERED,
        ).values_list("student_id", flat=True)
    )
    return session, facilitator_ids, student_ids


def _lock_group_schedule_context(
    *,
    session_id: uuid.UUID,
    actor: User,
    new_facilitator_ids: tuple[uuid.UUID, ...] = (),
):
    """Lock Users in canonical order, then Service and Group Session; reject stale snapshots."""

    snapshot, old_facilitator_ids, old_student_ids = _schedule_context_snapshot(session_id)
    try:
        lock_schedule_users(
            *_actor_schedule_lock_ids(actor),
            snapshot.organizer_id,
            *old_facilitator_ids,
            *new_facilitator_ids,
            *old_student_ids,
        )
    except ValueError as exc:
        raise ValidationError("A Group Session participant is no longer available; retry.") from exc
    service = Service.objects.select_for_update().filter(pk=snapshot.service_id).first()
    session = (
        GroupSession.objects.select_for_update(of=("self",))
        .select_related("service", "organizer__role")
        .filter(pk=session_id, service_id=snapshot.service_id)
        .first()
    )
    if session is None or service is None:
        raise ValidationError("Group session not found.")
    _, current_facilitator_ids, current_student_ids = _schedule_context_snapshot(session_id)
    if set(current_facilitator_ids) != set(old_facilitator_ids) or set(current_student_ids) != set(
        old_student_ids
    ):
        raise ValidationError("Group Session participants changed during this operation; retry.")
    return session, service, old_facilitator_ids, old_student_ids


def sanitize_csv_cell(value: Any) -> str:
    """Protect against spreadsheet formula injection."""
    if value is None:
        return ""
    s = str(value).strip()
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


def list_group_facilitator_candidates(
    *, actor: User, search: str | None = None
) -> tuple[User, ...]:
    """Return internal facilitator candidates in the actor's direct operational scope."""

    current = current_group_session_staff(actor)
    if current is None:
        raise PermissionError("Group Session management access is required.")
    if current.role.code == "GUIDANCE_SERVICES_STAFF":
        supervisor = supervised_counselor(current)
        if supervisor is None:
            raise PermissionError("Group Session management access is required.")
        scoped = Q(pk__in={current.pk, supervisor.pk})
    else:
        from compass.organization.models import StaffSupervision

        direct_staff_ids = set(
            StaffSupervision.objects.filter(
                supervisor_id=current.pk,
                staff__is_active=True,
                staff__role__code="GUIDANCE_SERVICES_STAFF",
            ).values_list("staff_id", flat=True)
        )
        # A Counselor may explicitly invite another current Counselor as a session facilitator.
        # GSS candidates stay restricted to directly supervised staff.
        scoped = Q(role__code="COUNSELOR") | Q(pk__in=direct_staff_ids)

    candidates = User.objects.select_related("role").filter(
        scoped,
        is_active=True,
        role__code__in=INTERNAL_FACILITATOR_ROLE_CODES,
    )
    if search is not None:
        if not isinstance(search, str):
            raise ValidationError("Search must be text.")
        for token in search.strip()[:160].split():
            candidates = candidates.filter(
                Q(first_name__icontains=token)
                | Q(middle_name__icontains=token)
                | Q(last_name__icontains=token)
            )
    return tuple(
        item
        for item in candidates.order_by("last_name", "first_name", "pk")
        if item.has_capability("appointments.manage")
    )


def group_session_notification_is_current(notification: Notification) -> bool:
    """Verify that a Group Session notification is still current before external delivery."""
    if not notification.recipient.is_active:
        return False
    event_code = notification.event_code
    if event_code == NotificationEvent.GROUP_SESSION_REGISTERED:
        return GroupSessionRegistration.objects.filter(
            pk=notification.source_id,
            student_id=notification.recipient_id,
            status=RegistrationStatus.REGISTERED,
            group_session__status=GroupSessionStatus.PUBLISHED,
        ).exists()
    if event_code == NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED:
        return GroupSessionRegistration.objects.filter(
            pk=notification.source_id,
            student_id=notification.recipient_id,
            status=RegistrationStatus.CANCELLED,
        ).exists()
    if event_code == NotificationEvent.GROUP_SESSION_CANCELLED:
        return GroupSession.objects.filter(
            pk=notification.source_id,
            status=GroupSessionStatus.CANCELLED,
        ).exists()
    if event_code == NotificationEvent.GROUP_SESSION_RESCHEDULED:
        session = GroupSession.objects.filter(
            pk=notification.source_id,
            status=GroupSessionStatus.PUBLISHED,
        ).first()
        if session is None:
            return False
        source_type = notification.source_type
        if source_type.startswith("group_session_schedule_v"):
            revision_value = source_type.removeprefix("group_session_schedule_v")
            if not revision_value.isdigit() or int(revision_value) != session.schedule_revision:
                return False
        elif source_type.startswith("group_session_v"):
            # Read legacy notices using the old general version until they age out.
            revision_value = source_type.removeprefix("group_session_v")
            if not revision_value.isdigit() or int(revision_value) != session.version:
                return False
        else:
            return False
        return GroupSessionRegistration.objects.filter(
            group_session_id=session.pk,
            student_id=notification.recipient_id,
            status=RegistrationStatus.REGISTERED,
        ).exists()
    return True


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
    facilitators: list[dict[str, Any]] | None = None,
    facilitator_ids: list[uuid.UUID] | None = None,
    lead_facilitator_id: uuid.UUID | None = None,
) -> GroupSession:
    """Create a new group session in DRAFT status."""
    cleaned_title = title.strip()
    if not cleaned_title:
        raise ValidationError("Session title is required.")

    if starts_at >= ends_at:
        raise ValidationError("Session start time must be before end time.")
    if timezone.is_naive(starts_at) or timezone.is_naive(ends_at):
        raise ValidationError("Session start and end times must include a time zone.")
    if capacity < 1:
        raise ValidationError("Capacity must be at least 1.")

    for value in (reg_opens_at, reg_closes_at):
        if value is not None and timezone.is_naive(value):
            raise ValidationError("Registration times must include a time zone.")

    if reg_opens_at and reg_closes_at and reg_opens_at >= reg_closes_at:
        raise ValidationError("Registration open time must be before close time.")
    if reg_opens_at and reg_opens_at >= starts_at:
        raise ValidationError("Registration must open before the session starts.")
    if reg_closes_at and reg_closes_at > starts_at:
        raise ValidationError("Registration must close on or before session start time.")
    assignments = (
        _normalize_facilitator_assignments(
            assignments=facilitators,
            legacy_facilitator_ids=facilitator_ids or [],
            lead_facilitator_id=lead_facilitator_id,
        )
        or []
    )
    internal_ids = tuple(
        item["internal_user_id"]
        for item in assignments
        if item["kind"] == GroupSessionFacilitatorKind.INTERNAL
    )

    with transaction.atomic():
        actor_ids = _actor_schedule_lock_ids(organizer)
        try:
            locked_users = lock_schedule_users(*actor_ids, *internal_ids)
        except ValueError as exc:
            raise ValidationError("The selected internal facilitator is not available.") from exc
        current_organizer = current_group_session_staff(organizer, lock_supervision=True)
        if current_organizer is None:
            raise ValidationError("Group session not found.")
        service = Service.objects.select_for_update().filter(id=service_id).first()
        if not service:
            raise ValidationError("Service does not exist.")
        if not service.is_active:
            raise ValidationError("An inactive Service cannot accept new Group Sessions.")
        if not service.booking_pathways.filter(code=BookingPathwayCode.GROUP_SESSION).exists():
            raise ValidationError("This Service does not have the Group Sessions pathway enabled.")
        if not service_supports_delivery_mode(service, delivery_mode):
            raise ValidationError(
                f"Delivery mode '{delivery_mode}' is not supported by this Service."
            )
        _validate_internal_facilitators(assignments, locked_users, actor=current_organizer)

        session = GroupSession.objects.create(
            service=service,
            organizer=current_organizer,
            title=cleaned_title,
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

        _write_facilitator_assignments(
            session=session,
            assignments=assignments,
            users=locked_users,
            now=timezone.now(),
        )

        record_event(
            context=AuditContext.user(current_organizer),
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
                "facilitator_count": len(assignments),
                "external_facilitator_count": sum(
                    item["kind"] == GroupSessionFacilitatorKind.EXTERNAL for item in assignments
                ),
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
    reg_opens_at_provided: bool | None = None,
    reg_closes_at_provided: bool | None = None,
    facilitators: list[dict[str, Any]] | None = None,
    facilitator_ids: list[uuid.UUID] | None = None,
    lead_facilitator_id: uuid.UUID | None = None,
) -> GroupSession:
    """Update an existing group session and notify registered students on material reschedule."""
    assignments = _normalize_facilitator_assignments(
        assignments=facilitators,
        legacy_facilitator_ids=facilitator_ids,
        lead_facilitator_id=lead_facilitator_id,
    )
    new_facilitator_ids = tuple(
        item["internal_user_id"]
        for item in assignments or []
        if item["kind"] == GroupSessionFacilitatorKind.INTERNAL
    )
    with transaction.atomic():
        session, locked_service, old_facilitator_ids, old_student_ids = (
            _lock_group_schedule_context(
                session_id=session_id,
                actor=actor,
                new_facilitator_ids=new_facilitator_ids,
            )
        )
        locked_ids = set(_actor_schedule_lock_ids(actor)) | {session.organizer_id}
        locked_ids.update(old_facilitator_ids)
        locked_ids.update(old_student_ids)
        locked_ids.update(new_facilitator_ids)
        locked_users = {
            user.pk: user for user in User.objects.select_related("role").filter(pk__in=locked_ids)
        }
        require_group_session_access(
            actor=actor,
            session=session,
            permission="can_manage",
            lock_supervision=True,
        )
        if session.status in (GroupSessionStatus.CANCELLED, GroupSessionStatus.COMPLETED):
            raise ValidationError(f"Cannot update a session with status {session.status}.")

        old_starts = session.starts_at
        old_ends = session.ends_at
        old_mode = session.delivery_mode
        old_venue = session.venue_or_meeting_url
        active_facilitators = list(
            GroupSessionFacilitator.objects.filter(
                group_session=session,
                removed_at__isnull=True,
            )
        )
        if assignments is None:
            desired_assignments = [
                {
                    "kind": item.kind,
                    "internal_user_id": item.internal_user_id,
                    "external_display_name": item.external_display_name,
                    "is_lead": item.is_lead,
                }
                for item in active_facilitators
            ]
        else:
            desired_assignments = assignments
            _validate_internal_facilitators(desired_assignments, locked_users, actor=actor)
        if session.status == GroupSessionStatus.PUBLISHED and not desired_assignments:
            raise ValidationError("Published session must have at least one facilitator.")
        current_identity_leads = {
            _active_facilitator_identity(item): item.is_lead for item in active_facilitators
        }
        desired_identity_leads = {
            _assignment_identity(item): item["is_lead"] for item in desired_assignments
        }
        facilitator_assignments_changed = current_identity_leads != desired_identity_leads
        current_internal_ids = {
            item.internal_user_id
            for item in active_facilitators
            if item.kind == GroupSessionFacilitatorKind.INTERNAL
        }
        desired_internal_ids = {
            item["internal_user_id"]
            for item in desired_assignments
            if item["kind"] == GroupSessionFacilitatorKind.INTERNAL
        }

        if title is not None:
            cleaned_title = title.strip()
            if not cleaned_title:
                raise ValidationError("Session title is required.")
            session.title = cleaned_title
        if description is not None:
            session.description = description.strip()
        if delivery_mode is not None:
            if not service_supports_delivery_mode(locked_service, delivery_mode):
                raise ValidationError(
                    f"Delivery mode '{delivery_mode}' is not supported by this Service."
                )
            session.delivery_mode = delivery_mode
        if venue_or_meeting_url is not None:
            session.venue_or_meeting_url = venue_or_meeting_url.strip()

        new_starts = starts_at if starts_at is not None else session.starts_at
        new_ends = ends_at if ends_at is not None else session.ends_at
        if timezone.is_naive(new_starts) or timezone.is_naive(new_ends):
            raise ValidationError("Session start and end times must include a time zone.")
        if new_starts >= new_ends:
            raise ValidationError("Session start time must be before end time.")
        if session.status == GroupSessionStatus.PUBLISHED and new_starts <= timezone.now():
            raise ValidationError("A published Group Session must remain scheduled in the future.")
        session.starts_at = new_starts
        session.ends_at = new_ends

        update_reg_opens = (
            reg_opens_at is not None if reg_opens_at_provided is None else reg_opens_at_provided
        )
        update_reg_closes = (
            reg_closes_at is not None if reg_closes_at_provided is None else reg_closes_at_provided
        )
        if update_reg_opens:
            if reg_opens_at is not None and timezone.is_naive(reg_opens_at):
                raise ValidationError("Registration times must include a time zone.")
            session.reg_opens_at = reg_opens_at
        if update_reg_closes:
            if reg_closes_at is not None and timezone.is_naive(reg_closes_at):
                raise ValidationError("Registration times must include a time zone.")
            session.reg_closes_at = reg_closes_at

        if (
            session.reg_opens_at
            and session.reg_closes_at
            and session.reg_opens_at >= session.reg_closes_at
        ):
            raise ValidationError("Registration open time must be before close time.")
        if session.reg_opens_at and session.reg_opens_at >= session.starts_at:
            raise ValidationError("Registration must open before the session starts.")
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

        schedule_changed = session.starts_at != old_starts or session.ends_at != old_ends
        schedule_or_delivery_changed = (
            schedule_changed
            or session.delivery_mode != old_mode
            or session.venue_or_meeting_url != old_venue
        )
        if session.status == GroupSessionStatus.PUBLISHED and (
            schedule_changed or current_internal_ids != desired_internal_ids
        ):
            inactive_facilitators = [
                user_id
                for user_id in desired_internal_ids
                if user_id not in locked_users
                or not locked_users[user_id].is_active
                or locked_users[user_id].role.code not in INTERNAL_FACILITATOR_ROLE_CODES
            ]
            if inactive_facilitators:
                raise ValidationError(
                    "Replace inactive internal facilitators before changing the published schedule."
                )
            provider_conflicts = providers_with_schedule_conflicts(
                provider_ids=desired_internal_ids,
                starts_at=session.starts_at,
                ends_at=session.ends_at,
                exclude_group_session_id=session.pk,
            )
            if provider_conflicts:
                raise ValidationError(
                    "A facilitator has an overlapping Appointment, Fixed Slot, or Group Session."
                )
        if session.status == GroupSessionStatus.PUBLISHED and schedule_changed:
            student_conflicts = students_with_schedule_conflicts(
                student_ids=old_student_ids,
                starts_at=session.starts_at,
                ends_at=session.ends_at,
                exclude_group_session_id=session.pk,
            )
            if student_conflicts:
                raise ValidationError(
                    "The revised time overlaps an Appointment or another registered Group Session. "
                    "Resolve those conflicts before rescheduling this event."
                )

        assignment_changed = False
        if facilitator_assignments_changed:
            assignment_changed = _write_facilitator_assignments(
                session=session,
                assignments=desired_assignments,
                users=locked_users,
                now=timezone.now(),
            )

        session.version += 1
        if schedule_or_delivery_changed:
            session.schedule_revision += 1
        session.save()
        if session.status == GroupSessionStatus.PUBLISHED and schedule_or_delivery_changed:
            active_regs_list = list(
                session.registrations.filter(status=RegistrationStatus.REGISTERED).select_related(
                    "student"
                )
            )
            for reg in active_regs_list:
                create_notification_for_event(
                    recipient=reg.student,
                    event=NotificationEvent.GROUP_SESSION_RESCHEDULED,
                    source_type=f"group_session_schedule_v{session.schedule_revision}",
                    source_id=session.id,
                    target_type=NotificationTargetType.GROUP_SESSION,
                    target_id=session.id,
                )

        record_event(
            context=AuditContext.user(actor),
            action=GROUP_SESSION_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={
                "title": session.title,
                "version": session.version,
                "schedule_revision": session.schedule_revision,
                "status": session.status,
                "facilitator_assignments_changed": assignment_changed,
            },
        )

    return session


def publish_group_session(*, session_id: uuid.UUID, actor: User) -> GroupSession:
    """Publish a draft group session."""
    with transaction.atomic():
        session, service, facilitator_ids, student_ids = _lock_group_schedule_context(
            session_id=session_id,
            actor=actor,
        )
        locked_users = {
            user.pk: user
            for user in User.objects.select_related("role").filter(
                pk__in=set(_actor_schedule_lock_ids(actor))
                | {session.organizer_id}
                | set(facilitator_ids)
                | set(student_ids)
            )
        }
        require_group_session_access(
            actor=actor,
            session=session,
            permission="can_manage",
            lock_supervision=True,
        )
        if session.status != GroupSessionStatus.DRAFT:
            raise ValidationError("Only DRAFT sessions can be published.")

        if not service.is_active:
            raise ValidationError("Cannot publish a session for an inactive Service.")
        if not service.booking_pathways.filter(code=BookingPathwayCode.GROUP_SESSION).exists():
            raise ValidationError("Service does not support the Group Session pathway.")
        if not service_supports_delivery_mode(service, session.delivery_mode):
            raise ValidationError(
                f"Delivery mode '{session.delivery_mode}' is not supported by this Service."
            )

        if session.starts_at <= timezone.now():
            raise ValidationError("Cannot publish a session scheduled in the past.")

        facilitators = list(
            GroupSessionFacilitator.objects.filter(
                group_session=session,
                removed_at__isnull=True,
            )
        )
        if not facilitators:
            raise ValidationError("Session must have at least one facilitator before publishing.")
        assignments = [
            {
                "kind": item.kind,
                "internal_user_id": item.internal_user_id,
                "external_display_name": item.external_display_name,
                "is_lead": item.is_lead,
            }
            for item in facilitators
        ]
        _validate_internal_facilitators(assignments, locked_users, actor=actor)
        conflicts = providers_with_schedule_conflicts(
            provider_ids=(
                item.internal_user_id
                for item in facilitators
                if item.kind == GroupSessionFacilitatorKind.INTERNAL
            ),
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            exclude_group_session_id=session.pk,
        )
        if conflicts:
            raise ValidationError(
                "A facilitator has an overlapping Appointment, published Fixed Slot, "
                "or Group Session."
            )
        student_conflicts = students_with_schedule_conflicts(
            student_ids=student_ids,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            exclude_group_session_id=session.pk,
        )
        if student_conflicts:
            raise ValidationError(
                "A registered Student has an overlapping Appointment or Group Session."
            )

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


def cancel_group_session(*, session_id: uuid.UUID, actor: User, reason: str) -> GroupSession:
    """Cancel a published group session and notify registered students."""
    if not reason.strip():
        raise ValidationError("Cancellation reason is required.")

    with transaction.atomic():
        session, _, _, _ = _lock_group_schedule_context(
            session_id=session_id,
            actor=actor,
        )
        require_group_session_access(
            actor=actor,
            session=session,
            permission="can_manage",
            lock_supervision=True,
        )
        if session.status != GroupSessionStatus.PUBLISHED:
            raise ValidationError("Only PUBLISHED sessions can be cancelled; withdraw a DRAFT.")

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

            create_notification_for_event(
                recipient=reg.student,
                event=NotificationEvent.GROUP_SESSION_CANCELLED,
                source_type="group_session",
                source_id=session.id,
                target_type=NotificationTargetType.GROUP_SESSION,
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


def withdraw_group_session(*, session_id: uuid.UUID, actor: User, reason: str = "") -> GroupSession:
    """Withdraw a DRAFT session into the existing CANCELLED lifecycle without deleting it."""

    with transaction.atomic():
        session, _, _, _ = _lock_group_schedule_context(
            session_id=session_id,
            actor=actor,
        )
        require_group_session_access(
            actor=actor,
            session=session,
            permission="can_manage",
            lock_supervision=True,
        )
        if session.status != GroupSessionStatus.DRAFT:
            raise ValidationError("Only DRAFT sessions can be withdrawn.")
        if session.registrations.filter(status=RegistrationStatus.REGISTERED).exists():
            raise ValidationError("A draft with active registrations cannot be withdrawn.")

        now = timezone.now()
        cleaned_reason = reason.strip()[:1000] or "Draft withdrawn by staff."
        session.status = GroupSessionStatus.CANCELLED
        session.cancelled_at = now
        session.cancellation_reason = cleaned_reason
        session.version += 1
        session.save(
            update_fields=["status", "cancelled_at", "cancellation_reason", "version", "updated_at"]
        )
        record_event(
            context=AuditContext.user(actor),
            action=GROUP_SESSION_WITHDRAWN,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.session",
            target_id=session.id,
            metadata={"title": session.title, "reason": cleaned_reason},
        )
        return session


def complete_group_session(
    *, session_id: uuid.UUID, actor: User, now: datetime | None = None
) -> GroupSession:
    """Mark a published group session as COMPLETED."""
    with transaction.atomic():
        session, _, _, _ = _lock_group_schedule_context(
            session_id=session_id,
            actor=actor,
        )
        require_group_session_access(
            actor=actor,
            session=session,
            permission="can_manage",
            lock_supervision=True,
        )
        if session.status != GroupSessionStatus.PUBLISHED:
            raise ValidationError("Only PUBLISHED sessions can be completed.")
        if session.ends_at > (now or timezone.now()):
            raise ValidationError("A Group Session cannot be completed before it has ended.")

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


def register_student(*, session_id: uuid.UUID, student: User) -> GroupSessionRegistration:
    """Register a student for a published group session with transactional capacity guard."""
    if not is_current_student(student):
        raise ValidationError(
            "Current Student lifecycle is required to register for a group session."
        )

    with transaction.atomic():
        snapshot = GroupSession.objects.filter(pk=session_id).only("service_id").first()
        if snapshot is None:
            raise ValidationError("Group session not found.")
        try:
            locked_users = lock_schedule_users(student.pk)
        except ValueError as exc:
            raise ValidationError("Current Student lifecycle is required to register.") from exc
        locked_student = locked_users[student.pk]
        if not is_current_student(locked_student):
            raise ValidationError(
                "Current Student lifecycle is required to register for a group session."
            )
        service = Service.objects.select_for_update().filter(pk=snapshot.service_id).first()
        session = (
            GroupSession.objects.select_for_update(of=("self",))
            .select_related("service")
            .filter(id=session_id, service_id=snapshot.service_id)
            .first()
        )
        if not session or service is None:
            raise ValidationError("Group session not found.")
        now = timezone.now()
        if session.status != GroupSessionStatus.PUBLISHED:
            raise ValidationError("Session is not open for registration.")
        if (
            not service.is_active
            or not service.booking_pathways.filter(code=BookingPathwayCode.GROUP_SESSION).exists()
        ):
            raise ValidationError(
                "This Service is not currently accepting group session registrations."
            )
        if not service_supports_delivery_mode(service, session.delivery_mode):
            raise ValidationError(
                "This Service is no longer accepting registrations for the session's delivery mode."
            )
        if session.starts_at <= now:
            raise ValidationError("This session has already commenced.")

        if session.reg_opens_at and session.reg_opens_at > now:
            opens_str = session.reg_opens_at.strftime("%b %d, %Y %I:%M %p")
            raise ValidationError(f"Registration has not opened yet. It opens on {opens_str}.")
        if session.reg_closes_at and session.reg_closes_at < now:
            raise ValidationError("Registration for this session has closed.")

        # Check existing registration
        existing = session.registrations.filter(
            student=student, status=RegistrationStatus.REGISTERED
        ).first()
        if existing:
            raise ValidationError("You are already registered for this session.")

        if student_schedule_conflict(
            student_id=locked_student.pk,
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            exclude_group_session_id=session.pk,
        ):
            raise ValidationError(
                "You already have an overlapping Appointment or registered Group Session."
            )

        active_count = session.registrations.filter(status=RegistrationStatus.REGISTERED).count()
        if active_count >= session.capacity:
            raise ValidationError("This session is full. Maximum participant capacity reached.")

        registration = GroupSessionRegistration.objects.create(
            group_session=session,
            student=locked_student,
            status=RegistrationStatus.REGISTERED,
            registered_at=now,
        )

        create_notification_for_event(
            recipient=locked_student,
            event=NotificationEvent.GROUP_SESSION_REGISTERED,
            source_type="group_session_registration",
            source_id=registration.id,
            target_type=NotificationTargetType.GROUP_SESSION,
            target_id=session.id,
        )

        record_event(
            context=AuditContext.user(locked_student),
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
        snapshot = GroupSession.objects.filter(pk=session_id).only("service_id").first()
        if snapshot is None:
            raise ValidationError("Active registration not found.")
        try:
            locked_student = lock_schedule_users(student.pk)[student.pk]
        except ValueError as exc:
            raise ValidationError("Active registration not found.") from exc
        Service.objects.select_for_update().filter(pk=snapshot.service_id).first()
        locked_session = (
            GroupSession.objects.select_for_update(of=("self",))
            .filter(pk=session_id, service_id=snapshot.service_id)
            .first()
        )
        if locked_session is None:
            raise ValidationError("Active registration not found.")
        registration = (
            GroupSessionRegistration.objects.select_for_update(of=("self",))
            .filter(
                group_session=locked_session,
                student=locked_student,
                status=RegistrationStatus.REGISTERED,
            )
            .select_related("group_session__service")
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

        create_notification_for_event(
            recipient=locked_student,
            event=NotificationEvent.GROUP_SESSION_REGISTRATION_CANCELLED,
            source_type="group_session_registration",
            source_id=registration.id,
            target_type=NotificationTargetType.GROUP_SESSION,
            target_id=session.id,
        )

        record_event(
            context=AuditContext.user(locked_student),
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
        session, _, _, _ = _lock_group_schedule_context(
            session_id=session_id,
            actor=actor,
        )
        access = require_group_session_access(
            actor=actor,
            session=session,
            permission="can_record_attendance",
            lock_supervision=True,
        )
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

            registration = (
                session.registrations.select_for_update(of=("self",))
                .filter(id=reg_id, status=RegistrationStatus.REGISTERED)
                .first()
            )
            if not registration:
                raise ValidationError("Active registration not found for this session.")

            if not access.can_manage and notes:
                raise ValidationError("Only session organizers may manage attendance notes.")

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
                update_fields = ["attended", "marked_by", "updated_at"]
                if access.can_manage:
                    attendance.notes = notes
                    update_fields.append("notes")
                attendance.save(update_fields=update_fields)

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
    with transaction.atomic():
        session, _, _, _ = _lock_group_schedule_context(
            session_id=session_id,
            actor=actor,
        )
        session = (
            GroupSession.objects.filter(pk=session.pk)
            .select_related("service", "organizer__role")
            .prefetch_related("facilitators", "registrations__student", "registrations__attendance")
            .first()
        )
        if session is None:
            raise ValidationError("Group session not found.")
        require_group_session_access(
            actor=actor,
            session=session,
            permission="can_export_roster",
            lock_supervision=True,
        )

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
            action=REPORT_EXPORT_RELEASED,
            outcome=AuditOutcome.SUCCESS,
            target_type="service.group.roster",
            target_id=session.id,
            metadata={"title": session.title},
        )

        return output.getvalue()


def get_group_session_metrics(
    *,
    actor: User,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    service_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Calculate operational reporting metrics for group sessions."""
    qs = scope_group_sessions(GroupSession.objects.all(), actor, permission="manage")
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

    active_capacity_qs = qs.filter(
        status__in=[GroupSessionStatus.PUBLISHED, GroupSessionStatus.COMPLETED]
    )
    total_capacity = sum(active_capacity_qs.values_list("capacity", flat=True)) or 0
    utilization_rate = (
        round((total_registrations / total_capacity) * 100, 1) if total_capacity > 0 else 0.0
    )

    # Attendance for active registrations
    attendances = GroupSessionAttendance.objects.filter(
        registration__group_session__in=qs,
        registration__status=RegistrationStatus.REGISTERED,
    )
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
