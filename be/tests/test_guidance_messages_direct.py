"""GMSG-4: one persistent pair-scoped direct thread per Counselor pair, on PostgreSQL."""

from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest

from compass.accounts.models import Capability, Role, User, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.guidance_messages import policy, services, work
from compass.guidance_messages.errors import (
    InvalidMessageInput,
    MessagesConflict,
    MessagesPermissionDenied,
    ThreadNotFound,
)
from compass.guidance_messages.models import (
    GuidanceMessage,
    GuidanceThread,
    GuidanceThreadReadState,
)
from tests.test_guidance_messages import BASE, BODY, post, world  # noqa: F401
from tests.test_notifications import auth_client

# Imported world fixture is injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db

DIRECT_VIEW = "guidance_messages.counselor_direct.view"
DIRECT_MANAGE = "guidance_messages.counselor_direct.manage"


def open_direct(world, *, actor=None, peer=None, client_id=None, body=BODY):
    return services.open_counselor_direct_thread(
        actor=actor or world.counselor,
        peer_id=(peer or world.other).pk,
        client_message_id=client_id or uuid4(),
        body=body,
    )


def send(world, thread, *, actor=None, client_id=None, body=BODY):
    return services.send_message(
        actor=actor or world.counselor,
        thread_id=thread.pk,
        client_message_id=client_id or uuid4(),
        body=body,
    )


def make_user(name, role="COUNSELOR", *, active=True):
    return User.objects.create_user(
        email=f"gm-direct-{name}@example.edu",
        password=None,
        role=Role.objects.get(code=role),
        first_name="Synthetic",
        last_name=name,
        is_active=active,
    )


def faculty_actor():
    return User.objects.filter(email="gm-direct-faculty@example.edu").first() or make_user(
        "faculty", "FACULTY"
    )


@contextmanager
def overrides(user, effect, *codes):
    rows = [
        UserCapabilityOverride.objects.create(
            user=user,
            capability=Capability.objects.get(code=code),
            effect=effect,
            reason="Synthetic direct messaging proof",
        )
        for code in codes
    ]
    try:
        yield
    finally:
        UserCapabilityOverride.objects.filter(pk__in=[row.pk for row in rows]).delete()


def audit_actions(thread):
    return list(
        AuditEvent.objects.filter(target_id=thread.pk, action__startswith="guidance_messages.")
        .order_by("occurred_at")
        .values_list("action", flat=True)
    )


def test_peer_directory_is_bounded_name_only_and_manage_scoped(world):
    peers, has_next = services.counselor_peers(actor=world.counselor, page_size=10)
    assert {peer.pk for peer in peers} == {world.other.pk, world.head.pk}
    assert has_next is False

    inactive = make_user("inactive", active=False)
    revoked = make_user("revoked")
    view_only = make_user("view-only")
    with overrides(revoked, "REVOKE", DIRECT_MANAGE), overrides(view_only, "REVOKE", DIRECT_MANAGE):
        peers, _ = services.counselor_peers(actor=world.counselor, page_size=10)
        assert {peer.pk for peer in peers} == {world.other.pk, world.head.pk}
        assert inactive.pk not in {peer.pk for peer in peers}
        assert revoked.pk not in {peer.pk for peer in peers}

        found, _ = services.counselor_peers(actor=world.counselor, search="head")
        assert [peer.pk for peer in found] == [world.head.pk]
        found, _ = services.counselor_peers(actor=world.counselor, search="oth")
        assert [peer.pk for peer in found] == [world.other.pk]

        first, more = services.counselor_peers(actor=world.counselor, page=1, page_size=1)
        second, more_second = services.counselor_peers(actor=world.counselor, page=2, page_size=1)
        assert [peer.pk for peer in first] == [world.head.pk]
        assert more is True
        assert [peer.pk for peer in second] == [world.other.pk]
        assert more_second is False

        with pytest.raises(InvalidMessageInput):
            services.counselor_peers(actor=world.counselor, search="a" * 161)

        client = auth_client(world.counselor)
        response = client.get(BASE + "/counselor-peers", {"page_size": 10})
        assert response.status_code == 200, response.content
        items = response.json()["items"]
        assert {item["id"] for item in items} == {str(world.other.pk), str(world.head.pk)}
        assert all(set(item) == {"id", "display_name"} for item in items)
        assert client.get(BASE + "/counselor-peers", {"search": "head"}).json()["items"] == [
            {"id": str(world.head.pk), "display_name": "Synthetic head"}
        ]
        assert client.get(BASE + "/counselor-peers", {"search": "a" * 161}).status_code == 422
        paged = client.get(BASE + "/counselor-peers", {"page_size": 1, "page": 1}).json()
        assert [item["id"] for item in paged["items"]] == [str(world.head.pk)]
        assert paged["has_next"] is True
        second_page = client.get(BASE + "/counselor-peers", {"page_size": 1, "page": 2}).json()
        assert [item["id"] for item in second_page["items"]] == [str(world.other.pk)]
        assert second_page["has_next"] is False

        for outsider in (world.student, world.gss, view_only):
            assert auth_client(outsider).get(BASE + "/counselor-peers").status_code == 403

    with (
        overrides(world.admin, "GRANT", DIRECT_VIEW, DIRECT_MANAGE),
        overrides(world.dpo, "GRANT", DIRECT_VIEW, DIRECT_MANAGE),
        overrides(world.gss, "GRANT", DIRECT_VIEW, DIRECT_MANAGE),
    ):
        for outsider in (world.admin, world.dpo, world.gss):
            assert auth_client(outsider).get(BASE + "/counselor-peers").status_code == 403


