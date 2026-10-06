"""ADR-083 storage, disclosure, migration and rotation; synthetic keys/data only."""

from __future__ import annotations

import base64
import importlib
import json
import runpy
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from pypdf import PdfReader

from compass.audit.models import AuditEvent
from compass.inventory import confidential_content as content
from compass.inventory import documents, services
from compass.inventory.migrations import _inventory_confidential_content_v1 as frozen
from compass.inventory.models import InventoryReopenEvent, StudentInventory
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.models import AcademicYear
from compass.reports.pdf import render_student_profiling_pdf
from compass.reports.services import build_student_profiling_report, resolve_report_access_scope
from compass.reports.xlsx import render_student_profiling_xlsx
from compass.routine_interviews.services import list_direct_student_candidates
from compass.student_support.services import get_student_support_context
from tests.inventory_test_helpers import minimum_normalized_inventory_values
from tests.test_inventory_counselor_review import (
    affiliate,
    auth_client,
    configure_year,
    context,
    make_head,
    make_org,
    make_user,
    sync_policy,
)

K1, K2, K3, K4, K5, K6, K7, K8 = (
    base64.urlsafe_b64encode(bytes([n]) * 32).decode() for n in range(111, 119)
)
SETTING = content.SETTING
BEFORE = [("inventory", "0005_submission_history_reopen")]
BACKFILLED = [("inventory", "0006_encrypt_confidential_content")]
AFTER = [("inventory", "0007_remove_plaintext_confidential_content")]
NAMES = tuple(name for name, _, _ in content.FAMILIES)
REASON = "PRIVATE-REOPEN-SENTINEL 雪"


@pytest.fixture(autouse=True)
def ring(settings):
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


def private_payload(family):
    if family == "InventoryReopenEvent":
        return {"reason": REASON}
    payload = content.PROJECTIONS[family]().payload()
    for name in payload:
        if name == "date_of_birth":
            payload[name] = "1970-01-02"
        elif name == "age":
            payload[name] = 20
        elif name == "sex":
            payload[name] = "FEMALE"
        elif name == "prior_counseling_experience":
            payload[name] = True
        elif name == "immunizations":
            payload[name] = ["OTHER", "HEPATITIS_B"]
        elif name == "email_address":
            payload[name] = "private-inventory-sentinel@example.edu"
        else:
            payload[name] = f"PRIVATE-{name.upper()}-SENTINEL 雪 café"
    return payload


def example(family):
    model = apps.get_model("inventory", family)
    values = {} if family == "StudentInventory" else {"inventory_id": uuid4()}
    values.update(
        {
            "StudentInventory": {"living_arrangement": "BOARDING_HOUSE", "pwd_status": "PWD"},
            "InventoryFamilyMember": {"kind": "FATHER"},
            "InventorySibling": {"sort_order": 0},
            "InventoryEducationEntry": {"level": "ELEMENTARY"},
            "InventoryOrganizationMembership": {"scope": "INSIDE_SCHOOL", "sort_order": 0},
            "InventoryTransportationEntry": {"mode": "BUS", "frequency_category": "OTHER"},
        }.get(family, {})
    )
    row = model(**values)
    content.write_confidential_content(row, private_payload(family))
    return row


def column(family):
    return next(col for name, col, _ in content.FAMILIES if name == family)


def safe(value, *extras):
    text = str(value)
    assert "PRIVATE-" not in text and K1 not in text and K2 not in text
    assert all(extra not in text for extra in extras)


@pytest.mark.parametrize("family", NAMES)
def test_runtime_frozen_wire_compatible_exact_schema_no_implicit_plaintext(family):
    row = example(family)
    token = getattr(row, column(family))
    envelope = json.loads(Fernet(K1).decrypt(token.encode()))
    assert type(envelope["schema_version"]) is int and envelope["schema_version"] == 1
    assert set(envelope) == {"schema_version", "payload", *content.binding(row, family)}
    assert envelope["payload"] == private_payload(family)
    assert frozen.decrypt(frozen.keyring(), row, token, family) == envelope["payload"]
    setattr(row, column(family), frozen.encrypt(frozen.keyring(), row, envelope["payload"], family))
    assert content.read_confidential_content(row).payload() == private_payload(family)
    assert not any(hasattr(row, name) for name in content.FIELDS[family])


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
        "non-string",
        "nul",
        "surrogate",
    ],
)
def test_all_families_fail_closed_with_safe_context(family, fault):
    row = example(family)
    col = column(family)
    token = getattr(row, col)
    if fault == "missing":
        token = None
    elif fault == "tamper":
        token = token[:40] + ("A" if token[40] != "A" else "B") + token[41:]
    elif fault == "truncate":
        token = token[:32]
    elif fault == "nonascii":
        token = "雪"
    elif fault == "random":
        token = "private-broken-sentinel"
    else:
        envelope = json.loads(Fernet(K1).decrypt(token.encode()))
        payload = envelope["payload"]
        first = next(name for name, value in payload.items() if isinstance(value, str))
        if fault == "schema":
            envelope["schema_version"] = 2
        elif fault == "boolean-version":
            envelope["schema_version"] = True
        elif fault == "missing-field":
            payload.pop(first)
        elif fault == "extra-field":
            payload["unexpected"] = "PRIVATE-EXTRA-SENTINEL"
        else:
            payload[first] = {
                "null": None,
                "non-string": 1,
                "nul": "a\x00b",
                "surrogate": "\ud800",
            }[fault]
        token = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    setattr(row, col, token)
    with pytest.raises(content.InventoryConfidentialContentUnavailable) as caught:
        content.read_confidential_content(row)
    safe(caught.value, "private-broken-sentinel")
    assert caught.value.family == family and caught.value.object_id == row.pk
    assert caught.value.reason in {"missing", "undecryptable", "malformed", "unsupported_schema"}


