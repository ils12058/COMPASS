"""Synthetic workflow policies only; real PostgreSQL, no deployed approval or keys."""

import json
from dataclasses import replace
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from compass.accounts.models import Role, UserCapabilityOverride
from compass.accounts.services import set_user_capability_override
from compass.audit.models import AuditEvent
from compass.confidential_data import crypto
from compass.counseling import (
    coverage_policy,
    coverage_selection,
    handoff_content,
    handoff_services,
)
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.coverage_policy import ApprovedCoverageWorkflowPolicy, ApprovedOfficeCase
from compass.counseling.handoff_models import CounselorHandoffSummary as Handoff
from tests import test_continuity_access as selected
from tests.test_continuity import client, decide, request

metadata_case = selected.metadata_case
selected_case = selected.selected_case
pytestmark = pytest.mark.django_db(transaction=True)
TEXT = "  Confidential synthetic handoff — 你好\nExact second line  \n"


@pytest.fixture
def workflow_case(selected_case, monkeypatch):
    c = selected_case
    c.workflow = ApprovedCoverageWorkflowPolicy(
        version="TEST-WORKFLOW-V1",
        evidence_reference="TEST-D11",
        selection_evidence="TEST-D05",
        handoff_basis_evidence="TEST-D08",
        retention_evidence="TEST-D14",
        author_qualification_evidence="TEST-D11-AUTHOR",
        client_safety_evidence="TEST-D18",
        valid_from=c.policy.valid_from,
        valid_until=c.policy.valid_until,
        college_ids=c.policy.college_ids,
        office_cases=(ApprovedOfficeCase(c.head.pk, c.student.pk, c.author.pk),),
        source_kinds=frozenset({"ENCOUNTER", "ROUTINE_EVALUATION"}),
    )
    c.control.operational = replace(
        c.policy,
        workflow_policy_digest=c.workflow.digest,
        office_requester_ids=frozenset({c.head.pk}),
    )
    c.policy = c.control.operational
    c.workflow_control = [c.workflow]
    monkeypatch.setattr(
        coverage_policy, "get_approved_workflow_policy", lambda: c.workflow_control[0]
    )
    for u in [c.author, c.receiver, c.head, c.outsider, c.student]:
        for code in ["counseling.handoff.manage_own", "counseling.handoff.read_received"]:
            set_user_capability_override(
                user=u, capability=code, effect="GRANT", reason="SYNTHETIC ONLY"
            )
    return c


def op(c, g, operation, actor=None, **kw):
    return handoff_services.operate(
        actor=actor or c.author,
        grant_id=g["id"],
        operation=operation,
        expected_grant_version=g["version"],
        **kw,
    )


def draft(c, g, body=TEXT):
    return op(c, g, "save", expected_version=0, body=body)


def submitted(c, g):
    d = draft(c, g)
    return op(c, g, "submit", expected_version=d["version"])


def test_planned_draft_submit_independent_approval_receiver_and_immutable(workflow_case):
    c = workflow_case
    g = request(c)
    d = draft(c, g)
    row = Handoff.objects.get()
    assert TEXT not in row.content_ciphertext
    assert op(c, g, "author_read")["content"] == TEXT
    assert op(c, g, "metadata", actor=c.head)["handoff"] is None
    assert op(c, g, "metadata", actor=c.receiver)["handoff"] is None
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)
    d = op(c, g, "save", body=TEXT + "updated", expected_version=d["version"])
    s = op(c, g, "submit", expected_version=d["version"])
    assert op(c, g, "submit", expected_version=d["version"]) == s
    with pytest.raises(ContinuityError, match="handoff_submitted"):
        op(c, g, "save", body="replace", expected_version=s["version"])
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)
    g = decide(c, g)
    assert op(c, g, "receive", actor=c.receiver)["content"] == TEXT + "updated"
    assert op(c, g, "metadata", actor=c.head)["handoff"]["state"] == "SUBMITTED"
    assert Handoff.objects.get().author_id == c.author.pk
    assert AuditEvent.objects.filter(action="counseling.handoff.submitted").count() == 1
    assert TEXT not in json.dumps(list(AuditEvent.objects.values("metadata")), default=str)


@pytest.mark.parametrize("who", ["head", "outsider", "student"])
@pytest.mark.parametrize("operation", ["save", "submit", "author_read", "receive"])
def test_denied_relationship_never_decrypts(workflow_case, monkeypatch, who, operation):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)

    def forbidden(*a, **k):
        raise AssertionError("unauthorized decrypt")

    monkeypatch.setattr(handoff_content, "read", forbidden)
    with pytest.raises(ContinuityError):
        op(c, g, operation, actor=getattr(c, who), expected_version=1, body="new")


