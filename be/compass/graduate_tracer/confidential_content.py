"""Explicit authorized Graduate Tracer private projections, ADR-084 / ADR-079."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from types import MappingProxyType
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from compass.confidential_data.crypto import (
    decrypt_bound_json,
    encrypt_bound_json,
    parse_fernet_keyring,
    reencrypt_with_primary_key,
)
from compass.confidential_data.crypto import encrypted_with_primary_key as _is_primary
from compass.confidential_data.errors import ConfidentialDataUnavailable, UnavailableReason

from .errors import GraduateTracerError, InvalidGraduateTracerInput

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


@dataclass(frozen=True, slots=True)
class GraduateTracerResponseConfidentialContent:
    permanent_address_snapshot: str = ""
    email_snapshot: str = ""
    telephone_contact_numbers_snapshot: str = ""
    mobile_number_snapshot: str = ""
    birth_date: date | None = None
    province: str = ""
    undergraduate_degree_reasons: tuple[str, ...] = ()
    graduate_study_reasons: tuple[str, ...] = ()
    degree_other_reason: str = ""
    advanced_study_reasons: tuple[str, ...] = ()
    advanced_study_other_reason: str = ""
    unemployment_other_reason: str = ""
    self_employed_college_skills: str = ""
    present_occupation: str = ""
    reasons_for_staying_other: str = ""
    reasons_for_accepting_first_job: tuple[str, ...] = ()
    reasons_for_accepting_other: str = ""
    reasons_for_changing_job: tuple[str, ...] = ()
    reasons_for_changing_other: str = ""
    first_job_duration_other: str = ""
    first_job_source_other: str = ""
    time_to_first_job_other: str = ""
    useful_competencies_other: str = ""
    curriculum_improvement_suggestions: str = ""

    def payload(self):
        values = asdict(self)
        values["birth_date"] = self.birth_date.isoformat() if self.birth_date else None
        values["undergraduate_degree_reasons"] = list(self.undergraduate_degree_reasons)
        values["graduate_study_reasons"] = list(self.graduate_study_reasons)
        values["advanced_study_reasons"] = list(self.advanced_study_reasons)
        values["reasons_for_accepting_first_job"] = list(self.reasons_for_accepting_first_job)
        values["reasons_for_changing_job"] = list(self.reasons_for_changing_job)
        return values


@dataclass(frozen=True, slots=True)
class GraduateTracerEducationConfidentialContent:
    degree_and_specialization: str = ""
    college_or_university: str = ""
    year_graduated: int = 1900
    honors_or_awards: str = ""

    def payload(self):
        values = asdict(self)
        return values


@dataclass(frozen=True, slots=True)
class GraduateTracerProfessionalExamConfidentialContent:
    examination_name: str = ""
    date_taken: date | None = None
    rating: str = ""

    def payload(self):
        values = asdict(self)
        values["date_taken"] = self.date_taken.isoformat() if self.date_taken else None
        return values


@dataclass(frozen=True, slots=True)
class GraduateTracerTrainingConfidentialContent:
    title: str = ""
    duration_and_credits: str = ""
    institution: str = ""

    def payload(self):
        values = asdict(self)
        return values


PROJECTIONS = {
    "GraduateTracerResponse": GraduateTracerResponseConfidentialContent,
    "GraduateTracerEducation": GraduateTracerEducationConfidentialContent,
    "GraduateTracerProfessionalExam": GraduateTracerProfessionalExamConfidentialContent,
    "GraduateTracerTraining": GraduateTracerTrainingConfidentialContent,
}


class GraduateTracerConfidentialContentUnavailable(GraduateTracerError):
    def __init__(self, row, *, reason: UnavailableReason):
        self.response_id = (
            row.pk if type(row).__name__ == "GraduateTracerResponse" else row.response_id
        )
        self.object_id = row.pk
        self.family = type(row).__name__
        if self.family not in FIELDS or reason not in {
            "missing",
            "undecryptable",
            "malformed",
            "unsupported_schema",
            "binding_mismatch",
        }:
            raise ValueError("Invalid failure context")
        self.reason = reason
        super().__init__("The Graduate Tracer confidential content is unavailable.")


def keyring():
    return parse_fernet_keyring(getattr(settings, SETTING, ""), setting=SETTING)


def _projection(payload, family):
    values = dict(payload)
    for name in {"birth_date", "date_taken"}.intersection(values):
        values[name] = date.fromisoformat(values[name]) if values[name] is not None else None
    for name in set(LIST_CHOICES).intersection(values):
        values[name] = tuple(values[name])
    return PROJECTIONS[family](**values)


def project_confidential_input(values, family):
    if hasattr(values, "payload"):
        values = values.payload()
    payload = dict(values)
    for name in {"birth_date", "date_taken"}.intersection(payload):
        if type(payload[name]) is date:
            payload[name] = payload[name].isoformat()
    for name in set(LIST_CHOICES).intersection(payload):
        if isinstance(payload[name], tuple):
            payload[name] = list(payload[name])
    try:
        validate_payload(payload, family)
    except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
        raise InvalidGraduateTracerInput(
            "The Graduate Tracer confidential content contains invalid values."
        ) from None
    return _projection(payload, family)


def write_confidential_content(row, values):
    family = type(row).__name__
    projection = project_confidential_input(values, family)
    row.confidential_content_ciphertext = encrypt_bound_json(
        keyring=keyring(),
        schema_version=1,
        binding=binding(row, family),
        payload=projection.payload(),
    )


def read_confidential_content(row):
    family = type(row).__name__
    try:
        try:
            ring = keyring()
        except ValueError:
            raise ConfidentialDataUnavailable(reason="missing") from None
        payload = decrypt_bound_json(
            row.confidential_content_ciphertext,
            keyring=ring,
            schema_version=1,
            binding=binding(row, family),
        )
        try:
            validate_payload(payload, family)
        except (ValueError, TypeError, UnicodeEncodeError, ValidationError):
            raise ConfidentialDataUnavailable(reason="malformed") from None
    except ConfidentialDataUnavailable as exc:
        raise GraduateTracerConfidentialContentUnavailable(row, reason=exc.reason) from None
    return _projection(payload, family)


@dataclass(frozen=True, slots=True)
class GraduateTracerPrivateProjection:
    root: GraduateTracerResponseConfidentialContent
    children: Mapping[UUID, object]


def read_private_projection(item):
    root = read_confidential_content(item)
    children = {
        row.pk: read_confidential_content(row)
        for _, _, relation in FAMILIES[1:]
        for row in getattr(item, relation).all()
    }
    return GraduateTracerPrivateProjection(root, MappingProxyType(children))


def encrypted_with_primary_key(token):
    return _is_primary(token, keyring=keyring())


def reencrypt_confidential_content(row):
    read_confidential_content(row)
    return reencrypt_with_primary_key(row.confidential_content_ciphertext, keyring=keyring())