@pytest.mark.parametrize(
    "family,attribute",
    [
        (family, attribute)
        for family, values in content.BINDINGS.items()
        for attribute in values.values()
    ],
)
def test_each_authenticated_binding_rejects_transplant(family, attribute):
    row = example(family)
    old = getattr(row, attribute)
    setattr(
        row,
        attribute,
        old + 1
        if type(old) is int
        else uuid4()
        if attribute.endswith("id") or attribute == "pk"
        else "OTHER",
    )
    with pytest.raises(content.InventoryConfidentialContentUnavailable) as caught:
        content.read_confidential_content(row)
    assert caught.value.reason == "binding_mismatch"


@pytest.mark.parametrize("source,target", [(a, b) for a in NAMES for b in NAMES if a != b])
def test_cross_family_transplant_rejected(source, target):
    row, other = example(target), example(source)
    setattr(row, column(target), getattr(other, column(source)))
    with pytest.raises(content.InventoryConfidentialContentUnavailable):
        content.read_confidential_content(row)


@pytest.mark.parametrize(
    "family,field,limit",
    [
        (family, name, maximum)
        for family, fields in content.FIELDS.items()
        for name, maximum in fields.items()
        if maximum is not None and name != "sex"
    ],
)
def test_original_text_limits_not_weakened(family, field, limit):
    row = example(family)
    payload = private_payload(family)
    payload[field] = "a" * (limit + 1)
    with pytest.raises(services.InvalidInventoryInput) as caught:
        content.write_confidential_content(row, payload)
    safe(caught.value)


@pytest.mark.parametrize(
    "family,field,value",
    [
        ("StudentInventory", "prior_counseling_experience", 1),
        ("StudentInventory", "immunizations", "OTHER"),
        ("StudentInventory", "immunizations", ["UNSUPPORTED"]),
        ("InventoryFamilyMember", "date_of_birth", "19700102"),
        ("InventorySibling", "age", True),
        ("InventorySibling", "age", -1),
        ("InventorySibling", "age", 32768),
        ("InventorySibling", "sex", "OTHER"),
        ("StudentInventory", "email_address", "invalid-email"),
        ("InventoryReopenEvent", "reason", "  "),
    ],
)
def test_strict_typed_payloads(family, field, value):
    row = example(family)
    payload = private_payload(family)
    payload[field] = value
    with pytest.raises(services.InvalidInventoryInput):
        content.write_confidential_content(row, payload)


@pytest.fixture
def world(db):
    return make_world()


def make_world():
    sync_policy()
    call_command("sync_institutional_forms", verbosity=0)
    student = make_user(
        "inventory-private-student@example.edu", "STUDENT", institutional_id="SEARCH-001"
    )
    other = make_user("inventory-private-other@example.edu", "STUDENT")
    head = make_head("inventory-private-head@example.edu")
    counselor = make_user("inventory-outside-counselor@example.edu", "COUNSELOR")
    year = configure_year(head)
    _, college, program = make_org("PRIVATE")
    affiliate(student, college)
    item = services.ensure_current_inventory(student=student, context=context(student))
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(private_payload("StudentInventory"))
    values.update(
        living_arrangement="BOARDING_HOUSE",
        boarding_exclusive=True,
        pwd_status="PWD",
        civil_status_category="OTHER",
        current_religion_category="OTHER",
    )
    values["family_members"] = [
        {
            "kind": kind,
            "occupation_category": "OTHER",
            "annual_income_status": "NONE",
            **private_payload("InventoryFamilyMember"),
        }
        for kind in ("FATHER", "MOTHER")
    ]
    values["siblings"] = [
        {"sort_order": 0, "is_self": False, **private_payload("InventorySibling")}
    ]
    values["education_entries"] = [
        {
            "level": "ELEMENTARY",
            **{
                **private_payload("InventoryEducationEntry"),
                "school_attended_address": "PRIVATE-SCHOOL",
            },
        }
    ]
    values["organization_memberships"] = [
        {
            "scope": "INSIDE_SCHOOL",
            "sort_order": 0,
            **private_payload("InventoryOrganizationMembership"),
        }
    ]
    values["transportation_entries"] = [
        {
            "mode": "BUS",
            "frequency_category": "OTHER",
            "fare": "10",
            **private_payload("InventoryTransportationEntry"),
        }
    ]
    item = services.replace_current_inventory(student=student, values=values)
    return dict(
        student=student,
        other=other,
        head=head,
        counselor=counselor,
        year=year,
        program=program,
        item=item,
    )


