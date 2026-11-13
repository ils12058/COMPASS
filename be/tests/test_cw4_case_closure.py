"""Closure cycles, protected notes and every outstanding-work disposition on PostgreSQL."""

import io
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.counseling import case_closure_content as content
from compass.counseling import case_closure_services as closure
from compass.counseling.case_appointment_services import link_appointment, unlink_appointment
from compass.counseling.case_closure_models import CounselingCaseClosure
from compass.counseling.case_services import (
    CounselingCaseChanged,
    CounselingCaseClosed,
    CounselingCaseInvalid,
    CounselingCaseNotFound,
    CounselingCaseNotPermitted,
    get_case,
    link_session,
    lock_case_for_recording,
    unlink_session,
)
from compass.guidance_followups import policy
from compass.guidance_followups import services as followups
from compass.guidance_followups.errors import FollowUpConflict
from compass.notifications.models import Notification
from tests.test_appointment_management_scope import auth_client, csrf
from tests.test_counseling import context, make_user
from tests.test_counseling_cases import intake, link, record
from tests.test_cw2_next_actions import create as create_task
from tests.test_cw3_case_coverage import (
    decide as decide_coverage,
)
from tests.test_cw3_case_coverage import (
    offer as offer_coverage,
)
from tests.test_cw3_case_coverage import (
    prepare as prepare_coverage,
)
from tests.test_cw3_transfers import (
    decide as decide_transfer,
)
from tests.test_cw3_transfers import (
    future_appointment,
    transfer_world,
)
from tests.test_cw3_transfers import (
    offer as offer_transfer,
)
from tests.test_cw3_transfers import (
    prepare as prepare_transfer,
)

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/counseling/cases"
NOTE = "Contact attempts were documented on three separate occasions."


@pytest.fixture
def cw4(settings):
    return transfer_world(settings, "cw4")


def close(w, *, actor=None, **changes):
    w.case.refresh_from_db()
    values = {
        "actor": actor or w.a,
        "case_id": w.case.pk,
        "expected_version": w.case.version,
        "reason": "PLANNED_SUPPORT_CONCLUDED",
        "outcome": "GOALS_MET",
        "context": context(actor or w.a),
    }
    values.update(changes)
    return closure.close_case(**values)


def reopen(w, *, actor=None, **changes):
    w.case.refresh_from_db()
    values = {
        "actor": actor or w.a,
        "case_id": w.case.pk,
        "expected_version": w.case.version,
        "reason": "SAME_CONCERN_RETURNED",
        "context": context(actor or w.a),
    }
    values.update(changes)
    return closure.reopen_case(**values)


def designate(w, task, **changes):
    w.case.refresh_from_db()
    task.refresh_from_db()
    values = {
        "actor": w.a,
        "case_id": w.case.pk,
        "task_id": task.pk,
        "expected_version": w.case.version,
        "expected_task_version": task.version,
        "administrative_action": True,
        "assigned_to_id": task.assigned_to_id,
        "due_at": timezone.now() + timedelta(days=3),
        "context": context(w.a),
    }
    values.update(changes)
    return closure.designate_task(**values)


def write(client, path, data):
    return client.post(
        path, data=json.dumps(data, default=str), content_type="application/json", **csrf(client)
    )


@pytest.mark.parametrize("audience", ["b", "head", "goa", "faculty", "student", "it"])
def test_every_non_owner_is_denied_close_reopen_and_note_read(cw4, audience):
    w = cw4
    if audience == "it":
        actor = make_user("cw4-it@example.edu", "IT_ADMIN")
    else:
        actor = getattr(w, audience)
    client = auth_client(actor)
    before = w.case.version
    for action, payload in (
        ("close", {"reason": "PLANNED_SUPPORT_CONCLUDED", "outcome": "GOALS_MET"}),
        ("reopen", {"reason": "SAME_CONCERN_RETURNED"}),
    ):
        result = write(
            client, f"{ROOT}/{w.case.pk}/{action}", {"expected_version": before, **payload}
        )
        assert result.status_code in {403, 404}, result.content
    assert client.get(f"{ROOT}/{w.case.pk}").status_code in {403, 404}
    w.case.refresh_from_db()
    assert w.case.status == "ACTIVE" and w.case.version == before
    assert not CounselingCaseClosure.objects.exists()


