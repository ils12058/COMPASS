"""Institutional, authorization, confidentiality and correction proofs on PostgreSQL."""

import base64
import json
from dataclasses import asdict
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import Capability, Designation, Role, User, UserCapabilityOverride
from compass.accounts.policy import CAPABILITY_DEPENDENCIES, ROLE_CAPABILITY_GRANTS
from compass.assessment_records import confidential_content as content
from compass.assessment_records import services
from compass.assessment_records.errors import (
    AssessmentRecordAccessDenied,
    AssessmentRecordConflict,
    AssessmentRecordNotFound,
    InvalidAssessmentRecordInput,
)
from compass.assessment_records.models import StudentAssessmentRecord
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from compass.confidential_data import crypto
from compass.organization.models import Campus, College, CounselorResponsibility, StudentAffiliation
from tests.test_notifications import auth_client

pytestmark = pytest.mark.django_db
BASE = "/api/v1/assessment-records"
PAYLOAD = {key: "SENTINEL_" + key.upper() for key in content.CONTENT_LIMITS}
# Fixed synthetic keys, never deployment configuration.
OLD = base64.urlsafe_b64encode(b"a" * 32).decode()
NEW = base64.urlsafe_b64encode(b"b" * 32).decode()


@pytest.fixture
def world():
    sync_identity_policy()

    def user(name, role):
        return User.objects.create_user(
            email=f"assessment-{name}@example.edu",
            password=None,
            role=Role.objects.get(code=role),
            first_name="Synthetic",
            middle_name="Middle",
            last_name=name,
            institutional_id=f"ASSESSMENT-{name}",
        )

    head = user("head", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    ordinary = user("ordinary", "COUNSELOR")
    gss = user("staff", "GUIDANCE_SERVICES_STAFF")
    admin = user("admin", "IT_ADMIN")
    dpo = user("dpo", "INSTITUTIONAL_OFFICER")
    dpo.designations.add(Designation.objects.get(code="DPO"))
    student = user("student", "STUDENT")
    other_student = user("other", "STUDENT")
    campus = Campus.objects.create(code="AS", name="Synthetic Campus")
    college_a = College.objects.create(campus=campus, code="AS-A", name="College A")
    college_b = College.objects.create(campus=campus, code="AS-B", name="College B")
    CounselorResponsibility.objects.create(counselor=ordinary, college=college_a)
    StudentAffiliation.objects.create(student=student, college=college_a)
    StudentAffiliation.objects.create(student=other_student, college=college_b)
    assessment_type = services.create_type(actor=head, values={"name": "Career Aptitude Test"})
    return SimpleNamespace(**locals())


def values(world, **changes):
    return {
        "student_id": world.student.pk,
        "assessment_type_id": world.assessment_type.pk,
        "administered_on": institution_today(),
        **PAYLOAD,
        **changes,
    }


def record(world, **changes):
    return services.create_record(actor=world.head, values=values(world, **changes))[0]


def grant(user):
    for code in ("assessment_records.view", "assessment_records.manage"):
        UserCapabilityOverride.objects.create(
            user=user,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic exception",
        )


def test_head_designation_grants_and_dependency_only(world):
    assert world.head.has_capability("assessment_records.view")
    assert world.head.has_capability("assessment_records.manage")
    assert CAPABILITY_DEPENDENCIES["assessment_records.manage"] == {"assessment_records.view"}
    assert not any(
        "assessment_records.view" in grants for grants in ROLE_CAPABILITY_GRANTS.values()
    )
    assert not world.ordinary.has_capability("assessment_records.view")
    assert auth_client(world.head).get(BASE).status_code == 200


@pytest.mark.parametrize("actor", ["ordinary", "gss", "student", "admin", "dpo"])
def test_baseline_unsupported_access_denied(world, actor):
    user = getattr(world, actor)
    item = record(world)
    client = auth_client(user)
    assert client.get(BASE).status_code == 403
    assert client.get(f"{BASE}/{item.pk}").status_code == 403
    assert client.get(BASE + "/types").status_code == 403
    with pytest.raises(AssessmentRecordAccessDenied):
        services.get_record(actor=user, record_id=item.pk)


@pytest.mark.parametrize("actor", ["gss", "student", "admin", "dpo"])
def test_role_fence_survives_unusual_override(world, actor):
    user = getattr(world, actor)
    grant(user)
    assert auth_client(user).get(BASE).status_code == 403
    with pytest.raises(AssessmentRecordAccessDenied):
        services.create_record(actor=user, values=values(world))


def test_inactive_stale_and_changed_identity_and_anonymous(world):
    client = auth_client(world.head)
    User.objects.filter(pk=world.head.pk).update(is_active=False)
    assert client.get(BASE).status_code == 401
    with pytest.raises(AssessmentRecordAccessDenied):
        services.list_records(actor=world.head)
    User.objects.filter(pk=world.head.pk).update(is_active=True, role=world.gss.role)
    assert client.get(BASE).status_code == 403
    with pytest.raises(AssessmentRecordAccessDenied):
        services.list_records(actor=world.head)
    assert Client().get(BASE).status_code == 401


def test_ordinary_override_is_scoped_and_catalog_management_head_only(world):
    a, b = record(world), record(world, student_id=world.other_student.pk)
    grant(world.ordinary)
    client = auth_client(world.ordinary)
    assert [row["id"] for row in client.get(BASE).json()["items"]] == [str(a.pk)]
    assert client.get(f"{BASE}/{a.pk}").status_code == 200
    assert client.get(f"{BASE}/{b.pk}").status_code == 404
    assert (
        client.patch(
            f"{BASE}/{b.pk}", data=json.dumps({"score": "changed"}), content_type="application/json"
        ).status_code
        == 404
    )
    assert len(services.list_records(actor=world.head)["items"]) == 2
    assert (
        services.create_record(actor=world.ordinary, values=values(world))[0].student_id
        == a.student_id
    )
    with pytest.raises(AssessmentRecordNotFound):
        services.create_record(actor=world.ordinary, values=values(world, student_id=b.student_id))
    with pytest.raises(AssessmentRecordAccessDenied):
        services.create_type(actor=world.ordinary, values={"name": "Restricted catalog write"})


@pytest.mark.parametrize("target", ["college", "campus", "responsibility"])
def test_inactive_or_removed_responsibility_conceals_record(world, target):
    item = record(world)
    grant(world.ordinary)
    if target == "college":
        College.objects.filter(pk=world.college_a.pk).update(is_active=False)
    elif target == "campus":
        Campus.objects.filter(pk=world.campus.pk).update(is_active=False)
    else:
        CounselorResponsibility.objects.filter(counselor=world.ordinary).delete()
    with pytest.raises(AssessmentRecordNotFound):
        services.get_record(actor=world.ordinary, record_id=item.pk)
    assert services.list_records(actor=world.ordinary)["items"] == []


def test_structural_list_never_selects_or_decrypts_result(world, monkeypatch):
    item = record(world)
    client = auth_client(world.head)

    def forbidden(*args, **kwargs):
        raise AssertionError("List must not decrypt")

    monkeypatch.setattr(services, "read_confidential_content", forbidden)
    monkeypatch.setattr(crypto, "decrypt_bound_json", forbidden)
    with CaptureQueriesContext(connection) as queries:
        response = client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == str(item.pk)
    assert not set(PAYLOAD).intersection(body["items"][0])
    assert "assessment_records_studentassessmentrecord" in " ".join(q["sql"] for q in queries)
    assert (
        '"assessment_records_studentassessmentrecord"."confidential_content_ciphertext"'
        not in " ".join(q["sql"] for q in queries)
    )
    assert not any(sentinel in response.content.decode() for sentinel in PAYLOAD.values())


def test_raw_database_and_initial_model_have_no_plaintext_columns(world, caplog):
    item = record(world)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT row_to_json(r)::text "
            "FROM assessment_records_studentassessmentrecord r WHERE id=%s",
            [item.pk],
        )
        raw = cursor.fetchone()[0]
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, item._meta.db_table
            )
        }
    assert not set(PAYLOAD).intersection(columns)
    assert not any(value in raw for value in PAYLOAD.values())
    assert set(columns) == {
        "id",
        "student_id",
        "assessment_type_id",
        "administered_on",
        "confidential_content_ciphertext",
        "recorded_by_id",
        "created_at",
        "updated_at",
    }
    assert not any(value in caplog.text for value in PAYLOAD.values())
    with pytest.raises(IntegrityError), transaction.atomic():
        StudentAssessmentRecord.objects.filter(pk=item.pk).update(
            confidential_content_ciphertext=""
        )


