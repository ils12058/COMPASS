"""Integrated CONT-4 boundaries; synthetic evidence is never institutional approval."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier, current_thread
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.counseling import continuity_access, handoff_content, handoff_services
from compass.counseling import student_session_summary_content as summary_content
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.handoff_models import CounselorHandoffSummary as Handoff
from compass.counseling.student_session_summaries import (
    publish_assigned_student_session_summary,
    put_assigned_student_session_summary,
)
from compass.notifications.models import EmailDelivery, Notification, PushDelivery
from tests import test_handoff as cases
from tests.test_continuity import client
from tests.test_continuity_access import approved, read
from tests.test_continuity_release_concurrency import run

metadata_case = cases.metadata_case
selected_case = cases.selected_case
workflow_case = cases.workflow_case
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("published", [False, True])
@pytest.mark.parametrize("who", ["receiver", "head", "outsider"])
def test_effective_grant_and_handoff_never_authorize_student_summary(
    workflow_case, monkeypatch, published, who
):
    c = workflow_case
    g = approved(c)
    cases.submitted(c, g)
    summary = put_assigned_student_session_summary(
        encounter_id=c.encounter.pk, counselor=c.author, content="SYNTHETIC STUDENT AUDIENCE"
    )
    if published:
        publish_assigned_student_session_summary(
            encounter_id=c.encounter.pk, counselor=c.author, context=AuditContext.user(c.author)
        )
    assert read(c, g)["evaluation"]
    assert cases.op(c, g, "receive", actor=c.receiver)["content"] == cases.TEXT
    assert (
        client(c.author)
        .get(f"/api/v1/counseling/encounters/{c.encounter.pk}/student-session-summary")
        .status_code
        == 200
    )
    own = client(c.student).get(f"/api/v1/counseling/me/student-session-summaries/{summary.pk}")
    assert own.status_code == (200 if published else 404)
    monkeypatch.setattr(
        summary_content,
        "decrypt_student_session_summary_content",
        lambda *a, **kw: pytest.fail("cross-author Summary decryption"),
    )
    response = client(getattr(c, who)).get(
        f"/api/v1/counseling/encounters/{c.encounter.pk}/student-session-summary"
    )
    assert response.status_code == 404
    assert b"SYNTHETIC STUDENT AUDIENCE" not in response.content


def test_student_summary_publication_never_converts_handoff_audience(workflow_case, monkeypatch):
    c = workflow_case
    g = approved(c)
    cases.submitted(c, g)
    summary = put_assigned_student_session_summary(
        encounter_id=c.encounter.pk, counselor=c.author, content="SYNTHETIC STUDENT AUDIENCE"
    )
    publish_assigned_student_session_summary(
        encounter_id=c.encounter.pk, counselor=c.author, context=AuditContext.user(c.author)
    )
    assert (
        client(c.student)
        .get(f"/api/v1/counseling/me/student-session-summaries/{summary.pk}")
        .status_code
        == 200
    )
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("Student Handoff decrypt"))
    for route in ("author", "submitted", "metadata"):
        response = client(c.student).get(
            f"/api/v1/counseling/continuity-grants/{g['id']}/handoff/{route}",
            {"expected_grant_version": g["version"]},
        )
        assert response.status_code == 403
        assert cases.TEXT.encode() not in response.content


@pytest.mark.parametrize("audit_failure", [False, True])
def test_two_handoff_reads_commit_only_their_own_success_audit(
    workflow_case, monkeypatch, audit_failure
):
    c = workflow_case
    g = approved(c)
    cases.submitted(c, g)
    barrier = Barrier(2)
    original = handoff_services.record_event

    def audit(**kwargs):
        if audit_failure and current_thread().name.startswith("cont4-fail"):
            raise RuntimeError("Synthetic CONT-4 Audit failure")
        return original(**kwargs)

    monkeypatch.setattr(handoff_services, "record_event", audit)

    def action():
        barrier.wait(timeout=5)
        return cases.op(c, g, "receive", actor=c.receiver)

    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="cont4-fail") as first,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="cont4-good") as second,
    ):
        futures = [first.submit(run, action), second.submit(run, action)]
        results = [f.result(timeout=10) for f in futures]
    if audit_failure:
        assert results[0] == ("failure", "Synthetic CONT-4 Audit failure")
    else:
        assert results[0][0] == "ok" and results[0][1]["content"] == cases.TEXT
    assert results[1][0] == "ok" and results[1][1]["content"] == cases.TEXT
    events = AuditEvent.objects.filter(action="counseling.handoff.read")
    assert events.count() == (1 if audit_failure else 2)
    assert set(events.values_list("actor_user_id", flat=True)) == {c.receiver.pk}


def test_valid_second_grant_cannot_accept_first_grant_ciphertext(workflow_case):
    c = workflow_case
    first = approved(c)
    cases.submitted(c, first)
    token = Handoff.objects.get(grant_id=first["id"]).content_ciphertext
    second = approved(
        c,
        request_id=uuid4(),
        starts_at=first["expires_at"],
        expires_at=first["expires_at"] + timedelta(hours=1),
    )
    cases.draft(c, second)
    Handoff.objects.filter(grant_id=second["id"]).update(content_ciphertext=token)
    with pytest.raises(ContinuityError, match="handoff_unavailable"):
        cases.op(c, second, "author_read")
    assert not AuditEvent.objects.filter(
        action="counseling.handoff.read",
        target_id=str(Handoff.objects.get(grant_id=second["id"]).pk),
    ).exists()


def test_source_selected_only_under_another_real_grant_is_denied(workflow_case, monkeypatch):
    c = workflow_case
    first = approved(c)
    second = approved(
        c,
        request_id=uuid4(),
        starts_at=first["expires_at"],
        expires_at=first["expires_at"] + timedelta(hours=1),
        scopes=[s for s in c.payload["scopes"] if s.resource_kind == "ENCOUNTER"],
    )
    monkeypatch.setattr(continuity_access.timezone, "now", lambda: second["starts_at"])
    http = client(c.receiver)
    prefix = f"/api/v1/counseling/continuity-grants/{second['id']}"
    assert (
        http.get(
            prefix + f"/encounters/{c.encounter.pk}/metadata",
            {"expected_version": second["version"]},
        ).status_code
        == 200
    )
    monkeypatch.setattr(
        cases.selected.content, "read_evaluation", lambda *_: pytest.fail("cross-Grant decrypt")
    )
    response = http.get(
        prefix + f"/routine-evaluations/{c.routine.pk}",
        {"expected_version": second["version"]},
    )
    assert response.status_code == 404
    assert b"SYNTHETIC-PROFESSIONAL-CONTENT" not in response.content
    assert not AuditEvent.objects.filter(
        action="counseling.continuity.source_read", metadata__resource_kind="ROUTINE_EVALUATION"
    ).exists()


def test_rotation_corrupt_batch_preserves_evidence_and_resumes(workflow_case, settings):
    c = workflow_case
    first = approved(c)
    cases.submitted(c, first)
    second = approved(
        c,
        request_id=uuid4(),
        starts_at=first["expires_at"],
        expires_at=first["expires_at"] + timedelta(hours=1),
    )
    cases.draft(c, second)
    Handoff.objects.filter(grant_id=second["id"]).update(content_ciphertext="SYNTHETIC-CORRUPT")
    before = {r["id"]: r for r in Handoff.objects.values()}
    models = (AuditEvent, Notification, EmailDelivery, PushDelivery)
    evidence = [list(m.objects.order_by("pk").values()) for m in models]
    old = settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS
    primary = Fernet.generate_key().decode()
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (primary, *old)

    for dry_run in (True, False):
        output = StringIO()
        with pytest.raises(CommandError, match="Unreadable Handoff payloads left unchanged"):
            call_command(
                "rotate_counselor_handoff_summary_encryption",
                dry_run=dry_run,
                batch_size=1,
                stdout=output,
            )
        assert output.getvalue() == (
            f"Handoff encryption: scanned=2; rewrap=1; unreadable=1; dry_run={dry_run}\n"
        )
        after = {r["id"]: r for r in Handoff.objects.values()}
        if dry_run:
            assert after == before
        else:
            for pk, row in after.items():
                expected = before[pk].copy()
                token = expected.pop("content_ciphertext")
                actual = row.copy()
                replacement = actual.pop("content_ciphertext")
                assert actual == expected
                assert (replacement == token) == (token == "SYNTHETIC-CORRUPT")
        assert [list(m.objects.order_by("pk").values()) for m in models] == evidence
        assert primary not in output.getvalue() and cases.TEXT not in output.getvalue()
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (primary,)
    assert cases.op(c, first, "receive", actor=c.receiver)["content"] == cases.TEXT
    output = StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_counselor_handoff_summary_encryption", stdout=output)
    assert output.getvalue() == (
        "Handoff encryption: scanned=2; rewrap=0; unreadable=1; dry_run=False\n"
    )
