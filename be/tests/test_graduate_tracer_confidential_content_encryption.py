"""ADR-084 confidential storage, disclosure, retention, migration and rotation.

Only synthetic keys and synthetic personal data; dedicated transactional test database.
"""

from __future__ import annotations

import base64
import importlib
import json
import runpy
from dataclasses import FrozenInstanceError
from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.utils import timezone
from openpyxl import load_workbook

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.graduate_tracer import confidential_content as content
from compass.graduate_tracer import services
from compass.graduate_tracer.disposition import (
    ANALYTICAL_FIELDS,
)
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation
from compass.notifications.models import EmailDelivery, Notification
from compass.reports.graduate_tracer import build_graduate_tracer_report
from compass.reports.graduate_tracer_xlsx import render_graduate_tracer_xlsx
from tests.encryption_oracles import graduate_tracer_confidential_content_v1 as frozen
from tests.graduate_tracer_test_helpers import encrypted_row
from tests.historical_outcome_fixtures import historical_anonymized_contribution
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
    historical_anonymized_contribution(item)
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


def test_demo_tracer_projection_uses_explicit_encrypted_snapshots(world, monkeypatch):
    from types import SimpleNamespace

    from compass.demo_seed import scenarios

    item = filled(world)
    private = content.read_confidential_content(item)
    birthday = date(2001, 2, 3)
    monkeypatch.setattr(
        scenarios,
        "program_for",
        lambda _persona: SimpleNamespace(college_id=24, pk=42),
    )
    values = scenarios._tracer_values(
        item,
        SimpleNamespace(date_of_birth=birthday),
        {"sex": "MALE"},
        graduation_year=2020,
    )
    assert values == {
        "name_snapshot": item.name_snapshot,
        "permanent_address_snapshot": private.permanent_address_snapshot,
        "email_snapshot": private.email_snapshot,
        "telephone_contact_numbers_snapshot": private.telephone_contact_numbers_snapshot,
        "mobile_number_snapshot": private.mobile_number_snapshot,
        "birth_date": birthday,
        "graduated_college_id": 24,
        "graduated_program_id": 42,
        "graduation_year": 2020,
        "sex": "MALE",
    }
