from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import AppointmentStatus
from compass.appointments.services import (
    cancel_appointment,
    complete_appointment,
    mark_appointment_no_show,
    reassign_appointment,
)
from compass.audit.models import AuditEvent
from compass.counseling import finish_service as finish_service_module
from compass.counseling.finish_service import (
    CounselingAppointmentClosed,
    CounselingFinishConflict,
    finish_counseling_appointment,
)
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import (
    CounselingAppointmentAlreadyUsed,
    CounselingNotFound,
    create_encounter,
)
from compass.feedback.models import FeedbackOpportunity
from compass.notifications.models import Notification
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    RoutineInterviewAppointmentInvalid,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from tests.test_counseling import (
    actual_times,
    context,
    create_counseling_service,
    make_appointment,
    make_user,
    sync_policy,
)
from tests.test_routine_interviews import configure_year, submit_inventory


def setup_domain(prefix: str):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    return admin, counselor, student, service


def setup_student_context(prefix: str):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    return admin, counselor, student, service


def fresh_user(user_id):
    return User.objects.select_related("role").get(pk=user_id)


def finish_as(counselor_id, appointment_id, *, start, end, now=None):
    actor = fresh_user(counselor_id)
    return finish_counseling_appointment(
        appointment_id=appointment_id,
        counselor=actor,
        counseling_occurred=True,
        actual_started_at=start,
        actual_ended_at=end,
        context=context(actor),
        now=now,
    )


def audit_count(action: str, target_id=None) -> int:
    queryset = AuditEvent.objects.filter(action=action)
    if target_id is not None:
        queryset = queryset.filter(target_id=str(target_id))
    return queryset.count()


