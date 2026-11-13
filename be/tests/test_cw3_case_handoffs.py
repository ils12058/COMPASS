"""CW-3b bound snapshots, real prerequisites, audiences, receipt and rollback."""

import io
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling import case_handoff_content as content
from compass.counseling import case_handoff_services as handoffs
from compass.counseling import case_transfer_projections as projections
from compass.counseling import case_transfer_services as transfers
from compass.counseling.case_continuity_rules import CaseContinuityError
from compass.counseling.case_handoff_models import (
    CounselingCaseHandoff,
    CounselingCaseHandoffAddendum,
    CounselingCaseHandoffException,
    CounselingCaseHandoffReceipt,
)
from compass.counseling.case_transfer_models import CounselingCaseTransfer
from compass.counseling.continuity_locks import AUTHORITY_TABLES
from tests.test_appointment_management_scope import auth_client
from tests.test_counseling import context
from tests.test_cw2_next_actions import create as create_task
from tests.test_cw3_transfers import (
    ROOT,
    decide,
    ensure_handoff,
    offer,
    prepare,
    transfer_world,
    values,
    write,
)

pytestmark = pytest.mark.django_db
TEXT = "Synthetic confidential continuation context."
SECTIONS = {
    "context_and_purpose": TEXT,
    "support_and_progress": "Support reviewed.",
    "continuing_considerations": "Review the bounded work plan.",
    "receiver_next_steps": "Review and handle the named actions.",
}


@pytest.fixture
def cw3b(settings):
    # These body-boundary tests do not race authority DML. Hold a fixture fence in the
    # test transaction so background maintenance cannot interrupt setup between its
    # identity writes and the application's NOWAIT fence. Real authority races remain
    # covered by the unchanged transaction/concurrency suites.
    tables = ", ".join(connection.ops.quote_name(name) for name in AUTHORITY_TABLES)
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '5000ms'")
        cursor.execute(f"LOCK TABLE {tables} IN SHARE MODE")
    return transfer_world(settings, "cw3b")


def op(item, actor, action, **kwargs):
    item.refresh_from_db()
    return handoffs.operate(
        actor=actor,
        transfer_id=item.pk,
        operation=action,
        expected_transfer_version=item.version,
        **kwargs,
    )


def submitted(item, actor):
    draft = op(item, actor, "save", sections=SECTIONS)
    result = op(item, actor, "submit", expected_handoff_version=draft["version"])
    item.refresh_from_db()
    return result


def test_new_submission_requires_submitted_handoff_and_draft_does_not_suffice(cw3b):
    w = cw3b
    item = prepare(w)
    before = CounselingCaseTransfer.objects.values().get(pk=item.pk)
    with pytest.raises(CaseContinuityError, match="Submit the structured handoff"):
        transfers.submit_transfer(
            actor=w.a, transfer_id=item.pk, expected_version=item.version, context=context(w.a)
        )
    assert CounselingCaseTransfer.objects.values().get(pk=item.pk) == before
    draft = op(item, w.a, "save", sections=SECTIONS)
    with pytest.raises(CaseContinuityError, match="Submit the structured handoff"):
        transfers.submit_transfer(
            actor=w.a,
            transfer_id=item.pk,
            expected_version=draft["transfer_version"],
            context=context(w.a),
        )
    op(item, w.a, "submit", expected_handoff_version=draft["version"])
    item.refresh_from_db()
    assert transfers.submit_transfer(
        actor=w.a, transfer_id=item.pk, expected_version=item.version, context=context(w.a)
    ).submitted_at


def test_structured_body_is_bound_immutable_and_work_never_contains_task_text(cw3b):
    w = cw3b
    task = create_task(w)
    item = prepare(w)
    body = submitted(item, w.a)
    row = CounselingCaseHandoff.objects.get(pk=body["id"])
    assert TEXT not in row.content_ciphertext
    assert content.read(row)["sections"] == SECTIONS
    assert body["work"]["tasks"][0]["responsible"]["id"] == str(w.b.pk)
    assert "title" not in json.dumps(body["work"]) and "description" not in json.dumps(body["work"])
    assert str(task.pk) in json.dumps(body["work"])
    before = row.content_ciphertext
    with pytest.raises(CaseContinuityError, match="immutable"):
        op(item, w.a, "save", sections=SECTIONS, expected_handoff_version=row.version)
    with pytest.raises(ValueError, match="immutable"):
        row.save()
    assert CounselingCaseHandoff.objects.get(pk=row.pk).content_ciphertext == before


