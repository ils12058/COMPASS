"""Aggregate authority, shared actionable populations and structural privacy on PostgreSQL."""

import re
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from pydantic import ValidationError

from compass.accounts.models import Capability, Designation, User, UserCapabilityOverride
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.call_slips.models import CallSlip
from compass.counseling.models import CounselingEncounter
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import issue_request, prepare_request
from compass.guidance_messages import services as messages
from compass.guidance_messages.models import GuidanceThread
from compass.guidance_operations import services
from compass.guidance_operations.schemas import DueMetric, WaitingMetric
from compass.institutional_forms.bootstrap import sync_institutional_forms
from compass.organization.models import StaffSupervision, StudentAffiliation
from compass.overview.services import build_overview_summary
from compass.routine_interviews.content import initial_content
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import finalize_assigned_evaluation
from compass.service_catalog.models import Service
from compass.work_queue import services as work
from tests.test_guidance_messages import counseling, deny, office, send, world  # noqa: F401
from tests.test_notifications import auth_client
from tests.test_work_queue import assign, call_slip, good_moral, routine

# ruff: noqa: F811
pytestmark = pytest.mark.django_db
BASE = "/api/v1/guidance-operations"


def summary(world, actor=None, now=None):
    return services.get_guidance_operations(actor=actor or world.counselor, now=now)


@pytest.mark.parametrize("actor", ["counselor", "gss", "head"])
def test_active_staff_access_without_new_capability(world, actor):
    response = auth_client(getattr(world, actor)).get(BASE)
    assert response.status_code == 200
    assert not Capability.objects.filter(code__startswith="guidance_operations.").exists()
    assert not Capability.objects.filter(code__startswith="guidance_dashboard.").exists()


@pytest.mark.parametrize("actor", ["student", "admin", "dpo"])
def test_unsupported_identity_is_403_even_with_capability_override(world, actor):
    user = getattr(world, actor)
    UserCapabilityOverride.objects.create(
        user=user,
        capability=Capability.objects.get(code="call_slips.view"),
        effect="GRANT",
        reason="Synthetic",
    )
    assert auth_client(user).get(BASE).status_code == 403


def test_inactive_stale_actor_fails_closed(world):
    client = auth_client(world.counselor)
    User.objects.filter(pk=world.counselor.pk).update(is_active=False)
    # Shared session authentication rejects inactive identities before endpoint composition.
    assert client.get(BASE).status_code == 401
    with pytest.raises(services.GuidanceOperationsAccessDenied):
        summary(world)


def test_anonymous_endpoint_requires_canonical_session():
    assert Client().get(BASE).status_code == 401


def test_stale_counselor_role_does_not_retain_projection_access(world):
    client = auth_client(world.counselor)
    User.objects.filter(pk=world.counselor.pk).update(role_id=world.student.role_id)
    assert client.get(BASE).status_code == 403
    with pytest.raises(services.GuidanceOperationsAccessDenied):
        summary(world)


def test_authorized_zero_and_gss_null(world):
    result = summary(world)
    for metric in result.backlog.model_dump().values():
        assert metric["count"] == 0
        assert list(metric.values())[1] is None
    gss = summary(world, world.gss)
    assert gss.backlog.routine_evaluations is None
    assert gss.backlog.good_moral_issuance is None
    assert gss.backlog.good_moral_preparation.count == 0
    assert gss.schedule.upcoming_self_appointments_count is None
    assert result.schedule.upcoming_managed_appointments_count is None


@pytest.mark.parametrize(
    "capability,section,field",
    [
        ("guidance_messages.manage", "backlog", "guidance_messages"),
        ("guidance_messages.view", "backlog", "guidance_messages"),
        ("routine_interviews.view_assigned", "backlog", "routine_evaluations"),
        ("routine_interviews.manage_assigned", "backlog", "routine_evaluations"),
        ("good_moral.prepare", "backlog", "good_moral_preparation"),
        ("good_moral.issue", "backlog", "good_moral_issuance"),
        ("call_slips.view", "backlog", "call_slips_due"),
        ("call_slips.view", "schedule", "active_call_slips_count"),
        ("appointments.view_self", "schedule", "upcoming_self_appointments_count"),
    ],
)
def test_capability_removal_means_null_not_zero(world, capability, section, field):
    deny(world.counselor, capability)
    result = summary(world)
    assert getattr(getattr(result, section), field) is None


