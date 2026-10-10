"""Local consent and access-window facts only; no Daily client, credential or room query."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Min

from compass.accounts.services import is_current_student
from compass.appointments.models import AppointmentStatus
from compass.counseling.services import CounselingConfigurationConflict, get_counseling_service
from compass.service_catalog.models import DeliveryMode

from .models import ConsentDecision, ECounselingConsent
from .services import _appointment_queryset, ecounseling_access_window


def pending_consents(*, student, limit):
    if (
        not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability("ecounseling.consent_self")
    ):
        return ()
    # Consent decisions permit denial even after current lifecycle ends. No schedule/status gate.
    return tuple(
        ECounselingConsent.objects.filter(
            room__appointment__student_id=student.pk,
            room__appointment__service__code="COUNSELING",
            room__appointment__delivery_mode=DeliveryMode.ONLINE,
            decision=ConsentDecision.PENDING,
            withdrawn_at__isnull=True,
        )
        .values("room__appointment_id")
        .annotate(
            pending_count=Count("id"),
            waiting_since=Min("requested_at"),
        )
        .order_by("waiting_since", "room__appointment_id")[:limit]
    )


def open_join_windows(*, student, now, limit):
    if (
        not is_current_student(student)
        or not student.has_capability("ecounseling.join_self")
        or not settings.DAILY_ENABLED
    ):
        return ()
    try:
        service = get_counseling_service(require_active=True)
    except CounselingConfigurationConflict:
        return ()
    # SQL bounds equal the canonical inclusive window and run before LIMIT.
    rows = (
        _appointment_queryset()
        .filter(
            student_id=student.pk,
            service_id=service.pk,
            delivery_mode=DeliveryMode.ONLINE,
            status=AppointmentStatus.SCHEDULED,
            provider__is_active=True,
            provider__role__code="COUNSELOR",
            starts_at__lte=now + timedelta(seconds=settings.ECOUNSELING_JOIN_EARLY_SECONDS),
            ends_at__gte=now - timedelta(seconds=settings.ECOUNSELING_REJOIN_GRACE_SECONDS),
        )
        .only("id", "starts_at", "ends_at")
        .select_related(None)
        .order_by("ends_at", "starts_at", "id")[:limit]
    )
    return tuple((row, ecounseling_access_window(row, now=now)) for row in rows)
