from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.demo_seed.cast import RECENT_GRADUATE
from compass.demo_seed.history import seed_exit_interview
from compass.demo_seed.narratives import RECENT_GRADUATE_EXIT_INTERVIEW
from compass.demo_seed.support import SeedSession
from compass.demo_seed.timeline import DemoTimeline
from compass.exit_interviews.models import ExitInterview, ExitInterviewOpportunity
from compass.exit_interviews.opportunities import open_opportunity, revoke_opportunity
from compass.exit_interviews.services import (
    ExitInterviewOpportunityConflict,
    ExitInterviewOpportunityNotOpen,
    ensure_my_current,
    reopen_for_correction,
    submit_mine,
)
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import GoodMoralExitInterviewRequired
from tests.test_exit_interviews import (
    auth_client,
    csrf,
    ensure_api,
    make_head,
    make_inventory,
    make_user,
    make_year,
    put_api,
    submit_api,
    sync_policy,
    valid_payload,
)
from tests.test_good_moral import create_my_current_student, make_affiliation


def setup_student():
    sync_policy()
    student = make_user("opportunity-student@example.edu")
    head = make_head("opportunity-head@example.edu")
    year = make_year()
    inventory = make_inventory(student, year, admit=False)
    return student, head, year, inventory


def open_for(student, head, year, source="GRADUATION", note=""):
    return open_opportunity(
        actor=head,
        student_id=student.pk,
        academic_year_id=year.pk,
        source=source,
        note=note,
        context=AuditContext.user(head),
    )


def request_f4(student, **kwargs):
    return create_my_current_student(
        student=student,
        year_level="Fourth",
        semester="First",
        context=AuditContext.user(student),
        **kwargs,
    )


def prepare_response(student):
    client = auth_client(student)
    ensured = ensure_api(client)
    assert ensured.status_code == 200
    assert put_api(client, valid_payload()).status_code == 200
    return client, ExitInterview.objects.get(pk=ensured.json()["id"])


