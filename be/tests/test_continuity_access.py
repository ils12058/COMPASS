"""Selected reads under live authority and fixed field inventories."""

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    Role,
    RoleCapability,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.audit.models import AuditEvent
from compass.confidential_data import crypto
from compass.counseling import continuity_access as access
from compass.counseling import coverage_selection, handoff_services
from compass.counseling.continuity_encounters import read_selected_encounter_for_continuity
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_models import CounselorCaseContinuityScope as Scope
from compass.counseling.continuity_rules import ENCOUNTER_METADATA_FIELDS, ContinuityError
from compass.counseling.models import CounselingEncounter
from compass.guidance_messages import services as messages
from compass.guidance_messages.errors import CaseCoordinationEnded, ThreadNotFound
from compass.organization.models import CounselorResponsibility, StaffSupervision
from compass.routine_interviews import content
from compass.routine_interviews.continuity import read_selected_evaluation_for_continuity
from compass.routine_interviews.crypto import RoutineContentSection, encrypt_section
from compass.routine_interviews.models import RoutineInterview
from compass.student_academics.models import StudentAcademicProfile
from tests import test_continuity as foundation_tests
from tests.test_continuity import client, decide, request

metadata_case = foundation_tests.case
synthetic_case = foundation_tests.synthetic_case

pytestmark = pytest.mark.django_db(transaction=True)
SENTINEL = "SYNTHETIC-PROFESSIONAL-CONTENT-NOT-FOR-ERRORS"


@pytest.fixture
def mutable_selected_case(selected_case):
    return selected_case


@pytest.fixture
def selected_case(metadata_case):
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
    assert result["grant_version"] == 2
    if kind == "ENCOUNTER":
        assert set(result["encounter"]) == ENCOUNTER_METADATA_FIELDS
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


@pytest.mark.parametrize("role", ["IT_ADMIN", "GUIDANCE_OFFICE_ASSISTANT", "INSTITUTIONAL_OFFICER"])
def test_unsupported_roles_with_unusual_capabilities(selected_case, role, monkeypatch):
    c = selected_case
    g = approved(c)
    user = c.user("unsupported", role)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with expect("invalid_role"):
        read(c, g, actor=user)


