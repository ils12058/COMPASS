"""Faculty ownership and live disclosure authorization; never disclose GCO internals."""

from compass.referrals.faculty_rules import (
    FacultyReferralError,
    active_colleges,
    faculty_can_track,
)


def require_tracking_for_queryset(actor, queryset, now):
    if (
        not faculty_can_track(actor)
        or queryset.exclude(submitted_by_id=actor.pk, submission_channel="FACULTY_PORTAL").exists()
        or queryset.exclude(
            student_college_at_submission_id__in=active_colleges().values("pk")
        ).exists()
    ):
        raise FacultyReferralError("not_permitted")


def require_tracking_for_item(actor, item, now):
    from compass.referrals.models import Referral

    require_tracking_for_queryset(actor, Referral.objects.filter(pk=item.pk), now)
