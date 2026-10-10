"""Authoritative Student action transitions, policy/privacy, SQL bounds and local time proofs."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.call_slips.models import CallSlip
from compass.ecounseling.media import decide_my_consent
from compass.ecounseling.models import ECounselingConsent, ECounselingRoom
from compass.exit_interviews.models import ExitInterview, ExitInterviewOpportunity
from compass.exit_interviews.services import (
    _require_draft_admission,
    ensure_my_current,
    reopen_for_correction,
)
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.guidance_messages import services as messages
from compass.guidance_messages.models import GuidanceMessage, GuidanceThreadReadState
from compass.inventory.models import StudentInventory
from compass.inventory.services import reopen_inventory_for_correction
from compass.organization.models import AcademicYear
from compass.routine_interviews.models import RoutineInterview
from compass.student_actions import services
from compass.student_actions.schemas import StudentActionKind as Kind
from tests.test_exit_interviews import make_exit_interview, make_inventory
from tests.test_guidance_messages import deny, office, send, world  # noqa: F401
from tests.test_notifications import auth_client
from tests.test_work_queue import call_slip

# ruff: noqa: F811
pytestmark = pytest.mark.django_db


def actions(world, actor=None, **kwargs):
    return services.list_actions(actor=actor or world.student, **kwargs).items


def kinds(world, actor=None):
    return [row.kind for row in actions(world, actor)]


def year():
    return AcademicYear.objects.create(label="2026-2027", is_current=True)


def routine(world, **kwargs):
    return RoutineInterview.objects.create(
        student=world.student,
        counselor=world.counselor,
        entry_mode="APPOINTMENT" if kwargs.get("appointment") else "WALK_IN",
        delivery_mode="IN_PERSON",
        student_intake_ciphertext="structural-only",
        counselor_evaluation_ciphertext="structural-only",
        **kwargs,
    )


def online(world):
    world.service.is_active = True
    world.service.save(update_fields=["is_active"])
    appointment = world.appointment
    appointment.delivery_mode = "ONLINE"
    appointment.save(update_fields=["delivery_mode"])
    return appointment


def room(world):
    return ECounselingRoom.objects.create(
        appointment=online(world), daily_room_name="synthetic-" + str(uuid4())
    )


def test_inventory_missing_draft_submitted_and_real_reopen(world):
    ay = year()
    assert kinds(world) == [Kind.INVENTORY_START]
    assert actions(world)[0].source_id == ay.pk
    inventory = make_inventory(world.student, ay, submitted=False, admit=False)
    assert kinds(world) == [Kind.INVENTORY_CONTINUE]
    StudentInventory.objects.filter(pk=inventory.pk).update(
        submitted_at=timezone.now(), first_submitted_at=timezone.now()
    )
    assert actions(world) == []
    reopen_inventory_for_correction(
        actor=world.counselor,
        inventory_id=inventory.pk,
        reason="Synthetic correction",
        context=AuditContext.user(world.counselor),
    )
    assert kinds(world) == [Kind.INVENTORY_CONTINUE]


@pytest.mark.parametrize("lifecycle", ["GRADUATED", "FORMER"])
def test_inventory_current_lifecycle_and_capability(world, lifecycle):
    year()
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status=lifecycle)
    assert actions(world) == []


def test_inventory_and_exit_capability_removed(world):
    ay = year()
    make_inventory(world.student, ay)
    assert Kind.EXIT_INTERVIEW_START in kinds(world)
    deny(world.student, "exit_interviews.manage_self")
    assert actions(world) == []
    StudentInventory.objects.filter(student=world.student).update(submitted_at=None)
    deny(world.student, "inventory.manage_self")
    assert actions(world) == []


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_routine_parent_closed_ownership_submission_and_order(world, status):
    linked = routine(world, appointment=world.appointment)
    direct = routine(world)
    assert [i.source_id for i in actions(world)] == [linked.pk, direct.pk]
    assert actions(world, world.other_student) == []
    # Synthetic source outcome; same state consumed by canonical mutations.
    from compass.appointments.models import Appointment

    values = {"status": status}
    if status == "CANCELLED":
        values.update(cancelled_at=timezone.now(), cancelled_by=world.counselor)
    else:
        values.update(no_show_at=timezone.now(), no_show_by=world.counselor)
    Appointment.objects.filter(pk=world.appointment.pk).update(**values)
    assert [i.source_id for i in actions(world)] == [direct.pk]
    RoutineInterview.objects.filter(pk=direct.pk).update(intake_submitted_at=timezone.now())
    assert actions(world) == []


def test_routine_capability_and_current_lifecycle(world):
    routine(world)
    deny(world.student, "routine_interviews.manage_self")
    assert actions(world) == []


def test_exit_inventory_sequence_and_revoked_initial_draft(world):
    ay = year()
    inventory = make_inventory(world.student, ay, submitted=False)
    assert kinds(world) == [Kind.INVENTORY_CONTINUE]
    StudentInventory.objects.filter(pk=inventory.pk).update(submitted_at=timezone.now())
    assert kinds(world) == [Kind.EXIT_INTERVIEW_START]
    result = ensure_my_current(student=world.student, context=AuditContext.user(world.student))
    assert kinds(world) == [Kind.EXIT_INTERVIEW_CONTINUE]
    opportunity = ExitInterviewOpportunity.objects.get(student=world.student)
    ExitInterviewOpportunity.objects.filter(pk=opportunity.pk).update(
        status="REVOKED", revoked_at=timezone.now(), revoked_by=world.head
    )
    assert actions(world) == []
    from compass.exit_interviews.services import ExitInterviewOpportunityNotOpen

    with pytest.raises(ExitInterviewOpportunityNotOpen):
        _require_draft_admission(result)


@pytest.mark.parametrize("historical", [False, True])
def test_exit_real_reopen_including_historical_and_completed_opportunity(world, historical):
    ay = year()
    make_inventory(world.student, ay)
    item = ensure_my_current(student=world.student, context=AuditContext.user(world.student))
    now = timezone.now()
    ExitInterview.objects.filter(pk=item.pk).update(
        status="SUBMITTED", first_submitted_at=now, last_submitted_at=now
    )
    ExitInterviewOpportunity.objects.filter(pk=item.opportunity_id).update(
        status="COMPLETED", completed_at=now
    )
    if historical:
        AcademicYear.objects.filter(pk=ay.pk).update(is_current=False)
        AcademicYear.objects.create(label="2027-2028", is_current=True)
        # Remove unrelated Inventory action for the new current year in this narrow proof.
        deny(world.student, "inventory.manage_self")
    assert actions(world) == []
    reopened = reopen_for_correction(
        actor=world.head,
        exit_interview_id=item.pk,
        reason="Synthetic correction",
        context=AuditContext.user(world.head),
    )
    assert kinds(world) == [Kind.EXIT_INTERVIEW_CORRECTION]
    assert actions(world)[0].source_id == reopened.pk
    _require_draft_admission(reopened)
    assert actions(world)[0].due_at is None


def test_exit_legacy_admitted_draft_and_no_good_moral_extra(world):
    ay = year()
    inventory = make_inventory(world.student, ay, admit=False)
    make_exit_interview(student=world.student, academic_year=ay, inventory=inventory)
    assert kinds(world) == [Kind.EXIT_INTERVIEW_CONTINUE]
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    assert actions(world) == []


def test_graduate_available_not_obligation_draft_submitted_and_disposed(world):
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    assert actions(world) == []
    row = GraduateTracerResponse.objects.create(
        student=world.student, confidential_content_ciphertext="structural"
    )
    assert kinds(world) == [Kind.GRADUATE_TRACER_CONTINUE]
    GraduateTracerResponse.objects.filter(pk=row.pk).update(
        status="SUBMITTED", submitted_at=timezone.now()
    )
    assert actions(world) == []
    GraduateTracerResponse.objects.filter(pk=row.pk).update(
        student=None, anonymized_at=timezone.now(), confidential_content_ciphertext=None
    )
    assert actions(world) == []


def test_graduate_draft_capability_and_lifecycle(world):
    GraduateTracerResponse.objects.create(
        student=world.student, confidential_content_ciphertext="structural"
    )
    assert actions(world) == []
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    deny(world.student, "graduate_tracer.manage_self")
    assert actions(world) == []


def test_call_slip_live_future_due_overdue_completed_voided_and_provenance(world):
    now = timezone.now()
    due = call_slip(world, now=now)
    future = call_slip(world, now=now + timedelta(days=1))
    old = call_slip(world, now=now - timedelta(days=1))
    historical = call_slip(world, now=now)
    legacy = call_slip(world, now=now)
    CallSlip.objects.filter(pk=historical.pk).update(issuance_mode="HISTORICAL")
    CallSlip.objects.filter(pk=legacy.pk).update(issuance_mode="LEGACY_UNKNOWN")
    call_slip(world, now=now, student=world.other_student)
    with patch.object(services.timezone, "now", return_value=now):
        items = actions(world)
        assert [i.source_id for i in items] == [old.pk, due.pk, future.pk]
        assert [i.priority for i in items] == [
            "TIME_SENSITIVE",
            "TIME_SENSITIVE",
            "ACTION_REQUIRED",
        ]
    CallSlip.objects.filter(pk=old.pk).update(interview_ended_at=now)
    CallSlip.objects.filter(pk=due.pk).update(
        voided_at=now, voided_by=world.counselor, void_reason="Synthetic"
    )
    with patch.object(services.timezone, "now", return_value=future.report_at):
        assert actions(world)[0].priority == "TIME_SENSITIVE"
    deny(world.student, "call_slips.view_self")
    assert actions(world) == []


def test_consent_grouping_earliest_real_decisions_and_capability(world):
    anchor = room(world)
    consents = [
        ECounselingConsent.objects.create(room=anchor, scope=scope, requested_by=world.counselor)
        for scope in ["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"]
    ]
    earlier = timezone.now() - timedelta(days=1)
    ECounselingConsent.objects.filter(pk=consents[0].pk).update(requested_at=earlier)
    item = actions(world)[0]
    assert item.kind == Kind.ECOUNSELING_CONSENT and item.source_id == world.appointment.pk
    assert item.pending_count == 2 and item.waiting_since == earlier
    assert actions(world, world.other_student) == []
    for i, consent in enumerate(consents):
        decide_my_consent(
            student=world.student,
            appointment_id=world.appointment.pk,
            consent_id=consent.pk,
            decision="DENIED",
            context=AuditContext.user(world.student),
        )
        assert len(actions(world)) == (1 if i == 0 else 0)
    # Pending denial stays available after graduation, matching canonical decision rules.
    deny(world.student, "ecounseling.consent_self")
    assert actions(world) == []


@pytest.mark.parametrize(
    "offset,expected", [(-1, False), (0, True), (1, True), (7200, True), (7201, False)]
)
def test_join_inclusive_windows_without_daily_calls(world, settings, offset, expected):
    appointment = online(world)
    settings.DAILY_ENABLED = True
    settings.ECOUNSELING_JOIN_EARLY_SECONDS = 0
    settings.ECOUNSELING_REJOIN_GRACE_SECONDS = 3600
    now = appointment.starts_at + timedelta(seconds=offset)
    with (
        patch.object(services.timezone, "now", return_value=now),
        patch(
            "compass.ecounseling.services.DailyClient.from_settings",
            side_effect=AssertionError("Daily contacted"),
        ),
    ):
        items = actions(world)
    assert bool(items) == expected
    if expected:
        assert items[0].kind == Kind.ECOUNSELING_JOIN and items[0].priority == "TIME_SENSITIVE"
        assert items[0].due_at == appointment.ends_at + timedelta(seconds=3600)


@pytest.mark.parametrize(
    "change",
    [
        "disabled",
        "completed",
        "cancelled",
        "no-show",
        "offline",
        "service",
        "provider",
        "lifecycle",
        "capability",
    ],
)
def test_join_eligibility_exclusions(world, settings, change):
    appointment = online(world)
    settings.DAILY_ENABLED = True
    now = appointment.starts_at
    from compass.appointments.models import Appointment

    if change == "disabled":
        settings.DAILY_ENABLED = False
    elif change == "completed":
        Appointment.objects.filter(pk=appointment.pk).update(
            status="COMPLETED", completed_at=now, completed_by=world.counselor
        )
    elif change == "cancelled":
        Appointment.objects.filter(pk=appointment.pk).update(
            status="CANCELLED", cancelled_at=now, cancelled_by=world.counselor
        )
    elif change == "no-show":
        Appointment.objects.filter(pk=appointment.pk).update(
            status="NO_SHOW", no_show_at=now, no_show_by=world.counselor
        )
    elif change == "offline":
        Appointment.objects.filter(pk=appointment.pk).update(delivery_mode="IN_PERSON")
    elif change == "service":
        world.service.is_active = False
        world.service.save(update_fields=["is_active"])
    elif change == "provider":
        User.objects.filter(pk=world.counselor.pk).update(is_active=False)
    elif change == "lifecycle":
        User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    else:
        deny(world.student, "ecounseling.join_self")
    with patch.object(services.timezone, "now", return_value=now):
        assert actions(world) == []


def test_unread_messages_oldest_cursor_resolved_privacy_and_no_read_writes(world, settings):
    thread, _ = office(world)
    assert actions(world) == []  # own send is never inbound unread
    first = send(world, thread, actor=world.counselor)
    oldest = timezone.now() - timedelta(days=1)
    GuidanceMessage.objects.filter(pk=first.pk).update(created_at=oldest)
    send(world, thread)  # own newer send cannot move the waiting anchor
    send(world, thread, actor=world.counselor)
    messages.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ""
    before = list(GuidanceThreadReadState.objects.values())
    with (
        patch("compass.guidance_messages.content.read_body", side_effect=AssertionError("decrypt")),
        CaptureQueriesContext(connection) as queries,
    ):
        result = actions(world)
    assert result[0].kind == Kind.GUIDANCE_MESSAGE_UNREAD
    assert result[0].pending_count == 2 and result[0].waiting_since == oldest
    assert all("body_ciphertext" not in q["sql"] for q in queries)
    assert list(GuidanceThreadReadState.objects.values()) == before
    assert set(result[0].model_dump()) == {
        "id",
        "kind",
        "priority",
        "source_id",
        "due_at",
        "waiting_since",
        "conversation_kind",
        "pending_count",
    }
    assert actions(world, world.other_student) == []
    messages.mark_read(actor=world.student, thread_id=thread.pk, sequence=4)
    assert actions(world) == []


@pytest.mark.parametrize(
    "capability", ["guidance_messages.view_self", "guidance_messages.manage_self"]
)
def test_messages_require_read_and_cursor_authority(world, capability):
    thread, _ = office(world)
    send(world, thread, actor=world.counselor)
    deny(world.student, capability)
    assert actions(world) == []


def test_global_merge_rank_stable_pages_and_source_sql_bounds(world, settings):
    ay = year()
    make_inventory(world.student, ay, submitted=False, admit=False)
    now = timezone.now()
    slip = call_slip(world, now=now - timedelta(hours=1))
    future = call_slip(world, now=now + timedelta(days=1))
    intake = routine(world)
    thread, _ = office(world)
    send(world, thread, actor=world.counselor)
    expected = [slip.pk, future.pk, intake.pk, thread.pk]
    with patch.object(services.timezone, "now", return_value=now):
        all_items = actions(world)
        assert [i.source_id for i in all_items[:4]] == expected
        assert all_items[-1].kind == Kind.INVENTORY_CONTINUE
        pages = [services.list_actions(actor=world.student, page=p, page_size=2) for p in [1, 2, 3]]
        assert [i.id for page in pages for i in page.items] == [i.id for i in all_items]
        assert [p.has_next for p in pages] == [True, True, False]
    for _ in range(110):
        routine(world)
    with CaptureQueriesContext(connection) as queries:
        result = services.list_actions(actor=world.student)
    sql = [q["sql"] for q in queries if 'FROM "routine_interviews_routineinterview"' in q["sql"]]
    assert sql and all("LIMIT 21" in q for q in sql)
    assert result.has_next


def test_unexpected_source_failure_propagates_and_no_false_empty(world):
    with (
        patch.object(
            services, "pending_intakes", side_effect=RuntimeError("Synthetic source failed")
        ),
        pytest.raises(RuntimeError),
    ):
        services.list_actions(actor=world.student)


@pytest.mark.parametrize(
    "role", ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]
)
def test_endpoint_denies_nonstudents(world, role):
    actor = next(
        u for u in [world.counselor, world.gss, world.admin, world.dpo] if u.role.code == role
    )
    assert auth_client(actor).get("/api/v1/student-actions").status_code == 403


def test_endpoint_active_account_strict_paging_and_single_now(world):
    client = auth_client(world.student)
    assert client.get("/api/v1/student-actions").status_code == 200
    for query in ["page=0", "page=101", "page_size=51", "page=-1", "page=abc"]:
        assert client.get("/api/v1/student-actions?" + query).status_code == 422
    User.objects.filter(pk=world.student.pk).update(is_active=False)
    with pytest.raises(services.StudentActionsAccessDenied):
        services.list_actions(actor=world.student)


def submit_inventory_locally(world):
    from compass.inventory.services import (
        ensure_current_inventory,
        replace_current_inventory,
        submit_current_inventory,
    )
    from compass.organization.models import Program
    from tests.inventory_test_helpers import (
        ensure_inventory_form_revision,
        minimum_normalized_inventory_values,
    )

    ensure_inventory_form_revision()
    item = ensure_current_inventory(student=world.student, context=AuditContext.user(world.student))
    program = Program.objects.create(college=world.colleges[0], code="LOCAL", name="Synthetic")
    replace_current_inventory(
        student=world.student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )
    submit_current_inventory(student=world.student, context=AuditContext.user(world.student))
    return item


def test_local_inventory_start_save_submit_reopen_services(world):
    from compass.inventory.services import ensure_current_inventory
    from tests.inventory_test_helpers import ensure_inventory_form_revision

    year()
    assert kinds(world) == [Kind.INVENTORY_START]
    ensure_inventory_form_revision()
    ensure_current_inventory(student=world.student, context=AuditContext.user(world.student))
    assert kinds(world) == [Kind.INVENTORY_CONTINUE]
    item = submit_inventory_locally(world)
    assert actions(world) == []
    reopen_inventory_for_correction(
        actor=world.counselor,
        inventory_id=item.pk,
        reason="Synthetic local correction",
        context=AuditContext.user(world.counselor),
    )
    assert kinds(world) == [Kind.INVENTORY_CONTINUE]


def test_local_routine_create_save_submit_and_cancelled_parent_services(world):
    from compass.appointments.models import Appointment
    from compass.routine_interviews.services import replace_my_intake, submit_my_intake
    from compass.service_catalog.models import ServiceDeliveryMode
    from tests.test_routine_interviews import direct_routine

    ServiceDeliveryMode.objects.create(service=world.service, mode="IN_PERSON")
    world.service.is_active = True
    world.service.save(update_fields=["is_active"])
    item = direct_routine(counselor=world.counselor, student=world.student)
    assert kinds(world) == [Kind.ROUTINE_INTAKE]
    replace_my_intake(
        student=world.student,
        routine_interview_id=item.pk,
        values={"concerns": ["ACADEMIC"], "academic_goals": "Synthetic goal"},
    )
    submit_my_intake(
        student=world.student,
        routine_interview_id=item.pk,
        context=AuditContext.user(world.student),
    )
    assert actions(world) == []
    routine(world, appointment=world.appointment)
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status="CANCELLED", cancelled_at=timezone.now(), cancelled_by=world.counselor
    )
    assert actions(world) == []


@pytest.mark.parametrize("historical", [False, True])
def test_local_exit_opportunity_inventory_submit_response_submit_reopen(world, historical):
    from compass.exit_interviews.api import ExitInterviewDraftPayload, _payload_values
    from compass.exit_interviews.opportunities import open_opportunity
    from compass.exit_interviews.services import replace_mine, submit_mine
    from tests.test_exit_interviews import valid_payload

    ay = year()
    open_opportunity(
        actor=world.head,
        student_id=world.student.pk,
        academic_year_id=ay.pk,
        source="MANUAL",
        note="Synthetic admission",
        context=AuditContext.user(world.head),
    )
    assert kinds(world) == [Kind.INVENTORY_START]
    submit_inventory_locally(world)
    assert kinds(world) == [Kind.EXIT_INTERVIEW_START]
    item = ensure_my_current(student=world.student, context=AuditContext.user(world.student))
    assert kinds(world) == [Kind.EXIT_INTERVIEW_CONTINUE]
    replace_mine(
        student=world.student,
        exit_interview_id=item.pk,
        values=_payload_values(ExitInterviewDraftPayload(**valid_payload())),
    )
    submit_mine(
        student=world.student, exit_interview_id=item.pk, context=AuditContext.user(world.student)
    )
    assert actions(world) == []
    if historical:
        AcademicYear.objects.filter(pk=ay.pk).update(is_current=False)
        AcademicYear.objects.create(label="2027-2028", is_current=True)
        deny(world.student, "inventory.manage_self")
    reopen_for_correction(
        actor=world.head,
        exit_interview_id=item.pk,
        reason="Synthetic correction",
        context=AuditContext.user(world.head),
    )
    assert kinds(world) == [Kind.EXIT_INTERVIEW_CORRECTION]
    submit_mine(
        student=world.student, exit_interview_id=item.pk, context=AuditContext.user(world.student)
    )
    assert actions(world) == []


def test_local_graduate_start_save_submit_services(world):
    from compass.graduate_tracer.api import GraduateTracerDraftPayload, _payload_values
    from compass.graduate_tracer.services import (
        ensure_my_response,
        replace_my_draft,
        submit_my_response,
    )
    from tests.test_graduate_tracer import valid_unemployed_payload

    world.student.student_lifecycle_status = "GRADUATED"
    world.student.save(update_fields=["student_lifecycle_status"])
    assert actions(world) == []
    ensure_my_response(student=world.student, context=AuditContext.user(world.student))
    assert kinds(world) == [Kind.GRADUATE_TRACER_CONTINUE]
    replace_my_draft(
        student=world.student,
        values=_payload_values(GraduateTracerDraftPayload(**valid_unemployed_payload())),
    )
    submit_my_response(student=world.student, context=AuditContext.user(world.student))
    assert actions(world) == []


def test_local_live_call_slip_issue_due_and_complete_services(world):
    from compass.call_slips.services import record_interview_ended
    from tests.test_call_slips import create_for, ensure_call_slip_form_revision

    ensure_call_slip_form_revision()
    now = timezone.now()
    item = create_for(
        world.counselor,
        world.student,
        key="local-call",
        fingerprint="a" * 64,
        report_at=now + timedelta(hours=1),
        notify_student=True,
    )
    with patch.object(services.timezone, "now", return_value=now):
        assert actions(world)[0].priority == "ACTION_REQUIRED"
    with patch.object(services.timezone, "now", return_value=item.report_at):
        assert actions(world)[0].priority == "TIME_SENSITIVE"
    record_interview_ended(
        actor=world.counselor,
        call_slip_id=item.pk,
        interview_ended_at=item.report_at,
        now=item.report_at,
        context=AuditContext.user(world.counselor),
    )
    assert actions(world) == []
    historical = call_slip(world, now=now)
    CallSlip.objects.filter(pk=historical.pk).update(issuance_mode="HISTORICAL")
    assert actions(world) == []


def test_local_consent_request_two_scopes_then_decide_services(world):
    from compass.ecounseling.media import request_consents

    online(world)
    requested = request_consents(
        counselor=world.counselor,
        appointment_id=world.appointment.pk,
        scopes=["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"],
        context=AuditContext.user(world.counselor),
    )
    assert actions(world)[0].pending_count == 2
    for remaining, consent in zip([1, 0], requested, strict=True):
        decide_my_consent(
            student=world.student,
            appointment_id=world.appointment.pk,
            consent_id=consent["id"],
            decision="DENIED",
            context=AuditContext.user(world.student),
        )
        assert len(actions(world)) == bool(remaining)
        if remaining:
            assert actions(world)[0].pending_count == remaining


def test_consent_pending_capability_and_graduated_denial_remain_canonical(world):
    anchor = room(world)
    consent = ECounselingConsent.objects.create(
        room=anchor, scope="SESSION_MEDIA_CAPTURE", requested_by=world.counselor
    )
    world.student.student_lifecycle_status = "GRADUATED"
    world.student.save(update_fields=["student_lifecycle_status"])
    assert kinds(world) == [Kind.ECOUNSELING_CONSENT]
    denied = deny(world.student, "ecounseling.consent_self")
    assert actions(world) == []
    denied.delete()
    decide_my_consent(
        student=world.student,
        appointment_id=world.appointment.pk,
        consent_id=consent.pk,
        decision="DENIED",
        context=AuditContext.user(world.student),
    )
    assert actions(world) == []


def test_disposed_participation_hides_stray_personal_graduate_draft(world):
    from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation

    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    GraduateTracerResponse.objects.create(
        student=world.student, confidential_content_ciphertext="structural"
    )
    GraduateTracerDisposedParticipation.objects.create(
        student=world.student, instrument_schema_version=1, disposed_on=timezone.now().date()
    )
    assert actions(world) == []


def test_inventory_and_exit_projection_select_no_confidential_payload(world):
    ay = year()
    make_inventory(world.student, ay)
    with CaptureQueriesContext(connection) as queries:
        assert kinds(world) == [Kind.EXIT_INTERVIEW_START]
    assert all("ciphertext" not in q["sql"] for q in queries)


def test_global_due_waiting_and_stable_ties_across_source_pages(world):
    from compass.routine_interviews.student_actions import pending_intakes

    now = timezone.now()
    slips = [call_slip(world, now=now + timedelta(days=1)) for _ in range(4)]
    intakes = [routine(world) for _ in range(5)]
    CallSlip.objects.filter(pk__in=[row.pk for row in slips]).update(created_at=now)
    RoutineInterview.objects.filter(pk__in=[row.pk for row in intakes]).update(created_at=now)
    with patch.object(services.timezone, "now", return_value=now):
        pages = [
            services.list_actions(actor=world.student, page=p, page_size=2) for p in range(1, 6)
        ]
    expected = [row.pk for row in sorted(slips, key=lambda row: str(row.pk))]
    expected += [row.pk for row in sorted(intakes, key=lambda row: str(row.pk))]
    assert [item.source_id for page in pages for item in page.items] == expected
    assert [page.has_next for page in pages] == [True, True, True, True, False]
    assert [row.pk for row in pending_intakes(student=world.student, limit=3)] == expected[4:7]


@pytest.mark.parametrize("source", ["exit", "call", "consent", "join", "message"])
def test_multirow_sources_exclude_old_ineligible_rows_before_sql_prefix(world, settings, source):
    from compass.appointments.models import Appointment
    from compass.call_slips.student_actions import live_instructions
    from compass.ecounseling.student_actions import open_join_windows, pending_consents
    from compass.exit_interviews.student_actions import editable_drafts
    from compass.guidance_messages.models import GuidanceThread
    from compass.guidance_messages.student_actions import unread_threads

    now = timezone.now()
    world.service.is_active = True
    world.service.save(update_fields=["is_active"])
    expected = []
    for i in range(8):
        eligible = i >= 4
        stamp = now + timedelta(seconds=i)
        if source == "exit":
            ay = AcademicYear.objects.create(label=f"Synthetic-{i}")
            inventory = make_inventory(world.student, ay, admit=False)
            row = make_exit_interview(
                student=world.student,
                academic_year=ay,
                inventory=inventory,
                status="DRAFT" if eligible else "SUBMITTED",
                last_submitted_at=None if eligible else stamp,
            )
            ExitInterview.objects.filter(pk=row.pk).update(created_at=stamp)
        elif source == "call":
            row = call_slip(world, now=stamp)
            CallSlip.objects.filter(pk=row.pk).update(
                issuance_mode="LIVE" if eligible else "HISTORICAL"
            )
        elif source in {"consent", "join"}:
            row = Appointment.objects.create(
                reference_code=f"PREFIX-{i}",
                student=world.student,
                provider=world.counselor,
                service=world.service,
                delivery_mode="ONLINE",
                created_by=world.student,
                starts_at=now - timedelta(hours=2),
                ends_at=now + timedelta(hours=1, seconds=i)
                if eligible
                else now - timedelta(hours=1),
            )
            if source == "consent":
                anchor = ECounselingRoom.objects.create(
                    appointment=row, daily_room_name=f"prefix-{i}"
                )
                for scope in ["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"]:
                    consent = ECounselingConsent.objects.create(
                        room=anchor,
                        scope=scope,
                        requested_by=world.counselor,
                        decision="PENDING" if eligible else "DENIED",
                        decided_at=None if eligible else now,
                    )
                    ECounselingConsent.objects.filter(pk=consent.pk).update(requested_at=stamp)
        else:
            row = GuidanceThread.objects.create(
                student=world.student,
                kind="OFFICE",
                status="RESOLVED",
                created_by=world.student,
                routing_college=world.colleges[0],
                assigned_to=world.counselor,
                resolved_by=world.counselor,
                resolved_at=now,
                last_sequence=1,
                last_message_at=stamp,
            )
            message = GuidanceMessage.objects.create(
                thread=row,
                sender=world.counselor,
                sequence=1,
                client_message_id=uuid4(),
                body_ciphertext="unread-by-projection",
            )
            GuidanceMessage.objects.filter(pk=message.pk).update(created_at=stamp)
            GuidanceThreadReadState.objects.create(
                thread=row, user=world.student, last_read_sequence=0 if eligible else 1
            )
        if eligible:
            expected.append(row.pk)
    settings.DAILY_ENABLED = True
    settings.ECOUNSELING_JOIN_EARLY_SECONDS = 0
    settings.ECOUNSELING_REJOIN_GRACE_SECONDS = 0
    with CaptureQueriesContext(connection) as queries:
        if source == "exit":
            result = editable_drafts(student=world.student, limit=3)
            ids = [row.pk for row in result]
            table = "exit_interviews_exitinterview"
        elif source == "call":
            result = live_instructions(student=world.student, now=now, limit=3)
            ids = [row.pk for row in result]
            table = "call_slips_callslip"
        elif source == "consent":
            result = pending_consents(student=world.student, limit=3)
            ids = [row["room__appointment_id"] for row in result]
            assert all(row["pending_count"] == 2 for row in result)
            table = "ecounseling_ecounselingconsent"
        elif source == "join":
            result = open_join_windows(student=world.student, now=now, limit=3)
            ids = [row.pk for row, window in result]
            table = "appointments_appointment"
        else:
            result = unread_threads(student=world.student, limit=3)
            ids = [row.pk for row in result]
            table = "guidance_messages_guidancethread"
    assert ids == expected[:3]
    sql = [q["sql"] for q in queries if f'FROM "{table}"' in q["sql"]]
    assert sql and all("LIMIT 3" in query for query in sql)
    assert all("ciphertext" not in query for query in sql)
