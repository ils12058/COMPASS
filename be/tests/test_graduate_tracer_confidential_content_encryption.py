"""ADR-084 confidential storage, disclosure, retention, migration and rotation.

Only synthetic keys and synthetic personal data; dedicated transactional test database.
"""

from __future__ import annotations

import base64
import importlib
import json
import runpy
from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from openpyxl import load_workbook

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.graduate_tracer import confidential_content as content
from compass.graduate_tracer import services
from compass.graduate_tracer.disposition import (
    ANALYTICAL_FIELDS,
    anonymize_response,
    verify_anonymized,
)
from compass.graduate_tracer.migrations import _graduate_tracer_confidential_content_v1 as frozen
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation
from compass.notifications.models import EmailDelivery, Notification
from compass.reports.graduate_tracer import build_graduate_tracer_report
from compass.reports.graduate_tracer_xlsx import render_graduate_tracer_xlsx
from tests.graduate_tracer_test_helpers import encrypted_row
from tests.test_graduate_tracer import (
    auth_client,
    make_head,
    make_user,
    post_empty,
    put_json,
    sync_policy,
    valid_employed_payload,
    valid_unemployed_payload,
)

K1, K2, K3 = (base64.urlsafe_b64encode(bytes([n]) * 32).decode() for n in (121, 122, 123))
NAMES = tuple(content.FIELDS)
BEFORE = [("graduate_tracer", "0002_graduatetracerdisposedparticipation_and_more")]
BACKFILLED = [("graduate_tracer", "0003_encrypt_confidential_content")]
AFTER = [("graduate_tracer", "0004_remove_plaintext_confidential_content")]
SETTING = content.SETTING


@pytest.fixture(autouse=True)
def ring(settings):
    settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


def private_payload(family):
    result = content.PROJECTIONS[family]().payload()
    for name in result:
        if name in {"birth_date", "date_taken"}:
            result[name] = "2000-01-02"
        elif name == "year_graduated":
            result[name] = 2020
        elif name in content.LIST_CHOICES:
            result[name] = list(content.LIST_CHOICES[name])[-2:]
        elif name == "email_snapshot":
            result[name] = "private-tracer-sentinel@example.edu"
        else:
            result[name] = f"PRIVATE-{name}-SENTINEL 雪 café 🎓"
    return result


def example(family):
    model = apps.get_model("graduate_tracer", family)
    row = model(**({} if family == NAMES[0] else {"response_id": uuid4(), "position": 1}))
    content.write_confidential_content(row, private_payload(family))
    return row


def safe(value, *extras):
    text = str(value)
    assert "PRIVATE-" not in text and K1 not in text and K2 not in text
    assert all(extra not in text for extra in extras)


def forbid(*args, **kwargs):
    pytest.fail("Private crypto was called by a plaintext-only operation")


@pytest.mark.parametrize("family", NAMES)
def test_exact_wire_schema_frozen_compatibility_and_immutable_projection(family):
    row = example(family)
    envelope = json.loads(Fernet(K1).decrypt(row.confidential_content_ciphertext.encode()))
    assert type(envelope["schema_version"]) is int and envelope["schema_version"] == 1
    assert set(envelope) == {"schema_version", "payload", *content.binding(row, family)}
    assert envelope["payload"] == private_payload(family)
    assert (
        frozen.decrypt(frozen.keyring(), row, row.confidential_content_ciphertext, family)
        == envelope["payload"]
    )
    row.confidential_content_ciphertext = frozen.encrypt(
        frozen.keyring(), row, envelope["payload"], family
    )
    projection = content.read_confidential_content(row)
    assert projection.payload() == private_payload(family)
    assert not any(hasattr(row, name) for name in content.FIELDS[family])
    with pytest.raises(FrozenInstanceError):
        setattr(projection, next(iter(content.FIELDS[family])), "changed")
    for name in {"birth_date", "date_taken"}.intersection(content.FIELDS[family]):
        assert type(getattr(projection, name)) is date


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "tamper",
        "truncate",
        "nonascii",
        "random",
        "schema",
        "boolean-version",
        "missing-field",
        "extra-field",
        "null",
        "wrong-type",
        "binding",
    ],
)
def test_all_family_failures_are_bounded_and_content_free(family, fault):
    row = example(family)
    token = row.confidential_content_ciphertext
    envelope = json.loads(Fernet(K1).decrypt(token.encode()))
    if fault == "missing":
        token = None
    elif fault == "tamper":
        token = token[:-3] + "xxx"
    elif fault == "truncate":
        token = token[:35]
    elif fault == "nonascii":
        token = "PRIVATE-雪"
    elif fault == "random":
        token = "PRIVATE-broken-token"
    else:
        if fault == "schema":
            envelope["schema_version"] = 2
        elif fault == "boolean-version":
            envelope["schema_version"] = True
        elif fault == "missing-field":
            envelope["payload"].pop(next(iter(envelope["payload"])))
        elif fault == "extra-field":
            envelope["payload"]["extra"] = "PRIVATE-extra"
        elif fault == "null":
            envelope["payload"] = None
        elif fault == "wrong-type":
            envelope["payload"][next(iter(envelope["payload"]))] = False
        elif fault == "binding":
            envelope[next(iter(content.BINDINGS[family]))] = str(uuid4())
        token = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    row.confidential_content_ciphertext = token
    with pytest.raises(content.GraduateTracerConfidentialContentUnavailable) as caught:
        content.read_confidential_content(row)
    exc = caught.value
    assert set(vars(exc)) == {"response_id", "object_id", "family", "reason"}
    assert exc.family == family and exc.reason in {
        "missing",
        "undecryptable",
        "malformed",
        "unsupported_schema",
        "binding_mismatch",
    }
    safe(exc, token if token else "PRIVATE-extra")


