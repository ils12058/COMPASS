"""Canonical state, policy and bounded merge proofs; all records and names are synthetic."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.call_slips.models import CallSlip
from compass.good_moral.models import GoodMoralRequest
from compass.guidance_messages import services as messages
from compass.guidance_messages.models import GuidanceThread
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.organization.models import StaffSupervision
from compass.routine_interviews.models import RoutineInterview
from compass.work_queue import services
from compass.work_queue.schemas import WorkKind
from tests.test_guidance_messages import counseling, deny, office, send, world  # noqa: F401
from tests.test_notifications import auth_client

# ruff: noqa: F811
pytestmark = pytest.mark.django_db


def queue(world, actor=None, **kwargs):
    return services.list_work(actor=actor or world.counselor, **kwargs).items


def assign(world, thread, actor=None):
    return messages.assign_handler(
        actor=world.counselor, thread_id=thread.pk, handler_id=(actor or world.counselor).pk
    )


def routine(world, **kwargs):
    return RoutineInterview.objects.create(
        student=world.student,
        counselor=world.counselor,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=timezone.now(),
        student_intake_ciphertext="unread-by-projection",
        counselor_evaluation_ciphertext="unread",
        **kwargs,
    )


def good_moral(world, student=None):
    return GoodMoralRequest.objects.create(student=student or world.student, variant="GRADUATE")


def call_slip(world, *, now, student=None, **kwargs):
    revision = FormRevision.objects.create(
        family=FormFamily.objects.create(
            key="work-call-" + str(timezone.now().timestamp()), title="Synthetic"
        ),
        internal_schema_version=1,
    )
    return CallSlip.objects.create(
        student=student or world.student,
        student_name_snapshot="Synthetic",
        course_year_snapshot="Synthetic",
        destination_type="GUIDANCE_OFFICE",
        report_at=now,
        issuance_mode="LIVE",
        issued_by=world.counselor,
        issued_by_name_snapshot="Synthetic",
        form_revision=revision,
        **kwargs,
    )


def test_office_reply_read_reply_reassignment_and_scope(world):
    thread, _ = office(world)
    GuidanceThread.objects.filter(pk=thread.pk).update(assigned_to=None)
    assert queue(world) == []  # unassigned is not personal work
    assign(world, thread)
    assert [i.source_id for i in queue(world)] == [thread.pk]
    messages.mark_read(actor=world.counselor, thread_id=thread.pk, sequence=1)
    assert len(queue(world)) == 1
    send(world, thread, actor=world.gss)
    assert queue(world) == []  # any staff reply changes the latest sender
    send(world, thread)
    assert len(queue(world)) == 1
    assign(world, thread, world.gss)
    assert queue(world) == []
    assert len(queue(world, world.gss)) == 1
    StaffSupervision.objects.filter(staff=world.gss).delete()
    assert queue(world, world.gss) == []
    assert GuidanceThread.objects.get(pk=thread.pk).assigned_to_id == world.gss.pk


def test_reply_resolution_and_removed_capability(world):
    thread, _ = office(world)
    assign(world, thread)
    messages.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    assert queue(world) == []
    messages.set_status(actor=world.counselor, thread_id=thread.pk, resolved=False)
    deny(world.counselor, "guidance_messages.manage")
    assert queue(world) == []


def test_counseling_exact_persisted_provider(world):
    thread, _ = counseling(world)
    assert len(queue(world)) == 1
    for actor in [world.gss, world.head, world.other]:
        assert queue(world, actor) == []
    world.appointment.provider = world.other
    world.appointment.save(update_fields=["provider"])
    assert len(queue(world)) == 1
    assert queue(world, world.other) == []
    send(world, thread, actor=world.counselor)
    assert queue(world) == []


def test_message_projection_never_decrypts_or_selects_ciphertext(world, settings):
    thread, _ = office(world)
    assign(world, thread)
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ""
    with patch(
        "compass.guidance_messages.content.read_body", side_effect=AssertionError("decrypt")
    ):
        with CaptureQueriesContext(connection) as queries:
            result = queue(world)
    assert len(result) == 1
    assert all("body_ciphertext" not in q["sql"] for q in queries)
    data = result[0].model_dump(mode="json")
    assert set(data) == {
        "id",
        "kind",
        "priority",
        "source_id",
        "student",
        "conversation_kind",
        "due_at",
        "waiting_since",
    }
    assert set(data["student"]) == {"id", "display_name"}


def test_routine_assigned_pending_and_closed_parent(world):
    direct = routine(world)
    linked = RoutineInterview.objects.create(
        student=world.student,
        counselor=world.counselor,
        appointment=world.appointment,
        entry_mode="APPOINTMENT",
        delivery_mode="IN_PERSON",
        intake_submitted_at=timezone.now(),
        student_intake_ciphertext="unread",
        counselor_evaluation_ciphertext="unread",
    )
    assert {i.source_id for i in queue(world)} == {direct.pk, linked.pk}
    assert queue(world, world.other) == queue(world, world.gss) == []
    world.appointment.status = "CANCELLED"
    world.appointment.cancelled_at = timezone.now()
    world.appointment.cancelled_by = world.counselor
    world.appointment.save(update_fields=["status", "cancelled_at", "cancelled_by"])
    assert [i.source_id for i in queue(world)] == [direct.pk]
    deny(world.counselor, "routine_interviews.manage_assigned")
    assert queue(world) == []


def test_good_moral_officewide_separate_prepare_and_issue(world):
    row = good_moral(world, world.other_student)
    assert queue(world, world.gss)[0].kind == WorkKind.GOOD_MORAL_PREPARATION
    deny(world.gss, "good_moral.prepare")
    assert queue(world, world.gss) == []
    GoodMoralRequest.objects.filter(pk=row.pk).update(
        status="READY_FOR_ISSUANCE", prepared_at=timezone.now(), prepared_by=world.counselor
    )
    assert queue(world)[0].kind == WorkKind.GOOD_MORAL_ISSUANCE
    UserCapabilityOverride.objects.create(
        user=world.gss,
        capability=Capability.objects.get(code="good_moral.issue"),
        effect="GRANT",
        reason="Synthetic",
    )
    assert queue(world, world.gss) == []  # the domain still requires a Counselor
    deny(world.counselor, "good_moral.issue")
    assert queue(world) == []


def test_call_slip_due_equality_future_completion_and_head_scope(world):
    now = timezone.now()
    past = call_slip(world, now=now - timedelta(seconds=1))
    exact = call_slip(world, now=now)
    future = call_slip(world, now=now + timedelta(seconds=1))
    outside = call_slip(world, now=now, student=world.other_student)
    with patch.object(services.timezone, "now", return_value=now):
        assert {i.source_id for i in queue(world)} == {past.pk, exact.pk}
        assert {i.source_id for i in queue(world, world.head)} == {past.pk, exact.pk, outside.pk}
        assert {i.source_id for i in queue(world, world.head_gss)} == set()
        CallSlip.objects.filter(pk=past.pk).update(interview_ended_at=now)
        CallSlip.objects.filter(pk=exact.pk).update(
            voided_at=now, voided_by=world.counselor, void_reason="Synthetic"
        )
        assert queue(world) == []
        assert future.pk not in {i.source_id for i in queue(world, world.head)}


def test_global_interleaved_rank_and_pages(world):
    now = timezone.now()
    gm = good_moral(world)
    pending = routine(world)
    thread, _ = office(world)
    assign(world, thread)
    GuidanceThread.objects.filter(pk=thread.pk).update(last_message_at=now - timedelta(days=3))
    RoutineInterview.objects.filter(pk=pending.pk).update(
        intake_submitted_at=now - timedelta(days=2)
    )
    GoodMoralRequest.objects.filter(pk=gm.pk).update(created_at=now - timedelta(days=1))
    later = call_slip(world, now=now - timedelta(hours=1))
    earlier = call_slip(world, now=now - timedelta(hours=2))
    expected = [earlier.pk, later.pk, thread.pk, pending.pk, gm.pk]
    assert [i.source_id for i in queue(world)] == expected
    pages = [services.list_work(actor=world.counselor, page=p, page_size=2) for p in [1, 2, 3]]
    assert [i.source_id for page in pages for i in page.items] == expected
    assert [page.has_next for page in pages] == [True, True, False]
    # Equal waiting facts use stable kind+UUID, not created_at or incidental ORM order.
    GuidanceThread.objects.filter(pk=thread.pk).update(last_message_at=now)
    RoutineInterview.objects.filter(pk=pending.pk).update(intake_submitted_at=now)
    GoodMoralRequest.objects.filter(pk=gm.pk).update(created_at=now)
    action = [i for i in queue(world) if i.waiting_since]
    assert [i.id for i in action] == sorted(i.id for i in action)


@pytest.mark.parametrize("actor", ["student", "admin", "dpo"])
def test_other_roles_are_denied(world, actor):
    assert auth_client(getattr(world, actor)).get("/api/v1/work").status_code == 403


def test_inactive_and_stale_actor_denied(world):
    type(world.counselor).objects.filter(pk=world.counselor.pk).update(is_active=False)
    with pytest.raises(services.WorkQueueAccessDenied):
        queue(world)


@pytest.mark.parametrize("query", ["page=0", "page=101", "page_size=0", "page_size=51", "page=no"])
def test_pagination_is_bounded_at_api(world, query):
    assert auth_client(world.counselor).get("/api/v1/work?" + query).status_code == 422


def test_each_source_gets_only_required_prefix_and_failures_propagate(world):
    names = [
        "reply_needed_threads",
        "pending_evaluations",
        "preparation_requests",
        "issuance_requests",
        "due_call_slips",
    ]
    from contextlib import ExitStack

    with ExitStack() as stack:
        helpers = [
            stack.enter_context(patch.object(services, name, return_value=())) for name in names
        ]
        services.list_work(actor=world.counselor, page=3, page_size=20)
        assert all(helper.call_args.kwargs["limit"] == 61 for helper in helpers)
    with patch.object(
        services, "pending_evaluations", side_effect=RuntimeError("synthetic failure")
    ):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            queue(world)


def test_real_source_sql_is_bounded_and_never_counts_whole_sources(world):
    GoodMoralRequest.objects.bulk_create(
        [GoodMoralRequest(student=world.student, variant="GRADUATE") for _ in range(120)]
    )
    with CaptureQueriesContext(connection) as queries:
        page = services.list_work(actor=world.counselor)
    assert len(page.items) == 20 and page.has_next
    source_queries = [q["sql"] for q in queries if 'FROM "good_moral_goodmoralrequest"' in q["sql"]]
    assert source_queries and all("LIMIT 21" in sql for sql in source_queries)
    assert all("COUNT(" not in sql for sql in source_queries)


def test_real_good_moral_prepare_and_issue_transitions():
    from compass.audit.context import AuditContext
    from compass.good_moral.services import issue_request, prepare_request
    from tests.test_good_moral_preparation import setup_request

    staff, counselor, _, item = setup_request()
    assert services.list_work(actor=staff).items[0].kind == WorkKind.GOOD_MORAL_PREPARATION
    prepared = prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    assert services.list_work(actor=staff).items == []
    assert services.list_work(actor=counselor).items[0].kind == WorkKind.GOOD_MORAL_ISSUANCE
    issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
        expected_preparation_version=prepared.prepared_at.isoformat(),
    )
    assert services.list_work(actor=counselor).items == []


def test_real_routine_submission_and_finalization_transitions(world):
    from compass.audit.context import AuditContext
    from compass.counseling.models import CounselingEncounter
    from compass.routine_interviews.services import (
        finalize_assigned_evaluation,
        replace_my_intake,
        submit_my_intake,
    )
    from compass.service_catalog.models import ServiceDeliveryMode
    from tests.test_routine_interviews import direct_routine

    world.service.is_active = True
    world.service.save(update_fields=["is_active"])
    ServiceDeliveryMode.objects.create(service=world.service, mode="IN_PERSON")
    item = direct_routine(counselor=world.counselor, student=world.student)
    assert queue(world) == []
    replace_my_intake(
        student=world.student,
        routine_interview_id=item.pk,
        values={"college_experience": "Synthetic submitted intake"},
    )
    submit_my_intake(
        student=world.student,
        routine_interview_id=item.pk,
        context=AuditContext.user(world.student),
    )
    assert queue(world)[0].kind == WorkKind.ROUTINE_EVALUATION
    end = timezone.now() - timedelta(minutes=5)
    encounter = CounselingEncounter.objects.create(
        student=world.student,
        counselor=world.counselor,
        service=world.service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=45),
        ended_at=end,
        created_by=world.counselor,
    )
    finalize_assigned_evaluation(
        counselor=world.counselor,
        routine_interview_id=item.pk,
        encounter_id=encounter.pk,
        context=AuditContext.user(world.counselor),
    )
    assert queue(world) == []


def test_real_call_slip_due_and_completion_transition(world):
    from compass.audit.context import AuditContext
    from compass.call_slips.services import record_interview_ended

    now = timezone.now()
    item = call_slip(world, now=now + timedelta(minutes=1))
    with patch.object(services.timezone, "now", return_value=now):
        assert queue(world) == []
    due = now + timedelta(minutes=1)
    with patch.object(services.timezone, "now", return_value=due):
        assert queue(world)[0].kind == WorkKind.CALL_SLIP_DUE
        record_interview_ended(
            actor=world.counselor,
            call_slip_id=item.pk,
            interview_ended_at=due,
            now=due,
            context=AuditContext.user(world.counselor),
        )
        assert queue(world) == []