@pytest.mark.parametrize(
    "fault",
    [
        "case_id",
        "transfer_id",
        "student_id",
        "author_id",
        "receiving_counselor_id",
        "plan_digest",
        "ciphertext",
    ],
)
def test_binding_failure_is_content_free_503(cw3b, fault):
    from uuid import uuid4

    item = prepare(cw3b)
    body = submitted(item, cw3b.a)
    row = CounselingCaseHandoff.objects.get(pk=body["id"])
    setattr(
        row,
        fault if fault != "ciphertext" else "content_ciphertext",
        "0" * 64 if fault == "plan_digest" else "broken" if fault == "ciphertext" else uuid4(),
    )
    with pytest.raises(CaseContinuityError) as raised:
        content.read(row)
    assert raised.value.status == 503 and TEXT not in str(raised.value)


@pytest.mark.parametrize("fault", ["bound", "null", "unicode", "section", "empty_required"])
def test_invalid_and_overlong_narrative_never_writes(cw3b, fault):
    sections = dict(SECTIONS)
    if fault == "bound":
        sections["support_and_progress"] = "x" * 12000
    elif fault == "null":
        sections["support_and_progress"] = "\x00"
    elif fault == "unicode":
        sections["support_and_progress"] = "\ud800"
    elif fault == "section":
        sections["invented"] = "additional"
    else:
        sections["context_and_purpose"] = " "
    item = prepare(cw3b)
    if fault == "empty_required":
        body = op(item, cw3b.a, "save", sections=sections)
        with pytest.raises(CaseContinuityError):
            op(item, cw3b.a, "submit", expected_handoff_version=body["version"])
        assert CounselingCaseHandoff.objects.get().state == "DRAFT"
    else:
        with pytest.raises(CaseContinuityError):
            op(item, cw3b.a, "save", sections=sections)
        assert not CounselingCaseHandoff.objects.exists()


def test_author_receiver_head_and_post_transfer_readership_and_receipt(cw3b):
    w = cw3b
    item = prepare(w)
    body = submitted(item, w.a)
    for actor in (w.b, w.head, w.goa, w.student):
        with pytest.raises(CaseContinuityError):
            op(item, actor, "read", handoff_id=body["id"])
    item = transfers.submit_transfer(
        actor=w.a, transfer_id=item.pk, expected_version=item.version, context=context(w.a)
    )
    item = decide(item, w.head, "authorize")
    assert projections.transfer_detail(item, w.head)["can_read_handoff"] is False
    for _ in range(2):
        assert op(item, w.b, "read", handoff_id=body["id"])["sections"] == SECTIONS
    assert (
        CounselingCaseHandoffReceipt.objects.filter(handoff_id=body["id"], reader=w.b).count() == 1
    )
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == w.a.pk
    item = decide(item, w.b, "accept")
    assert op(item, w.b, "read", handoff_id=body["id"])["sections"] == SECTIONS
    w.case.status = "CLOSED"
    w.case.save(update_fields=["status"])
    assert op(item, w.b, "read", handoff_id=body["id"])["sections"] == SECTIONS
    assert op(item, w.a, "read", handoff_id=body["id"])["sections"] == SECTIONS


@pytest.mark.parametrize("ending", ["decline", "cancel", "expiry", "owner", "eligibility"])
def test_receiver_review_body_ends_and_cannot_record_receipt(cw3b, ending):
    w = cw3b
    item = offer(w)
    handoff_id = item.case_handoff_id
    if ending in {"decline", "cancel"}:
        decide(item, w.b if ending == "decline" else w.a, ending, "ARRANGEMENT_NOT_SUITABLE")
    elif ending == "expiry":
        CounselingCaseTransfer.objects.filter(pk=item.pk).update(review_expires_at=timezone.now())
    elif ending == "owner":
        w.case.primary_counselor = w.head
        w.case.save(update_fields=["primary_counselor"])
    else:
        w.b.is_active = False
        w.b.save(update_fields=["is_active"])
    with pytest.raises(CaseContinuityError):
        op(item, w.b, "read", handoff_id=handoff_id)
    assert not CounselingCaseHandoffReceipt.objects.exists()


