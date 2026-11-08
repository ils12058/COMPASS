"""GMSG-6: Seen comes only from genuine read cursors; nothing claims delivery."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from compass.audit.models import AuditEvent
from compass.guidance_messages import services
from compass.guidance_messages.models import GuidanceThreadReadState
from compass.organization.models import CounselorResponsibility
from compass.realtime import publish
from realtime_service import protocol
from tests.test_guidance_messages import BASE, counseling, office, send, world  # noqa: F401
from tests.test_guidance_messages_faculty import faculty, inquiry, with_intake
from tests.test_notifications import auth_client

# Imported world fixture is injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db


def seen(actor, thread):
    return services.thread_receipt(services.get_thread(actor=actor, thread_id=thread.pk), actor)


def read(actor, thread, sequence):
    return services.mark_read(actor=actor, thread_id=thread.pk, sequence=sequence)


@pytest.fixture
def publications(settings, monkeypatch):
    settings.REALTIME_ENABLED = True
    frames = []
    monkeypatch.setattr(
        publish,
        "_publish",
        lambda channel, frame: frames.append((channel, json.loads(frame))) or True,
    )
    return frames


def channels(frames):
    return {channel for channel, _ in frames}


def test_counseling_pair_sees_only_the_counterpart_cursor(world):
    thread, _ = counseling(world)
    assert seen(world.student, thread) == ("PERSON", 0)
    assert seen(world.counselor, thread) == ("PERSON", 0)
    read(world.counselor, thread, 1)
    assert seen(world.student, thread) == ("PERSON", 1)
    # A reader's own cursor never becomes their own receipt.
    assert seen(world.counselor, thread) == ("PERSON", 0)


def test_requester_sees_seen_by_office_from_any_authorized_office_read(world):
    thread, _ = office(world)
    assert seen(world.student, thread) == ("OFFICE", 0)
    read(world.goa, thread, 1)
    assert seen(world.student, thread) == ("OFFICE", 1)
    read(world.counselor, thread, 1)
    assert seen(world.student, thread) == ("OFFICE", 1)


def test_office_staff_see_the_students_cursor_never_a_colleagues(world):
    thread, _ = office(world)
    send(world, thread, actor=world.counselor)
    read(world.counselor, thread, 2)
    assert seen(world.goa, thread) == ("PERSON", 0)
    read(world.student, thread, 2)
    assert seen(world.goa, thread) == ("PERSON", 2)
    assert seen(world.counselor, thread) == ("PERSON", 2)


def test_office_seen_does_not_revert_when_the_reader_loses_access(world):
    thread, _ = office(world)
    read(world.counselor, thread, 1)
    CounselorResponsibility.objects.filter(counselor=world.counselor).delete()
    assert seen(world.student, thread) == ("OFFICE", 1)


def test_faculty_inquiry_withholds_the_requesters_seen_from_staff(world):
    requester = faculty()
    holder = with_intake(world.other)
    thread, _ = inquiry(requester)
    assert seen(holder, thread) == (None, None)
    assert seen(requester, thread) == ("OFFICE", 0)
    read(holder, thread, 1)
    assert seen(requester, thread) == ("OFFICE", 1)
    send(world, thread, actor=holder)
    read(requester, thread, 2)
    assert seen(holder, thread) == (None, None)


def test_loading_the_directory_or_thread_never_marks_anything_seen(world):
    thread, _ = office(world)
    services.list_threads(actor=world.counselor)
    services.get_thread(actor=world.counselor, thread_id=thread.pk)
    services.list_messages(actor=world.counselor, thread_id=thread.pk)
    assert not GuidanceThreadReadState.objects.filter(user=world.counselor).exists()
    assert seen(world.student, thread) == ("OFFICE", 0)


def test_cursor_is_monotonic_and_audit_free(world):
    thread, _ = office(world)
    send(world, thread, actor=world.counselor)
    audits = AuditEvent.objects.count()
    assert read(world.student, thread, 2).last_read_sequence == 2
    assert read(world.student, thread, 1).last_read_sequence == 2
    assert read(world.student, thread, 0).last_read_sequence == 2
    assert AuditEvent.objects.count() == audits


def test_database_guard_never_moves_a_cursor_back(world, monkeypatch):
    thread, _ = office(world)
    for _ in range(3):
        send(world, thread, actor=world.counselor)
    read(world.student, thread, 1)
    state = GuidanceThreadReadState.objects.get(thread=thread, user=world.student)
    real = GuidanceThreadReadState.objects.get_or_create

    def stale(**kwargs):
        # A stale in-memory row: the database already holds a further cursor.
        row, created = real(**kwargs)
        GuidanceThreadReadState.objects.filter(pk=row.pk).update(last_read_sequence=4)
        return row, created

    monkeypatch.setattr(GuidanceThreadReadState.objects, "get_or_create", stale)
    assert read(world.student, thread, 3).last_read_sequence == 4
    state.refresh_from_db()
    assert state.last_read_sequence == 4


def test_read_hints_reach_only_the_counterpart_who_can_see_the_receipt(
    world, publications, django_capture_on_commit_callbacks
):
    thread, _ = office(world)
    student_channel = protocol.user_channel(world.student.pk)
    publications.clear()
    with django_capture_on_commit_callbacks(execute=True):
        read(world.counselor, thread, 1)
    # The Student learns "Seen by Guidance Office"; no other staff member is told anything.
    assert channels(publications) == {protocol.user_channel(world.counselor.pk), student_channel}

    publications.clear()
    with django_capture_on_commit_callbacks(execute=True):
        read(world.goa, thread, 1)
    # Office Seen did not move, so only the reader's own sessions refresh.
    assert channels(publications) == {protocol.user_channel(world.goa.pk)}

    send(world, thread, actor=world.counselor)
    publications.clear()
    with django_capture_on_commit_callbacks(execute=True):
        read(world.student, thread, 2)
    staff = {world.counselor, world.goa, world.head, world.head_goa}
    assert channels(publications) == {student_channel} | {
        protocol.user_channel(user.pk) for user in staff
    }
    assert all(
        frame == {"v": 1, "type": "messages.thread_changed", "thread_id": str(thread.pk)}
        for _, frame in publications
    )


def test_reading_only_your_own_messages_tells_nobody_else(
    world, publications, django_capture_on_commit_callbacks
):
    thread, _ = counseling(world)
    publications.clear()
    with django_capture_on_commit_callbacks(execute=True):
        read(world.student, thread, 1)
    assert channels(publications) == {protocol.user_channel(world.student.pk)}


def test_thread_payload_carries_the_receipt_and_nothing_about_the_reader(world):
    thread, _ = office(world)
    read(world.counselor, thread, 1)
    payload = auth_client(world.student).get(f"{BASE}/threads/{thread.pk}").json()
    assert payload["seen_sequence"] == 1
    assert payload["seen_scope"] == "OFFICE"
    assert str(world.counselor.pk) not in json.dumps(payload)
    listed = auth_client(world.student).get(f"{BASE}/threads").json()["items"][0]
    assert (listed["seen_sequence"], listed["seen_scope"]) == (1, "OFFICE")
    staff = auth_client(world.counselor).get(f"{BASE}/threads/{thread.pk}").json()
    assert (staff["seen_sequence"], staff["seen_scope"]) == (0, "PERSON")


def test_unknown_thread_receipt_is_concealed(world):
    response = auth_client(world.student).get(f"{BASE}/threads/{uuid4()}")
    assert response.status_code == 404
