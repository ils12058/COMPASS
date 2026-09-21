"""Exit Interview draft, submission, history, and correction lifecycle services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.profiles import get_person_profile_context
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    EXIT_INTERVIEW_CREATED,
    EXIT_INTERVIEW_REOPENED,
    EXIT_INTERVIEW_RESUBMITTED,
    EXIT_INTERVIEW_SUBMITTED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.inventory.services import (
    CurrentAcademicYearNotConfigured,
    InventoryConflict,
    require_current_submitted_inventory,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.academic_years import AcademicYearConflict, require_current_academic_year

from .models import (
    CareerMode,
    CollegeFeedbackItem,
    DelayReason,
    ExitInterview,
    ExitInterviewCollegeFeedbackRating,
    ExitInterviewReopenEvent,
    ExitInterviewSelfAssessmentRating,
    ExitInterviewStatus,
    ProgramCompletion,
    SelfAssessmentItem,
    SignificantLearningExperience,
    StudyCareerChoice,
    WorkCareerChoice,
)

MAX_ADDRESS_LENGTH = 2000
MAX_COMMENT_LENGTH = 4000
MAX_OTHER_LENGTH = 1000
MAX_REOPEN_REASON_LENGTH = 1000
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SEARCH_LENGTH = 160

ROOT_EDITABLE_FIELDS = frozenset(
    {
        "student_name_snapshot",
        "age_snapshot",
        "civil_status_snapshot",
        "course_snapshot",
        "major_snapshot",
        "email_snapshot",
        "home_address_snapshot",
        "contact_number_snapshot",
        "program_completion",
        "extra_terms_count",
        "delay_reasons",
        "delay_other",
        "significant_learning_experiences",
        "significant_learning_other",
        "career_modes",
        "work_choices",
        "study_choices",
        "dean_comments",
        "program_chair_comments",
        "faculty_comments",
        "curriculum_comments",
        "guidance_counselor_comments",
        "office_staff_comments",
        "facilities_comments",
        "suggestions_recommendations",
    }
)
COLLECTION_FIELDS = frozenset({"self_assessment_ratings", "college_feedback_ratings"})


class ExitInterviewError(RuntimeError):
    pass


class ExitInterviewNotFound(ExitInterviewError):
    pass


class ExitInterviewConflict(ExitInterviewError):
    pass


class ExitInterviewNotPermitted(ExitInterviewError):
    pass


class ExitInterviewInventoryRequired(ExitInterviewError):
    pass


class ExitInterviewCurrentStudentRequired(ExitInterviewError):
    pass


class ExitInterviewCurrentAcademicYearNotConfigured(ExitInterviewError):
    pass


class InvalidExitInterviewInput(ExitInterviewError):
    pass


@dataclass(frozen=True, slots=True)
class ExitInterviewPage:
    items: tuple[ExitInterview, ...]
    page: int
    page_size: int
    has_next: bool


def _queryset():
    return ExitInterview.objects.select_related(
        "student",
        "student__role",
        "academic_year",
        "inventory",
        "inventory__academic_year",
    ).prefetch_related(
        "self_assessment_ratings",
        "college_feedback_ratings",
        "reopen_events",
        "reopen_events__reopened_by",
    )


def _validate_student(student: User) -> None:
    if not getattr(student, "pk", None) or not student.is_active or student.role.code != "STUDENT":
        raise ExitInterviewNotPermitted(
            "Only an active Student may use Exit Interview self-service."
        )


def _validate_head(actor: User, capability: str) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability(capability)
    ):
        raise ExitInterviewNotPermitted("Head Guidance Exit Interview authority is required.")


def _current_year():
    try:
        return require_current_academic_year()
    except AcademicYearConflict as exc:
        raise ExitInterviewCurrentAcademicYearNotConfigured(str(exc)) from exc


def _require_submitted_current_inventory(student: User):
    try:
        return require_current_submitted_inventory(student)
    except CurrentAcademicYearNotConfigured as exc:
        raise ExitInterviewCurrentAcademicYearNotConfigured(str(exc)) from exc
    except InventoryConflict as exc:
        raise ExitInterviewInventoryRequired(str(exc)) from exc


def _age_on(date_of_birth: date | None, reference_date: date) -> int | None:
    if date_of_birth is None:
        return None
    if date_of_birth > reference_date:
        raise InvalidExitInterviewInput("The current profile date_of_birth is in the future.")
    years = reference_date.year - date_of_birth.year
    before_birthday = (reference_date.month, reference_date.day) < (
        date_of_birth.month,
        date_of_birth.day,
    )
    return years - int(before_birthday)


def _clean_text(value: object, field_name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidExitInterviewInput(f"{field_name} must be text.")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise InvalidExitInterviewInput(f"{field_name} is too long.")
    return cleaned


def _normalize_choice_list(
    raw: object,
    *,
    allowed: set[str],
    field_name: str,
) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidExitInterviewInput(f"{field_name} must be a list.")
    normalized: list[str] = []
    for value in raw:
        candidate = value.value if hasattr(value, "value") else str(value)
        if candidate not in allowed:
            raise InvalidExitInterviewInput(f"{field_name} contains an unsupported source value.")
        if candidate in normalized:
            raise InvalidExitInterviewInput(f"{field_name} must not contain duplicate values.")
        normalized.append(candidate)
    return normalized


def _normalize_age(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 150:
        raise InvalidExitInterviewInput("age must be between 0 and 150 when supplied.")
    return value


def _normalize_extra_terms(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 1:
        raise InvalidExitInterviewInput(
            "extra_terms_count must be a positive integer when supplied."
        )
    return value


def _normalize_program_completion(value: object) -> str:
    if value in {None, ""}:
        return ""
    candidate = value.value if hasattr(value, "value") else str(value)
    if candidate not in ProgramCompletion.values:
        raise InvalidExitInterviewInput("program_completion is not source-backed.")
    return candidate


def _normalized_root(values: dict[str, object]) -> dict[str, object]:
    allowed = ROOT_EDITABLE_FIELDS | COLLECTION_FIELDS
    unsupported = set(values) - allowed
    if unsupported:
        raise InvalidExitInterviewInput("The Exit Interview update contains unsupported fields.")

    normalized: dict[str, object] = {
        "student_name_snapshot": _clean_text(
            values.get("student_name_snapshot", ""),
            "student_name",
            200,
        ),
        "age_snapshot": _normalize_age(values.get("age_snapshot")),
        "civil_status_snapshot": _clean_text(
            values.get("civil_status_snapshot", ""),
            "civil_status",
            80,
        ),
        "course_snapshot": _clean_text(values.get("course_snapshot", ""), "course", 180),
        "major_snapshot": _clean_text(values.get("major_snapshot", ""), "major", 180),
        "email_snapshot": _clean_text(values.get("email_snapshot", ""), "email_address", 320),
        "home_address_snapshot": _clean_text(
            values.get("home_address_snapshot", ""),
            "home_address",
            MAX_ADDRESS_LENGTH,
        ),
        "contact_number_snapshot": _clean_text(
            values.get("contact_number_snapshot", ""),
            "contact_number",
            64,
        ),
        "program_completion": _normalize_program_completion(values.get("program_completion", "")),
        "extra_terms_count": _normalize_extra_terms(values.get("extra_terms_count")),
        "delay_reasons": _normalize_choice_list(
            values.get("delay_reasons", []),
            allowed=set(DelayReason.values),
            field_name="delay_reasons",
        ),
        "delay_other": _clean_text(
            values.get("delay_other", ""),
            "delay_other",
            MAX_OTHER_LENGTH,
        ),
        "significant_learning_experiences": _normalize_choice_list(
            values.get("significant_learning_experiences", []),
            allowed=set(SignificantLearningExperience.values),
            field_name="significant_learning_experiences",
        ),
        "significant_learning_other": _clean_text(
            values.get("significant_learning_other", ""),
            "significant_learning_other",
            MAX_OTHER_LENGTH,
        ),
        "career_modes": _normalize_choice_list(
            values.get("career_modes", []),
            allowed=set(CareerMode.values),
            field_name="career_modes",
        ),
        "work_choices": _normalize_choice_list(
            values.get("work_choices", []),
            allowed=set(WorkCareerChoice.values),
            field_name="work_choices",
        ),
        "study_choices": _normalize_choice_list(
            values.get("study_choices", []),
            allowed=set(StudyCareerChoice.values),
            field_name="study_choices",
        ),
    }
    for field_name in (
        "dean_comments",
        "program_chair_comments",
        "faculty_comments",
        "curriculum_comments",
        "guidance_counselor_comments",
        "office_staff_comments",
        "facilities_comments",
        "suggestions_recommendations",
    ):
        normalized[field_name] = _clean_text(
            values.get(field_name, ""),
            field_name,
            MAX_COMMENT_LENGTH,
        )

    _validate_consistency(normalized)
    return normalized


def _validate_consistency(values: dict[str, object]) -> None:
    completion = values["program_completion"]
    extra_terms = values["extra_terms_count"]
    delay_reasons = values["delay_reasons"]
    delay_other = values["delay_other"]

    if completion == ProgramCompletion.ACCORDING_TO_SCHEDULE:
        if extra_terms is not None or delay_reasons or delay_other:
            raise InvalidExitInterviewInput(
                "Delay details must be empty when the program was completed according to schedule."
            )
    elif completion == ProgramCompletion.WITH_SOME_DELAY:
        if extra_terms is None:
            raise InvalidExitInterviewInput(
                "extra_terms_count is required when program completion has some delay."
            )
    elif extra_terms is not None or delay_reasons or delay_other:
        raise InvalidExitInterviewInput(
            "Delay details require a program_completion source selection."
        )

    if DelayReason.OTHER in delay_reasons and not delay_other:
        raise InvalidExitInterviewInput(
            "delay_other is required when OTHER delay reason is selected."
        )
    if DelayReason.OTHER not in delay_reasons and delay_other:
        raise InvalidExitInterviewInput(
            "delay_other must be empty unless OTHER delay reason is selected."
        )

    learning = values["significant_learning_experiences"]
    learning_other = values["significant_learning_other"]
    if SignificantLearningExperience.OTHER in learning and not learning_other:
        raise InvalidExitInterviewInput(
            "significant_learning_other is required when OTHER learning experience is selected."
        )
    if SignificantLearningExperience.OTHER not in learning and learning_other:
        raise InvalidExitInterviewInput(
            "significant_learning_other must be empty unless OTHER learning experience is selected."
        )

    career_modes = values["career_modes"]
    if CareerMode.WORK not in career_modes and values["work_choices"]:
        raise InvalidExitInterviewInput("work_choices require the WORK career mode.")
    if CareerMode.STUDY not in career_modes and values["study_choices"]:
        raise InvalidExitInterviewInput("study_choices require the STUDY career mode.")


def _normalize_ratings(
    raw: object,
    *,
    allowed: set[str],
    minimum: int,
    maximum: int,
    field_name: str,
) -> list[tuple[str, int]]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidExitInterviewInput(f"{field_name} must be a list.")
    seen: set[str] = set()
    normalized: list[tuple[str, int]] = []
    for row in raw:
        if not isinstance(row, dict):
            raise InvalidExitInterviewInput(f"{field_name} contains an invalid row.")
        extra = set(row) - {"item_code", "rating"}
        if extra or "item_code" not in row or "rating" not in row:
            raise InvalidExitInterviewInput(f"{field_name} contains an invalid row.")
        raw_code = row["item_code"]
        code = raw_code.value if hasattr(raw_code, "value") else str(raw_code)
        rating = row["rating"]
        if code not in allowed:
            raise InvalidExitInterviewInput(f"{field_name} contains an unsupported item code.")
        if code in seen:
            raise InvalidExitInterviewInput(f"{field_name} contains a duplicate item code.")
        if type(rating) is not int or not minimum <= rating <= maximum:
            raise InvalidExitInterviewInput(
                f"{field_name} ratings must be between {minimum} and {maximum}."
            )
        seen.add(code)
        normalized.append((code, rating))
    return normalized


def _replace_ratings(item: ExitInterview, values: dict[str, object]) -> None:
    self_rows = _normalize_ratings(
        values.get("self_assessment_ratings", []),
        allowed=set(SelfAssessmentItem.values),
        minimum=1,
        maximum=5,
        field_name="self_assessment_ratings",
    )
    feedback_rows = _normalize_ratings(
        values.get("college_feedback_ratings", []),
        allowed=set(CollegeFeedbackItem.values),
        minimum=0,
        maximum=5,
        field_name="college_feedback_ratings",
    )

    item.self_assessment_ratings.all().delete()
    ExitInterviewSelfAssessmentRating.objects.bulk_create(
        [
            ExitInterviewSelfAssessmentRating(
                exit_interview=item,
                item_code=code,
                rating=rating,
            )
            for code, rating in self_rows
        ]
    )
    item.college_feedback_ratings.all().delete()
    ExitInterviewCollegeFeedbackRating.objects.bulk_create(
        [
            ExitInterviewCollegeFeedbackRating(
                exit_interview=item,
                item_code=code,
                rating=rating,
            )
            for code, rating in feedback_rows
        ]
    )


def _safe_metadata(
    item: ExitInterview,
    *,
    transition: str,
    reopen_event_id: UUID | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "academic_year": item.academic_year.label,
        "transition": transition,
    }
    if reopen_event_id is not None:
        metadata["reopen_event_id"] = str(reopen_event_id)
    return metadata


def ensure_my_current(
    *,
    student: User,
    context: AuditContext,
) -> ExitInterview:
    _validate_student(student)
    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise ExitInterviewNotFound("The Student account was not found.")
        _validate_student(locked_student)
        if not is_current_student(locked_student):
            raise ExitInterviewCurrentStudentRequired(
                "Current Student lifecycle is required to initiate an Exit Interview."
            )

        # Domain prerequisite: this is intentionally independent of Service Catalog.
        inventory = _require_submitted_current_inventory(locked_student)
        current = inventory.academic_year

        existing = (
            ExitInterview.objects.select_for_update()
            .filter(student_id=locked_student.pk, academic_year_id=current.pk)
            .first()
        )
        if existing is not None:
            return _queryset().get(pk=existing.pk)

        profile = get_person_profile_context(locked_student)
        reference_date = timezone.localdate()
        home_address = profile.current_address.strip() or profile.permanent_address.strip()
        try:
            item = ExitInterview.objects.create(
                student=locked_student,
                academic_year=current,
                inventory=inventory,
                student_name_snapshot=profile.full_name.strip(),
                age_snapshot=_age_on(profile.date_of_birth, reference_date),
                civil_status_snapshot=profile.civil_status.strip(),
                course_snapshot=inventory.course_currently_enrolled.strip(),
                major_snapshot=inventory.major.strip(),
                email_snapshot=profile.email.strip(),
                home_address_snapshot=home_address,
                contact_number_snapshot=profile.contact_number.strip(),
            )
        except IntegrityError:
            concurrent = ExitInterview.objects.filter(
                student_id=locked_student.pk,
                academic_year_id=current.pk,
            ).first()
            if concurrent is None:
                raise ExitInterviewConflict(
                    "The current Exit Interview could not be created safely; retry the request."
                ) from None
            return _queryset().get(pk=concurrent.pk)

        item_for_audit = _queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=EXIT_INTERVIEW_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="exitinterviews.exitinterview",
            target_id=item.pk,
            metadata=_safe_metadata(item_for_audit, transition="NONE -> DRAFT"),
        )
        return item_for_audit


def get_my_current(student: User) -> ExitInterview:
    _validate_student(student)
    current = _current_year()
    item = _queryset().filter(student_id=student.pk, academic_year_id=current.pk).first()
    if item is None:
        raise ExitInterviewNotFound("The current Academic Year Exit Interview was not found.")
    return item


def list_mine(student: User) -> tuple[ExitInterview, ...]:
    _validate_student(student)
    return tuple(_queryset().filter(student_id=student.pk).order_by("-created_at", "id"))


def get_mine(*, student: User, exit_interview_id: UUID) -> ExitInterview:
    _validate_student(student)
    item = _queryset().filter(pk=exit_interview_id, student_id=student.pk).first()
    if item is None:
        raise ExitInterviewNotFound("The requested Exit Interview was not found.")
    return item


def replace_my_current(*, student: User, values: dict[str, object]) -> ExitInterview:
    _validate_student(student)
    if not is_current_student(student):
        raise ExitInterviewCurrentStudentRequired(
            "Current Student lifecycle is required to edit an Exit Interview."
        )
    current = _current_year()
    normalized = _normalized_root(values)

    with transaction.atomic():
        item = (
            ExitInterview.objects.select_for_update()
            .filter(student_id=student.pk, academic_year_id=current.pk)
            .first()
        )
        if item is None:
            raise ExitInterviewNotFound("The current Academic Year Exit Interview was not found.")
        if item.status != ExitInterviewStatus.DRAFT:
            raise ExitInterviewConflict(
                "A submitted Exit Interview is locked against Student edits."
            )

        for field_name, value in normalized.items():
            setattr(item, field_name, value)
        try:
            item.full_clean(exclude=("student", "academic_year", "inventory"))
        except ValidationError as exc:
            raise InvalidExitInterviewInput(
                "The Exit Interview contains invalid typed values."
            ) from exc
        item.save(update_fields=[*normalized.keys(), "updated_at"])
        _replace_ratings(item, values)
        return _queryset().get(pk=item.pk)


def replace_mine(
    *,
    student: User,
    exit_interview_id: UUID,
    values: dict[str, object],
) -> ExitInterview:
    """Replace one owned reopened draft without re-resolving the institution-current year."""

    _validate_student(student)
    if not is_current_student(student):
        raise ExitInterviewCurrentStudentRequired(
            "Current Student lifecycle is required to edit an Exit Interview."
        )
    normalized = _normalized_root(values)

    with transaction.atomic():
        item = (
            ExitInterview.objects.select_for_update()
            .filter(pk=exit_interview_id, student_id=student.pk)
            .first()
        )
        if item is None:
            raise ExitInterviewNotFound("The requested Exit Interview was not found.")
        if item.status != ExitInterviewStatus.DRAFT:
            raise ExitInterviewConflict(
                "A submitted Exit Interview is locked against Student edits."
            )

        for field_name, value in normalized.items():
            setattr(item, field_name, value)
        try:
            item.full_clean(exclude=("student", "academic_year", "inventory"))
        except ValidationError as exc:
            raise InvalidExitInterviewInput(
                "The Exit Interview contains invalid typed values."
            ) from exc
        item.save(update_fields=[*normalized.keys(), "updated_at"])
        _replace_ratings(item, values)
        return _queryset().get(pk=item.pk)


def _validate_submission(item: ExitInterview) -> None:
    root_values = {field: getattr(item, field) for field in ROOT_EDITABLE_FIELDS}
    _validate_consistency(root_values)

    self_codes = set(item.self_assessment_ratings.values_list("item_code", flat=True))
    if self_codes != set(SelfAssessmentItem.values):
        raise InvalidExitInterviewInput(
            "All 15 fixed Self-Assessment items are required before submission."
        )
    feedback_codes = set(item.college_feedback_ratings.values_list("item_code", flat=True))
    if feedback_codes != set(CollegeFeedbackItem.values):
        raise InvalidExitInterviewInput(
            "All 26 fixed College Feedback items are required before submission."
        )

    if (
        item.inventory.student_id != item.student_id
        or item.inventory.academic_year_id != item.academic_year_id
        or item.inventory.submitted_at is None
    ):
        raise ExitInterviewInventoryRequired(
            "The bound submitted Individual Inventory provenance is inconsistent."
        )


def submit_my_current(
    *,
    student: User,
    context: AuditContext,
    now: datetime | None = None,
) -> ExitInterview:
    _validate_student(student)
    if not is_current_student(student):
        raise ExitInterviewCurrentStudentRequired(
            "Current Student lifecycle is required to submit an Exit Interview."
        )
    current = _current_year()
    submitted_at = now or timezone.now()
    if timezone.is_naive(submitted_at):
        raise InvalidExitInterviewInput("The submission time must be timezone-aware.")

    with transaction.atomic():
        item = (
            ExitInterview.objects.select_for_update()
            .select_related("academic_year", "inventory")
            .filter(student_id=student.pk, academic_year_id=current.pk)
            .first()
        )
        if item is None:
            raise ExitInterviewNotFound("The current Academic Year Exit Interview was not found.")
        if item.status == ExitInterviewStatus.SUBMITTED:
            return _queryset().get(pk=item.pk)

        _validate_submission(item)
        first_submission = item.first_submitted_at is None
        if first_submission:
            item.first_submitted_at = submitted_at
        item.last_submitted_at = submitted_at
        item.status = ExitInterviewStatus.SUBMITTED
        item.save(
            update_fields=[
                "status",
                "first_submitted_at",
                "last_submitted_at",
                "updated_at",
            ]
        )
        action = EXIT_INTERVIEW_SUBMITTED if first_submission else EXIT_INTERVIEW_RESUBMITTED
        record_event(
            context=context,
            action=action,
            outcome=AuditOutcome.SUCCESS,
            target_type="exitinterviews.exitinterview",
            target_id=item.pk,
            metadata=_safe_metadata(item, transition="DRAFT -> SUBMITTED"),
        )
        return _queryset().get(pk=item.pk)


def submit_mine(
    *,
    student: User,
    exit_interview_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> ExitInterview:
    """Submit one owned reopened draft while preserving its historical year and Inventory."""

    _validate_student(student)
    if not is_current_student(student):
        raise ExitInterviewCurrentStudentRequired(
            "Current Student lifecycle is required to submit an Exit Interview."
        )
    submitted_at = now or timezone.now()
    if timezone.is_naive(submitted_at):
        raise InvalidExitInterviewInput("The submission time must be timezone-aware.")

    with transaction.atomic():
        item = (
            ExitInterview.objects.select_for_update()
            .select_related("academic_year", "inventory")
            .filter(pk=exit_interview_id, student_id=student.pk)
            .first()
        )
        if item is None:
            raise ExitInterviewNotFound("The requested Exit Interview was not found.")
        if item.status == ExitInterviewStatus.SUBMITTED:
            return _queryset().get(pk=item.pk)

        _validate_submission(item)
        first_submission = item.first_submitted_at is None
        if first_submission:
            item.first_submitted_at = submitted_at
        item.last_submitted_at = submitted_at
        item.status = ExitInterviewStatus.SUBMITTED
        item.save(
            update_fields=[
                "status",
                "first_submitted_at",
                "last_submitted_at",
                "updated_at",
            ]
        )
        action = EXIT_INTERVIEW_SUBMITTED if first_submission else EXIT_INTERVIEW_RESUBMITTED
        record_event(
            context=context,
            action=action,
            outcome=AuditOutcome.SUCCESS,
            target_type="exitinterviews.exitinterview",
            target_id=item.pk,
            metadata=_safe_metadata(item, transition="DRAFT -> SUBMITTED"),
        )
        return _queryset().get(pk=item.pk)


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidExitInterviewInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidExitInterviewInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _clean_search(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise InvalidExitInterviewInput("search must be text.")
    cleaned = search.strip()
    if len(cleaned) > MAX_SEARCH_LENGTH:
        raise InvalidExitInterviewInput(
            f"search must be at most {MAX_SEARCH_LENGTH} characters."
        )
    return cleaned


def list_for_head(
    *,
    actor: User,
    academic_year_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    student_id: UUID | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ExitInterviewPage:
    _validate_head(actor, "exit_interviews.view")
    page, page_size = _pagination(page, page_size)
    term = _clean_search(search)
    qs = _queryset()
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if academic_year_id is not None:
        qs = qs.filter(academic_year_id=academic_year_id)
    if status is not None:
        if status not in ExitInterviewStatus.values:
            raise InvalidExitInterviewInput("status is not supported.")
        qs = qs.filter(status=status)
    if term:
        qs = qs.filter(
            Q(student__institutional_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__middle_name__icontains=term)
            | Q(student__last_name__icontains=term)
            | Q(student_name_snapshot__icontains=term)
        )
    qs = qs.order_by("-created_at", "id")
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return ExitInterviewPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def get_for_head(*, actor: User, exit_interview_id: UUID) -> ExitInterview:
    _validate_head(actor, "exit_interviews.view")
    item = _queryset().filter(pk=exit_interview_id).first()
    if item is None:
        raise ExitInterviewNotFound("The requested Exit Interview was not found.")
    return item


def reopen_for_correction(
    *,
    actor: User,
    exit_interview_id: UUID,
    reason: str,
    context: AuditContext,
    now: datetime | None = None,
) -> ExitInterview:
    _validate_head(actor, "exit_interviews.reopen")
    cleaned_reason = _clean_text(reason, "reason", MAX_REOPEN_REASON_LENGTH)
    if not cleaned_reason:
        raise InvalidExitInterviewInput("reason is required to reopen an Exit Interview.")
    reopened_at = now or timezone.now()
    if timezone.is_naive(reopened_at):
        raise InvalidExitInterviewInput("The reopen time must be timezone-aware.")

    with transaction.atomic():
        item = (
            ExitInterview.objects.select_for_update()
            .select_related("academic_year", "student__role")
            .filter(pk=exit_interview_id)
            .first()
        )
        if item is None:
            raise ExitInterviewNotFound("The requested Exit Interview was not found.")
        if item.status != ExitInterviewStatus.SUBMITTED:
            raise ExitInterviewConflict("Only a submitted Exit Interview may be reopened.")
        if not is_current_student(item.student):
            raise ExitInterviewCurrentStudentRequired(
                "Current Student lifecycle is required before reopening for Student correction."
            )

        event = ExitInterviewReopenEvent.objects.create(
            exit_interview=item,
            reopened_at=reopened_at,
            reopened_by=actor,
            reason=cleaned_reason,
        )
        item.status = ExitInterviewStatus.DRAFT
        item.save(update_fields=["status", "updated_at"])
        record_event(
            context=context,
            action=EXIT_INTERVIEW_REOPENED,
            outcome=AuditOutcome.SUCCESS,
            target_type="exitinterviews.exitinterview",
            target_id=item.pk,
            metadata=_safe_metadata(
                item,
                transition="SUBMITTED -> DRAFT",
                reopen_event_id=event.pk,
            ),
        )
        create_notification_for_event(
            recipient=item.student,
            event=NotificationEvent.EXIT_INTERVIEW_REOPENED,
            source_type="exit_interview_reopen_event",
            source_id=event.pk,
            target_type="EXIT_INTERVIEW",
            target_id=item.pk,
        )
        return _queryset().get(pk=item.pk)
