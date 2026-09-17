"""Transactional Counseling encounter workflows and assigned-resource access rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.actions import COUNSELING_ENCOUNTER_CREATED, COUNSELING_ENCOUNTER_UPDATED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.models import DeliveryMode, Service
from compass.service_catalog.services import (
    provider_role_eligible,
    service_supports_delivery_mode,
)

from .models import CounselingEncounter, CounselingEntryMode

COUNSELING_SERVICE_CODE = "COUNSELING"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_STUDENT_SEARCH_LENGTH = 160


class CounselingError(RuntimeError):
    pass


class CounselingNotFound(CounselingError):
    pass


class InvalidCounselingInput(CounselingError):
    pass


class CounselingConfigurationConflict(CounselingError):
    pass


class CounselingNotPermitted(CounselingError):
    pass


class CounselingAppointmentInvalid(CounselingError):
    pass


class CounselingAppointmentAlreadyUsed(CounselingError):
    pass


class CounselingInvalidTime(CounselingError):
    pass


@dataclass(frozen=True, slots=True)
class CounselingPage:
    items: tuple[CounselingEncounter, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class StudentPage:
    items: tuple[User, ...]
    page: int
    page_size: int
    has_next: bool


def _institution_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIME_ZONE)
    except ZoneInfoNotFoundError as exc:
        raise CounselingConfigurationConflict(
            "The configured institutional timezone is unavailable."
        ) from exc


def _normalize_entry_mode(value: str | CounselingEntryMode) -> str:
    normalized = value.value if isinstance(value, CounselingEntryMode) else value
    if normalized not in CounselingEntryMode.values:
        raise InvalidCounselingInput(
            "entry_mode must be APPOINTMENT, WALK_IN, CALLED_IN, or REFERRED"
        )
    return str(normalized)


def _normalize_delivery_mode(value: str | DeliveryMode) -> str:
    normalized = value.value if isinstance(value, DeliveryMode) else value
    if normalized not in DeliveryMode.values:
        raise InvalidCounselingInput("delivery_mode must be IN_PERSON or ONLINE")
    return str(normalized)


def _normalize_actual_times(
    started_at: datetime,
    ended_at: datetime,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    if not isinstance(started_at, datetime) or not isinstance(ended_at, datetime):
        raise CounselingInvalidTime("started_at and ended_at must be datetimes")
    if timezone.is_naive(started_at) or timezone.is_naive(ended_at):
        raise CounselingInvalidTime("Counseling encounter times must be timezone-aware.")
    zone = _institution_zone()
    normalized_start = started_at.astimezone(zone)
    normalized_end = ended_at.astimezone(zone)
    if normalized_start >= normalized_end:
        raise CounselingInvalidTime("started_at must be earlier than ended_at.")
    current = (now or timezone.now()).astimezone(zone)
    if normalized_end > current:
        raise CounselingInvalidTime("ended_at must not be in the future.")
    return normalized_start, normalized_end


def _validate_page(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidCounselingInput("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidCounselingInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _encounter_queryset():
    return CounselingEncounter.objects.select_related(
        "student",
        "student__role",
        "counselor",
        "counselor__role",
        "service",
        "appointment",
        "created_by",
    )


def get_counseling_service(*, require_active: bool = True, for_update: bool = False) -> Service:
    queryset = Service.objects
    if for_update:
        queryset = queryset.select_for_update()
    service = queryset.filter(code=COUNSELING_SERVICE_CODE).first()
    if service is None:
        raise CounselingConfigurationConflict(
            "The canonical COUNSELING Service has not been configured."
        )
    if require_active and not service.is_active:
        raise CounselingConfigurationConflict("The canonical COUNSELING Service is inactive.")
    return service


def _lock_users(*user_ids: UUID) -> dict[UUID, User]:
    unique_ids = sorted(set(user_ids), key=str)
    rows = list(
        User.objects.select_for_update()
        .select_related("role")
        .filter(pk__in=unique_ids)
        .order_by("pk")
    )
    by_id = {row.pk: row for row in rows}
    if len(by_id) != len(unique_ids):
        raise CounselingNotPermitted("A Counseling participant no longer exists.")
    return by_id


def _validate_active_counselor(user: User) -> None:
    if not user.is_active or user.role.code != "COUNSELOR":
        raise CounselingNotPermitted("An active Counselor account is required.")


def _validate_active_student(user: User) -> None:
    if not user.is_active or user.role.code != "STUDENT":
        raise CounselingNotPermitted("The selected account must be an active Student.")


def _validate_service_for_new_encounter(
    *, service: Service, counselor: User, delivery_mode: str
) -> None:
    if service.code != COUNSELING_SERVICE_CODE or not service.is_active:
        raise CounselingConfigurationConflict("The canonical COUNSELING Service is not active.")
    if not provider_role_eligible(service, counselor):
        raise CounselingNotPermitted("The COUNSELING Service does not permit this Counselor.")
    if not service_supports_delivery_mode(service, delivery_mode):
        raise CounselingNotPermitted(
            "The COUNSELING Service does not support the requested delivery mode."
        )


def _validate_appointment_link(
    *,
    appointment: Appointment,
    counselor_id: UUID,
    student_id: UUID,
    service_id: UUID,
    delivery_mode: str,
    require_unused_by: UUID | None = None,
) -> None:
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise CounselingAppointmentInvalid("The linked Appointment must be SCHEDULED.")
    if appointment.provider_id != counselor_id:
        raise CounselingAppointmentInvalid(
            "The linked Appointment is assigned to a different Counselor."
        )
    if appointment.student_id != student_id:
        raise CounselingAppointmentInvalid(
            "The linked Appointment belongs to a different Student."
        )
    if appointment.service_id != service_id:
        raise CounselingAppointmentInvalid(
            "The linked Appointment does not use the canonical COUNSELING Service."
        )
    if appointment.delivery_mode != delivery_mode:
        raise CounselingAppointmentInvalid(
            "The linked Appointment delivery mode does not match the Encounter."
        )
    existing = CounselingEncounter.objects.filter(appointment_id=appointment.pk)
    if require_unused_by is not None:
        existing = existing.exclude(pk=require_unused_by)
    if existing.exists():
        raise CounselingAppointmentAlreadyUsed(
            "The linked Appointment already has a Counseling Encounter."
        )


def _create_row(
    *,
    student: User,
    counselor: User,
    service: Service,
    appointment: Appointment | None,
    entry_mode: str,
    delivery_mode: str,
    started_at: datetime,
    ended_at: datetime,
    context: AuditContext,
) -> CounselingEncounter:
    try:
        with transaction.atomic():
            encounter = CounselingEncounter.objects.create(
                student=student,
                counselor=counselor,
                service=service,
                appointment=appointment,
                entry_mode=entry_mode,
                delivery_mode=delivery_mode,
                started_at=started_at,
                ended_at=ended_at,
                created_by=counselor,
            )
    except IntegrityError as exc:
        if appointment is not None:
            raise CounselingAppointmentAlreadyUsed(
                "The linked Appointment already has a Counseling Encounter."
            ) from exc
        raise
    record_event(
        context=context,
        action=COUNSELING_ENCOUNTER_CREATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.encounter",
        target_id=encounter.pk,
        metadata={
            "entry_mode": entry_mode,
            "delivery_mode": delivery_mode,
            "appointment_id": str(appointment.pk) if appointment is not None else None,
        },
    )
    return encounter


def create_encounter(
    *,
    counselor: User,
    entry_mode: str,
    started_at: datetime,
    ended_at: datetime,
    student_id: UUID | None = None,
    delivery_mode: str | None = None,
    appointment_id: UUID | None = None,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingEncounter:
    normalized_entry = _normalize_entry_mode(entry_mode)
    normalized_start, normalized_end = _normalize_actual_times(started_at, ended_at, now=now)

    if appointment_id is not None:
        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().filter(pk=appointment_id).first()
            if appointment is None:
                raise CounselingAppointmentInvalid("The linked Appointment was not found.")
            locked = _lock_users(counselor.pk, appointment.student_id)
            locked_counselor = locked[counselor.pk]
            locked_student = locked[appointment.student_id]
            _validate_active_counselor(locked_counselor)
            _validate_active_student(locked_student)
            service = get_counseling_service(require_active=True, for_update=True)
            normalized_mode = _normalize_delivery_mode(appointment.delivery_mode)
            _validate_service_for_new_encounter(
                service=service,
                counselor=locked_counselor,
                delivery_mode=normalized_mode,
            )
            if appointment.service_id != service.pk:
                raise CounselingAppointmentInvalid(
                    "The linked Appointment does not use the canonical COUNSELING Service."
                )
            if student_id is not None and student_id != appointment.student_id:
                raise CounselingAppointmentInvalid(
                    "student_id does not match the linked Appointment."
                )
            if delivery_mode is not None:
                supplied_mode = _normalize_delivery_mode(delivery_mode)
                if supplied_mode != normalized_mode:
                    raise CounselingAppointmentInvalid(
                        "delivery_mode does not match the linked Appointment."
                    )
            _validate_appointment_link(
                appointment=appointment,
                counselor_id=locked_counselor.pk,
                student_id=locked_student.pk,
                service_id=service.pk,
                delivery_mode=normalized_mode,
            )
            encounter = _create_row(
                student=locked_student,
                counselor=locked_counselor,
                service=service,
                appointment=appointment,
                entry_mode=normalized_entry,
                delivery_mode=normalized_mode,
                started_at=normalized_start,
                ended_at=normalized_end,
                context=context,
            )
        return _encounter_queryset().get(pk=encounter.pk)

    if normalized_entry == CounselingEntryMode.APPOINTMENT:
        raise CounselingAppointmentInvalid(
            "entry_mode APPOINTMENT requires an appointment_id."
        )
    if student_id is None:
        raise InvalidCounselingInput("student_id is required without an Appointment.")
    if delivery_mode is None:
        raise InvalidCounselingInput("delivery_mode is required without an Appointment.")
    normalized_mode = _normalize_delivery_mode(delivery_mode)

    with transaction.atomic():
        locked = _lock_users(counselor.pk, student_id)
        locked_counselor = locked[counselor.pk]
        locked_student = locked[student_id]
        _validate_active_counselor(locked_counselor)
        _validate_active_student(locked_student)
        service = get_counseling_service(require_active=True, for_update=True)
        _validate_service_for_new_encounter(
            service=service,
            counselor=locked_counselor,
            delivery_mode=normalized_mode,
        )
        encounter = _create_row(
            student=locked_student,
            counselor=locked_counselor,
            service=service,
            appointment=None,
            entry_mode=normalized_entry,
            delivery_mode=normalized_mode,
            started_at=normalized_start,
            ended_at=normalized_end,
            context=context,
        )
    return _encounter_queryset().get(pk=encounter.pk)


def _date_bounds(
    from_date: date | None, to_date: date | None
) -> tuple[datetime | None, datetime | None]:
    if from_date is not None and not isinstance(from_date, date):
        raise InvalidCounselingInput("from_date must be a date")
    if to_date is not None and not isinstance(to_date, date):
        raise InvalidCounselingInput("to_date must be a date")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise InvalidCounselingInput("from_date must not be after to_date")
    zone = _institution_zone()
    start = datetime.combine(from_date, time.min, tzinfo=zone) if from_date else None
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=zone) if to_date else None
    return start, end


def list_my_encounters(
    *,
    counselor: User,
    entry_mode: str | None = None,
    delivery_mode: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    student_id: UUID | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CounselingPage:
    page, page_size = _validate_page(page, page_size)
    qs = _encounter_queryset().filter(counselor_id=counselor.pk)
    if entry_mode is not None:
        qs = qs.filter(entry_mode=_normalize_entry_mode(entry_mode))
    if delivery_mode is not None:
        qs = qs.filter(delivery_mode=_normalize_delivery_mode(delivery_mode))
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    start, end = _date_bounds(from_date, to_date)
    if start is not None:
        qs = qs.filter(started_at__gte=start)
    if end is not None:
        qs = qs.filter(started_at__lt=end)
    offset = (page - 1) * page_size
    rows = list(qs.order_by("-started_at", "id")[offset : offset + page_size + 1])
    return CounselingPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def get_encounter_for_actor(*, encounter_id: UUID, actor: User) -> CounselingEncounter:
    item = _encounter_queryset().filter(pk=encounter_id, counselor_id=actor.pk).first()
    if item is None:
        raise CounselingNotFound("The requested Counseling Encounter was not found.")
    if not actor.is_active or actor.role.code != "COUNSELOR":
        raise CounselingNotFound("The requested Counseling Encounter was not found.")
    return item


def list_students(
    *, search: str | None = None, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
) -> StudentPage:
    page, page_size = _validate_page(page, page_size)
    qs = User.objects.filter(is_active=True, role__code="STUDENT").select_related("role")
    if search and search.strip():
        term = search.strip()[:MAX_STUDENT_SEARCH_LENGTH]
        qs = qs.filter(
            Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
        )
    qs = qs.order_by("last_name", "first_name", "middle_name", "id")
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return StudentPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def update_encounter(
    *,
    encounter_id: UUID,
    counselor: User,
    changes: dict[str, object],
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingEncounter:
    allowed = {"entry_mode", "appointment_id", "delivery_mode", "started_at", "ended_at"}
    unknown = set(changes) - allowed
    if unknown:
        raise InvalidCounselingInput(
            "Unsupported Counseling correction fields: " + ", ".join(sorted(unknown))
        )

    with transaction.atomic():
        item = CounselingEncounter.objects.select_for_update().filter(pk=encounter_id).first()
        if item is None or item.counselor_id != counselor.pk:
            raise CounselingNotFound("The requested Counseling Encounter was not found.")
        locked_actor = _lock_users(counselor.pk)[counselor.pk]
        _validate_active_counselor(locked_actor)

        next_entry = (
            _normalize_entry_mode(changes["entry_mode"])
            if "entry_mode" in changes
            else item.entry_mode
        )
        next_mode = (
            _normalize_delivery_mode(changes["delivery_mode"])
            if "delivery_mode" in changes and changes["delivery_mode"] is not None
            else item.delivery_mode
        )
        next_started = changes.get("started_at", item.started_at)
        next_ended = changes.get("ended_at", item.ended_at)
        normalized_start, normalized_end = _normalize_actual_times(
            next_started,
            next_ended,
            now=now,
        )

        if "appointment_id" in changes:
            proposed_appointment_id = changes["appointment_id"]
            if proposed_appointment_id is not None and not isinstance(proposed_appointment_id, UUID):
                raise InvalidCounselingInput("appointment_id must be a UUID or null")
        else:
            proposed_appointment_id = item.appointment_id

        appointment_ids = {
            appointment_id
            for appointment_id in (item.appointment_id, proposed_appointment_id)
            if appointment_id is not None
        }
        appointments = {
            row.pk: row
            for row in Appointment.objects.select_for_update()
            .filter(pk__in=sorted(appointment_ids, key=str))
            .order_by("pk")
        }
        if proposed_appointment_id is not None and proposed_appointment_id not in appointments:
            raise CounselingAppointmentInvalid("The linked Appointment was not found.")

        service = Service.objects.select_for_update().filter(pk=item.service_id).first()
        if service is None or service.code != COUNSELING_SERVICE_CODE:
            raise CounselingConfigurationConflict(
                "The Encounter is not bound to the canonical COUNSELING Service."
            )

        proposed_appointment = (
            appointments.get(proposed_appointment_id)
            if proposed_appointment_id is not None
            else None
        )
        if proposed_appointment is None:
            if next_entry == CounselingEntryMode.APPOINTMENT:
                raise CounselingAppointmentInvalid(
                    "entry_mode APPOINTMENT requires an Appointment link."
                )
            if "delivery_mode" in changes and not service_supports_delivery_mode(service, next_mode):
                raise CounselingNotPermitted(
                    "The COUNSELING Service does not support the corrected delivery mode."
                )
        else:
            _validate_appointment_link(
                appointment=proposed_appointment,
                counselor_id=item.counselor_id,
                student_id=item.student_id,
                service_id=item.service_id,
                delivery_mode=next_mode,
                require_unused_by=item.pk,
            )

        changed_fields: list[str] = []
        scalar_changes = {
            "entry_mode": next_entry,
            "delivery_mode": next_mode,
            "started_at": normalized_start,
            "ended_at": normalized_end,
            "appointment_id": proposed_appointment_id,
        }
        for field, value in scalar_changes.items():
            if getattr(item, field) != value:
                setattr(item, field, value)
                changed_fields.append(field)

        if not changed_fields:
            return _encounter_queryset().get(pk=item.pk)

        item.save(update_fields=[*changed_fields, "updated_at"])
        record_event(
            context=context,
            action=COUNSELING_ENCOUNTER_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.encounter",
            target_id=item.pk,
            metadata={"changed_fields": sorted(changed_fields)},
        )
    return _encounter_queryset().get(pk=item.pk)