def test_detail_authorizes_before_decryption_and_is_bounded(world, monkeypatch):
    item = record(world)
    client = auth_client(world.head)
    result = client.get(f"{BASE}/{item.pk}")
    assert result.status_code == 200
    assert all(result.json()[key] == value for key, value in PAYLOAD.items())
    assert "ciphertext" not in result.content.decode()

    def unavailable(*args, **kwargs):
        raise content.AssessmentRecordConfidentialContentUnavailable(reason="undecryptable")

    monkeypatch.setattr(services, "read_confidential_content", unavailable)
    assert client.get(BASE).status_code == 200
    response = client.get(f"{BASE}/{item.pk}")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "assessment_record_content_unavailable"
    assert not any(value in response.content.decode() for value in PAYLOAD.values())
    assert auth_client(world.student).get(f"{BASE}/{item.pk}").status_code == 403


@pytest.mark.parametrize("field", ["student_id", "assessment_type_id", "id"])
def test_ciphertext_cannot_move_between_students_types_or_records(world, field):
    original = record(world)
    rebound = record(world)
    if field == "student_id":
        original.student_id = world.other_student.pk
    elif field == "assessment_type_id":
        original.assessment_type_id = services.create_type(
            actor=world.head, values={"name": "Other Type"}
        ).pk
    else:
        original.pk = rebound.pk
    with pytest.raises(content.AssessmentRecordConfidentialContentUnavailable) as caught:
        content.read_confidential_content(original)
    assert caught.value.reason == "binding_mismatch"
    exposed = repr(caught.value) + str(caught.value)
    assert not any(
        value in exposed for value in [*PAYLOAD.values(), original.confidential_content_ciphertext]
    )


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("invalid", "undecryptable"),
        ("missing", "missing"),
        ("extra", "malformed"),
        ("nonstring", "malformed"),
        ("blank", "malformed"),
        ("version", "unsupported_schema"),
    ],
)
def test_malformed_content_is_not_released(world, damage, reason):
    item = record(world)
    if damage in {"missing", "invalid"}:
        item.confidential_content_ciphertext = "" if damage == "missing" else "not-fernet"
    else:
        payload = dict(PAYLOAD)
        if damage == "extra":
            payload["extra"] = "forbidden"
        if damage == "nonstring":
            payload["score"] = 82
        if damage == "blank":
            payload = {key: " " for key in PAYLOAD}
        from django.conf import settings

        item.confidential_content_ciphertext = crypto.encrypt_bound_json(
            keyring=getattr(settings, content.KEYRING_SETTING),
            schema_version=2 if damage == "version" else 1,
            binding={
                "assessment_record_id": str(item.pk),
                "student_id": str(item.student_id),
                "assessment_type_id": str(item.assessment_type_id),
            },
            payload=payload,
        )
    with pytest.raises(content.AssessmentRecordConfidentialContentUnavailable) as caught:
        content.read_confidential_content(item)
    assert caught.value.reason == reason