def test_gss_managed_appointment_capability_removal(world):
    deny(world.gss, "appointments.manage")
    assert summary(world, world.gss).schedule.upcoming_managed_appointments_count is None


def test_message_reply_read_send_resolve_assignment_scope_and_oldest(world):
    first, _ = office(world)
    second, _ = counseling(world)
    assign(world, first)
    now = timezone.now()
    old = now - timedelta(days=2)
    GuidanceThread.objects.filter(pk=first.pk).update(last_message_at=old)
    GuidanceThread.objects.filter(pk=second.pk).update(last_message_at=now)
    assert summary(world).backlog.guidance_messages.count == 2
    assert summary(world).backlog.guidance_messages.oldest_waiting_since == old
    messages.mark_read(actor=world.counselor, thread_id=first.pk, sequence=1)
    assert summary(world).backlog.guidance_messages.count == 2
    send(world, first, actor=world.counselor)
    assert summary(world).backlog.guidance_messages.count == 1
    send(world, first)
    assert summary(world).backlog.guidance_messages.count == 2
    messages.set_status(actor=world.counselor, thread_id=first.pk, resolved=True)
    assert summary(world).backlog.guidance_messages.count == 1
    messages.set_status(actor=world.counselor, thread_id=first.pk, resolved=False)
    assign(world, first, world.gss)
    assert summary(world).backlog.guidance_messages.count == 1
    assert summary(world, world.gss).backlog.guidance_messages.count == 1
    StaffSupervision.objects.filter(staff=world.gss).delete()
    assert summary(world, world.gss).backlog.guidance_messages.count == 0
    assert GuidanceThread.objects.get(pk=first.pk).assigned_to_id == world.gss.pk
    GuidanceThread.objects.filter(pk=first.pk).update(assigned_to=None)
    assert summary(world).backlog.guidance_messages.count == 1


def test_message_assignment_never_grants_current_scope(world):
    thread, _ = office(world)
    GuidanceThread.objects.filter(pk=thread.pk).update(assigned_to=world.other)
    assert summary(world, world.other).backlog.guidance_messages.count == 0


def test_counseling_exact_persisted_provider_and_no_gss_or_head_broadening(world):
    thread, _ = counseling(world)
    for actor in [world.other, world.head, world.gss, world.head_gss]:
        assert summary(world, actor).backlog.guidance_messages.count == 0
    Appointment.objects.filter(pk=world.appointment.pk).update(provider=world.other)
    assert summary(world).backlog.guidance_messages.count == 1
    assert summary(world, world.other).backlog.guidance_messages.count == 0
    assert thread.counselor_id == world.counselor.pk