@pytest.mark.django_db
def test_no_opportunity_blocks_admission_and_status_is_unambiguous():
    student, _, _, _ = setup_student()
    client = auth_client(student)
    response = ensure_api(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "exit_interview_opportunity_required"
    status = client.get("/api/v1/exit-interviews/me/status")
    assert status.status_code == 200
    assert status.json()["opportunity"] is None
    assert status.json()["current_record"] is None
    assert status.json()["can_start"] is False
    assert status.json()["has_records"] is False
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["exit_interview_workspace_available"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("source", ["MANUAL", "GRADUATION"])
def test_explicit_opening_admits_and_successful_submission_completes_once(source):
    student, head, year, _ = setup_student()
    opportunity = open_for(student, head, year, source, note="Private operational note")
    client = auth_client(student)
    status = client.get("/api/v1/exit-interviews/me/status").json()
    assert status["can_start"] is True
    assert status["opportunity"]["source"] == source
    assert "Private operational note" not in json.dumps(status)
    assert status["graduation_good_moral_blocked"] is (source == "GRADUATION")
    assert client.get("/api/v1/auth/session").json()["user"]["exit_interview_workspace_available"]
    client, item = prepare_response(student)
    assert item.opportunity_id == opportunity.pk
    assert submit_api(client).status_code == 200
    assert submit_api(client).status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.status == "COMPLETED"
    assert opportunity.completed_at is not None
    status = client.get("/api/v1/exit-interviews/me/status").json()
    assert status["can_start"] is False
    assert status["graduation_good_moral_blocked"] is False
    assert status["current_record"]["status"] == "SUBMITTED"
    assert (
        AuditEvent.objects.filter(
            action="exit_interview.opportunity_completed", target_id=opportunity.pk
        ).count()
        == 1
    )
    assert ensure_api(client).json()["id"] == str(item.pk)


@pytest.mark.django_db
def test_opportunity_for_another_year_does_not_admit_or_gate_f4():
    student, head, _, _ = setup_student()
    prior = make_year("2098-2099", current=False)
    open_for(student, head, prior)
    assert (
        ensure_api(auth_client(student)).json()["error"]["code"]
        == "exit_interview_opportunity_required"
    )
    make_affiliation(student)
    assert request_f4(student).graduation_opportunity_id is None


@pytest.mark.django_db
def test_duplicate_and_changed_source_conflict_and_database_uniqueness():
    student, head, year, _ = setup_student()
    first = open_for(student, head, year)
    assert open_for(student, head, year).pk == first.pk
    with pytest.raises(ExitInterviewOpportunityConflict):
        open_for(student, head, year, "MANUAL")
    with pytest.raises(IntegrityError), transaction.atomic():
        ExitInterviewOpportunity.objects.create(
            student=student,
            academic_year=year,
            source="MANUAL",
            opened_by=head,
            opened_at=timezone.now(),
        )
    assert AuditEvent.objects.filter(action="exit_interview.opportunity_opened").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]
)
def test_unauthorized_actor_cannot_operate_or_discover_opportunities(role):
    student, head, year, _ = setup_student()
    opportunity = open_for(student, head, year)
    actor = make_user("unauthorized@example.edu", role=role)
    client = auth_client(actor)
    for path in [
        "/api/v1/exit-interviews/opportunities",
        "/api/v1/exit-interviews/opportunities/students",
        f"/api/v1/exit-interviews/opportunities/{opportunity.pk}",
    ]:
        assert client.get(path).status_code == 403
    response = client.post(
        "/api/v1/exit-interviews/opportunities",
        data=json.dumps({"student_id": str(student.pk), "source": "GRADUATION"}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 403
    assert (
        client.post(
            f"/api/v1/exit-interviews/opportunities/{opportunity.pk}/revoke", **csrf(client)
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_operational_api_supports_search_open_inspect_revoke_and_privacy_minimized_audit():
    student, head, year, _ = setup_student()
    client = auth_client(head)
    options = client.get("/api/v1/exit-interviews/opportunities/students", {"search": "Exit"})
    assert options.status_code == 200
    assert [row["id"] for row in options.json()["items"]] == [str(student.pk)]
    payload = {
        "student_id": str(student.pk),
        "source": "GRADUATION",
        "note": "Sensitive operation note",
    }
    response = client.post(
        "/api/v1/exit-interviews/opportunities",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 200
    item = response.json()
    assert item["academic_year"]["id"] == str(year.pk)
    assert (
        client.get(f"/api/v1/exit-interviews/opportunities/{item['id']}").json()["note"]
        == payload["note"]
    )
    listing = client.get(
        "/api/v1/exit-interviews/opportunities",
        {"student_id": str(student.pk), "academic_year_id": str(year.pk), "status": "OPEN"},
    )
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()["items"]] == [item["id"]]
    assert listing.json()["current_academic_year"]["id"] == str(year.pk)
    prior = make_year("2098-2099", current=False)
    open_for(student, head, prior, "MANUAL")
    current_only = client.get("/api/v1/exit-interviews/opportunities", {"current_year_only": True})
    assert [row["id"] for row in current_only.json()["items"]] == [item["id"]]
    assert (
        client.post(
            f"/api/v1/exit-interviews/opportunities/{item['id']}/revoke", **csrf(client)
        ).json()["status"]
        == "REVOKED"
    )
    assert (
        ensure_api(auth_client(student)).json()["error"]["code"]
        == "exit_interview_opportunity_not_open"
    )
    metadata = list(
        AuditEvent.objects.filter(target_id=item["id"]).values_list("metadata", flat=True)
    )
    assert len(metadata) == 2
    assert payload["note"] not in json.dumps(metadata)
    assert all(row["academic_year_id"] == str(year.pk) for row in metadata)


@pytest.mark.django_db
def test_revocation_preserves_draft_but_blocks_new_work_until_explicit_reopening():
    student, head, year, _ = setup_student()
    opportunity = open_for(student, head, year)
    client, item = prepare_response(student)
    revoke_opportunity(actor=head, opportunity_id=opportunity.pk, context=AuditContext.user(head))
    assert client.get(f"/api/v1/exit-interviews/me/{item.pk}").json()["can_edit"] is False
    assert (
        put_api(client, valid_payload()).json()["error"]["code"]
        == "exit_interview_opportunity_not_open"
    )
    assert submit_api(client).json()["error"]["code"] == "exit_interview_opportunity_not_open"
    assert (
        client.put(
            f"/api/v1/exit-interviews/me/{item.pk}",
            data=json.dumps(valid_payload()),
            content_type="application/json",
            **csrf(client),
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/v1/exit-interviews/me/{item.pk}/submit", **csrf(client)).status_code
        == 409
    )
    assert ExitInterview.objects.filter(pk=item.pk).exists()
    assert open_for(student, head, year).pk == opportunity.pk
    assert put_api(client, valid_payload()).status_code == 200
    assert submit_api(client).status_code == 200


@pytest.mark.django_db
def test_legacy_draft_without_opportunity_remains_editable_submittable_and_historical():
    student, _, year, inventory = setup_student()
    item = ExitInterview.objects.create(student=student, academic_year=year, inventory=inventory)
    client = auth_client(student)
    assert ensure_api(client).json()["id"] == str(item.pk)
    assert put_api(client, valid_payload()).status_code == 200
    assert submit_api(client).status_code == 200
    for lifecycle in [StudentLifecycleStatus.GRADUATED, StudentLifecycleStatus.FORMER]:
        student.student_lifecycle_status = lifecycle
        student.save(update_fields=["student_lifecycle_status", "updated_at"])
        assert client.get(f"/api/v1/exit-interviews/me/{item.pk}").status_code == 200
        assert client.get("/api/v1/exit-interviews/me/status").json()["has_records"] is True
        assert client.get("/api/v1/auth/session").json()["user"][
            "exit_interview_workspace_available"
        ]
    assert not ExitInterviewOpportunity.objects.exists()


@pytest.mark.django_db
def test_completed_opportunity_allows_controlled_reopen_edit_resubmit_and_blocks_f4_while_draft():
    student, head, year, _ = setup_student()
    opportunity = open_for(student, head, year)
    make_affiliation(student)
    client, item = prepare_response(student)
    assert submit_api(client).status_code == 200
    initial = request_f4(student)
    assert initial.graduation_opportunity_id == opportunity.pk
    assert initial.exit_interview_id == item.pk
    initial_time = initial.exit_interview_submitted_at
    reopen_for_correction(
        actor=head, exit_interview_id=item.pk, reason="Correction", context=AuditContext.user(head)
    )
    assert client.get("/api/v1/exit-interviews/me/status").json()["can_edit_current"] is True
    with pytest.raises(GoodMoralExitInterviewRequired):
        request_f4(student)
    assert put_api(client, valid_payload()).status_code == 200
    assert submit_api(client).status_code == 200
    second = request_f4(student)
    assert second.exit_interview_submitted_at > initial_time
    initial.refresh_from_db()
    assert initial.exit_interview_submitted_at == initial_time
    assert ExitInterviewOpportunity.objects.count() == 1
    with pytest.raises(ExitInterviewOpportunityConflict):
        revoke_opportunity(
            actor=head, opportunity_id=opportunity.pk, context=AuditContext.user(head)
        )


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["NOT_STARTED", "DRAFT", "WRONG_YEAR_SUBMITTED"])
def test_graduation_f4_requires_matching_submitted_response_with_controlled_api_error(state):
    student, head, year, inventory = setup_student()
    open_for(student, head, year)
    make_affiliation(student)
    if state == "DRAFT":
        prepare_response(student)
    elif state == "WRONG_YEAR_SUBMITTED":
        prior = make_year("2098-2099", current=False)
        prior_inventory = make_inventory(student, prior, admit=False)
        ExitInterview.objects.create(
            student=student,
            academic_year=prior,
            inventory=prior_inventory,
            status="SUBMITTED",
            first_submitted_at=timezone.now(),
            last_submitted_at=timezone.now(),
        )
    client = auth_client(student)
    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "Fourth", "semester": "First"}),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="opportunity-f4",
        **csrf(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "good_moral_exit_interview_required"
    assert not GoodMoralRequest.objects.exists()
    assert inventory.submitted_at is not None


@pytest.mark.django_db
@pytest.mark.parametrize("source", ["NONE", "MANUAL"])
def test_ordinary_and_manual_do_not_gate_f4(source):
    student, head, year, _ = setup_student()
    make_affiliation(student)
    if source != "NONE":
        open_for(student, head, year, "MANUAL")
    assert request_f4(student).graduation_opportunity_id is None


@pytest.mark.django_db
def test_revocation_does_not_reclassify_a_graduation_workflow_as_ordinary_f4():
    student, head, year, _ = setup_student()
    make_affiliation(student)
    opportunity = open_for(student, head, year)
    revoke_opportunity(actor=head, opportunity_id=opportunity.pk, context=AuditContext.user(head))
    with pytest.raises(GoodMoralExitInterviewRequired):
        request_f4(student)
    assert (
        auth_client(student)
        .get("/api/v1/exit-interviews/me/status")
        .json()["graduation_good_moral_blocked"]
        is True
    )


@pytest.mark.django_db
def test_graduation_creation_replay_survives_reopen_but_new_creation_intent_is_blocked():
    student, head, year, _ = setup_student()
    open_for(student, head, year)
    make_affiliation(student)
    client, item = prepare_response(student)
    assert submit_api(client).status_code == 200
    first = request_f4(student, idempotency_key="graduation-exact-replay")
    reopen_for_correction(
        actor=head, exit_interview_id=item.pk, reason="Correction", context=AuditContext.user(head)
    )
    assert request_f4(student, idempotency_key="graduation-exact-replay").pk == first.pk
    with pytest.raises(GoodMoralExitInterviewRequired):
        request_f4(student, idempotency_key="new-graduation-request")


@pytest.mark.django_db
def test_opportunity_management_depends_on_identity_access_without_granting_response_access():
    from compass.accounts.policy import resolve_capability_dependencies

    assert resolve_capability_dependencies({"exit_interviews.manage_opportunities"}) == frozenset()
    assert resolve_capability_dependencies(
        {"accounts.view", "exit_interviews.manage_opportunities"}
    ) == {"accounts.view", "exit_interviews.manage_opportunities"}


def in_thread(callback):
    close_old_connections()
    try:
        return callback()
    finally:
        close_old_connections()


@pytest.mark.django_db
def test_demo_exit_interview_explicitly_opens_manual_access_and_preserves_timeline():
    student, head, year, _ = setup_student()
    submitted = timezone.now() - timedelta(days=1)
    started = submitted - timedelta(days=2)
    session = SeedSession(
        timeline=DemoTimeline(anchor=submitted.date(), zone=ZoneInfo("Asia/Manila")),
        app_env="local-staging",
        users={RECENT_GRADUATE.key: student, "head_guidance": head},
    )
    seed_exit_interview(
        session,
        RECENT_GRADUATE,
        started=started,
        saved=submitted - timedelta(hours=1),
        submitted=submitted,
        narrative=RECENT_GRADUATE_EXIT_INTERVIEW,
    )
    opportunity = ExitInterviewOpportunity.objects.get(student=student, academic_year=year)
    assert opportunity.source == "MANUAL"
    assert opportunity.status == "COMPLETED"
    assert opportunity.opened_at == started
    assert opportunity.completed_at == submitted
    assert opportunity.updated_at == submitted
    assert opportunity.exit_interview.last_submitted_at == submitted
    assert session.created["Exit Interviews"] == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_openings_create_one_opportunity_and_one_audit():
    student, head, year, _ = setup_student()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(lambda _: in_thread(lambda: open_for(student, head, year).pk), range(2))
        )
    assert ids[0] == ids[1]
    assert ExitInterviewOpportunity.objects.count() == 1
    assert AuditEvent.objects.filter(action="exit_interview.opportunity_opened").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_start_and_revocation_leave_a_safe_noneditable_workflow():
    student, head, year, _ = setup_student()
    opportunity = open_for(student, head, year)

    def start():
        try:
            return ensure_my_current(student=student, context=AuditContext.user(student)).pk
        except ExitInterviewOpportunityNotOpen:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        started = pool.submit(in_thread, start)
        revoked = pool.submit(
            in_thread,
            lambda: revoke_opportunity(
                actor=head, opportunity_id=opportunity.pk, context=AuditContext.user(head)
            ),
        )
        started.result(timeout=15)
        revoked.result(timeout=15)
    opportunity.refresh_from_db()
    assert opportunity.status == "REVOKED"
    if ExitInterview.objects.filter(student=student).exists():
        item = ExitInterview.objects.get(student=student)
        with pytest.raises(ExitInterviewOpportunityNotOpen):
            submit_mine(
                student=student, exit_interview_id=item.pk, context=AuditContext.user(student)
            )


@pytest.mark.django_db(transaction=True)
def test_concurrent_submission_and_revocation_are_serialized():
    student, head, year, _ = setup_student()
    opportunity = open_for(student, head, year)
    _, item = prepare_response(student)

    def submit():
        try:
            return submit_mine(
                student=student, exit_interview_id=item.pk, context=AuditContext.user(student)
            ).status
        except ExitInterviewOpportunityNotOpen:
            return "BLOCKED"

    def revoke():
        try:
            return revoke_opportunity(
                actor=head, opportunity_id=opportunity.pk, context=AuditContext.user(head)
            ).status
        except ExitInterviewOpportunityConflict:
            return "BLOCKED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        submission = pool.submit(in_thread, submit)
        revocation = pool.submit(in_thread, revoke)
        results = (submission.result(timeout=15), revocation.result(timeout=15))
    assert results in [("SUBMITTED", "BLOCKED"), ("BLOCKED", "REVOKED")]


@pytest.mark.django_db(transaction=True)
def test_concurrent_f4_creation_and_reopen_preserve_checked_submission_provenance(monkeypatch):
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    student, head, year, _ = setup_student()
    open_for(student, head, year)
    make_affiliation(student)
    client, item = prepare_response(student)
    assert submit_api(client).status_code == 200

    def create():
        try:
            return request_f4(student)
        except GoodMoralExitInterviewRequired:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        creation = pool.submit(in_thread, create)
        reopening = pool.submit(
            in_thread,
            lambda: reopen_for_correction(
                actor=head,
                exit_interview_id=item.pk,
                reason="Concurrent correction",
                context=AuditContext.user(head),
            ),
        )
        request = creation.result(timeout=15)
        reopening.result(timeout=15)
    item.refresh_from_db()
    assert item.status == "DRAFT"
    if request:
        assert request.exit_interview_id == item.pk
        assert request.exit_interview_submitted_at == item.last_submitted_at
    else:
        assert not GoodMoralRequest.objects.exists()
