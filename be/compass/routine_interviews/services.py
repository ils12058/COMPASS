"""Transactional Routine Interview workflows and privacy/resource invariants."""

from __future__ import annotations

import hashlib
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.actions import (
    ROUTINE_INTERVIEW_CREATED,
    ROUTINE_INTERVIEW_EVALUATION_FINALIZED,
    ROUTINE_INTERVIEW_INTAKE_SUBMITTED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.counseling.services import (
    CounselingConfigurationConflict,
    get_counseling_service,
)
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    get_active_supported_form_revision,
)
from compass.inventory.services import (
    CurrentAcademicYearNotConfigured,
    InventoryConflict,
    require_current_submitted_inventory,
)
from compass.service_catalog.models import DeliveryMode
from compass.service_catalog.services import (
    provider_role_eligible,
    service_supports_delivery_mode,
)

from .models import RoutineConcern, RoutineInterview

ROUTINE_FORM_FAMILY_KEY = "routine_interview"
INTAKE_FIELDS = (
    "coping_with_college_challenges",
    "coping_remarks",
    "college_experience",
    "reason_for_choosing_institution",
    "difficulties_encountered",
    "stress_anxiety_causes",
    "stress_anxiety_management",
    "family_description",
    "concerns",
    "other_concern_specification",
    "concerns_explanation",
    "college_adjustment_and_peer_group",
    "academic_goals",
    "career_goals",
)
EVALUATION_FIELDS = (
    "academic_adjustment_rating",
    "physical_adjustment_rating",
    "social_adjustment_rating",
    "spiritual_adjustment_rating",
    "financial_adjustment_rating",
    "emotional_adjustment_rating",
    "other_adjustment",
    "special_concern",
    "recommendations",
)
RATING_FIELDS = EVALUATION_FIELDS[:6]
DIRECT_ENTRY_MODES = frozenset(
    {
        CounselingEntryMode.WALK_IN,
        CounselingEntryMode.CALLED_IN,
        CounselingEntryMode.REFERRED,
    }
)


class RoutineInterviewError(RuntimeError):
    pass


class RoutineInterviewNotFound(RoutineInterviewError):
    pass


class RoutineInterviewNotPermitted(RoutineInterviewError):
    pass


class InvalidRoutineInterviewInput(RoutineInterviewError):
    pass


class RoutineInterviewAppointmentInvalid(RoutineInterviewError):
    pass


class RoutineInterviewInventoryRequired(RoutineInterviewError):
    pass


class RoutineInterviewIntakeSubmitted(RoutineInterviewError):
    pass


class RoutineInterviewIntakeRequired(RoutineInterviewError):
    pass


class RoutineInterviewEvaluationFinalized(RoutineInterviewError):
    pass


class RoutineInterviewEncounterRequired(RoutineInterviewError):
    pass


class RoutineInterviewEncounterMismatch(RoutineInterviewError):
    pass


class RoutineInterviewCreationConflict(RoutineInterviewError):
    pass


class RoutineInterviewFormRevisionUnsupported(RoutineInterviewError):
    pass


def _queryset():
    return RoutineInterview.objects.select_related(
        "student",
        "student__role",
        "counselor",
        "counselor__role",
        "inventory",
        "inventory__academic_year",
        "appointment",
        "appointment__service",
        "counseling_encounter",
        "counseling_encounter__service",
        "form_revision",
        "form_revision__family",
        "created_by",
    )


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
        raise RoutineInterviewNotFound("A Routine Interview participant was not found.")
    return by_id


def _validate_student(student: User) -> None:
    if not student.is_active or student.role.code != "STUDENT":
        raise RoutineInterviewNotPermitted("An active Student account is required.")


def _validate_counselor(counselor: User) -> None:
    if not counselor.is_active or counselor.role.code != "COUNSELOR":
        raise RoutineInterviewNotPermitted("An active Counselor account is required.")


def _normalize_delivery_mode(value: str | DeliveryMode) -> str:
    normalized = value.value if isinstance(value, DeliveryMode) else value
    if normalized not in DeliveryMode.values:
        raise InvalidRoutineInterviewInput("delivery_mode must be IN_PERSON or ONLINE.")
    return str(normalized)