@pytest.mark.parametrize(
    "score",
    [
        "82",
        "82/100",
        "91st percentile",
        "Stanine 7",
        "Above Average",
        "Profile A",
        "  Source\ntext  ",
    ],
)
def test_source_score_text_is_preserved(world, score):
    item = record(world, score=score)
    assert content.read_confidential_content(item).score == score


@pytest.mark.parametrize(
    "changes",
    [
        {key: " " for key in PAYLOAD},
        {"score": "\x00"},
        {"result": "\ud800"},
        {"score": "x" * 501},
        {"result": "x" * 4001},
        {"interpretation": "x" * 8001},
        {"remarks": "x" * 4001},
        {"administered_on": institution_today() + timedelta(days=1)},
        {"score": 82},
    ],
)
def test_invalid_content_or_date_rejected_before_persistence(world, changes):
    with pytest.raises(InvalidAssessmentRecordInput):
        record(world, **changes)
    assert StudentAssessmentRecord.objects.count() == 0
    assert not AuditEvent.objects.filter(action="assessment_record.created").exists()


def test_picker_is_narrow_current_active_student_and_structural_search(world):
    grant(world.ordinary)
    for field in ("institutional_id", "first_name", "middle_name", "last_name"):
        needle = getattr(world.student, field)
        result = services.eligible_students(actor=world.ordinary, search=needle)
        assert [row.id for row in result.items] == [world.student.pk]
    assert len(services.eligible_students(actor=world.head).items) == 2
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    User.objects.filter(pk=world.other_student.pk).update(is_active=False)
    assert services.eligible_students(actor=world.head).items == ()
    for student in (world.student, world.other_student, world.gss):
        with pytest.raises(AssessmentRecordNotFound):
            record(world, student_id=student.pk)