def test_multiple_heads_fail_closed_for_message_fallback(world):
    StudentAffiliation.objects.filter(student=world.student).update(college=world.colleges[3])
    thread, _ = office(world)
    assert thread.assigned_to_id == world.head.pk
    assert summary(world, world.head).backlog.guidance_messages.count == 1
    world.other.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    assert summary(world, world.head).backlog.guidance_messages.count == 0
    assert summary(world, world.head_gss).backlog.guidance_messages.count == 0


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_routine_closed_parent_shared_with_work_and_overview(world, status):
    direct = routine(world)
    linked = RoutineInterview.objects.create(
        student=world.student,
        counselor=world.counselor,
        appointment=world.appointment,
        entry_mode="APPOINTMENT",
        delivery_mode="IN_PERSON",
        intake_submitted_at=timezone.now(),
        student_intake_ciphertext="Synthetic",
        counselor_evaluation_ciphertext="Synthetic",
    )
    assert summary(world).backlog.routine_evaluations.count == 2
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status=status,
        **{("cancelled_at" if status == "CANCELLED" else "no_show_at"): timezone.now()},
    )
    assert summary(world).backlog.routine_evaluations.count == 1
    assert build_overview_summary(world.counselor).guidance.routine_evaluation_pending_count == 1
    assert [row.source_id for row in work.list_work(actor=world.counselor).items] == [direct.pk]
    assert summary(world, world.other).backlog.routine_evaluations.count == 0
    RoutineInterview.objects.filter(pk=direct.pk).update(**initial_content(direct.pk))
    now = timezone.now()
    encounter = CounselingEncounter.objects.create(
        student=world.student,
        counselor=world.counselor,
        service=world.service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(minutes=10),
        ended_at=now,
        created_by=world.counselor,
    )
    finalize_assigned_evaluation(
        counselor=world.counselor,
        routine_interview_id=direct.pk,
        encounter_id=encounter.pk,
        context=AuditContext.user(world.counselor),
    )
    assert summary(world).backlog.routine_evaluations.count == 0
    assert linked.pk != direct.pk


def test_good_moral_separate_authorities_and_timestamp_anchors(world):
    first = good_moral(world)
    second = good_moral(world, world.other_student)
    old = timezone.now() - timedelta(days=3)
    GoodMoralRequest.objects.filter(pk=first.pk).update(created_at=old)
    assert summary(world, world.gss).backlog.good_moral_preparation.count == 2
    assert summary(world).backlog.good_moral_preparation.oldest_waiting_since == old
    sync_institutional_forms()
    GoodMoralRequest.objects.filter(pk=first.pk).update(
        applicant_name_snapshot="Synthetic",
        degree_snapshot="Synthetic degree",
        graduation_date=date(2000, 1, 1),
    )
    prepare_request(
        actor=world.gss, request_id=first.pk, context=AuditContext.user(world.gss), now=old
    )
    assert summary(world).backlog.good_moral_preparation.count == 1
    assert summary(world).backlog.good_moral_issuance.count == 1
    assert summary(world).backlog.good_moral_issuance.oldest_waiting_since == old
    UserCapabilityOverride.objects.create(
        user=world.gss,
        capability=Capability.objects.get(code="good_moral.issue"),
        effect="GRANT",
        reason="Synthetic",
    )
    assert summary(world, world.gss).backlog.good_moral_issuance is None
    issue_request(
        actor=world.counselor, request_id=first.pk, context=AuditContext.user(world.counselor)
    )
    GoodMoralRequest.objects.filter(pk=second.pk).update(
        status="CANCELLED",
        cancelled_at=timezone.now(),
        cancelled_by=world.student,
        cancellation_reason="Synthetic",
    )
    assert summary(world).backlog.good_moral_issuance.count == 0
    assert summary(world).backlog.good_moral_preparation.count == 0


def test_call_slip_active_due_equality_future_completion_void_and_oldest(world):
    now = timezone.now()
    past = call_slip(world, now=now - timedelta(hours=2))
    exact = call_slip(world, now=now)
    future = call_slip(world, now=now + timedelta(hours=2))
    result = summary(world, now=now)
    assert result.schedule.active_call_slips_count == 3
    assert result.backlog.call_slips_due.count == 2
    assert result.backlog.call_slips_due.oldest_due_at == past.report_at
    CallSlip.objects.filter(pk=past.pk).update(interview_ended_at=now)
    CallSlip.objects.filter(pk=exact.pk).update(
        voided_at=now, voided_by=world.counselor, void_reason="Synthetic"
    )
    result = summary(world, now=now)
    assert result.schedule.active_call_slips_count == 1
    assert result.backlog.call_slips_due.count == 0
    assert result.backlog.call_slips_due.oldest_due_at is None
    assert summary(world, now=future.report_at).backlog.call_slips_due.count == 1


