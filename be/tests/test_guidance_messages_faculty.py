"""GMSG-2: a Faculty inquiry reaches General Guidance intake and nobody else."""

from __future__ import annotations

from uuid import uuid4

import pytest
from compass.accounts.models import Designation, Role, User
from compass.accounts.services import effective_capabilities
from compass.audit.models import AuditEvent
from compass.guidance_messages import content, policy, services, work
from compass.guidance_messages.errors import (
    MessagesConflict,
    MessagesPermissionDenied,
    ThreadNotFound,
)
from compass.guidance_messages.models import (
    GuidanceMessage,
    GuidanceThread,
    ThreadKind,
    ThreadStatus,
)
from tests.test_guidance_messages import (  # noqa: F401
    BASE,
    BODY,
    auth_client,
    deny,
    office,
    post,
    world,
)

# Imported world fixture is injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db

INTAKE = "GENERAL_GUIDANCE_INTAKE"
CAP = "You already have 5 open Guidance Office inquiries."
UNAVAILABLE = "Guidance Office intake is currently unavailable."


def faculty():
    return User.objects.create_user(
        email=f"gm-faculty-{uuid4().hex}@example.edu",
        password=None,
        role=Role.objects.get(code="FACULTY"),
        first_name="Synthetic",
        last_name="Faculty",
    )


def with_intake(user):
    """An intake holder is a staff account plus the designation; no role grants intake."""
    user.designations.add(Designation.objects.get(code=INTAKE))
    return user


def inquiry(actor, client_id=None):
    return services.open_faculty_inquiry(
        actor=actor, client_message_id=client_id or uuid4(), body=BODY
    )


def open_inquiry(world, actor=None, intake_holder=None):
    holder = intake_holder if intake_holder is not None else with_intake(world.other)
    requester = actor if actor is not None else faculty()
    thread, message = inquiry(requester)
    return requester, holder, thread, message