@pytest.mark.parametrize("active", [True, False])
def test_historical_students_remain_readable_after_graduation(world, active):
    item = record(world)
    User.objects.filter(pk=world.student.pk).update(
        student_lifecycle_status="GRADUATED", is_active=active
    )
    assert (
        services.get_record(actor=world.head, record_id=item.pk)[0].student_id == world.student.pk
    )
    assert services.list_records(actor=world.head)["items"][0].pk == item.pk
    assert world.student.pk not in [
        row.id for row in services.eligible_students(actor=world.head).items
    ]


def test_catalog_lifecycle_and_historical_inactive_types(world):
    item = record(world)
    assessment_type = services.update_type(
        actor=world.head,
        type_id=world.assessment_type.pk,
        values={"name": "Corrected Name", "description": "Catalog description", "is_active": False},
    )
    assert not assessment_type.is_active
    assert (
        services.get_record(actor=world.head, record_id=item.pk)[0].assessment_type.name
        == "Corrected Name"
    )
    assert services.list_types(actor=world.head, active_only=True) == []
    with pytest.raises(InvalidAssessmentRecordInput):
        record(world)
    with pytest.raises(ProtectedError):
        assessment_type.delete()
    services.update_type(actor=world.head, type_id=assessment_type.pk, values={"is_active": True})
    assert record(world).assessment_type_id == assessment_type.pk


@pytest.mark.parametrize(
    "name", ["", "   ", "bad\nname", "bad\x00name", "bad\x7fname", "bad\ud800"]
)
def test_catalog_name_rejects_blank_controls_and_invalid_unicode(world, name):
    with pytest.raises(InvalidAssessmentRecordInput):
        services.create_type(actor=world.head, values={"name": name})


def test_obvious_duplicate_catalog_names_and_noop(world):
    with pytest.raises(AssessmentRecordConflict):
        services.create_type(actor=world.head, values={"name": " career  aptitude TEST "})
    before = world.assessment_type.updated_at
    audits = AuditEvent.objects.count()
    after = services.update_type(
        actor=world.head,
        type_id=world.assessment_type.pk,
        values={"name": world.assessment_type.name},
    )
    assert after.updated_at == before and AuditEvent.objects.count() == audits


def test_atomic_correction_type_rebinding_provenance_and_noop(world):
    item = record(world)
    original_token = item.confidential_content_ciphertext
    original_created = item.created_at
    other_type = services.create_type(actor=world.head, values={"name": "Interest Inventory"})
    item, projected = services.update_record(
        actor=world.head,
        record_id=item.pk,
        values={
            "score": "Corrected source score",
            "assessment_type_id": other_type.pk,
            "administered_on": institution_today() - timedelta(days=90),
        },
    )
    assert item.confidential_content_ciphertext != original_token
    assert item.recorded_by_id == world.head.pk and item.created_at == original_created
    assert projected.score == "Corrected source score" and projected.result == PAYLOAD["result"]
    assert content.read_confidential_content(item) == projected
    item.assessment_type_id = world.assessment_type.pk
    with pytest.raises(content.AssessmentRecordConfidentialContentUnavailable):
        content.read_confidential_content(item)
    item.refresh_from_db()
    before = (item.updated_at, item.confidential_content_ciphertext, AuditEvent.objects.count())
    after, _ = services.update_record(actor=world.head, record_id=item.pk, values={})
    assert (
        after.updated_at,
        after.confidential_content_ciphertext,
        AuditEvent.objects.count(),
    ) == before
    with pytest.raises(InvalidAssessmentRecordInput):
        services.update_record(
            actor=world.head, record_id=item.pk, values={"student_id": world.other_student.pk}
        )
    assert StudentAssessmentRecord.objects.get(pk=item.pk).student_id == world.student.pk


def test_corrupt_ciphertext_cannot_be_repaired_by_patch(world):
    item = record(world)
    StudentAssessmentRecord.objects.filter(pk=item.pk).update(
        confidential_content_ciphertext="invalid"
    )
    before = AuditEvent.objects.count()
    with pytest.raises(content.AssessmentRecordConfidentialContentUnavailable):
        services.update_record(actor=world.head, record_id=item.pk, values={"score": "replacement"})
    assert (
        StudentAssessmentRecord.objects.get(pk=item.pk).confidential_content_ciphertext == "invalid"
    )
    assert AuditEvent.objects.count() == before


