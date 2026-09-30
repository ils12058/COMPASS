from __future__ import annotations

from datetime import time, timedelta

import pytest

from compass.availability.services import (
    compute_base_availability,
    create_office_exception,
    create_provider_exception,
    replace_office_weekly,
    replace_provider_weekly,
)
from tests.test_appointments import (
    active_service,
    context,
    create_list_appointment,
    future_local_start,
    make_user,
    sync_policy,
    weekly,
)


def _setup_reservation():
    sync_policy()
    actor = make_user("availability-admin@example.edu", "IT_ADMIN")
    provider = make_user("availability-provider@example.edu", "COUNSELOR")
    student = make_user("availability-student@example.edu", "STUDENT")
    service = active_service(
        actor,
        code="AVAILABILITY_NEUTRAL",
        delivery_modes=["IN_PERSON"],
    )
    replace_office_weekly(windows=[weekly()], context=context(actor))
    replace_provider_weekly(
        provider_id=provider.pk,
        windows=[weekly()],
        context=context(actor),
    )
    starts_at = future_local_start()
    appointment = create_list_appointment(
        reference_code="APT-AVAILABILITY-NEUTRAL",
        student=student,
        provider=provider,
        service=service,
        starts_at=starts_at,
        delivery_mode="IN_PERSON",
    )
    return actor, provider, service, appointment


def _snapshot(appointment) -> tuple[object, ...]:
    appointment.refresh_from_db()
    return (
        appointment.status,
        appointment.starts_at,
        appointment.ends_at,
        appointment.provider_id,
        appointment.student_id,
        appointment.service_id,
        appointment.delivery_mode,
    )


def _interval_remains_bookable(*, provider, service, appointment) -> bool:
    result = compute_base_availability(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode=appointment.delivery_mode,
        start_date=appointment.starts_at.date(),
        end_date=appointment.starts_at.date() + timedelta(days=1),
    )
    return any(
        window.starts_at <= appointment.starts_at and window.ends_at >= appointment.ends_at
        for window in result.windows
    )


@pytest.mark.django_db
def test_provider_weekly_narrowing_changes_future_bookability_not_existing_reservation():
    actor, provider, service, appointment = _setup_reservation()
    before = _snapshot(appointment)
    assert _interval_remains_bookable(
        provider=provider,
        service=service,
        appointment=appointment,
    )

    replace_provider_weekly(
        provider_id=provider.pk,
        windows=[weekly(start=time(12), end=time(17))],
        context=context(actor),
    )

    assert _snapshot(appointment) == before
    assert not _interval_remains_bookable(
        provider=provider,
        service=service,
        appointment=appointment,
    )


@pytest.mark.django_db
def test_office_weekly_narrowing_changes_future_bookability_not_existing_reservation():
    actor, provider, service, appointment = _setup_reservation()
    before = _snapshot(appointment)

    replace_office_weekly(
        windows=[weekly(start=time(12), end=time(17))],
        context=context(actor),
    )

    assert _snapshot(appointment) == before
    assert not _interval_remains_bookable(
        provider=provider,
        service=service,
        appointment=appointment,
    )


@pytest.mark.django_db
def test_provider_unavailability_changes_future_bookability_not_existing_reservation():
    actor, provider, service, appointment = _setup_reservation()
    before = _snapshot(appointment)

    create_provider_exception(
        provider_id=provider.pk,
        starts_at=appointment.starts_at - timedelta(hours=1),
        ends_at=appointment.ends_at + timedelta(hours=1),
        mode_scope="ALL",
        reason="Operational unavailability",
        context=context(actor),
    )

    assert _snapshot(appointment) == before
    assert not _interval_remains_bookable(
        provider=provider,
        service=service,
        appointment=appointment,
    )


@pytest.mark.django_db
def test_office_unavailability_changes_future_bookability_not_existing_reservation():
    actor, provider, service, appointment = _setup_reservation()
    before = _snapshot(appointment)

    create_office_exception(
        starts_at=appointment.starts_at - timedelta(hours=1),
        ends_at=appointment.ends_at + timedelta(hours=1),
        mode_scope="ALL",
        reason="Office closure",
        context=context(actor),
    )

    assert _snapshot(appointment) == before
    assert not _interval_remains_bookable(
        provider=provider,
        service=service,
        appointment=appointment,
    )