def test_faculty_opens_an_inquiry_by_service_and_http(world):
    requester, _, thread, message = open_inquiry(world)

    assert thread.kind == ThreadKind.FACULTY_INQUIRY
    assert thread.status == ThreadStatus.OPEN
    assert thread.requester_id == requester.pk
    assert thread.student_id is None
    assert thread.counselor_id is None
    assert thread.relationship_appointment_id is None
    assert thread.routing_college_id is None
    assert thread.assigned_to_id is None
    assert message.sequence == 1
    assert content.read_body(message) == BODY
    assert BODY not in message.body_ciphertext

    event = AuditEvent.objects.get(
        action="guidance_messages.thread.created", target_id=thread.pk
    )
    assert event.metadata["kind"] == "FACULTY_INQUIRY"

    second = faculty()
    second_thread, _ = inquiry(second)
    assert second_thread.requester_id == second.pk
    payload = post(
        auth_client(second),
        "/faculty-inquiry",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert payload.status_code == 200
    body = payload.json()
    assert body["thread"]["kind"] == "FACULTY_INQUIRY"
    assert body["thread"]["requester"]["id"] == str(second.pk)
    assert body["thread"]["student"] is None
    assert body["thread"]["counselor"] is None
    assert body["thread"]["routing_college"] is None
    assert body["thread"]["assigned_to"] is None
    assert body["message"]["sequence"] == 1
    assert body["message"]["body"] == BODY


@pytest.mark.parametrize(
    "name", ["student", "counselor", "gss", "head", "admin", "dpo"],
)
def test_only_faculty_may_open_an_inquiry(world, name):
    with_intake(world.other)
    actor = getattr(world, name)
    with pytest.raises(MessagesPermissionDenied):
        inquiry(actor)
    response = post(
        auth_client(actor), "/faculty-inquiry", {"client_message_id": str(uuid4()), "body": BODY}
    )
    assert response.status_code == 403
    assert not GuidanceThread.objects.filter(kind=ThreadKind.FACULTY_INQUIRY).exists()


def test_managing_inquiries_needs_the_manage_capability(world):
    with_intake(world.other)
    actor = faculty()
    assert {"guidance_messages.inquiry_view_self", "guidance_messages.inquiry_manage_self"} <= (
        effective_capabilities(actor)
    )
    deny(actor, "guidance_messages.inquiry_manage_self")
    after = effective_capabilities(actor)
    assert "guidance_messages.inquiry_view_self" in after
    assert "guidance_messages.inquiry_manage_self" not in after

    with pytest.raises(MessagesPermissionDenied):
        inquiry(actor)
    response = post(
        auth_client(actor), "/faculty-inquiry", {"client_message_id": str(uuid4()), "body": BODY}
    )
    assert response.status_code == 403
    assert auth_client(actor).get(f"{BASE}/threads").status_code == 200


def test_replay_returns_the_original_inquiry(world):
    requester, _, thread, message = open_inquiry(world)
    client_id = message.client_message_id

    replayed_thread, replayed = inquiry(requester, client_id)
    assert (replayed_thread.pk, replayed.pk) == (thread.pk, message.pk)
    assert GuidanceThread.objects.count() == 1
    assert GuidanceMessage.objects.count() == 1


def test_a_client_id_used_by_an_office_thread_conflicts(world):
    # Reachable only after a role change: a sender's client id is globally unique, so the family
    # check matters for an account that once wrote as staff and now writes as Faculty.
    holder = with_intake(world.counselor)
    thread, message = services.open_office_thread(
        actor=holder, student_id=world.student.pk, client_message_id=uuid4(), body=BODY
    )
    holder.role = Role.objects.get(code="FACULTY")
    holder.save(update_fields=("role",))

    with pytest.raises(MessagesConflict):
        inquiry(holder, message.client_message_id)
    assert GuidanceThread.objects.filter(kind=ThreadKind.FACULTY_INQUIRY).count() == 0
    assert thread.messages.count() == 1


def test_creation_waits_for_an_intake_holder(world):
    actor = faculty()
    assert not policy.has_intake_staff()
    with pytest.raises(MessagesConflict, match=UNAVAILABLE):
        inquiry(actor)
    assert GuidanceThread.objects.count() == 0

    with_intake(world.gss)
    assert policy.has_intake_staff()
    thread, _ = inquiry(actor)
    assert thread.requester_id == actor.pk


def test_intake_by_capability_only_is_not_enough(world):
    # `guidance_messages.manage` is broad Office authority; it never implies intake.
    assert world.counselor.has_capability("guidance_messages.manage")
    assert not policy.has_intake_staff()
    with pytest.raises(MessagesConflict, match=UNAVAILABLE):
        inquiry(faculty())


def test_five_open_inquiries_is_the_cap(world):
    holder = with_intake(world.other)
    actor = faculty()
    threads = [inquiry(actor)[0] for _ in range(5)]
    assert all(thread.status == ThreadStatus.OPEN for thread in threads)

    with pytest.raises(MessagesConflict, match=CAP):
        inquiry(actor)

    services.set_status(actor=holder, thread_id=threads[0].pk, resolved=True)
    sixth = inquiry(actor)[0]
    assert sixth.status == ThreadStatus.OPEN

    # Reopening is deliberately not cap-checked: resolving must stay a safe act for the requester.
    services.set_status(actor=actor, thread_id=threads[0].pk, resolved=False)
    assert GuidanceThread.objects.filter(requester=actor, status=ThreadStatus.OPEN).count() == 6


@pytest.mark.parametrize("name", ["counselor", "gss", "head", "admin", "dpo"])
def test_inquiries_are_concealed_from_staff_without_intake(world, name):
    _, _, thread, _ = open_inquiry(world)
    actor = getattr(world, name)
    client = auth_client(actor)
    assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 404
    assert client.get(f"{BASE}/threads/{thread.pk}/messages").status_code == 404
    assert post(client, f"/threads/{thread.pk}/resolve", {}).status_code == 404
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=actor, thread_id=thread.pk)
    if actor.role.code in policy.STAFF_ROLES:
        # A staff directory loads; the inquiry simply is not in it.
        assert thread.pk not in {row.pk for row in services.list_threads(actor=actor)[0]}
    else:
        # Outside roles fail the capability gate before any thread question is asked.
        assert auth_client(actor).get(f"{BASE}/threads").status_code == 403
        with pytest.raises(MessagesPermissionDenied):
            services.list_threads(actor=actor)