def test_owner_and_head_only_close_their_own_case_and_guessed_ids_are_concealed(cw4):
    w = cw4
    close(w)
    assert w.case.closures.count() == 1
    own = intake(w.head, w.student)
    result = closure.close_case(
        actor=w.head,
        case_id=own.pk,
        expected_version=own.version,
        reason="STUDENT_DISCONTINUED",
        outcome="NOT_ASSESSED",
        context=context(w.head),
    )
    assert result.status == "CLOSED"
    with pytest.raises(CounselingCaseNotFound):
        closure.close_case(
            actor=w.a,
            case_id=uuid4(),
            expected_version=1,
            reason="STUDENT_DISCONTINUED",
            outcome="NOT_ASSESSED",
        )


@pytest.mark.parametrize(
    "reason",
    [
        "PLANNED_SUPPORT_CONCLUDED",
        "STUDENT_DISCONTINUED",
        "CONTACT_NOT_REESTABLISHED",
        "EXTERNAL_HANDOVER_CONFIRMED",
        "ELIGIBILITY_ENDED",
    ],
)
def test_each_reason_records_separate_outcome_and_encrypted_optional_note(cw4, reason):
    w = cw4
    close(w, reason=reason, outcome="NOT_ASSESSED", note=NOTE)
    row = w.case.closures.get()
    assert (
        row.reason == reason
        and row.outcome == "NOT_ASSESSED"
        and NOTE not in row.content_ciphertext
    )
    assert content.read(row) == NOTE
    assert (
        list(AuditEvent.objects.filter(action="counseling.case.closed"))[0].metadata["reason"]
        == reason
    )
    assert NOTE not in json.dumps(list(AuditEvent.objects.values("metadata")), default=str)


@pytest.mark.parametrize("note", [None, "", "Brief attempt", "x" * 4001])
def test_contact_attempts_note_has_meaningful_length_and_bounded_plain_text(cw4, note):
    with pytest.raises(CounselingCaseInvalid):
        close(cw4, reason="CONTACT_NOT_REESTABLISHED", note=note)
    assert cw4.case.closures.count() == 0


def test_note_envelope_cannot_be_copied_and_rotation_preserves_history(cw4, settings):
    w = cw4
    close(w, note=NOTE)
    first = w.case.closures.get()
    before = (first.closed_at, first.closed_by_id, first.reason, first.outcome)
    reopen(w)
    close(w, note="Another retained closure note.")
    second = w.case.closures.exclude(pk=first.pk).get()
    second.content_ciphertext = first.content_ciphertext
    with pytest.raises(content.ClosureContentUnavailable):
        content.read(second)
    old = settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (Fernet.generate_key().decode(), *old)
    output = io.StringIO()
    call_command("rotate_counselor_handoff_summary_encryption", stdout=output)
    first.refresh_from_db()
    assert (
        content.read(first) == NOTE
        and (first.closed_at, first.closed_by_id, first.reason, first.outcome) == before
    )
    assert "Case closure note encryption: scanned=2; rewrap=2; unreadable=0" in output.getvalue()
    assert NOTE not in output.getvalue()


def test_closure_and_reopening_are_immutable_and_each_cycle_stays_ordered(cw4):
    w = cw4
    close(w, note=NOTE)
    first = w.case.closures.get()
    first.reason = "ELIGIBILITY_ENDED"
    with pytest.raises(ValueError):
        first.save()
    with pytest.raises(ValueError):
        first.delete()
    first.refresh_from_db()
    reopen(w)
    close(w, reason="STUDENT_DISCONTINUED", outcome="NOT_ASSESSED")
    reopen(w, reason="FURTHER_SUPPORT_NEEDED")
    rows = list(w.case.closures.all())
    assert len(rows) == 2 and all(row.reopened_at is not None for row in rows)
    assert (
        rows[0].reason == "PLANNED_SUPPORT_CONCLUDED" and rows[1].reason == "STUDENT_DISCONTINUED"
    )
    assert rows[0].closed_at <= rows[0].reopened_at <= rows[1].closed_at <= rows[1].reopened_at
    rows[0].reopen_reason = "CLOSED_IN_ERROR"
    with pytest.raises(ValueError):
        rows[0].save()
    assert w.case.events.filter(kind="OPENED").count() == 1