@pytest.mark.parametrize(
    "role", ["IT_ADMIN", "GUIDANCE_SERVICES_STAFF", "STUDENT", "INSTITUTIONAL_OFFICER"]
)
def test_unsupported_role_even_with_overrides(workflow_case, role, monkeypatch):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    c.receiver.role = Role.objects.get(code=role)
    c.receiver.save(update_fields=["role"])
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("decrypt"))
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)


@pytest.mark.parametrize(
    "change",
    [
        "inactive",
        "capability",
        "expired_capability",
        "role",
        "student",
        "affiliation",
        "policy",
        "workflow",
        "manifest",
        "revoked",
        "expired",
        "scheduled",
        "version",
        "draft",
    ],
)
def test_receiver_invalidations_before_decrypt(workflow_case, monkeypatch, change):
    c = workflow_case
    g = selected.approved(c)
    if change == "draft":
        draft(c, g)
    else:
        submitted(c, g)
    if change == "inactive":
        c.receiver.is_active = False
        c.receiver.save(update_fields=["is_active"])
    elif change == "capability":
        set_user_capability_override(
            user=c.receiver,
            capability="counseling.handoff.read_received",
            effect="REVOKE",
            reason="TEST",
        )
    elif change == "expired_capability":
        UserCapabilityOverride.objects.filter(
            user=c.receiver, capability__code="counseling.handoff.read_received"
        ).update(expires_at=c.now - timedelta(seconds=1))
    elif change == "role":
        c.receiver.role = Role.objects.get(code="IT_ADMIN")
        c.receiver.save(update_fields=["role"])
    elif change == "student":
        c.student.is_active = False
        c.student.save(update_fields=["is_active"])
    elif change == "affiliation":
        selected.StudentAffiliation.objects.filter(student=c.student).update(college=c.college_b)
    elif change == "policy":
        c.control.operational = None
    elif change == "workflow":
        c.workflow_control[0] = None
    elif change == "manifest":
        c.workflow_control[0] = replace(c.workflow, evidence_reference="CHANGED")
    elif change == "revoked":
        decide(c, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
    elif change == "expired":
        monkeypatch.setattr(handoff_services.timezone, "now", lambda: g["expires_at"])
    elif change == "scheduled":
        monkeypatch.setattr(
            handoff_services.timezone, "now", lambda: g["starts_at"] - timedelta(microseconds=1)
        )
    elif change == "version":
        g = g | {"version": g["version"] - 1}
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("decrypt"))
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)


@pytest.mark.parametrize("operation", ["save", "submit", "author_read", "receive"])
def test_audit_failure_rolls_back_body_and_state(workflow_case, monkeypatch, operation):
    c = workflow_case
    g = selected.approved(c)
    if operation != "save":
        draft(c, g)
    if operation == "receive":
        op(c, g, "submit", expected_version=1)
    before = list(Handoff.objects.values())
    count = AuditEvent.objects.count()

    def fail(**kw):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(handoff_services, "record_event", fail)
    with pytest.raises(RuntimeError):
        op(
            c,
            g,
            operation,
            actor=c.receiver if operation == "receive" else c.author,
            expected_version=0 if operation == "save" else 1,
            body=TEXT,
        )
    assert list(Handoff.objects.values()) == before
    assert AuditEvent.objects.count() == count


@pytest.mark.parametrize("operation", ["author_read", "receive", "submit"])
def test_post_audit_expiry_releases_nothing(workflow_case, monkeypatch, operation):
    c = workflow_case
    g = selected.approved(c)
    draft(c, g)
    if operation == "receive":
        op(c, g, "submit", expected_version=1)
    real = handoff_services.record_event
    now = [c.now]
    monkeypatch.setattr(handoff_services.timezone, "now", lambda: now[0])

    def audit(**kw):
        real(**kw)
        now[0] = g["expires_at"]

    monkeypatch.setattr(handoff_services, "record_event", audit)
    count = AuditEvent.objects.count()
    with pytest.raises(ContinuityError):
        op(
            c,
            g,
            operation,
            actor=c.receiver if operation == "receive" else c.author,
            expected_version=1,
        )
    assert AuditEvent.objects.count() == count
    if operation == "submit":
        assert Handoff.objects.get().state == "DRAFT"