def test_structural_filters_ordering_pagination_and_bad_range(world, monkeypatch):
    first = record(world, administered_on=institution_today() - timedelta(days=2))
    second = record(
        world,
        student_id=world.other_student.pk,
        administered_on=institution_today() - timedelta(days=1),
    )
    third = record(world)

    def forbidden(*args, **kwargs):
        raise AssertionError("No filter may decrypt")

    monkeypatch.setattr(services, "read_confidential_content", forbidden)

    def ids(**query):
        return [row.pk for row in services.list_records(actor=world.head, **query)["items"]]

    assert ids() == [third.pk, second.pk, first.pk]
    assert ids(ordering="OLDEST_ADMINISTERED") == [first.pk, second.pk, third.pk]
    assert ids(search="ASSESSMENT-other") == [second.pk]
    assert ids(assessment_type_id=world.assessment_type.pk) == [third.pk, second.pk, first.pk]
    assert ids(student_id=world.student.pk) == [third.pk, first.pk]
    assert ids(
        administered_from=second.administered_on, administered_to=second.administered_on
    ) == [second.pk]
    assert ids(search="SENTINEL") == []
    assert ids(page=2, page_size=1) == [second.pk]
    assert services.list_records(actor=world.head, page_size=1)["has_next"]
    assert not services.list_records(actor=world.head, page=3, page_size=1)["has_next"]
    for query in (
        {"page": 0},
        {"page_size": 51},
        {"ordering": "score"},
        {"administered_from": institution_today(), "administered_to": first.administered_on},
    ):
        with pytest.raises(InvalidAssessmentRecordInput):
            ids(**query)


def test_audit_metadata_api_and_logs_exclude_result_content(world, caplog):
    item = record(world)
    services.update_record(
        actor=world.head, record_id=item.pk, values={"remarks": "corrected remark"}
    )
    for event in AuditEvent.objects.filter(action__startswith="assessment_record."):
        assert event.metadata == {"assessment_type_id": str(world.assessment_type.pk)}
        assert event.target_id == str(item.pk)
        assert not any(value in json.dumps(event.metadata) for value in PAYLOAD.values())
    assert not any(value in caplog.text for value in PAYLOAD.values())
    client = auth_client(world.head)
    assert client.delete(f"{BASE}/{item.pk}").status_code == 405
    assert client.get(BASE + "/me").status_code in {404, 422}
    assert (
        client.patch(
            f"{BASE}/{item.pk}",
            data=json.dumps({"student_id": str(world.other_student.pk)}),
            content_type="application/json",
        ).status_code
        == 422
    )


def test_first_key_older_reads_rotation_and_stable_metadata(world):
    with override_settings(**{content.KEYRING_SETTING: (OLD,)}):
        item = record(world)
    before = (item.created_at, item.updated_at, item.recorded_by_id, AuditEvent.objects.count())
    with override_settings(**{content.KEYRING_SETTING: (NEW, OLD)}):
        assert asdict(content.read_confidential_content(item)) == PAYLOAD
        new = record(world)
        Fernet(NEW).decrypt(new.confidential_content_ciphertext.encode())
        with pytest.raises(InvalidToken):
            Fernet(OLD).decrypt(new.confidential_content_ciphertext.encode())
        output = StringIO()
        call_command(
            "rotate_assessment_record_confidential_content",
            dry_run=True,
            batch_size=1,
            stdout=output,
        )
        item.refresh_from_db()
        assert not content.encrypted_with_primary_key(item.confidential_content_ciphertext)
        assert "needing rotation 1" in output.getvalue()
        audit_count = AuditEvent.objects.count()
        output = StringIO()
        with CaptureQueriesContext(connection) as queries:
            call_command(
                "rotate_assessment_record_confidential_content", batch_size=1, stdout=output
            )
        assert any("FOR UPDATE" in query["sql"] for query in queries)
        item.refresh_from_db()
        assert content.encrypted_with_primary_key(item.confidential_content_ciphertext)
        assert asdict(content.read_confidential_content(item)) == PAYLOAD
        assert (item.created_at, item.updated_at, item.recorded_by_id) == before[:3]
        assert AuditEvent.objects.count() == audit_count
        call_command("rotate_assessment_record_confidential_content", batch_size=1, stdout=output)
        assert "rotated 0" in output.getvalue()
        assert not any(
            value in output.getvalue()
            for value in [*PAYLOAD.values(), OLD, NEW, item.confidential_content_ciphertext]
        )