def test_office_exception_has_head_work_and_is_historical_after_acceptance(cw3b):
    w = cw3b
    item = prepare(w, actor=w.goa)
    queue = auth_client(w.head).get("/api/v1/work").json()["items"]
    assert any(
        row["kind"] == "CASE_HANDOFF_EXCEPTION" and row["source_id"] == str(item.pk)
        for row in queue
    )
    for actor in (w.goa, w.b):
        with pytest.raises(CaseContinuityError):
            op(item, actor, "save", sections=SECTIONS)
        with pytest.raises(CaseContinuityError):
            op(item, actor, "exception", exception_reason="OWNER_UNAVAILABLE")
    op(item, w.head, "exception", exception_reason="OWNER_UNAVAILABLE")
    assert not CounselingCaseHandoff.objects.exists()
    item.refresh_from_db()
    assert projections.transfer_detail(item, w.goa)["can_submit"]
    item = transfers.submit_transfer(
        actor=w.goa, transfer_id=item.pk, expected_version=item.version, context=context(w.goa)
    )
    item = decide(item, w.head, "authorize")
    item = decide(item, w.b, "accept")
    detail = projections.transfer_detail(item, w.b)
    assert detail["handoff_ready"] and detail["handoff"] is None
    assert detail["handoff_exception"]["recorded_by"]["id"] == w.head.pk
    audit = AuditEvent.objects.get(action="counseling.case_handoff.unavailable_recorded")
    assert audit.target_type.endswith("counselingcasehandoffexception")


def test_personal_owner_to_head_exception_is_unavailable_but_explicit_handoff_works(cw3b):
    w = cw3b
    item = prepare(w, receiver=w.head)
    for actor in (w.a, w.head, w.goa):
        with pytest.raises(CaseContinuityError):
            op(item, actor, "exception", exception_reason="INFORMATION_NOT_OBTAINABLE")
    item = ensure_handoff(item, w.a)
    item = transfers.submit_transfer(
        actor=w.a, transfer_id=item.pk, expected_version=item.version, context=context(w.a)
    )
    assert item.authorization_route == "OWNER_TO_HEAD" and not item.independent_authorization
    assert op(item, w.head, "read", handoff_id=item.case_handoff_id)["sections"]
    assert decide(item, w.head, "accept").state == "ACCEPTED"


def test_addenda_preserve_snapshot_reset_pending_review_and_are_attributed(cw3b):
    w = cw3b
    item = offer(w)
    row = item.case_handoff
    before = CounselingCaseHandoff.objects.values().get(pk=row.pk)
    with pytest.raises(CaseContinuityError):
        op(item, w.b, "addendum", handoff_id=row.pk, addendum="Receiver before acceptance")
    result = op(item, w.a, "addendum", handoff_id=row.pk, addendum="Synthetic new information")
    assert result["addenda"][0]["author"]["id"] == w.a.pk
    assert CounselingCaseHandoff.objects.values().get(pk=row.pk) == before
    item.refresh_from_db()
    assert (
        item.state == "PREPARED" and item.authorized_at is None and item.authorized_version is None
    )
    with pytest.raises(CaseContinuityError):
        op(item, w.b, "read", handoff_id=row.pk)
    item = transfers.submit_transfer(
        actor=w.a, transfer_id=item.pk, expected_version=item.version, context=context(w.a)
    )
    item = decide(item, w.head, "authorize")
    item = decide(item, w.b, "accept")
    accepted_version = item.version
    op(item, w.b, "addendum", handoff_id=row.pk, addendum="Accepted owner's dated update")
    current = CounselingCaseTransfer.objects.get(pk=item.pk)
    assert current.state == "ACCEPTED" and current.version == accepted_version + 1
    with pytest.raises(CaseContinuityError) as stale:
        handoffs.operate(
            actor=w.b,
            transfer_id=item.pk,
            operation="addendum",
            expected_transfer_version=accepted_version,
            handoff_id=row.pk,
            addendum="Unconfirmed same-version retry",
        )
    assert stale.value.status == 409
    assert CounselingCaseHandoffAddendum.objects.filter(handoff=row).count() == 2
    addition = CounselingCaseHandoffAddendum.objects.order_by("-created_at").first()
    assert addition.author_id == w.b.pk and "dated update" not in addition.content_ciphertext
    with pytest.raises(ValueError, match="immutable"):
        addition.save()


def test_plan_edits_preserve_old_submitted_snapshot_and_require_a_new_one(cw3b):
    w = cw3b
    item = offer(w)
    original = item.case_handoff_id
    item = transfers.prepare_transfer(
        actor=w.a,
        case_id=w.case.pk,
        transfer_id=item.pk,
        expected_version=item.version,
        values=values(w),
        context=context(w.a),
    )
    assert item.case_handoff_id is None and item.state == "PREPARED"
    assert CounselingCaseHandoff.objects.get(pk=original).state == "SUBMITTED"
    with pytest.raises(CaseContinuityError):
        transfers.submit_transfer(
            actor=w.a, transfer_id=item.pk, expected_version=item.version, context=context(w.a)
        )
    result = submitted(item, w.a)
    assert result["id"] != original


