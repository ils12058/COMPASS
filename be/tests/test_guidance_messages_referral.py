"""GMSG-3: one Referral, one REFERRAL_COORDINATION thread, current-placement staff scope."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from compass.accounts.models import Capability, Designation, Role, User, UserCapabilityOverride
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.guidance_messages import content, policy, services
from compass.guidance_messages.errors import (
    MessagesPermissionDenied,
    ReferralVoided,
    ThreadNotFound,
)
from compass.guidance_messages.models import GuidanceMessage, GuidanceThread, ThreadKind
from compass.organization.models import College, CounselorResponsibility, StaffSupervision
from compass.referrals.models import Referral
from compass.referrals.services import void_referral
from compass.student_academics.models import StudentAcademicProfile
from tests.faculty_referral_helpers import confirm, make_world, submit
from tests.test_guidance_messages import BASE, BODY, post
from tests.test_notifications import auth_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(monkeypatch):
    base = make_world(monkeypatch)
    college_b = College.objects.create(campus=base.campus, code="CHS", name="Synthetic CHS")

    def staff(label, role):
        return User.objects.create_user(
            email=f"gm-referral-{label}@synthetic.invalid",
            password=None,
            role=Role.objects.get(code=role),
            first_name="Synthetic",
            last_name=label,
        )

    counselor_a = staff("counselor-a", "COUNSELOR")
    counselor_b = staff("counselor-b", "COUNSELOR")
    gss_a = staff("gss-a", "GUIDANCE_SERVICES_STAFF")
    head = staff("head", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    CounselorResponsibility.objects.create(college=base.ccms, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=college_b, counselor=counselor_b)
    StaffSupervision.objects.create(staff=gss_a, supervisor=counselor_a)
    projection, created = submit(base)
    assert created
    referral = Referral.objects.get(pk=projection["id"])
    return SimpleNamespace(
        **base.__dict__,
        college_b=college_b,
        counselor_a=counselor_a,
        counselor_b=counselor_b,
        gss_a=gss_a,
        head=head,
        referral=referral,
    )


def open_thread(world, *, actor=None, client_id=None):
    return services.open_referral_thread(
        actor=actor or world.faculty,
        referral_id=world.referral.pk,
        client_message_id=client_id or uuid4(),
        body=BODY,
    )


def referral_snapshot(referral):
    referral.refresh_from_db()
    return (
        referral.submission_channel,
        referral.submitted_by_id,
        referral.submitted_at,
        referral.received_at,
        referral.acknowledged_by_id,
        referral.administratively_closed_at,
        referral.administratively_closed_by_id,
        referral.administrative_version,
        referral.voided_at,
        referral.voided_by_id,
        referral.confidential_content_ciphertext,
        referral.form_revision_id,
        referral.student_name_snapshot,
        referral.course_year_block_snapshot,
        referral.updated_at,
        tuple(referral.actions.values_list("pk", "action_type", "remarks_ciphertext")),
    )


def void(world, referral=None):
    return void_referral(
        actor=world.counselor_a,
        referral_id=(referral or world.referral).pk,
        reason="Synthetic void reason",
        context=AuditContext.user(world.counselor_a),
    )


def test_faculty_submitter_opens_and_replies_by_service_and_http(world):
    thread, message = open_thread(world)

    assert thread.kind == ThreadKind.REFERRAL_COORDINATION
    assert thread.status == "OPEN"
    assert thread.requester_id == world.faculty.pk
    assert thread.relationship_referral_id == world.referral.pk
    assert thread.student_subject_id == world.student.pk
    assert thread.routing_college_id == world.referral.student_college_at_submission_id
    assert thread.student_id is None
    assert thread.counselor_id is None
    assert thread.assigned_to_id is None
    assert message.sequence == 1
    assert content.read_body(message) == BODY
    assert BODY not in message.body_ciphertext
    assert GuidanceThread.objects.filter(kind=ThreadKind.REFERRAL_COORDINATION).count() == 1

    event = AuditEvent.objects.get(action="guidance_messages.thread.created", target_id=thread.pk)
    assert event.metadata["kind"] == "REFERRAL_COORDINATION"
    assert event.metadata["referral_id"] == str(world.referral.pk)

    reply = services.send_message(
        actor=world.faculty,
        thread_id=thread.pk,
        client_message_id=uuid4(),
        body="Synthetic reply.",
    )
    assert reply.sequence == 2

    response = post(
        auth_client(world.faculty),
        f"/referrals/{world.referral.pk}/referral-thread",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["thread"]["id"] == str(thread.pk)
    assert body["thread"]["requester"]["id"] == str(world.faculty.pk)
    assert body["thread"]["student"] is None
    assert body["message"]["sequence"] == 3


def test_idempotent_open_reuses_one_thread_and_one_message(world):
    key = uuid4()
    first_thread, first_message = open_thread(world, client_id=key)
    again_thread, again_message = open_thread(world, client_id=key)

    assert first_thread.pk == again_thread.pk
    assert first_message.pk == again_message.pk
    assert GuidanceMessage.objects.filter(sender=world.faculty).count() == 1
    assert GuidanceThread.objects.count() == 1

    second_thread, second_message = open_thread(world)
    assert second_thread.pk == first_thread.pk
    assert second_message.sequence == 2
    assert GuidanceThread.objects.count() == 1


def test_in_scope_staff_read_and_reply_but_can_never_create(world):
    thread, _ = open_thread(world)

    for actor in (world.counselor_a, world.gss_a, world.head):
        assert services.get_thread(actor=actor, thread_id=thread.pk).pk == thread.pk, (
            actor.role.code
        )
        reply = services.send_message(
            actor=actor, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
        assert reply.thread_id == thread.pk

    with pytest.raises(MessagesPermissionDenied):
        open_thread(world, actor=world.counselor_a)
    response = post(
        auth_client(world.counselor_a),
        f"/referrals/{world.referral.pk}/referral-thread",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 403
    assert GuidanceThread.objects.count() == 1


def test_out_of_scope_staff_is_concealed_everywhere(world):
    thread, _ = open_thread(world)
    client = auth_client(world.counselor_b)

    with pytest.raises(ThreadNotFound):
        services.referral_context(actor=world.counselor_b, referral_id=world.referral.pk)
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=world.counselor_b, thread_id=thread.pk)
    with pytest.raises(ThreadNotFound):
        services.send_message(
            actor=world.counselor_b, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
    with pytest.raises(ThreadNotFound):
        services.set_status(actor=world.counselor_b, thread_id=thread.pk, resolved=True)

    assert [row.pk for row in services.list_threads(actor=world.counselor_b)[0]] == []
    assert client.get(f"{BASE}/referrals/{world.referral.pk}/context").status_code == 404
    assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 404
    assert (
        post(
            client,
            f"/threads/{thread.pk}/messages",
            {"client_message_id": str(uuid4()), "body": BODY},
        ).status_code
        == 404
    )
    assert client.post(f"{BASE}/threads/{thread.pk}/resolve").status_code == 404


def test_scope_follows_the_current_placement_not_the_routing_snapshot(world):
    thread, _ = open_thread(world)
    snapshot_college = thread.routing_college_id
    assert snapshot_college == world.ccms.pk

    StudentAcademicProfile.objects.filter(student=world.student).update(
        current_college=world.college_b
    )

    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=world.counselor_a, thread_id=thread.pk)
    assert services.get_thread(actor=world.counselor_b, thread_id=thread.pk).pk == thread.pk
    thread.refresh_from_db()
    assert thread.routing_college_id == snapshot_college
    assert thread.routing_college_id != world.college_b.pk


def test_head_designation_sees_every_referral_thread(world):
    thread, _ = open_thread(world)
    assert services.get_thread(actor=world.head, thread_id=thread.pk).pk == thread.pk
    listed = [row.pk for row in services.list_threads(actor=world.head)[0]]
    assert thread.pk in listed

    StudentAcademicProfile.objects.filter(student=world.student).update(
        current_college=world.college_b
    )
    assert services.get_thread(actor=world.head, thread_id=thread.pk).pk == thread.pk


def test_void_keeps_history_readable_and_makes_the_conversation_read_only(world):
    key = uuid4()
    thread, message = open_thread(world, client_id=key)
    services.send_message(
        actor=world.counselor_a, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
    )
    voided = void(world)
    assert voided.voided_at is not None

    assert services.get_thread(actor=world.faculty, thread_id=thread.pk).pk == thread.pk
    assert services.get_thread(actor=world.counselor_a, thread_id=thread.pk).pk == thread.pk
    listed = [row.pk for row in services.list_threads(actor=world.counselor_a)[0]]
    assert thread.pk in listed

    with pytest.raises(ReferralVoided):
        services.send_message(
            actor=world.faculty, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
    with pytest.raises(ReferralVoided):
        services.set_status(actor=world.counselor_a, thread_id=thread.pk, resolved=True)
    with pytest.raises(ReferralVoided):
        services.set_status(actor=world.faculty, thread_id=thread.pk, resolved=False)

    # Replay is history, not a new send: an accepted client id still returns its message.
    replayed = services.send_message(
        actor=world.faculty, thread_id=thread.pk, client_message_id=key, body=BODY
    )
    assert replayed.pk == message.pk
    replayed_open, replayed_message = open_thread(world, client_id=key)
    assert replayed_open.pk == thread.pk
    assert replayed_message.pk == message.pk

    client = auth_client(world.faculty)
    response = post(
        client,
        f"/threads/{thread.pk}/messages",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "guidance_messages_referral_voided"
    assert response.json()["error"]["message"] == (
        "This Referral was voided, so its conversation is read-only."
    )
    resolve = client.post(f"{BASE}/threads/{thread.pk}/resolve")
    assert resolve.status_code == 409
    assert resolve.json()["error"]["code"] == "guidance_messages_referral_voided"
    reopen = client.post(f"{BASE}/threads/{thread.pk}/reopen")
    assert reopen.status_code == 409
    assert reopen.json()["error"]["code"] == "guidance_messages_referral_voided"
    replay_http = post(
        client,
        f"/threads/{thread.pk}/messages",
        {"client_message_id": str(key), "body": BODY},
    )
    assert replay_http.status_code == 200
    assert replay_http.json()["id"] == str(message.pk)

    assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 200


def test_voided_referral_without_a_thread_is_concealed_and_cannot_open(world):
    projection, created = submit(
        world,
        confirmation=confirm(world)["confirmation"],
        idempotency_key="synthetic-faculty-referral-2",
    )
    assert created
    second = Referral.objects.get(pk=projection["id"])
    void(world, second)

    with pytest.raises(ThreadNotFound):
        services.referral_context(actor=world.faculty, referral_id=second.pk)
    with pytest.raises(ReferralVoided):
        services.open_referral_thread(
            actor=world.faculty,
            referral_id=second.pk,
            client_message_id=uuid4(),
            body=BODY,
        )
    client = auth_client(world.faculty)
    assert client.get(f"{BASE}/referrals/{second.pk}/context").status_code == 404
    response = post(
        client,
        f"/referrals/{second.pk}/referral-thread",
        {"client_message_id": str(uuid4()), "body": BODY},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "guidance_messages_referral_voided"
    assert not GuidanceThread.objects.exists()


def test_context_reports_thread_and_can_start_per_actor(world):
    assert services.referral_context(actor=world.faculty, referral_id=world.referral.pk) == (
        None,
        True,
    )
    assert services.referral_context(actor=world.counselor_a, referral_id=world.referral.pk) == (
        None,
        False,
    )
    with pytest.raises(ThreadNotFound):
        services.referral_context(actor=world.other_faculty, referral_id=world.referral.pk)
    with pytest.raises(ThreadNotFound):
        services.referral_context(actor=world.student, referral_id=world.referral.pk)

    faculty_client = auth_client(world.faculty)
    payload = faculty_client.get(f"{BASE}/referrals/{world.referral.pk}/context").json()
    assert payload == {"thread": None, "can_start": True}
    staff_payload = auth_client(world.counselor_a).get(
        f"{BASE}/referrals/{world.referral.pk}/context"
    )
    assert staff_payload.status_code == 200
    assert staff_payload.json() == {"thread": None, "can_start": False}
    assert (
        auth_client(world.other_faculty)
        .get(f"{BASE}/referrals/{world.referral.pk}/context")
        .status_code
        == 404
    )

    thread, _ = open_thread(world)
    existing, can_start = services.referral_context(
        actor=world.faculty, referral_id=world.referral.pk
    )
    assert existing.pk == thread.pk and can_start is False
    staff_existing, staff_can_start = services.referral_context(
        actor=world.counselor_a, referral_id=world.referral.pk
    )
    assert staff_existing.pk == thread.pk and staff_can_start is False
    after = auth_client(world.faculty).get(f"{BASE}/referrals/{world.referral.pk}/context").json()
    assert after["thread"]["id"] == str(thread.pk)
    assert after["can_start"] is False

    void(world)
    assert (
        services.referral_context(actor=world.faculty, referral_id=world.referral.pk)[0].pk
        == thread.pk
    )
    assert (
        services.referral_context(actor=world.counselor_a, referral_id=world.referral.pk)[0].pk
        == thread.pk
    )


def test_thread_dto_exposes_the_referral_fields_to_both_viewers(world):
    thread, _ = open_thread(world)
    reference = world.referral.reference_code

    faculty_payload = auth_client(world.faculty).get(f"{BASE}/threads/{thread.pk}").json()
    assert faculty_payload["relationship_referral_id"] == str(world.referral.pk)
    assert faculty_payload["relationship_referral_reference"] == reference
    assert faculty_payload["relationship_referral_voided"] is False
    assert faculty_payload["student"] is None
    assert faculty_payload["routing_college"] is None
    assert faculty_payload["assigned_to"] is None

    staff_payload = auth_client(world.counselor_a).get(f"{BASE}/threads/{thread.pk}").json()
    assert staff_payload["relationship_referral_id"] == str(world.referral.pk)
    assert staff_payload["relationship_referral_reference"] == reference
    assert staff_payload["relationship_referral_voided"] is False
    assert staff_payload["student"] is None
    assert staff_payload["routing_college"]["id"] == str(world.ccms.pk)
    assert staff_payload["assigned_to"] is None

    void(world)
    voided_payload = auth_client(world.faculty).get(f"{BASE}/threads/{thread.pk}").json()
    assert voided_payload["relationship_referral_voided"] is True


def test_messaging_never_changes_referral_state(world):
    before = referral_snapshot(world.referral)

    thread, _ = open_thread(world)
    services.send_message(
        actor=world.faculty, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
    )
    services.send_message(
        actor=world.counselor_a, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
    )
    services.set_status(actor=world.counselor_a, thread_id=thread.pk, resolved=True)
    services.set_status(actor=world.counselor_a, thread_id=thread.pk, resolved=False)

    assert referral_snapshot(world.referral) == before
    assert (
        Referral.objects.get(pk=world.referral.pk).confidential_content_ciphertext == (before[10])
    )


def test_capability_revocation_narrows_read_write_and_start(world):
    manage = UserCapabilityOverride.objects.create(
        user=world.faculty,
        capability=Capability.objects.get(code="guidance_messages.referral_manage_self"),
        effect="REVOKE",
        reason="Synthetic revocation",
    )
    try:
        assert services.referral_context(actor=world.faculty, referral_id=world.referral.pk) == (
            None,
            False,
        )
        with pytest.raises(MessagesPermissionDenied):
            open_thread(world)
        response = post(
            auth_client(world.faculty),
            f"/referrals/{world.referral.pk}/referral-thread",
            {"client_message_id": str(uuid4()), "body": BODY},
        )
        assert response.status_code == 403
    finally:
        manage.delete()

    thread, _ = open_thread(world)
    manage = UserCapabilityOverride.objects.create(
        user=world.faculty,
        capability=Capability.objects.get(code="guidance_messages.referral_manage_self"),
        effect="REVOKE",
        reason="Synthetic revocation",
    )
    try:
        with pytest.raises(ThreadNotFound):
            services.send_message(
                actor=world.faculty,
                thread_id=thread.pk,
                client_message_id=uuid4(),
                body=BODY,
            )
        client = auth_client(world.faculty)
        assert client.get(f"{BASE}/threads/{thread.pk}").status_code == 200
        assert (
            post(
                client,
                f"/threads/{thread.pk}/messages",
                {"client_message_id": str(uuid4()), "body": BODY},
            ).status_code
            == 404
        )
        existing, can_start = services.referral_context(
            actor=world.faculty, referral_id=world.referral.pk
        )
        assert existing.pk == thread.pk and can_start is False
    finally:
        manage.delete()

    referrals_manage = UserCapabilityOverride.objects.create(
        user=world.counselor_a,
        capability=Capability.objects.get(code="referrals.manage"),
        effect="REVOKE",
        reason="Synthetic revocation",
    )
    try:
        with pytest.raises(ThreadNotFound):
            services.send_message(
                actor=world.counselor_a,
                thread_id=thread.pk,
                client_message_id=uuid4(),
                body=BODY,
            )
        with pytest.raises(ThreadNotFound):
            services.set_status(actor=world.counselor_a, thread_id=thread.pk, resolved=True)
        assert services.get_thread(actor=world.counselor_a, thread_id=thread.pk).pk == thread.pk
    finally:
        referrals_manage.delete()


def test_recipients_are_the_submitter_and_in_scope_staff_only(world):
    thread, _ = open_thread(world)
    recipients = set(policy.recipient_ids(thread))
    assert recipients == {
        world.faculty.pk,
        world.counselor_a.pk,
        world.gss_a.pk,
        world.head.pk,
    }
    assert world.student.pk not in recipients
    assert world.other_faculty.pk not in recipients
    assert world.counselor_b.pk not in recipients


def test_referral_threads_have_no_handler_assignment(world):
    thread, _ = open_thread(world)
    with pytest.raises(ThreadNotFound):
        services.assign_handler(
            actor=world.counselor_a, thread_id=thread.pk, handler_id=world.counselor_a.pk
        )
    with pytest.raises(ThreadNotFound):
        services.eligible_handlers(actor=world.counselor_a, thread_id=thread.pk)
    assert (
        auth_client(world.counselor_a)
        .get(f"{BASE}/threads/{thread.pk}/eligible-handlers")
        .status_code
        == 404
    )
    assert (
        auth_client(world.counselor_a)
        .patch(
            f"{BASE}/threads/{thread.pk}/handler",
            data={"handler_id": str(world.counselor_a.pk)},
            content_type="application/json",
        )
        .status_code
        == 404
    )