def submitted(world):
    return services.submit_current_inventory(
        student=world["student"], context=context(world["student"])
    )


def event(world, item):
    services.reopen_inventory_for_correction(
        actor=world["head"], inventory_id=item.pk, reason=REASON, context=context(world["head"])
    )
    return InventoryReopenEvent.objects.get(inventory=item)


def raw(model, pk):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{model._meta.db_table}" WHERE id = %s', [pk])
        return dict(zip([col.name for col in cursor.description], cursor.fetchone(), strict=True))


def columns(model):
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, model._meta.db_table)
        }


def snapshots():
    return {
        (name, row.pk): raw(apps.get_model("inventory", name), row.pk)
        for name, _, _ in content.FAMILIES
        for row in apps.get_model("inventory", name).objects.all()
    }


def effects():
    return tuple(model.objects.count() for model in (AuditEvent, Notification, EmailDelivery))


def test_storage_ciphertext_only_and_normalized_columns_queryable(world):
    item = submitted(world)
    event(world, item)
    for name, col, _ in content.FAMILIES:
        model = apps.get_model("inventory", name)
        assert not set(content.FIELDS[name]) & columns(model)
        for row in model.objects.all():
            safe(raw(model, row.pk))
            assert raw(model, row.pk)[col].startswith("gAAAA")
    # E0 saved identity is deliberately queryable; private sentinels are not present.
    assert StudentInventory.objects.filter(
        student_number="SEARCH-001", pwd_status="PWD", year_level=1
    ).exists()
    assert (
        item.family_members.filter(
            occupation_category="OTHER", annual_income_status="NONE", annual_income_previous_year=0
        ).count()
        == 2
    )
    assert item.transportation_entries.filter(frequency_category="OTHER", fare=10).exists()
    assert item.geographic_locations.filter(kind="CURRENT", not_specified=True).exists()


def test_metadata_dependencies_work_with_key_and_decrypt_unavailable(world, monkeypatch, settings):
    item = submitted(world)
    clients = {name: auth_client(world[name]) for name in ("head", "student")}
    from tests.test_routine_interviews import create_counseling_service

    create_counseling_service(world["head"])
    access = resolve_report_access_scope(world["head"])

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata-only operation decrypted private Inventory content")

    monkeypatch.setattr(content, "decrypt_bound_json", forbidden)
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = ()
    for path in (
        "/api/v1/inventory/students?page_size=1&search=SEARCH-001&status=SUBMITTED",
        f"/api/v1/inventory/students/{world['student'].pk}/history",
    ):
        assert clients["head"].get(path).status_code == 200
    assert clients["student"].get("/api/v1/inventory/me/history").status_code == 200
    assert clients["student"].get("/api/v1/inventory/me/status").status_code == 200
    assert services.require_current_submitted_inventory(world["student"]).pk == item.pk
    assert services.has_current_submitted_inventory(world["student"])
    assert get_student_support_context(
        actor=world["head"], student_id=world["student"].pk
    ).available
    assert (
        build_student_profiling_report(access_scope=access)["report_context"][
            "submitted_inventory_count"
        ]
        == 1
    )
    assert render_student_profiling_pdf(access_scope=access).pdf_bytes.startswith(b"%PDF")
    assert render_student_profiling_xlsx(access_scope=access).xlsx_bytes.startswith(b"PK")
    assert (
        list_direct_student_candidates(counselor=world["head"], search="SEARCH-001")
        .items[0]
        .inventory.pk
        == item.pk
    )
    safe(build_student_profiling_report(access_scope=access))


def test_all_unauthorized_or_draft_raw_reads_fail_before_decrypt(world, monkeypatch):
    clients = {name: auth_client(world[name]) for name in ("head", "other", "counselor")}

    def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized or DRAFT decryption")

    monkeypatch.setattr(content, "decrypt_bound_json", forbidden)
    item = world["item"]
    for suffix in ("", "/pdf"):
        assert (
            clients["head"].get(f"/api/v1/inventory/records/{item.pk}{suffix}").status_code == 409
        )
        assert (
            clients["counselor"].get(f"/api/v1/inventory/records/{item.pk}{suffix}").status_code
            == 404
        )
        assert clients["other"].get(f"/api/v1/inventory/me/{item.pk}{suffix}").status_code == 404
    # Reopening changes only structural state and encrypts a reason; no raw-content read.
    StudentInventory.objects.filter(pk=item.pk).update(
        submitted_at=timezone.now(), first_submitted_at=timezone.now()
    )
    event(world, item)
    assert clients["head"].get(f"/api/v1/inventory/records/{item.pk}").status_code == 409


