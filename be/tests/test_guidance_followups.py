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
    due_at=None,
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
        due_at=due_at if due_at is not None else now + timedelta(days=3),
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


def test_durable_lifecycle_retry_does_not_duplicate_activity(world):
    counselor, *_ = world
    item = create(world)
    key = str(uuid4())
    args = dict(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        remarks="Contacted safely",
        context=context(counselor),
        mutation_key=key,
        mutation_fingerprint="c" * 64,
    )
    first, event = services.record_activity(**args)
    replay, repeated = services.record_activity(**args)
    assert first.pk == replay.pk and event.pk == repeated.pk
    assert replay.version == 2
    assert replay.events.count() == 2
    with pytest.raises(FollowUpConflict):
        services.record_activity(**{**args, "mutation_fingerprint": "d" * 64})


def test_work_and_notifications_are_current_and_content_minimized(world, settings):
    from unittest.mock import patch

    from compass.guidance_followups.integration import pending_followups
    from compass.notifications.delivery import deliver_email_delivery
    from compass.notifications.models import EmailDelivery, Notification
    from compass.notifications.services import list_my_notifications, unread_count_for
    from compass.work_queue.services import list_work

    counselor, _, gss, *_ = world
    settings.GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED = True
    item = create(world)
    notice = Notification.objects.get(source_type="guidance_followup_event")
    assert notice.recipient_id == counselor.pk
    assert item.student.get_full_name() not in notice.message
    work = [row for row in list_work(actor=counselor).items if row.kind == "GUIDANCE_FOLLOW_UP"]
    assert [row.source_id for row in work] == [item.pk]
    assert "Private notes" not in str(work)
    changed = services.reassign_followup(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        assigned_to_id=gss.pk,
        context=context(counselor),
    )
    assert not pending_followups(actor=counselor, limit=20)
    assert [row.pk for row in pending_followups(actor=gss, limit=20)] == [item.pk]
    assert not list_my_notifications(actor=counselor).items
    assert unread_count_for(actor=counselor) == 0
    delivery = EmailDelivery.objects.get(notification=notice)
    with patch("compass.notifications.delivery.Mailer") as mailer:
        assert deliver_email_delivery(delivery.pk) == "skipped"
        mailer.assert_not_called()
    # Returning to the earlier owner never revives an older occurrence.
    services.reassign_followup(
        actor=gss,
        followup_id=item.pk,
        expected_version=changed.version,
        assigned_to_id=counselor.pk,
        context=context(gss),
    )
    notices = list_my_notifications(actor=counselor).items
    assert len(notices) == 1 and notices[0].pk != notice.pk
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = ()
    assert pending_followups(actor=counselor, limit=20)
    assert list_my_notifications(actor=counselor).items


def test_followup_external_delivery_is_off_by_default(world, settings):
    from compass.notifications.models import EmailDelivery, Notification, PushDelivery
    from compass.notifications.services import list_my_notifications, unread_count_for

    settings.GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED = False
    item = create(world)
    notice = Notification.objects.get(target_id=item.pk)
    assert notice in list_my_notifications(actor=world[0]).items
    assert unread_count_for(actor=world[0]) == 1
    assert not EmailDelivery.objects.filter(notification__target_id=item.pk).exists()
    assert not PushDelivery.objects.filter(notification__target_id=item.pk).exists()


def test_pending_followup_email_is_suppressed_after_external_pause(world, settings):
    from unittest.mock import patch

    from compass.notifications.delivery import deliver_email_delivery
    from compass.notifications.models import EmailDelivery, EmailDeliveryStatus, Notification
    from compass.notifications.services import list_my_notifications, unread_count_for

    settings.GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED = True
    item = create(world)
    notice = Notification.objects.get(target_id=item.pk)
    delivery = EmailDelivery.objects.get(notification=notice)

    settings.GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED = False
    with patch("compass.notifications.delivery.Mailer") as mailer:
        assert deliver_email_delivery(delivery.pk) == "skipped"
        mailer.assert_not_called()

    delivery.refresh_from_db()
    assert delivery.status == EmailDeliveryStatus.CANCELLED
    assert notice in list_my_notifications(actor=world[0]).items
    assert unread_count_for(actor=world[0]) == 1