def test_head_scope_is_owned_by_each_domain(world):
    now = timezone.now()
    call_slip(world, now=now)
    call_slip(world, now=now, student=world.other_student)
    good_moral(world)
    good_moral(world, world.other_student)
    routine(world)
    counseling(world)
    result = summary(world, world.head, now)
    assert result.backlog.call_slips_due.count == 2
    assert result.schedule.active_call_slips_count == 2
    assert result.backlog.good_moral_preparation.count == 2
    assert result.backlog.guidance_messages.count == 0
    assert result.backlog.routine_evaluations.count == 0
    assert result.schedule.upcoming_self_appointments_count == 0
    assert result.schedule.upcoming_managed_appointments_count is None
    assert summary(world, world.gss, now).backlog.call_slips_due.count == 1
    assert summary(world, world.head_gss, now).backlog.call_slips_due.count == 0


def test_gss_supervision_move_changes_only_canonical_scoped_populations(world):
    now = timezone.now()
    thread, _ = office(world)
    assign(world, thread, world.gss)
    call_slip(world, now=now)
    good_moral(world)
    service = Service.objects.create(code="OPERATIONS", name="Synthetic")
    Appointment.objects.create(
        reference_code="OPS-ORGANIZATIONAL",
        student=world.student,
        provider=world.counselor,
        service=service,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
        created_by=world.student,
    )
    before = summary(world, world.gss, now)
    assert before.backlog.guidance_messages.count == 1
    assert before.backlog.call_slips_due.count == 1
    assert before.schedule.upcoming_managed_appointments_count == 1
    assert before.backlog.routine_evaluations is None
    assert before.backlog.good_moral_issuance is None
    StaffSupervision.objects.filter(staff=world.gss).update(supervisor=world.other)
    after = summary(world, world.gss, now)
    assert after.backlog.guidance_messages.count == 0
    assert after.backlog.call_slips_due.count == 0
    assert after.schedule.upcoming_managed_appointments_count == 0
    assert after.backlog.good_moral_preparation.count == 1


def test_schedule_preserves_canonical_inclusive_start_boundary_and_relationship(world):
    now = world.appointment.starts_at
    assert summary(world, now=now).schedule.upcoming_self_appointments_count == 1
    assert (
        summary(
            world, now=now + timedelta(microseconds=1)
        ).schedule.upcoming_self_appointments_count
        == 0
    )
    assert summary(world, world.gss, now).schedule.upcoming_managed_appointments_count == 0
    assert summary(world, world.head, now).schedule.upcoming_self_appointments_count == 0
    Appointment.objects.filter(pk=world.appointment.pk).update(status="COMPLETED", completed_at=now)
    assert summary(world, now=now).schedule.upcoming_self_appointments_count == 0


def test_one_aware_server_now_used_by_all_time_sources(world):
    now = timezone.now()
    from unittest.mock import Mock

    clock = Mock(return_value=now)
    with (
        patch.object(services, "timezone", SimpleNamespace(now=clock, is_naive=timezone.is_naive)),
        patch.object(
            services, "due_call_slip_summary", wraps=services.due_call_slip_summary
        ) as due,
        patch.object(
            services,
            "count_upcoming_self_appointments",
            wraps=services.count_upcoming_self_appointments,
        ) as upcoming,
    ):
        assert summary(world).generated_at == now
        assert clock.call_count == 1
        assert due.call_args.kwargs["now"] is now
        assert upcoming.call_args.kwargs["now"] is now
    with pytest.raises(ValueError, match="aware"):
        summary(world, now=now.replace(tzinfo=None))


@pytest.mark.parametrize(
    "model,field", [(WaitingMetric, "oldest_waiting_since"), (DueMetric, "oldest_due_at")]
)
@pytest.mark.parametrize("count,has_time", [(-1, False), (0, True), (1, False)])
def test_metric_schema_rejects_inconsistent_population(model, field, count, has_time):
    with pytest.raises(ValidationError):
        model.model_validate({"count": count, field: timezone.now() if has_time else None})