def test_cross_college_and_legitimate_head_receiver(mutable_selected_case):
    c = mutable_selected_case
    CounselorResponsibility.objects.create(college=c.college_b, counselor=c.receiver)
    g = approved(c)
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    decide(c, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
    UserDesignation.objects.create(
        user=c.outsider, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
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
    ],
)
def test_current_authority_rechecked_before_decrypt(mutable_selected_case, monkeypatch, change):
    c = mutable_selected_case
    g = approved(c)
    if change == "inactive":
        User.objects.filter(pk=c.receiver.pk).update(is_active=False)
    elif change == "role":
        User.objects.filter(pk=c.receiver.pk).update(
            role=Role.objects.get(code="GUIDANCE_OFFICE_ASSISTANT")
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
        RoleCapability.objects.filter(
            role__code="COUNSELOR", capability__code="counseling.continuity.read_selected"
        ).delete()
        UserCapabilityOverride.objects.filter(
            user=c.receiver, capability__code="counseling.continuity.read_selected"
        ).update(expires_at=c.now - timedelta(seconds=1))
    elif change == "transfer":
        StudentAcademicProfile.objects.filter(student=c.student).update(
            current_college=c.college_b, updated_at=timezone.now()
        )
    elif change == "former":
        User.objects.filter(pk=c.student.pk).update(student_lifecycle_status="FORMER")
    elif change == "student_inactive":
        User.objects.filter(pk=c.student.pk).update(is_active=False)
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
        assert set(read(c, g, "ENCOUNTER")["encounter"]) == ENCOUNTER_METADATA_FIELDS
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


def test_real_head_receiver_outsider_and_expiry(selected_case, monkeypatch):
    c = selected_case
    UserCapabilityOverride.objects.all().delete()
    assert c.head.has_capability("counseling.continuity.approve")
    assert c.receiver.has_capability("counseling.continuity.read_selected")
    g = decide(c, request(c, communication_purpose="CASE_COORDINATION"))
    assert g["effective_status"] == "ACTIVE"
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    d = handoff_services.operate(
        actor=c.author,
        grant_id=g["id"],
        operation="save",
        expected_grant_version=g["version"],
        expected_version=0,
        body="Synthetic handoff",
    )
    handoff_services.operate(
        actor=c.author,
        grant_id=g["id"],
        operation="submit",
        expected_grant_version=g["version"],
        expected_version=d["version"],
    )
    assert (
        handoff_services.operate(
            actor=c.receiver,
            grant_id=g["id"],
            operation="receive",
            expected_grant_version=g["version"],
        )["content"]
        == "Synthetic handoff"
    )
    thread, _ = messages.open_case_coordination_thread(
        actor=c.author, grant_id=g["id"], client_message_id=uuid4(), body="Synthetic coordination"
    )
    assert messages.list_messages(actor=c.receiver, thread_id=thread.pk)[0]
    with pytest.raises(ContinuityError):
        read(c, g, actor=c.outsider)
    with pytest.raises(ThreadNotFound):
        messages.get_thread(actor=c.outsider, thread_id=thread.pk)
    moment = g["expires_at"]
    monkeypatch.setattr(timezone, "now", lambda: moment)
    for actor in (c.author, c.receiver):
        with pytest.raises(CaseCoordinationEnded):
            messages.list_messages(actor=actor, thread_id=thread.pk)
        with pytest.raises(ContinuityError):
            handoff_services.operate(
                actor=actor,
                grant_id=g["id"],
                operation="receive",
                expected_grant_version=g["version"],
            )
    with pytest.raises(ContinuityError):
        read(c, g)


def test_assistant_request_uses_live_responsibility_and_independent_head(selected_case):
    c = selected_case
    assistant = c.user("office-assistant", "GUIDANCE_OFFICE_ASSISTANT")
    UserCapabilityOverride.objects.all().delete()
    StaffSupervision.objects.create(staff=assistant, supervisor=c.author)
    CounselorResponsibility.objects.create(college=c.college, counselor=c.author)
    config = coverage_selection.configuration(actor=assistant)
    assert config["can_request"] and not config["can_approve"]
    assert {x["student_id"] for x in config["office_cases"]} == {c.student.pk}
    assert (
        len(
            coverage_selection.select(
                actor=assistant, student_id=c.student.pk, original_counselor_id=c.author.pk
            )["items"]
        )
        == 2
    )
    g = request(c, actor=assistant, coverage_kind="TEMPORARY_COVERAGE")
    with pytest.raises(ContinuityError):
        decide(c, g, actor=assistant)
    assert decide(c, g)["effective_status"] == "ACTIVE"
    CounselorResponsibility.objects.filter(college=c.college).delete()
    assert coverage_selection.configuration(actor=assistant)["office_cases"] == []
    with pytest.raises(ContinuityError):
        coverage_selection.select(
            actor=assistant, student_id=c.student.pk, original_counselor_id=c.author.pk
        )


def test_demo_coverage_uses_real_services_and_does_not_extend_expiry(selected_case):
    from types import SimpleNamespace

    from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
    from compass.staging_seed.scenarios.continuity import DEMO_REQUEST_ID, seed_demo_coverage
    from compass.staging_seed.staff import COUNSELOR_A, COUNSELOR_B, HEAD_GUIDANCE
    from compass.staging_seed.students import FOURTH_YEAR

    c = selected_case
    UserCapabilityOverride.objects.all().delete()
    users = {
        COUNSELOR_A.key: c.author,
        COUNSELOR_B.key: c.receiver,
        HEAD_GUIDANCE.key: c.head,
        FOURTH_YEAR.key: c.student,
    }
    records = []
    session = SimpleNamespace(user=users.__getitem__, record=lambda name, **kw: records.append(kw))
    seed_demo_coverage(session)
    grant = Grant.objects.get(request_id=DEMO_REQUEST_ID)
    expiry = grant.expires_at
    assert grant.decision == "APPROVED" and grant.communication_purpose == "CASE_COORDINATION"
    assert (
        read(c, {"id": grant.pk, "version": grant.version})["evaluation"]["recommendations"]
        == SENTINEL
    )
    seed_demo_coverage(session)
    grant.refresh_from_db()
    assert grant.expires_at == expiry and records == [{"created": True}, {"created": False}]


def test_completed_approval_survives_live_head_turnover(selected_case):
    from compass.counseling.case_communication import authorize_case_coordination
    from compass.counseling.continuity_rules import active_college_ids, is_head, is_office_requester

    c = selected_case
    UserCapabilityOverride.objects.all().delete()
    g = approved(c, communication_purpose="CASE_COORDINATION")
    UserDesignation.objects.filter(user=c.head).delete()
    User.objects.filter(pk=c.head.pk).update(is_active=False)
    c.head.refresh_from_db()
    new_head = c.user("new-head")
    assistant = c.user("new-assistant", "GUIDANCE_OFFICE_ASSISTANT")
    UserCapabilityOverride.objects.all().delete()
    UserDesignation.objects.create(
        user=new_head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    added = foundation_tests.College.objects.create(campus=c.campus, code="NEW", name="New")
    assert is_head(new_head) and not is_head(c.head)
    assert is_office_requester(assistant) and added.pk in active_college_ids()
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    authorize_case_coordination(actor=c.receiver, grant_id=g["id"])
    with pytest.raises(ContinuityError):
        decide(c, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
    decide(c, g, "REVOKED", actor=new_head, revocation_reason="COVERAGE_ENDED")
    with pytest.raises(ContinuityError):
        read(c, g)


@pytest.mark.parametrize("entity", ["college", "campus"])
def test_active_college_and_campus_membership_rechecked(selected_case, entity):
    c = selected_case
    g = approved(c)
    target = c.college if entity == "college" else c.campus
    type(target).objects.filter(pk=target.pk).update(is_active=False)
    with pytest.raises(ContinuityError):
        read(c, g)
    with pytest.raises(ContinuityError, match="ineligible_student"):
        request(c, request_id=uuid4())


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT", "FACULTY"])
def test_office_capability_does_not_replace_live_membership(selected_case, role):
    c = selected_case
    if role == "FACULTY":
        actor = User.objects.create_user(
            email="office-impostor@synthetic.test",
            role=role,
            password=None,
            first_name="Synthetic",
            last_name="Faculty",
        )
        # The capability ceiling also forbids granting continuity permissions to Faculty.
        with pytest.raises(ValueError, match="Faculty Role"):
            foundation_tests.grant_caps(actor)
    else:
        actor = c.user("office-impostor", role)
    # Continuity capabilities never replace Counselor/office membership.
    if role == "GUIDANCE_OFFICE_ASSISTANT":
        StaffSupervision.objects.create(staff=actor, supervisor=c.author)
        CounselorResponsibility.objects.create(college=c.college, counselor=c.author)
        g = request(c, actor=actor)
        assert decide(c, g)["effective_status"] == "ACTIVE"
        StaffSupervision.objects.filter(staff=actor).delete()
    with pytest.raises(ContinuityError):
        coverage_selection.select(
            actor=actor, student_id=c.student.pk, original_counselor_id=c.author.pk
        )
    with pytest.raises(ContinuityError):
        read(c, {"id": uuid4(), "version": 2}, actor=actor)