def _normalize_direct_entry_mode(value: str | CounselingEntryMode) -> str:
    normalized = value.value if isinstance(value, CounselingEntryMode) else value
    if normalized not in DIRECT_ENTRY_MODES:
        raise InvalidRoutineInterviewInput(
            "Direct Routine Interview entry_mode must be WALK_IN, CALLED_IN, or REFERRED."
        )
    return str(normalized)


def _submitted_inventory(student: User):
    try:
        return require_current_submitted_inventory(student)
    except CurrentAcademicYearNotConfigured:
        raise
    except InventoryConflict as exc:
        raise RoutineInterviewInventoryRequired(
            "A submitted Individual Inventory for the current Academic Year is required."
        ) from exc


def _optional_form_revision():
    try:
        return get_active_supported_form_revision(ROUTINE_FORM_FAMILY_KEY)
    except InstitutionalFormConflict as exc:
        raise RoutineInterviewFormRevisionUnsupported(
            "The active Routine Interview Form Revision is not supported by this COMPASS version."
        ) from exc


def _validate_counseling_service(*, service, counselor: User, delivery_mode: str) -> None:
    if service.code != "COUNSELING" or not service.is_active:
        raise RoutineInterviewAppointmentInvalid(
            "Routine Interview requires the active canonical COUNSELING Service."
        )
    if not provider_role_eligible(service, counselor):
        raise RoutineInterviewAppointmentInvalid(
            "The assigned provider is not eligible for the COUNSELING Service."
        )
    if not service_supports_delivery_mode(service, delivery_mode):
        raise RoutineInterviewAppointmentInvalid(
            "The COUNSELING Service does not support this delivery mode."
        )


def _safe_creation_metadata(item: RoutineInterview) -> dict[str, object]:
    revision = item.form_revision
    return {
        "entry_mode": item.entry_mode,
        "academic_year": item.inventory.academic_year.label,
        "appointment_id": str(item.appointment_id) if item.appointment_id else None,
        "form_revision_id": str(revision.pk) if revision is not None else None,
    }


def ensure_for_appointment(
    *,
    student: User,
    appointment_id: UUID,
    context: AuditContext,
) -> RoutineInterview:
    _validate_student(student)
    with transaction.atomic():
        appointment = (
            Appointment.objects.select_for_update()
            .select_related("student__role", "provider__role", "service")
            .filter(pk=appointment_id)
            .first()
        )
        if appointment is None or appointment.student_id != student.pk:
            raise RoutineInterviewAppointmentInvalid(
                "The requested Counseling Appointment is not available to this Student."
            )

        existing = RoutineInterview.objects.filter(appointment_id=appointment.pk).first()
        if existing is not None:
            if existing.student_id != student.pk:
                raise RoutineInterviewAppointmentInvalid(
                    "The Appointment is already bound to another Routine Interview."
                )
            return _queryset().get(pk=existing.pk)

        if appointment.status != AppointmentStatus.SCHEDULED:
            raise RoutineInterviewAppointmentInvalid("The Appointment must be SCHEDULED.")
        counselor = appointment.provider
        _validate_counselor(counselor)
        try:
            counseling_service = get_counseling_service(require_active=True, for_update=True)
        except CounselingConfigurationConflict as exc:
            raise RoutineInterviewAppointmentInvalid(str(exc)) from exc
        if appointment.service_id != counseling_service.pk:
            raise RoutineInterviewAppointmentInvalid(
                "The Appointment does not use the canonical COUNSELING Service."
            )
        _validate_counseling_service(
            service=counseling_service,
            counselor=counselor,
            delivery_mode=appointment.delivery_mode,
        )

        inventory = _submitted_inventory(student)
        revision = _optional_form_revision()
        try:
            item = RoutineInterview.objects.create(
                student=student,
                counselor=counselor,
                inventory=inventory,
                appointment=appointment,
                form_revision=revision,
                entry_mode=CounselingEntryMode.APPOINTMENT,
                delivery_mode=appointment.delivery_mode,
                created_by=student,
            )
        except IntegrityError:
            concurrent = RoutineInterview.objects.filter(appointment_id=appointment.pk).first()
            if concurrent is None:
                raise RoutineInterviewCreationConflict(
                    "The Routine Interview could not be created safely; retry the request."
                ) from None
            return _queryset().get(pk=concurrent.pk)

        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine_interviews.routineinterview",
            target_id=item.pk,
            metadata=_safe_creation_metadata(
                RoutineInterview.objects.select_related(
                    "inventory__academic_year", "form_revision"
                ).get(pk=item.pk)
            ),
        )
        return _queryset().get(pk=item.pk)