@pytest.mark.parametrize("family", NAMES)
def test_authorized_unreadable_family_generic_500_no_partial_repair(world, family, caplog):
    item = submitted(world)
    if family == "InventoryReopenEvent":
        event(world, item)
    model = apps.get_model("inventory", family)
    row = model.objects.first()
    model.objects.filter(pk=row.pk).update(**{column(family): "private-corrupt-sentinel"})
    before = snapshots()
    response = auth_client(world["student"]).get("/api/v1/inventory/me/current")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "inventory_confidential_content_unavailable"
    safe(response.content, "private-corrupt-sentinel")
    safe(caplog.text, "private-corrupt-sentinel")
    assert snapshots() == before
    if family != "InventoryReopenEvent":
        response = auth_client(world["head"]).get(f"/api/v1/inventory/records/{item.pk}/pdf")
        assert response.status_code == 500
        assert not AuditEvent.objects.filter(action="document.download_released").exists()


def test_full_replacement_does_not_silently_repair_corruption(world):
    item = world["item"]
    row = item.siblings.get()
    row.__class__.objects.filter(pk=row.pk).update(confidential_content_ciphertext="broken")
    before = snapshots()
    with pytest.raises(content.InventoryConfidentialContentUnavailable):
        services.replace_current_inventory(
            student=world["student"],
            values=minimum_normalized_inventory_values(program_id=world["program"].pk),
        )
    assert snapshots() == before


def test_owner_submitted_detail_pdf_projection_and_content_free_effects(world, monkeypatch):
    item = submitted(world)
    read = content.decrypt_bound_json
    seen = []

    def observe(*args, **kwargs):
        seen.append(kwargs["binding"])
        return read(*args, **kwargs)

    monkeypatch.setattr(content, "decrypt_bound_json", observe)
    private = content.read_inventory_private_projection(item)
    assert len(seen) == 7  # root + two parents + four other child tables
    seen.clear()
    # Builder consumes the authorized projection and never decrypts.
    projection = documents.build_inventory_render_context(item, private=private)
    assert seen == []
    assert projection["inventory_form"]["concerns"] == private.root.current_concerns
    response = auth_client(world["student"]).get(f"/api/v1/inventory/me/{item.pk}/pdf")
    assert response.status_code == 200 and len(seen) == 7
    pdf = PdfReader(BytesIO(response.content))
    assert len(pdf.pages) == 3
    text = (
        "".join(page.extract_text() or "" for page in pdf.pages).replace("\n", "").replace(" ", "")
    )
    assert "PRIVATE-CURRENT_CONCERNS-SENTINEL" in text
    assert "PRIVATE-SCHOOL" in text
    event(world, item)
    assert (
        auth_client(world["student"])
        .get("/api/v1/inventory/me/status")
        .json()["latest_correction"]["message"]
        == REASON
    )
    for model in (AuditEvent, Notification, EmailDelivery):
        for row in model.objects.all():
            safe(row.__dict__)


@pytest.fixture
def settings_env(monkeypatch):
    values = {
        "SECRET_KEY": "test-only-secret",
        "AUTH_TOTP_ENCRYPTION_KEY": K3,
        "WEB_PUSH_STORAGE_KEY": K4,
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS": K5,
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS": K6,
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS": K7,
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS": K8,
        SETTING: K1,
        "WEB_PUSH_ENABLED": "false",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
        monkeypatch.delenv(f"{name}_FILE", raising=False)


def load_settings():
    return runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))


@pytest.mark.parametrize("value", [None, "", "private-invalid-key", f"{K1},{K1}", f"{K1},"])
def test_required_ordered_config_keyring(settings_env, monkeypatch, value):
    if value is None:
        monkeypatch.delenv(SETTING)
    else:
        monkeypatch.setenv(SETTING, value)
    with pytest.raises(ValueError) as caught:
        load_settings()
    safe(caught.value, "private-invalid-key")


@pytest.mark.parametrize(
    "domain",
    [
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    ],
)
def test_config_rejects_reuse_including_previous_key(settings_env, monkeypatch, domain):
    monkeypatch.setenv(domain, f"{K2},{K1}" if domain.endswith("_KEYS") else K1)
    with pytest.raises(ValueError, match="must not reuse") as caught:
        load_settings()
    safe(caught.value)


def test_file_configuration_order(settings_env, monkeypatch, tmp_path):
    path = tmp_path / "synthetic-inventory-ring"
    path.write_text(f"{K2},{K1}\r\n")
    monkeypatch.delenv(SETTING)
    monkeypatch.setenv(f"{SETTING}_FILE", str(path))
    assert load_settings()[SETTING] == (K2, K1)


def rotate(**options):
    out, err = StringIO(), StringIO()
    call_command("rotate_inventory_confidential_content", stdout=out, stderr=err, **options)
    safe(out.getvalue())
    safe(err.getvalue())
    return out.getvalue()