def test_creation_persists_one_canonical_pair_thread_with_no_legacy_columns(world):
    thread, message = open_direct(world, actor=world.counselor, peer=world.other)

    assert GuidanceThread.objects.filter(kind="COUNSELOR_DIRECT").count() == 1
    assert thread.kind == "COUNSELOR_DIRECT"
    assert thread.status == "OPEN"
    assert thread.created_by_id == world.counselor.pk
    assert (thread.direct_first_user_id, thread.direct_second_user_id) == tuple(
        sorted((world.counselor.pk, world.other.pk))
    )
    for name in (
        "student_id",
        "counselor_id",
        "requester_id",
        "student_subject_id",
        "relationship_referral_id",
        "relationship_case_grant_id",
        "relationship_appointment_id",
        "routing_college_id",
        "assigned_to_id",
    ):
        assert getattr(thread, name) is None, name
    assert message.thread_id == thread.pk
    assert message.sequence == 1
    assert message.sender_id == world.counselor.pk

    # world.other is responsible for a different College; a direct pair is College-agnostic.
    assert world.other.pk != world.counselor.pk
    assert thread.routing_college_id is None


def test_replay_and_reverse_direction_reuse_the_same_thread_and_audit(world):
    key = uuid4()
    first_thread, first_message = open_direct(
        world, actor=world.counselor, peer=world.other, client_id=key
    )
    replay_thread, replay_message = open_direct(
        world, actor=world.counselor, peer=world.other, client_id=key
    )
    assert replay_thread.pk == first_thread.pk
    assert replay_message.pk == first_message.pk
    assert GuidanceMessage.objects.filter(thread=first_thread).count() == 1
    assert (
        AuditEvent.objects.filter(
            action="guidance_messages.thread.created", target_id=first_thread.pk
        ).count()
        == 1
    )

    reverse_thread, reverse_message = open_direct(
        world, actor=world.other, peer=world.counselor, client_id=uuid4()
    )
    assert reverse_thread.pk == first_thread.pk
    assert reverse_message.sequence == 2
    assert reverse_message.sender_id == world.other.pk
    first_thread.refresh_from_db()
    assert first_thread.last_sequence == 2
    assert GuidanceMessage.objects.filter(thread=first_thread).count() == 2

    created = AuditEvent.objects.get(
        action="guidance_messages.thread.created", target_id=first_thread.pk
    )
    assert created.metadata["kind"] == "COUNSELOR_DIRECT"
    assert created.metadata["peer_id"] == str(world.other.pk)
    assert created.metadata["thread_id"] == str(first_thread.pk)


