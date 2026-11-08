"""GMSG-5: authorized Counselor case coordination on one live continuity grant.

Synthetic institutional evidence only. The deployed communication policy provider stays `None`,
so every helper here replaces it inside one test; nothing asserts GCO/DPO approval.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from compass.accounts.models import Capability, Role, User, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.guidance_messages import policy, services, work
from compass.guidance_messages.errors import (
    CaseCoordinationEnded,
    MessagesConflict,
    ThreadNotFound,
)
from compass.guidance_messages.models import GuidanceMessage, GuidanceThread, ThreadKind
from compass.notifications.models import Notification
from tests.case_communication_helpers import (  # noqa: F401
    additional_student,
    case,
    communication,
    expire,
    live_case_grant,
    revoke,
)
from tests.test_guidance_messages import BASE, BODY, post
from tests.test_guidance_messages_concurrency import parallel
from tests.test_notifications import auth_client

# Imported fixtures are injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db(transaction=True)

CASE_VIEW = "guidance_messages.case_coordination.view"
CASE_MANAGE = "guidance_messages.case_coordination.manage"
CASE_KIND = ThreadKind.COUNSELOR_CASE_COORDINATION


@pytest.fixture
def world(communication):
    world = communication
    world.grant = live_case_grant(world)
    world.goa = User.objects.create_user(
        email="case-goa@synthetic.test",
        password=None,
        role=Role.objects.get(code="GUIDANCE_OFFICE_ASSISTANT"),
        first_name="Synthetic",
        last_name="goa",
    )
    world.faculty = User.objects.create_user(
        email="case-faculty@synthetic.test",
        password=None,
        role=Role.objects.get(code="FACULTY"),
        first_name="Synthetic",
        last_name="faculty",
    )
    return world


def open_thread(world, *, actor=None, client_id=None, grant=None, body=BODY):
    return services.open_case_coordination_thread(
        actor=actor or world.author,
        grant_id=(grant or world.grant)["id"],
        client_message_id=client_id or uuid4(),
        body=body,
    )


def send(world, thread, *, actor=None, client_id=None, body=BODY):
    return services.send_message(
        actor=actor or world.author,
        thread_id=thread.pk,
        client_message_id=client_id or uuid4(),
        body=body,
    )


@contextmanager
def overrides(user, effect, *codes):
    rows = [
        UserCapabilityOverride.objects.create(
            user=user,
            capability=Capability.objects.get(code=code),
            effect=effect,
            reason="Synthetic case-coordination proof",
        )
        for code in codes
    ]
    try:
        yield
    finally:
        UserCapabilityOverride.objects.filter(pk__in=[row.pk for row in rows]).delete()


@pytest.mark.parametrize("who", ["student", "goa", "faculty", "head", "outsider"])
def test_open_is_unavailable_to_anyone_outside_the_exact_pair(world, who):
    actor = getattr(world, who)
    with pytest.raises(ThreadNotFound):
        open_thread(world, actor=actor)
    response = post(
        auth_client(actor),
        f"/case-grants/{world.grant['id']}/thread",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 404, response.content
    assert response.json()["error"]["code"] == "guidance_thread_not_found"
    assert not GuidanceThread.objects.filter(kind=CASE_KIND).exists()


def test_role_gate_precedes_a_granted_case_capability(world):
    for actor in (world.student, world.goa, world.faculty, world.outsider):
        with overrides(actor, "GRANT", CASE_VIEW, CASE_MANAGE):
            with pytest.raises(ThreadNotFound):
                open_thread(world, actor=actor)
            context = auth_client(actor).get(f"{BASE}/case-grants/{world.grant['id']}/context")
            assert context.status_code == 404
    assert not GuidanceThread.objects.filter(kind=CASE_KIND).exists()


def test_case_capability_without_a_grant_sees_zero_threads(world):
    thread, _ = open_thread(world)
    for actor in (world.head, world.outsider):
        assert actor.has_capability(CASE_VIEW) and actor.has_capability(CASE_MANAGE)
        rows, _ = services.list_threads(actor=actor)
        assert thread.pk not in {row.pk for row in rows}
        client = auth_client(actor)
        assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 404
        assert client.get(f"{BASE}/threads/{thread.pk}/messages").status_code == 404
        assert client.get(f"{BASE}/case-grants/{world.grant['id']}/context").status_code == 404
        listed = client.get(f"{BASE}/threads").json()["items"]
        assert thread.pk not in {item["id"] for item in listed}
        assert work.reply_needed_summary(actor=actor).count == 0


def test_open_creates_one_canonical_case_thread(world):
    thread, message = open_thread(world)

    assert GuidanceThread.objects.filter(kind=CASE_KIND).count() == 1
    assert thread.kind == CASE_KIND
    assert thread.status == "OPEN"
    assert thread.created_by_id == world.author.pk
    assert thread.relationship_case_grant_id == world.grant["id"]
    assert thread.student_subject_id == world.student.pk
    for name in (
        "student_id",
        "counselor_id",
        "requester_id",
        "direct_first_user_id",
        "direct_second_user_id",
        "relationship_referral_id",
        "relationship_appointment_id",
        "routing_college_id",
        "assigned_to_id",
    ):
        assert getattr(thread, name) is None, name
    assert message.thread_id == thread.pk
    assert message.sequence == 1
    assert message.sender_id == world.author.pk

    for participant in (world.author, world.receiver):
        payload = auth_client(participant).get(f"{BASE}/threads/{thread.pk}").json()
        assert payload["kind"] == "COUNSELOR_CASE_COORDINATION"
        assert payload["status"] == "OPEN"
        assert payload["student_subject"] == {
            "id": str(world.student.pk),
            "display_name": world.student.get_full_name(),
        }
        assert payload["relationship_case_grant_id"] == str(world.grant["id"])
        for name in (
            "student",
            "counselor",
            "requester",
            "direct_first_user",
            "direct_second_user",
            "routing_college",
            "assigned_to",
            "relationship_referral_id",
            "relationship_appointment_id",
        ):
            assert payload[name] is None, name


def test_first_message_replay_and_reverse_direction_reuse_one_thread(world):
    key = uuid4()
    thread, message = open_thread(world, actor=world.author, client_id=key)
    replay_thread, replay_message = open_thread(world, actor=world.author, client_id=key)
    assert (replay_thread.pk, replay_message.pk) == (thread.pk, message.pk)
    assert GuidanceMessage.objects.filter(thread=thread).count() == 1

    reverse_thread, reverse_message = open_thread(world, actor=world.receiver)
    assert reverse_thread.pk == thread.pk
    assert reverse_message.sequence == 2
    assert reverse_message.sender_id == world.receiver.pk
    assert GuidanceThread.objects.filter(kind=CASE_KIND).count() == 1
    assert (
        AuditEvent.objects.filter(
            action="guidance_messages.thread.created", target_id=thread.pk
        ).count()
        == 1
    )


def test_reused_client_message_id_across_case_threads_is_a_conflict(world):
    other = additional_student(world)
    second_grant = live_case_grant(world, student_id=other.student.pk, scopes=other.scopes)
    key = uuid4()
    open_thread(world, actor=world.author, client_id=key)

    with pytest.raises(MessagesConflict):
        services.open_case_coordination_thread(
            actor=world.author,
            grant_id=second_grant["id"],
            client_message_id=key,
            body=BODY,
        )
    response = post(
        auth_client(world.author),
        f"/case-grants/{second_grant['id']}/thread",
        {"client_message_id": str(key), "body": BODY},
    )
    assert response.status_code == 409, response.content
    assert response.json()["error"]["code"] == "guidance_messages_conflict"


def test_open_reuses_a_thread_created_by_a_prior_race(world):
    existing = GuidanceThread.objects.create(
        kind=CASE_KIND,
        relationship_case_grant_id=world.grant["id"],
        student_subject_id=world.student.pk,
        created_by=world.receiver,
    )
    thread, message = open_thread(world, actor=world.author)
    assert thread.pk == existing.pk
    assert message.sequence == 1
    assert GuidanceMessage.objects.filter(thread=existing).count() == 1
    assert not AuditEvent.objects.filter(
        action="guidance_messages.thread.created", target_id=existing.pk
    ).exists()


def test_unique_index_guards_one_thread_per_grant_and_student(world):
    open_thread(world)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind=CASE_KIND,
            relationship_case_grant_id=world.grant["id"],
            student_subject_id=world.student.pk,
            created_by=world.author,
        )
    assert GuidanceThread.objects.filter(kind=CASE_KIND).count() == 1


def test_concurrent_same_and_mixed_direction_opens_converge(world):
    actors = [world.author, world.receiver]
    keys = [uuid4(), uuid4()]
    results = parallel(
        20,
        lambda index: services.open_case_coordination_thread(
            actor=actors[index % 2],
            grant_id=world.grant["id"],
            client_message_id=keys[index % 2],
            body=BODY,
        ),
    )
    threads = [thread for thread, _ in results]
    assert len({thread.pk for thread in threads}) == 1
    thread = threads[0]
    assert GuidanceThread.objects.filter(kind=CASE_KIND).count() == 1
    sequences = GuidanceMessage.objects.filter(thread=thread).values_list("sequence", flat=True)
    assert sorted(sequences) == [1, 2]
    assert (
        AuditEvent.objects.filter(
            action="guidance_messages.thread.created", target_id=thread.pk
        ).count()
        == 1
    )


@pytest.mark.parametrize("end", ["revoked", "expired"])
def test_ended_grant_denies_every_messaging_operation(world, end):
    thread, _ = open_thread(world)
    if end == "revoked":
        revoke(world, world.grant)
    else:
        expire(world.grant)

    for actor in (world.author, world.receiver):
        with pytest.raises(CaseCoordinationEnded):
            send(world, thread, actor=actor)
        with pytest.raises(CaseCoordinationEnded):
            services.get_thread(actor=actor, thread_id=thread.pk)
        with pytest.raises(CaseCoordinationEnded):
            services.list_messages(actor=actor, thread_id=thread.pk)
        with pytest.raises(CaseCoordinationEnded):
            services.mark_read(actor=actor, thread_id=thread.pk, sequence=1)
        for resolved in (True, False):
            with pytest.raises(CaseCoordinationEnded):
                services.set_status(actor=actor, thread_id=thread.pk, resolved=resolved)
        with pytest.raises(CaseCoordinationEnded):
            open_thread(world, actor=actor)
        rows, _ = services.list_threads(actor=actor)
        assert thread.pk not in {row.pk for row in rows}

    client = auth_client(world.author)
    for path in (f"/threads/{thread.pk}", f"/threads/{thread.pk}/messages"):
        response = client.get(BASE + path)
        assert response.status_code == 403, response.content
        assert response.json()["error"]["code"] == "guidance_messages_case_coordination_ended"
    sent = post(
        client,
        f"/threads/{thread.pk}/messages",
        {"body": BODY, "client_message_id": str(uuid4())},
    )
    assert sent.status_code == 403
    assert sent.json()["error"]["code"] == "guidance_messages_case_coordination_ended"
    read = client.patch(
        f"{BASE}/threads/{thread.pk}/read",
        data=json.dumps({"sequence": 1}),
        content_type="application/json",
    )
    assert read.status_code == 403
    for action in ("resolve", "reopen"):
        response = post(client, f"/threads/{thread.pk}/{action}", {})
        assert response.status_code == 403, response.content
        assert response.json()["error"]["code"] == "guidance_messages_case_coordination_ended"
    listed = client.get(f"{BASE}/threads")
    assert listed.status_code == 200
    assert str(thread.pk) not in {item["id"] for item in listed.json()["items"]}


def test_resolve_and_reopen_never_mutate_the_grant(world):
    thread, _ = open_thread(world)
    before = Grant.objects.filter(pk=world.grant["id"]).values().get()
    audits = AuditEvent.objects.filter(action__startswith="counseling.continuity.").count()

    services.set_status(actor=world.author, thread_id=thread.pk, resolved=True)
    thread.refresh_from_db()
    assert thread.status == "RESOLVED"
    services.set_status(actor=world.receiver, thread_id=thread.pk, resolved=False)
    thread.refresh_from_db()
    assert thread.status == "OPEN"

    assert Grant.objects.filter(pk=world.grant["id"]).values().get() == before
    assert AuditEvent.objects.filter(action__startswith="counseling.continuity.").count() == audits


def test_recipients_are_only_the_exact_pair(world):
    thread, _ = open_thread(world)
    send(world, thread, actor=world.receiver)
    assert set(policy.recipient_ids(thread)) == {world.author.pk, world.receiver.pk}
    for outsider in (world.student, world.goa, world.faculty, world.head, world.outsider):
        assert outsider.pk not in policy.recipient_ids(thread)


def test_case_thread_has_no_assignment_work_or_handler_recipients(world):
    thread, _ = open_thread(world)
    with pytest.raises(ThreadNotFound):
        services.assign_handler(actor=world.author, thread_id=thread.pk, handler_id=world.head.pk)
    with pytest.raises(ThreadNotFound):
        services.eligible_handlers(actor=world.author, thread_id=thread.pk)

    client = auth_client(world.author)
    assert client.get(f"{BASE}/threads/{thread.pk}/eligible-handlers").status_code == 404
    assigned = client.patch(
        f"{BASE}/threads/{thread.pk}/handler",
        data=json.dumps({"handler_id": str(world.head.pk)}),
        content_type="application/json",
    )
    assert assigned.status_code == 404

    for actor in (world.author, world.receiver):
        assert work.reply_needed_summary(actor=actor).count == 0
    thread.refresh_from_db()
    assert thread.routing_college_id is None
    assert thread.assigned_to_id is None


def test_context_offers_start_then_the_existing_thread_to_the_pair(world):
    client = auth_client(world.author)
    payload = client.get(f"{BASE}/case-grants/{world.grant['id']}/context").json()
    assert payload["thread"] is None
    assert payload["can_start"] is True
    assert payload["access_ended"] is False
    assert payload["counterpart"] == {
        "id": str(world.receiver.pk),
        "display_name": world.receiver.get_full_name(),
    }

    thread, _ = open_thread(world)
    payload = client.get(f"{BASE}/case-grants/{world.grant['id']}/context").json()
    assert payload["thread"]["id"] == str(thread.pk)
    assert payload["thread"]["student_subject"]["id"] == str(world.student.pk)
    assert payload["thread"]["relationship_case_grant_id"] == str(world.grant["id"])
    assert payload["can_start"] is False
    assert payload["access_ended"] is False
    peer = auth_client(world.receiver).get(f"{BASE}/case-grants/{world.grant['id']}/context")
    assert peer.json()["counterpart"]["id"] == str(world.author.pk)


@pytest.mark.parametrize("end", ["revoked", "expired"])
def test_context_reports_ended_only_to_the_previously_authorized_pair(world, end):
    thread, _ = open_thread(world)
    if end == "revoked":
        revoke(world, world.grant)
    else:
        expire(world.grant)

    for actor, peer in ((world.author, world.receiver), (world.receiver, world.author)):
        payload = auth_client(actor).get(f"{BASE}/case-grants/{world.grant['id']}/context").json()
        assert payload["thread"] is None
        assert payload["can_start"] is False
        assert payload["access_ended"] is True
        assert payload["counterpart"]["id"] == str(peer.pk)
    for outsider in (world.head, world.outsider, world.student, world.goa, world.faculty):
        response = auth_client(outsider).get(f"{BASE}/case-grants/{world.grant['id']}/context")
        assert response.status_code == 404, (outsider.role.code, response.content)
    missing = uuid4()
    assert auth_client(world.author).get(f"{BASE}/case-grants/{missing}/context").status_code == 404


def test_student_is_never_a_participant_and_receives_no_notification(world):
    thread, _ = open_thread(world)
    send(world, thread, actor=world.receiver)

    assert set(policy.recipient_ids(thread)) == {world.author.pk, world.receiver.pk}
    assert not Notification.objects.filter(recipient=world.student).exists()
    assert not Notification.objects.filter(recipient__in=[world.author, world.receiver]).exists()

    client = auth_client(world.student)
    assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 404
    assert client.get(f"{BASE}/threads/{thread.pk}/messages").status_code == 404
    assert client.get(f"{BASE}/case-grants/{world.grant['id']}/context").status_code == 404
    items = client.get(f"{BASE}/threads").json()["items"]
    assert str(thread.pk) not in {item["id"] for item in items}