@pytest.mark.parametrize("family", NAMES)
def test_uuid_transplant_and_child_parent_change_fail_but_position_metadata_do_not(family):
    first, second = example(family), example(family)
    second.confidential_content_ciphertext = first.confidential_content_ciphertext
    with pytest.raises(
        content.GraduateTracerConfidentialContentUnavailable, match="unavailable"
    ) as caught:
        content.read_confidential_content(second)
    assert caught.value.reason == "binding_mismatch"
    if family != NAMES[0]:
        first.response_id = uuid4()
        with pytest.raises(content.GraduateTracerConfidentialContentUnavailable) as caught:
            content.read_confidential_content(first)
        assert caught.value.reason == "binding_mismatch"
    else:
        first.student_id = uuid4()
        first.status = "SUBMITTED"
        first.submitted_at = timezone.now()
        first.current_employment_state = "NOT_EMPLOYED"
        assert content.read_confidential_content(first).payload() == private_payload(family)
    row = example(family)
    row.position = 9
    assert content.read_confidential_content(row).payload() == private_payload(family)


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("fault", ["nul", "surrogate", "overflow"])
def test_payload_text_validation_rejects_without_encrypt(family, fault, monkeypatch):
    row = example(family)
    payload = private_payload(family)
    name = next(name for name, limit in content.FIELDS[family].items() if limit is not None)
    payload[name] = {
        "nul": "PRIVATE-\x00",
        "surrogate": "\ud800",
        "overflow": "X" * (content.FIELDS[family][name] + 1),
    }[fault]
    monkeypatch.setattr(content, "encrypt_bound_json", forbid)
    with pytest.raises(services.InvalidGraduateTracerInput) as caught:
        content.write_confidential_content(row, payload)
    safe(caught.value)


@pytest.mark.parametrize(
    "name,value",
    [
        ("birth_date", "2000-1-02"),
        ("birth_date", True),
        ("birth_date", "invalid"),
        ("undergraduate_degree_reasons", ["UNKNOWN"]),
        ("graduate_study_reasons", ["PEER_INFLUENCE", "PEER_INFLUENCE"]),
        ("advanced_study_reasons", "OTHER"),
        ("email_snapshot", "bad-email"),
    ],
)
def test_authenticated_invalid_root_payload_is_unavailable(name, value):
    row = example(NAMES[0])
    envelope = json.loads(Fernet(K1).decrypt(row.confidential_content_ciphertext.encode()))
    envelope["payload"][name] = value
    row.confidential_content_ciphertext = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    with pytest.raises(content.GraduateTracerConfidentialContentUnavailable) as caught:
        content.read_confidential_content(row)
    assert caught.value.reason == "malformed"


@pytest.fixture
def world(db):
    sync_policy()
    student = make_user("encrypted-tracer@example.edu")
    head = make_head("encrypted-tracer-head@example.edu")
    item = services.ensure_my_response(student=student, context=AuditContext.user(student))
    return {"student": student, "head": head, "item": item, "client": auth_client(student)}


def filled(world, *, submit=False):
    values = valid_employed_payload()
    values["professional_exams"] = [
        {"examination_name": "PRIVATE-exam", "date_taken": "2000-01-02", "rating": "PRIVATE-rating"}
    ]
    values["trainings"] = [
        {
            "title": "PRIVATE-training",
            "duration_and_credits": "PRIVATE-duration",
            "institution": "PRIVATE-institution",
        }
    ]
    values["name"] = "Historical Searchable Graduate"
    values["permanent_address"] = "PRIVATE-address 雪 café 🎓"
    values["curriculum_improvement_suggestions"] = "PRIVATE-curriculum"
    response = put_json(world["client"], "/api/v1/graduate-tracer/me", values)
    assert response.status_code == 200, response.content
    if submit:
        response = post_empty(world["client"], "/api/v1/graduate-tracer/me/submit")
        assert response.status_code == 200, response.content
    return GraduateTracerResponse.objects.get(pk=world["item"].pk)


def raw_all():
    result = {}
    for family in NAMES:
        model = apps.get_model("graduate_tracer", family)
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM "{model._meta.db_table}" ORDER BY id')
            names = [col.name for col in cursor.description]
            result[family] = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    return result


def columns(model):
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, model._meta.db_table)
        }


def effects():
    return (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
        GraduateTracerDisposedParticipation.objects.count(),
    )


def test_raw_storage_removed_private_columns_and_queryable_search_and_e1(world, monkeypatch):
    item = filled(world, submit=True)
    for family in NAMES:
        assert not set(content.FIELDS[family]).intersection(
            columns(apps.get_model("graduate_tracer", family))
        )
    text = json.dumps(raw_all(), default=str)
    assert "PRIVATE-" not in text and "graduate@example.edu" not in text
    assert "Historical Searchable Graduate" in text
    for field in ANALYTICAL_FIELDS:
        assert list(GraduateTracerResponse.objects.values_list(field, flat=True)) == [
            getattr(item, field)
        ]
    monkeypatch.setattr(content, "decrypt_bound_json", forbid)
    monkeypatch.setattr(content, "read_confidential_content", forbid)
    monkeypatch.setattr(content, "read_private_projection", forbid)
    monkeypatch.setattr(services, "read_private_projection", forbid)
    client = auth_client(world["head"])
    result = client.get(
        "/api/v1/graduate-tracer/responses?search=Historical%20Searchable&page_size=1&current_employment_state=EMPLOYED"
    )
    assert result.status_code == 200 and result.json()["items"][0]["id"] == str(item.pk)