def test_material_due_change_has_new_occurrence_and_activity_does_not_notify(world, settings):
    from compass.notifications.models import Notification
    from compass.notifications.services import list_my_notifications

    counselor, *_ = world
    item = create(world)
    first = Notification.objects.get(target_id=item.pk)
    services.record_activity(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        remarks="Progress",
        context=context(counselor),
    )
    assert Notification.objects.filter(target_id=item.pk).count() == 1
    services.update_followup(
        actor=counselor,
        followup_id=item.pk,
        expected_version=2,
        due_at=item.due_at + timedelta(days=1),
        context=context(counselor),
    )
    assert Notification.objects.filter(target_id=item.pk).count() == 2
    current = list_my_notifications(actor=counselor).items
    assert len(current) == 1 and current[0].source_id != first.source_id


def test_reassignment_recovery_is_operational_and_resource_scoped(world):
    from compass.accounts.models import User
    from compass.guidance_followups.recovery import list_recoverable

    counselor, counselor_b, gss, student, *_ = world
    item = create(world, assignee=gss)
    assert not list_recoverable(actor=counselor)["items"]
    User.objects.filter(pk=gss.pk).update(is_active=False)
    assert [row.pk for row in list_recoverable(actor=counselor)["items"]] == [item.pk]
    assert not list_recoverable(actor=counselor_b)["items"]
    # Recovery grants only reassignment, never prior protected detail or editing.
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=counselor, followup_id=item.pk)
    with pytest.raises(FollowUpNotFound):
        services.update_followup(
            actor=counselor,
            followup_id=item.pk,
            expected_version=1,
            description="Not an authorized read",
            context=context(counselor),
        )
    result = services.reassign_followup(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        assigned_to_id=counselor.pk,
        context=context(counselor),
    )
    assert result.assigned_to_id == counselor.pk
    assert not list_recoverable(actor=counselor)["items"]


def test_recovery_detects_capability_revocation_without_loading_descriptions(world):
    from compass.guidance_followups.recovery import list_recoverable

    counselor, _, gss, *_ = world
    item = create(world, assignee=gss)
    UserCapabilityOverride.objects.create(
        user=gss,
        capability=Capability.objects.get(code="guidance_followups.view"),
        effect="REVOKE",
        reason="Recovery fixture",
    )
    assert [row.pk for row in list_recoverable(actor=counselor)["items"]] == [item.pk]


def test_head_recovery_never_includes_confidential_followups(world):
    from compass.accounts.models import Designation, User, UserDesignation
    from compass.guidance_followups.recovery import list_recoverable

    counselor, head, gss, student, *_ = world
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    operational = create(world, assignee=gss)
    service = Service.objects.create(code="FUP_HEAD_RECOVERY", name="Counseling", is_active=True)
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=timezone.now() - timedelta(hours=1),
        ended_at=timezone.now(),
    )
    confidential = create(
        world, source_kind="COUNSELING_ENCOUNTER", source_id=encounter.pk, category="COUNSELING"
    )
    User.objects.filter(pk=counselor.pk).update(is_active=False)
    rows = list_recoverable(actor=head)["items"]
    assert [row.pk for row in rows] == [operational.pk]
    assert confidential.pk not in {row.pk for row in rows}


def test_followup_key_rotation_preserves_bound_content_and_business_state(world, settings):
    from io import StringIO

    from django.core.management import call_command

    counselor, *_ = world
    item = create(world)
    services.record_activity(
        actor=counselor,
        followup_id=item.pk,
        expected_version=1,
        remarks="Protected activity",
        context=context(counselor),
    )
    old = item.description_ciphertext
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (
        Fernet.generate_key().decode(),
        *settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS,
    )
    call_command("rotate_guidance_followup_encryption", dry_run=True, stdout=StringIO())
    item.refresh_from_db()
    assert item.description_ciphertext == old
    version, updated = item.version, item.updated_at
    call_command("rotate_guidance_followup_encryption", stdout=StringIO())
    item.refresh_from_db()
    assert item.description_ciphertext != old
    assert (item.version, item.updated_at) == (version, updated)
    assert services.followup_detail(actor=counselor, item=item)["description"] == "Private notes"
    assert (
        services.followup_detail(actor=counselor, item=item)["events"][-1]["remarks"]
        == "Protected activity"
    )


