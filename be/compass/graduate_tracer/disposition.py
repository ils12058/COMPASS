"""Irreversible, allowlisted aggregate-preserving Graduate Tracer anonymization."""

from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User

from .models import GTS_SCHEMA_VERSION, GraduateTracerResponse, GraduateTracerStatus
from .participation import GraduateTracerDisposedParticipation

# Every value below is used in the current closed aggregate report. All other survey fields,
# even coded ones, are removed. A new UUID prevents historical audit targets becoming a lookup.
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


@transaction.atomic
def anonymize_response(source_id):
    initial = GraduateTracerResponse.objects.get(pk=source_id)
    if initial.student_id:
        User.objects.select_for_update().get(pk=initial.student_id)
    source = GraduateTracerResponse.objects.select_for_update().get(pk=source_id)
    if source.anonymized_at is not None:
        if not verify_anonymized(source):
            raise ValueError("Anonymization verification failed.")
        return
    if (
        source.status != GraduateTracerStatus.SUBMITTED
        or source.student_id is None
        or source.instrument_schema_version != GTS_SCHEMA_VERSION
    ):
        raise ValueError("Only identifiable submitted responses may be anonymized.")
    # Preserve calendar-day report filters without retaining exact submission timestamps.
    submitted_day = timezone.make_aware(
        datetime.combine(timezone.localdate(source.submitted_at), time.min)
    )
    operation_day = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    retained = GraduateTracerResponse.objects.create(
        student=None,
        confidential_content_ciphertext=None,
        instrument_schema_version=GTS_SCHEMA_VERSION,
        status=GraduateTracerStatus.SUBMITTED,
        submitted_at=submitted_day,
        anonymized_at=operation_day,
        **{field: getattr(source, field) for field in ANALYTICAL_FIELDS},
    )
    GraduateTracerResponse.objects.filter(pk=retained.pk).update(
        created_at=submitted_day, updated_at=operation_day
    )
    if not verify_anonymized(retained):
        raise ValueError("Anonymization verification failed.")
    GraduateTracerDisposedParticipation.objects.get_or_create(
        student_id=source.student_id,
        instrument_schema_version=GTS_SCHEMA_VERSION,
        defaults={"disposed_on": timezone.localdate()},
    )
    # Only the three domain-owned child tables cascade; protected relationships stay intact.
    source.delete()
    if GraduateTracerResponse.objects.filter(pk=source_id).exists():
        raise ValueError("Identifiable source still exists.")
    # Deliberately return no new identifier and persist no original-to-anonymous mapping.