def test_inquiries_are_concealed_from_other_faculty(world):
    requester, holder, thread, _ = open_inquiry(world)
    stranger = faculty()
    client = auth_client(stranger)
    assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 404
    assert post(client, f"/threads/{thread.pk}/messages", {"body": BODY}).status_code == 422
    assert post(
        client,
        f"/threads/{thread.pk}/messages",
        {"client_message_id": str(uuid4()), "body": BODY},
    ).status_code == 404
    assert post(client, f"/threads/{thread.pk}/resolve", {}).status_code == 404
    with pytest.raises(ThreadNotFound):
        services.send_message(
            actor=stranger, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
    assert [row.pk for row in services.list_threads(actor=stranger)[0]] == []
    assert [row.pk for row in services.list_threads(actor=requester)[0]] == [thread.pk]
    assert {row.pk for row in services.list_threads(actor=holder)[0]} == {thread.pk}
    assert client.get(f"{BASE}/threads/{uuid4()}").status_code == 404


def test_recipients_are_the_requester_and_effective_intake_only(world):
    requester, holder, thread, _ = open_inquiry(world)
    sidelined = with_intake(world.gss)
    deny(sidelined, "guidance_messages.intake")

    assert set(policy.recipient_ids(thread)) == {requester.pk, holder.pk}
    assert thread.pk is not None
    for actor in (world.counselor, world.head, world.student, sidelined):
        assert actor.pk not in set(policy.recipient_ids(thread))


def test_requester_and_intake_change_status(world):
    requester, holder, thread, _ = open_inquiry(world)

    resolved = services.set_status(actor=requester, thread_id=thread.pk, resolved=True)
    assert resolved.status == ThreadStatus.RESOLVED
    with pytest.raises(MessagesConflict):
        services.send_message(
            actor=requester, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )

    reopened = services.set_status(actor=holder, thread_id=thread.pk, resolved=False)
    assert reopened.status == ThreadStatus.OPEN
    assert services.send_message(
        actor=holder, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
    ).sequence == 2

    with pytest.raises(ThreadNotFound):
        services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    assert (
        post(auth_client(world.counselor), f"/threads/{thread.pk}/resolve", {}).status_code == 404
    )
    assert post(auth_client(requester), f"/threads/{thread.pk}/resolve", {}).status_code == 200
    assert post(auth_client(holder), f"/threads/{thread.pk}/reopen", {}).status_code == 200


def test_directory_and_unread_counts(world):
    requester, holder, thread, _ = open_inquiry(world)
    other_requester, _, other_thread, _ = open_inquiry(world, intake_holder=holder)

    assert [row.pk for row in services.list_threads(actor=requester)[0]] == [thread.pk]
    assert {row.pk for row in services.list_threads(actor=holder)[0]} == {
        thread.pk,
        other_thread.pk,
    }
    assert services.list_threads(actor=world.counselor)[0] == []

    services.send_message(actor=holder, thread_id=thread.pk, client_message_id=uuid4(), body=BODY)
    assert services.count_unread_conversations(actor=requester) == 1
    assert services.count_unread_conversations(actor=holder) == 2
    assert services.count_unread_conversations(actor=world.counselor) == 0
    assert services.get_thread(actor=requester, thread_id=thread.pk).own_unread_count == 1

    services.mark_read(actor=requester, thread_id=thread.pk, sequence=thread.last_sequence + 1)
    assert services.count_unread_conversations(actor=requester) == 0


def test_handler_identity_and_routing_stay_staff_only(world):
    thread, _ = office(world)
    student_payload = auth_client(world.student).get(f"{BASE}/threads/{thread.pk}").json()
    assert student_payload["assigned_to"] is None
    assert student_payload["routing_college"] is None
    assert set(student_payload) >= {"assigned_to", "routing_college"}

    staff_payload = auth_client(world.counselor).get(f"{BASE}/threads/{thread.pk}").json()
    assert staff_payload["assigned_to"]["id"] == str(thread.assigned_to_id)
    assert staff_payload["routing_college"]["id"] == str(thread.routing_college_id)

    requester, holder, inquiry_thread, _ = open_inquiry(world)
    assert inquiry_thread.routing_college_id is None and inquiry_thread.assigned_to_id is None
    for actor in (holder, requester):
        payload = auth_client(actor).get(f"{BASE}/threads/{inquiry_thread.pk}").json()
        assert payload["requester"]["id"] == str(requester.pk)
        assert payload["assigned_to"] is None
        assert payload["routing_college"] is None


def test_reply_work_queue_excludes_inquiries(world):
    requester, holder, thread, _ = open_inquiry(world)
    assert [row.pk for row in services.list_threads(actor=holder)[0]] == [thread.pk]
    assert thread.pk in {row.pk for row in policy.authorized_threads(holder, manage=True)}

    assert work.reply_needed_summary(actor=holder).count == 0
    assert work.reply_needed_threads(actor=holder, limit=10) == ()
    assert requester.pk != holder.pk