def test_rotation_all_seven_families_bytes_timestamp_metadata_idempotent(world, settings):
    item = submitted(world)
    event(world, item)
    before, counts = snapshots(), effects()
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    assert rotate(dry_run=True, batch_size=1).count("failures 0") == 7
    assert snapshots() == before
    assert rotate(batch_size=1).count("failures 0") == 7
    after = snapshots()
    for (family, pk), row in before.items():
        col = column(family)
        old, new = row[col].encode(), after[family, pk][col].encode()
        assert Fernet(K1).decrypt(old) == Fernet(K2).decrypt(new)
        assert Fernet(K1).extract_timestamp(old) == Fernet(K2).extract_timestamp(new)
        assert {k: v for k, v in row.items() if k != col} == {
            k: v for k, v in after[family, pk].items() if k != col
        }
    assert effects() == counts
    rotate(batch_size=1)
    assert snapshots() == after


def test_rotation_safe_bounded_failures_and_batch_validation(world):
    item = world["item"]
    InventoryReopenEvent.objects.bulk_create(
        [
            InventoryReopenEvent(
                inventory=item,
                reopened_by=world["head"],
                reason_ciphertext="private-broken-token",
                reopened_at=timezone.now(),
            )
            for _ in range(27)
        ]
    )
    before = snapshots()
    for dry in (True, False):
        out, err = StringIO(), StringIO()
        with pytest.raises(CommandError) as caught:
            call_command(
                "rotate_inventory_confidential_content",
                dry_run=dry,
                batch_size=1,
                stdout=out,
                stderr=err,
            )
        assert err.getvalue().count("Unreadable:") == 20 and "and 7 more" in err.getvalue()
        safe(out.getvalue(), "private-broken-token")
        safe(err.getvalue(), "private-broken-token")
        safe(caught.value)
        assert snapshots() == before
    for size in (0, 1001):
        with pytest.raises(CommandError, match="between 1 and 1000"):
            rotate(batch_size=size)


@pytest.mark.django_db(transaction=True)
def test_rotation_real_row_locks_and_interruption_resume(world, settings, monkeypatch):
    submitted(world)
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    original = content.reencrypt_confidential_content
    command = importlib.import_module(
        "compass.inventory.management.commands.rotate_inventory_confidential_content"
    )
    seen = []

    def interrupt(row):
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout = '100ms'")
                with pytest.raises(OperationalError, match="lock timeout"):
                    cursor.execute(
                        f'UPDATE "{row._meta.db_table}" SET id = id WHERE id = %s', [row.pk]
                    )
        finally:
            writer.close()
        seen.append(row.pk)
        if len(seen) == 2:
            raise RuntimeError("synthetic interruption")
        return original(row)

    before = snapshots()
    monkeypatch.setattr(command, "reencrypt_confidential_content", interrupt)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        rotate(batch_size=1)
    intermediate = snapshots()
    # This test requires committed batches; transactional_db marker below prevents outer rollback.
    assert sum(before[key] != value for key, value in intermediate.items()) == 1
    monkeypatch.setattr(command, "reencrypt_confidential_content", original)
    rotate(batch_size=1)
    assert (
        snapshots()["StudentInventory", world["item"].pk]
        == intermediate["StudentInventory", world["item"].pk]
    )


@pytest.fixture
def legacy(transactional_db):
    initial = MigrationExecutor(connection).loader.graph.leaf_nodes()
    # PostgreSQL keeps dropped attribute slots. Refresh only empty, dedicated test tables;
    # rebuilding the entire dependency graph per case is unnecessary and very expensive.
    assert connection.settings_dict["NAME"].startswith("test_")
    models = [apps.get_model("inventory", name) for name in NAMES]
    assert all(not model.objects.exists() for model in models)
    tables = [model._meta.db_table for model in models]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
            "FROM pg_constraint WHERE contype = 'f' "
            "AND confrelid = ANY(%s::regclass[]) AND NOT conrelid = ANY(%s::regclass[])",
            [tables, tables],
        )
        incoming = cursor.fetchall()
    with connection.schema_editor() as editor:
        for model in reversed(models):
            editor.delete_model(model)
        for model in models:
            editor.create_model(model)
        for table, name, definition in incoming:
            editor.execute(
                f"ALTER TABLE {editor.quote_name(table)} "
                f"ADD CONSTRAINT {editor.quote_name(name)} {definition}"
            )
    world = make_world()
    MigrationExecutor(connection).migrate(BEFORE)
    try:
        yield MigrationExecutor(connection).loader.project_state(BEFORE).apps, world
    finally:
        # Test cleanup after dual-schema refusal/atomicity assertions; never production repair.
        for family, col, _ in content.FAMILIES:
            model = apps.get_model("inventory", family)
            existing = columns(model)
            if col in existing and set(content.FIELDS[family]) & existing:
                with connection.cursor() as cursor:
                    cursor.execute(f'UPDATE "{model._meta.db_table}" SET "{col}" = NULL')
        MigrationExecutor(connection).migrate(initial)


def all_raw():
    result = {}
    for family, _, _ in content.FAMILIES:
        model = apps.get_model("inventory", family)
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM "{model._meta.db_table}" ORDER BY id')
            names = [col.name for col in cursor.description]
            result[family] = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    return result