def _validate_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 255:
        raise InvalidRoutineInterviewInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    if value.strip() != value or not value.isprintable():
        raise InvalidRoutineInterviewInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    return value


def _creation_digest(*, actor_id: UUID, key: str) -> str:
    return hashlib.sha256(f"{actor_id}\0{key}".encode()).hexdigest()


def create_direct(
    *,
    counselor: User,
    student_id: UUID,
    entry_mode: str,
    delivery_mode: str,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> RoutineInterview:
    _validate_counselor(counselor)
    normalized_entry = _normalize_direct_entry_mode(entry_mode)
    normalized_delivery = _normalize_delivery_mode(delivery_mode)
    key = _validate_idempotency_key(idempotency_key)
    if len(request_fingerprint) != 64 or any(
        char not in "0123456789abcdef" for char in request_fingerprint
    ):
        raise InvalidRoutineInterviewInput("The direct-create request fingerprint is invalid.")
    digest = _creation_digest(actor_id=counselor.pk, key=key)

    with transaction.atomic():
        existing = (
            RoutineInterview.objects.select_for_update()
            .filter(direct_creation_key_digest=digest)
            .first()
        )
        if existing is not None:
            if existing.direct_request_fingerprint != request_fingerprint:
                raise RoutineInterviewCreationConflict(
                    "The Idempotency-Key was already used for a different Routine Interview request."
                )
            return _queryset().get(pk=existing.pk)

        locked = _lock_users(counselor.pk, student_id)
        student = locked[student_id]
        locked_counselor = locked[counselor.pk]
        _validate_student(student)
        _validate_counselor(locked_counselor)

        try:
            service = get_counseling_service(require_active=True, for_update=True)
        except CounselingConfigurationConflict as exc:
            raise RoutineInterviewAppointmentInvalid(str(exc)) from exc
        _validate_counseling_service(
            service=service,
            counselor=locked_counselor,
            delivery_mode=normalized_delivery,
        )
        inventory = _submitted_inventory(student)
        revision = _optional_form_revision()

        try:
            item = RoutineInterview.objects.create(
                student=student,
                counselor=locked_counselor,
                inventory=inventory,
                appointment=None,
                form_revision=revision,
                entry_mode=normalized_entry,
                delivery_mode=normalized_delivery,
                created_by=locked_counselor,
                direct_creation_key_digest=digest,
                direct_request_fingerprint=request_fingerprint,
            )
        except IntegrityError:
            concurrent = RoutineInterview.objects.filter(direct_creation_key_digest=digest).first()
            if concurrent is None:
                raise RoutineInterviewCreationConflict(
                    "The Routine Interview could not be created safely; retry the request."
                ) from None
            if concurrent.direct_request_fingerprint != request_fingerprint:
                raise RoutineInterviewCreationConflict(
                    "The Idempotency-Key was already used for a different Routine Interview request."
                )
            return _queryset().get(pk=concurrent.pk)

        item_for_audit = RoutineInterview.objects.select_related(
            "inventory__academic_year", "form_revision"
        ).get(pk=item.pk)
        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine_interviews.routineinterview",
            target_id=item.pk,
            metadata=_safe_creation_metadata(item_for_audit),
        )
        return _queryset().get(pk=item.pk)


def list_mine(student: User) -> tuple[RoutineInterview, ...]:
    _validate_student(student)
    return tuple(_queryset().filter(student_id=student.pk).order_by("-created_at", "id"))


def get_mine(*, student: User, routine_interview_id: UUID) -> RoutineInterview:
    _validate_student(student)
    item = _queryset().filter(pk=routine_interview_id, student_id=student.pk).first()
    if item is None:
        raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
    return item


def get_assigned(*, counselor: User, routine_interview_id: UUID) -> RoutineInterview:
    _validate_counselor(counselor)
    item = _queryset().filter(pk=routine_interview_id, counselor_id=counselor.pk).first()
    if item is None:
        raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
    return item


