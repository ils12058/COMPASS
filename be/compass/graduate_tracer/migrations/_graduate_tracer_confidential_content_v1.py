"""Frozen ADR-084 v1 schema and crypto; never imports the runtime adapter."""

import base64
import binascii
import json
from datetime import date
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

SETTING = "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
FIELDS = {
    "GraduateTracerResponse": {
        "permanent_address_snapshot": 2000,
        "email_snapshot": 320,
        "telephone_contact_numbers_snapshot": 128,
        "mobile_number_snapshot": 64,
        "birth_date": None,
        "province": 160,
        "undergraduate_degree_reasons": None,
        "graduate_study_reasons": None,
        "degree_other_reason": 1000,
        "advanced_study_reasons": None,
        "advanced_study_other_reason": 1000,
        "unemployment_other_reason": 1000,
        "self_employed_college_skills": 4000,
        "present_occupation": 255,
        "reasons_for_staying_other": 1000,
        "reasons_for_accepting_first_job": None,
        "reasons_for_accepting_other": 1000,
        "reasons_for_changing_job": None,
        "reasons_for_changing_other": 1000,
        "first_job_duration_other": 1000,
        "first_job_source_other": 1000,
        "time_to_first_job_other": 1000,
        "useful_competencies_other": 1000,
        "curriculum_improvement_suggestions": 4000,
    },
    "GraduateTracerEducation": {
        "degree_and_specialization": 255,
        "college_or_university": 255,
        "year_graduated": None,
        "honors_or_awards": 255,
    },
    "GraduateTracerProfessionalExam": {"examination_name": 255, "date_taken": None, "rating": 128},
    "GraduateTracerTraining": {"title": 255, "duration_and_credits": 255, "institution": 255},
}
BINDINGS = {
    "GraduateTracerResponse": {"graduate_tracer_response_id": "pk"},
    "GraduateTracerEducation": {
        "graduate_tracer_response_id": "response_id",
        "education_row_id": "pk",
    },
    "GraduateTracerProfessionalExam": {
        "graduate_tracer_response_id": "response_id",
        "professional_exam_row_id": "pk",
    },
    "GraduateTracerTraining": {
        "graduate_tracer_response_id": "response_id",
        "training_row_id": "pk",
    },
}
FAMILIES = (
    ("GraduateTracerResponse", "confidential_content_ciphertext", None),
    ("GraduateTracerEducation", "confidential_content_ciphertext", "education_rows"),
    ("GraduateTracerProfessionalExam", "confidential_content_ciphertext", "professional_exam_rows"),
    ("GraduateTracerTraining", "confidential_content_ciphertext", "training_rows"),
)
LIST_CHOICES = {
    "undergraduate_degree_reasons": [
        "HIGH_GRADES_RELATED_COURSE",
        "GOOD_GRADES_HIGH_SCHOOL",
        "PARENTS_RELATIVES",
        "PEER_INFLUENCE",
        "ROLE_MODEL",
        "PASSION_PROFESSION",
        "IMMEDIATE_EMPLOYMENT",
        "STATUS_PRESTIGE",
        "COURSE_AVAILABILITY",
        "CAREER_ADVANCEMENT",
        "AFFORDABLE",
        "ATTRACTIVE_COMPENSATION",
        "EMPLOYMENT_ABROAD",
        "NO_PARTICULAR_CHOICE",
    ],
    "graduate_study_reasons": [
        "HIGH_GRADES_RELATED_COURSE",
        "GOOD_GRADES_HIGH_SCHOOL",
        "PARENTS_RELATIVES",
        "PEER_INFLUENCE",
        "ROLE_MODEL",
        "PASSION_PROFESSION",
        "IMMEDIATE_EMPLOYMENT",
        "STATUS_PRESTIGE",
        "COURSE_AVAILABILITY",
        "CAREER_ADVANCEMENT",
        "AFFORDABLE",
        "ATTRACTIVE_COMPENSATION",
        "EMPLOYMENT_ABROAD",
        "NO_PARTICULAR_CHOICE",
    ],
    "advanced_study_reasons": ["PROMOTION", "PROFESSIONAL_DEVELOPMENT", "OTHER"],
    "reasons_for_accepting_first_job": [
        "SALARIES_BENEFITS",
        "CAREER_CHALLENGE",
        "RELATED_SPECIAL_SKILLS",
        "PROXIMITY_RESIDENCE",
        "OTHER",
    ],
    "reasons_for_changing_job": [
        "SALARIES_BENEFITS",
        "CAREER_CHALLENGE",
        "RELATED_SPECIAL_SKILLS",
        "PROXIMITY_RESIDENCE",
        "OTHER",
    ],
}