@pytest.mark.parametrize(
    "role",
    ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER", "STUDENT", "DPO"],
)
def test_unauthorized_raw_detail_never_decrypts(world, monkeypatch, role):
    item = filled(world, submit=True)
    user = make_user(
        f"denied-{role}@example.edu", role="INSTITUTIONAL_OFFICER" if role == "DPO" else role
    )
    if role == "DPO":
        from compass.accounts.models import Designation, UserDesignation

        UserDesignation.objects.create(user=user, designation=Designation.objects.get(code="DPO"))
    monkeypatch.setattr(content, "decrypt_bound_json", forbid)
    client = auth_client(user)
    assert client.get(f"/api/v1/graduate-tracer/responses/{item.pk}").status_code == 403
    if role == "STUDENT":
        assert client.get("/api/v1/graduate-tracer/me").status_code == 404


def test_head_draft_not_found_before_decrypt_and_revoked_owner_before_decrypt(world, monkeypatch):
    monkeypatch.setattr(content, "decrypt_bound_json", forbid)
    assert (
        auth_client(world["head"])
        .get(f"/api/v1/graduate-tracer/responses/{world['item'].pk}")
        .status_code
        == 404
    )
    from compass.accounts.models import Capability, UserCapabilityOverride

    UserCapabilityOverride.objects.create(
        user=world["student"],
        capability=Capability.objects.get(code="graduate_tracer.view_self"),
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Synthetic revocation",
    )
    assert world["client"].get("/api/v1/graduate-tracer/me").status_code == 403


@pytest.mark.parametrize("family", NAMES)
def test_authorized_detail_unreadable_root_or_child_generic500_no_partial(world, family, caplog):
    item = filled(world, submit=True)
    model = apps.get_model("graduate_tracer", family)
    model.objects.update(confidential_content_ciphertext="PRIVATE-corrupt-token")
    for client, path in [
        (world["client"], "/api/v1/graduate-tracer/me"),
        (auth_client(world["head"]), f"/api/v1/graduate-tracer/responses/{item.pk}"),
    ]:
        result = client.get(path)
        assert result.status_code == 500
        assert result.json()["error"]["code"] == "graduate_tracer_confidential_content_unavailable"
        safe(result.content, "PRIVATE-corrupt-token")
    safe(caplog.text, "PRIVATE-corrupt-token")


def test_draft_replacement_cannot_repair_corruption_and_is_atomic(world):
    filled(world)
    GraduateTracerResponse.objects.update(confidential_content_ciphertext="PRIVATE-corrupt-token")
    before = raw_all(), effects()
    result = put_json(world["client"], "/api/v1/graduate-tracer/me", valid_unemployed_payload())
    assert result.status_code == 500
    assert (raw_all(), effects()) == before


def test_no_decrypt_aggregate_services_json_xlsx_and_anonymous_population(
    world, settings, monkeypatch
):
    item = filled(world, submit=True)
    anonymize_response(item.pk)
    other = encrypted_row(
        GraduateTracerResponse,
        student=make_user("report-identifiable@example.edu"),
        current_employment_state="NOT_EMPLOYED",
        status="SUBMITTED",
        submitted_at=timezone.now(),
    )
    GraduateTracerResponse.objects.filter(pk=other.pk).update(
        confidential_content_ciphertext="PRIVATE-corrupt-token"
    )
    settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = ()
    for name in [
        "decrypt_bound_json",
        "read_confidential_content",
        "read_private_projection",
        "keyring",
    ]:
        monkeypatch.setattr(content, name, forbid)
    report = build_graduate_tracer_report()
    assert report["report_context"]["submitted_response_count"] == 2
    result = render_graduate_tracer_xlsx()
    book = load_workbook(BytesIO(result.xlsx_bytes))
    assert len(book.worksheets) == 5 and all(sheet.sheet_state == "visible" for sheet in book)
    assert "PRIVATE-" not in str([cell.value for sheet in book for row in sheet for cell in row])
    client = auth_client(world["head"])
    assert client.get("/api/v1/reports/graduate-tracer").status_code == 200
    assert client.get("/api/v1/reports/graduate-tracer/xlsx").status_code == 200
    assert [
        row["id"] for row in client.get("/api/v1/graduate-tracer/responses").json()["items"]
    ] == [str(other.pk)]
    anonymous = GraduateTracerResponse.objects.get(student__isnull=True)
    assert client.get(f"/api/v1/graduate-tracer/responses/{anonymous.pk}").status_code == 404


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("value", [None, ""])
def test_identifiable_database_cipher_invariant(world, family, value):
    filled(world)
    model = apps.get_model("graduate_tracer", family)
    row = model.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.filter(pk=row.pk).update(confidential_content_ciphertext=value)