def test_unplanned_absence_no_author_login_or_handoff_and_narrow_selection(
    workflow_case, monkeypatch
):
    c = workflow_case
    c.author.is_active = False
    c.author.save(update_fields=["is_active"])
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("selection decrypt"))
    page = coverage_selection.select(
        actor=c.head, student_id=c.student.pk, original_counselor_id=c.author.pk
    )
    assert {i["source_id"] for i in page["items"]} == {c.encounter.pk, c.routine.pk}
    g = request(
        c, actor=c.head, coverage_kind="TEMPORARY_COVERAGE", reason_category="UNEXPECTED_ABSENCE"
    )
    with pytest.raises(ContinuityError, match="self_approval"):
        decide(c, g)
    c.control.operational = replace(c.policy, approver_ids=frozenset({c.head.pk, c.outsider.pk}))
    selected.UserDesignation.objects.create(
        user=c.outsider,
        designation=selected.Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    # A changed approval policy requires a new request, never rebind an old sealed grant.
    with pytest.raises(ContinuityError, match="policy"):
        decide(c, g, actor=c.outsider)
    assert not Handoff.objects.exists()


def test_unplanned_with_independent_authorized_backup(workflow_case):
    c = workflow_case
    c.control.operational = replace(
        c.policy,
        office_requester_ids=frozenset({c.head.pk}),
        approver_ids=frozenset({c.head.pk, c.outsider.pk}),
    )
    selected.UserDesignation.objects.create(
        user=c.outsider,
        designation=selected.Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    c.author.is_active = False
    c.author.save(update_fields=["is_active"])
    g = request(
        c, actor=c.head, coverage_kind="TEMPORARY_COVERAGE", reason_category="UNEXPECTED_ABSENCE"
    )
    g = decide(c, g, actor=c.outsider)
    assert selected.read(c, g)["evaluation"]["recommendations"] == selected.SENTINEL
    assert op(c, g, "metadata", actor=c.receiver)["handoff"] is None
    assert not Handoff.objects.exists()


@pytest.mark.parametrize(
    "change", ["requester", "student", "original", "missing_policy", "case", "kind"]
)
def test_unapproved_selector_never_decrypts(workflow_case, monkeypatch, change):
    c = workflow_case
    kw = dict(actor=c.head, student_id=c.student.pk, original_counselor_id=c.author.pk)
    if change == "requester":
        kw["actor"] = c.outsider
    elif change == "student":
        kw["student_id"] = c.receiver.pk
    elif change == "original":
        kw["original_counselor_id"] = c.outsider.pk
    elif change == "missing_policy":
        c.workflow_control[0] = None
    elif change == "case":
        c.workflow_control[0] = replace(c.workflow, office_cases=())
    elif change == "kind":
        c.workflow_control[0] = replace(c.workflow, source_kinds=frozenset())
    monkeypatch.setattr(
        selected.content, "read_evaluation", lambda *_: pytest.fail("evaluation decrypt")
    )
    with pytest.raises(ContinuityError):
        coverage_selection.select(**kw)


def test_selection_is_metadata_only_and_request_requires_approved_case(workflow_case):
    c = workflow_case
    page = coverage_selection.select(
        actor=c.author, student_id=c.student.pk, original_counselor_id=c.author.pk
    )
    assert len(page["items"]) == 2
    assert set(page["items"][0]) == {
        "resource_kind",
        "source_id",
        "projection",
        "counselor_id",
        "recorded_at",
        "eligible",
    }
    assert len(page["receivers"]) >= 1
    c.workflow_control[0] = replace(c.workflow, office_cases=())
    c.control.operational = replace(c.policy, workflow_policy_digest=c.workflow_control[0].digest)
    with pytest.raises(ContinuityError):
        request(c, actor=c.head)


@pytest.mark.parametrize(
    "field", ["student_id", "author_id", "receiving_counselor_id", "grant_id", "id"]
)
def test_ciphertext_identity_binding_and_metadata_tamper(workflow_case, field):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    item = Handoff.objects.get()
    setattr(item, field, uuid4())
    with pytest.raises(ContinuityError, match="handoff_unavailable"):
        handoff_content.read(item)


@pytest.mark.parametrize("bad", [None, 1, [], {}, "\0", "\ud800", "x" * 12001])
def test_invalid_content_is_safe(workflow_case, bad):
    c = workflow_case
    g = request(c)
    with pytest.raises(ContinuityError, match="invalid_handoff_content"):
        draft(c, g, bad)
    assert not Handoff.objects.exists()


@pytest.mark.parametrize("empty", ["", " ", "\n\t"])
def test_empty_draft_allowed_but_submit_denied(workflow_case, empty):
    c = workflow_case
    g = request(c)
    draft(c, g, empty)
    with pytest.raises(ContinuityError, match="empty_handoff"):
        op(c, g, "submit", expected_version=1)
    assert Handoff.objects.get().state == "DRAFT"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "invalid",
        "wrong",
        "duplicate",
        "corrupt",
        "legacy",
        "envelope",
        "schema",
        "payload",
    ],
)
def test_safe_crypto_failures(workflow_case, settings, fault):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    item = Handoff.objects.get()
    if fault == "missing":
        settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = ()
    elif fault == "invalid":
        settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = ("bad",)
    elif fault == "wrong":
        settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    elif fault == "duplicate":
        settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (
            settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS * 2
        )
    elif fault == "corrupt":
        item.content_ciphertext = "corrupt"
    elif fault == "legacy":
        from compass.counseling.student_session_summary_content import (
            encrypt_student_session_summary_content,
        )

        item.content_ciphertext = encrypt_student_session_summary_content(
            summary_id=item.pk, encounter_id=c.encounter.pk, content=TEXT
        )
    elif fault == "envelope":
        item.content_ciphertext = Fernet(handoff_content.keyring()[0]).encrypt(b"[]").decode()
    else:
        item.content_ciphertext = crypto.encrypt_bound_json(
            keyring=handoff_content.keyring(),
            schema_version=2 if fault == "schema" else 1,
            binding=handoff_content.binding(item),
            payload={"wrong": TEXT},
        )
    item.save(update_fields=["content_ciphertext"])
    with pytest.raises(ContinuityError, match="handoff_unavailable") as e:
        op(c, g, "receive", actor=c.receiver)
    assert e.value.status == 503 and TEXT not in str(e.value)