def old_root(registry, world, index, variant):
    year = AcademicYear.objects.create(label=f"204{index}-204{index + 1}")
    root = registry.get_model("inventory", "StudentInventory")
    values = (
        content.InventoryConfidentialContent().payload()
        if variant == "empty"
        else private_payload("StudentInventory")
    )
    if variant != "empty":
        values["current_address"] = '  雪 café\n"quotes" \\ path  '
    return root.objects.create(
        student_id=world["student"].pk,
        academic_year_id=year.pk,
        form_revision_id=world["item"].form_revision_id,
        full_name_snapshot="Historical searchable identity",
        student_number="HISTORICAL-1",
        living_arrangement="BOARDING_HOUSE" if variant != "empty" else "",
        # Legacy NULL normalized fields are intentional and retain raw answers exactly.
        civil_status_category=None,
        current_religion_category=None,
        pwd_status=None,
        submitted_at=timezone.now() if variant == "submitted" else None,
        first_submitted_at=timezone.now() if variant in {"submitted", "reopened"} else None,
        last_submitted_at=timezone.now() if variant in {"submitted", "reopened"} else None,
        **values,
    )


def old_reason(registry, world, root):
    return registry.get_model("inventory", "InventoryReopenEvent").objects.create(
        inventory_id=root.pk,
        reopened_by_id=world["head"].pk,
        reason=REASON,
        reopened_at=timezone.now(),
    )


def test_migrations_forward_reverse_exact_all_fields_empty_partial_legacy_submitted(legacy):
    registry, world = legacy
    for index, variant in enumerate(("empty", "filled", "submitted", "reopened")):
        root = old_root(registry, world, index, variant)
        if variant == "reopened":
            old_reason(registry, world, root)
    before, counts = all_raw(), effects()
    MigrationExecutor(connection).migrate(AFTER)
    for family, col, _ in content.FAMILIES:
        model = apps.get_model("inventory", family)
        assert not set(content.FIELDS[family]) & columns(model)
        for historical in before[family]:
            row = model.objects.get(pk=historical["id"])
            expected = {name: historical[name] for name in content.FIELDS[family]}
            if "date_of_birth" in expected and expected["date_of_birth"] is not None:
                expected["date_of_birth"] = expected["date_of_birth"].isoformat()
            assert content.read_confidential_content(row).payload() == expected
            assert {k: v for k, v in raw(model, row.pk).items() if k != col} == {
                k: v for k, v in historical.items() if k not in content.FIELDS[family]
            }
    MigrationExecutor(connection).migrate(BACKFILLED)
    restored = all_raw()
    for family, col, _ in content.FAMILIES:
        assert [{k: v for k, v in row.items() if k != col} for row in restored[family]] == before[
            family
        ]
    MigrationExecutor(connection).migrate(BEFORE)
    assert all_raw() == before and effects() == counts