def test_approved_disposition_corrupt_source_missing_keys_no_crypto_and_four_disposed_operations(
    world, settings, monkeypatch, caplog
):
    from compass.accounts.models import Designation, UserDesignation
    from compass.privacy_governance.tasks import execute_disposition
    from tests.test_operational_retention import active_rule, approve, discovered_case
    from tests.test_operational_retention import make_user as retention_user

    item = filled(world, submit=True)
    dpo = retention_user("tracer-retention-dpo@example.edu", role="INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(user=dpo, designation=Designation.objects.get(code="DPO"))
    active_rule(dpo)
    GraduateTracerResponse.objects.filter(pk=item.pk).update(
        submitted_at=timezone.now() - timedelta(days=31)
    )
    item.refresh_from_db()
    expected = build_graduate_tracer_report()
    old_e1 = {name: getattr(item, name) for name in ANALYTICAL_FIELDS}
    case = approve(dpo, discovered_case(item))
    for family in NAMES:
        apps.get_model("graduate_tracer", family).objects.update(
            confidential_content_ciphertext="PRIVATE-corrupt-token"
        )
    settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = ()
    for name in [
        "decrypt_bound_json",
        "read_confidential_content",
        "read_private_projection",
        "keyring",
        "encrypt_bound_json",
        "write_confidential_content",
    ]:
        monkeypatch.setattr(content, name, forbid)
    execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "COMPLETED"
    assert not GraduateTracerResponse.objects.filter(pk=item.pk).exists()
    anonymous = GraduateTracerResponse.objects.get(student__isnull=True)
    assert anonymous.pk != item.pk and anonymous.confidential_content_ciphertext is None
    assert verify_anonymized(anonymous)
    assert {name: getattr(anonymous, name) for name in ANALYTICAL_FIELDS} == old_e1
    after = build_graduate_tracer_report()
    assert after["sections"] == expected["sections"]
    assert after["methodology"] == expected["methodology"]
    assert after["disclosure_warnings"] == expected["disclosure_warnings"]
    assert (
        after["report_context"]["submitted_response_count"]
        == expected["report_context"]["submitted_response_count"]
    )
    assert all(
        not apps.get_model("graduate_tracer", family).objects.exists() for family in NAMES[1:]
    )
    participation = GraduateTracerDisposedParticipation.objects.get(student=world["student"])
    assert not any(
        "response" in field.name or "cipher" in field.name or "anonymous" in field.name
        for field in participation._meta.fields
    )
    for result in [
        world["client"].get("/api/v1/graduate-tracer/me"),
        post_empty(world["client"], "/api/v1/graduate-tracer/me"),
        put_json(world["client"], "/api/v1/graduate-tracer/me", valid_unemployed_payload()),
        post_empty(world["client"], "/api/v1/graduate-tracer/me/submit"),
    ]:
        assert (
            result.status_code == 409
            and result.json()["error"]["code"] == "graduate_tracer_disposed"
        )
    safe(
        list(AuditEvent.objects.values_list("metadata", flat=True)),
        "PRIVATE-corrupt-token",
        str(anonymous.pk),
    )
    safe(caplog.text, "PRIVATE-corrupt-token")
    with pytest.raises(IntegrityError), transaction.atomic():
        GraduateTracerResponse.objects.filter(pk=anonymous.pk).update(
            confidential_content_ciphertext="any-token"
        )


@pytest.mark.parametrize(
    "branch",
    ["NOT_EMPLOYED", "NEVER_EMPLOYED", "NOT_SELF", "CURRICULUM", "NOT_FIRST", "NOT_RELATED"],
)
def test_cross_boundary_branch_clearing_before_encrypt(world, branch):
    payload = valid_employed_payload()
    payload.update(
        present_employment_status="SELF_EMPLOYED",
        self_employed_college_skills="PRIVATE-skills",
        first_job_after_college=True,
        first_job_related_to_course=True,
        reasons_for_staying_on_job=["OTHER"],
        reasons_for_staying_other="PRIVATE-staying",
        reasons_for_accepting_first_job=["OTHER"],
        reasons_for_accepting_other="PRIVATE-accepting",
        reasons_for_changing_job=["OTHER"],
        reasons_for_changing_other="PRIVATE-changing",
        curriculum_relevant_to_first_job=True,
        useful_competencies=["OTHER"],
        useful_competencies_other="PRIVATE-useful",
    )
    if branch in {"NOT_EMPLOYED", "NEVER_EMPLOYED"}:
        payload["current_employment_state"] = branch
    elif branch == "NOT_SELF":
        payload["present_employment_status"] = "REGULAR_PERMANENT"
    elif branch == "CURRICULUM":
        payload["curriculum_relevant_to_first_job"] = False
    elif branch == "NOT_FIRST":
        payload["first_job_after_college"] = False
    else:
        payload["first_job_related_to_course"] = False
    result = put_json(world["client"], "/api/v1/graduate-tracer/me", payload)
    assert result.status_code == 200
    row = GraduateTracerResponse.objects.get(pk=world["item"].pk)
    private = content.read_confidential_content(row)
    if branch in {"NOT_EMPLOYED", "NEVER_EMPLOYED"}:
        assert all(
            getattr(private, name) == ""
            for name in [
                "self_employed_college_skills",
                "present_occupation",
                "reasons_for_staying_other",
                "reasons_for_accepting_other",
                "reasons_for_changing_other",
                "useful_competencies_other",
            ]
        )
        assert private.reasons_for_accepting_first_job == private.reasons_for_changing_job == ()
    elif branch == "NOT_SELF":
        assert private.self_employed_college_skills == ""
    elif branch == "CURRICULUM":
        assert private.useful_competencies_other == "" and row.useful_competencies == []
    elif branch == "NOT_FIRST":
        assert private.reasons_for_staying_other == private.reasons_for_accepting_other == ""
    else:
        assert (
            private.reasons_for_accepting_first_job == ()
            and private.reasons_for_accepting_other == ""
        )


def rotate(**options):
    out, err = StringIO(), StringIO()
    call_command("rotate_graduate_tracer_confidential_content", stdout=out, stderr=err, **options)
    safe(out.getvalue())
    safe(err.getvalue())
    return out.getvalue()


def test_rotation_bytes_timestamp_metadata_anonymous_skip_and_idempotence(world, settings):
    filled(world, submit=True)
    anonymous = GraduateTracerResponse.objects.create(
        student=None,
        status="SUBMITTED",
        submitted_at=timezone.now(),
        anonymized_at=timezone.now(),
        confidential_content_ciphertext=None,
    )
    before, counts = raw_all(), effects()
    settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    assert rotate(dry_run=True, batch_size=1).count("failures 0") == 4
    assert raw_all() == before
    assert "Anonymous contributions skipped: 1" in rotate(batch_size=1)
    after = raw_all()
    for family in NAMES:
        for old, new in zip(before[family], after[family], strict=True):
            if old["id"] == anonymous.pk:
                assert old == new and new["confidential_content_ciphertext"] is None
                continue
            col = "confidential_content_ciphertext"
            assert Fernet(K1).decrypt(old[col].encode()) == Fernet(K2).decrypt(new[col].encode())
            assert Fernet(K1).extract_timestamp(old[col].encode()) == Fernet(K2).extract_timestamp(
                new[col].encode()
            )
            with pytest.raises(InvalidToken):
                Fernet(K1).decrypt(new[col].encode())
            assert {k: v for k, v in old.items() if k != col} == {
                k: v for k, v in new.items() if k != col
            }
    assert effects() == counts
    rotate(batch_size=1)
    assert raw_all() == after


@pytest.mark.django_db(transaction=True)
def test_rotation_real_row_locks_interrupted_committed_batch_resumes(world, settings, monkeypatch):
    filled(world)
    settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    command = importlib.import_module(
        "compass.graduate_tracer.management.commands.rotate_graduate_tracer_confidential_content"
    )
    original = command.reencrypt_confidential_content
    seen = []

    def interrupt(row):
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout='100ms'")
                with pytest.raises(OperationalError, match="lock timeout"):
                    cursor.execute(f'UPDATE "{row._meta.db_table}" SET id=id WHERE id=%s', [row.pk])
        finally:
            writer.close()
        seen.append(row.pk)
        if len(seen) == 2:
            raise RuntimeError("synthetic interruption")
        return original(row)

    before = raw_all()
    monkeypatch.setattr(command, "reencrypt_confidential_content", interrupt)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        rotate(batch_size=1)
    intermediate = raw_all()
    assert sum(before[name] != intermediate[name] for name in NAMES) == 1
    monkeypatch.setattr(command, "reencrypt_confidential_content", original)
    rotate(batch_size=1)
    assert raw_all()[NAMES[0]] == intermediate[NAMES[0]]


def test_rotation_bounded_failures_and_batch_bounds(world):
    from compass.graduate_tracer.models import GraduateTracerTraining

    GraduateTracerTraining.objects.bulk_create(
        [
            GraduateTracerTraining(
                response=world["item"],
                position=n,
                confidential_content_ciphertext="PRIVATE-broken-token",
            )
            for n in range(1, 28)
        ]
    )
    before = raw_all()
    for dry in (True, False):
        out, err = StringIO(), StringIO()
        with pytest.raises(CommandError) as caught:
            call_command(
                "rotate_graduate_tracer_confidential_content",
                dry_run=dry,
                batch_size=1,
                stdout=out,
                stderr=err,
            )
        assert err.getvalue().count("Unreadable:") == 20 and "and 7 more" in err.getvalue()
        safe(out.getvalue())
        safe(err.getvalue())
        safe(caught.value)
        assert raw_all() == before
    for size in (0, 1001):
        with pytest.raises(CommandError, match="between 1 and 1000"):
            rotate(batch_size=size)


@pytest.fixture
def legacy(transactional_db):
    initial = MigrationExecutor(connection).loader.graph.leaf_nodes()
    assert connection.settings_dict["NAME"].startswith("test_")
    models = [apps.get_model("graduate_tracer", name) for name in NAMES]
    assert all(not model.objects.exists() for model in models)
    # Reset empty dedicated test tables to avoid PostgreSQL dropped-attribute exhaustion.
    with connection.schema_editor() as editor:
        for model in reversed(models):
            editor.delete_model(model)
        for model in models:
            editor.create_model(model)
    sync_policy()
    MigrationExecutor(connection).migrate(BEFORE)
    try:
        yield MigrationExecutor(connection).loader.project_state(BEFORE).apps
    finally:
        # Test cleanup only: remove bad transitional test data before restoring current graph.
        with connection.cursor() as cursor:
            for model in reversed(models):
                cursor.execute(f'DELETE FROM "{model._meta.db_table}"')
        MigrationExecutor(connection).migrate(initial)


def old_rows(registry, variant="filled", index=0):
    student = make_user(f"old-tracer-{index}@example.edu")
    model = registry.get_model("graduate_tracer", NAMES[0])
    values = (
        content.PROJECTIONS[NAMES[0]]().payload()
        if variant == "empty"
        else private_payload(NAMES[0])
    )
    values["birth_date"] = (
        date.fromisoformat(values["birth_date"]) if values["birth_date"] else None
    )
    if variant == "partial":
        values["email_snapshot"] = ""
        values["advanced_study_other_reason"] = ""
    root = model.objects.create(
        student_id=student.pk,
        name_snapshot="Historical Searchable Graduate",
        status="SUBMITTED" if variant == "submitted" else "DRAFT",
        submitted_at=timezone.now() if variant == "submitted" else None,
        current_employment_state=["EMPLOYED", "NOT_EMPLOYED", "NEVER_EMPLOYED"][index % 3],
        **values,
    )
    if variant not in {"empty", "partial"}:
        for family in NAMES[1:]:
            values = private_payload(family)
            if "date_taken" in values:
                values["date_taken"] = date.fromisoformat(values["date_taken"])
            registry.get_model("graduate_tracer", family).objects.create(
                response_id=root.pk, position=1, **values
            )
    return root


def old_anonymous(registry):
    return registry.get_model("graduate_tracer", NAMES[0]).objects.create(
        student_id=None,
        status="SUBMITTED",
        submitted_at=timezone.now(),
        anonymized_at=timezone.now(),
        sex="FEMALE",
        current_employment_state="EMPLOYED",
    )


def test_migration_all_four_families_exact_forward_reverse_variants_anonymous_and_tombstone(legacy):
    for index, variant in enumerate(["empty", "partial", "filled", "submitted"]):
        old_rows(legacy, variant, index)
    anonymous = old_anonymous(legacy)
    student = make_user("old-disposed@example.edu")
    GraduateTracerDisposedParticipation.objects.create(
        student=student, instrument_schema_version=1, disposed_on=timezone.localdate()
    )
    before, counts = raw_all(), effects()
    MigrationExecutor(connection).migrate(AFTER)
    assert effects() == counts
    for family in NAMES:
        assert not set(content.FIELDS[family]).intersection(
            columns(apps.get_model("graduate_tracer", family))
        )
        for row in apps.get_model("graduate_tracer", family).objects.all():
            if family == NAMES[0] and row.pk == anonymous.pk:
                assert verify_anonymized(row) and row.confidential_content_ciphertext is None
            else:
                old = next(old for old in before[family] if old["id"] == row.pk)
                expected = {name: old[name] for name in content.FIELDS[family]}
                for name in {"birth_date", "date_taken"}.intersection(expected):
                    expected[name] = expected[name].isoformat() if expected[name] else None
                assert content.read_confidential_content(row).payload() == expected
    MigrationExecutor(connection).migrate(BEFORE)
    assert raw_all() == before and effects() == counts


def test_phase_b_reconciles_latest_old_root_children_and_submission(legacy):
    root = old_rows(legacy)
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    model = registry.get_model("graduate_tracer", NAMES[0])
    model.objects.filter(pk=root.pk).update(
        permanent_address_snapshot="Latest PRIVATE-address 🎓",
        current_employment_state="NOT_EMPLOYED",
        reasons_for_staying_other="",
        reasons_for_accepting_first_job=[],
        reasons_for_accepting_other="",
        status="SUBMITTED",
        submitted_at=timezone.now(),
    )
    for family in NAMES[1:]:
        child = registry.get_model("graduate_tracer", family)
        child.objects.all().delete()
        values = private_payload(family)
        name = next(iter(values))
        values[name] = "Latest PRIVATE-child"
        if "date_taken" in values:
            values["date_taken"] = date.fromisoformat(values["date_taken"])
        child.objects.create(response_id=root.pk, position=1, **values)
    late = old_rows(registry, "empty", 1)
    before = raw_all()
    MigrationExecutor(connection).migrate(AFTER)
    assert (
        content.read_confidential_content(
            GraduateTracerResponse.objects.get(pk=root.pk)
        ).permanent_address_snapshot
        == "Latest PRIVATE-address 🎓"
    )
    assert content.read_confidential_content(GraduateTracerResponse.objects.get(pk=late.pk))
    for family in NAMES:
        assert [row["id"] for row in raw_all()[family]] == [row["id"] for row in before[family]]
    MigrationExecutor(connection).migrate(BEFORE)
    assert {
        name: [
            {k: v for k, v in row.items() if k != "confidential_content_ciphertext"} for row in rows
        ]
        for name, rows in before.items()
    } == raw_all()


def test_phase_a_old_disposition_new_anonymous_null_is_valid(legacy):
    root = old_rows(legacy, "submitted")
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    model = registry.get_model("graduate_tracer", NAMES[0])
    source = model.objects.get(pk=root.pk)
    retained = model.objects.create(
        student_id=None,
        status="SUBMITTED",
        submitted_at=source.submitted_at,
        anonymized_at=timezone.now(),
        **{name: getattr(source, name) for name in ANALYTICAL_FIELDS},
    )
    GraduateTracerDisposedParticipation.objects.create(
        student_id=source.student_id, instrument_schema_version=1, disposed_on=timezone.localdate()
    )
    source.delete()
    assert retained.confidential_content_ciphertext is None
    MigrationExecutor(connection).migrate(AFTER)
    assert verify_anonymized(GraduateTracerResponse.objects.get(pk=retained.pk))
    assert not GraduateTracerResponse.objects.filter(pk=root.pk).exists()
    MigrationExecutor(connection).migrate(BEFORE)
    restored = (
        MigrationExecutor(connection)
        .loader.project_state(BEFORE)
        .apps.get_model("graduate_tracer", NAMES[0])
        .objects.get(pk=retained.pk)
    )
    assert all(
        getattr(restored, name) == restored._meta.get_field(name).get_default()
        for name in content.FIELDS[NAMES[0]]
    )


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("fault", ["tamper", "binding", "schema", "payload", "undecryptable"])
def test_corrupt_phase_a_aborts_earlier_updates_and_all_ddl(legacy, family, fault):
    root = old_rows(legacy)
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    model = registry.get_model("graduate_tracer", family)
    row = model.objects.first()
    token = row.confidential_content_ciphertext
    envelope = json.loads(Fernet(K1).decrypt(token.encode()))
    if fault == "binding":
        envelope[next(iter(content.BINDINGS[family]))] = str(uuid4())
    elif fault == "schema":
        envelope["schema_version"] = True
    elif fault == "payload":
        envelope["payload"]["unexpected"] = "PRIVATE-extra"
    token = (
        "PRIVATE-corrupt-token"
        if fault == "tamper"
        else Fernet(K2).encrypt(b"{}").decode()
        if fault == "undecryptable"
        else Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    )
    model.objects.filter(pk=row.pk).update(confidential_content_ciphertext=token)
    registry.get_model("graduate_tracer", NAMES[0]).objects.filter(pk=root.pk).update(
        province="Latest PRIVATE-province"
    )
    before = raw_all()
    with pytest.raises(RuntimeError) as caught:
        MigrationExecutor(connection).migrate(AFTER)
    safe(caught.value, token)
    assert raw_all() == before
    assert AFTER[0] not in MigrationExecutor(connection).loader.applied_migrations
    for family in NAMES:
        assert set(content.FIELDS[family]) <= columns(apps.get_model("graduate_tracer", family))


@pytest.mark.parametrize(
    "stage,fault",
    [
        (BEFORE, "private"),
        (BEFORE, "child"),
        (BACKFILLED, "private"),
        (BACKFILLED, "child"),
        (BACKFILLED, "ciphertext"),
    ],
)
def test_migration_anonymous_integrity_aborts_without_normalizing(legacy, stage, fault):
    anonymous = old_anonymous(legacy)
    if stage == BACKFILLED:
        MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(stage).apps
    model = registry.get_model("graduate_tracer", NAMES[0])
    if fault == "private":
        model.objects.filter(pk=anonymous.pk).update(province="PRIVATE-leaked")
    elif fault == "child":
        registry.get_model("graduate_tracer", NAMES[1]).objects.create(
            response_id=anonymous.pk,
            position=1,
            degree_and_specialization="PRIVATE-degree",
            college_or_university="PRIVATE-school",
            year_graduated=2020,
        )
    else:
        model.objects.filter(pk=anonymous.pk).update(
            confidential_content_ciphertext="PRIVATE-token"
        )
    before = raw_all()
    with pytest.raises(RuntimeError) as caught:
        MigrationExecutor(connection).migrate(AFTER)
    safe(caught.value, "PRIVATE-token")
    assert raw_all() == before


@pytest.mark.parametrize("family", NAMES)
def test_corrupt_reverse_rolls_back_plaintext_ddl_and_data(legacy, family):
    old_rows(legacy)
    MigrationExecutor(connection).migrate(AFTER)
    model = apps.get_model("graduate_tracer", family)
    row = model.objects.first()
    model.objects.filter(pk=row.pk).update(confidential_content_ciphertext="PRIVATE-corrupt-token")
    before = raw_all()
    with pytest.raises(RuntimeError) as caught:
        MigrationExecutor(connection).migrate(BEFORE)
    safe(caught.value, "PRIVATE-corrupt-token")
    assert raw_all() == before
    for name in NAMES:
        assert not set(content.FIELDS[name]).intersection(
            columns(apps.get_model("graduate_tracer", name))
        )


@pytest.mark.parametrize("reverse", [False, True])
def test_writer_fence_precedes_forward_and_reverse_verification_and_ddl(
    legacy, monkeypatch, reverse
):
    old_rows(legacy)
    MigrationExecutor(connection).migrate(AFTER if reverse else BACKFILLED)
    phase = importlib.import_module(
        "compass.graduate_tracer.migrations.0004_remove_plaintext_confidential_content"
    )
    original = phase.lock_tables
    seen = []

    def probe(registry, editor):
        original(registry, editor)
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout='100ms'")
                for name in NAMES:
                    table = registry.get_model("graduate_tracer", name)._meta.db_table
                    with pytest.raises(OperationalError, match="lock timeout"):
                        cursor.execute(f'UPDATE "{table}" SET id=id')
                    seen.append(name)
                table = registry.get_model("graduate_tracer", NAMES[0])._meta.db_table
                # Aggregate report row-population FOR SHARE/FOR UPDATE conflicts with the fence.
                with pytest.raises(OperationalError, match="lock timeout"):
                    cursor.execute(f'SELECT id FROM "{table}" FOR UPDATE')
        finally:
            writer.close()

    monkeypatch.setattr(phase, "lock_tables", probe)
    # RunPython stores function references at module import; update reverse reference explicitly.
    if reverse:
        monkeypatch.setattr(phase.Migration.operations[-1], "reverse_code", probe)
    MigrationExecutor(connection).migrate(BEFORE if reverse else AFTER)
    assert seen == list(NAMES)


def test_dual_schema_rotation_refused_and_identical_tokens_kept(legacy):
    old_rows(legacy)
    MigrationExecutor(connection).migrate(BACKFILLED)
    before = raw_all()
    for dry in (True, False):
        with pytest.raises(CommandError, match="Legacy plaintext"):
            rotate(dry_run=dry)
    MigrationExecutor(connection).migrate(AFTER)
    for family in NAMES:
        assert [row["confidential_content_ciphertext"] for row in raw_all()[family]] == [
            row["confidential_content_ciphertext"] for row in before[family]
        ]


@pytest.mark.parametrize("keys", [(), "", "invalid-key", (K1, K1)])
def test_invalid_historical_keyring_aborts_without_data_or_schema_change(legacy, settings, keys):
    old_rows(legacy)
    before = raw_all()
    settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = keys
    try:
        with pytest.raises(RuntimeError) as caught:
            MigrationExecutor(connection).migrate(BACKFILLED)
        safe(caught.value, "invalid-key")
        assert raw_all() == before
    finally:
        settings.GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


@pytest.mark.parametrize(
    "source",
    [
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    ],
)
@pytest.mark.parametrize("position", [0, 1])
def test_settings_rejects_reused_current_or_previous_key_without_disclosure(
    monkeypatch, source, position
):
    values = {
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS": K1,
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS": K2,
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS": K3,
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS": base64.urlsafe_b64encode(
            b"e" * 32
        ).decode(),
        "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS": base64.urlsafe_b64encode(
            b"i" * 32
        ).decode(),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    reused = (
        base64.urlsafe_b64encode(b"o" * 32).decode()
        if source in values and position
        else values.get(source, base64.urlsafe_b64encode(b"s" * 32).decode())
    )
    if source in values:
        monkeypatch.setenv(source, values[source] + "," + reused if position else reused)
    else:
        monkeypatch.setenv(source, reused)
    fresh = base64.urlsafe_b64encode(b"g" * 32).decode()
    monkeypatch.setenv(SETTING, reused + "," + fresh if not position else fresh + "," + reused)
    with pytest.raises(ValueError) as caught:
        runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))
    assert SETTING in str(caught.value) and "reuse" in str(caught.value)
    assert reused not in str(caught.value)


