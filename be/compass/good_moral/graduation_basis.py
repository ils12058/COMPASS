"""Registrar evidence frozen at request creation, without a new persistence column."""

from compass.audit.actions import GOOD_MORAL_PREPARED, GOOD_MORAL_REQUEST_CREATED
from compass.audit.models import AuditEvent, AuditOutcome
from compass.student_academics.models import StudentGraduationRecord


def graduation_context(student_id):
    record = (
        StudentGraduationRecord.objects.select_related("graduated_college", "graduated_program")
        .filter(student_id=student_id)
        .first()
    )
    if record is None:
        return {
            "graduation_basis": "DOCUMENT_CHECK",
            "graduated_college": None,
            "degree": None,
            "graduation_date": None,
            "record_id": None,
            "verification_source": None,
            "verified_at": None,
        }
    college = record.graduated_college
    return {
        "graduation_basis": "REGISTRAR_RECORD",
        "graduated_college": {"id": str(college.pk), "code": college.code, "name": college.name},
        "degree": record.graduated_program.name if record.graduated_program_id else None,
        "graduation_date": record.graduation_date.isoformat(),
        "record_id": str(record.pk),
        "verification_source": record.verification_source,
        "verified_at": record.verified_at.isoformat(),
    }


def request_graduation_evidence(item):
    # Legacy requests without a frozen basis still need a document check. Never claim that a
    # subsequently added/edited Registrar record verified the facts on an earlier certificate.
    event = (
        AuditEvent.objects.filter(
            action=GOOD_MORAL_REQUEST_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=str(item.pk),
        )
        .order_by("occurred_at", "id")
        .first()
    )
    return event.metadata.get("graduation", {}) if event else {}


def document_check_evidence(item):
    if item.prepared_at is None:
        return None
    event = (
        AuditEvent.objects.filter(
            action=GOOD_MORAL_PREPARED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=str(item.pk),
            metadata__diploma_tor_checked=True,
            metadata__document_checked_at=item.prepared_at.isoformat(),
            actor_user_id=item.prepared_by_id,
        )
        .order_by("-occurred_at", "-id")
        .first()
    )
    return event.metadata if event else None


def needs_document_confirmation(item):
    return (
        item.variant == "GRADUATE"
        and request_graduation_evidence(item).get("graduation_basis") != "REGISTRAR_RECORD"
        and not document_check_evidence(item)
    )
