"""Independent Faculty disclosure authorization; never disclose GCO internals."""

from compass.referrals import administrative_policy
from compass.referrals.faculty_policy import FacultyReferralError


def require_tracking_for_queryset(actor, queryset, now):
    tracked = queryset.filter(acknowledged_by__isnull=False)
    if not tracked.exists():
        return None
    try:
        policy = administrative_policy.require_policy("FACULTY_TRACKING", now)
        if actor.pk not in policy.actor_ids or actor.role.code not in policy.roles:
            raise administrative_policy.AdministrativeReferralError("not_permitted")
        if tracked.exclude(
            student_college_at_submission_id__in=policy.student_college_ids
        ).exists():
            raise administrative_policy.AdministrativeReferralError("not_permitted")
        return policy
    except administrative_policy.AdministrativeReferralError:
        raise FacultyReferralError("tracking_projection_unconfirmed") from None


def require_tracking_for_item(actor, item, now):
    from compass.referrals.models import Referral

    return require_tracking_for_queryset(actor, Referral.objects.filter(pk=item.pk), now)
