"""RT-1A commit truth, current participant authority and real Redis/socket/HTTP proof."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
import redis
from django.db import connection, connections, transaction

from compass.accounts.models import Capability, Role, UserCapabilityOverride
from compass.ecounseling import consent_realtime, media
from compass.ecounseling.models import ECounselingConsent
from compass.ecounseling.services import ECounselingNotPermitted, ECounselingProviderUnavailable
from compass.notifications import services as notifications
from compass.notifications.models import Notification
from compass.realtime import connection as realtime_connection
from compass.realtime import publish
from realtime_service import protocol
from tests.test_ecounseling_media import (
    FakeMediaDailyClient,
    context,
    make_user,
    setup_session,
)
from tests.test_notifications import auth_client
from tests.test_realtime_service import Socket, run
from tests.test_realtime_tickets import issue

pytestmark = pytest.mark.django_db(transaction=True)
EVENT = "ecounseling.consent.changed"
SCOPES = ["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"]
ORIGINAL_PUBLISH = publish._publish


@pytest.fixture
def world(settings, monkeypatch):
    # All data and provider behavior are synthetic; normal notification rows are preserved.
    settings.REALTIME_ENABLED = True
    monkeypatch.setattr(notifications, "_safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr(notifications, "_safe_kick_push_delivery", lambda _: None)
    admin, student, counselor, appointment = setup_session(media_policy_version=2)
    return admin, student, counselor, appointment


@pytest.fixture
def publications(monkeypatch):
    frames = []

    def send(channel, frame):
        assert not connection.in_atomic_block, "No Redis publication while DB locks are held"
        frames.append((channel, json.loads(frame)))
        return True

    monkeypatch.setattr(publish, "_publish", send)
    return frames


def request(world, scopes=None):
    _, _, counselor, appointment = world
    return media.request_consents(
        counselor=counselor,
        appointment_id=appointment.pk,
        scopes=scopes or SCOPES,
        context=context(counselor),
    )


def decide(world, consent, decision="APPROVED"):
    _, student, _, appointment = world
    return media.decide_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=consent["id"],
        decision=decision,
        context=context(student),
    )


def withdraw(world, consent, **kwargs):
    _, student, _, appointment = world
    return media.withdraw_my_consent(
        student=student,
        appointment_id=appointment.pk,
        consent_id=consent["id"],
        context=context(student),
        **kwargs,
    )


def hints(frames):
    return [(channel, frame) for channel, frame in frames if frame["type"] == EVENT]


def assert_participants(world, frames, recipients=None):
    _, student, counselor, appointment = world
    recipients = [student, counselor] if recipients is None else recipients
    expected = {protocol.user_channel(user.pk) for user in recipients}
    observed = hints(frames)
    assert len(observed) == len(expected)
    assert {channel for channel, _ in observed} == expected
    assert all(
        frame == {"v": 1, "type": EVENT, "appointment_id": str(appointment.pk)}
        for _, frame in observed
    )


@pytest.mark.parametrize("scopes", [[SCOPES[0]], SCOPES])
def test_new_request_one_hint_per_participant_only_after_outer_commit(world, publications, scopes):
    with transaction.atomic():
        rows = request(world, scopes)
        assert ECounselingConsent.objects.count() == len(scopes)
        assert publications == []
    assert_participants(world, publications)
    assert Notification.objects.count() == 1
    assert (
        len([frame for _, frame in publications if frame["type"] == "notifications.changed"]) == 1
    )
    publications.clear()
    assert request(world, scopes) == rows
    assert publications == []
    assert Notification.objects.count() == 1


@pytest.mark.parametrize("decision", ["APPROVED", "DENIED"])
def test_decision_only_after_commit_and_repeated_decision_is_rejected(
    world, publications, decision
):
    consent = request(world)[0]
    publications.clear()
    with transaction.atomic():
        decided = decide(world, consent, decision)
        assert decided["decision"] == decision
        assert publications == []
    assert_participants(world, publications)
    publications.clear()
    with pytest.raises(media.ECounselingConsentConflict):
        decide(world, consent, decision)
    assert publications == []


def test_withdrawal_only_after_commit_and_repeat_emits_nothing(world, publications):
    consent = request(world)[0]
    decide(world, consent)
    publications.clear()
    with transaction.atomic():
        withdrawn = withdraw(world, consent)
        assert withdrawn["withdrawn_at"] is not None and not withdrawn["effective"]
        assert publications == []
    assert_participants(world, publications)
    publications.clear()
    with pytest.raises(media.ECounselingConsentConflict):
        withdraw(world, consent)
    assert publications == []


def test_withdrawal_hint_precedes_provider_stop_failure_and_remains_durable(
    world, publications, settings
):
    consent = request(world)[0]
    decide(world, consent)
    _, _, counselor, appointment = world
    settings.DAILY_ENABLED = True
    client = FakeMediaDailyClient(fail_stop=True)
    from compass.ecounseling.services import create_join_credential

    create_join_credential(
        actor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    media.start_recording(
        counselor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=client,
    )
    publications.clear()
    original_stop = client.stop_recording

    def failing_stop(**kwargs):
        assert not connection.in_atomic_block
        assert ECounselingConsent.objects.get(pk=consent["id"]).withdrawn_at is not None
        assert_participants(world, publications)
        return original_stop(**kwargs)

    client.stop_recording = failing_stop
    with pytest.raises(ECounselingProviderUnavailable):
        withdraw(world, consent, daily_client=client)
    assert_participants(world, publications)
    assert ECounselingConsent.objects.get(pk=consent["id"]).withdrawn_at is not None


@pytest.mark.parametrize("operation", ["request", "approve", "deny", "withdraw"])
@pytest.mark.parametrize("nested", [False, True])
def test_outer_or_nested_rollback_discards_hint_and_state(world, publications, operation, nested):
    consent = None if operation == "request" else request(world)[0]
    if operation == "withdraw":
        decide(world, consent)
    publications.clear()
    before = list(ECounselingConsent.objects.values("id", "decision", "withdrawn_at"))

    def mutation():
        if operation == "request":
            request(world)
        elif operation == "withdraw":
            withdraw(world, consent)
        else:
            decide(world, consent, "DENIED" if operation == "deny" else "APPROVED")

    if nested:
        with transaction.atomic():
            with pytest.raises(RuntimeError), transaction.atomic():
                mutation()
                assert publications == []
                raise RuntimeError("synthetic savepoint rollback")
    else:
        with pytest.raises(RuntimeError), transaction.atomic():
            mutation()
            assert publications == []
            raise RuntimeError("synthetic outer rollback")
    assert publications == []
    assert list(ECounselingConsent.objects.values("id", "decision", "withdrawn_at")) == before


@pytest.mark.parametrize("operation", ["request", "approve", "deny", "withdraw"])
@pytest.mark.parametrize("transport", ["disabled", "refused"])
def test_transport_failure_never_changes_committed_operation(
    world, publications, settings, monkeypatch, operation, transport
):
    settings.REALTIME_ENABLED = False
    consent = None if operation == "request" else request(world)[0]
    if operation == "withdraw":
        decide(world, consent)
    if transport == "refused":
        settings.REALTIME_ENABLED = True
        # A real refused loopback connection, unrelated to the test Redis instance.
        client = redis.Redis(
            host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1
        )
        monkeypatch.setattr(publish, "_publish", ORIGINAL_PUBLISH)
        monkeypatch.setattr(publish, "realtime_redis", lambda: client)
        monkeypatch.setattr(notifications, "_safe_kick_email_delivery", lambda _: None)
        monkeypatch.setattr(notifications, "_safe_kick_push_delivery", lambda _: None)
    if operation == "request":
        result = request(world)[0]
        assert ECounselingConsent.objects.filter(pk=result["id"]).exists()
    elif operation == "withdraw":
        assert withdraw(world, consent)["withdrawn_at"] is not None
    else:
        decision = "DENIED" if operation == "deny" else "APPROVED"
        assert decide(world, consent, decision)["decision"] == decision
    assert publications == []


@pytest.mark.parametrize("participant", ["student", "counselor"])
@pytest.mark.parametrize(
    "change", ["disabled", "role", "workspace_capability", "consent_capability"]
)
def test_current_access_loss_before_commit_excludes_recipient(
    world, publications, participant, change
):
    _, student, counselor, _ = world
    actor = student if participant == "student" else counselor
    with transaction.atomic():
        request(world)
        if change == "disabled":
            actor.is_active = False
            actor.save(update_fields=["is_active"])
        elif change == "role":
            actor.role = Role.objects.get(code="IT_ADMIN")
            actor.save(update_fields=["role"])
        else:
            code = (
                (
                    "ecounseling.view_self"
                    if participant == "student"
                    else "ecounseling.view_assigned"
                )
                if change == "workspace_capability"
                else (
                    "ecounseling.consent_self"
                    if participant == "student"
                    else "ecounseling.manage_media_assigned"
                )
            )
            UserCapabilityOverride.objects.create(
                user=actor,
                capability=Capability.objects.get(code=code),
                effect="REVOKE",
                reason="Synthetic",
            )
        assert publications == []
    assert_participants(world, publications, [counselor if participant == "student" else student])


def test_reassignment_before_publish_targets_only_current_assigned_counselor(world, publications):
    _, student, _, appointment = world
    replacement = make_user("replacement@example.edu", "COUNSELOR")
    with transaction.atomic():
        request(world)
        appointment.provider = replacement
        appointment.save(update_fields=["provider"])
    assert_participants(world, publications, [student, replacement])


def test_reassignment_during_first_recipient_publication_is_resolved_again(
    world, publications, monkeypatch
):
    _, student, _, appointment = world
    replacement = make_user("mid-publication@example.edu", "COUNSELOR")
    original = consent_realtime.publish_to_user_on_commit

    def publish_current(user_id, event_type, fields):
        original(user_id, event_type, fields)
        if user_id == student.pk:
            appointment.provider = replacement
            appointment.save(update_fields=["provider"])

    monkeypatch.setattr(consent_realtime, "publish_to_user_on_commit", publish_current)
    request(world)
    assert_participants(world, publications, [student, replacement])


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN"])
def test_unrelated_or_designated_staff_never_qualify(world, publications, role):
    other = make_user(f"unrelated-{role}@example.edu", role)
    # Even explicit capabilities cannot override exact appointment ownership/role.
    for code in ("ecounseling.view_assigned", "ecounseling.manage_media_assigned"):
        UserCapabilityOverride.objects.create(
            user=other,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic",
        )
    request(world)
    assert_participants(world, publications)
    assert all(channel != protocol.user_channel(other.pk) for channel, _ in hints(publications))


def test_invalid_requests_and_wrong_participants_emit_nothing(world, publications):
    _, student, counselor, appointment = world
    for scopes in ([], [SCOPES[0], SCOPES[0]], ["not-a-scope"], ["TRANSCRIPT_STORAGE"]):
        with pytest.raises(media.ECounselingConsentConflict):
            media.request_consents(
                counselor=counselor,
                appointment_id=appointment.pk,
                scopes=scopes,
                context=context(counselor),
            )
    other = make_user("other-student@example.edu", "STUDENT")
    with pytest.raises(ECounselingNotPermitted):
        media.request_consents(
            counselor=student,
            appointment_id=appointment.pk,
            scopes=SCOPES,
            context=context(student),
        )
    assert publications == []
    consent = request(world)[0]
    publications.clear()
    with pytest.raises(ECounselingNotPermitted):
        media.decide_my_consent(
            student=other,
            appointment_id=appointment.pk,
            consent_id=consent["id"],
            decision="APPROVED",
            context=context(other),
        )
    with pytest.raises(media.ECounselingConsentConflict):
        decide(world, consent, "PENDING")
    assert publications == []


def test_resolution_failure_cannot_fail_committed_request_or_log_private_data(
    world, publications, monkeypatch, caplog
):
    private = "synthetic private content must not be logged"

    def fail(_, **kwargs):
        raise RuntimeError(private)

    monkeypatch.setattr(consent_realtime, "_recipient_id", fail)
    request(world)
    assert ECounselingConsent.objects.count() == 2
    assert hints(publications) == []
    assert private not in caplog.text
    assert "consent freshness hint was not published" in caplog.text


@pytest.mark.parametrize(
    "field", ["decision", "scope", "consent_id", "room_id", "timestamp", "student_id"]
)
def test_public_contract_rejects_every_extra_field(field):
    fields = {"appointment_id": str(uuid4()), field: str(uuid4())}
    with pytest.raises(ValueError):
        protocol.encode_event(EVENT, fields)
    assert protocol.decode_channel_message(json.dumps({"v": 1, "type": EVENT, **fields})) is None


@pytest.mark.parametrize(
    "identifier", [None, 1, True, "bad", "F0000000-0000-4000-8000-000000000001"]
)
def test_public_contract_rejects_malformed_appointment(identifier):
    with pytest.raises(ValueError):
        protocol.encode_event(EVENT, {"appointment_id": identifier})


def test_real_redis_socket_and_authorized_http_consent_flow(world, settings, monkeypatch):
    _, student, counselor, appointment = world
    settings.REALTIME_ENABLED = True
    realtime_connection._client.cache_clear()
    other = make_user("socket-other@example.edu", "COUNSELOR")
    clients = [auth_client(student), auth_client(counselor), auth_client(other)]
    student_path = f"/api/v1/e-counseling/me/appointments/{appointment.pk}/consents"
    counselor_path = f"/api/v1/e-counseling/appointments/{appointment.pk}/consents"
    frame = json.loads(protocol.encode_event(EVENT, {"appointment_id": appointment.pk}))

    async def database_call(function, *args, **kwargs):
        def call():
            try:
                return function(*args, **kwargs)
            finally:
                connections.close_all()

        return await asyncio.to_thread(call)

    async def receive(socket, expected):
        message = await socket.next()
        assert message["type"] == "websocket.send"
        assert json.loads(message["text"]) == expected

    async def test(app, _redis):
        sockets = []
        try:
            for client in clients:
                # Mint before opening each socket. HTTP/CSRF setup must not consume the
                # bounded socket authentication deadline, especially on a cold test database.
                ticket = await database_call(issue, client)
                assert ticket.status_code == 200
                socket = Socket(app)
                sockets.append(socket)
                await socket.ready(ticket.json()["ticket"])
            created = await database_call(
                clients[1].post,
                counselor_path,
                data=json.dumps({"scopes": SCOPES}),
                content_type="application/json",
            )
            assert created.status_code == 200
            await receive(sockets[0], {"v": 1, "type": "notifications.changed"})
            await receive(sockets[0], frame)
            await receive(sockets[1], frame)
            await sockets[2].nothing()
            listed = await database_call(clients[0].get, student_path)
            assert listed.status_code == 200 and len(listed.json()["items"]) == 2
            consent = next(row for row in listed.json()["items"] if row["scope"] == SCOPES[0])
            approved = await database_call(
                clients[0].post,
                f"{student_path}/{consent['id']}/decision",
                data='{"decision":"APPROVED"}',
                content_type="application/json",
            )
            assert approved.status_code == 200
            await receive(sockets[0], frame)
            await receive(sockets[1], frame)
            state = await database_call(clients[1].get, counselor_path)
            assert next(row for row in state.json()["items"] if row["id"] == consent["id"])[
                "effective"
            ]
            withdrawn = await database_call(
                clients[0].post,
                f"{student_path}/{consent['id']}/withdraw",
                data="{}",
                content_type="application/json",
            )
            assert withdrawn.status_code == 200 and withdrawn.json()["withdrawn_at"]
            await receive(sockets[0], frame)
            await receive(sockets[1], frame)
            state = await database_call(clients[1].get, counselor_path)
            assert not next(row for row in state.json()["items"] if row["id"] == consent["id"])[
                "effective"
            ]
            await sockets[2].nothing()
            denied = await database_call(clients[2].get, counselor_path)
            assert denied.status_code == 403
            # Leave sockets on real Redis; make only Django publication use a refused connection.
            refused = redis.Redis(
                host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1
            )
            monkeypatch.setattr(publish, "realtime_redis", lambda: refused)
            storage = next(row for row in listed.json()["items"] if row["scope"] == SCOPES[1])
            declined = await database_call(
                clients[0].post,
                f"{student_path}/{storage['id']}/decision",
                data='{"decision":"DENIED"}',
                content_type="application/json",
            )
            assert declined.status_code == 200 and declined.json()["decision"] == "DENIED"
            for socket in sockets:
                await socket.nothing()
            state = await database_call(clients[1].get, counselor_path)
            assert (
                next(row for row in state.json()["items"] if row["id"] == storage["id"])["decision"]
                == "DENIED"
            )
        finally:
            for socket in sockets:
                await socket.disconnect()

    try:
        run(test)
    finally:
        realtime_connection._client.cache_clear()