def _normalize_concerns(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidRoutineInterviewInput("concerns must be a list of source-backed values.")
    allowed = set(RoutineConcern.values)
    normalized: list[str] = []
    for value in raw:
        candidate = value.value if isinstance(value, RoutineConcern) else str(value)
        if candidate not in allowed:
            raise InvalidRoutineInterviewInput("concerns contains an unsupported source value.")
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _validate_intake_submission(item: RoutineInterview) -> None:
    if RoutineConcern.OTHER in item.concerns and not item.other_concern_specification.strip():
        raise InvalidRoutineInterviewInput(
            "other_concern_specification is required when OTHER concern is selected."
        )
    meaningful_text = any(
        getattr(item, field).strip()
        for field in INTAKE_FIELDS
        if field not in {"concerns", "other_concern_specification"}
    )
    if not meaningful_text and not item.concerns and not item.other_concern_specification.strip():
        raise InvalidRoutineInterviewInput(
            "At least one Student Intake response or concern is required before submission."
        )


def replace_my_intake(
    *,
    student: User,
    routine_interview_id: UUID,
    values: dict[str, object],
) -> RoutineInterview:
    _validate_student(student)
    unsupported = set(values) - set(INTAKE_FIELDS)
    if unsupported:
        raise InvalidRoutineInterviewInput("The Student Intake update contains unsupported fields.")

    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update()
            .filter(pk=routine_interview_id, student_id=student.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        if item.intake_submitted_at is not None:
            raise RoutineInterviewIntakeSubmitted("A submitted Student Intake is locked.")

        for field in INTAKE_FIELDS:
            if field not in values:
                continue
            if field == "concerns":
                item.concerns = _normalize_concerns(values[field])
            else:
                setattr(item, field, values[field])
        if RoutineConcern.OTHER not in item.concerns:
            item.other_concern_specification = ""

        try:
            item.full_clean(
                exclude=(
                    "student",
                    "counselor",
                    "inventory",
                    "appointment",
                    "counseling_encounter",
                    "form_revision",
                    "created_by",
                )
            )
        except ValidationError as exc:
            raise InvalidRoutineInterviewInput(
                "The Student Intake contains invalid values."
            ) from exc
        item.save(update_fields=[*INTAKE_FIELDS, "updated_at"])
        return _queryset().get(pk=item.pk)


def submit_my_intake(
    *,
    student: User,
    routine_interview_id: UUID,
    context: AuditContext,
) -> RoutineInterview:
    _validate_student(student)
    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update()
            .select_related("inventory__academic_year")
            .filter(pk=routine_interview_id, student_id=student.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        if item.intake_submitted_at is not None:
            return _queryset().get(pk=item.pk)
        if item.inventory.student_id != student.pk or item.inventory.submitted_at is None:
            raise RoutineInterviewInventoryRequired(
                "The bound submitted Individual Inventory is inconsistent."
            )
        _validate_intake_submission(item)
        item.intake_submitted_at = timezone.now()
        item.save(update_fields=["intake_submitted_at", "updated_at"])
        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_INTAKE_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine_interviews.routineinterview",
            target_id=item.pk,
            metadata={
                "entry_mode": item.entry_mode,
                "academic_year": item.inventory.academic_year.label,
                "appointment_id": str(item.appointment_id) if item.appointment_id else None,
            },
        )
        return _queryset().get(pk=item.pk)


def _validate_evaluation_values(item: RoutineInterview) -> None:
    for field in RATING_FIELDS:
        value = getattr(item, field)
        if value is not None and (type(value) is not int or not 1 <= value <= 10):
            raise InvalidRoutineInterviewInput(f"{field} must be between 1 and 10 when supplied.")


def replace_assigned_evaluation(
    *,
    counselor: User,
    routine_interview_id: UUID,
    values: dict[str, object],
) -> RoutineInterview:
    _validate_counselor(counselor)
    unsupported = set(values) - set(EVALUATION_FIELDS)
    if unsupported:
        raise InvalidRoutineInterviewInput(
            "The Counselor Evaluation update contains unsupported fields."
        )

    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update()
            .filter(pk=routine_interview_id, counselor_id=counselor.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        if item.intake_submitted_at is None:
            raise RoutineInterviewIntakeRequired(
                "Student Intake must be submitted before Counselor Evaluation can be saved."
            )
        if item.evaluation_finalized_at is not None:
            raise RoutineInterviewEvaluationFinalized(
                "The Counselor Evaluation is finalized and locked."
            )
        for field in EVALUATION_FIELDS:
            if field in values:
                setattr(item, field, values[field])
        _validate_evaluation_values(item)
        try:
            item.full_clean(
                exclude=(
                    "student",
                    "counselor",
                    "inventory",
                    "appointment",
                    "counseling_encounter",
                    "form_revision",
                    "created_by",
                )
            )
        except ValidationError as exc:
            raise InvalidRoutineInterviewInput(
                "The Counselor Evaluation contains invalid values."
            ) from exc
        item.save(update_fields=[*EVALUATION_FIELDS, "updated_at"])
        return _queryset().get(pk=item.pk)


def _validate_encounter_match(*, item: RoutineInterview, encounter: CounselingEncounter) -> None:
    if encounter.student_id != item.student_id:
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter belongs to another Student."
        )
    if encounter.counselor_id != item.counselor_id:
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter belongs to another Counselor."
        )
    if encounter.service.code != "COUNSELING":
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter does not use the canonical COUNSELING Service."
        )
    if encounter.delivery_mode != item.delivery_mode:
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter delivery mode does not match the Routine Interview."
        )
    if encounter.ended_at > timezone.now():
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter must represent a completed interaction."
        )

    if item.appointment_id is not None:
        if encounter.entry_mode != CounselingEntryMode.APPOINTMENT:
            raise RoutineInterviewEncounterMismatch(
                "An Appointment-backed Routine Interview requires an APPOINTMENT Encounter."
            )
        if encounter.appointment_id != item.appointment_id:
            raise RoutineInterviewEncounterMismatch(
                "The Counseling Encounter Appointment does not match the Routine Interview."
            )
    else:
        if encounter.appointment_id is not None:
            raise RoutineInterviewEncounterMismatch(
                "A direct Routine Interview cannot link an Appointment-backed Encounter."
            )
        if encounter.entry_mode != item.entry_mode:
            raise RoutineInterviewEncounterMismatch(
                "The Counseling Encounter entry mode does not match the Routine Interview."
            )