def test_fixed_wire_contract_contains_no_content_identities_or_work_pages(world, settings):
    thread, _ = office(world)
    assign(world, thread)
    routine(world)
    good_moral(world)
    call_slip(world, now=timezone.now())
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ""
    with (
        patch("compass.guidance_messages.content.read_body", side_effect=AssertionError("decrypt")),
        patch.object(work, "list_work", side_effect=AssertionError("cannot count pages")),
        CaptureQueriesContext(connection) as queries,
    ):
        result = summary(world)
    sql = "\n".join(row["sql"] for row in queries)
    for forbidden in [
        "body_ciphertext",
        "student_intake_ciphertext",
        "counselor_evaluation_ciphertext",
        "audit_auditevent",
    ]:
        assert forbidden not in sql
    aggregates = [row["sql"] for row in queries if "MIN(" in row["sql"]]
    assert len(aggregates) == 5
    # The latest-sender structural subquery legitimately has LIMIT 1; the outer aggregate has none.
    assert all("COUNT(" in sql and not re.search(r"LIMIT \d+\s*$", sql) for sql in aggregates)
    data = result.model_dump(mode="json")
    assert set(data) == {"generated_at", "backlog", "schedule"}
    assert set(data["backlog"]) == {
        "guidance_messages",
        "routine_evaluations",
        "good_moral_preparation",
        "good_moral_issuance",
        "call_slips_due",
    }
    assert set(data["schedule"]) == {
        "upcoming_self_appointments_count",
        "upcoming_managed_appointments_count",
        "active_call_slips_count",
    }
    serialized = result.model_dump_json()
    assert str(world.student.pk) not in serialized and str(thread.pk) not in serialized
    assert "Synthetic" not in serialized
    with pytest.raises(ValidationError):
        WaitingMetric.model_validate({"count": 0, "oldest_waiting_since": None, "metadata": {}})


def test_fixed_query_cost_and_counts_beyond_a_work_page(world):
    good_moral(world)
    with CaptureQueriesContext(connection) as small:
        summary(world)
    GoodMoralRequest.objects.bulk_create(
        [GoodMoralRequest(student=world.student, variant="GRADUATE") for _ in range(150)]
    )
    with CaptureQueriesContext(connection) as large:
        result = summary(world)
    assert result.backlog.good_moral_preparation.count == 151
    assert len(large) == len(small)


def test_controlled_shared_work_populations_agree_without_paging(world):
    now = timezone.now()
    thread, _ = office(world)
    assign(world, thread)
    routine(world)
    good_moral(world)
    row = good_moral(world)
    GoodMoralRequest.objects.filter(pk=row.pk).update(
        status="READY_FOR_ISSUANCE",
        prepared_at=now,
        prepared_by=world.counselor,
    )
    call_slip(world, now=now)
    from compass.call_slips.work import due_call_slips
    from compass.good_moral.work import issuance_requests, preparation_requests
    from compass.guidance_messages.work import reply_needed_threads
    from compass.routine_interviews.work import pending_evaluations

    result = summary(world, now=now).backlog
    assert (
        result.guidance_messages.count
        == len(reply_needed_threads(actor=world.counselor, limit=10))
        == 1
    )
    assert (
        result.routine_evaluations.count
        == len(pending_evaluations(actor=world.counselor, limit=10))
        == 1
    )
    assert (
        result.good_moral_preparation.count
        == len(preparation_requests(actor=world.counselor, limit=10))
        == 1
    )
    assert (
        result.good_moral_issuance.count
        == len(issuance_requests(actor=world.counselor, limit=10))
        == 1
    )
    assert (
        result.call_slips_due.count
        == len(due_call_slips(actor=world.counselor, now=now, limit=10))
        == 1
    )


@pytest.mark.parametrize(
    "source",
    [
        "reply_needed_summary",
        "pending_evaluation_summary",
        "preparation_summary",
        "issuance_summary",
        "due_call_slip_summary",
        "count_active_call_slips",
        "count_upcoming_self_appointments",
    ],
)
def test_source_failure_is_never_silently_null(world, source):
    with patch.object(services, source, side_effect=RuntimeError("Synthetic source failure")):
        with pytest.raises(RuntimeError, match="source failure"):
            summary(world)
