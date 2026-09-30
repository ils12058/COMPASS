from __future__ import annotations

import json
import pytest
from django.test import override_settings
from compass.audit.models import AuditEvent
from compass.service_catalog.bootstrap import sync_canonical_services
from compass.service_catalog.models import ServiceDeliveryMode
from compass.service_catalog.services import (
    ServiceSchedulingConsequenceReviewRequired,
    update_service,
)
from tests.test_appointments import (
    active_service,
    context,
    create_list_appointment,
    future_local_start,
    make_user,
    sync_policy,
)
from tests.test_service_catalog import auth_client, csrf


def _appointment_snapshot(item) -> tuple[object, ...]:
    item.refresh_from_db()
    return (
        item.status,
        item.starts_at,
        item.ends_at,
        item.provider_id,
        item.student_id,
        item.service_id,
        item.delivery_mode,
        item.cancellation_cutoff_minutes,
    )


def _future_appointment(
    *, service, provider, student, mode: str = "ONLINE", status: str = "SCHEDULED"
):
    return create_list_appointment(
        reference_code=f"APT-{service.code}-{mode}-{status}",
        student=student,
        provider=provider,
        service=service,
        starts_at=future_local_start(),
        status=status,
        delivery_mode=mode,
    )


@pytest.mark.django_db
def test_ordinary_service_edits_need_no_acknowledgement_and_keep_appointment_snapshots():
    sync_policy()
    actor = make_user("ordinary-admin@example.edu", "IT_ADMIN")
    provider = make_user("ordinary-provider@example.edu", "COUNSELOR")
    student = make_user("ordinary-student@example.edu", "STUDENT")
    service = active_service(actor, code="ORDINARY_EDIT", duration=60, cutoff=30)
    appointment = _future_appointment(
        service=service,
        provider=provider,
        student=student,
        mode="ONLINE",
    )
    before = _appointment_snapshot(appointment)

    updated = update_service(
        service_id=service.pk,
        changes={
            "description": "Updated description",
            "default_duration_minutes": 45,
            "cancellation_cutoff_minutes": 15,
            "requires_current_inventory": True,
        },
        context=context(actor),
    )

    assert updated.description == "Updated description"
    assert updated.default_duration_minutes == 45
    assert updated.cancellation_cutoff_minutes == 15
    assert updated.requires_current_inventory
    assert _appointment_snapshot(appointment) == before


@pytest.mark.django_db
def test_delivery_mode_removal_requires_review_only_when_future_scheduled_dependency_exists():
    sync_policy()
    actor = make_user("mode-admin@example.edu", "IT_ADMIN")
    provider = make_user("mode-provider@example.edu", "COUNSELOR")
    student = make_user("mode-student@example.edu", "STUDENT")
    service = active_service(actor, code="MODE_REVIEW")
    appointment = _future_appointment(
        service=service,
        provider=provider,
        student=student,
        mode="ONLINE",
    )
    before = _appointment_snapshot(appointment)

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired):
        update_service(
            service_id=service.pk,
            changes={"delivery_modes": ["IN_PERSON"]},
            context=context(actor),
        )

    assert set(
        ServiceDeliveryMode.objects.filter(service=service).values_list("mode", flat=True)
    ) == {"IN_PERSON", "ONLINE"}
    assert _appointment_snapshot(appointment) == before

    updated = update_service(
        service_id=service.pk,
        changes={"delivery_modes": ["IN_PERSON"]},
        context=context(actor),
        acknowledge_scheduling_consequences=True,
    )

    assert {row.mode for row in updated.delivery_mode_assignments.all()} == {"IN_PERSON"}
    assert _appointment_snapshot(appointment) == before
    event = AuditEvent.objects.filter(action="service.updated", target_id=str(service.pk)).latest(
        "created_at"
    )
    assert event.metadata["scheduling_consequence_acknowledged"] is True
    assert event.metadata["existing_appointment_dependency_detected"] is True
    assert event.metadata["counseling_online_enabled"] is False


@pytest.mark.django_db
def test_removing_unused_delivery_mode_does_not_require_review():
    sync_policy()
    actor = make_user("unused-admin@example.edu", "IT_ADMIN")
    provider = make_user("unused-provider@example.edu", "COUNSELOR")
    student = make_user("unused-student@example.edu", "STUDENT")
    service = active_service(actor, code="UNUSED_MODE")
    appointment = _future_appointment(
        service=service,
        provider=provider,
        student=student,
        mode="IN_PERSON",
    )
    before = _appointment_snapshot(appointment)

    updated = update_service(
        service_id=service.pk,
        changes={"delivery_modes": ["IN_PERSON"]},
        context=context(actor),
    )

    assert {row.mode for row in updated.delivery_mode_assignments.all()} == {"IN_PERSON"}
    assert _appointment_snapshot(appointment) == before