def test_phase_b_reconciles_stale_root_children_reason_and_late_replacements(legacy):
    registry, world = legacy
    root = world["item"]
    old_reason(registry, world, root)
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    before = all_raw()
    for family, _col, _ in content.FAMILIES:
        model = registry.get_model("inventory", family)
        for row in model.objects.all():
            field = next(
                name
                for name, val in frozen.plaintext(row, family).items()
                if isinstance(val, str) and name not in {"sex", "email_address", "date_of_birth"}
            )
            model.objects.filter(pk=row.pk).update(**{field: "latest old writer 雪"})
    registry.get_model("inventory", "StudentInventory").objects.filter(pk=root.pk).update(
        accidents_experienced="latest health detail",
        current_fears="latest fear detail",
        prior_counseling_experience=False,
        prior_counselor_name="",
        prior_counseling_when="",
        prior_counseling_where="",
        civil_status_category="NOT_SPECIFIED",
        civil_status="",
        current_religion_category="NOT_SPECIFIED",
        current_religion="",
        pwd_status="NON_PWD",
        physical_disadvantage="",
        living_arrangement="OWN_HOUSE",
        boarding_exclusive=None,
        boarding_landlord_name="",
        boarding_address="",
    )
    # Every delete/recreate collection gets new UUIDs; keep Father as a readable stale row.
    replaced_ids = {}
    replacement_values = {
        "InventoryFamilyMember": {"kind": "MOTHER", "name": "late family"},
        "InventoryEducationEntry": {
            "level": "ELEMENTARY",
            "school_attended_address": "late school",
        },
        "InventoryOrganizationMembership": {
            "scope": "INSIDE_SCHOOL",
            "sort_order": 0,
            "organization_name": "late organization",
        },
        "InventoryTransportationEntry": {
            "mode": "BUS",
            "frequency_category": "OTHER",
            "frequency": "late replacement frequency",
        },
    }
    for family, values in replacement_values.items():
        model = registry.get_model("inventory", family)
        rows = model.objects.filter(inventory_id=root.pk)
        if family == "InventoryFamilyMember":
            rows = rows.filter(kind="MOTHER")
        replaced_ids[family] = list(rows.values_list("pk", flat=True))
        rows.delete()
        model.objects.create(inventory_id=root.pk, **values)
    siblings = registry.get_model("inventory", "InventorySibling")
    old_ids = list(siblings.objects.values_list("pk", flat=True))
    siblings.objects.all().delete()
    late = siblings.objects.create(
        inventory_id=root.pk, sort_order=0, name="latest replacement child", age=None, sex=""
    )
    transport = registry.get_model("inventory", "InventoryTransportationEntry")
    transport.objects.create(
        inventory_id=root.pk, mode="JEEPNEY", frequency_category="OTHER", frequency="late child"
    )
    event_model = registry.get_model("inventory", "InventoryReopenEvent")
    event_model.objects.create(
        inventory_id=root.pk,
        reopened_by_id=world["head"].pk,
        reason="late reason",
        reopened_at=timezone.now(),
    )
    expected = all_raw()
    MigrationExecutor(connection).migrate(AFTER)
    for family, ids in replaced_ids.items():
        assert not apps.get_model("inventory", family).objects.filter(pk__in=ids).exists()
    assert (
        not apps.get_model("inventory", "InventorySibling").objects.filter(pk__in=old_ids).exists()
    )
    assert (
        content.read_confidential_content(
            apps.get_model("inventory", "InventorySibling").objects.get(pk=late.pk)
        ).name
        == "latest replacement child"
    )
    for family, col, _ in content.FAMILIES:
        for saved in expected[family]:
            payload = content.read_confidential_content(
                apps.get_model("inventory", family).objects.get(pk=saved["id"])
            ).payload()
            original = {name: saved[name] for name in content.FIELDS[family]}
            if "date_of_birth" in original and original["date_of_birth"] is not None:
                original["date_of_birth"] = original["date_of_birth"].isoformat()
            assert payload == original
            assert {
                k: v for k, v in saved.items() if k not in content.FIELDS[family] and k != col
            } == {
                k: v
                for k, v in raw(apps.get_model("inventory", family), saved["id"]).items()
                if k != col
            }
    assert before != expected


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("fault", ["tamper", "schema", "payload", "binding"])
def test_corrupt_present_phase_a_aborts_earlier_updates_and_ddl(legacy, family, fault):
    registry, world = legacy
    old_reason(registry, world, world["item"])
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    model = registry.get_model("inventory", family)
    row = model.objects.order_by("pk").first()
    col = column(family)
    token = getattr(row, col)
    if fault == "tamper":
        token = "private-corrupt-token"
    else:
        envelope = json.loads(Fernet(K1).decrypt(token.encode()))
        if fault == "schema":
            envelope["schema_version"] = True
        elif fault == "payload":
            envelope["payload"]["unexpected"] = "PRIVATE-BAD-SENTINEL"
        else:
            envelope[next(iter(content.BINDINGS[family]))] = str(uuid4())
        token = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    model.objects.filter(pk=row.pk).update(**{col: token})
    registry.get_model("inventory", "StudentInventory").objects.filter(pk=world["item"].pk).update(
        nickname="latest stale writer"
    )
    before = all_raw()
    with pytest.raises(RuntimeError) as caught:
        MigrationExecutor(connection).migrate(AFTER)
    safe(caught.value, "private-corrupt-token")
    assert all_raw() == before
    assert ("inventory", AFTER[0][1]) not in MigrationExecutor(connection).loader.applied_migrations
    for family in NAMES:
        assert set(content.FIELDS[family]) <= columns(apps.get_model("inventory", family))


@pytest.mark.parametrize("family", NAMES)
def test_reverse_corruption_atomic_no_blank_restoration(legacy, family):
    registry, world = legacy
    old_reason(registry, world, world["item"])
    MigrationExecutor(connection).migrate(AFTER)
    model = apps.get_model("inventory", family)
    row = model.objects.first()
    col = column(family)
    original = getattr(row, col)
    model.objects.filter(pk=row.pk).update(**{col: "private-corrupt-token"})
    before = all_raw()
    try:
        with pytest.raises(RuntimeError) as caught:
            MigrationExecutor(connection).migrate(BEFORE)
        safe(caught.value, "private-corrupt-token")
        assert all_raw() == before
        for name in NAMES:
            assert not set(content.FIELDS[name]) & columns(apps.get_model("inventory", name))
    finally:
        model.objects.filter(pk=row.pk).update(**{col: original})


def test_phase_b_fences_all_seven_old_writer_tables_before_reads(legacy, monkeypatch):
    registry, world = legacy
    old_reason(registry, world, world["item"])
    MigrationExecutor(connection).migrate(BACKFILLED)
    phase = importlib.import_module(
        "compass.inventory.migrations.0007_remove_plaintext_confidential_content"
    )
    original, seen = phase._lock, []

    def probe(registry, editor):
        original(registry, editor)
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout = '100ms'")
                for family in NAMES:
                    table = registry.get_model("inventory", family)._meta.db_table
                    with pytest.raises(OperationalError, match="lock timeout"):
                        cursor.execute(f'UPDATE "{table}" SET id = id')
                    seen.append(family)
        finally:
            writer.close()

    monkeypatch.setattr(phase, "_lock", probe)
    MigrationExecutor(connection).migrate(AFTER)
    assert seen == list(NAMES)