def test_rotation_dryrun_verification_identity_and_metadata_preservation(workflow_case, settings):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    before = Handoff.objects.values().get()
    old = settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (Fernet.generate_key().decode(), *old)
    output = StringIO()
    call_command("rotate_counselor_handoff_summary_encryption", dry_run=True, stdout=output)
    assert Handoff.objects.values().get() == before
    call_command("rotate_counselor_handoff_summary_encryption", batch_size=1, stdout=output)
    after = Handoff.objects.values().get()
    assert before["content_ciphertext"] != after.pop("content_ciphertext")
    before.pop("content_ciphertext")
    assert after == before
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (
        settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS[:1]
    )
    assert op(c, g, "receive", actor=c.receiver)["content"] == TEXT
    assert TEXT not in output.getvalue()


def test_stale_versions_relations_and_protected_references(workflow_case):
    c = workflow_case
    g = request(c)
    draft(c, g)
    with pytest.raises(ContinuityError, match="stale_handoff_version"):
        op(c, g, "save", body="new", expected_version=0)
    with pytest.raises(ProtectedError):
        Grant.objects.get(pk=g["id"]).delete()
    with transaction.atomic():
        with pytest.raises(RuntimeError, match="durable"):
            op(c, g, "author_read")


def test_api_csrf_cache_content_separation_and_default_unavailable(workflow_case):
    c = workflow_case
    g = selected.approved(c)
    base = f"/api/v1/counseling/continuity-grants/{g['id']}/handoff"
    a = client(c.author)
    csrf = a.get("/api/v1/auth/csrf").json()["csrf_token"]
    data = dict(expected_grant_version=g["version"], expected_version=0, content=TEXT)
    resp = a.put(
        base + "/draft",
        data=json.dumps(data),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert resp.status_code == 200, resp.content
    assert "content" not in resp.json() and resp["Cache-Control"] == "private, no-store"
    assert (
        a.get(base + "/author", {"expected_grant_version": g["version"]}).json()["content"] == TEXT
    )
    data.pop("content")
    data["expected_version"] = 1
    assert (
        a.post(
            base + "/submit",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        ).status_code
        == 200
    )
    r = client(c.receiver).get(base + "/submitted", {"expected_grant_version": g["version"]})
    assert r.status_code == 200 and r.json()["content"] == TEXT
    c.workflow_control[0] = None
    r = client(c.receiver).get(base + "/submitted", {"expected_grant_version": g["version"]})
    assert (
        r.status_code == 403
        and r["Cache-Control"] == "private, no-store"
        and TEXT not in r.content.decode()
    )


@pytest.mark.parametrize("identity", ["student_id", "author_id", "receiving_counselor_id"])
def test_structural_document_identity_tamper_is_denied_before_decrypt(
    workflow_case, monkeypatch, identity
):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    Handoff.objects.filter(grant_id=g["id"]).update(**{identity: c.outsider.pk})
    monkeypatch.setattr(
        handoff_content, "read", lambda *_: pytest.fail("decrypt tampered identity")
    )
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)


