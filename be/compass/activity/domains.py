"""Closed domain policies for My Activity, independent of all other activity surfaces.

Source queries validate current read authority before event pagination. Only typed primary-key
subqueries are compared with audit strings: never cast untrusted target IDs, decrypt content,
infer ownership from metadata, or load an entire caseload into application memory.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import CharField, OuterRef, Q, Subquery
from django.db.models.functions import Cast

from compass.accounts.services import effective_capabilities
from compass.appointments.access import scope_managed_appointments
from compass.appointments.models import Appointment
from compass.audit import actions
from compass.audit.models import AuditActorType, AuditOutcome
from compass.call_slips.models import CallSlip
from compass.call_slips.services import _scope_queryset as scope_call_slips
from compass.exit_interviews.models import ExitInterview
from compass.good_moral.models import GoodMoralInitiationOrigin, GoodMoralRequest
from compass.inventory.models import StudentInventory
from compass.inventory.services import _scoped_students as inventory_students
from compass.referrals.models import Referral, ReferralAction
from compass.referrals.services import _scope_queryset as scope_referrals
from compass.routine_interviews.models import RoutineInterview

from .presenters import ActivityItem

STUDENT = "STUDENT"
COUNSELOR = "COUNSELOR"
OPERATIONAL = frozenset({COUNSELOR, "GUIDANCE_SERVICES_STAFF"})


@dataclass(frozen=True, slots=True)
class DomainActivityPolicy:
    target_type: str
    title: str
    student_self: str | None = None
    student_affected: str | None = None
    staff_self: str | None = None
    staff_roles: frozenset[str] = OPERATIONAL

    def present(self, event, *, user) -> ActivityItem:
        if user.role.code == STUDENT:
            description = (
                self.student_self if event.actor_user_id == user.pk else None
            ) or self.student_affected
        else:
            description = self.staff_self
        # Selection and presentation use the same immutable policy; missing copy fails closed.
        if description is None:
            raise ValueError("No domain presentation for this viewer relationship")
        return ActivityItem(event.id, event.action, self.title, description, event.occurred_at)


# Each row corresponds to the evidence matrix in BACKLOG-ACT-2-Implementation-Report.md.
# An action constant or source model added elsewhere never automatically enters this projection.
DOMAIN_ACTIVITY_POLICIES = {
    actions.APPOINTMENT_CREATED: DomainActivityPolicy(
        "appointments.appointment",
        "Appointment booked",
        student_self="You booked an appointment.",
    ),
    actions.APPOINTMENT_CANCELLED: DomainActivityPolicy(
        "appointments.appointment",
        "Appointment cancelled",
        "You cancelled your appointment.",
        "Your appointment was cancelled.",
        "You cancelled an appointment.",
    ),
    actions.APPOINTMENT_RESCHEDULED: DomainActivityPolicy(
        "appointments.appointment",
        "Appointment rescheduled",
        "You rescheduled your appointment.",
        "Your appointment was rescheduled.",
        "You rescheduled an appointment.",
    ),
    actions.APPOINTMENT_REASSIGNED: DomainActivityPolicy(
        "appointments.appointment",
        "Appointment reassigned",
        student_affected="Your appointment was reassigned.",
        staff_self="You reassigned an appointment.",
    ),
    actions.APPOINTMENT_COMPLETED: DomainActivityPolicy(
        "appointments.appointment",
        "Appointment completed",
        student_affected="Your appointment was marked as completed.",
        staff_self="You marked an appointment as completed.",
    ),
    actions.APPOINTMENT_NO_SHOW: DomainActivityPolicy(
        "appointments.appointment",
        "Appointment marked as no-show",
        student_affected="Your appointment was marked as a no-show.",
        staff_self="You marked an appointment as a no-show.",
    ),
    actions.INVENTORY_CREATED: DomainActivityPolicy(
        "inventory.studentinventory",
        "Individual Inventory started",
        student_self="You started your Individual Inventory.",
    ),
    actions.INVENTORY_SUBMITTED: DomainActivityPolicy(
        "inventory.studentinventory",
        "Individual Inventory submitted",
        student_self="You submitted your Individual Inventory.",
    ),
    actions.INVENTORY_RESUBMITTED: DomainActivityPolicy(
        "inventory.studentinventory",
        "Individual Inventory resubmitted",
        student_self="You resubmitted your Individual Inventory.",
    ),
    actions.INVENTORY_REOPENED: DomainActivityPolicy(
        "inventory.studentinventory",
        "Individual Inventory returned for correction",
        student_affected="Your Individual Inventory was returned for correction.",
        staff_self="You returned an Individual Inventory for correction.",
        staff_roles=frozenset({COUNSELOR}),
    ),
    actions.GOOD_MORAL_REQUEST_CREATED: DomainActivityPolicy(
        "goodmoral.request",
        "Good Moral certificate requested",
        student_self="You requested a Good Moral certificate.",
        student_affected="The Guidance and Counseling Office started a Good Moral request for you.",
        staff_self="You started a Good Moral request for a Student.",
    ),
    actions.GOOD_MORAL_REQUEST_UPDATED: DomainActivityPolicy(
        "goodmoral.request",
        "Good Moral request updated",
        student_affected="Your Good Moral request was updated.",
        staff_self="You updated a Good Moral request.",
    ),
    actions.GOOD_MORAL_PREPARED: DomainActivityPolicy(
        "goodmoral.request",
        "Good Moral certificate prepared",
        student_affected="Your Good Moral certificate was prepared.",
        staff_self="You prepared a Good Moral certificate.",
    ),
    actions.GOOD_MORAL_RETURNED_TO_PREPARATION: DomainActivityPolicy(
        "goodmoral.request",
        "Good Moral request returned for preparation",
        student_affected="Your Good Moral request was returned for preparation.",
        staff_self="You returned a Good Moral request for preparation.",
    ),
    actions.GOOD_MORAL_REQUEST_CANCELLED: DomainActivityPolicy(
        "goodmoral.request",
        "Good Moral request cancelled",
        "You cancelled your Good Moral request.",
        "Your Good Moral request was cancelled.",
        "You cancelled a Good Moral request.",
        frozenset({COUNSELOR}),
    ),
    actions.GOOD_MORAL_ISSUED: DomainActivityPolicy(
        "goodmoral.request",
        "Good Moral certificate issued",
        student_affected="Your Good Moral certificate was issued.",
        staff_self="You issued a Good Moral certificate.",
        staff_roles=frozenset({COUNSELOR}),
    ),
    actions.EXIT_INTERVIEW_CREATED: DomainActivityPolicy(
        "exitinterviews.exitinterview",
        "Exit Interview started",
        student_self="You started your Exit Interview.",
    ),
    actions.EXIT_INTERVIEW_SUBMITTED: DomainActivityPolicy(
        "exitinterviews.exitinterview",
        "Exit Interview submitted",
        student_self="You submitted your Exit Interview.",
    ),
    actions.EXIT_INTERVIEW_RESUBMITTED: DomainActivityPolicy(
        "exitinterviews.exitinterview",
        "Exit Interview resubmitted",
        student_self="You resubmitted your Exit Interview.",
    ),
    actions.EXIT_INTERVIEW_REOPENED: DomainActivityPolicy(
        "exitinterviews.exitinterview",
        "Exit Interview returned for correction",
        student_affected="Your Exit Interview was returned for correction.",
        staff_self="You returned an Exit Interview for correction.",
        staff_roles=frozenset({COUNSELOR}),
    ),
    actions.ROUTINE_INTERVIEW_CREATED: DomainActivityPolicy(
        "routine.interview",
        "Routine Interview intake started",
        student_self="You started your Routine Interview intake.",
    ),
    actions.ROUTINE_INTERVIEW_INTAKE_SUBMITTED: DomainActivityPolicy(
        "routine.interview",
        "Routine Interview intake submitted",
        student_self="You submitted your Routine Interview intake.",
    ),
    actions.REFERRAL_CREATED: DomainActivityPolicy(
        "referrals.referral",
        "Referral recorded",
        staff_self="You recorded a referral.",
    ),
    actions.REFERRAL_STATUS_UPDATED: DomainActivityPolicy(
        "referrals.referral",
        "Referral status updated",
        staff_self="You updated a referral status note.",
    ),
    actions.REFERRAL_ACTION_RECORDED: DomainActivityPolicy(
        "referrals.referralaction",
        "Referral action recorded",
        staff_self="You recorded an operational referral action.",
    ),
    actions.REFERRAL_VOIDED: DomainActivityPolicy(
        "referrals.referral",
        "Referral voided",
        staff_self="You voided a referral.",
    ),
    actions.CALL_SLIP_CREATED: DomainActivityPolicy(
        "callslips.callslip",
        "Call Slip recorded",
        student_affected="A Call Slip was recorded for you.",
        staff_self="You recorded a Call Slip.",
    ),
    actions.CALL_SLIP_VOIDED: DomainActivityPolicy(
        "callslips.callslip",
        "Call Slip voided",
        student_affected="Your Call Slip was voided.",
        staff_self="You voided a Call Slip.",
    ),
}


def _source_queries(user, capabilities):
    """Return only source rows the viewer may currently read, without loading their content."""
    sources = {}
    if user.role.code == STUDENT:
        for target, model, capability in (
            ("appointments.appointment", Appointment, "appointments.view_self"),
            ("inventory.studentinventory", StudentInventory, "inventory.view_self"),
            ("goodmoral.request", GoodMoralRequest, "good_moral.view_self"),
            ("exitinterviews.exitinterview", ExitInterview, "exit_interviews.view_self"),
            ("routine.interview", RoutineInterview, "routine_interviews.view_self"),
            ("callslips.callslip", CallSlip, "call_slips.view_self"),
        ):
            if capability in capabilities:
                sources[target] = model.objects.filter(student_id=user.pk)
    elif user.role.code in OPERATIONAL:
        if "appointments.manage" in capabilities:
            sources["appointments.appointment"] = scope_managed_appointments(
                Appointment.objects.all(), user
            )
        if "good_moral.view" in capabilities:
            sources["goodmoral.request"] = GoodMoralRequest.objects.all()
        if "call_slips.view" in capabilities:
            sources["callslips.callslip"] = scope_call_slips(CallSlip.objects.all(), user)
        if "referrals.view" in capabilities:
            referrals = scope_referrals(Referral.objects.all(), user)
            sources["referrals.referral"] = referrals
            sources["referrals.referralaction"] = ReferralAction.objects.filter(
                referral_id__in=referrals.values("pk")
            )
        if user.role.code == COUNSELOR:
            if "inventory.view" in capabilities:
                sources["inventory.studentinventory"] = StudentInventory.objects.filter(
                    student_id__in=inventory_students(user).values("pk")
                )
            if "exit_interviews.view" in capabilities:
                sources["exitinterviews.exitinterview"] = ExitInterview.objects.all()
    return sources


def domain_selection_filter(*, user) -> Q:
    if not user.is_active or user.role.code not in {STUDENT, *OPERATIONAL}:
        return Q(pk__in=[])
    sources = _source_queries(user, effective_capabilities(user))
    selection = Q(pk__in=[])
    for action, policy in DOMAIN_ACTIVITY_POLICIES.items():
        source = sources.get(policy.target_type)
        if source is None:
            continue
        relationship = Q(actor_user_id=user.pk)
        if user.role.code == STUDENT:
            if policy.student_affected is not None:
                # The source subquery has already restricted canonical Student ownership.
                relationship = Q()
            elif policy.student_self is None:
                continue
        elif policy.staff_self is None or user.role.code not in policy.staff_roles:
            continue
        if action == actions.GOOD_MORAL_REQUEST_CREATED:
            # Affected-party copy requires persisted assisted provenance and the actual initiator.
            source = source.filter(
                Q(
                    student_id=OuterRef("actor_user_id"),
                    initiation_origin__in=(
                        GoodMoralInitiationOrigin.STUDENT_SELF,
                        GoodMoralInitiationOrigin.LEGACY_UNSPECIFIED,
                    ),
                )
                | Q(
                    initiation_origin=GoodMoralInitiationOrigin.GCO_ASSISTED,
                    initiated_by_id=OuterRef("actor_user_id"),
                )
            )
        target_ids = Subquery(
            source.order_by()
            .annotate(_activity_id=Cast("pk", output_field=CharField(max_length=36)))
            .values("_activity_id")
        )
        selection |= Q(
            relationship,
            action=action,
            actor_type=AuditActorType.USER,
            outcome=AuditOutcome.SUCCESS,
            target_type=policy.target_type,
            target_id__in=target_ids,
        )
    return selection