@pytest.mark.parametrize("kind", ["TRANSFER", "COVERAGE", "APPOINTMENT", "TASK"])
def test_each_blocker_preserves_case_and_resolves_through_its_own_workflow(cw4, kind):
    w = cw4
    if kind == "TRANSFER":
        item = prepare_transfer(w)
    elif kind == "COVERAGE":
        item = prepare_coverage(w)
    elif kind == "APPOINTMENT":
        item = future_appointment(w)
        link_appointment(
            actor=w.a,
            case_id=w.case.pk,
            appointment_id=item.pk,
            expected_version=w.case.version,
            context=context(w.a),
        )
    else:
        item = create_task(w)
    w.case.refresh_from_db()
    before = (w.case.status, w.case.version)
    with pytest.raises(closure.CaseCloseBlocked) as error:
        close(w)
    assert kind in error.value.blockers
    w.case.refresh_from_db()
    assert (w.case.status, w.case.version) == before and w.case.closures.count() == 0
    if kind == "TRANSFER":
        decide_transfer(item, w.a, "cancel", reason="REQUEST_WITHDRAWN")
    elif kind == "COVERAGE":
        decide_coverage(item, w.a, "cancel", reason="REQUEST_WITHDRAWN")
    elif kind == "APPOINTMENT":
        unlink_appointment(
            actor=w.a,
            case_id=w.case.pk,
            appointment_id=item.pk,
            reason="NOT_PART_OF_THIS_CASE",
            expected_version=w.case.version,
            context=context(w.a),
        )
    else:
        followups.cancel_followup(
            reason="Administrative action withdrawn",
            actor=w.a,
            followup_id=item.pk,
            expected_version=item.version,
            context=context(w.a),
        )
    close(w)
    assert w.case.closures.count() == 1


def test_active_coverage_and_delegated_work_block_then_explicit_revoke_returns_work(cw4):
    w = cw4
    task = create_task(w)
    item = offer_coverage(w, tasks=(task,))
    item = decide_coverage(item, w.b, "accept")
    package = closure.get_closure_context(actor=w.a, case_id=w.case.pk)
    assert {"COVERAGE", "DELEGATED_TASK", "TASK"}.issubset(package["blockers"])
    with pytest.raises(closure.CaseCloseBlocked):
        close(w)
    decide_coverage(item, w.a, "revoke", reason="REQUEST_WITHDRAWN")
    task.refresh_from_db()
    designate(w, task)
    close(w)
    assert item.task_plans.get().returned_at is not None and w.case.closures.count() == 1


def test_all_blockers_are_reported_together_without_implicit_cancellation(cw4):
    w = cw4
    transfer = prepare_transfer(w)
    coverage = prepare_coverage(w)
    task = create_task(w)
    appointment = future_appointment(w)
    w.case.refresh_from_db()
    link_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=appointment.pk,
        expected_version=w.case.version,
        context=context(w.a),
    )
    client = auth_client(w.a)
    w.case.refresh_from_db()
    result = write(
        client,
        f"{ROOT}/{w.case.pk}/close",
        {
            "expected_version": w.case.version,
            "reason": "PLANNED_SUPPORT_CONCLUDED",
            "outcome": "GOALS_MET",
        },
    )
    assert (
        result.status_code == 409
        and result.json()["error"]["code"] == "counseling_case_close_blocked"
    )
    assert set(result.json()["error"]["details"]["blocking_item_kinds"]) == {
        "TRANSFER",
        "COVERAGE",
        "TASK",
        "APPOINTMENT",
    }
    task.refresh_from_db()
    appointment.refresh_from_db()
    transfer.refresh_from_db()
    coverage.refresh_from_db()
    assert (
        task.status == "PENDING"
        and appointment.status == "SCHEDULED"
        and transfer.state == coverage.state == "PREPARED"
    )


