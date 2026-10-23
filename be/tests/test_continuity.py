"""Synthetic policy fixtures are isolated here; deployed provider stays fail closed."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling import continuity_policy
from compass.counseling import continuity_services as svc
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_models import CounselorCaseContinuityScope as Scope
from compass.counseling.continuity_policy import ApprovedContinuityPolicy, ContinuityError
from compass.counseling.continuity_sources import SelectedSource
from compass.counseling.models import CounselingEncounter
from compass.organization.models import Campus, College, StudentAffiliation
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import Service

pytestmark = pytest.mark.django_db(transaction=True)
CAPS = ["view", "request", "approve", "revoke", "read_selected"]
PREFIX = "/api/v1/counseling/continuity-grants"


def grant_caps(user, codes=CAPS):
    for code in codes:
        set_user_capability_override(
            user=user,
            capability="counseling.continuity." + code,
            effect="GRANT",
            reason="SYNTHETIC TEST POLICY ONLY",
        )


@pytest.fixture
def case(monkeypatch):
    call_command("sync_identity_policy", verbosity=0)

    def user(name, role="COUNSELOR"):
        u = User.objects.create_user(
            email=name + "@synthetic.test",
            role=role,
            password=None,
            first_name=name,
            last_name="Synthetic",
        )
        grant_caps(u)
        return u

    author, receiver, head, outsider = [user(n) for n in ["author", "receiver", "head", "outsider"]]
    student = user("student", "STUDENT")
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    campus = Campus.objects.create(code="SYNTHETIC", name="Synthetic")
    college = College.objects.create(campus=campus, code="A", name="A")
    college_b = College.objects.create(campus=campus, code="B", name="B")
    StudentAffiliation.objects.create(student=student, college=college)
    now = timezone.now()
    service = Service.objects.create(code="SYNTHETIC", name="Synthetic")
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=author,
        service=service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
    )
    routine = RoutineInterview.objects.create(
        student=student,
        counselor=author,
        counseling_encounter=encounter,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=now - timedelta(hours=2),
        evaluation_finalized_at=now,
        student_intake_ciphertext="UNREADABLE-SYNTHETIC-INTAKE",
        counselor_evaluation_ciphertext="UNREADABLE-SYNTHETIC-EVALUATION",
    )
    policy = ApprovedContinuityPolicy(
        version="synthetic-v1",
        evidence_reference="TEST-ONLY-D01-D13",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=20),
        maximum_duration=timedelta(hours=8),
        maximum_advance=timedelta(days=2),
        college_ids=frozenset([college.pk, college_b.pk]),
        approver_ids=frozenset([head.pk]),
        office_requester_ids=frozenset(),
        reason_categories=frozenset(["PLANNED_ABSENCE", "UNEXPECTED_ABSENCE", "TEMPORARY_SUPPORT"]),
        overlap_rule="REJECT_ALL_RECEIVERS",
        student_transfer_rule="REQUIRE_NEW_REQUEST",
        metadata_review_approved=True,
    )
    monkeypatch.setattr(continuity_policy, "get_approved_policy", lambda: policy)
    payload = dict(
        actor=author,
        student_id=student.pk,
        receiving_counselor_id=receiver.pk,
        original_counselor_id=author.pk,
        coverage_kind="PLANNED_HANDOFF",
        reason_category="PLANNED_ABSENCE",
        starts_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=1),
        request_id=uuid4(),
        expected_version=0,
        scopes=[
            SelectedSource("ENCOUNTER", encounter.pk, "ENCOUNTER_METADATA_V1"),
            SelectedSource("ROUTINE_EVALUATION", routine.pk, "FINALIZED_EVALUATION_V1"),
        ],
    )
    return SimpleNamespace(**locals())


def request(case, **changes):
    return svc.request_coverage(**(case.payload | changes))


def decide(case, grant, decision="APPROVED", **changes):
    return svc.decide_coverage(
        **(
            dict(
                actor=case.head,
                grant_id=grant["id"],
                decision=decision,
                expected_version=grant["version"],
            )
            | changes
        )
    )


def expect(code):
    return pytest.raises(ContinuityError, match=code)


def test_lifecycle_exact_boundaries_version_and_idempotency(case, monkeypatch):
    g = request(case, starts_at=case.now + timedelta(minutes=5))
    assert g["effective_status"] == "PENDING" and g["version"] == 1
    g = decide(case, g)
    assert g["effective_status"] == "SCHEDULED" and g["version"] == 2
    count = AuditEvent.objects.filter(action__startswith="counseling.continuity.").count()
    assert decide(case, g)["version"] == 2
    assert AuditEvent.objects.filter(action__startswith="counseling.continuity.").count() == count
    for now, status in [
        (g["starts_at"], "ACTIVE"),
        (g["expires_at"] - timedelta(microseconds=1), "ACTIVE"),
        (g["expires_at"], "EXPIRED"),
    ]:
        monkeypatch.setattr(svc.timezone, "now", lambda instant=now: instant)
        assert (
            svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])["effective_status"]
            == status
        )


@pytest.mark.parametrize("decision", ["DECLINED", "CANCELLED", "REVOKED"])
def test_terminal_transitions(case, decision):
    g = request(case)
    actor = case.author if decision == "CANCELLED" else case.head
    if decision == "REVOKED":
        g = decide(case, g)
    options = {"actor": actor}
    if decision == "REVOKED":
        options["revocation_reason"] = "COVERAGE_ENDED"
    g = decide(case, g, decision, **options)
    assert g["decision"] == decision and g["effective_status"] == decision
    assert decide(case, g, decision, **options)["version"] == g["version"]
    with expect("stale_version"):
        decide(case, g, decision, expected_version=g["version"] - 1, **options)
    with expect("invalid_transition"):
        decide(case, g, "APPROVED")


@pytest.mark.parametrize("who", ["author", "receiver"])
def test_self_approval_denied_even_head(case, monkeypatch, who):
    actor = getattr(case, who)
    UserDesignation.objects.create(
        user=actor, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    monkeypatch.setattr(
        continuity_policy,
        "get_approved_policy",
        lambda: replace(case.policy, approver_ids=frozenset([actor.pk])),
    )
    g = request(case)
    with expect("self_approval"):
        decide(case, g, actor=actor)


@pytest.mark.parametrize(
    "role", ["GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "STUDENT", "INSTITUTIONAL_OFFICER"]
)
@pytest.mark.parametrize("operation", ["request", "detail", "approve"])
def test_unsupported_roles_with_all_capabilities(case, role, operation):
    actor = case.user("unsupported", role)
    g = request(case)
    with expect("invalid_role"):
        if operation == "request":
            request(case, actor=actor)
        elif operation == "detail":
            svc.get_grant_metadata(actor=actor, grant_id=g["id"])
        else:
            decide(case, g, actor=actor)


@pytest.mark.parametrize("operation", ["request", "detail", "approve"])
def test_inactive_actor_and_stale_user_object(case, operation):
    g = request(case)
    actor = case.head if operation == "approve" else case.author
    User.objects.filter(pk=actor.pk).update(is_active=False)
    with expect("invalid_role"):
        if operation == "request":
            request(case)
        elif operation == "detail":
            svc.get_grant_metadata(actor=actor, grant_id=g["id"])
        else:
            decide(case, g)


@pytest.mark.parametrize(
    "change", ["no_head", "missing_cap", "expired_cap", "explicit_revoke", "unnamed_head"]
)
def test_current_head_authority_and_no_acting_override(case, change, monkeypatch):
    g = request(case)
    if change == "no_head":
        UserDesignation.objects.filter(user=case.head).delete()
    if change in ["missing_cap", "explicit_revoke"]:
        set_user_capability_override(
            user=case.head,
            capability="counseling.continuity.approve",
            effect="REVOKE",
            reason="Synthetic revoke",
        )
    if change == "expired_cap":
        UserCapabilityOverride.objects.filter(
            user=case.head, capability__code="counseling.continuity.approve"
        ).update(expires_at=case.now - timedelta(seconds=1))
    if change == "unnamed_head":
        monkeypatch.setattr(
            continuity_policy,
            "get_approved_policy",
            lambda: replace(case.policy, approver_ids=frozenset([case.outsider.pk])),
        )
    with expect(
        "missing_capability"
        if change in ["missing_cap", "expired_cap", "explicit_revoke"]
        else "approval_authority_missing"
    ):
        decide(case, g)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", ""),
        ("evidence_reference", ""),
        ("maximum_duration", timedelta(0)),
        ("metadata_review_approved", False),
        ("approver_ids", frozenset()),
        ("overlap_rule", "UNKNOWN"),
        ("student_transfer_rule", "ALLOW_TRANSFER"),
    ],
)
def test_policy_incomplete_remains_denied(case, monkeypatch, field, value):
    monkeypatch.setattr(
        continuity_policy, "get_approved_policy", lambda: replace(case.policy, **{field: value})
    )
    with expect("policy_unconfirmed"):
        request(case)
    assert Grant.objects.count() == 0


def test_default_provider_and_missing_approval_policy(case, monkeypatch):
    g = request(case)
    monkeypatch.setattr(continuity_policy, "get_approved_policy", lambda: None)
    with expect("policy_unconfirmed"):
        decide(case, g)
    with expect("policy_unconfirmed"):
        svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])
    with expect("policy_unconfirmed"):
        request(case)
    from pathlib import Path

    assert "return None" in Path(continuity_policy.__file__).read_text()


@pytest.mark.parametrize("seconds", [0, -1, 8 * 3600 + 1])
def test_invalid_intervals(case, seconds):
    with expect("invalid_interval"):
        request(case, expires_at=case.payload["starts_at"] + timedelta(seconds=seconds))


def test_naive_and_unbounded_advance_intervals(case):
    with expect("invalid_interval"):
        request(case, starts_at=case.now.replace(tzinfo=None))
    with expect("invalid_interval"):
        request(
            case,
            starts_at=case.now + timedelta(days=3),
            expires_at=case.now + timedelta(days=3, hours=1),
        )


@pytest.mark.parametrize(
    "invalid",
    [
        "wildcard",
        "projection",
        "missing",
        "other_student",
        "draft",
        "wrong_original",
        "duplicate",
        "no_scopes",
    ],
)
def test_exact_source_validation(case, invalid):
    payload = {}
    if invalid == "wildcard":
        payload["scopes"] = [
            SelectedSource("ALL_RECORDS", case.encounter.pk, "ENCOUNTER_METADATA_V1")
        ]
    if invalid == "projection":
        payload["scopes"] = [
            SelectedSource("ENCOUNTER", case.encounter.pk, "FINALIZED_EVALUATION_V1")
        ]
    if invalid == "missing":
        payload["scopes"] = [SelectedSource("ENCOUNTER", uuid4(), "ENCOUNTER_METADATA_V1")]
    if invalid == "other_student":
        other = case.user("other-student", "STUDENT")
        CounselingEncounter.objects.filter(pk=case.encounter.pk).update(student=other)
    if invalid == "draft":
        RoutineInterview.objects.filter(pk=case.routine.pk).update(evaluation_finalized_at=None)
    if invalid == "wrong_original":
        payload["original_counselor_id"] = case.outsider.pk
    if invalid == "duplicate":
        payload["scopes"] = case.payload["scopes"] * 2
    if invalid == "no_scopes":
        payload["scopes"] = []
    with pytest.raises(ContinuityError):
        request(case, **payload)
    assert Grant.objects.count() == Scope.objects.count() == 0


@pytest.mark.parametrize(
    "kind",
    [
        "STUDENT_SESSION_SUMMARY",
        "INTAKE",
        "INVENTORY",
        "ASSESSMENT",
        "RECORDING",
        "TRANSCRIPT",
        "MESSAGE",
        "CREDENTIAL",
        "REFERRAL",
        "GUIDANCE_FOLLOWUP",
    ],
)
def test_excluded_source_kinds_never_accepted(case, kind):
    with expect("invalid_source_category"):
        request(case, scopes=[SelectedSource(kind, case.encounter.pk, "ENCOUNTER_METADATA_V1")])


@pytest.mark.parametrize(
    "change",
    [
        "source_revision",
        "source_student",
        "draft",
        "scope",
        "receiver",
        "student",
        "purpose",
        "interval",
    ],
)
def test_approval_binds_reviewed_snapshot(case, change):
    g = request(case)
    if change == "source_revision":
        CounselingEncounter.objects.filter(pk=case.encounter.pk).update(
            updated_at=timezone.now() + timedelta(seconds=1)
        )
    elif change == "source_student":
        CounselingEncounter.objects.filter(pk=case.encounter.pk).update(
            student=case.user("other", "STUDENT")
        )
    elif change == "draft":
        RoutineInterview.objects.filter(pk=case.routine.pk).update(evaluation_finalized_at=None)
    elif change == "scope":
        Scope.objects.filter(grant_id=g["id"], resource_kind="ENCOUNTER").update(source_id=uuid4())
    elif change == "receiver":
        Grant.objects.filter(pk=g["id"]).update(receiving_counselor=case.outsider)
    elif change == "student":
        Grant.objects.filter(pk=g["id"]).update(student=case.user("other", "STUDENT"))
    elif change == "purpose":
        Grant.objects.filter(pk=g["id"]).update(reason_category="TEMPORARY_SUPPORT")
    elif change == "interval":
        Grant.objects.filter(pk=g["id"]).update(expires_at=case.now + timedelta(hours=2))
    with pytest.raises(ContinuityError):
        decide(case, g)
    assert Grant.objects.get(pk=g["id"]).decision == "REQUESTED"


def test_post_approval_scope_widening_is_denied(case):
    g = decide(case, request(case))
    Scope.objects.create(
        grant_id=g["id"],
        resource_kind="ENCOUNTER",
        source_id=uuid4(),
        projection="ENCOUNTER_METADATA_V1",
        source_revision="forged",
    )
    with expect("scope_changed"):
        svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])


@pytest.mark.parametrize(
    "change",
    [
        "inactive",
        "role",
        "revoke",
        "override_expired",
        "transfer",
        "former",
        "student_inactive",
        "policy",
    ],
)
def test_effective_eligibility_revalidated(case, monkeypatch, change):
    g = decide(case, request(case))
    if change == "inactive":
        User.objects.filter(pk=case.receiver.pk).update(is_active=False)
    elif change == "role":
        User.objects.filter(pk=case.receiver.pk).update(
            role=Role.objects.get(code="GUIDANCE_SERVICES_STAFF")
        )
    elif change == "revoke":
        set_user_capability_override(
            user=case.receiver,
            capability="counseling.continuity.read_selected",
            effect="REVOKE",
            reason="Synthetic revoke",
        )
    elif change == "override_expired":
        UserCapabilityOverride.objects.filter(
            user=case.receiver, capability__code="counseling.continuity.read_selected"
        ).update(expires_at=case.now - timedelta(seconds=1))
    elif change == "transfer":
        StudentAffiliation.objects.filter(student=case.student).update(
            college=case.college_b, updated_at=timezone.now()
        )
    elif change == "former":
        User.objects.filter(pk=case.student.pk).update(student_lifecycle_status="FORMER")
    elif change == "student_inactive":
        User.objects.filter(pk=case.student.pk).update(is_active=False)
    elif change == "policy":
        monkeypatch.setattr(continuity_policy, "get_approved_policy", lambda: None)
    if change == "policy":
        with expect("policy_unconfirmed"):
            svc.get_grant_metadata(actor=case.author, grant_id=g["id"])
    else:
        assert (
            svc.get_grant_metadata(actor=case.author, grant_id=g["id"])["effective_status"]
            == "UNAVAILABLE"
        )


def test_original_departure_is_historical_only_and_absence_has_no_required_original(
    case, monkeypatch
):
    g = decide(case, request(case))
    User.objects.filter(pk=case.author.pk).update(is_active=False)
    assert (
        svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])["effective_status"]
        == "ACTIVE"
    )
    decide(case, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
    monkeypatch.setattr(
        continuity_policy,
        "get_approved_policy",
        lambda: replace(case.policy, office_requester_ids=frozenset([case.outsider.pk])),
    )
    g = request(
        case,
        actor=case.outsider,
        original_counselor_id=None,
        coverage_kind="TEMPORARY_COVERAGE",
        reason_category="UNEXPECTED_ABSENCE",
        request_id=uuid4(),
    )
    assert decide(case, g)["effective_status"] == "ACTIVE"


def test_scope_before_pagination_and_concealed_detail(case):
    g = request(case)
    assert svc.list_metadata_page(actor=case.outsider)["items"] == []
    for gid in [g["id"], uuid4()]:
        with expect("not_found"):
            svc.get_grant_metadata(actor=case.outsider, grant_id=gid)
    assert len(svc.list_metadata_page(actor=case.receiver)["items"]) == 1
    assert len(svc.list_metadata_page(actor=case.head)["items"]) == 1
    assert svc.list_metadata_page(actor=case.author, page=2, page_size=1)["items"] == []


def test_request_replay_and_conflicting_intent(case):
    g = request(case)
    assert request(case)["id"] == g["id"]
    assert Grant.objects.count() == 1
    assert AuditEvent.objects.filter(action="counseling.continuity.requested").count() == 1
    with expect("request_conflict"):
        request(case, expires_at=case.now + timedelta(hours=2))


@pytest.mark.parametrize("point", ["request", "approve", "revoke", "cancel", "decline"])
def test_audit_failure_rolls_back(case, monkeypatch, point):
    g = request(case) if point != "request" else None
    if point == "revoke":
        g = decide(case, g)
    before = list(Grant.objects.values())
    before_scopes = list(Scope.objects.values())

    def fail(**kwargs):
        raise RuntimeError("synthetic audit unavailable")

    monkeypatch.setattr(svc, "record_event", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        if point == "request":
            request(case)
        else:
            decide(
                case,
                g,
                {
                    "approve": "APPROVED",
                    "revoke": "REVOKED",
                    "cancel": "CANCELLED",
                    "decline": "DECLINED",
                }[point],
                actor=case.author if point == "cancel" else case.head,
                revocation_reason="COVERAGE_ENDED" if point == "revoke" else "",
            )
    assert list(Grant.objects.values()) == before
    assert list(Scope.objects.values()) == before_scopes


def test_metadata_never_loads_or_decrypts_content(case, monkeypatch):
    from compass.confidential_data import crypto as bound_json_content

    # All domain content codecs delegate to this primitive; any attempted decrypt fails.
    def forbidden(*args, **kwargs):
        raise AssertionError("confidential decryption attempted")

    for name in dir(bound_json_content):
        if "decrypt" in name:
            monkeypatch.setattr(bound_json_content, name, forbidden)
    from compass.assessment_records import confidential_content as assessment_content
    from compass.counseling import student_session_summary_content as summary_content
    from compass.ecounseling import artifacts
    from compass.inventory import confidential_content as inventory_content
    from compass.referrals import confidential_content as referral_content
    from compass.routine_interviews import content as routine_content

    for module, names in [
        (routine_content, ["read_intake", "read_evaluation"]),
        (summary_content, ["read_student_session_summary_content"]),
        (inventory_content, ["read_confidential_content"]),
        (referral_content, ["read_referral_confidential_content", "read_referral_action_remarks"]),
        (assessment_content, ["read_confidential_content"]),
        (artifacts, ["access_artifact"]),
    ]:
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    with CaptureQueriesContext(connection) as queries:
        g = decide(case, request(case))
        svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])
        svc.list_metadata_page(actor=case.head)
    selected_sql = " ".join(
        q["sql"].lower()
        for q in queries.captured_queries
        if q["sql"].lstrip().lower().startswith("select")
    )
    assert "ciphertext" not in selected_sql
    events = list(
        AuditEvent.objects.filter(action__startswith="counseling.continuity.").values(
            "action", "metadata"
        )
    )
    assert len(events) == 2
    assert "UNREADABLE-SYNTHETIC" not in json.dumps(events)
    assert all(
        set(e["metadata"])
        == {
            "student_id",
            "receiving_counselor_id",
            "coverage_kind",
            "reason_code",
            "version",
            "starts_at",
            "expires_at",
            "policy_version",
            "policy_evidence",
            "scope_snapshot_digest",
        }
        for e in events
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", 0),
        ("coverage_kind", "ALL"),
        ("reason_category", "CLINICAL_TEXT"),
        ("decision", "ACTIVE"),
        ("policy_evidence", ""),
        ("decision", "APPROVED"),
        ("revoked_at", timezone.now()),
    ],
)
def test_database_grant_constraints(case, field, value):
    g = request(case)
    with pytest.raises(IntegrityError), transaction.atomic():
        Grant.objects.filter(pk=g["id"]).update(**{field: value})


def test_database_scope_constraints_finite_times_and_protected_identity(case):
    from django.db.models.deletion import ProtectedError

    g = request(case)
    s = Scope.objects.filter(grant_id=g["id"]).first()
    with pytest.raises(IntegrityError), transaction.atomic():
        Scope.objects.create(
            grant_id=g["id"],
            resource_kind=s.resource_kind,
            source_id=s.source_id,
            projection=s.projection,
            source_revision=s.source_revision,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Scope.objects.filter(pk=s.pk).update(projection="UNKNOWN")
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE counseling_counselorcasecontinuitygrant "
                "SET expires_at='infinity' WHERE id=%s",
                [g["id"]],
            )
    with pytest.raises(ProtectedError):
        case.student.delete()
    with pytest.raises(ProtectedError):
        Grant.objects.get(pk=g["id"]).delete()


def client(user):
    c = Client()
    c.cookies["compass_session"] = create_auth_session(user, now=timezone.now()).token
    return c


def test_api_contract_csrf_cache_and_no_source_read(case):
    c = client(case.author)
    raw = {k: v for k, v in case.payload.items() if k not in ["actor", "scopes"]}
    raw["scopes"] = [
        dict(resource_kind=s.resource_kind, source_id=s.source_id, projection=s.projection)
        for s in case.payload["scopes"]
    ]
    data = json.dumps(raw, default=str)
    denied = Client().get(PREFIX)
    assert denied.status_code == 401
    assert denied.headers["Cache-Control"] == "private, no-store"
    c = Client(enforce_csrf_checks=True)
    c.cookies["compass_session"] = create_auth_session(case.author, now=timezone.now()).token
    denied = c.post(PREFIX, data=data, content_type="application/json")
    assert denied.status_code == 403
    author_csrf = c.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = c.post(
        PREFIX, data=data, content_type="application/json", HTTP_X_CSRFTOKEN=author_csrf
    )
    assert response.status_code == 201, response.content
    g = response.json()
    assert response.headers["Cache-Control"] == "private, no-store"
    assert set(g) == set(svc.get_grant_metadata(actor=case.author, grant_id=g["id"]))
    head = client(case.head)
    csrf = head.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = head.post(
        PREFIX + "/" + g["id"] + "/approve",
        data=json.dumps({"expected_version": 1}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200, response.content
    assert response.json()["version"] == 2
    for path in ["/sources", "/sources/" + str(case.routine.pk), "/content", "/export"]:
        r = head.get(PREFIX + "/" + g["id"] + path)
        assert r.status_code == 404 and r.headers["Cache-Control"] == "private, no-store"
    bad = c.post(
        PREFIX,
        data=json.dumps(raw | {"narrative": "DO NOT ACCEPT"}, default=str),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=author_csrf,
    )
    assert bad.status_code == 422 and bad.headers["Cache-Control"] == "private, no-store"
    assert "narrative" not in g


def race(*operations):
    assert connection.vendor == "postgresql"
    barrier = Barrier(len(operations))

    def run(op):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return ("ok", op())
        except ContinuityError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        futures = [pool.submit(run, op) for op in operations]
        return [f.result(timeout=20) for f in futures]


@pytest.mark.parametrize("same_intent", [False, True])
def test_postgresql_concurrent_requests_and_duplicates(case, same_intent):
    outcomes = race(
        lambda: request(case),
        lambda: request(case, request_id=case.payload["request_id"] if same_intent else uuid4()),
    )
    assert Grant.objects.count() == 1
    assert sum(o[0] == "ok" for o in outcomes) == (2 if same_intent else 1)
    assert AuditEvent.objects.filter(action="counseling.continuity.requested").count() == 1
    if not same_intent:
        assert ("error", "continuity_overlap") in outcomes


@pytest.mark.parametrize("second", ["APPROVED", "DECLINED", "CANCELLED"])
def test_postgresql_concurrent_approval_decisions(case, second):
    g = request(case)
    outcomes = race(
        lambda: decide(case, g),
        lambda: decide(case, g, second, actor=case.author if second == "CANCELLED" else case.head),
    )
    assert sum(o[0] == "ok" for o in outcomes) == 1
    assert ("error", "continuity_stale_version") in outcomes
    assert Grant.objects.get(pk=g["id"]).version == 2
    assert AuditEvent.objects.filter(action__startswith="counseling.continuity.").count() == 2


def test_postgresql_stale_approval_vs_revocation_and_metadata(case):
    g = decide(case, request(case))
    outcomes = race(
        lambda: decide(case, g, expected_version=1),
        lambda: decide(case, g, "REVOKED", revocation_reason="COVERAGE_ENDED"),
    )
    assert ("error", "continuity_stale_version") in outcomes
    assert Grant.objects.get(pk=g["id"]).decision == "REVOKED"
    # Separate valid grant for revoke/read serialization.
    g = decide(case, request(case, request_id=uuid4()))
    outcomes = race(
        lambda: svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"]),
        lambda: decide(case, g, "REVOKED", revocation_reason="COVERAGE_ENDED"),
    )
    assert all(o[0] == "ok" for o in outcomes)
    assert outcomes[0][1]["effective_status"] in {"ACTIVE", "REVOKED"}
    assert (
        svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])["effective_status"]
        == "REVOKED"
    )


@pytest.mark.parametrize("change", ["capability", "deactivate"])
def test_postgresql_authority_mutation_serializes(case, change):
    g = request(case)

    def mutate():
        if change == "capability":
            set_user_capability_override(
                user=case.head,
                capability="counseling.continuity.approve",
                effect="REVOKE",
                reason="Concurrent synthetic revoke",
            )
        else:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=case.head.pk)
                user.is_active = False
                user.save(update_fields=["is_active"])

    outcomes = race(lambda: decide(case, g), mutate)
    assert outcomes[1][0] == "ok"
    assert outcomes[0][0] == "ok" or outcomes[0][1] in {
        "continuity_missing_capability",
        "continuity_invalid_role",
    }
    stored = Grant.objects.get(pk=g["id"])
    if stored.decision == "APPROVED":
        assert (
            svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])["effective_status"]
            == "UNAVAILABLE"
        )
    else:
        assert stored.decision == "REQUESTED"


def test_adjacent_intervals_and_different_receiver_policy(case, monkeypatch):
    request(case)
    request(
        case,
        starts_at=case.payload["expires_at"],
        expires_at=case.payload["expires_at"] + timedelta(hours=1),
        request_id=uuid4(),
    )
    with expect("overlap"):
        request(case, receiving_counselor_id=case.outsider.pk, request_id=uuid4())
    monkeypatch.setattr(
        continuity_policy,
        "get_approved_policy",
        lambda: replace(case.policy, overlap_rule="ALLOW_DIFFERENT_RECEIVERS"),
    )
    request(case, receiving_counselor_id=case.outsider.pk, request_id=uuid4())


def test_capability_registration_has_no_automatic_role_or_designation_grants(case):
    from compass.accounts.models import DesignationCapability, RoleCapability

    assert Capability.objects.filter(code__startswith="counseling.continuity.").count() == 5
    assert not RoleCapability.objects.filter(
        capability__code__startswith="counseling.continuity."
    ).exists()
    assert not DesignationCapability.objects.filter(
        capability__code__startswith="counseling.continuity."
    ).exists()


@pytest.mark.parametrize("point", ["request", "approval"])
@pytest.mark.parametrize("identity", ["student", "receiver"])
def test_ineligible_identity_before_mutation(case, point, identity):
    g = request(case) if point == "approval" else None
    user = case.student if identity == "student" else case.receiver
    User.objects.filter(pk=user.pk).update(is_active=False)
    with expect("ineligible_" + identity):
        if g:
            decide(case, g)
        else:
            request(case)


def test_request_requires_verified_relationship_even_with_capability(case):
    with expect("source_not_found"):
        request(case, actor=case.outsider)
    g = request(case)
    with expect("not_found"):
        decide(case, g, "CANCELLED", actor=case.receiver)


def test_unverified_acting_head_with_expiring_override_denied(case, monkeypatch):
    actor = case.outsider
    monkeypatch.setattr(
        continuity_policy,
        "get_approved_policy",
        lambda: replace(case.policy, approver_ids=frozenset([actor.pk])),
    )
    set_user_capability_override(
        user=actor,
        capability="counseling.continuity.approve",
        effect="GRANT",
        reason="Acting label is not institutional evidence",
        expires_at=case.now + timedelta(hours=1),
    )
    g = request(case)
    with expect("approval_authority_missing"):
        decide(case, g, actor=actor)
    UserCapabilityOverride.objects.filter(
        user=actor, capability__code="counseling.continuity.approve"
    ).update(expires_at=case.now - timedelta(seconds=1))
    with expect("missing_capability"):
        decide(case, g, actor=actor)


def test_policy_expiry_and_approval_scope_changed(case, monkeypatch):
    g = request(case)
    monkeypatch.setattr(
        continuity_policy,
        "get_approved_policy",
        lambda: replace(case.policy, valid_until=case.now - timedelta(seconds=1)),
    )
    with expect("policy_unconfirmed"):
        decide(case, g)
    monkeypatch.setattr(continuity_policy, "get_approved_policy", lambda: case.policy)
    StudentAffiliation.objects.filter(student=case.student).update(
        college=case.college_b, updated_at=timezone.now()
    )
    with expect("student_changed"):
        decide(case, g)


def test_postgresql_busy_source_fails_without_deadlock(case):
    from threading import Event

    locked, release = Event(), Event()

    def source_writer():
        close_old_connections()
        try:
            with transaction.atomic():
                CounselingEncounter.objects.select_for_update().get(pk=case.encounter.pk)
                locked.set()
                assert release.wait(timeout=10)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(source_writer)
        assert locked.wait(timeout=10)
        try:
            with expect("source_busy"):
                request(case)
            assert Grant.objects.count() == 0
        finally:
            release.set()
        future.result(timeout=10)
    assert request(case)["version"] == 1


def test_override_expiry_during_selection_is_rechecked_before_approval(case, monkeypatch):
    g = request(case)
    expires = timezone.now() + timedelta(minutes=1)
    UserCapabilityOverride.objects.filter(
        user=case.head, capability__code="counseling.continuity.approve"
    ).update(expires_at=expires)
    original = svc._sources

    def source_check(*args, **kwargs):
        original(*args, **kwargs)
        monkeypatch.setattr(svc.timezone, "now", lambda: expires)

    monkeypatch.setattr(svc, "_sources", source_check)
    with expect("missing_capability"):
        decide(case, g)
    assert Grant.objects.get(pk=g["id"]).decision == "REQUESTED"


def test_timezone_equivalent_snapshots_and_request_replay(case):
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Manila")
    g = request(
        case,
        starts_at=case.payload["starts_at"].astimezone(zone),
        expires_at=case.payload["expires_at"].astimezone(zone),
    )
    assert svc.get_grant_metadata(actor=case.author, grant_id=g["id"])["version"] == 1
    assert request(case)["id"] == g["id"]
    assert decide(case, g)["effective_status"] == "ACTIVE"


@pytest.mark.parametrize("mutation", ["deactivate", "override"])
def test_postgresql_real_account_management_race(case, mutation):
    from compass.account_management.services import set_account_active, set_capability_override
    from compass.audit.context import AuditContext

    manager = case.user("manager", "IT_ADMIN")
    verified_at = timezone.now()
    session = create_auth_session(manager, now=verified_at, mfa_verified_at=verified_at).session
    g = request(case)
    context = AuditContext.user(manager)

    def mutate():
        if mutation == "deactivate":
            return set_account_active(
                actor=manager,
                actor_session=session,
                target_id=case.head.pk,
                context=context,
                is_active=False,
            ).changed
        return set_capability_override(
            actor=manager,
            actor_session=session,
            target_id=case.head.pk,
            context=context,
            capability="counseling.continuity.approve",
            effect="REVOKE",
            reason="Concurrent synthetic revoke",
        ).changed

    outcomes = race(lambda: decide(case, g), mutate)
    assert outcomes[1] == ("ok", True)
    assert outcomes[0][0] == "ok" or outcomes[0][1] in {
        "continuity_invalid_role",
        "continuity_missing_capability",
    }
    assert svc.get_grant_metadata(actor=case.receiver, grant_id=g["id"])["effective_status"] in {
        "PENDING",
        "UNAVAILABLE",
    }


def test_default_policy_http_denial_has_no_store(case, monkeypatch):
    monkeypatch.setattr(continuity_policy, "get_approved_policy", lambda: None)
    response = client(case.author).get(PREFIX)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "continuity_policy_unconfirmed"
    assert response.headers["Cache-Control"] == "private, no-store"


def test_approved_grant_never_bypasses_ordinary_content_or_mutation(case, monkeypatch):
    from compass.confidential_data import crypto
    from compass.counseling.models import StudentSessionSummary

    g = decide(case, request(case))
    StudentSessionSummary.objects.create(
        encounter=case.encounter, content_ciphertext="UNREADABLE-SYNTHETIC-SUMMARY"
    )
    c = client(case.receiver)
    csrf = c.get("/api/v1/auth/csrf").json()["csrf_token"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Grant must not decrypt source content")

    monkeypatch.setattr(crypto, "decrypt_bound_json", forbidden)
    before = [
        list(model.objects.values())
        for model in [CounselingEncounter, RoutineInterview, StudentSessionSummary]
    ]
    encounter = "/api/v1/counseling/encounters/" + str(case.encounter.pk)
    routine = "/api/v1/routine-interviews/" + str(case.routine.pk)
    for path in [encounter, routine, encounter + "/student-session-summary"]:
        response = c.get(path, {"grant_id": str(g["id"])})
        assert response.status_code in {403, 404}, response.content
    for method, path, payload in [
        ("patch", encounter, {"ended_at": case.encounter.ended_at.isoformat()}),
        ("put", routine + "/evaluation", {}),
        ("put", encounter + "/student-session-summary", {"content": "UNAUTHORIZED"}),
    ]:
        response = getattr(c, method)(
            path, data=json.dumps(payload), content_type="application/json", HTTP_X_CSRFTOKEN=csrf
        )
        assert response.status_code in {403, 404}, response.content
    assert [
        list(model.objects.values())
        for model in [CounselingEncounter, RoutineInterview, StudentSessionSummary]
    ] == before


def test_audit_actor_spoof_rolls_back(case):
    from compass.audit.context import AuditContext

    with pytest.raises(ValueError, match="match the acting user"):
        request(case, context=AuditContext.user(case.outsider))
    assert Grant.objects.count() == 0
