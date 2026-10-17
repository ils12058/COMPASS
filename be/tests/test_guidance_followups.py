"""FUP-1A privacy, lifecycle, persistence, and concurrency regression proofs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import close_old_connections, connections
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.counseling.models import CounselingEncounter
from compass.guidance_followups import services
from compass.guidance_followups.content import decrypt_text
from compass.guidance_followups.errors import (
    FollowUpConflict,
    FollowUpContentUnavailable,
    FollowUpInvalid,
    FollowUpNotFound,
    FollowUpPermissionDenied,
)
from compass.guidance_followups.models import (
    FollowUpEventType,
    FollowUpStatus,
    GuidanceFollowUp,
    GuidanceFollowUpEvent,
)
from compass.organization.models import StaffSupervision
from compass.referrals.models import Referral
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import Service
from tests.test_referrals import context, create_for, setup_scope, sync_policy


@pytest.fixture
def world(settings):
    sync_policy()
    settings.GUIDANCE_FOLLOWUPS_ENABLED = True
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    counselor_a, counselor_b, gss, student_a, student_b, student_none = setup_scope()
    return counselor_a, counselor_b, gss, student_a, student_b, student_none


def create(
    world,
    actor=None,
    student=None,
    assignee=None,
    *,
    key=None,
    description="Private notes",
    source_kind=None,
    source_id=None,
    category="ADMINISTRATIVE",
    now=None,
    visibility=None,
):
    a, _, _, s, _, _ = world
    actor = actor or a
    now = now or timezone.now()
    return services.create_followup(
        actor=actor,
        student_id=(student or s).pk,
        assigned_to_id=(assignee or actor).pk,
        category=category,
        due_at=now + timedelta(days=3),
        source_kind=source_kind,
        source_id=source_id,
        description=description,
        visibility=visibility,
        idempotency_key=key or str(uuid4()),
        request_fingerprint="a" * 64,
        context=context(actor),
        now=now,
    )


pytestmark = pytest.mark.django_db


def test_disabled_by_default_and_strict_server_access(world, settings, client):
    settings.GUIDANCE_FOLLOWUPS_ENABLED = False
    assert client.get("/api/v1/guidance-followups").status_code in (401, 403, 503)
    assert not GuidanceFollowUp.objects.exists()


def test_operational_create_read_complete_and_immutable_history(world):
    counselor, _, gss, student, *_ = world
    item = create(world, actor=gss, student=student)
    assert item.status == FollowUpStatus.PENDING
    assert item.visibility == "OPERATIONAL"
    assert item.events.count() == 1
    assert item.description_ciphertext != "Private notes"
    detail = services.followup_detail(actor=gss, item=item)
    assert detail["description"] == "Private notes"
    assert services.get_followup(actor=gss, followup_id=item.pk).pk == item.pk
    assert services.list_followups(actor=gss).items[0].pk == item.pk

    before = AuditEvent.objects.filter(action="guidance_followup.completed").count()
    result = services.complete_followup(
        actor=gss,
        followup_id=item.pk,
        expected_version=1,
        outcome="Contact completed and acknowledged",
        context=context(gss),
    )
    assert result.status == "COMPLETED"
    assert result.version == 2
    assert result.events.count() == 2
    assert services.followup_detail(actor=gss, item=result)["outcome"] == (
        "Contact completed and acknowledged"
    )
    assert AuditEvent.objects.filter(action="guidance_followup.completed").count() == before + 1
    with pytest.raises(FollowUpConflict):
        services.complete_followup(
            actor=gss,
            followup_id=item.pk,
            expected_version=2,
            outcome="Repeat",
            context=context(gss),
        )
    assert item.events.count() == 2
    assert services.list_followups(actor=gss, status="PENDING").items == ()
    assert counselor.pk != gss.pk


def test_gss_assignment_reassignment_and_supervision_loss(world):
    counselor, counselor_b, gss, student, *_ = world
    item = create(world, actor=counselor)
    changed = services.reassign_followup(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        assigned_to_id=gss.pk,
        context=context(counselor),
    )
    assert changed.assigned_to_id == gss.pk
    assert changed.events.count() == 2
    assert services.list_followups(actor=counselor).items == ()
    assert services.list_followups(actor=gss).items[0].pk == item.pk
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=counselor, followup_id=item.pk)
    with pytest.raises(FollowUpInvalid):
        services.reassign_followup(
            actor=gss,
            followup_id=item.pk,
            expected_version=2,
            assigned_to_id=counselor_b.pk,
            context=context(gss),
        )
    StaffSupervision.objects.filter(staff=gss).delete()
    assert services.list_followups(actor=gss).items == ()
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=gss, followup_id=item.pk)


def test_source_classification_cannot_be_downgraded(world):
    counselor, _, gss, student, *_ = world
    service = Service.objects.create(code="FUP_TEST", name="Counseling for test")
    now = timezone.now()
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        service_name_snapshot=service.name,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        created_by=counselor,
    )
    with pytest.raises(FollowUpInvalid):
        create(
            world,
            source_kind="COUNSELING_ENCOUNTER",
            source_id=encounter.pk,
            category="COUNSELING",
            visibility="OPERATIONAL",
        )
    confidential = create(
        world,
        source_kind="COUNSELING_ENCOUNTER",
        source_id=encounter.pk,
        category="COUNSELING",
    )
    assert confidential.visibility == "COUNSELOR_CONFIDENTIAL"
    assert services.get_followup(actor=counselor, followup_id=confidential.pk).pk == confidential.pk
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=gss, followup_id=confidential.pk)
    with pytest.raises(FollowUpInvalid):
        services.reassign_followup(
            actor=counselor,
            followup_id=confidential.pk,
            expected_version=1,
            assigned_to_id=gss.pk,
            context=context(counselor),
        )


def test_source_matches_student_and_current_actor(world):
    counselor, counselor_b, gss, student_a, student_b, _ = world
    service = Service.objects.create(code="FUP_SOURCE", name="Source service")
    now = timezone.now()
    encounter = CounselingEncounter.objects.create(
        student=student_a,
        counselor=counselor,
        service=service,
        service_name_snapshot=service.name,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        created_by=counselor,
    )
    for student, actor in ((student_b, counselor), (student_a, counselor_b), (student_a, gss)):
        with pytest.raises(FollowUpNotFound):
            create(
                world,
                actor=actor,
                student=student,
                source_kind="COUNSELING_ENCOUNTER",
                source_id=encounter.pk,
                category="COUNSELING",
            )
    routine = RoutineInterview.objects.create(
        student=student_a,
        counselor=counselor,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        student_intake_ciphertext="not read",
        counselor_evaluation_ciphertext="not read",
    )
    linked = create(
        world, source_kind="ROUTINE_INTERVIEW", source_id=routine.pk, category="COUNSELING"
    )
    assert linked.visibility == "COUNSELOR_CONFIDENTIAL"
    with pytest.raises(FollowUpNotFound):
        create(world, source_kind="ROUTINE_INTERVIEW", source_id=uuid4(), category="COUNSELING")


def test_referral_source_keeps_operational_scope(world):
    counselor, counselor_b, gss, student, student_b, _ = world
    source = create_for(
        counselor,
        student,
        key="fup-referral-parent",
        fingerprint="b" * 64,
    )
    item = create(
        world, actor=gss, source_kind="REFERRAL", source_id=source.pk, category="REFERRAL_ACTION"
    )
    assert item.visibility == "OPERATIONAL"
    assert services.followup_detail(actor=gss, item=item)["source"]["id"] == source.pk
    with pytest.raises(FollowUpNotFound):
        create(
            world,
            actor=counselor_b,
            student=student,
            source_kind="REFERRAL",
            source_id=source.pk,
            category="REFERRAL_ACTION",
        )
    Referral.objects.filter(pk=source.pk).update(voided_at=timezone.now(), voided_by=counselor)
    assert services.followup_detail(actor=gss, item=item)["source"] is None


def test_missing_key_tamper_and_cross_record_ciphertext(world, settings):
    counselor, _, _, student, *_ = world
    one = create(world)
    two = create(world)
    with pytest.raises(FollowUpContentUnavailable):
        decrypt_text(one.pk, "description", two.description_ciphertext)
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = ()
    with pytest.raises(FollowUpContentUnavailable):
        services.followup_detail(actor=counselor, item=one)
    with pytest.raises(FollowUpContentUnavailable):
        services.complete_followup(
            actor=counselor,
            followup_id=one.pk,
            expected_version=1,
            outcome="Confidential result",
            context=context(counselor),
        )
    one.refresh_from_db()
    assert one.status == "PENDING"
    assert one.events.count() == 1


def test_idempotency_conflicting_replay_and_version_guard(world):
    counselor, _, _, student, *_ = world
    key = "repeat-key-at-least-twelve"
    one = create(world, key=key)
    replay = create(world, key=key)
    assert one.pk == replay.pk
    assert GuidanceFollowUp.objects.count() == 1
    assert one.events.count() == 1
    with pytest.raises(FollowUpConflict):
        services.create_followup(
            actor=counselor,
            student_id=student.pk,
            assigned_to_id=counselor.pk,
            category="ADMINISTRATIVE",
            due_at=timezone.now() + timedelta(days=1),
            source_kind=None,
            source_id=None,
            description=None,
            visibility=None,
            idempotency_key=key,
            request_fingerprint="b" * 64,
            context=context(counselor),
        )
    services.record_activity(
        actor=counselor,
        followup_id=one.pk,
        expected_version=1,
        remarks="Contacted the Student",
        context=context(counselor),
    )
    with pytest.raises(FollowUpConflict):
        services.update_followup(
            actor=counselor,
            followup_id=one.pk,
            expected_version=1,
            category="STUDENT_CONTACT",
            context=context(counselor),
        )
    one.refresh_from_db()
    assert one.version == 2
    assert one.events.filter(kind=FollowUpEventType.ACTIVITY_RECORDED).count() == 1


def test_cancel_is_terminal_with_encrypted_reason(world):
    counselor, *_ = world
    item = create(world)
    cancelled = services.cancel_followup(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        reason="No longer needed",
        context=context(counselor),
    )
    assert cancelled.status == FollowUpStatus.CANCELLED
    assert cancelled.events.count() == 2
    assert services.followup_detail(actor=counselor, item=cancelled)["events"][-1]["remarks"] == (
        "No longer needed"
    )
    with pytest.raises(FollowUpConflict):
        services.record_activity(
            actor=counselor,
            followup_id=item.pk,
            expected_version=2,
            remarks="Later",
            context=context(counselor),
        )


def test_capability_deactivation_and_direct_object_scope(world):
    counselor, _, gss, student_a, student_b, student_none = world
    item = create(world)
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=gss, followup_id=item.pk)
    capability = Capability.objects.get(code="guidance_followups.manage")
    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=capability,
        effect="REVOKE",
        reason="Regression test capability revoke",
    )
    with pytest.raises(FollowUpPermissionDenied):
        services.complete_followup(
            actor=counselor,
            followup_id=item.pk,
            expected_version=1,
            outcome="Denied",
            context=context(counselor),
        )
    other = create(world, actor=gss, student=student_a, assignee=gss)
    StaffSupervision.objects.filter(staff=gss).update(supervisor=counselor)
    # Student B and unaffiliated Student are never addressable by GSS.
    with pytest.raises(FollowUpNotFound):
        create(world, actor=gss, student=student_b, assignee=gss)
    with pytest.raises(FollowUpNotFound):
        create(world, actor=gss, student=student_none, assignee=gss)
    assert other.pk


@pytest.mark.django_db(transaction=True)
def test_postgres_concurrent_completions_commit_once(world):
    counselor, *_ = world
    item = create(world)

    def run():
        close_old_connections()
        try:
            return services.complete_followup(
                actor=counselor,
                followup_id=item.pk,
                expected_version=1,
                outcome="Completed",
                context=context(counselor),
            ).status
        except FollowUpConflict:
            return "CONFLICT"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _idx: run(), range(2)))
    assert sorted(values) == ["COMPLETED", "CONFLICT"]
    assert (
        GuidanceFollowUpEvent.objects.filter(
            followup=item,
            kind=FollowUpEventType.COMPLETED,
        ).count()
        == 1
    )


def test_deactivated_student_removes_followup_access(world):
    item = create(world)
    item.student.is_active = False
    item.student.save(update_fields=["is_active"])
    assert services.list_followups(actor=world[0]).items == ()
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=world[0], followup_id=item.pk)


def test_workspace_options_filters_and_reporting_are_scoped(world):
    from django.db.models import F

    from compass.guidance_followups import workspace

    counselor, _, gss, student, *_ = world
    mine = create(world)
    create(world, actor=gss)
    students = workspace.eligible_students(actor=counselor)
    assert student.pk in {row.id for row in students.items}
    staff = workspace.eligible_assignees(
        actor=counselor, student_id=student.pk, category="ADMINISTRATIVE"
    )
    assert {counselor.pk, gss.pk} <= {row.pk for row in staff.items}
    GuidanceFollowUp.objects.filter(pk=mine.pk).update(due_at=F("due_at") - timedelta(days=5))
    assert [
        row.pk for row in services.list_followups(actor=counselor, due_window="OVERDUE").items
    ] == [mine.pk]
    assert not services.list_followups(actor=counselor, due_window="UPCOMING").items
    report = workspace.reporting(actor=counselor)
    assert report["pending"] == report["overdue"] == 1
    assert "Private notes" not in str(report)


def test_confidential_source_options_do_not_offer_gss(world):
    from compass.guidance_followups import workspace

    counselor, _, gss, student, *_ = world
    service = Service.objects.create(code="FUP_SOURCE_OPTIONS", name="Counseling", is_active=True)
    source = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=timezone.now() - timedelta(hours=1),
        ended_at=timezone.now(),
    )
    result = workspace.source_context(
        actor=counselor, source_kind="COUNSELING_ENCOUNTER", source_id=source.pk
    )
    assert result["visibility"] == "COUNSELOR_CONFIDENTIAL"
    options = workspace.eligible_assignees(
        actor=counselor,
        student_id=student.pk,
        category="COUNSELING",
        source_kind="COUNSELING_ENCOUNTER",
        source_id=source.pk,
    )
    assert [row.pk for row in options.items] == [counselor.pk]
    with pytest.raises(FollowUpNotFound):
        workspace.source_context(actor=gss, source_kind="COUNSELING_ENCOUNTER", source_id=source.pk)


def test_delegated_create_has_safe_receipt_and_durable_replay(world):
    from compass.guidance_followups.api import _detail_or_receipt

    counselor, _, gss, *_ = world
    key = str(uuid4())
    first = create(world, assignee=gss, key=key)
    receipt = _detail_or_receipt(counselor, first)
    assert receipt["description"] is None
    assert receipt["events"] == []
    assert create(world, assignee=gss, key=key).pk == first.pk
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=counselor, followup_id=first.pk)


def test_http_workspace_contracts_reject_nonstaff_and_unknown_parameters(world):
    from tests.test_appointment_management_scope import auth_client

    counselor, _, _, student, *_ = world
    item = create(world)
    client = auth_client(counselor)
    for path in [
        "/api/v1/guidance-followups",
        "/api/v1/guidance-followups/eligible-students",
        "/api/v1/guidance-followups/report",
        f"/api/v1/guidance-followups/{item.pk}",
    ]:
        result = client.get(path)
        assert result.status_code == 200, result.content
        assert auth_client(student).get(path).status_code == 403
    result = client.get("/api/v1/guidance-followups?not_a_filter=true")
    assert result.status_code == 422