def test_expired_transfer_and_coverage_do_not_block_closure(cw4):
    w = cw4
    transfer = offer_transfer(w)
    transfer.review_expires_at = timezone.now() - timedelta(minutes=1)
    transfer.save(update_fields=["review_expires_at"])
    coverage = prepare_coverage(w)
    coverage.expires_at = timezone.now() - timedelta(seconds=1)
    coverage.starts_at = coverage.expires_at - timedelta(days=1)
    coverage.save(update_fields=["starts_at", "expires_at"])
    close(w)
    assert w.case.closures.count() == 1


def test_administrative_designation_requires_explicit_choice_and_valid_versions(cw4):
    w = cw4
    task = create_task(w)
    with pytest.raises(CounselingCaseInvalid):
        designate(w, task, administrative_action=False)
    with pytest.raises(CounselingCaseChanged):
        designate(w, task, expected_task_version=999)
    from compass.guidance_followups.errors import FollowUpInvalid

    with pytest.raises(FollowUpInvalid):
        designate(w, task, assigned_to_id=w.b.pk)
    designate(w, task)
    task.refresh_from_db()
    assert task.post_closure_designated_at and task.post_closure_closure_id is None
    close(w)
    task.refresh_from_db()
    assert task.post_closure_closure_id == w.case.closures.get().pk
    followups.update_followup(
        actor=w.a,
        followup_id=task.pk,
        expected_version=task.version,
        due_at=timezone.now() + timedelta(days=5),
        context=context(w.a),
    )
    task.refresh_from_db()
    followups.complete_followup(
        actor=w.a,
        followup_id=task.pk,
        expected_version=task.version,
        outcome="Administrative action finished.",
        context=context(w.a),
    )
    task.refresh_from_db()
    assert task.status == "COMPLETED"


def test_unmarked_task_on_closed_case_can_be_completed_or_cancelled_and_no_creation(cw4):
    w = cw4
    first = create_task(w)
    second = create_task(w)
    # Inconsistent legacy state must permit existing-task recovery without fabricated history.
    w.case.status = "CLOSED"
    w.case.save(update_fields=["status"])
    assert policy.authorized(w.a, first, manage=True)
    followups.complete_followup(
        actor=w.a,
        followup_id=first.pk,
        expected_version=first.version,
        outcome="Finished",
        context=context(w.a),
    )
    followups.cancel_followup(
        reason="Administrative action withdrawn",
        actor=w.a,
        followup_id=second.pk,
        expected_version=second.version,
        context=context(w.a),
    )
    with pytest.raises(FollowUpConflict):
        create_task(w)


def test_closed_case_refuses_all_membership_mutations_and_preserves_records(cw4):
    w = cw4
    session = record(w.a, w.student)
    link(w.a, w.case, session)
    appointment = future_appointment(w)
    w.case.refresh_from_db()
    link_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=appointment.pk,
        expected_version=w.case.version,
        context=context(w.a),
    )
    # Resolve via deliberate unlink; closure keeps the provenance row.
    w.case.refresh_from_db()
    unlink_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=appointment.pk,
        reason="NOT_PART_OF_THIS_CASE",
        expected_version=w.case.version,
        context=context(w.a),
    )
    close(w)
    for operation in (
        lambda: link_session(
            actor=w.a,
            case_id=w.case.pk,
            encounter_id=session.pk,
            expected_version=w.case.version,
            context=context(w.a),
        ),
        lambda: unlink_session(
            actor=w.a,
            case_id=w.case.pk,
            encounter_id=session.pk,
            reason="LINKED_BY_MISTAKE",
            expected_version=w.case.version,
            context=context(w.a),
        ),
        lambda: link_appointment(
            actor=w.a,
            case_id=w.case.pk,
            appointment_id=appointment.pk,
            expected_version=w.case.version,
            context=context(w.a),
        ),
        lambda: unlink_appointment(
            actor=w.a,
            case_id=w.case.pk,
            appointment_id=appointment.pk,
            reason="LINKED_BY_MISTAKE",
            expected_version=w.case.version,
            context=context(w.a),
        ),
        lambda: lock_case_for_recording(actor=w.a, case_id=w.case.pk),
    ):
        with pytest.raises(CounselingCaseClosed):
            operation()
    view = get_case(actor=w.a, case_id=w.case.pk)
    assert (
        view.summary.session_count == 1 and len(view.sessions) == 1 and len(view.appointments) == 1
    )
    assert not view.can_manage and not view.can_link_appointments and not view.next_actions.can_add


