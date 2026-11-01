"""Inactive FAC-D8 candidate intent, deliberately not connected to any producer.

No Notification, EmailDelivery, push, task or external message is created here.
FAC-5 must review any adapter to the existing Notification catalog/currentness/
idempotency/trusted-origin framework after actual institutional approval.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.utils import timezone

from compass.accounts.models import User
from compass.referrals import administrative_policy
from compass.referrals.faculty_policy import FacultyReferralError, require_submission_policy
from compass.referrals.models import Referral
from compass.referrals.tracking_disclosure import require_tracking_for_item


@dataclass(frozen=True)
class FacultyAdministrativeNoticeIntent:
    recipient_id: UUID
    referral_id: UUID
    reference_code: str
    event: str
    event_at: datetime
    route: str
    deduplication_key: str


def prepare_candidate_intent(*, referral_id, event):
    """Re-resolve current recipient/ownership/event; not a delivery authorization."""
    now = timezone.now()
    try:
        policy = administrative_policy.require_policy("FACULTY_NOTICES", now)
    except administrative_policy.AdministrativeReferralError:
        return None
    item = Referral.objects.filter(
        pk=referral_id, submission_channel="FACULTY_PORTAL", voided_at__isnull=True
    ).first()
    if item is None:
        return None
    recipient = (
        User.objects.select_related("role")
        .filter(pk=item.submitted_by_id, is_active=True, role__code="FACULTY")
        .first()
    )
    if recipient is None or not recipient.has_capability("referrals.view_submitted_self"):
        return None
    from compass.organization.models import FacultyAffiliation

    if not FacultyAffiliation.objects.filter(
        faculty=recipient, college__is_active=True, college__campus__is_active=True
    ).exists():
        return None
    try:
        submission = require_submission_policy(now)
        if (
            recipient.pk not in submission.faculty_ids
            or item.student_college_at_submission_id not in submission.student_college_ids
        ):
            return None
        require_tracking_for_item(recipient, item, now)
        administrative_policy.require_admitted(
            recipient, item.student_college_at_submission_id, policy
        )
    except (FacultyReferralError, administrative_policy.AdministrativeReferralError):
        return None
    if (
        event == "RECEIVED_BY_GCO"
        and item.acknowledged_by_id
        and item.administratively_closed_at is None
    ):
        at = item.received_at
    elif event == "ADMINISTRATIVELY_CLOSED" and item.administratively_closed_at is not None:
        at = item.administratively_closed_at
    else:
        return None
    return FacultyAdministrativeNoticeIntent(
        recipient_id=recipient.pk,
        referral_id=item.pk,
        reference_code=item.reference_code,
        event=event,
        event_at=at,
        route=f"/portal/faculty/referrals/{item.pk}",
        deduplication_key=f"faculty-referral:{item.pk}:{event}:{at.isoformat()}",
    )
