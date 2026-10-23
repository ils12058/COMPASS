"""Actual selected reads under explicit synthetic policy evidence. No runtime activation."""

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserCapabilityOverride, UserDesignation
from compass.accounts.services import set_user_capability_override
from compass.audit.models import AuditEvent
from compass.confidential_data import crypto
from compass.counseling import continuity_access as access
from compass.counseling import continuity_disclosure as disclosure
from compass.counseling import continuity_policy
from compass.counseling.continuity_disclosure import (
    ENCOUNTER_METADATA_FIELDS_V1,
    EVALUATION_FIELDS_V1,
    ApprovedDisclosurePolicy,
    ApprovedSourceProjection,
)
from compass.counseling.continuity_encounters import read_selected_encounter_for_continuity
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_models import CounselorCaseContinuityScope as Scope
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.models import CounselingEncounter
from compass.organization.models import CounselorResponsibility, StudentAffiliation
from compass.routine_interviews import content
from compass.routine_interviews.continuity import read_selected_evaluation_for_continuity
from compass.routine_interviews.crypto import RoutineContentSection, encrypt_section
from compass.routine_interviews.models import RoutineInterview
from tests import test_continuity as foundation_tests
from tests.test_continuity import client, decide, request

metadata_case = foundation_tests.case

pytestmark = pytest.mark.django_db(transaction=True)
SENTINEL = "SYNTHETIC-PROFESSIONAL-CONTENT-NOT-FOR-ERRORS"


@pytest.fixture
def selected_case(metadata_case, monkeypatch):
    c = metadata_case
    c.service.code = "COUNSELING"
    c.service.save(update_fields=["code"])
    c.values = content.empty_evaluation() | {
        "academic_adjustment_rating": 7,
        "recommendations": SENTINEL,
        "other_adjustment": "UNAPPROVED-OTHER-SENTINEL",
        "special_concern": "UNAPPROVED-CONCERN-SENTINEL",
    }
    content.write_evaluation(c.routine, c.values)
    c.routine.save(update_fields=["counselor_evaluation_ciphertext", "updated_at"])
    c.disclosure = ApprovedDisclosurePolicy(
        version="TEST-DISCLOSURE-V1",
        evidence_reference="TEST-D06",
        basis_evidence_reference="TEST-BASIS-D08",
        transparency_evidence_reference="TEST-TRANSPARENCY-D08",
        retention_evidence_reference="TEST-D14",
        monitoring_evidence_reference="TEST-D13",
        coordination_evidence_reference="TEST-PG-PROVIDER-FENCE",
        valid_from=c.policy.valid_from,
        valid_until=c.policy.valid_until,
        college_ids=c.policy.college_ids,
        projections=(
            ApprovedSourceProjection(
                "ENCOUNTER", "ENCOUNTER_METADATA_V1", ENCOUNTER_METADATA_FIELDS_V1
            ),
            ApprovedSourceProjection(
                "ROUTINE_EVALUATION",
                "FINALIZED_EVALUATION_V1",
                frozenset({"academic_adjustment_rating", "recommendations"}),
            ),
        ),
    )
    c.policy = replace(c.policy, disclosure_policy_digest=c.disclosure.digest)
    c.control = SimpleNamespace(operational=c.policy, disclosure=c.disclosure)
    monkeypatch.setattr(continuity_policy, "get_approved_policy", lambda: c.control.operational)
    monkeypatch.setattr(disclosure, "get_approved_disclosure_policy", lambda: c.control.disclosure)
    return c


def approved(c, approver=None, **changes):
    g = request(c, **changes)
    return decide(c, g, actor=approver or c.head)


def read(c, g, kind="ROUTINE_EVALUATION", **changes):
    data = dict(actor=c.receiver, grant_id=g["id"], expected_version=g["version"]) | changes
    if kind == "ENCOUNTER":
        return read_selected_encounter_for_continuity(**(dict(encounter_id=c.encounter.pk) | data))
    return read_selected_evaluation_for_continuity(
        **(dict(routine_interview_id=c.routine.pk) | data)
    )


def expect(code):
    return pytest.raises(ContinuityError, match=code)