@pytest.mark.parametrize("operation", ["save", "submit", "author_read"])
def test_author_post_expiry_denial(workflow_case, monkeypatch, operation):
    c = workflow_case
    g = selected.approved(c)
    draft(c, g)
    monkeypatch.setattr(handoff_services.timezone, "now", lambda: g["expires_at"])
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("expired decrypt"))
    with pytest.raises(ContinuityError):
        op(c, g, operation, expected_version=1, body=TEXT)


def test_receiver_cannot_read_draft_and_swapped_ciphertext_never_releases(workflow_case):
    c = workflow_case
    g = selected.approved(c)
    draft(c, g)
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)
    row = Handoff.objects.get()
    other = Handoff(
        grant_id=uuid4(),
        student_id=row.student_id,
        author_id=row.author_id,
        receiving_counselor_id=row.receiving_counselor_id,
    )
    row.content_ciphertext = handoff_content.encrypt(other, TEXT)
    row.save(update_fields=["content_ciphertext"])
    with pytest.raises(ContinuityError):
        op(c, g, "author_read")


def test_real_csrf_and_unapproved_endpoints_no_store(workflow_case):
    from django.test import Client

    from compass.authentication.sessions import create_auth_session

    c = workflow_case
    g = selected.approved(c)
    a = Client(enforce_csrf_checks=True)
    a.cookies["compass_session"] = create_auth_session(c.author, now=timezone.now()).token
    base = f"/api/v1/counseling/continuity-grants/{g['id']}/handoff"
    response = a.put(
        base + "/draft",
        data=json.dumps(
            {"content": TEXT, "expected_grant_version": g["version"], "expected_version": 0}
        ),
        content_type="application/json",
    )
    assert response.status_code == 403 and response["Cache-Control"] == "private, no-store"
    assert not Handoff.objects.exists()
    for suffix in ["/acknowledge", "/publish", "/export"]:
        response = a.get(base + suffix)
        assert response.status_code == 404 and response["Cache-Control"] == "private, no-store"
    assert not AuditEvent.objects.filter(action="counseling.handoff.read").exists()


def test_default_providers_and_policy_manifest_validation():
    from compass.counseling.continuity_disclosure import get_approved_disclosure_policy
    from compass.counseling.continuity_policy import get_approved_policy

    assert get_approved_policy() is None
    assert get_approved_disclosure_policy() is None
    assert coverage_policy.get_approved_workflow_policy() is None


@pytest.mark.parametrize("fault", ["revoked", "rotated", "expired", "wrong_actor"])
def test_http_session_rechecked_before_handoff_decryption(workflow_case, monkeypatch, fault):
    from compass.authentication.models import AuthSession
    from compass.authentication.sessions import create_auth_session

    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    created = create_auth_session(c.receiver, now=timezone.now())
    session = AuthSession.objects.get(pk=created.session.pk)
    digest = session.token_digest
    if fault == "revoked":
        AuthSession.objects.filter(pk=session.pk).update(revoked_at=timezone.now())
    elif fault == "rotated":
        AuthSession.objects.filter(pk=session.pk).update(token_digest="synthetic-new-digest")
    elif fault == "expired":
        expires = timezone.now() + timedelta(seconds=1)
        AuthSession.objects.filter(pk=session.pk).update(expires_at=expires)
        monkeypatch.setattr(handoff_services.timezone, "now", lambda: expires)
    else:
        AuthSession.objects.filter(pk=session.pk).update(user=c.outsider)
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("session-denied decrypt"))
    with pytest.raises(ContinuityError):
        op(
            c,
            g,
            "receive",
            actor=c.receiver,
            actor_session_id=session.pk,
            actor_session_digest=digest,
        )


def test_no_handoff_notification_intents_or_student_disclosure(workflow_case):
    from compass.notifications.models import Notification

    c = workflow_case
    g = selected.approved(c)
    before = Notification.objects.count()
    submitted(c, g)
    op(c, g, "receive", actor=c.receiver)
    assert Notification.objects.count() == before
    path = f"/api/v1/counseling/continuity-grants/{g['id']}/handoff/submitted"
    response = client(c.student).get(path, {"expected_grant_version": g["version"]})
    assert response.status_code == 403 and TEXT not in response.content.decode()