@pytest.mark.parametrize(
    "family,name,value",
    [
        (NAMES[0], "birth_date", "9999-01-01"),
        (NAMES[1], "year_graduated", True),
        (NAMES[1], "year_graduated", 1899),
        (NAMES[1], "year_graduated", 32767),
        (NAMES[1], "degree_and_specialization", ""),
        (NAMES[2], "date_taken", "2000-1-02"),
        (NAMES[2], "date_taken", "9999-01-01"),
        (NAMES[3], "institution", None),
    ],
)
def test_exact_payload_dates_years_and_required_content(family, name, value):
    row = example(family)
    envelope = json.loads(Fernet(K1).decrypt(row.confidential_content_ciphertext.encode()))
    envelope["payload"][name] = value
    row.confidential_content_ciphertext = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    with pytest.raises(content.GraduateTracerConfidentialContentUnavailable) as caught:
        content.read_confidential_content(row)
    assert caught.value.reason == "malformed"


@pytest.mark.parametrize("family", NAMES[1:])
def test_existing_child_stale_and_missing_tokens_reconcile(legacy, family):
    old_rows(legacy)
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    model = registry.get_model("graduate_tracer", family)
    row = model.objects.first()
    field = next(iter(content.FIELDS[family]))
    model.objects.filter(pk=row.pk).update(**{field: "Latest PRIVATE-row"})
    other_values = private_payload(family)
    if "date_taken" in other_values:
        other_values["date_taken"] = date.fromisoformat(other_values["date_taken"])
    other = model.objects.create(response_id=row.response_id, position=2, **other_values)
    model.objects.filter(pk=other.pk).update(confidential_content_ciphertext="")
    MigrationExecutor(connection).migrate(AFTER)
    final = apps.get_model("graduate_tracer", family)
    assert (
        getattr(content.read_confidential_content(final.objects.get(pk=row.pk)), field)
        == "Latest PRIVATE-row"
    )
    assert content.read_confidential_content(
        final.objects.get(pk=other.pk)
    ).payload() == private_payload(family)