def patch_email_kick(monkeypatch) -> None:
    monkeypatch.setattr(
        "compass.notifications.services._safe_kick_email_delivery",
        lambda delivery_id: None,
    )


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_finishes_create_one_encounter_and_one_replay(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_domain("race-finish-finish")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    barrier = threading.Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                result = finish_as(counselor.pk, appointment.pk, start=start, end=end)
            except Exception as exc:  # pragma: no cover - reported through the assertion
                return {"error": f"{type(exc).__name__}: {exc}"}
            return {
                "result": result.encounter_result,
                "already_finished": result.already_finished,
                "encounter_id": result.encounter.pk,
            }
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        outcomes = [future.result(timeout=30) for future in futures]

    assert all("error" not in outcome for outcome in outcomes), outcomes
    assert {outcome["result"] for outcome in outcomes} == {"CREATED", "EXISTING"}
    assert sorted(outcome["already_finished"] for outcome in outcomes) == [False, True]
    assert len({outcome["encounter_id"] for outcome in outcomes}) == 1

    assert CounselingEncounter.objects.count() == 1
    assert FeedbackOpportunity.objects.count() == 1
    assert Notification.objects.filter(event_code="feedback.invitation").count() == 1
    assert audit_count("appointment.completed", appointment.pk) == 1
    assert audit_count("counseling.encounter.created") == 1


@pytest.mark.django_db(transaction=True)
def test_finish_and_legacy_creation_serialize_on_the_appointment(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_domain("race-finish-legacy")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    barrier = threading.Barrier(2)

    def finish_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = finish_as(counselor.pk, appointment.pk, start=start, end=end)
            return {"result": result.encounter_result, "encounter_id": result.encounter.pk}
        finally:
            connection.close()

    def legacy_worker():
        close_old_connections()
        try:
            actor = fresh_user(counselor.pk)
            barrier.wait(timeout=10)
            try:
                encounter = create_encounter(
                    counselor=actor,
                    entry_mode="APPOINTMENT",
                    appointment_id=appointment.pk,
                    started_at=start,
                    ended_at=end,
                    context=context(actor),
                )
            except CounselingAppointmentAlreadyUsed:
                return {"result": "already_used"}
            return {"result": "created", "encounter_id": encounter.pk}
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        finish_future = executor.submit(finish_worker)
        legacy_future = executor.submit(legacy_worker)
        finish_outcome = finish_future.result(timeout=30)
        legacy_outcome = legacy_future.result(timeout=30)

    assert CounselingEncounter.objects.count() == 1
    assert audit_count("appointment.completed", appointment.pk) == 1
    if legacy_outcome["result"] == "created":
        assert finish_outcome["result"] == "EXISTING"
        assert finish_outcome["encounter_id"] == legacy_outcome["encounter_id"]
        assert appointment_status(appointment) == AppointmentStatus.COMPLETED
    else:
        assert legacy_outcome["result"] == "already_used"
        assert finish_outcome["result"] == "CREATED"


def appointment_status(appointment) -> str:
    appointment.refresh_from_db()
    return appointment.status


@pytest.mark.django_db(transaction=True)
def test_finish_and_administrative_completion_write_one_completion_event(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_domain("race-finish-complete")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    barrier = threading.Barrier(2)

    def finish_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = finish_as(counselor.pk, appointment.pk, start=start, end=end)
            return result.encounter_result
        finally:
            connection.close()

    def complete_worker():
        close_old_connections()
        try:
            actor = fresh_user(counselor.pk)
            barrier.wait(timeout=10)
            item = complete_appointment(
                appointment_id=appointment.pk,
                actor=actor,
                context=context(actor),
            )
            return item.status
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        finish_future = executor.submit(finish_worker)
        complete_future = executor.submit(complete_worker)
        finish_result = finish_future.result(timeout=30)
        complete_result = complete_future.result(timeout=30)

    assert finish_result == "CREATED"
    assert complete_result == AppointmentStatus.COMPLETED
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.COMPLETED
    assert CounselingEncounter.objects.filter(appointment=appointment).count() == 1
    assert audit_count("appointment.completed", appointment.pk) == 1


@pytest.mark.django_db(transaction=True)
def test_finish_and_cancellation_never_leave_a_cancelled_appointment_with_an_encounter(
    monkeypatch,
):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_domain("race-finish-cancel")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    starts_at = timezone.now() + timedelta(hours=1)
    appointment.starts_at = starts_at
    appointment.ends_at = starts_at + timedelta(hours=1)
    appointment.cancellation_cutoff_minutes = 0
    appointment.save(
        update_fields=[
            "starts_at",
            "ends_at",
            "cancellation_cutoff_minutes",
            "updated_at",
        ]
    )
    start, end = starts_at, starts_at + timedelta(minutes=4)
    barrier = threading.Barrier(2)

    def finish_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                finish_as(
                    counselor.pk,
                    appointment.pk,
                    start=start,
                    end=end,
                    now=starts_at + timedelta(minutes=5),
                )
            except CounselingAppointmentClosed:
                return "closed"
            return "finished"
        finally:
            connection.close()

    def cancel_worker():
        close_old_connections()
        try:
            actor = fresh_user(student.pk)
            barrier.wait(timeout=10)
            try:
                cancel_appointment(
                    appointment_id=appointment.pk,
                    actor=actor,
                    administrative=False,
                    context=context(actor),
                    now=starts_at - timedelta(minutes=1),
                )
            except Exception:
                return "conflict"
            return "cancelled"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        finish_future = executor.submit(finish_worker)
        cancel_future = executor.submit(cancel_worker)
        finish_outcome = finish_future.result(timeout=30)
        cancel_outcome = cancel_future.result(timeout=30)

    expected = {(finish_outcome, cancel_outcome)}
    assert expected <= {("finished", "conflict"), ("closed", "cancelled")}
    appointment.refresh_from_db()
    encounter_count = CounselingEncounter.objects.filter(appointment=appointment).count()
    if finish_outcome == "finished":
        assert appointment.status == AppointmentStatus.COMPLETED
        assert encounter_count == 1
    else:
        assert appointment.status == AppointmentStatus.CANCELLED
        assert encounter_count == 0


@pytest.mark.django_db(transaction=True)
def test_finish_and_no_show_never_leave_a_no_show_appointment_with_an_encounter(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_domain("race-finish-no-show")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    barrier = threading.Barrier(2)

    def finish_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                finish_as(counselor.pk, appointment.pk, start=start, end=end)
            except CounselingAppointmentClosed:
                return "closed"
            return "finished"
        finally:
            connection.close()

    def no_show_worker():
        close_old_connections()
        try:
            actor = fresh_user(counselor.pk)
            barrier.wait(timeout=10)
            try:
                mark_appointment_no_show(
                    appointment_id=appointment.pk,
                    actor=actor,
                    context=context(actor),
                    now=end + timedelta(minutes=1),
                )
            except Exception:
                return "conflict"
            return "no_show"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        finish_future = executor.submit(finish_worker)
        no_show_future = executor.submit(no_show_worker)
        finish_outcome = finish_future.result(timeout=30)
        no_show_outcome = no_show_future.result(timeout=30)

    assert (finish_outcome, no_show_outcome) in {
        ("finished", "conflict"),
        ("closed", "no_show"),
    }
    appointment.refresh_from_db()
    encounter_count = CounselingEncounter.objects.filter(appointment=appointment).count()
    if finish_outcome == "finished":
        assert appointment.status == AppointmentStatus.COMPLETED
        assert encounter_count == 1
    else:
        assert appointment.status == AppointmentStatus.NO_SHOW
        assert encounter_count == 0


@pytest.mark.django_db(transaction=True)
def test_finish_and_routine_finalization_leave_a_valid_link_and_no_orphan(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_student_context("race-finish-finalize")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    routine = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"college_experience": "Submitted intake."},
    )
    submit_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        context=context(student),
    )
    start, end = actual_times()
    encounter = create_encounter(
        counselor=counselor,
        entry_mode="APPOINTMENT",
        appointment_id=appointment.pk,
        started_at=start,
        ended_at=end,
        context=context(counselor),
    )
    barrier = threading.Barrier(2)

    def finish_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = finish_as(counselor.pk, appointment.pk, start=start, end=end)
            return (result.encounter_result, result.encounter.pk)
        finally:
            connection.close()

    def finalize_worker():
        close_old_connections()
        try:
            actor = fresh_user(counselor.pk)
            barrier.wait(timeout=10)
            finalize_assigned_evaluation(
                counselor=actor,
                routine_interview_id=routine.pk,
                encounter_id=None,
                context=context(actor),
            )
            return "finalized"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        finish_future = executor.submit(finish_worker)
        finalize_future = executor.submit(finalize_worker)
        finish_result = finish_future.result(timeout=30)
        finalize_result = finalize_future.result(timeout=30)

    assert finish_result == ("EXISTING", encounter.pk)
    assert finalize_result == "finalized"
    routine.refresh_from_db()
    assert routine.evaluation_finalized_at is not None
    assert routine.counseling_encounter_id == encounter.pk
    assert CounselingEncounter.objects.filter(appointment=appointment).count() == 1
    assert audit_count("appointment.completed", appointment.pk) == 1
    assert audit_count("routine_interview.encounter_linked", routine.pk) == 1


@pytest.mark.django_db(transaction=True)
def test_finish_and_reassignment_never_both_win():
    _, counselor, student, service = setup_domain("race-finish-reassign")
    other = make_user("race-finish-reassign-other@example.edu", "COUNSELOR")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    starts_at = timezone.now() + timedelta(hours=2)
    appointment.starts_at = starts_at
    appointment.ends_at = starts_at + timedelta(hours=1)
    appointment.save(update_fields=["starts_at", "ends_at", "updated_at"])
    start, end = starts_at, starts_at + timedelta(minutes=4)
    barrier = threading.Barrier(2)

    def finish_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                finish_as(
                    counselor.pk,
                    appointment.pk,
                    start=start,
                    end=end,
                    now=starts_at + timedelta(minutes=5),
                )
            except (CounselingAppointmentClosed, CounselingNotFound):
                return "not_found"
            except Exception as exc:
                return f"error:{type(exc).__name__}"
            return "finished"
        finally:
            connection.close()

    def reassign_worker():
        close_old_connections()
        try:
            actor = fresh_user(counselor.pk)
            barrier.wait(timeout=10)
            try:
                reassign_appointment(
                    appointment_id=appointment.pk,
                    actor=actor,
                    provider_id=other.pk,
                    reason="Synthetic concurrent reassignment.",
                    context=context(actor),
                    now=starts_at - timedelta(minutes=1),
                )
            except Exception:
                return "conflict"
            return "reassigned"
        finally:
            connection.close()

    with (
        patch("compass.appointments.services._validate_existing_service"),
        patch("compass.appointments.services._interval_is_available", return_value=True),
        patch("compass.appointments.services._has_overlap", return_value=False),
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            finish_future = executor.submit(finish_worker)
            reassign_future = executor.submit(reassign_worker)
            finish_outcome = finish_future.result(timeout=30)
            reassign_outcome = reassign_future.result(timeout=30)

    assert (finish_outcome, reassign_outcome) in {
        ("finished", "conflict"),
        ("not_found", "reassigned"),
    }
    appointment.refresh_from_db()
    if finish_outcome == "finished":
        assert appointment.provider_id == counselor.pk
        assert CounselingEncounter.objects.filter(appointment=appointment).count() == 1
    else:
        assert appointment.provider_id == other.pk
        assert appointment.status == AppointmentStatus.SCHEDULED
        assert not CounselingEncounter.objects.filter(appointment=appointment).exists()


@pytest.mark.django_db(transaction=True)
def test_retry_after_commit_returns_the_same_identifiers(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_domain("race-retry")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()

    def worker():
        close_old_connections()
        try:
            result = finish_as(counselor.pk, appointment.pk, start=start, end=end)
            return {
                "result": result.encounter_result,
                "already_finished": result.already_finished,
                "encounter_id": result.encounter.pk,
                "appointment_id": result.appointment.pk,
            }
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(worker).result(timeout=30)
        counts = (
            CounselingEncounter.objects.count(),
            FeedbackOpportunity.objects.count(),
            audit_count("appointment.completed", appointment.pk),
            audit_count("counseling.encounter.created"),
        )
        second = executor.submit(worker).result(timeout=30)

    assert first["result"] == "CREATED"
    assert first["already_finished"] is False
    assert second["result"] == "EXISTING"
    assert second["already_finished"] is True
    assert second["encounter_id"] == first["encounter_id"]
    assert second["appointment_id"] == first["appointment_id"]
    assert (
        CounselingEncounter.objects.count(),
        FeedbackOpportunity.objects.count(),
        audit_count("appointment.completed", appointment.pk),
        audit_count("counseling.encounter.created"),
    ) == counts


@pytest.mark.django_db(transaction=True)
def test_finish_detects_a_routine_created_after_its_unlocked_lookup(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_student_context("race-fix-one")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    lookup_done = threading.Event()
    routine_created = threading.Event()
    real_lock = finish_service_module.lock_routine_for_encounter_recording

    def observed_lock(**kwargs):
        item = real_lock(**kwargs)
        assert item is None
        lookup_done.set()
        if not routine_created.wait(timeout=15):
            raise AssertionError("timed out waiting for the concurrent Routine creation")
        return item

    monkeypatch.setattr(
        finish_service_module,
        "lock_routine_for_encounter_recording",
        observed_lock,
    )

    def finish_worker():
        close_old_connections()
        try:
            try:
                finish_as(counselor.pk, appointment.pk, start=start, end=end)
            except CounselingFinishConflict:
                return "conflict"
            return "finished"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(finish_worker)
        assert lookup_done.wait(timeout=15)
        routine = ensure_for_appointment(
            student=student,
            appointment_id=appointment.pk,
            context=context(student),
        )
        routine_created.set()
        outcome = future.result(timeout=30)

    assert outcome == "conflict"
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert not CounselingEncounter.objects.filter(appointment=appointment).exists()
    assert audit_count("appointment.completed", appointment.pk) == 0
    assert audit_count("counseling.encounter.created") == 0
    assert audit_count("routine_interview.encounter_linked", routine.pk) == 0

    monkeypatch.setattr(
        finish_service_module,
        "lock_routine_for_encounter_recording",
        real_lock,
    )
    retried = finish_as(counselor.pk, appointment.pk, start=start, end=end)
    assert retried.encounter_result == "CREATED"
    assert retried.routine_interview is not None
    assert retried.routine_interview.pk == routine.pk
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == retried.encounter.pk
    assert audit_count("appointment.completed", appointment.pk) == 1
    assert audit_count("routine_interview.encounter_linked", routine.pk) == 1


@pytest.mark.django_db(transaction=True)
def test_routine_first_is_the_supported_order_after_a_finish(monkeypatch):
    patch_email_kick(monkeypatch)
    _, counselor, student, service = setup_student_context("race-safe-order")
    first_appointment = make_appointment(student=student, provider=counselor, service=service)
    start, end = actual_times()
    first = finish_as(counselor.pk, first_appointment.pk, start=start, end=end)
    assert first.encounter_result == "CREATED"
    counts = (
        CounselingEncounter.objects.count(),
        audit_count("appointment.completed", first_appointment.pk),
    )

    with pytest.raises(RoutineInterviewAppointmentInvalid):
        ensure_for_appointment(
            student=student,
            appointment_id=first_appointment.pk,
            context=context(student),
        )
    assert not RoutineInterview.objects.filter(appointment_id=first_appointment.pk).exists()
    assert (
        CounselingEncounter.objects.count(),
        audit_count("appointment.completed", first_appointment.pk),
    ) == counts

    second_appointment = make_appointment(student=student, provider=counselor, service=service)
    routine = ensure_for_appointment(
        student=student,
        appointment_id=second_appointment.pk,
        context=context(student),
    )
    second = finish_as(counselor.pk, second_appointment.pk, start=start, end=end)

    assert second.routine_interview is not None
    assert second.routine_interview.pk == routine.pk
    routine.refresh_from_db()
    assert routine.counseling_encounter_id == second.encounter.pk
    assert CounselingEncounter.objects.filter(appointment=second_appointment).count() == 1
    assert audit_count("appointment.completed", second_appointment.pk) == 1