def test_rotation_validates_even_primary_key_tokens_and_preserves_corrupt_rows(world):
    item = record(world)
    StudentAssessmentRecord.objects.filter(pk=item.pk).update(
        confidential_content_ciphertext="corrupt-token"
    )
    output, errors = StringIO(), StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_assessment_record_confidential_content", stdout=output, stderr=errors)
    assert (
        StudentAssessmentRecord.objects.get(pk=item.pk).confidential_content_ciphertext
        == "corrupt-token"
    )
    assert "undecryptable" in errors.getvalue()
    assert "corrupt-token" not in errors.getvalue()
    with pytest.raises(CommandError):
        call_command("rotate_assessment_record_confidential_content", batch_size=0)


def test_keyless_nonweb_confidential_access_fails_closed_while_list_works(world):
    item = record(world)
    with override_settings(**{content.KEYRING_SETTING: ()}):
        assert auth_client(world.head).get(BASE).status_code == 200
        assert auth_client(world.head).get(f"{BASE}/{item.pk}").status_code == 500
        with pytest.raises(content.AssessmentRecordConfidentialContentUnavailable):
            record(world)


def test_authorization_and_scope_fail_before_result_accessor(world, monkeypatch):
    item = record(world, student_id=world.other_student.pk)
    grant(world.ordinary)

    def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized access invoked the confidential accessor")

    monkeypatch.setattr(services, "read_confidential_content", forbidden)
    with pytest.raises(AssessmentRecordNotFound):
        services.get_record(actor=world.ordinary, record_id=item.pk)
    with pytest.raises(AssessmentRecordNotFound):
        services.update_record(actor=world.ordinary, record_id=item.pk, values={"score": "x"})
    with pytest.raises(AssessmentRecordAccessDenied):
        services.get_record(actor=world.admin, record_id=item.pk)


def test_persistence_and_correction_roll_back_when_audit_fails(world, monkeypatch):
    item = record(world)
    original = (item.confidential_content_ciphertext, item.updated_at)

    def failed_audit(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(services, "record_event", failed_audit)
    with pytest.raises(RuntimeError):
        record(world)
    assert StudentAssessmentRecord.objects.count() == 1
    with pytest.raises(RuntimeError):
        services.update_record(actor=world.head, record_id=item.pk, values={"score": "corrected"})
    item.refresh_from_db()
    assert (item.confidential_content_ciphertext, item.updated_at) == original


def test_rotation_rejects_invalid_payload_even_when_token_uses_primary_key(world):
    item = record(world)
    token = crypto.encrypt_bound_json(
        keyring=content._keyring(),
        schema_version=content.SCHEMA_VERSION,
        binding=content._binding(item),
        payload={**PAYLOAD, "score": 88},
    )
    StudentAssessmentRecord.objects.filter(pk=item.pk).update(confidential_content_ciphertext=token)
    assert content.encrypted_with_primary_key(token)
    errors = StringIO()
    with pytest.raises(CommandError):
        call_command(
            "rotate_assessment_record_confidential_content", stdout=StringIO(), stderr=errors
        )
    item.refresh_from_db()
    assert item.confidential_content_ciphertext == token
    assert "malformed" in errors.getvalue() and token not in errors.getvalue()


def test_interrupted_rotation_rolls_back_batch_and_can_resume(world, monkeypatch):
    from compass.assessment_records.management.commands import (
        rotate_assessment_record_confidential_content as command,
    )

    with override_settings(**{content.KEYRING_SETTING: (OLD,)}):
        items = [record(world), record(world)]
    before = {item.pk: item.confidential_content_ciphertext for item in items}
    original = command.reencrypt_confidential_content
    calls = 0

    def interrupted(item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return original(item)

    with override_settings(**{content.KEYRING_SETTING: (NEW, OLD)}):
        monkeypatch.setattr(command, "reencrypt_confidential_content", interrupted)
        with pytest.raises(KeyboardInterrupt):
            call_command(
                "rotate_assessment_record_confidential_content", batch_size=2, stdout=StringIO()
            )
        assert (
            dict(
                StudentAssessmentRecord.objects.values_list("pk", "confidential_content_ciphertext")
            )
            == before
        )
        monkeypatch.setattr(command, "reencrypt_confidential_content", original)
        call_command(
            "rotate_assessment_record_confidential_content", batch_size=1, stdout=StringIO()
        )
        for item in items:
            item.refresh_from_db()
            assert content.encrypted_with_primary_key(item.confidential_content_ciphertext)
            assert asdict(content.read_confidential_content(item)) == PAYLOAD
