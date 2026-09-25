"""Graduate Tracer draft, submission, history, and restricted review services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.accounts.profiles import get_person_profile_context
from compass.audit.actions import GRADUATE_TRACER_DRAFT_CREATED, GRADUATE_TRACER_SUBMITTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import (
    GTS_SCHEMA_VERSION,
    GraduateTracerEducation,
    GraduateTracerProfessionalExam,
    GraduateTracerResponse,
    GraduateTracerStatus,
    GraduateTracerTraining,
    GTSAdvancedStudyReason,
    GTSBusinessLine,
    GTSCivilStatus,
    GTSDegreeReason,
    GTSEarningBracket,
    GTSEmploymentState,
    GTSFirstJobDuration,
    GTSFirstJobSource,
    GTSJobLevel,
    GTSJobReason,
    GTSPlaceOfWork,
    GTSPresentEmploymentStatus,
    GTSRegionOfOrigin,
    GTSResidenceLocation,
    GTSSex,
    GTSStayingReason,
    GTSUnemploymentReason,
    GTSUsefulCompetency,
)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_ADDRESS_LENGTH = 2000
MAX_LONG_TEXT_LENGTH = 4000
MAX_OTHER_LENGTH = 1000
MAX_SEARCH_LENGTH = 160

TEXT_FIELD_LIMITS = {
    "name_snapshot": 200,
    "permanent_address_snapshot": MAX_ADDRESS_LENGTH,
    "email_snapshot": 320,
    "telephone_contact_numbers_snapshot": 128,
    "mobile_number_snapshot": 64,
    "province": 160,
    "degree_other_reason": MAX_OTHER_LENGTH,
    "advanced_study_other_reason": MAX_OTHER_LENGTH,
    "unemployment_other_reason": MAX_OTHER_LENGTH,
    "self_employed_college_skills": MAX_LONG_TEXT_LENGTH,
    "present_occupation": 255,
    "reasons_for_staying_other": MAX_OTHER_LENGTH,
    "reasons_for_accepting_other": MAX_OTHER_LENGTH,
    "reasons_for_changing_other": MAX_OTHER_LENGTH,
    "first_job_duration_other": MAX_OTHER_LENGTH,
    "first_job_source_other": MAX_OTHER_LENGTH,
    "time_to_first_job_other": MAX_OTHER_LENGTH,
    "useful_competencies_other": MAX_OTHER_LENGTH,
    "curriculum_improvement_suggestions": MAX_LONG_TEXT_LENGTH,
}

CHOICE_FIELDS = {
    "civil_status": set(GTSCivilStatus.values),
    "sex": set(GTSSex.values),
    "region_of_origin": set(GTSRegionOfOrigin.values),
    "residence_location": set(GTSResidenceLocation.values),
    "current_employment_state": set(GTSEmploymentState.values),
    "present_employment_status": set(GTSPresentEmploymentStatus.values),
    "employer_business_line": set(GTSBusinessLine.values),
    "place_of_work": set(GTSPlaceOfWork.values),
    "first_job_duration": set(GTSFirstJobDuration.values),
    "first_job_source": set(GTSFirstJobSource.values),
    "time_to_first_job": set(GTSFirstJobDuration.values),
    "first_job_level": set(GTSJobLevel.values),
    "current_job_level": set(GTSJobLevel.values),
    "initial_gross_monthly_earning": set(GTSEarningBracket.values),
}

LIST_FIELDS = {
    "undergraduate_degree_reasons": set(GTSDegreeReason.values),
    "graduate_study_reasons": set(GTSDegreeReason.values),
    "advanced_study_reasons": set(GTSAdvancedStudyReason.values),
    "unemployment_reasons": set(GTSUnemploymentReason.values),
    "reasons_for_staying_on_job": set(GTSStayingReason.values),
    "reasons_for_accepting_first_job": set(GTSJobReason.values),
    "reasons_for_changing_job": set(GTSJobReason.values),
    "useful_competencies": set(GTSUsefulCompetency.values),
}

BOOLEAN_FIELDS = {
    "first_job_after_college",
    "first_job_related_to_course",
    "curriculum_relevant_to_first_job",
}


class GraduateTracerError(RuntimeError):
    pass


class GraduateTracerNotFound(GraduateTracerError):
    pass


class GraduateTracerNotPermitted(GraduateTracerError):
    pass


class GraduateTracerGraduatedStudentRequired(GraduateTracerError):
    pass


class GraduateTracerConflict(GraduateTracerError):
    pass


class InvalidGraduateTracerInput(GraduateTracerError):
    pass


@dataclass(frozen=True, slots=True)
class GraduateTracerPage:
    items: tuple[GraduateTracerResponse, ...]
    page: int
    page_size: int
    has_next: bool


def _queryset():
    return GraduateTracerResponse.objects.select_related(
        "student", "student__role"
    ).prefetch_related(
        "education_rows",
        "professional_exam_rows",
        "training_rows",
    )


def _validate_student_access(student: User, capability: str) -> None:
    if (
        not getattr(student, "pk", None)
        or not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability(capability)
    ):
        raise GraduateTracerNotPermitted("Active Student Graduate Tracer access is required.")


def _validate_graduated_student(student: User) -> None:
    _validate_student_access(student, "graduate_tracer.manage_self")
    if student.student_lifecycle_status != StudentLifecycleStatus.GRADUATED:
        raise GraduateTracerGraduatedStudentRequired(
            "Graduated Student lifecycle is required to create, edit, or submit "
            "Graduate Tracer data."
        )


def _validate_viewer(actor: User) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability("graduate_tracer.view")
    ):
        raise GraduateTracerNotPermitted(
            "Head Guidance Graduate Tracer review authority is required."
        )


def _clean_text(value: object, field_name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidGraduateTracerInput(f"{field_name} must be text.")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise InvalidGraduateTracerInput(f"{field_name} is too long.")
    return cleaned


def _choice(value: object, allowed: set[str], field_name: str) -> str:
    if value in {None, ""}:
        return ""
    candidate = value.value if hasattr(value, "value") else str(value)
    if candidate not in allowed:
        raise InvalidGraduateTracerInput(f"{field_name} contains an unsupported source value.")
    return candidate


def _choice_list(value: object, allowed: set[str], field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise InvalidGraduateTracerInput(f"{field_name} must be a list.")
    normalized: list[str] = []
    for raw in value:
        candidate = raw.value if hasattr(raw, "value") else str(raw)
        if candidate not in allowed:
            raise InvalidGraduateTracerInput(f"{field_name} contains an unsupported source value.")
        if candidate in normalized:
            raise InvalidGraduateTracerInput(f"{field_name} must not contain duplicate values.")
        normalized.append(candidate)
    return normalized


def _optional_bool(value: object, field_name: str) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise InvalidGraduateTracerInput(f"{field_name} must be true, false, or null.")
    return value


def _birth_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvalidGraduateTracerInput("birth_date must be a date or null.")
    if value > timezone.localdate():
        raise InvalidGraduateTracerInput("birth_date must not be in the future.")
    return value


def _profile_civil_status(value: str) -> str:
    normalized = value.strip().casefold()
    for candidate, label in GTSCivilStatus.choices:
        if normalized in {candidate.casefold(), label.casefold()}:
            return candidate
    return ""


def ensure_my_response(
    *,
    student: User,
    context: AuditContext,
) -> GraduateTracerResponse:
    _validate_graduated_student(student)
    with transaction.atomic():
        locked = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked is None:
            raise GraduateTracerNotFound("The Student account was not found.")
        _validate_graduated_student(locked)

        existing = (
            GraduateTracerResponse.objects.select_for_update()
            .filter(student_id=locked.pk, instrument_schema_version=GTS_SCHEMA_VERSION)
            .first()
        )
        if existing is not None:
            return _queryset().get(pk=existing.pk)

        profile = get_person_profile_context(locked)
        try:
            item = GraduateTracerResponse.objects.create(
                student=locked,
                instrument_schema_version=GTS_SCHEMA_VERSION,
                name_snapshot=profile.full_name.strip(),
                permanent_address_snapshot=profile.permanent_address.strip(),
                email_snapshot=profile.email.strip(),
                telephone_contact_numbers_snapshot=profile.contact_number.strip(),
                mobile_number_snapshot="",
                birth_date=profile.date_of_birth,
                civil_status=_profile_civil_status(profile.civil_status),
            )
        except IntegrityError:
            concurrent = GraduateTracerResponse.objects.filter(
                student_id=locked.pk,
                instrument_schema_version=GTS_SCHEMA_VERSION,
            ).first()
            if concurrent is None:
                raise GraduateTracerConflict(
                    "The Graduate Tracer draft could not be created safely; retry the request."
                ) from None
            return _queryset().get(pk=concurrent.pk)

        record_event(
            context=context,
            action=GRADUATE_TRACER_DRAFT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="graduatetracer.response",
            target_id=item.pk,
            metadata={
                "instrument_schema_version": GTS_SCHEMA_VERSION,
                "transition": "NONE -> DRAFT",
            },
        )
        return _queryset().get(pk=item.pk)


def get_my_response(student: User) -> GraduateTracerResponse:
    _validate_student_access(student, "graduate_tracer.view_self")
    item = (
        _queryset()
        .filter(student_id=student.pk, instrument_schema_version=GTS_SCHEMA_VERSION)
        .first()
    )
    if item is None:
        raise GraduateTracerNotFound("The Graduate Tracer response was not found.")
    return item


def _normalize_education_rows(raw: object) -> list[dict[str, object]]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidGraduateTracerInput("education must be a list.")
    normalized: list[dict[str, object]] = []
    current_year = timezone.localdate().year
    for position, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise InvalidGraduateTracerInput("education contains an invalid row.")
        if set(row) - {
            "degree_and_specialization",
            "college_or_university",
            "year_graduated",
            "honors_or_awards",
        }:
            raise InvalidGraduateTracerInput("education contains unsupported fields.")
        degree = _clean_text(
            row.get("degree_and_specialization", ""),
            "education.degree_and_specialization",
            255,
        )
        institution = _clean_text(
            row.get("college_or_university", ""),
            "education.college_or_university",
            255,
        )
        year = row.get("year_graduated")
        honors = _clean_text(
            row.get("honors_or_awards", ""),
            "education.honors_or_awards",
            255,
        )
        if not degree or not institution:
            raise InvalidGraduateTracerInput(
                "Every education row requires degree_and_specialization and college_or_university."
            )
        if type(year) is not int or not 1900 <= year <= current_year:
            raise InvalidGraduateTracerInput(
                "education.year_graduated must be a sensible completed graduation year."
            )
        normalized.append(
            {
                "position": position,
                "degree_and_specialization": degree,
                "college_or_university": institution,
                "year_graduated": year,
                "honors_or_awards": honors,
            }
        )
    return normalized


def _normalize_exam_rows(raw: object) -> list[dict[str, object]]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidGraduateTracerInput("professional_exams must be a list.")
    normalized: list[dict[str, object]] = []
    for position, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise InvalidGraduateTracerInput("professional_exams contains an invalid row.")
        if set(row) - {"examination_name", "date_taken", "rating"}:
            raise InvalidGraduateTracerInput("professional_exams contains unsupported fields.")
        name = _clean_text(
            row.get("examination_name", ""),
            "professional_exams.examination_name",
            255,
        )
        taken = row.get("date_taken")
        rating = _clean_text(row.get("rating", ""), "professional_exams.rating", 128)
        if not name:
            raise InvalidGraduateTracerInput(
                "Every professional examination row requires examination_name."
            )
        if taken is not None:
            if not isinstance(taken, date) or isinstance(taken, datetime):
                raise InvalidGraduateTracerInput(
                    "professional_exams.date_taken must be a date or null."
                )
            if taken > timezone.localdate():
                raise InvalidGraduateTracerInput(
                    "professional_exams.date_taken must not be in the future."
                )
        normalized.append(
            {
                "position": position,
                "examination_name": name,
                "date_taken": taken,
                "rating": rating,
            }
        )
    return normalized


def _normalize_training_rows(raw: object) -> list[dict[str, object]]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidGraduateTracerInput("trainings must be a list.")
    normalized: list[dict[str, object]] = []
    for position, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise InvalidGraduateTracerInput("trainings contains an invalid row.")
        if set(row) - {"title", "duration_and_credits", "institution"}:
            raise InvalidGraduateTracerInput("trainings contains unsupported fields.")
        title = _clean_text(row.get("title", ""), "trainings.title", 255)
        duration = _clean_text(
            row.get("duration_and_credits", ""),
            "trainings.duration_and_credits",
            255,
        )
        institution = _clean_text(
            row.get("institution", ""),
            "trainings.institution",
            255,
        )
        if not title:
            raise InvalidGraduateTracerInput("Every training row requires title.")
        normalized.append(
            {
                "position": position,
                "title": title,
                "duration_and_credits": duration,
                "institution": institution,
            }
        )
    return normalized


def _normalize_root(values: dict[str, object]) -> dict[str, object]:
    allowed = (
        set(TEXT_FIELD_LIMITS)
        | set(CHOICE_FIELDS)
        | set(LIST_FIELDS)
        | BOOLEAN_FIELDS
        | {"birth_date"}
    )
    unknown = set(values) - allowed - {"education", "professional_exams", "trainings"}
    if unknown:
        raise InvalidGraduateTracerInput(
            "Unsupported Graduate Tracer fields: " + ", ".join(sorted(unknown)) + "."
        )

    normalized: dict[str, object] = {}
    for field_name, maximum in TEXT_FIELD_LIMITS.items():
        normalized[field_name] = _clean_text(values.get(field_name, ""), field_name, maximum)
    email = normalized["email_snapshot"]
    if email:
        try:
            validate_email(email)
        except ValidationError as exc:
            raise InvalidGraduateTracerInput(
                "email must be a valid email address when supplied."
            ) from exc

    normalized["birth_date"] = _birth_date(values.get("birth_date"))
    for field_name, allowed_values in CHOICE_FIELDS.items():
        normalized[field_name] = _choice(
            values.get(field_name, ""),
            allowed_values,
            field_name,
        )
    for field_name, allowed_values in LIST_FIELDS.items():
        normalized[field_name] = _choice_list(
            values.get(field_name, []),
            allowed_values,
            field_name,
        )
    for field_name in BOOLEAN_FIELDS:
        normalized[field_name] = _optional_bool(values.get(field_name), field_name)

    employment = normalized["current_employment_state"]
    if employment in {GTSEmploymentState.NOT_EMPLOYED, GTSEmploymentState.NEVER_EMPLOYED}:
        for field_name in (
            "present_employment_status",
            "self_employed_college_skills",
            "present_occupation",
            "employer_business_line",
            "place_of_work",
            "first_job_duration",
            "first_job_duration_other",
            "first_job_source",
            "first_job_source_other",
            "time_to_first_job",
            "time_to_first_job_other",
            "first_job_level",
            "current_job_level",
            "initial_gross_monthly_earning",
            "useful_competencies_other",
        ):
            normalized[field_name] = ""
        for field_name in (
            "reasons_for_staying_on_job",
            "reasons_for_accepting_first_job",
            "reasons_for_changing_job",
            "useful_competencies",
        ):
            normalized[field_name] = []
        normalized["first_job_after_college"] = None
        normalized["first_job_related_to_course"] = None
        normalized["curriculum_relevant_to_first_job"] = None
    elif employment == GTSEmploymentState.EMPLOYED:
        normalized["unemployment_reasons"] = []
        normalized["unemployment_other_reason"] = ""

    if normalized["present_employment_status"] != GTSPresentEmploymentStatus.SELF_EMPLOYED:
        normalized["self_employed_college_skills"] = ""

    if normalized["first_job_after_college"] is False:
        normalized["reasons_for_staying_on_job"] = []
        normalized["reasons_for_staying_other"] = ""
        normalized["first_job_related_to_course"] = None
        normalized["reasons_for_accepting_first_job"] = []
        normalized["reasons_for_accepting_other"] = ""
    elif normalized["first_job_related_to_course"] is False:
        normalized["reasons_for_accepting_first_job"] = []
        normalized["reasons_for_accepting_other"] = ""

    if normalized["curriculum_relevant_to_first_job"] is False:
        normalized["useful_competencies"] = []
        normalized["useful_competencies_other"] = ""

    return normalized


def _replace_children(
    item: GraduateTracerResponse,
    *,
    education: list[dict[str, object]],
    professional_exams: list[dict[str, object]],
    trainings: list[dict[str, object]],
) -> None:
    item.education_rows.all().delete()
    GraduateTracerEducation.objects.bulk_create(
        [GraduateTracerEducation(response=item, **row) for row in education]
    )
    item.professional_exam_rows.all().delete()
    GraduateTracerProfessionalExam.objects.bulk_create(
        [GraduateTracerProfessionalExam(response=item, **row) for row in professional_exams]
    )
    item.training_rows.all().delete()
    GraduateTracerTraining.objects.bulk_create(
        [GraduateTracerTraining(response=item, **row) for row in trainings]
    )


def replace_my_draft(
    *,
    student: User,
    values: dict[str, object],
) -> GraduateTracerResponse:
    _validate_graduated_student(student)
    normalized = _normalize_root(values)
    education = _normalize_education_rows(values.get("education", []))
    professional_exams = _normalize_exam_rows(values.get("professional_exams", []))
    trainings = _normalize_training_rows(values.get("trainings", []))

    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise GraduateTracerNotFound("The Student account was not found.")
        _validate_graduated_student(locked_student)
        item = (
            GraduateTracerResponse.objects.select_for_update()
            .filter(
                student_id=locked_student.pk,
                instrument_schema_version=GTS_SCHEMA_VERSION,
            )
            .first()
        )
        if item is None:
            raise GraduateTracerNotFound(
                "Create the Graduate Tracer draft before replacing its answers."
            )
        if item.status != GraduateTracerStatus.DRAFT:
            raise GraduateTracerConflict("A submitted Graduate Tracer response is immutable.")

        for field_name, value in normalized.items():
            setattr(item, field_name, value)
        item.save(update_fields=[*normalized.keys(), "updated_at"])
        _replace_children(
            item,
            education=education,
            professional_exams=professional_exams,
            trainings=trainings,
        )
        return _queryset().get(pk=item.pk)


def _require_text(value: str, label: str) -> None:
    if not value.strip():
        raise InvalidGraduateTracerInput(f"{label} is required before submission.")


def _validate_other(
    values: list[str],
    other_value: str,
    *,
    other_code: str,
    label: str,
) -> None:
    if other_code in values and not other_value.strip():
        raise InvalidGraduateTracerInput(f"{label} is required when OTHER is selected.")
    if other_code not in values and other_value.strip():
        raise InvalidGraduateTracerInput(f"{label} must be blank unless OTHER is selected.")


def _validate_submission(item: GraduateTracerResponse) -> None:
    _require_text(item.name_snapshot, "name")
    if not item.civil_status:
        raise InvalidGraduateTracerInput("civil_status is required before submission.")
    if not item.sex:
        raise InvalidGraduateTracerInput("sex is required before submission.")
    if item.birth_date is None:
        raise InvalidGraduateTracerInput("birth_date is required before submission.")
    if not item.region_of_origin:
        raise InvalidGraduateTracerInput("region_of_origin is required before submission.")
    _require_text(item.province, "province")
    if not item.residence_location:
        raise InvalidGraduateTracerInput("residence_location is required before submission.")
    if not item.education_rows.exists():
        raise InvalidGraduateTracerInput(
            "At least one baccalaureate education row is required before submission."
        )

    _validate_other(
        item.advanced_study_reasons,
        item.advanced_study_other_reason,
        other_code=GTSAdvancedStudyReason.OTHER,
        label="advanced_study_other_reason",
    )

    employment = item.current_employment_state
    if not employment:
        raise InvalidGraduateTracerInput("current_employment_state is required before submission.")

    if employment in {GTSEmploymentState.NOT_EMPLOYED, GTSEmploymentState.NEVER_EMPLOYED}:
        if not item.unemployment_reasons:
            raise InvalidGraduateTracerInput(
                "At least one unemployment reason is required for an unemployed respondent."
            )
        _validate_other(
            item.unemployment_reasons,
            item.unemployment_other_reason,
            other_code=GTSUnemploymentReason.OTHER,
            label="unemployment_other_reason",
        )
        return

    if employment != GTSEmploymentState.EMPLOYED:
        raise InvalidGraduateTracerInput("current_employment_state is not supported.")

    if not item.present_employment_status:
        raise InvalidGraduateTracerInput(
            "present_employment_status is required for an employed respondent."
        )
    if item.present_employment_status == GTSPresentEmploymentStatus.SELF_EMPLOYED:
        _require_text(item.self_employed_college_skills, "self_employed_college_skills")
    _require_text(item.present_occupation, "present_occupation")
    if not item.employer_business_line:
        raise InvalidGraduateTracerInput(
            "employer_business_line is required for an employed respondent."
        )
    if not item.place_of_work:
        raise InvalidGraduateTracerInput("place_of_work is required for an employed respondent.")
    if item.first_job_after_college is None:
        raise InvalidGraduateTracerInput(
            "first_job_after_college is required for an employed respondent."
        )

    if item.first_job_after_college:
        if not item.reasons_for_staying_on_job:
            raise InvalidGraduateTracerInput(
                "reasons_for_staying_on_job is required when the current job is the first job."
            )
        _validate_other(
            item.reasons_for_staying_on_job,
            item.reasons_for_staying_other,
            other_code=GTSStayingReason.OTHER,
            label="reasons_for_staying_other",
        )
        if item.first_job_related_to_course is None:
            raise InvalidGraduateTracerInput(
                "first_job_related_to_course is required when the current job is the first job."
            )

    _validate_other(
        item.reasons_for_accepting_first_job,
        item.reasons_for_accepting_other,
        other_code=GTSJobReason.OTHER,
        label="reasons_for_accepting_other",
    )
    _validate_other(
        item.reasons_for_changing_job,
        item.reasons_for_changing_other,
        other_code=GTSJobReason.OTHER,
        label="reasons_for_changing_other",
    )

    if not item.first_job_duration:
        raise InvalidGraduateTracerInput(
            "first_job_duration is required for an employed respondent."
        )
    if item.first_job_duration == GTSFirstJobDuration.OTHER:
        _require_text(item.first_job_duration_other, "first_job_duration_other")
    elif item.first_job_duration_other:
        raise InvalidGraduateTracerInput(
            "first_job_duration_other must be blank unless OTHER is selected."
        )

    if not item.first_job_source:
        raise InvalidGraduateTracerInput("first_job_source is required for an employed respondent.")
    if item.first_job_source == GTSFirstJobSource.OTHER:
        _require_text(item.first_job_source_other, "first_job_source_other")
    elif item.first_job_source_other:
        raise InvalidGraduateTracerInput(
            "first_job_source_other must be blank unless OTHER is selected."
        )

    if not item.time_to_first_job:
        raise InvalidGraduateTracerInput(
            "time_to_first_job is required for an employed respondent."
        )
    if item.time_to_first_job == GTSFirstJobDuration.OTHER:
        _require_text(item.time_to_first_job_other, "time_to_first_job_other")
    elif item.time_to_first_job_other:
        raise InvalidGraduateTracerInput(
            "time_to_first_job_other must be blank unless OTHER is selected."
        )

    if not item.first_job_level or not item.current_job_level:
        raise InvalidGraduateTracerInput(
            "first_job_level and current_job_level are required for an employed respondent."
        )
    if not item.initial_gross_monthly_earning:
        raise InvalidGraduateTracerInput(
            "initial_gross_monthly_earning is required for an employed respondent."
        )
    if item.curriculum_relevant_to_first_job is None:
        raise InvalidGraduateTracerInput(
            "curriculum_relevant_to_first_job is required for an employed respondent."
        )
    if item.curriculum_relevant_to_first_job:
        if not item.useful_competencies:
            raise InvalidGraduateTracerInput(
                "At least one useful competency is required when the curriculum was relevant."
            )
        _validate_other(
            item.useful_competencies,
            item.useful_competencies_other,
            other_code=GTSUsefulCompetency.OTHER,
            label="useful_competencies_other",
        )


def submit_my_response(
    *,
    student: User,
    context: AuditContext,
    now: datetime | None = None,
) -> GraduateTracerResponse:
    _validate_graduated_student(student)
    submitted_at = now or timezone.now()
    if timezone.is_naive(submitted_at):
        raise InvalidGraduateTracerInput("The submission time must be timezone-aware.")

    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise GraduateTracerNotFound("The Student account was not found.")
        _validate_graduated_student(locked_student)
        item = (
            GraduateTracerResponse.objects.select_for_update()
            .filter(
                student_id=locked_student.pk,
                instrument_schema_version=GTS_SCHEMA_VERSION,
            )
            .first()
        )
        if item is None:
            raise GraduateTracerNotFound("The Graduate Tracer response was not found.")
        if item.status == GraduateTracerStatus.SUBMITTED:
            return _queryset().get(pk=item.pk)

        item = _queryset().get(pk=item.pk)
        _validate_submission(item)
        item.status = GraduateTracerStatus.SUBMITTED
        item.submitted_at = submitted_at
        item.save(update_fields=["status", "submitted_at", "updated_at"])
        record_event(
            context=context,
            action=GRADUATE_TRACER_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="graduatetracer.response",
            target_id=item.pk,
            metadata={
                "instrument_schema_version": GTS_SCHEMA_VERSION,
                "transition": "DRAFT -> SUBMITTED",
            },
        )
        return _queryset().get(pk=item.pk)


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidGraduateTracerInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidGraduateTracerInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _clean_search(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise InvalidGraduateTracerInput("search must be text.")
    cleaned = search.strip()
    if len(cleaned) > MAX_SEARCH_LENGTH:
        raise InvalidGraduateTracerInput(f"search must be at most {MAX_SEARCH_LENGTH} characters.")
    return cleaned


def _submission_boundary(value: date, *, following_day: bool = False) -> datetime:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvalidGraduateTracerInput("submission date filters must be calendar dates.")
    local_date = value + timedelta(days=1) if following_day else value
    return timezone.make_aware(
        datetime.combine(local_date, time.min),
        timezone.get_current_timezone(),
    )


def list_submitted_for_head(
    *,
    actor: User,
    search: str | None = None,
    student_id: UUID | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    current_employment_state: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> GraduateTracerPage:
    _validate_viewer(actor)
    page, page_size = _pagination(page, page_size)
    term = _clean_search(search)
    if submitted_from is not None and submitted_to is not None and submitted_from > submitted_to:
        raise InvalidGraduateTracerInput("submitted_from must be on or before submitted_to.")
    queryset = _queryset().filter(status=GraduateTracerStatus.SUBMITTED)
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    if term:
        queryset = queryset.filter(
            Q(student__institutional_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__middle_name__icontains=term)
            | Q(student__last_name__icontains=term)
            | Q(name_snapshot__icontains=term)
        )
    if submitted_from is not None:
        queryset = queryset.filter(submitted_at__gte=_submission_boundary(submitted_from))
    if submitted_to is not None:
        queryset = queryset.filter(
            submitted_at__lt=_submission_boundary(submitted_to, following_day=True)
        )
    if current_employment_state is not None:
        employment_state = _choice(
            current_employment_state,
            set(GTSEmploymentState.values),
            "current_employment_state",
        )
        queryset = queryset.filter(current_employment_state=employment_state)
    queryset = queryset.order_by("-submitted_at", "id")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return GraduateTracerPage(
        tuple(rows[:page_size]),
        page,
        page_size,
        len(rows) > page_size,
    )


def get_submitted_for_head(
    *,
    actor: User,
    response_id: UUID,
) -> GraduateTracerResponse:
    _validate_viewer(actor)
    item = (
        _queryset()
        .filter(
            pk=response_id,
            status=GraduateTracerStatus.SUBMITTED,
        )
        .first()
    )
    if item is None:
        raise GraduateTracerNotFound("The submitted Graduate Tracer response was not found.")
    return item
