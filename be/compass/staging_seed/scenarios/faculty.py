"""Real provisional Faculty submissions and received notices; no credentials are issued."""

from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from compass.authentication.sessions import create_auth_session, revoke_auth_session
from compass.referrals import (
    administration,
    administrative_policy,
    faculty_policy,
    faculty_services,
)
from compass.referrals.models import Referral

from ..faculty import FACULTY
from ..staff import counselor_for
from ..students import STUDENTS_BY_KEY
from ..support import idempotency_key, settle_notifications


@contextmanager
def seed_actor_session(session, key):
    """Use a bounded service session, never MFA or a participant password; revoke on exit."""
    issued = create_auth_session(session.user(key))
    try:
        with transaction.atomic():
            yield issued.session
    finally:
        revoke_auth_session(
            session_id=issued.session.pk,
            context=session.system(),
            reason="staging_seed_completed",
        )


def seed_faculty_referrals(session):
    if not FACULTY:
        return
    # Resolve the same providers runtime calls use. Their fixed PROVISIONAL events are created
    # by the product, never fabricated as institutional APPROVED decisions by the dataset.
    now = timezone.now()
    faculty_policy.require_lookup_policy(now)
    faculty_policy.require_submission_policy(now)
    for kind in ("ACKNOWLEDGMENT", "CLOSURE", "FACULTY_TRACKING", "FACULTY_NOTICES"):
        administrative_policy.require_policy(kind, now)
    for spec in FACULTY:
        if Referral.objects.filter(
            submitted_by=session.users[spec.key], submission_channel="FACULTY_PORTAL"
        ).exists():
            session.record("Faculty Referral units", created=False)
            continue
        with transaction.atomic(), seed_actor_session(session, spec.key) as faculty_session:
            student = STUDENTS_BY_KEY[spec.received_student]
            confirmation = faculty_services.confirm_student(
                actor=session.user(spec.key),
                actor_session=faculty_session,
                institutional_id=student.institutional_id,
                ip_address="127.0.0.1",
            )
            item, created = faculty_services.submit_referral(
                actor=session.user(spec.key),
                actor_session=faculty_session,
                confirmation=confirmation["confirmation"],
                course_year_block=f"{student.program_code} {student.current_year_level}-A",
                reason="Synthetic adviser Referral: Student requests help balancing coursework.",
                idempotency_key=idempotency_key("faculty-received", spec.key),
                context=session.as_user(spec.key),
            )
            counselor = counselor_for(spec.campus_code, spec.college_code)
            with seed_actor_session(session, counselor) as counselor_session:
                administration.transition(
                    actor=session.user(counselor),
                    actor_session=counselor_session,
                    referral_id=item["id"],
                    expected_version=1,
                    kind="ACKNOWLEDGMENT",
                    context=session.as_user(counselor),
                )
            # Administrative provenance is immutable. Keep the product's real receipt time.
            received_at = Referral.objects.get(pk=item["id"]).received_at
            settle_notifications(source_id=item["id"], occurred_at=received_at)
            session.record("Faculty Referral units", created=created)