def test_pre_cw3b_submitted_offer_keeps_behavior_without_fabrication(cw3b):
    w = cw3b
    item = prepare(w)
    now = timezone.now()
    CounselingCaseTransfer.objects.filter(pk=item.pk).update(
        handoff_required_at=None,
        submitted_at=now,
        state="AUTHORIZED",
        authorized_by=w.head,
        authorized_at=now,
        authorized_version=item.version,
        authorization_route="INDEPENDENT_HEAD",
        review_expires_at=now + timedelta(days=7),
    )
    item.refresh_from_db()
    assert projections.transfer_detail(item, w.b)["can_accept"]
    assert decide(item, w.b, "accept").state == "ACCEPTED"
    assert (
        not CounselingCaseHandoff.objects.exists()
        and not CounselingCaseHandoffException.objects.exists()
    )


def test_http_private_errors_and_first_form_draft_cannot_be_written_by_office(cw3b):
    w = cw3b
    client = auth_client(w.a)
    response = write(
        client, "post", f"{ROOT}/cases/{w.case.pk}/transfers", values(w, handoff_sections=SECTIONS)
    )
    assert response.status_code == 201, response.content
    assert TEXT not in response.content.decode()
    item = response.json()
    assert item["handoff"]["state"] == "DRAFT"
    for actor in (None, w.head, w.b, w.student):
        client = auth_client(actor) if actor else Client()
        response = client.get(f"{ROOT}/handoffs/{item['handoff']['id']}")
        assert response.status_code in {401, 403, 404}
        assert "no-store" in response["Cache-Control"] and response["Pragma"] == "no-cache"
        assert TEXT not in response.content.decode()
    rejected = write(
        auth_client(w.goa),
        "post",
        f"{ROOT}/cases/{w.case.pk}/transfers",
        values(w, actor=w.goa, handoff_sections=SECTIONS),
    )
    assert rejected.status_code == 403


def test_late_expiry_and_audit_failure_roll_back_receipt_and_body(cw3b):
    w = cw3b
    item = offer(w)
    original_audit = handoffs.audit
    future = item.review_expires_at + timedelta(seconds=1)
    with patch.object(handoffs, "audit", side_effect=RuntimeError("synthetic audit failure")):
        with pytest.raises(RuntimeError):
            op(item, w.b, "read", handoff_id=item.case_handoff_id)
    assert not CounselingCaseHandoffReceipt.objects.exists()
    with patch.object(handoffs.timezone, "now", return_value=timezone.now()) as clock:

        def advance(*args, **kwargs):
            original_audit(*args, **kwargs)
            clock.return_value = future

        with patch.object(handoffs, "audit", side_effect=advance):
            with pytest.raises(CaseContinuityError):
                op(item, w.b, "read", handoff_id=item.case_handoff_id)
    assert not CounselingCaseHandoffReceipt.objects.exists()


def test_existing_rotation_covers_case_snapshots_and_addenda_without_business_changes(
    cw3b, settings
):
    w = cw3b
    item = offer(w)
    op(
        item,
        w.a,
        "addendum",
        handoff_id=item.case_handoff_id,
        addendum="Synthetic key custody update",
    )
    before = list(CounselingCaseHandoff.objects.values())
    additions_before = list(CounselingCaseHandoffAddendum.objects.values())
    audit_before = AuditEvent.objects.count()
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (
        Fernet.generate_key().decode(),
        *settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS,
    )
    output = io.StringIO()
    call_command("rotate_counselor_handoff_summary_encryption", dry_run=True, stdout=output)
    assert list(CounselingCaseHandoff.objects.values()) == before
    call_command("rotate_counselor_handoff_summary_encryption", batch_size=1, stdout=output)
    for previous, current in zip(
        before + additions_before,
        list(CounselingCaseHandoff.objects.values())
        + list(CounselingCaseHandoffAddendum.objects.values()),
        strict=True,
    ):
        assert previous.pop("content_ciphertext") != current.pop("content_ciphertext")
        assert previous == current
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (
        settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS[:1]
    )
    assert op(item, w.a, "read", handoff_id=item.case_handoff_id)["addenda"]
    assert AuditEvent.objects.count() == audit_before + 1
    assert TEXT not in output.getvalue()


