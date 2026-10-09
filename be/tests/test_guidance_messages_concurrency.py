"""Real independent PostgreSQL transactions; no mocked sequence/idempotency allocator."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import connections, transaction

from compass.audit.models import AuditEvent
from compass.guidance_messages import services
from compass.guidance_messages.errors import GuidanceMessageContentUnavailable
from compass.guidance_messages.models import GuidanceMessage, GuidanceThread
from tests.test_guidance_messages import BODY, counseling, office, world  # noqa: F401

# Imported world fixture is injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db(transaction=True)


def parallel(count, function):
    barrier = Barrier(count)

    def call(index):
        try:
            barrier.wait(timeout=30)
            return function(index)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(call, index) for index in range(count)]
        return [future.result(timeout=90) for future in futures]


@pytest.mark.parametrize("attempts", [20, 32])
def test_duplicate_send_concurrency_is_exactly_one_row_and_sequence(world, attempts):
    thread, _ = office(world)
    key = uuid4()
    messages = parallel(
        attempts,
        lambda _: services.send_message(
            actor=world.student, thread_id=thread.pk, client_message_id=key, body=BODY
        ),
    )
    assert len({message.pk for message in messages}) == 1
    assert GuidanceMessage.objects.filter(sender=world.student, client_message_id=key).count() == 1
    thread.refresh_from_db()
    assert thread.last_sequence == 2
    assert GuidanceMessage.objects.filter(thread=thread).count() == 2
    assert (
        AuditEvent.objects.filter(
            action="guidance_messages.message.sent", target_id=str(thread.pk)
        ).count()
        == 2
    )


@pytest.mark.parametrize("kind", ["OFFICE", "COUNSELING"])
def test_concurrent_creation_has_one_thread_and_first_message(world, kind):
    key = uuid4()

    def create(_):
        if kind == "OFFICE":
            return services.open_office_thread(
                actor=world.student, client_message_id=key, body=BODY
            )
        return services.open_counseling_thread(
            actor=world.student,
            appointment_id=world.appointment.pk,
            client_message_id=key,
            body=BODY,
        )

    results = parallel(20, create)
    assert len({thread.pk for thread, _ in results}) == 1
    assert len({message.pk for _, message in results}) == 1
    assert GuidanceThread.objects.count() == GuidanceMessage.objects.count() == 1


def test_distinct_concurrent_senders_have_contiguous_committed_sequences(world):
    thread, _ = office(world)
    users = [world.student, world.counselor, world.gss]
    messages = parallel(
        24,
        lambda index: services.send_message(
            actor=users[index % len(users)],
            thread_id=thread.pk,
            client_message_id=uuid4(),
            body=f"Synthetic concurrent message {index}",
        ),
    )
    assert sorted(message.sequence for message in messages) == list(range(2, 26))
    assert len({message.pk for message in messages}) == 24
    thread.refresh_from_db()
    latest = GuidanceMessage.objects.get(thread=thread, sequence=25)
    assert thread.last_sequence == latest.sequence
    assert thread.last_message_at == latest.created_at


def test_concurrent_read_updates_never_regress(world):
    thread, _ = office(world)
    for _ in range(7):
        services.send_message(
            actor=world.counselor, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
    parallel(
        16,
        lambda index: services.mark_read(
            actor=world.student, thread_id=thread.pk, sequence=index % 9
        ),
    )
    result = services.get_thread(actor=world.student, thread_id=thread.pk)
    assert result.own_last_read_sequence == 8
    assert result.own_unread_count == 0


def test_rollback_and_encryption_failure_leave_no_phantom_or_sequence_gap(world, settings):
    thread, _ = office(world)
    before = AuditEvent.objects.count()
    with pytest.raises(RuntimeError, match="synthetic rollback"), transaction.atomic():
        services.send_message(
            actor=world.student, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
        raise RuntimeError("synthetic rollback")
    assert GuidanceMessage.objects.count() == 1
    assert AuditEvent.objects.count() == before
    original = settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ()
    with pytest.raises(GuidanceMessageContentUnavailable):
        services.send_message(
            actor=world.student, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
        )
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = original
    message = services.send_message(
        actor=world.student, thread_id=thread.pk, client_message_id=uuid4(), body=BODY
    )
    assert message.sequence == 2
    thread.refresh_from_db()
    assert thread.last_sequence == 2


@pytest.mark.parametrize("kind", ["OFFICE", "COUNSELING"])
def test_different_participants_concurrently_open_the_same_anchor(world, kind):
    actors = [world.student, world.gss if kind == "OFFICE" else world.counselor]
    client_id = uuid4()

    def create(index):
        actor = actors[index % 2]
        if kind == "OFFICE":
            return services.open_office_thread(
                actor=actor,
                student_id=world.student.pk if actor != world.student else None,
                client_message_id=client_id,
                body=BODY,
            )
        return services.open_counseling_thread(
            actor=actor, appointment_id=world.appointment.pk, client_message_id=client_id, body=BODY
        )

    results = parallel(20, create)
    assert len({thread.pk for thread, _ in results}) == 1
    assert GuidanceThread.objects.count() == 1
    # Sender is part of idempotency identity; each participant intended one Message.
    assert GuidanceMessage.objects.count() == 2
    assert sorted(GuidanceMessage.objects.values_list("sequence", flat=True)) == [1, 2]


def test_simultaneous_client_id_reuse_across_threads_conflicts_safely(world):
    from compass.guidance_messages.errors import MessagesConflict

    first, _ = office(world)
    second, _ = counseling(world)
    client_id = uuid4()

    def attempt(index):
        try:
            message = services.send_message(
                actor=world.student,
                thread_id=[first.pk, second.pk][index % 2],
                client_message_id=client_id,
                body=BODY,
            )
            return message.pk
        except MessagesConflict:
            return None

    results = parallel(20, attempt)
    assert None in results
    assert len({result for result in results if result is not None}) == 1
    assert (
        GuidanceMessage.objects.filter(sender=world.student, client_message_id=client_id).count()
        == 1
    )
    assert sorted(GuidanceThread.objects.values_list("last_sequence", flat=True)) == [1, 2]