def keyring():
    configured = getattr(settings, SETTING, "")
    entries = configured.split(",") if isinstance(configured, str) else configured
    if not isinstance(entries, (list, tuple)) or not entries:
        raise RuntimeError(f"{SETTING} is required for Graduate Tracer migration")
    keys, seen = [], set()
    for position, entry in enumerate(entries, start=1):
        key = entry.strip() if isinstance(entry, str) else ""
        try:
            raw = base64.urlsafe_b64decode(key.encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError):
            raw = b""
        if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii") != key:
            raise RuntimeError(f"{SETTING} entry {position} is invalid")
        if raw in seen:
            raise RuntimeError(f"{SETTING} entry {position} repeats an earlier key")
        seen.add(raw)
        keys.append(Fernet(key))
    return MultiFernet(keys)


def validate_payload(payload, family):
    if not isinstance(payload, dict) or set(payload) != set(FIELDS[family]):
        raise ValueError("Invalid Graduate Tracer payload")
    for name, maximum in FIELDS[family].items():
        value = payload[name]
        if name in {"birth_date", "date_taken"}:
            if value is not None:
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError("Invalid canonical date")
                if date.fromisoformat(value) > timezone.localdate():
                    raise ValueError("Future date")
        elif name == "year_graduated":
            if type(value) is not int or not 1900 <= value <= timezone.localdate().year:
                raise ValueError("Invalid graduation year")
        elif name in LIST_CHOICES:
            if (
                not isinstance(value, list)
                or any(type(entry) is not str or entry not in LIST_CHOICES[name] for entry in value)
                or len(set(value)) != len(value)
            ):
                raise ValueError("Invalid source choices")
        else:
            if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
                raise ValueError("Invalid text")
            value.encode("utf-8")
            if name == "email_snapshot" and value:
                validate_email(value)
            if (
                name
                in {
                    "degree_and_specialization",
                    "college_or_university",
                    "examination_name",
                    "title",
                }
                and not value.strip()
            ):
                raise ValueError("Required child text")
    return payload


def binding(row, family):
    return {key: str(getattr(row, attribute)) for key, attribute in BINDINGS[family].items()}


def failure(row, reason, family):
    return RuntimeError(f"Graduate Tracer {family} {row.pk}: {reason}; migration stopped")


def validate(row, payload, family):
    try:
        validate_payload(payload, family)
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise failure(row, "malformed", family) from None
    return payload


def plaintext(row, family):
    payload = {name: getattr(row, name) for name in FIELDS[family]}
    for name in {"birth_date", "date_taken"}.intersection(payload):
        if payload[name] is not None:
            payload[name] = payload[name].isoformat()
    return validate(row, payload, family)


def encrypt(ring, row, payload, family):
    validate(row, payload, family)
    envelope = {"schema_version": 1, **binding(row, family), "payload": payload}
    raw = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return ring.encrypt(raw).decode("ascii")


def _reject_constant(_value):
    raise ValueError("Non-finite JSON")


def decrypt(ring, row, token, family):
    if not isinstance(token, str) or not token:
        raise failure(row, "missing", family)
    try:
        raw = ring.decrypt(token.encode("ascii"))
    except (InvalidToken, UnicodeEncodeError):
        raise failure(row, "undecryptable", family) from None
    try:
        envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise failure(row, "malformed", family) from None
    expected = binding(row, family)
    if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "payload", *expected}:
        raise failure(row, "malformed", family)
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise failure(row, "unsupported_schema", family)
    if any(envelope[name] != value for name, value in expected.items()):
        raise failure(row, "binding_mismatch", family)
    return validate(row, envelope["payload"], family)


ANALYTICAL_FIELDS = (
    "sex",
    "civil_status",
    "region_of_origin",
    "residence_location",
    "current_employment_state",
    "unemployment_reasons",
    "present_employment_status",
    "employer_business_line",
    "place_of_work",
    "first_job_after_college",
    "reasons_for_staying_on_job",
    "first_job_related_to_course",
    "first_job_duration",
    "first_job_source",
    "time_to_first_job",
    "first_job_level",
    "current_job_level",
    "initial_gross_monthly_earning",
    "curriculum_relevant_to_first_job",
    "useful_competencies",
)


def verify_anonymous(row, rows, families):
    if (
        row.student_id is not None
        or row.anonymized_at is None
        or row.status != "SUBMITTED"
        or row.confidential_content_ciphertext is not None
    ):
        raise failure(row, "malformed", "GraduateTracerResponse")
    allowed = {
        "id",
        "student",
        "anonymized_at",
        "instrument_schema_version",
        "status",
        "submitted_at",
        "created_at",
        "updated_at",
        *ANALYTICAL_FIELDS,
    }
    for field in row._meta.concrete_fields:
        if field.name not in allowed and getattr(row, field.attname) != field.get_default():
            raise failure(row, "malformed", "GraduateTracerResponse")
    for model in families:
        if model.objects.using(rows.db).filter(response_id=row.pk).exists():
            raise failure(row, "malformed", "GraduateTracerResponse")

    try:
        row.full_clean()
    except ValidationError:
        raise failure(row, "malformed", "GraduateTracerResponse") from None