@pytest.mark.django_db
def test_appointment_policy_none_requires_review_and_preserves_existing_reservation():
    sync_policy()
    actor = make_user("policy-admin@example.edu", "IT_ADMIN")
    provider = make_user("policy-provider@example.edu", "COUNSELOR")
    student = make_user("policy-student@example.edu", "STUDENT")
    service = active_service(actor, code="POLICY_REVIEW")
    appointment = _future_appointment(
        service=service,
        provider=provider,
        student=student,
        mode="IN_PERSON",
    )
    before = _appointment_snapshot(appointment)

    changes = {
        "appointment_policy": "NONE",
        "cancellation_cutoff_minutes": None,
    }
    with pytest.raises(ServiceSchedulingConsequenceReviewRequired):
        update_service(
            service_id=service.pk,
            changes=changes,
            context=context(actor),
        )

    service.refresh_from_db()
    assert service.appointment_policy == "OPTIONAL"
    assert service.cancellation_cutoff_minutes == 30
    assert _appointment_snapshot(appointment) == before

    updated = update_service(
        service_id=service.pk,
        changes=changes,
        context=context(actor),
        acknowledge_scheduling_consequences=True,
    )
    assert updated.appointment_policy == "NONE"
    assert updated.cancellation_cutoff_minutes is None
    assert _appointment_snapshot(appointment) == before


@pytest.mark.django_db
def test_policy_none_ignores_terminal_appointments_and_optional_required_transition():
    sync_policy()
    actor = make_user("terminal-admin@example.edu", "IT_ADMIN")
    provider = make_user("terminal-provider@example.edu", "COUNSELOR")
    student = make_user("terminal-student@example.edu", "STUDENT")
    service = active_service(actor, code="TERMINAL_ONLY")

    for index, status in enumerate(("COMPLETED", "CANCELLED", "NO_SHOW"), start=1):
        create_list_appointment(
            reference_code=f"APT-TERMINAL-{index}",
            student=student,
            provider=provider,
            service=service,
            starts_at=future_local_start(days=7 + index),
            status=status,
            delivery_mode="ONLINE",
        )

    required = update_service(
        service_id=service.pk,
        changes={"appointment_policy": "REQUIRED"},
        context=context(actor),
    )
    assert required.appointment_policy == "REQUIRED"

    none = update_service(
        service_id=service.pk,
        changes={
            "appointment_policy": "NONE",
            "cancellation_cutoff_minutes": None,
        },
        context=context(actor),
    )
    assert none.appointment_policy == "NONE"


@pytest.mark.django_db
def test_mixed_service_update_is_atomic_across_review_boundary():
    sync_policy()
    actor = make_user("atomic-admin@example.edu", "IT_ADMIN")
    provider = make_user("atomic-provider@example.edu", "COUNSELOR")
    student = make_user("atomic-student@example.edu", "STUDENT")
    service = active_service(actor, code="ATOMIC_REVIEW")
    appointment = _future_appointment(
        service=service,
        provider=provider,
        student=student,
        mode="ONLINE",
    )
    original_description = service.description
    before = _appointment_snapshot(appointment)
    changes = {
        "description": "Must commit with delivery mode change",
        "delivery_modes": ["IN_PERSON"],
    }

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired):
        update_service(
            service_id=service.pk,
            changes=changes,
            context=context(actor),
        )

    service.refresh_from_db()
    assert service.description == original_description
    assert set(
        ServiceDeliveryMode.objects.filter(service=service).values_list("mode", flat=True)
    ) == {"IN_PERSON", "ONLINE"}
    assert _appointment_snapshot(appointment) == before

    updated = update_service(
        service_id=service.pk,
        changes=changes,
        context=context(actor),
        acknowledge_scheduling_consequences=True,
    )
    assert updated.description == "Must commit with delivery mode change"
    assert {row.mode for row in updated.delivery_mode_assignments.all()} == {"IN_PERSON"}
    assert _appointment_snapshot(appointment) == before


@pytest.mark.django_db
def test_service_update_api_exposes_stable_review_required_code_and_acknowledgement():
    sync_policy()
    actor = make_user("api-review-admin@example.edu", "IT_ADMIN")
    provider = make_user("api-review-provider@example.edu", "COUNSELOR")
    student = make_user("api-review-student@example.edu", "STUDENT")
    service = active_service(actor, code="API_REVIEW")
    _future_appointment(
        service=service,
        provider=provider,
        student=student,
        mode="ONLINE",
    )
    client = auth_client(actor)
    headers = csrf(client)

    blocked = client.patch(
        f"/api/v1/services/{service.pk}",
        data=json.dumps({"delivery_modes": ["IN_PERSON"]}),
        content_type="application/json",
        **headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "service_scheduling_consequence_review_required"

    acknowledged = client.patch(
        f"/api/v1/services/{service.pk}",
        data=json.dumps(
            {
                "delivery_modes": ["IN_PERSON"],
                "acknowledge_scheduling_consequences": True,
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["delivery_modes"] == ["IN_PERSON"]


@pytest.mark.django_db
@override_settings(DAILY_ENABLED=False)
def test_canonical_counseling_online_requires_review_but_not_provider_readiness():
    sync_policy()
    result = sync_canonical_services()
    service_id = result.service_id

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired):
        update_service(
            service_id=service_id,
            changes={"delivery_modes": ["IN_PERSON", "ONLINE"]},
            context=context(make_user("counseling-admin@example.edu", "IT_ADMIN")),
        )

    actor = make_user("counseling-admin-ack@example.edu", "IT_ADMIN")
    updated = update_service(
        service_id=service_id,
        changes={"delivery_modes": ["IN_PERSON", "ONLINE"]},
        context=context(actor),
        acknowledge_scheduling_consequences=True,
    )
    assert {row.mode for row in updated.delivery_mode_assignments.all()} == {
        "IN_PERSON",
        "ONLINE",
    }

    unrelated = update_service(
        service_id=service_id,
        changes={"description": "Online Counseling remains provider-independent."},
        context=context(actor),
    )
    assert unrelated.description == "Online Counseling remains provider-independent."