@pytest.mark.parametrize("fault", ["revoked", "expired", "digest", "wrong_user"])
def test_live_session_is_rechecked_before_receipt(cw3b, fault):
    w = cw3b
    item = offer(w)
    now = timezone.now()
    issued = create_auth_session(
        w.b,
        now=now - timedelta(days=1) if fault == "expired" else now,
        mfa_verified_at=now,
    )
    session = issued.session
    digest = session.token_digest
    if fault == "revoked":
        session.revoked_at = timezone.now()
    elif fault == "expired":
        session.expires_at = now - timedelta(seconds=1)
    elif fault == "digest":
        digest = "incorrect"
    else:
        session.user = w.a
    session.save()
    with pytest.raises(CaseContinuityError) as raised:
        handoffs.operate(
            actor=w.b,
            transfer_id=item.pk,
            handoff_id=item.case_handoff_id,
            operation="read",
            actor_session_id=session.pk,
            actor_session_digest=digest,
        )
    assert raised.value.status == 401 and not CounselingCaseHandoffReceipt.objects.exists()


def test_addendum_binding_and_aggregate_limit_are_enforced(cw3b):
    w = cw3b
    item = prepare(w)
    sections = dict(
        SECTIONS,
        context_and_purpose="c",
        receiver_next_steps="n",
        support_and_progress="x" * 11998,
        continuing_considerations="",
    )
    body = op(item, w.a, "save", sections=sections)
    body = op(item, w.a, "submit", expected_handoff_version=body["version"])
    op(item, w.a, "addendum", handoff_id=body["id"], addendum="Attributable update")
    addition = CounselingCaseHandoffAddendum.objects.get()
    addition.author_id = w.b.pk
    with pytest.raises(CaseContinuityError) as raised:
        content.read_addendum(addition)
    assert raised.value.status == 503
    for value in [" ", "x" * 12001]:
        with pytest.raises(CaseContinuityError):
            op(item, w.a, "addendum", handoff_id=body["id"], addendum=value)
    assert CounselingCaseHandoffAddendum.objects.count() == 1


def test_addendum_pages_are_bounded_and_handoff_audit_is_content_free(cw3b):
    w = cw3b
    item = decide(offer(w), w.b, "accept")
    for index in range(21):
        addition = CounselingCaseHandoffAddendum(handoff=item.case_handoff, author=w.b)
        addition.content_ciphertext = content.encrypt_addendum(
            addition, f"Synthetic update {index}"
        )
        addition.save(force_insert=True)
    first = op(item, w.b, "read", handoff_id=item.case_handoff_id, addenda_page=1)
    second = op(item, w.b, "read", handoff_id=item.case_handoff_id, addenda_page=2)
    assert len(first["addenda"]) == 20 and first["addenda_has_next"]
    assert len(second["addenda"]) == 1 and not second["addenda_has_next"]
    assert first["addenda"][0]["id"] != second["addenda"][0]["id"]
    metadata = json.dumps(
        list(
            AuditEvent.objects.filter(action__startswith="counseling.case_handoff.").values_list(
                "metadata", flat=True
            )
        )
    )
    assert "Synthetic update" not in metadata and "Continuing student support" not in metadata
    assert w.student.get_full_name() not in metadata


def test_case_handoff_contract_is_separate_from_legacy_and_work_is_read_only():
    from pathlib import Path

    contract = json.loads(
        (Path(__file__).resolve().parents[2] / "contracts/openapi.json").read_text()
    )
    schemas = contract["components"]["schemas"]
    assert schemas["CaseHandoffSaveRequest"]["additionalProperties"] is False
    assert set(schemas["CaseHandoffSaveRequest"]["properties"]) == {
        "sections",
        "expected_transfer_version",
        "expected_handoff_version",
    }
    assert schemas["CaseHandoffWork"]["additionalProperties"] is False
    assert set(schemas["CaseHandoffWork"]["properties"]) == {"tasks", "appointments"}
    for path, methods in contract["paths"].items():
        for operation in methods.values():
            if not isinstance(operation, dict) or operation.get("operationId") not in {
                "counselingSaveCaseHandoff",
                "counselingSubmitCaseHandoff",
                "counselingGetCaseHandoff",
                "counselingAddCaseHandoffAddendum",
                "counselingRecordCaseHandoffUnavailable",
            }:
                continue
            assert path.startswith(ROOT + "/") and "continuity-grants" not in path
            assert operation["security"] == [{"OpaqueSessionAuth": []}]
            assert not any(param["name"] == "response" for param in operation.get("parameters", []))