@pytest.mark.parametrize(
    "action,field,value",
    [
        ("activities", "remarks", "Synthetic activity"),
        ("complete", "outcome", "Synthetic outcome"),
        ("cancel", "reason", "Synthetic cancellation"),
        ("reassign", "assigned_to_id", None),
    ],
)
def test_http_lifecycle_requires_recent_mfa_and_replays_durably(world, action, field, value):
    import json

    from tests.test_appointment_management_scope import auth_client, csrf

    counselor, _, gss, *_ = world
    item = create(world)
    payload = {"expected_version": 1, field: value if value is not None else str(gss.pk)}
    path = f"/api/v1/guidance-followups/{item.pk}/{action}"
    headers = {"HTTP_IDEMPOTENCY_KEY": str(uuid4())}
    denied = auth_client(counselor)
    result = denied.post(
        path, data=json.dumps(payload), content_type="application/json", **csrf(denied), **headers
    )
    assert result.status_code == 403
    assert item.events.count() == 1
    client = auth_client(counselor, recent_mfa=True)
    for _ in range(2):
        result = client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **csrf(client),
            **headers,
        )
        assert result.status_code == 200, result.content
        if action == "reassign":
            assert result.json()["description"] is None
            assert result.json()["events"] == []
    assert item.events.count() == 2


def test_work_queue_prioritization_distinguishes_time_sensitive_and_action_required(world):
    from compass.work_queue.schemas import WorkPriority
    from compass.work_queue.services import list_work

    counselor, _, _, student, *_ = world
    now = timezone.now()

    # Overdue follow-up (created with future date, updated in DB to simulate elapsed time)
    overdue = create(world, due_at=now + timedelta(days=1), now=now)
    GuidanceFollowUp.objects.filter(pk=overdue.pk).update(due_at=now - timedelta(days=1))
    # Due soon (3 days, within 7-day horizon)
    due_soon = create(world, due_at=now + timedelta(days=3), now=now)
    # Due later (14 days, beyond 7-day horizon)
    due_later = create(world, due_at=now + timedelta(days=14), now=now)

    work_items = [
        row for row in list_work(actor=counselor).items if row.kind == "GUIDANCE_FOLLOW_UP"
    ]
    work_by_id = {row.source_id: row for row in work_items}

    assert work_by_id[overdue.pk].priority == WorkPriority.TIME_SENSITIVE
    assert work_by_id[due_soon.pk].priority == WorkPriority.TIME_SENSITIVE
    assert work_by_id[due_later.pk].priority == WorkPriority.ACTION_REQUIRED

    # TIME_SENSITIVE items rank before ACTION_REQUIRED items in the queue
    overdue_idx = next(i for i, r in enumerate(work_items) if r.source_id == overdue.pk)
    due_soon_idx = next(i for i, r in enumerate(work_items) if r.source_id == due_soon.pk)
    due_later_idx = next(i for i, r in enumerate(work_items) if r.source_id == due_later.pk)
    assert overdue_idx < due_later_idx
    assert due_soon_idx < due_later_idx


def test_standalone_student_followup_and_student_support_boundary(world):
    counselor, _, gss, student, *_ = world
    now = timezone.now()

    # Standalone follow-up without linked source record
    standalone = create(
        world,
        actor=counselor,
        student=student,
        category="STUDENT_CONTACT",
        due_at=now + timedelta(days=2),
        source_kind=None,
        source_id=None,
        description="Follow-up initiated from student context",
        now=now,
    )
    assert standalone.source_kind is None
    assert standalone.source_id is None
    assert standalone.visibility == "OPERATIONAL"

    # Counselor (assignee in scope) can view and manage
    assert services.get_followup(actor=counselor, followup_id=standalone.pk).pk == standalone.pk

    # Operational follow-up can be reassigned to GSS in scope, transferring access
    services.reassign_followup(
        actor=counselor,
        followup_id=standalone.pk,
        expected_version=standalone.version,
        assigned_to_id=gss.pk,
        context=context(counselor),
    )
    assert services.get_followup(actor=gss, followup_id=standalone.pk).pk == standalone.pk
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=counselor, followup_id=standalone.pk)