def reads():
    return AuditEvent.objects.filter(action="counseling.continuity.source_read")


@pytest.mark.parametrize("kind", ["ENCOUNTER", "ROUTINE_EVALUATION"])
def test_selected_projection_success_and_history_unchanged(selected_case, kind):
    c = selected_case
    g = approved(c)
    models = [Grant, Scope, CounselingEncounter, RoutineInterview]
    before = [list(m.objects.order_by("pk").values()) for m in models]
    result = read(c, g, kind)
    assert (
        result["grant_version"] == 2 and result["disclosure_policy_version"] == c.disclosure.version
    )
    if kind == "ENCOUNTER":
        assert set(result["encounter"]) == ENCOUNTER_METADATA_FIELDS_V1
        assert result["encounter"]["counselor_id"] == c.author.pk
    else:
        assert result["evaluation"] == {
            "academic_adjustment_rating": 7,
            "recommendations": SENTINEL,
        }
    assert [list(m.objects.order_by("pk").values()) for m in models] == before
    assert reads().count() == 1
    event = reads().get()
    assert event.actor_user_id == c.receiver.pk
    assert SENTINEL not in json.dumps(event.metadata)
    assert set(event.metadata) == {
        "grant_id",
        "receiving_counselor_id",
        "student_id",
        "resource_kind",
        "source_id",
        "projection",
        "grant_version",
        "policy_version",
        "policy_evidence",
        "disclosure_policy_version",
        "disclosure_policy_evidence",
        "disclosure_policy_digest",
    }


@pytest.mark.parametrize("who", ["author", "outsider", "head", "student"])
def test_only_exact_receiver_can_use_grant(selected_case, monkeypatch, who):
    c = selected_case
    g = approved(c)

    def fail(*a, **k):
        raise AssertionError("unauthorized decrypt")

    monkeypatch.setattr(content, "read_evaluation", fail)
    with pytest.raises(ContinuityError) as exc:
        read(c, g, actor=getattr(c, who))
    assert exc.value.status == (403 if who == "student" else 404)
    assert reads().count() == 0


@pytest.mark.parametrize("role", ["IT_ADMIN", "GUIDANCE_SERVICES_STAFF", "INSTITUTIONAL_OFFICER"])
def test_unsupported_roles_with_unusual_capabilities(selected_case, role, monkeypatch):
    c = selected_case
    g = approved(c)
    user = c.user("unsupported", role)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("invalid_role"):
        read(c, g, actor=user)


