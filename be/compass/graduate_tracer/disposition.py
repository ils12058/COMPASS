"""Integrity rules for historical anonymous Graduate Tracer contributions.

COMPASS no longer anonymizes responses (ADR-114); the executor that produced these rows under
ADR-072 is retired. Contributions it already created remain part of aggregate reporting, and the
allowlist and verification below still define what such a row may contain.
"""

from django.core.exceptions import ValidationError

from .models import GraduateTracerStatus

# Every value below is used in the current closed aggregate report. All other survey fields,
# even coded ones, were removed. The independent UUID prevents audit targets becoming a lookup.
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


def verify_anonymized(item):
    item.refresh_from_db()
    if (
        item.student_id is not None
        or item.anonymized_at is None
        or item.status != GraduateTracerStatus.SUBMITTED
        or item.confidential_content_ciphertext is not None
    ):
        return False
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
    for field in item._meta.concrete_fields:
        if field.name not in allowed and getattr(item, field.attname) != field.get_default():
            return False
    if any(
        getattr(item, relation).exists()
        for relation in ("education_rows", "professional_exam_rows", "training_rows")
    ):
        return False
    try:
        item.full_clean()
    except ValidationError:
        return False
    return True