def finalize_assigned_evaluation(
    *,
    counselor: User,
    routine_interview_id: UUID,
    encounter_id: UUID | None,
    context: AuditContext,
) -> RoutineInterview:
    _validate_counselor(counselor)
    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update()
            .select_related("inventory__academic_year")
            .filter(pk=routine_interview_id, counselor_id=counselor.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        if item.intake_submitted_at is None:
            raise RoutineInterviewIntakeRequired(
                "Student Intake must be submitted before Counselor Evaluation can be finalized."
            )
        if item.evaluation_finalized_at is not None:
            return _queryset().get(pk=item.pk)

        _validate_evaluation_values(item)
        if item.appointment_id is not None:
            encounter = (
                CounselingEncounter.objects.select_for_update()
                .select_related("service")
                .filter(appointment_id=item.appointment_id)
                .first()
            )
            if encounter is None:
                raise RoutineInterviewEncounterRequired(
                    "A completed Counseling Encounter for this Appointment is required."
                )
            if encounter_id is not None and encounter.pk != encounter_id:
                raise RoutineInterviewEncounterMismatch(
                    "The supplied Counseling Encounter does not match the Appointment."
                )
        else:
            if encounter_id is None:
                raise RoutineInterviewEncounterRequired(
                    "encounter_id is required for a direct Routine Interview."
                )
            encounter = (
                CounselingEncounter.objects.select_for_update()
                .select_related("service")
                .filter(pk=encounter_id)
                .first()
            )
            if encounter is None:
                raise RoutineInterviewEncounterRequired(
                    "The supplied Counseling Encounter was not found."
                )

        _validate_encounter_match(item=item, encounter=encounter)
        try:
            item.counseling_encounter = encounter
            item.evaluation_finalized_at = timezone.now()
            item.save(
                update_fields=[
                    "counseling_encounter",
                    "evaluation_finalized_at",
                    "updated_at",
                ]
            )
        except IntegrityError as exc:
            raise RoutineInterviewEncounterMismatch(
                "The Counseling Encounter is already linked to another Routine Interview."
            ) from exc

        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_EVALUATION_FINALIZED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine_interviews.routineinterview",
            target_id=item.pk,
            metadata={
                "entry_mode": item.entry_mode,
                "academic_year": item.inventory.academic_year.label,
                "appointment_id": str(item.appointment_id) if item.appointment_id else None,
                "encounter_id": str(encounter.pk),
            },
        )
        return _queryset().get(pk=item.pk)