def test_cross_college_and_legitimate_head_receiver(selected_case):
    c = selected_case
    CounselorResponsibility.objects.create(college=c.college_b, counselor=c.receiver)
    g = approved(c)
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    decide(c, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
    UserDesignation.objects.create(
        user=c.outsider, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    c.control.operational = replace(c.policy, approver_ids=frozenset([c.outsider.pk]))
    g = approved(c, approver=c.outsider, receiving_counselor_id=c.head.pk, request_id=uuid4())
    assert read(c, g, actor=c.head)["evaluation"]["recommendations"] == SENTINEL


@pytest.mark.parametrize(
    "change",
    [
        "inactive",
        "role",
        "revoke",
        "view_revoke",
        "source_capability",
        "override_expired",
        "transfer",
        "former",
        "student_inactive",
        "head_designation",
    ],
)
def test_current_authority_rechecked_before_decrypt(selected_case, monkeypatch, change):
    c = selected_case
    g = approved(c)
    if change == "inactive":
        User.objects.filter(pk=c.receiver.pk).update(is_active=False)
    elif change == "role":
        User.objects.filter(pk=c.receiver.pk).update(
            role=Role.objects.get(code="GUIDANCE_SERVICES_STAFF")
        )
    elif change in {"revoke", "view_revoke", "source_capability"}:
        cap = {
            "revoke": "counseling.continuity.read_selected",
            "view_revoke": "counseling.continuity.view",
            "source_capability": "routine_interviews.view_assigned",
        }[change]
        set_user_capability_override(
            user=c.receiver, capability=cap, effect="REVOKE", reason="Synthetic revoke"
        )
    elif change == "override_expired":
        UserCapabilityOverride.objects.filter(
            user=c.receiver, capability__code="counseling.continuity.read_selected"
        ).update(expires_at=c.now - timedelta(seconds=1))
    elif change == "transfer":
        StudentAffiliation.objects.filter(student=c.student).update(
            college=c.college_b, updated_at=timezone.now()
        )
    elif change == "former":
        User.objects.filter(pk=c.student.pk).update(student_lifecycle_status="FORMER")
    elif change == "student_inactive":
        User.objects.filter(pk=c.student.pk).update(is_active=False)
    elif change == "head_designation":
        UserDesignation.objects.filter(user=c.head).delete()
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with pytest.raises(ContinuityError):
        read(c, g)
    assert reads().count() == 0


@pytest.mark.parametrize("kind", ["ENCOUNTER", "ROUTINE_EVALUATION"])
def test_original_counselor_departure_does_not_rewrite_source(selected_case, kind):
    c = selected_case
    g = approved(c)
    User.objects.filter(pk=c.author.pk).update(is_active=False)
    assert read(c, g, kind)["grant_id"] == g["id"]


@pytest.mark.parametrize(
    "state", ["REQUESTED", "DECLINED", "CANCELLED", "SCHEDULED", "EXPIRED", "REVOKED"]
)
def test_noneffective_grant_concealed_before_decryption(selected_case, monkeypatch, state):
    c = selected_case
    if state == "SCHEDULED":
        g = approved(c, starts_at=c.now + timedelta(minutes=1))
    elif state == "REQUESTED":
        g = request(c)
    elif state in {"DECLINED", "CANCELLED"}:
        g = decide(c, request(c), state, actor=c.author if state == "CANCELLED" else c.head)
    else:
        g = approved(c)
        if state == "REVOKED":
            g = decide(c, g, state, revocation_reason="COVERAGE_ENDED")
        else:
            monkeypatch.setattr(access.timezone, "now", lambda: g["expires_at"])
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("not_found"):
        read(c, g)
    assert reads().count() == 0


@pytest.mark.parametrize(
    "change",
    [
        "operational_missing",
        "operational_expired",
        "operational_changed",
        "disclosure_missing",
        "disclosure_expired",
        "disclosure_changed",
        "unbound",
        "rebound_without_new_request",
    ],
)
def test_both_policies_independently_required_and_sealed(selected_case, monkeypatch, change):
    c = selected_case
    g = approved(c)
    if change == "operational_missing":
        c.control.operational = None
    elif change == "operational_expired":
        c.control.operational = replace(c.policy, valid_until=c.now - timedelta(seconds=1))
    elif change == "operational_changed":
        c.control.operational = replace(c.policy, version="CHANGED")
    elif change == "disclosure_missing":
        c.control.disclosure = None
    elif change == "disclosure_expired":
        c.control.disclosure = replace(c.disclosure, valid_until=c.now - timedelta(seconds=1))
    elif change == "disclosure_changed":
        c.control.disclosure = replace(c.disclosure, version="CHANGED")
    elif change == "unbound":
        c.control.operational = replace(c.policy, disclosure_policy_digest="")
    else:
        c.control.disclosure = replace(c.disclosure, version="CHANGED")
        c.control.operational = replace(
            c.policy, disclosure_policy_digest=c.control.disclosure.digest
        )
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("policy_unconfirmed"):
        read(c, g)
    assert reads().count() == 0


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "evidence_reference",
        "basis_evidence_reference",
        "transparency_evidence_reference",
        "retention_evidence_reference",
        "monitoring_evidence_reference",
        "coordination_evidence_reference",
    ],
)
def test_required_evidence_absence_denies_before_decrypt(selected_case, monkeypatch, field):
    c = selected_case
    g = approved(c)
    c.control.disclosure = replace(c.disclosure, **{field: ""})
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("disclosure_policy_unconfirmed"):
        read(c, g)


@pytest.mark.parametrize(
    "fields",
    [frozenset(), frozenset({"student_intake"}), frozenset({"recommendations", "future_field"})],
)
def test_empty_unknown_or_excluded_field_lists_denied(selected_case, monkeypatch, fields):
    c = selected_case
    g = approved(c)
    item = ApprovedSourceProjection("ROUTINE_EVALUATION", "FINALIZED_EVALUATION_V1", fields)
    c.control.disclosure = replace(c.disclosure, projections=(item,))
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("disclosure_policy_unconfirmed"):
        read(c, g)


