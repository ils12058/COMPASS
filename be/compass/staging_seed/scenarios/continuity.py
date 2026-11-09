"""One idempotent, time-bounded demo grant through the production coverage services."""

from datetime import timedelta
from uuid import UUID

from django.utils import timezone

from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_services import decide_coverage, request_coverage
from compass.counseling.continuity_sources import SelectedSource
from compass.routine_interviews.models import RoutineInterview

from ..staff import COUNSELOR_A, COUNSELOR_B, HEAD_GUIDANCE
from ..students import FOURTH_YEAR
from ..support import SeedSession

DEMO_REQUEST_ID = UUID("c02bde00-0000-4000-8000-000000000001")


def seed_demo_coverage(session: SeedSession):
    # Never refresh expiry, approval, selected records or evaluator decisions on a repeat seed.
    if Grant.objects.filter(request_id=DEMO_REQUEST_ID).exists():
        session.record("Case coverage grants", created=False)
        return
    original = session.user(COUNSELOR_A.key)
    student = session.user(FOURTH_YEAR.key)
    source = (
        RoutineInterview.objects.filter(
            student=student,
            counselor=original,
            evaluation_finalized_at__isnull=False,
            counseling_encounter__isnull=False,
        )
        .order_by("pk")
        .first()
    )
    if source is None:
        raise ValueError("Demo coverage needs the completed Counseling story")
    # The policy's 30-day maximum keeps the demonstration active through Evaluation.
    starts_at = timezone.now() - timedelta(minutes=1)
    grant = request_coverage(
        actor=original,
        student_id=student.pk,
        original_counselor_id=original.pk,
        receiving_counselor_id=session.user(COUNSELOR_B.key).pk,
        coverage_kind="PLANNED_HANDOFF",
        reason_category="PLANNED_ABSENCE",
        starts_at=starts_at,
        expires_at=starts_at + timedelta(days=30),
        scopes=[SelectedSource("ROUTINE_EVALUATION", source.pk, "FINALIZED_EVALUATION_V1")],
        communication_purpose="CASE_COORDINATION",
        request_id=DEMO_REQUEST_ID,
        expected_version=0,
    )
    decide_coverage(
        actor=session.user(HEAD_GUIDANCE.key),
        grant_id=grant["id"],
        expected_version=grant["version"],
        decision="APPROVED",
    )
    session.record("Case coverage grants", created=True)