@pytest.mark.parametrize(
    "change",
    [
        "author_rule",
        "post_expiry_rule",
        "acknowledgment_rule",
        "notification_rule",
        "source_kinds",
        "office_cases",
        "valid_until",
        "college_ids",
    ],
)
def test_unapproved_workflow_policy_contract_denies(workflow_case, change):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    value = {
        "author_rule": "ANY_COUNSELOR",
        "post_expiry_rule": "FOREVER",
        "acknowledgment_rule": "MANDATORY",
        "notification_rule": "SEND_ALL",
        "source_kinds": frozenset({"INTAKE"}),
        "office_cases": [],
        "valid_until": c.now - timedelta(seconds=1),
        "college_ids": frozenset(),
    }[change]
    c.workflow_control[0] = replace(c.workflow, **{change: value})
    with pytest.raises(ContinuityError):
        op(c, g, "receive", actor=c.receiver)


def test_bad_input_errors_and_audit_failure_never_echo_content(workflow_case, monkeypatch, caplog):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    http = client(c.receiver)
    base = f"/api/v1/counseling/continuity-grants/{g['id']}/handoff/submitted"

    def fail(**kw):
        raise RuntimeError("Synthetic audit persistence failure")

    monkeypatch.setattr(handoff_services, "record_event", fail)
    response = http.get(base, {"expected_grant_version": g["version"]})
    assert response.status_code == 500 and response["Cache-Control"] == "private, no-store"
    assert TEXT not in response.content.decode() and TEXT not in caplog.text
    a = client(c.author)
    csrf = a.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = a.put(
        base.replace("/submitted", "/draft"),
        data=json.dumps(
            {
                "expected_grant_version": g["version"],
                "expected_version": 2,
                "content": TEXT + "x" * 12001,
            }
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 422 and TEXT not in response.content.decode()


def test_original_author_participates_in_policy_bound_office_request_metadata(workflow_case):
    from compass.counseling import continuity_services

    c = workflow_case
    g = request(c, actor=c.head)
    assert continuity_services.get_grant_metadata(actor=c.author, grant_id=g["id"])["id"] == g["id"]
    assert [i["id"] for i in continuity_services.list_metadata_page(actor=c.author)["items"]] == [
        g["id"]
    ]
    draft(c, g)
    set_user_capability_override(
        user=c.author, capability="counseling.handoff.manage_own", effect="REVOKE", reason="TEST"
    )
    with pytest.raises(ContinuityError):
        continuity_services.get_grant_metadata(actor=c.author, grant_id=g["id"])


def test_real_workflow_configuration_and_metadata_selection_api(workflow_case):
    c = workflow_case
    base = "/api/v1/counseling/continuity-grants/workflow"
    response = client(c.author).get(base + "/configuration")
    assert response.status_code == 200, response.content
    assert response.json()["can_request"] and not response.json()["can_approve"]
    assert response.json()["office_cases"] == []
    assert response["Cache-Control"] == "private, no-store"
    response = client(c.head).get(
        base + "/selection", {"student_id": c.student.pk, "original_counselor_id": c.author.pk}
    )
    assert response.status_code == 200, response.content
    assert len(response.json()["items"]) == 2 and TEXT not in response.content.decode()
    assert selected.SENTINEL not in response.content.decode()
    assert response["Cache-Control"] == "private, no-store"
    response = client(c.outsider).get(
        base + "/selection", {"student_id": c.student.pk, "original_counselor_id": c.author.pk}
    )
    assert response.status_code in {403, 404}


def test_original_departure_preserves_submitted_receiver_access(workflow_case):
    c = workflow_case
    g = selected.approved(c)
    submitted(c, g)
    c.author.is_active = False
    c.author.save(update_fields=["is_active"])
    assert op(c, g, "receive", actor=c.receiver)["content"] == TEXT
    with pytest.raises(ContinuityError):
        op(c, g, "author_read")


def test_office_original_metadata_revalidates_current_scope(workflow_case):
    from compass.organization.models import Campus, College, StudentAffiliation

    c = workflow_case
    g = request(c, actor=c.head)
    draft(c, g)
    campus = Campus.objects.create(code="OTHER", name="Synthetic other")
    college = College.objects.create(campus=campus, code="OTHER", name="Synthetic other")
    StudentAffiliation.objects.filter(student=c.student).update(college=college)
    with pytest.raises(ContinuityError):
        op(c, g, "metadata")
