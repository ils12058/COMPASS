"""Eligible Office handlers (ADR-104): current workload decides, and assignment never grants."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from compass.accounts.models import Designation
from compass.audit.models import AuditEvent
from compass.guidance_messages import policy, services
from compass.guidance_messages.errors import InvalidMessageInput, ThreadNotFound
from compass.organization.models import (
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.realtime import publish
from tests.test_guidance_messages import BASE, counseling, deny, office, world  # noqa: F401
from tests.test_notifications import auth_client

# Imported fixture names are intentionally consumed by pytest injection.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db


def eligible(world, thread, *, actor=None, **query):
    rows, _ = services.eligible_handlers(
        actor=actor or world.counselor, thread_id=thread.pk, **query
    )
    return [row.pk for row in rows]


def office_in(world, college_index):
    StudentAffiliation.objects.filter(student=world.student).update(
        college=world.colleges[college_index]
    )
    thread, _ = office(world)
    return thread


def assign(client, thread, handler):
    return client.patch(
        f"{BASE}/threads/{thread.pk}/handler",
        data=json.dumps({"handler_id": str(handler.pk)}),
        content_type="application/json",
    )


# A. Ordinary Counselor and B. their supervised staff.
def test_ordinary_counselor_college_lists_its_counselor_and_supervised_staff(world):
    thread, _ = office(world)
    expected = sorted([world.counselor, world.gss], key=lambda user: user.get_full_name().lower())
    for actor in [world.counselor, world.gss]:
        assert eligible(world, thread, actor=actor) == [user.pk for user in expected]
    # Another Counselor's College, the Head and the Head's staff are not this College's handlers.
    for outsider in [world.other, world.head, world.head_gss]:
        assert not policy.eligible_handler(outsider, thread)


@pytest.mark.parametrize("breakage", ["removed", "inactive-supervisor", "non-counselor"])
def test_staff_are_eligible_only_through_valid_current_supervision(world, breakage):
    thread, _ = office(world)
    if breakage == "removed":
        StaffSupervision.objects.filter(staff=world.gss).delete()
    elif breakage == "inactive-supervisor":
        StaffSupervision.objects.filter(staff=world.gss).update(supervisor=world.other)
        world.other.is_active = False
        world.other.save(update_fields=("is_active",))
    else:
        StaffSupervision.objects.filter(staff=world.gss).update(supervisor=world.admin)
    assert world.gss.pk not in eligible(world, thread)


# C. Head and D. Head's supervised staff.
@pytest.mark.parametrize("college_index", [2, 3], ids=["explicit", "unique-head-fallback"])
def test_head_and_head_staff_for_explicit_or_unique_fallback_colleges(world, college_index):
    thread = office_in(world, college_index)
    for actor in [world.head, world.head_gss]:
        assert set(eligible(world, thread, actor=actor)) == {world.head.pk, world.head_gss.pk}
    for outsider in [world.counselor, world.gss, world.other]:
        assert not policy.eligible_handler(outsider, thread)


def test_head_designation_never_inherits_another_counselors_college(world):
    thread = office_in(world, 1)
    assert set(eligible(world, thread, actor=world.other)) == {world.other.pk}
    for actor in [world.head, world.head_gss]:
        assert not policy.eligible_handler(actor, thread)
        with pytest.raises(ThreadNotFound):
            services.eligible_handlers(actor=actor, thread_id=thread.pk)


def test_inactive_counselors_college_falls_back_only_to_the_unique_head(world):
    thread, _ = office(world)
    world.counselor.is_active = False
    world.counselor.save(update_fields=("is_active",))
    assert set(eligible(world, thread, actor=world.head)) == {world.head.pk, world.head_gss.pk}


# E. Multiple Heads.
def test_multiple_heads_fail_closed_for_fallback_colleges(world):
    fallback = office_in(world, 3)
    world.other.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    assert policy.eligible_handlers(fallback) == []
    for actor in [world.head, world.head_gss, world.other]:
        with pytest.raises(ThreadNotFound):
            services.eligible_handlers(actor=actor, thread_id=fallback.pk)
    # An explicit Head responsibility is still explicit; the second Head inherits nothing.
    StudentAffiliation.objects.filter(student=world.student).update(college=world.colleges[2])
    fallback.routing_college = world.colleges[2]
    fallback.save(update_fields=("routing_college",))
    assert set(eligible(world, fallback, actor=world.head)) == {world.head.pk, world.head_gss.pk}


# F. Inactive users and G. capability.
def test_inactive_staff_are_excluded(world):
    thread, _ = office(world)
    world.gss.is_active = False
    world.gss.save(update_fields=("is_active",))
    assert eligible(world, thread) == [world.counselor.pk]


@pytest.mark.parametrize("code", ["guidance_messages.manage", "guidance_messages.view"])
def test_capability_override_removing_manage_makes_a_candidate_ineligible(world, code):
    thread, _ = office(world)
    deny(world.gss, code)
    assert eligible(world, thread) == [world.counselor.pk]
    with pytest.raises(InvalidMessageInput):
        services.assign_handler(actor=world.counselor, thread_id=thread.pk, handler_id=world.gss.pk)


# H. Unauthorized requesters and I. Counseling threads are concealed.
@pytest.mark.parametrize(
    "actor", ["student", "other_student", "other", "head", "head_gss", "admin", "dpo"]
)
def test_unauthorized_requesters_are_concealed(world, actor):
    thread, _ = office(world)
    response = auth_client(getattr(world, actor)).get(
        f"{BASE}/threads/{thread.pk}/eligible-handlers"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "guidance_thread_not_found"
    assert "Synthetic" not in response.content.decode()


def test_view_only_staff_and_guessed_threads_are_concealed(world):
    thread, _ = office(world)
    deny(world.gss, "guidance_messages.manage")
    client = auth_client(world.gss)
    assert client.get(f"{BASE}/threads/{thread.pk}/eligible-handlers").status_code == 404
    assert client.get(f"{BASE}/threads/{uuid4()}/eligible-handlers").status_code == 404
    guessed = auth_client(world.counselor).get(f"{BASE}/threads/{uuid4()}/eligible-handlers")
    assert guessed.json()["error"]["code"] == "guidance_thread_not_found"


def test_counseling_threads_have_no_handlers(world):
    thread, _ = counseling(world)
    response = auth_client(world.counselor).get(f"{BASE}/threads/{thread.pk}/eligible-handlers")
    assert response.status_code == 404
    with pytest.raises(ThreadNotFound):
        services.eligible_handlers(actor=world.counselor, thread_id=thread.pk)
    assert policy.eligible_handlers(thread) == []


# J. A listed candidate can become stale before Assign.
def test_stale_candidate_is_rejected_by_the_assignment_revalidation(world):
    thread, _ = office(world)
    client = auth_client(world.counselor)
    listed = client.get(f"{BASE}/threads/{thread.pk}/eligible-handlers").json()["items"]
    assert str(world.gss.pk) in {item["id"] for item in listed}
    StaffSupervision.objects.filter(staff=world.gss).delete()
    response = assign(client, thread, world.gss)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_guidance_message_input"
    thread.refresh_from_db()
    assert thread.assigned_to_id == world.counselor.pk
    assert not AuditEvent.objects.filter(action="guidance_messages.thread.assigned").exists()


@pytest.mark.parametrize("handler", ["other", "head", "student", "admin"])
def test_assignment_rejects_anyone_the_list_would_not_offer(world, handler):
    thread, _ = office(world)
    response = assign(auth_client(world.counselor), thread, getattr(world, handler))
    assert response.status_code == 422
    assert getattr(world, handler).pk not in eligible(world, thread)


# K. Bounded fields, explicit name search and pagination.
def test_response_is_bounded_and_private(world):
    thread, _ = office(world)
    response = auth_client(world.counselor).get(f"{BASE}/threads/{thread.pk}/eligible-handlers")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private"
    page = response.json()
    assert set(page) == {"items", "page", "page_size", "has_next"}
    for item in page["items"]:
        assert set(item) == {"id", "display_name", "role"}
        assert item["role"] in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
    assert {item["role"] for item in page["items"]} == {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
    assert "@" not in response.content.decode()
    assert (
        not AuditEvent.objects.filter(action__startswith="guidance_messages.thread.")
        .exclude(action="guidance_messages.thread.created")
        .exists()
    )


def test_search_matches_display_name_only_and_pages_deterministically(world):
    thread, _ = office(world)
    assert eligible(world, thread, search="  GSS ") == [world.gss.pk]
    assert eligible(world, thread, search="synthetic counselor") == [world.counselor.pk]
    assert eligible(world, thread, search=world.gss.email) == []
    assert eligible(world, thread, search="example.edu") == []
    first, more = services.eligible_handlers(
        actor=world.counselor, thread_id=thread.pk, page=1, page_size=1
    )
    second, last = services.eligible_handlers(
        actor=world.counselor, thread_id=thread.pk, page=2, page_size=1
    )
    assert more and not last
    assert [row.pk for row in [*first, *second]] == eligible(world, thread)
    client = auth_client(world.counselor)
    for query in ["page=0", "page_size=51", "search=" + "x" * 161]:
        assert (
            client.get(f"{BASE}/threads/{thread.pk}/eligible-handlers?{query}").status_code == 422
        )


def test_listing_handlers_changes_nothing_and_publishes_nothing(
    world, settings, monkeypatch, django_capture_on_commit_callbacks
):
    thread, _ = office(world)
    settings.REALTIME_ENABLED = True
    frames = []
    monkeypatch.setattr(publish, "_publish", lambda channel, frame: frames.append(frame) or True)
    events = AuditEvent.objects.count()
    with django_capture_on_commit_callbacks(execute=True):
        auth_client(world.counselor).get(f"{BASE}/threads/{thread.pk}/eligible-handlers")
    assert frames == []
    assert AuditEvent.objects.count() == events


# Assignment is workflow ownership: it never preserves or grants access.
def test_assignment_never_grants_or_preserves_content_access(
    world, settings, monkeypatch, django_capture_on_commit_callbacks
):
    thread, _ = office(world)
    settings.REALTIME_ENABLED = True
    frames = []
    monkeypatch.setattr(
        publish, "_publish", lambda channel, frame: frames.append(json.loads(frame)) or True
    )
    sequence = thread.last_sequence
    with django_capture_on_commit_callbacks(execute=True):
        response = assign(auth_client(world.counselor), thread, world.gss)
    assert response.status_code == 200
    assert response.json()["assigned_to"]["id"] == str(world.gss.pk)
    assert {frame["type"] for frame in frames} == {"messages.thread_changed"}
    assert all(set(frame) <= {"v", "type", "thread_id"} for frame in frames)
    thread.refresh_from_db()
    assert thread.last_sequence == sequence
    assert thread.messages.count() == sequence
    StaffSupervision.objects.filter(staff=world.gss).delete()
    thread.refresh_from_db()
    assert thread.assigned_to_id == world.gss.pk
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=world.gss, thread_id=thread.pk)
    assert auth_client(world.gss).get(f"{BASE}/threads/{thread.pk}/messages").status_code == 404
    # A College Counselor keeps access without being the assignee.
    assert services.get_thread(actor=world.counselor, thread_id=thread.pk).pk == thread.pk


def test_responsibility_change_moves_eligibility_with_the_college(world):
    thread, _ = office(world)
    CounselorResponsibility.objects.filter(college=world.colleges[0]).update(counselor=world.other)
    assert eligible(world, thread, actor=world.other) == [world.other.pk]
    assert not policy.eligible_handler(world.counselor, thread)
    assert not policy.eligible_handler(world.gss, thread)
