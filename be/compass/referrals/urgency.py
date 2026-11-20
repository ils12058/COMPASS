"""Source-owned urgency, staff routing, concurrency and actionable predicate."""

from django.db.models import BooleanField, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.integrity import catalog_gate
from compass.referrals.faculty_rules import AdministrativeReferralError, require_administration
from compass.referrals.models import Referral, ReferralAction
from compass.referrals.services import ReferralNotFound, _scope_queryset, _student_in_scope
from compass.referrals.timing_services import _session
from compass.referrals.urgency_models import ReferralUrgencyChange


def with_urgency(queryset):
    latest = ReferralUrgencyChange.objects.filter(referral_id=OuterRef("pk")).order_by("-version")
    return queryset.annotate(
        is_urgent=Coalesce(
            Subquery(latest.values("is_urgent")[:1]), Value(False), output_field=BooleanField()
        ),
        urgency_version=Coalesce(
            Subquery(latest.values("version")[:1]), Value(0), output_field=IntegerField()
        ),
        urgency_change_id=Subquery(latest.values("pk")[:1]),
    )


def urgency_facts(referral):
    latest = referral.urgency_changes.select_related("actor").first()
    return {
        "is_urgent": latest.is_urgent if latest else False,
        "urgency_version": latest.version if latest else 0,
        "urgency_changed_at": latest.created_at if latest else None,
        "urgency_changed_by": {"id": latest.actor_id, "display_name": latest.actor.get_full_name()}
        if latest
        else None,
    }


def pending_urgent_referrals(*, actor):
    current = User.objects.select_related("role").filter(pk=getattr(actor, "pk", None)).first()
    try:
        require_administration(current, manage=True)
    except AdministrativeReferralError:
        return with_urgency(Referral.objects.none())
    handled_colleges = resolve_operational_responsibility_scope(current).college_ids
    return (
        with_urgency(_scope_queryset(Referral.objects.all(), current))
        .annotate(has_action=Exists(ReferralAction.objects.filter(referral_id=OuterRef("pk"))))
        .filter(
            Q(submission_channel="GCO_RECORDED") | Q(received_at__isnull=True),
            student__is_active=True,
            student__role__code="STUDENT",
            student__student_academic_profile__current_college_id__in=handled_colleges,
            is_urgent=True,
            administratively_closed_at__isnull=True,
            voided_at__isnull=True,
            has_action=False,
        )
    )


def append_urgency(*, referral, actor, is_urgent, context, now=None):
    if type(is_urgent) is not bool:
        raise AdministrativeReferralError("invalid_request", 422)
    latest = referral.urgency_changes.first()
    row = ReferralUrgencyChange.objects.create(
        referral=referral,
        version=(latest.version if latest else 0) + 1,
        is_urgent=is_urgent,
        actor=actor,
        created_at=now or timezone.now(),
    )
    record_event(
        context=context,
        action="referral.urgency.set" if is_urgent else "referral.urgency.cleared",
        outcome=AuditOutcome.SUCCESS,
        target_type="referrals.referral",
        target_id=referral.pk,
        metadata={"is_urgent": is_urgent, "version": row.version},
    )
    return row


def change_urgency(*, actor, actor_session, referral_id, expected_version, is_urgent, context):
    require_administration(
        User.objects.select_related("role").filter(pk=actor.pk).first(), manage=True
    )
    with catalog_gate(exclusive=True):
        student_id = (
            Referral.objects.filter(pk=referral_id).values_list("student_id", flat=True).first()
        )
        if student_id is None:
            raise ReferralNotFound("The Referral was not found.")
        users = {
            user.pk: user
            for user in User.objects.select_related("role")
            .select_for_update(no_key=True, of=("self",))
            .filter(pk__in={actor.pk, student_id})
            .order_by("id")
        }
        current = require_administration(users.get(actor.pk), manage=True)
        _session(current, actor_session, timezone.now())
        item = (
            Referral.objects.select_for_update(of=("self",))
            .filter(pk=referral_id, student_id=student_id)
            .first()
        )
        if item is None or not _student_in_scope(current, student_id):
            raise ReferralNotFound("The Referral was not found.")
        latest = item.urgency_changes.first()
        if type(expected_version) is not int or expected_version < 0 or type(is_urgent) is not bool:
            raise AdministrativeReferralError("invalid_request", 422)
        if item.voided_at is not None or expected_version != (latest.version if latest else 0):
            raise AdministrativeReferralError("conflict", 409)
        _session(current, actor_session, timezone.now())
        if is_urgent != (latest.is_urgent if latest else False):
            row = append_urgency(referral=item, actor=current, is_urgent=is_urgent, context=context)
            if row.is_urgent:
                from compass.referrals.notification_contract import create_urgent_notices

                create_urgent_notices(referral_id=item.pk)
        return urgency_facts(item)
