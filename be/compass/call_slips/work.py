"""Due active permits and supervising-Counselor approval work."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import CharField, Count, Exists, Min, OuterRef, Q
from django.db.models.functions import Cast

from compass.notifications.policy import NotificationEvent
from compass.organization.models import StaffSupervision

from .models import CallSlip, CallSlipApprovalStatus
from .services import _active_operational_queryset, _student_in_scope


@dataclass(frozen=True, slots=True)
class DueCallSlipSummary:
    count: int
    oldest_due_at: datetime | None


def _due_queryset(*, actor, now):
    rows = _active_operational_queryset(actor)
    return None if rows is None else rows.filter(report_at__lte=now)


def due_call_slip_summary(*, actor, now) -> DueCallSlipSummary | None:
    rows = _due_queryset(actor=actor, now=now)
    if rows is None:
        return None
    return DueCallSlipSummary(**rows.aggregate(count=Count("pk"), oldest_due_at=Min("report_at")))


def due_call_slips(*, actor, now, limit):
    rows = _due_queryset(actor=actor, now=now)
    if rows is None:
        return ()
    return tuple(
        rows.select_related("student")
        .only(
            "id",
            "report_at",
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by("report_at", "id")[:limit]
    )


def pending_call_slip_approvals(*, actor, limit):
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("call_slips.manage")
    ):
        return ()
    supervised_staff_ids = StaffSupervision.objects.filter(
        supervisor_id=actor.pk,
        supervisor__is_active=True,
        supervisor__role__code="COUNSELOR",
    ).values("staff_id")
    return tuple(
        CallSlip.objects.filter(
            voided_at__isnull=True,
            approval_status=CallSlipApprovalStatus.PENDING_APPROVAL,
            recorded_by_id__in=supervised_staff_ids,
        )
        .select_related("student")
        .only(
            "id",
            "report_at",
            "created_at",
            "updated_at",
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by("updated_at", "id")[:limit]
    )


def call_slip_approval_notice_is_current(notification) -> bool:
    recipient = getattr(notification, "recipient", None)
    if (
        recipient is None
        or not recipient.is_active
        or recipient.role.code != "COUNSELOR"
        or not recipient.has_capability("call_slips.manage")
        or notification.target_id is None
    ):
        return False
    item = (
        CallSlip.objects.filter(
            pk=notification.target_id,
            voided_at__isnull=True,
            approval_status=CallSlipApprovalStatus.PENDING_APPROVAL,
        )
        .only("id", "student_id", "recorded_by_id")
        .first()
    )
    if item is None or item.recorded_by_id is None:
        return False
    if not StaffSupervision.objects.filter(
        staff_id=item.recorded_by_id,
        supervisor_id=recipient.pk,
    ).exists():
        return False
    return _student_in_scope(recipient, item.student_id)


def scope_current_call_slip_approval_notifications(queryset, *, actor):
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("call_slips.manage")
    ):
        return queryset.exclude(event_code=NotificationEvent.CALL_SLIP_APPROVAL_REQUESTED)
    supervised_staff_ids = StaffSupervision.objects.filter(
        supervisor_id=actor.pk,
        supervisor__is_active=True,
        supervisor__role__code="COUNSELOR",
    ).values("staff_id")
    current_slip = CallSlip.objects.annotate(
        target_str=Cast("pk", output_field=CharField())
    ).filter(
        target_str=Cast(OuterRef("target_id"), output_field=CharField()),
        voided_at__isnull=True,
        approval_status=CallSlipApprovalStatus.PENDING_APPROVAL,
        recorded_by_id__in=supervised_staff_ids,
    )
    return queryset.filter(
        ~Q(event_code=NotificationEvent.CALL_SLIP_APPROVAL_REQUESTED) | Exists(current_slip)
    )