def test_dual_schema_rotation_refused_both_modes_and_identical_tokens_retained(legacy):
    MigrationExecutor(connection).migrate(BACKFILLED)
    before = all_raw()
    for dry in (True, False):
        with pytest.raises(CommandError, match="Legacy plaintext"):
            rotate(dry_run=dry)
    MigrationExecutor(connection).migrate(AFTER)
    after = all_raw()
    for family, col, _ in content.FAMILIES:
        assert [row[col] for row in before[family]] == [row[col] for row in after[family]]


@pytest.mark.parametrize(
    "fault",
    [
        "prior",
        "boarding",
        "pwd",
        "family-other",
        "transport-other",
        "transport-not-specified",
        "civil-fixed",
        "religion-fixed",
    ],
)
def test_latest_inconsistent_plaintext_aborts_destruction(legacy, fault):
    MigrationExecutor(connection).migrate(BACKFILLED)
    registry = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    if fault in {"prior", "boarding", "pwd", "civil-fixed", "religion-fixed"}:
        model = registry.get_model("inventory", "StudentInventory")
        values = {
            "prior": {"prior_counseling_experience": False},
            "boarding": {"living_arrangement": "OWN_HOUSE"},
            "pwd": {"pwd_status": "NON_PWD"},
            "civil-fixed": {"civil_status_category": "SINGLE"},
            "religion-fixed": {"current_religion_category": "NONE"},
        }[fault]
    elif fault == "family-other":
        model = registry.get_model("inventory", "InventoryFamilyMember")
        values = {"occupation": "", "occupation_category": "OTHER"}
    else:
        model = registry.get_model("inventory", "InventoryTransportationEntry")
        values = (
            {"frequency_category": "OTHER", "frequency": ""}
            if fault == "transport-other"
            else {"frequency_category": "NOT_SPECIFIED", "frequency": "stale"}
        )
    row = model.objects.first()
    original = {name: getattr(row, name) for name in values}
    model.objects.filter(pk=row.pk).update(**values)
    before = all_raw()
    try:
        with pytest.raises(RuntimeError, match="malformed"):
            MigrationExecutor(connection).migrate(AFTER)
        assert all_raw() == before
    finally:
        model.objects.filter(pk=row.pk).update(**original)


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("missing", [None, ""])
def test_database_requires_nonnull_nonempty_ciphertext(world, family, missing):
    model = apps.get_model("inventory", family)
    if family == "InventoryReopenEvent":
        event(world, submitted(world))
    row = model.objects.first()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            model.objects.filter(pk=row.pk).update(**{column(family): missing})
    assert content.read_confidential_content(model.objects.get(pk=row.pk))


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_concerns", "bad\x00value"),
        ("current_fears", "\ud800"),
        ("prior_counseling_experience", 1),
        ("immunizations", ["UNKNOWN"]),
        ("nickname", "x" * 101),
        ("email_address", "invalid email"),
    ],
)
def test_invalid_service_input_does_not_persist_or_disclose_content(world, field, value):
    before, counts = snapshots(), effects()
    with pytest.raises(services.InvalidInventoryInput) as caught:
        services.replace_current_inventory(student=world["student"], values={field: value})
    safe(caught.value, "bad\x00value", "invalid email")
    assert snapshots() == before and effects() == counts


def test_combined_prior_and_boarding_validation_precedes_encrypt(world, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Encrypted an inconsistent logical form")

    monkeypatch.setattr(content, "encrypt_bound_json", forbidden)
    for values in ({"prior_counseling_experience": False}, {"living_arrangement": "OWN_HOUSE"}):
        with pytest.raises(services.InvalidInventoryInput):
            services.replace_current_inventory(student=world["student"], values=values)


@pytest.mark.parametrize("role", ["GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"])
def test_non_counselor_roles_never_decrypt_raw_inventory(world, monkeypatch, role):
    item = submitted(world)
    actor = make_user(f"private-denied-{role.lower()}@example.edu", role)
    client = auth_client(actor)

    def forbidden(*args, **kwargs):
        pytest.fail("Non-Counselor raw decryption")

    monkeypatch.setattr(content, "decrypt_bound_json", forbidden)
    for suffix in ("", "/pdf"):
        assert client.get(f"/api/v1/inventory/records/{item.pk}{suffix}").status_code == 403


@pytest.mark.parametrize("keyring", [(), "", "invalid-key", (K1, K1)])
def test_migration_bad_keyring_aborts_without_changes(legacy, settings, keyring):
    before = all_raw()
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = keyring
    try:
        with pytest.raises(RuntimeError) as caught:
            MigrationExecutor(connection).migrate(BACKFILLED)
        safe(caught.value, "invalid-key")
        assert all_raw() == before
    finally:
        settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)
