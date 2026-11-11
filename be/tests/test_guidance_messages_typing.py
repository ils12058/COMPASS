"""GMSG-7: typing is a throttled, content-free hint to the other side; nothing is stored."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from compass.audit.models import AuditEvent
from compass.common.rate_limit import RateLimitResult, RateLimitUnavailable
from compass.guidance_messages import services
from compass.guidance_messages.errors import MessagesConflict, ReferralVoided, ThreadNotFound
from compass.guidance_messages.models import (
    GuidanceMessage,
    GuidanceThread,
    GuidanceThreadReadState,
)
from compass.realtime import publish
from realtime_service import protocol
from tests.test_guidance_messages import BASE, counseling, deny, office, world  # noqa: F401
from tests.test_guidance_messages_direct import open_direct
from tests.test_guidance_messages_referral import build_world as build_referral_world
from tests.test_guidance_messages_referral import open_thread as open_referral_thread
from tests.test_guidance_messages_referral import void as void_referral
from tests.test_notifications import auth_client

# Imported world fixture is injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db


class Limiter:
    """One hint per subject per window, like the Redis policy, without Redis."""

    def __init__(self):
        self.subjects = []
        self.unavailable = False

    def consume_with_failure_policy(self, policy, subject):
        if self.unavailable:
            raise RateLimitUnavailable("synthetic outage")
        self.subjects.append((policy.name, subject))
        count = sum(1 for _, seen in self.subjects if seen == subject)
        return RateLimitResult(
            allowed=count <= policy.limit,
            count=count,
            limit=policy.limit,
            remaining=max(policy.limit - count, 0),
            retry_after_seconds=policy.window_seconds,
        )


@pytest.fixture
def limiter(monkeypatch):
    fake = Limiter()
    monkeypatch.setattr(services, "RedisRateLimiter", SimpleNamespace(from_settings=lambda: fake))
    return fake


@pytest.fixture
def hints(settings, monkeypatch):
    frames = []
    monkeypatch.setattr(
        publish,
        "_publish",
        lambda channel, frame: frames.append((channel, json.loads(frame))) or True,
    )
    return frames


def receivers(frames):
    return {channel for channel, _ in frames}


def users(*people):
    return {protocol.user_channel(person.pk) for person in people}


def typing(actor, thread):
    return services.signal_typing(actor=actor, thread_id=thread.pk)


def test_requester_typing_reaches_office_readers_but_not_themselves(world, limiter, hints):
    thread, _ = office(world)
    assert typing(world.student, thread) is True
    assert receivers(hints) == users(world.counselor, world.goa, world.head, world.head_goa)
    assert all(
        frame == {"v": 1, "type": "messages.typing_changed", "thread_id": str(thread.pk)}
        for _, frame in hints
    )


def test_office_typing_reaches_only_the_requester(world, limiter, hints):
    thread, _ = office(world)
    assert typing(world.goa, thread) is True
    # Other staff never see a colleague typing, so "Student is typing" can never be wrong.
    assert receivers(hints) == users(world.student)


def test_pair_typing_reaches_only_the_other_person(world, limiter, hints):
    thread, _ = counseling(world)
    typing(world.counselor, thread)
    assert receivers(hints) == users(world.student)
    hints.clear()
    direct, _ = open_direct(world)
    typing(world.other, direct)
    assert receivers(hints) == users(world.counselor)


def test_typing_is_throttled_per_reader_and_thread(world, limiter, hints):
    thread, _ = office(world)
    assert typing(world.student, thread) is True
    hints.clear()
    assert typing(world.student, thread) is False
    assert hints == []
    assert typing(world.counselor, thread) is True
    assert limiter.subjects[0] == ("guidance-messages-typing", f"{world.student.pk}:{thread.pk}")


def test_unavailable_limiter_publishes_nothing_and_does_not_fail(world, limiter, hints):
    thread, _ = office(world)
    limiter.unavailable = True
    assert typing(world.student, thread) is False
    assert hints == []


def test_nothing_is_stored_or_audited(world, limiter, hints):
    thread, _ = office(world)
    before = (
        GuidanceMessage.objects.count(),
        GuidanceThreadReadState.objects.count(),
        AuditEvent.objects.count(),
        GuidanceThread.objects.get(pk=thread.pk).updated_at,
    )
    typing(world.student, thread)
    after = (
        GuidanceMessage.objects.count(),
        GuidanceThreadReadState.objects.count(),
        AuditEvent.objects.count(),
        GuidanceThread.objects.get(pk=thread.pk).updated_at,
    )
    assert before == after


def test_resolved_conversation_refuses_typing(world, limiter, hints):
    thread, _ = office(world)
    services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    with pytest.raises(MessagesConflict):
        typing(world.student, thread)
    assert hints == []


@pytest.mark.parametrize("name", ["other_student", "other", "admin", "officer"])
def test_outsiders_are_concealed(world, limiter, hints, name):
    thread, _ = counseling(world)
    with pytest.raises(ThreadNotFound):
        typing(getattr(world, name), thread)
    with pytest.raises(ThreadNotFound):
        services.signal_typing(actor=world.student, thread_id=uuid4())
    assert hints == []


def test_view_only_reader_cannot_signal(world, limiter, hints):
    thread, _ = office(world)
    deny(world.goa, "guidance_messages.manage")
    with pytest.raises(ThreadNotFound):
        typing(world.goa, thread)
    assert hints == []


def test_http_signal_is_204_with_no_body_and_concealment_is_404(world, limiter, hints):
    thread, _ = office(world)
    response = auth_client(world.student).post(f"{BASE}/threads/{thread.pk}/typing")
    assert response.status_code == 204
    assert response.content == b""
    assert response["Cache-Control"] == "no-store, private"
    hidden = auth_client(world.other_student).post(f"{BASE}/threads/{thread.pk}/typing")
    assert hidden.status_code == 404
    services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    resolved = auth_client(world.student).post(f"{BASE}/threads/{thread.pk}/typing")
    assert resolved.status_code == 409


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"thread_id": "bad"},
        {"thread_id": str(uuid4()), "sender_id": str(uuid4())},
        {"thread_id": str(uuid4()), "draft": "unsafe"},
        {"thread_id": str(uuid4()), "expires_in": 8},
    ],
)
def test_typing_hint_shape_is_exactly_one_thread_id(fields):
    with pytest.raises(ValueError):
        protocol.encode_event("messages.typing_changed", fields)
    assert (
        protocol.decode_channel_message(
            json.dumps({"v": 1, "type": "messages.typing_changed", **fields})
        )
        is None
    )


class TestReferralTyping:
    """The referred Student is never a participant and never learns anyone is typing."""

    @pytest.fixture
    def referral_world(self, monkeypatch):
        return build_referral_world(monkeypatch)

    def test_staff_typing_reaches_the_submitter_only(self, referral_world, limiter, hints):
        thread, _ = open_referral_thread(referral_world)
        services.signal_typing(actor=referral_world.counselor_a, thread_id=thread.pk)
        assert receivers(hints) == users(referral_world.faculty)
        hints.clear()
        services.signal_typing(actor=referral_world.faculty, thread_id=thread.pk)
        assert receivers(hints) == users(
            referral_world.counselor_a, referral_world.goa_a, referral_world.head
        )
        assert protocol.user_channel(referral_world.student.pk) not in receivers(hints)

    def test_voided_referral_refuses_typing(self, referral_world, limiter, hints):
        thread, _ = open_referral_thread(referral_world)
        void_referral(referral_world)
        with pytest.raises(ReferralVoided):
            services.signal_typing(actor=referral_world.faculty, thread_id=thread.pk)
        assert hints == []