def test_client_id_reuse_on_another_pair_or_family_is_a_conflict(world):
    key = uuid4()
    thread, message = open_direct(world, actor=world.counselor, peer=world.other, client_id=key)

    with pytest.raises(MessagesConflict):
        open_direct(world, actor=world.counselor, peer=world.head, client_id=key)
    with pytest.raises(MessagesConflict):
        services.open_office_thread(
            actor=world.counselor,
            student_id=world.student.pk,
            client_message_id=key,
            body=BODY,
        )
    assert GuidanceThread.objects.filter(kind="COUNSELOR_DIRECT").count() == 1
    assert (
        GuidanceMessage.objects.filter(sender=world.counselor, client_message_id=key).count() == 1
    )

    response = post(
        auth_client(world.counselor),
        f"/counselor-peers/{world.head.pk}/direct-thread",
        {"client_message_id": str(key), "body": BODY},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "guidance_messages_conflict"
    assert thread.pk == message.thread_id


def test_a_third_counselor_is_concealed_from_thread_and_directory(world):
    thread, _ = open_direct(world)
    outsider = world.head
    assert outsider.pk not in {thread.direct_first_user_id, thread.direct_second_user_id}

    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=outsider, thread_id=thread.pk)
    with pytest.raises(ThreadNotFound):
        send(world, thread, actor=outsider)
    with pytest.raises(ThreadNotFound):
        services.mark_read(actor=outsider, thread_id=thread.pk, sequence=1)
    with pytest.raises(ThreadNotFound):
        services.set_status(actor=outsider, thread_id=thread.pk, resolved=True)
    with pytest.raises(ThreadNotFound):
        services.set_status(actor=outsider, thread_id=thread.pk, resolved=False)
    with pytest.raises(ThreadNotFound):
        services.assign_handler(actor=outsider, thread_id=thread.pk, handler_id=world.gss.pk)
    with pytest.raises(ThreadNotFound):
        services.eligible_handlers(actor=outsider, thread_id=thread.pk)

    rows, _ = services.list_threads(actor=outsider)
    assert thread.pk not in {row.pk for row in rows}
    response = auth_client(outsider).get(BASE + "/threads")
    assert response.status_code == 200
    assert str(thread.pk) not in {item["id"] for item in response.json()["items"]}

    assert set(policy.recipient_ids(thread)) == {world.counselor.pk, world.other.pk}


def test_narrow_capability_narrowing_restores_after_each_step(world):
    thread, _ = open_direct(world)

    with overrides(world.other, "REVOKE", DIRECT_MANAGE):
        assert services.get_thread(actor=world.other, thread_id=thread.pk).pk == thread.pk
        with pytest.raises(ThreadNotFound):
            send(world, thread, actor=world.other)
        with pytest.raises(ThreadNotFound):
            services.mark_read(actor=world.other, thread_id=thread.pk, sequence=1)
        with pytest.raises(MessagesConflict):
            services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
        with pytest.raises(ThreadNotFound):
            services.set_status(actor=world.other, thread_id=thread.pk, resolved=True)

    with overrides(world.other, "REVOKE", DIRECT_VIEW):
        rows, _ = services.list_threads(actor=world.other)
        assert thread.pk not in {row.pk for row in rows}
        with pytest.raises(ThreadNotFound):
            services.get_thread(actor=world.other, thread_id=thread.pk)
        assert set(policy.recipient_ids(thread)) == {world.counselor.pk}

    assert services.get_thread(actor=world.other, thread_id=thread.pk).pk == thread.pk
    assert set(policy.recipient_ids(thread)) == {world.counselor.pk, world.other.pk}


def test_peer_validation_is_concealed_like_a_missing_thread(world):
    inactive = make_user("inactive-peer", active=False)
    revoked = make_user("revoked-peer")
    missing = uuid4()

    peers = [
        world.counselor,
        world.gss,
        inactive,
        world.student,
        revoked,
    ]
    with overrides(revoked, "REVOKE", DIRECT_MANAGE):
        for peer in peers:
            with pytest.raises(ThreadNotFound):
                open_direct(world, actor=world.counselor, peer=peer)
        with pytest.raises(ThreadNotFound):
            services.open_counselor_direct_thread(
                actor=world.counselor,
                peer_id=missing,
                client_message_id=uuid4(),
                body=BODY,
            )
        assert not GuidanceThread.objects.filter(kind="COUNSELOR_DIRECT").exists()

        client = auth_client(world.counselor)
        for peer in peers:
            response = post(
                client,
                f"/counselor-peers/{peer.pk}/direct-thread",
                {"client_message_id": str(uuid4()), "body": BODY},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "guidance_thread_not_found"
        response = post(
            client,
            f"/counselor-peers/{missing}/direct-thread",
            {"client_message_id": str(uuid4()), "body": BODY},
        )
        assert response.status_code == 404


def test_direct_conversations_never_resolve_or_reopen(world):
    thread, _ = open_direct(world)
    before = audit_actions(thread)

    for resolved in (True, False):
        with pytest.raises(MessagesConflict):
            services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=resolved)

    thread.refresh_from_db()
    assert thread.status == "OPEN"
    assert thread.resolved_at is None
    assert thread.resolved_by_id is None
    assert audit_actions(thread) == before
    assert not {
        "guidance_messages.thread.resolved",
        "guidance_messages.thread.reopened",
    } & set(audit_actions(thread))

    client = auth_client(world.counselor)
    for action in ("resolve", "reopen"):
        response = post(client, f"/threads/{thread.pk}/{action}", {})
        assert response.status_code == 409, response.content
        assert response.json()["error"]["code"] == "guidance_messages_conflict"