def test_migrations_are_runtime_adapter_independent_and_reverse_never_decrypts_anonymous(
    legacy, monkeypatch
):
    old_rows(legacy)
    anonymous = old_anonymous(legacy)
    with monkeypatch.context() as guard:
        for name in [
            "read_confidential_content",
            "write_confidential_content",
            "keyring",
            "decrypt_bound_json",
            "encrypt_bound_json",
        ]:
            guard.setattr(content, name, forbid)
        MigrationExecutor(connection).migrate(AFTER)
    phase = importlib.import_module(
        "compass.graduate_tracer.migrations.0004_remove_plaintext_confidential_content"
    )
    original = phase.decrypt

    def identifiable_only(ring, row, token, family):
        assert row.pk != anonymous.pk
        return original(ring, row, token, family)

    monkeypatch.setattr(phase, "decrypt", identifiable_only)
    MigrationExecutor(connection).migrate(BEFORE)


@pytest.mark.parametrize("fault", ["missing", "empty", "invalid", "duplicate", "file", "both"])
def test_setting_required_and_file_backed_no_fallback(monkeypatch, tmp_path, fault):
    monkeypatch.delenv(SETTING, raising=False)
    monkeypatch.delenv(SETTING + "_FILE", raising=False)
    path = tmp_path / "synthetic-keyring"
    path.write_text(K1 + "\n")
    if fault == "empty":
        monkeypatch.setenv(SETTING, "")
    elif fault == "invalid":
        monkeypatch.setenv(SETTING, "private-invalid-key")
    elif fault == "duplicate":
        monkeypatch.setenv(SETTING, K1 + "," + K1)
    elif fault == "file":
        monkeypatch.setenv(SETTING + "_FILE", str(path))
    elif fault == "both":
        monkeypatch.setenv(SETTING, K2)
        monkeypatch.setenv(SETTING + "_FILE", str(path))
    if fault == "file":
        result = runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))
        assert result[SETTING] == (K1,)
    else:
        with pytest.raises(ValueError) as caught:
            runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))
        assert SETTING in str(caught.value)
        safe(caught.value, "private-invalid-key")


def test_demo_tracer_projection_uses_explicit_encrypted_snapshots(world):
    from types import SimpleNamespace

    from compass.demo_seed.scenarios import _tracer_values

    item = filled(world)
    private = content.read_confidential_content(item)
    birthday = date(2001, 2, 3)
    values = _tracer_values(item, SimpleNamespace(date_of_birth=birthday), {"sex": "MALE"})
    assert values == {
        "name_snapshot": item.name_snapshot,
        "permanent_address_snapshot": private.permanent_address_snapshot,
        "email_snapshot": private.email_snapshot,
        "telephone_contact_numbers_snapshot": private.telephone_contact_numbers_snapshot,
        "mobile_number_snapshot": private.mobile_number_snapshot,
        "birth_date": birthday,
        "sex": "MALE",
    }
