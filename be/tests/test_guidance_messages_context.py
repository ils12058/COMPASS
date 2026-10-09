"""Appointment-context resolver for contextual Guidance Messages (ADR-103), synthetic text only."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.utils import timezone

from compass.appointments.models import Appointment
from compass.guidance_messages import services
from compass.guidance_messages.errors import ThreadNotFound
from compass.guidance_messages.models import GuidanceMessage, GuidanceThread
from compass.service_catalog.models import Service
from tests.test_guidance_messages import BASE, BODY, counseling, deny, post, world  # noqa: F401
from tests.test_notifications import auth_client

pytestmark = pytest.mark.django_db


def context_path(appointment_id):
    return f"{BASE}/appointments/{appointment_id}/context"


def resolve(world, actor):  # noqa: F811
    return services.appointment_context(
        actor=getattr(world, actor) if isinstance(actor, str) else actor,
        appointment_id=world.appointment.pk,
    )


# ── Existing thread ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("actor", ["student", "counselor"])
def test_existing_thread_resolves_for_persisted_participants(world, actor):  # noqa: F811
    thread, _ = counseling(world)
    resolved, can_start = resolve(world, actor)
    assert resolved.pk == thread.pk
    assert can_start is False
    response = auth_client(getattr(world, actor)).get(context_path(world.appointment.pk))
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private"
    payload = response.json()
    assert set(payload) == {"thread", "can_start"}
    assert payload["can_start"] is False
    assert payload["thread"]["id"] == str(thread.pk)
    assert payload["thread"]["kind"] == "COUNSELING"
    assert payload["thread"]["relationship_appointment_id"] == str(world.appointment.pk)
    assert set(payload["thread"]) == {
        "id",
        "kind",
        "status",
        "student",
        "counselor",
        "routing_college",
        "assigned_to",
        "relationship_appointment_id",
        "created_at",
        "last_message_at",
        "last_sequence",
        "own_last_read_sequence",
        "unread_count",
    }
    assert BODY.strip() not in response.content.decode()
    assert "email" not in response.content.decode()


@pytest.mark.parametrize(
    "actor", ["gss", "other", "head", "head_gss", "other_student", "admin", "dpo"]
)
def test_existing_thread_is_concealed_from_everyone_else(world, actor):  # noqa: F811
    counseling(world)
    with pytest.raises(ThreadNotFound):
        resolve(world, actor)
    response = auth_client(getattr(world, actor)).get(context_path(world.appointment.pk))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "guidance_thread_not_found"
    assert response["Cache-Control"] == "no-store, private"


def test_guessed_appointment_is_concealed(world):  # noqa: F811
    counseling(world)
    for actor in [world.student, world.counselor]:
        with pytest.raises(ThreadNotFound):
            services.appointment_context(actor=actor, appointment_id=uuid4())
        assert auth_client(actor).get(context_path(uuid4())).status_code == 404
    assert auth_client(world.student).get(context_path("not-a-uuid")).status_code == 422


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW", "COMPLETED"])
def test_lifecycle_change_keeps_existing_participant_access(world, status):  # noqa: F811
    thread, _ = counseling(world)
    stamp = {"CANCELLED": "cancelled_at", "NO_SHOW": "no_show_at", "COMPLETED": "completed_at"}
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status=status, **{stamp[status]: timezone.now()}
    )
    for actor in ["student", "counselor"]:
        resolved, can_start = resolve(world, actor)
        assert resolved.pk == thread.pk and can_start is False


def test_reassignment_never_transfers_the_existing_thread(world):  # noqa: F811
    thread, _ = counseling(world)
    Appointment.objects.filter(pk=world.appointment.pk).update(provider=world.other)
    # The persisted Counselor keeps the conversation; the new provider gains nothing.
    assert resolve(world, "counselor")[0].pk == thread.pk
    assert resolve(world, "student")[0].pk == thread.pk
    with pytest.raises(ThreadNotFound):
        resolve(world, "other")
    response = auth_client(world.other).get(context_path(world.appointment.pk))
    assert response.status_code == 404
    assert BODY.strip() not in response.content.decode()
    # Nor can the new provider create a second thread for the same Appointment.
    with pytest.raises(ThreadNotFound):
        services.open_counseling_thread(
            actor=world.other,
            appointment_id=world.appointment.pk,
            client_message_id=uuid4(),
            body=BODY,
        )
    assert GuidanceThread.objects.filter(relationship_appointment=world.appointment).count() == 1


def test_view_only_participant_reads_but_cannot_start(world):  # noqa: F811
    thread, _ = counseling(world)
    deny(world.student, "guidance_messages.manage_self")
    resolved, can_start = resolve(world, "student")
    assert resolved.pk == thread.pk and can_start is False


# ── No thread yet ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("actor", ["student", "counselor"])
def test_eligible_participant_may_start_without_creating_anything(world, actor):  # noqa: F811
    assert resolve(world, actor) == (None, True)
    response = auth_client(getattr(world, actor)).get(context_path(world.appointment.pk))
    assert response.status_code == 200
    assert response.json() == {"thread": None, "can_start": True}
    assert response["Cache-Control"] == "no-store, private"
    assert not GuidanceThread.objects.exists()
    assert not GuidanceMessage.objects.exists()


@pytest.mark.parametrize(
    "actor", ["gss", "other", "head", "head_gss", "other_student", "admin", "dpo"]
)
def test_unrelated_actor_cannot_learn_a_startable_relationship(world, actor):  # noqa: F811
    with pytest.raises(ThreadNotFound):
        resolve(world, actor)
    assert (
        auth_client(getattr(world, actor)).get(context_path(world.appointment.pk)).status_code
        == 404
    )


@pytest.mark.parametrize(
    "fault",
    [
        "CANCELLED",
        "NO_SHOW",
        "service",
        "inactive_provider",
        "provider_role",
        "provider_view",
        "inactive_student",
    ],
)
def test_ineligible_relationship_without_thread_fails_closed(world, fault):  # noqa: F811
    if fault in ["CANCELLED", "NO_SHOW"]:
        field = "cancelled_at" if fault == "CANCELLED" else "no_show_at"
        Appointment.objects.filter(pk=world.appointment.pk).update(
            status=fault, **{field: timezone.now()}
        )
    elif fault == "service":
        other_service = Service.objects.create(code="GM-CONTEXT", name="Synthetic Other Service")
        Appointment.objects.filter(pk=world.appointment.pk).update(service=other_service)
    elif fault == "inactive_provider":
        type(world.counselor).objects.filter(pk=world.counselor.pk).update(is_active=False)
    elif fault == "provider_role":
        Appointment.objects.filter(pk=world.appointment.pk).update(provider=world.gss)
    elif fault == "provider_view":
        deny(world.counselor, "guidance_messages.view")
    else:
        type(world.student).objects.filter(pk=world.student.pk).update(is_active=False)
    with pytest.raises(ThreadNotFound):
        resolve(world, "student" if fault != "inactive_student" else "counselor")
    assert not GuidanceThread.objects.exists()


@pytest.mark.parametrize(
    "actor,code",
    [("student", "guidance_messages.manage_self"), ("counselor", "guidance_messages.manage")],
)
def test_participant_without_manage_cannot_start(world, actor, code):  # noqa: F811
    deny(getattr(world, actor), code)
    with pytest.raises(ThreadNotFound):
        resolve(world, actor)
    assert (
        auth_client(getattr(world, actor)).get(context_path(world.appointment.pk)).status_code
        == 404
    )


def test_first_send_revalidates_after_a_startable_context(world):  # noqa: F811
    assert resolve(world, "student") == (None, True)
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status="CANCELLED", cancelled_at=timezone.now()
    )
    client = auth_client(world.student)
    response = post(
        client,
        f"/appointments/{world.appointment.pk}/counseling-thread",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 404
    assert not GuidanceThread.objects.exists()
    with pytest.raises(ThreadNotFound):
        resolve(world, "student")


def test_reassignment_before_first_send_moves_startability_not_history(world):  # noqa: F811
    assert resolve(world, "counselor") == (None, True)
    Appointment.objects.filter(pk=world.appointment.pk).update(provider=world.other)
    with pytest.raises(ThreadNotFound):
        resolve(world, "counselor")
    assert resolve(world, "other") == (None, True)
    with pytest.raises(ThreadNotFound):
        services.open_counseling_thread(
            actor=world.counselor,
            appointment_id=world.appointment.pk,
            client_message_id=uuid4(),
            body=BODY,
        )
    assert not GuidanceThread.objects.exists()


def test_start_then_resolve_returns_the_one_canonical_thread(world):  # noqa: F811
    assert resolve(world, "student") == (None, True)
    client = auth_client(world.student)
    response = post(
        client,
        f"/appointments/{world.appointment.pk}/counseling-thread",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 200
    thread_id = response.json()["thread"]["id"]
    for actor in [world.student, world.counselor]:
        payload = auth_client(actor).get(context_path(world.appointment.pk)).json()
        assert payload["thread"]["id"] == thread_id and payload["can_start"] is False
    services.set_status(actor=world.counselor, thread_id=thread_id, resolved=True)
    resolved, can_start = resolve(world, "student")
    assert str(resolved.pk) == thread_id and resolved.status == "RESOLVED" and can_start is False
    assert GuidanceThread.objects.count() == 1


def test_resolver_requires_a_session(world):  # noqa: F811
    from django.test import Client

    assert Client().get(context_path(world.appointment.pk)).status_code == 401