def test_owner_detail_is_private_lists_omit_notes_and_no_closure_notifications(cw4):
    w = cw4
    client = auth_client(w.a)
    before = Notification.objects.count()
    close(w, note=NOTE)
    response = client.get(f"{ROOT}/{w.case.pk}")
    assert response.status_code == 200, response.content
    assert response["Cache-Control"] == "private, no-store" and response["Pragma"] == "no-cache"
    data = response.json()
    assert data["closure"]["note"] == NOTE and data["can_reopen"] and not data["can_close"]
    listed = client.get(ROOT, {"status": "CLOSED"}).json()["items"][0]
    assert listed["closed_at"] and listed["closure_reason"] == "PLANNED_SUPPORT_CONCLUDED"
    assert "outcome" not in listed and "note" not in listed and NOTE not in json.dumps(listed)
    assert Notification.objects.count() == before
    from compass.guidance_followups.workspace import reporting
    from compass.work_queue.services import list_work

    assert NOTE not in list_work(actor=w.a).model_dump_json()
    assert NOTE not in json.dumps(reporting(actor=w.a), default=str)


def test_authority_rechecked_after_note_decryption_and_stale_actions_preserve_cycles(cw4):
    w = cw4
    close(w, note=NOTE)
    original = content.read

    def remove_authority(row):
        text = original(row)
        from compass.accounts.models import User

        User.objects.filter(pk=w.a.pk).update(is_active=False)
        return text

    with patch.object(content, "read", side_effect=remove_authority):
        with pytest.raises(CounselingCaseNotPermitted):
            closure.protected_closures(actor=w.a, case_id=w.case.pk)
    w.a.refresh_from_db()
    assert w.a.is_active  # protected read transaction rolled back
    with pytest.raises(CounselingCaseChanged):
        reopen(w, expected_version=999)
    assert w.case.closures.get().reopened_at is None


def test_accepted_handoff_remains_owner_readable_after_closure(cw4):
    w = cw4
    transfer = offer_transfer(w)
    transfer = decide_transfer(transfer, w.b, "accept")
    w.case.refresh_from_db()
    close(w, actor=w.b)
    from compass.counseling.case_handoff_services import operate

    body = operate(
        actor=w.b, transfer_id=transfer.pk, handoff_id=transfer.case_handoff_id, operation="read"
    )
    assert body["sections"]["context_and_purpose"] == "Continuing student support."


def test_missing_note_keyring_fails_atomically_but_an_optional_absent_note_needs_no_key(
    cw4, settings
):
    w = cw4
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = ()
    close(w)
    reopen(w)
    w.case.refresh_from_db()
    version = w.case.version
    with pytest.raises(content.ClosureContentUnavailable):
        close(w, reason="CONTACT_NOT_REESTABLISHED", note=NOTE)
    w.case.refresh_from_db()
    assert w.case.status == "ACTIVE" and w.case.version == version
    assert w.case.closures.count() == 1 and w.case.closures.get().reopened_at is not None


def test_close_and_reopen_audit_failure_roll_back_the_entire_cycle(cw4):
    w = cw4
    with patch.object(closure, "record_event", side_effect=RuntimeError("Synthetic audit failure")):
        with pytest.raises(RuntimeError):
            close(w, note=NOTE)
    w.case.refresh_from_db()
    assert w.case.status == "ACTIVE" and w.case.version == 1 and not w.case.closures.exists()
    close(w)
    w.case.refresh_from_db()
    version = w.case.version
    with patch.object(closure, "record_event", side_effect=RuntimeError("Synthetic audit failure")):
        with pytest.raises(RuntimeError):
            reopen(w)
    w.case.refresh_from_db()
    assert w.case.status == "CLOSED" and w.case.version == version
    assert w.case.closures.get().reopened_at is None