def test_direct_has_no_handler_or_work_leakage(world):
    thread, _ = open_direct(world)

    with pytest.raises(ThreadNotFound):
        services.assign_handler(
            actor=world.counselor, thread_id=thread.pk, handler_id=world.head.pk
        )
    with pytest.raises(ThreadNotFound):
        services.eligible_handlers(actor=world.counselor, thread_id=thread.pk)
    http = auth_client(world.counselor)
    assert http.get(f"{BASE}/threads/{thread.pk}/eligible-handlers").status_code == 404
    assigned = http.patch(
        f"{BASE}/threads/{thread.pk}/handler",
        data=json.dumps({"handler_id": str(world.head.pk)}),
        content_type="application/json",
    )
    assert assigned.status_code == 404

    for participant in (world.counselor, world.other):
        assert work.reply_needed_summary(actor=participant).count == 0
    thread.refresh_from_db()
    assert thread.routing_college_id is None
    assert thread.assigned_to_id is None


def test_dto_exposes_only_name_pair_and_nulls_every_legacy_field(world):
    thread, _ = open_direct(world)
    first_id, second_id = sorted((world.counselor.pk, world.other.pk))

    for participant in (world.counselor, world.other):
        response = auth_client(participant).get(f"{BASE}/threads/{thread.pk}")
        assert response.status_code == 200, response.content
        payload = response.json()
        assert payload["kind"] == "COUNSELOR_DIRECT"
        assert payload["status"] == "OPEN"
        assert set(payload["direct_first_user"]) == {"id", "display_name"}
        assert set(payload["direct_second_user"]) == {"id", "display_name"}
        assert payload["direct_first_user"]["id"] == str(first_id)
        assert payload["direct_second_user"]["id"] == str(second_id)
        for name in (
            "student",
            "counselor",
            "requester",
            "routing_college",
            "assigned_to",
            "relationship_appointment_id",
            "relationship_referral_id",
            "relationship_referral_reference",
            "relationship_referral_voided",
        ):
            assert payload[name] is None, name

    office_thread, _ = services.open_office_thread(
        actor=world.student, client_message_id=uuid4(), body=BODY
    )
    office_payload = auth_client(world.counselor).get(f"{BASE}/threads/{office_thread.pk}").json()
    assert office_payload["direct_first_user"] is None
    assert office_payload["direct_second_user"] is None


def test_role_gate_precedes_a_granted_narrow_capability(world):
    thread, _ = open_direct(world)
    faculty = faculty_actor()
    outsiders = [world.gss, world.admin, world.dpo, world.student, faculty]

    for outsider in outsiders:
        with overrides(outsider, "GRANT", DIRECT_VIEW, DIRECT_MANAGE):
            with pytest.raises(MessagesPermissionDenied):
                policy.require_actor(outsider, kind="COUNSELOR_DIRECT")
            with pytest.raises(MessagesPermissionDenied):
                policy.require_actor(outsider, manage=True, kind="COUNSELOR_DIRECT")
            with pytest.raises(ThreadNotFound):
                services.get_thread(actor=outsider, thread_id=thread.pk)
            with pytest.raises(ThreadNotFound):
                policy.require_thread(outsider, thread)
            response = auth_client(outsider).get(f"{BASE}/threads/{thread.pk}")
            assert response.status_code == 404, (outsider.role.code, response.content)
    assert set(policy.recipient_ids(thread)) == {world.counselor.pk, world.other.pk}


def test_unread_count_is_per_user_and_tracks_the_peer(world):
    thread, first = open_direct(world, actor=world.counselor, peer=world.other)
    assert first.sequence == 1
    assert services.count_unread_conversations(actor=world.other) == 1
    assert services.count_unread_conversations(actor=world.counselor) == 0

    services.mark_read(actor=world.other, thread_id=thread.pk, sequence=1)
    assert services.count_unread_conversations(actor=world.other) == 0
    assert services.count_unread_conversations(actor=world.counselor) == 0

    second = send(world, thread, actor=world.counselor)
    assert second.sequence == 2
    assert services.count_unread_conversations(actor=world.other) == 1
    assert services.count_unread_conversations(actor=world.counselor) == 0

    services.mark_read(actor=world.counselor, thread_id=thread.pk, sequence=2)
    assert services.count_unread_conversations(actor=world.counselor) == 0
    assert services.count_unread_conversations(actor=world.other) == 1

    states = {
        state.user_id: state.last_read_sequence
        for state in GuidanceThreadReadState.objects.filter(thread=thread)
    }
    assert states == {world.counselor.pk: 2, world.other.pk: 1}