def test_all_nine_fields_only_with_explicit_bound_projection(selected_case):
    c = selected_case
    item = ApprovedSourceProjection(
        "ROUTINE_EVALUATION", "FINALIZED_EVALUATION_V1", EVALUATION_FIELDS_V1
    )
    c.control.disclosure = replace(c.disclosure, projections=(item,))
    c.control.operational = replace(c.policy, disclosure_policy_digest=c.control.disclosure.digest)
    assert read(c, approved(c))["evaluation"] == c.values


def test_future_ordinary_evaluation_field_does_not_expand_projection(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    original = content.read_evaluation
    monkeypatch.setattr(
        content, "read_evaluation", lambda item: original(item) | {"future_field": "MUST-NOT-LEAK"}
    )
    assert set(read(c, g)["evaluation"]) == {"academic_adjustment_rating", "recommendations"}


@pytest.mark.parametrize(
    "change",
    [
        "wrong_student",
        "wrong_owner",
        "draft",
        "unsubmitted",
        "broken_link",
        "linked_owner",
        "linked_student",
        "linked_revision",
        "routine_revision",
        "scope",
        "grant_source_replacement",
        "source_deleted",
        "future_encounter",
        "mode_mismatch",
        "wrong_service",
    ],
)
def test_source_integrity_and_snapshot_before_decrypt(selected_case, monkeypatch, change):
    c = selected_case
    g = approved(c)
    if change == "wrong_student":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(student=c.user("other", "STUDENT"))
    elif change == "wrong_owner":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(counselor=c.outsider)
    elif change == "draft":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(evaluation_finalized_at=None)
    elif change == "unsubmitted":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(intake_submitted_at=None)
    elif change == "broken_link":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(
            evaluation_finalized_at=None, counseling_encounter=None
        )
    elif change == "linked_owner":
        CounselingEncounter.objects.filter(pk=c.encounter.pk).update(counselor=c.outsider)
    elif change == "linked_student":
        CounselingEncounter.objects.filter(pk=c.encounter.pk).update(
            student=c.user("other", "STUDENT")
        )
    elif change == "linked_revision":
        CounselingEncounter.objects.filter(pk=c.encounter.pk).update(
            updated_at=timezone.now() + timedelta(seconds=1)
        )
    elif change == "routine_revision":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(
            updated_at=timezone.now() + timedelta(seconds=1)
        )
    elif change == "scope":
        Scope.objects.filter(grant_id=g["id"], resource_kind="ROUTINE_EVALUATION").update(
            source_revision="FORGED"
        )
    elif change == "grant_source_replacement":
        Scope.objects.filter(grant_id=g["id"], resource_kind="ROUTINE_EVALUATION").update(
            source_id=uuid4()
        )
    elif change == "source_deleted":
        RoutineInterview.objects.filter(pk=c.routine.pk).delete()
    elif change == "future_encounter":
        CounselingEncounter.objects.filter(pk=c.encounter.pk).update(
            ended_at=timezone.now() + timedelta(hours=1)
        )
    elif change == "mode_mismatch":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(delivery_mode="ONLINE")
    elif change == "wrong_service":
        c.service.code = "UNRELATED"
        c.service.save(update_fields=["code"])
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with pytest.raises(ContinuityError) as exc:
        read(c, g)
    assert exc.value.status in {403, 404, 409}
    assert reads().count() == 0


@pytest.mark.parametrize(
    "what",
    [
        "nonexistent",
        "unselected_valid",
        "other_grant",
        "wrong_projection",
        "excluded_kind",
        "stale_version",
    ],
)
def test_guessed_source_or_projection_never_sufficient(selected_case, monkeypatch, what):
    c = selected_case
    g = approved(c)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with pytest.raises(ContinuityError) as exc:
        if what == "nonexistent":
            read(c, g, routine_interview_id=uuid4())
        elif what == "unselected_valid":
            read(c, g, routine_interview_id=c.encounter.pk)
        elif what == "other_grant":
            read(c, g, grant_id=uuid4())
        elif what == "wrong_projection":
            access.read_selected_continuity_record(
                actor=c.receiver,
                grant_id=g["id"],
                resource_kind="ROUTINE_EVALUATION",
                source_id=c.routine.pk,
                projection="ENCOUNTER_METADATA_V1",
                expected_version=2,
            )
        elif what == "excluded_kind":
            access.read_selected_continuity_record(
                actor=c.receiver,
                grant_id=g["id"],
                resource_kind="INTAKE",
                source_id=c.routine.pk,
                projection="FINALIZED_EVALUATION_V1",
                expected_version=2,
            )
        else:
            read(c, g, expected_version=1)
    assert exc.value.status in {404, 409}
    assert reads().count() == 0


@pytest.mark.parametrize(
    "failure", ["malformed", "binding", "schema", "payload", "wrong_key", "missing_key"]
)
def test_authenticated_encryption_failures_are_safe(selected_case, settings, failure):
    c = selected_case
    g = approved(c)
    if failure == "wrong_key":
        settings.ROUTINE_INTERVIEW_ENCRYPTION_KEYS = Fernet.generate_key().decode()
    elif failure == "missing_key":
        settings.ROUTINE_INTERVIEW_ENCRYPTION_KEYS = ""
    else:
        token = "INVALID-CIPHERTEXT"
        if failure == "binding":
            token = encrypt_section(
                routine_interview_id=uuid4(),
                section=RoutineContentSection.COUNSELOR_EVALUATION,
                payload=c.values,
            )
        if failure == "schema":
            token = crypto.encrypt_bound_json(
                keyring=crypto.parse_fernet_keyring(
                    settings.ROUTINE_INTERVIEW_ENCRYPTION_KEYS, setting="TEST"
                ),
                schema_version=2,
                binding={
                    "routine_interview_id": str(c.routine.pk),
                    "section": "counselor_evaluation",
                },
                payload=c.values,
            )
        if failure == "payload":
            token = encrypt_section(
                routine_interview_id=c.routine.pk,
                section=RoutineContentSection.COUNSELOR_EVALUATION,
                payload=c.values | {"academic_adjustment_rating": SENTINEL},
            )
        RoutineInterview.objects.filter(pk=c.routine.pk).update(
            counselor_evaluation_ciphertext=token
        )
    with expect("source_unavailable") as exc:
        read(c, g)
    assert exc.value.status == 503 and SENTINEL not in str(exc.value)
    assert reads().count() == 0


def test_only_evaluation_ciphertext_is_loaded_and_intake_never_decrypted(
    selected_case, monkeypatch
):
    c = selected_case
    g = approved(c)
    from compass.assessment_records import confidential_content as assessment
    from compass.counseling import student_session_summary_content as summaries
    from compass.ecounseling import artifacts
    from compass.inventory import confidential_content as inventory
    from compass.referrals import confidential_content as referrals

    def fail(*a, **k):
        pytest.fail("Unrelated confidential access")

    for module, name in [
        (content, "read_intake"),
        (inventory, "read_confidential_content"),
        (referrals, "read_referral_confidential_content"),
        (assessment, "read_confidential_content"),
        (summaries, "read_student_session_summary_content"),
        (artifacts, "access_artifact"),
    ]:
        monkeypatch.setattr(module, name, fail)
    with CaptureQueriesContext(connection) as q:
        read(c, g)
    selects = " ".join(
        i["sql"].lower()
        for i in q.captured_queries
        if i["sql"].lstrip().lower().startswith("select")
    )
    assert (
        "student_intake_ciphertext" not in selects
        and "profile_confidential_content_ciphertext" not in selects
    )
    assert "counselor_evaluation_ciphertext" in selects


@pytest.mark.parametrize("when", ["before_audit", "during_audit"])
def test_expiry_during_content_preparation_or_audit_rolls_back(selected_case, monkeypatch, when):
    c = selected_case
    g = approved(c)
    if when == "before_audit":
        original = content.read_evaluation

        def decrypt(item):
            value = original(item)
            monkeypatch.setattr(access.timezone, "now", lambda: g["expires_at"])
            return value

        monkeypatch.setattr(content, "read_evaluation", decrypt)
    else:
        original = access.record_event

        def audit(**kwargs):
            value = original(**kwargs)
            monkeypatch.setattr(access.timezone, "now", lambda: g["expires_at"])
            return value

        monkeypatch.setattr(access, "record_event", audit)
    with expect("not_found"):
        read(c, g)
    assert reads().count() == 0


def test_audit_failure_no_body_no_success_event(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)

    def fail(**kwargs):
        raise RuntimeError("synthetic Audit persistence failure")

    monkeypatch.setattr(access, "record_event", fail)
    with pytest.raises(RuntimeError, match="Audit persistence"):
        read(c, g)
    assert reads().count() == 0


def test_http_projection_omission_no_store_and_read_only(selected_case, monkeypatch):
    c = selected_case
    c.values["academic_adjustment_rating"] = None
    content.write_evaluation(c.routine, c.values)
    c.routine.save(update_fields=["counselor_evaluation_ciphertext", "updated_at"])
    g = approved(c)
    http = client(c.receiver)
    prefix = "/api/v1/counseling/continuity-grants/" + str(g["id"])
    path = prefix + "/routine-evaluations/" + str(c.routine.pk)
    response = http.get(path, {"expected_version": 2})
    assert response.status_code == 200, response.content
    assert response.json()["evaluation"] == {
        "academic_adjustment_rating": None,
        "recommendations": SENTINEL,
    }
    assert response.headers["Cache-Control"] == "private, no-store"
    assert (
        http.get(
            prefix + "/encounters/" + str(c.encounter.pk) + "/metadata", {"expected_version": 2}
        ).status_code
        == 200
    )
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    for suffix, query, status in [
        ("", {}, 422),
        ("", {"expected_version": 2, "fields": "special_concern"}, 422),
        ("", {"expected_version": 1}, 409),
    ]:
        r = http.get(path + suffix, query)
        assert r.status_code == status and r.headers["Cache-Control"] == "private, no-store"
    assert http.post(path).status_code in {403, 405}
    for excluded in [
        "/intake",
        "/student-session-summary",
        "/recordings",
        "/assessments",
        "/messages",
        "/export",
        "/sources/" + str(c.routine.pk) + "/content",
    ]:
        r = http.get(prefix + excluded, {"expected_version": 2})
        assert r.status_code == 404 and r.headers["Cache-Control"] == "private, no-store"
    assert reads().count() == 2


def test_old_metadata_policy_digest_is_preserved_and_cannot_disclose(metadata_case):
    c = metadata_case
    values = asdict(c.policy)
    values.pop("disclosure_policy_digest")
    for key, value in values.items():
        if isinstance(value, frozenset):
            values[key] = sorted(str(i) for i in value)
        elif isinstance(value, datetime):
            values[key] = value.astimezone(UTC).isoformat()
        elif isinstance(value, timedelta):
            values[key] = value.total_seconds()
    assert (
        c.policy.digest == hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    )
    g = approved(c)
    with expect("disclosure_policy_unconfirmed"):
        read(c, g)


@pytest.mark.parametrize("missing", ["operational", "disclosure"])
def test_policy_http_denial_before_decrypt_and_content_free_error(
    selected_case, monkeypatch, missing, caplog
):
    c = selected_case
    g = approved(c)
    http = client(c.receiver)
    setattr(c.control, missing, None)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    response = http.get(
        "/api/v1/counseling/continuity-grants/"
        + str(g["id"])
        + "/routine-evaluations/"
        + str(c.routine.pk),
        {"expected_version": 2},
    )
    assert response.status_code == 403 and response.headers["Cache-Control"] == "private, no-store"
    assert SENTINEL not in response.content.decode() and SENTINEL not in caplog.text
    assert reads().count() == 0


@pytest.mark.parametrize("failure", ["crypto", "audit"])
def test_authorized_http_failure_never_returns_prepared_body(
    selected_case, monkeypatch, failure, caplog
):
    c = selected_case
    g = approved(c)
    http = client(c.receiver)
    if failure == "crypto":
        RoutineInterview.objects.filter(pk=c.routine.pk).update(
            counselor_evaluation_ciphertext="BAD-CIPHERTEXT-SENTINEL"
        )
    else:

        def fail(**kwargs):
            raise RuntimeError("Synthetic read audit failure")

        monkeypatch.setattr(access, "record_event", fail)
    response = http.get(
        "/api/v1/counseling/continuity-grants/"
        + str(g["id"])
        + "/routine-evaluations/"
        + str(c.routine.pk),
        {"expected_version": 2},
    )
    assert response.status_code == (503 if failure == "crypto" else 500)
    assert response.headers["Cache-Control"] == "private, no-store"
    assert SENTINEL not in response.content.decode() and SENTINEL not in caplog.text
    assert "BAD-CIPHERTEXT-SENTINEL" not in response.content.decode()
    assert reads().count() == 0


@pytest.mark.parametrize(
    "change",
    [
        "lifecycle",
        "revision",
        "unknown_kind",
        "unknown_projection",
        "college_scope",
        "partial_encounter",
    ],
)
def test_invalid_disclosure_projection_contract_denied(selected_case, monkeypatch, change):
    c = selected_case
    g = approved(c)
    if change == "college_scope":
        p = replace(c.disclosure, college_ids=frozenset())
    else:
        item = c.disclosure.projections[1]
        if change == "lifecycle":
            item = replace(item, lifecycle_rule="ALLOW_DRAFT")
        if change == "revision":
            item = replace(item, revision_rule="IGNORE_CHANGE")
        if change == "unknown_kind":
            item = replace(item, resource_kind="INTAKE")
        if change == "unknown_projection":
            item = replace(item, projection="ALL_FIELDS")
        if change == "partial_encounter":
            item = ApprovedSourceProjection("ENCOUNTER", "ENCOUNTER_METADATA_V1", frozenset({"id"}))
        p = replace(c.disclosure, projections=(item,))
    c.control.disclosure = p
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("disclosure_policy_unconfirmed"):
        read(c, g)


def test_provider_drift_during_decryption_is_not_released(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    original = content.read_evaluation

    def decrypt(item):
        result = original(item)
        c.control.disclosure = None
        return result

    monkeypatch.setattr(content, "read_evaluation", decrypt)
    with expect("disclosure_policy_unconfirmed"):
        read(c, g)
    assert reads().count() == 0


@pytest.mark.parametrize("state", ["revoked", "expired", "rotated"])
def test_session_authority_is_rechecked_at_selected_read(selected_case, monkeypatch, state):
    from compass.authentication.models import AuthSession
    from compass.authentication.sessions import create_auth_session

    c = selected_case
    g = approved(c)
    session = create_auth_session(c.receiver, now=timezone.now()).session
    if state == "revoked":
        AuthSession.objects.filter(pk=session.pk).update(revoked_at=timezone.now())
    elif state == "expired":
        AuthSession.objects.filter(pk=session.pk).update(expires_at=timezone.now())
    else:
        AuthSession.objects.filter(pk=session.pk).update(token_digest="1" * 64)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("session_unavailable") as exc:
        read(c, g, actor_session_id=session.pk, actor_session_digest=session.token_digest)
    assert exc.value.status == 401 and reads().count() == 0


def test_new_valid_unselected_record_gains_no_entitlement(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    encounter = CounselingEncounter.objects.create(
        student=c.student,
        counselor=c.author,
        service=c.service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=c.encounter.started_at,
        ended_at=c.encounter.ended_at,
    )
    routine = RoutineInterview.objects.create(
        student=c.student,
        counselor=c.author,
        counseling_encounter=encounter,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=c.routine.intake_submitted_at,
        evaluation_finalized_at=c.routine.evaluation_finalized_at,
        student_intake_ciphertext="SYNTHETIC-UNREADABLE",
        counselor_evaluation_ciphertext="SYNTHETIC-UNREADABLE",
    )
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("source_not_found"):
        read(c, g, routine_interview_id=routine.pk)
    with expect("source_not_found"):
        read(c, g, "ENCOUNTER", encounter_id=encounter.pk)
    assert reads().count() == 0


def test_selected_read_does_not_authorize_ordinary_reads_or_writes(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    http = client(c.receiver)
    csrf = http.get("/api/v1/auth/csrf").json()["csrf_token"]
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("ordinary decrypt"))
    routine = "/api/v1/routine-interviews/" + str(c.routine.pk)
    encounter = "/api/v1/counseling/encounters/" + str(c.encounter.pk)
    before = [list(m.objects.values()) for m in [CounselingEncounter, RoutineInterview]]
    for path in [routine, encounter, encounter + "/student-session-summary"]:
        assert http.get(path, {"grant_id": str(g["id"])}).status_code in {403, 404}
    for method, path, payload in [
        ("put", routine + "/evaluation", {}),
        ("patch", encounter, {"ended_at": c.encounter.ended_at.isoformat()}),
    ]:
        r = getattr(http, method)(
            path, data=json.dumps(payload), content_type="application/json", HTTP_X_CSRFTOKEN=csrf
        )
        assert r.status_code in {403, 404}
    assert [list(m.objects.values()) for m in [CounselingEncounter, RoutineInterview]] == before


@pytest.mark.parametrize(
    "parent_state",
    ["valid", "cancelled", "no_show", "wrong_provider", "wrong_student", "mode", "service"],
)
def test_appointment_backed_source_lifecycle_is_independently_checked(
    selected_case, monkeypatch, parent_state
):
    from compass.appointments.models import Appointment
    from compass.service_catalog.models import Service

    c = selected_case
    parent = Appointment.objects.create(
        reference_code="SYNTHETIC-READ-PARENT",
        student=c.student,
        provider=c.author,
        service=c.service,
        delivery_mode="IN_PERSON",
        starts_at=c.encounter.started_at,
        ends_at=c.encounter.ended_at,
        status="COMPLETED",
        completed_at=c.encounter.ended_at,
    )
    c.encounter.entry_mode = "APPOINTMENT"
    c.encounter.appointment = parent
    c.encounter.save(update_fields=["entry_mode", "appointment", "updated_at"])
    c.routine.entry_mode = "APPOINTMENT"
    c.routine.appointment = parent
    c.routine.save(update_fields=["entry_mode", "appointment", "updated_at"])
    g = approved(c)
    if parent_state == "valid":
        assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
        assert set(read(c, g, "ENCOUNTER")["encounter"]) == ENCOUNTER_METADATA_FIELDS_V1
        return
    if parent_state == "cancelled":
        changes = {"status": "CANCELLED", "cancelled_at": timezone.now(), "completed_at": None}
    elif parent_state == "no_show":
        changes = {"status": "NO_SHOW", "no_show_at": timezone.now(), "completed_at": None}
    elif parent_state == "wrong_provider":
        changes = {"provider": c.outsider}
    elif parent_state == "wrong_student":
        changes = {"student": c.user("wrong-parent-student", "STUDENT")}
    elif parent_state == "mode":
        changes = {"delivery_mode": "ONLINE"}
    else:
        changes = {"service": Service.objects.create(code="OTHER-SERVICE", name="Synthetic other")}
    Appointment.objects.filter(pk=parent.pk).update(**changes)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    for kind in ["ENCOUNTER", "ROUTINE_EVALUATION"]:
        with expect("source_not_found"):
            read(c, g, kind)
    assert reads().count() == 0


def test_prepared_content_cannot_escape_an_outer_uncommitted_transaction(
    selected_case, monkeypatch
):
    c = selected_case
    g = approved(c)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with transaction.atomic(), pytest.raises(RuntimeError, match="durable atomic block"):
        read(c, g)
    assert reads().count() == 0


def test_selected_content_half_open_start_and_expiry_boundaries(selected_case, monkeypatch):
    c = selected_case
    g = approved(c, starts_at=c.now + timedelta(minutes=5))
    clock = SimpleNamespace(value=g["starts_at"] - timedelta(microseconds=1))
    monkeypatch.setattr(access.timezone, "now", lambda: clock.value)
    with expect("not_found"):
        read(c, g)
    clock.value = g["starts_at"]
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    clock.value = g["expires_at"] - timedelta(microseconds=1)
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    clock.value = g["expires_at"]
    with expect("not_found"):
        read(c, g)
    assert reads().count() == 2
