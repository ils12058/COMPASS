"""ADR-086 private storage, Head disclosure, independent snapshots, migrations/rotation."""

import json
from dataclasses import FrozenInstanceError, asdict
from io import StringIO
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from compass.accounts import confidential_profile as account_content
from compass.accounts.models import Designation, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.feedback import api, services
from compass.feedback import confidential_content as content
from compass.feedback.migrations import _feedback_confidential_content_v1 as frozen
from compass.feedback.models import ClientSatisfactionResponse, CustomerFeedbackResponse
from compass.institutional_forms.models import FormRevision
from compass.notifications.models import EmailDelivery, Notification
from tests.profile_fixtures import set_profile
from tests.residual_encryption_helpers import (
    FAULTS,
    K1,
    K2,
    cleanup_legacy,
    columns,
    command,
    envelope,
    fence_probe,
    metadata,
    migrate,
    mutated,
    raw,
    setup_legacy,
    state,
)
from tests.test_feedback import (
    auth_client,
    make_feedback_opportunity,
    make_head,
    make_user,
    post_json,
    sync_policy,
    valid_csm_payload,
    valid_f14_payload,
)

NAMES = content.FAMILIES
BEFORE = [("feedback", "0002_feedback_opportunity")]
BACKFILLED = [("feedback", "0003_encrypt_confidential_content")]
AFTER = [("feedback", "0004_remove_plaintext_confidential_content")]
PRIVATE = {
    NAMES[0]: {
        "other_service": "",
        "additional_feedback": "PRIVATE-feedback 雪 café 🎓",
        "future_service_improvement": "PRIVATE-future\nnext",
        "address_snapshot": "PRIVATE-address",
        "mobile_number_snapshot": "PRIVATE-phone",
    },
    NAMES[1]: {
        "suggestions": "PRIVATE-suggestions 雪 café 🎓",
        "email": "private-email-sentinel@example.edu",
    },
}


@pytest.fixture(autouse=True)
def ring(settings):
    settings.FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


def example(family):
    model = apps.get_model("feedback", family)
    item = model(
        **(
            {"form_revision_id": uuid4()}
            if family == NAMES[0]
            else {"instrument_schema_version": 1}
        )
    )
    cls = (
        content.CustomerFeedbackConfidentialContent
        if family == NAMES[0]
        else content.ClientSatisfactionConfidentialContent
    )
    content.write_feedback_confidential_content(item, cls(**PRIVATE[family]))
    return item


def safe(value, *extras):
    assert all(
        secret not in str(value)
        for secret in [K1, K2, "PRIVATE-", "private-email-sentinel", *extras]
    )


def forbid(*args, **kwargs):
    pytest.fail("Confidential decryption ran before authorization or in a metadata operation")


@pytest.mark.parametrize("family", NAMES)
def test_exact_envelope_frozen_roundtrip_projection_and_removed_attributes(family):
    item = example(family)
    token = getattr(item, content.COLUMN)
    data = envelope(token)
    assert (
        type(data["schema_version"]) is int
        and data["schema_version"] == 1
        and data["payload"] == PRIVATE[family]
    )
    assert data == {"schema_version": 1, **content._binding(item), "payload": PRIVATE[family]}
    assert frozen.decrypt((K1,), item, token, family) == PRIVATE[family]
    setattr(item, content.COLUMN, frozen.encrypt((K1,), item, PRIVATE[family], family))
    private = content.read_feedback_confidential_content(item)
    assert asdict(private) == PRIVATE[family]
    with pytest.raises(FrozenInstanceError):
        setattr(private, next(iter(PRIVATE[family])), "changed")
    assert not any(hasattr(item, f) for f in PRIVATE[family])


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("fault", FAULTS)
def test_all_failures_bounded_content_free(family, fault):
    item = example(family)
    setattr(item, content.COLUMN, mutated(getattr(item, content.COLUMN), fault))
    with pytest.raises(content.FeedbackConfidentialContentUnavailable) as caught:
        content.read_feedback_confidential_content(item)
    assert (
        set(vars(caught.value)) == {"object_id", "family", "reason"}
        and caught.value.family == family
    )
    safe(caught.value)


@pytest.mark.parametrize("family", NAMES)
def test_parent_revision_instrument_and_row_binding_transplants(family):
    item = example(family)
    other = example(family)
    setattr(other, content.COLUMN, getattr(item, content.COLUMN))
    with pytest.raises(content.FeedbackConfidentialContentUnavailable):
        content.read_feedback_confidential_content(other)
    if family == NAMES[0]:
        item.form_revision_id = uuid4()
    else:
        item.instrument_schema_version = 2
    with pytest.raises(content.FeedbackConfidentialContentUnavailable) as caught:
        content.read_feedback_confidential_content(item)
    assert caught.value.reason == "binding_mismatch"


def test_distinct_account_feedback_keys_and_cross_family_tokens(settings):
    settings.ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2,)
    user = User()
    account_content.write_account_profile_confidential_content(
        user, account_content.AccountProfileConfidentialContent()
    )
    feedback = example(NAMES[0])
    other = example(NAMES[1])
    other.confidential_content_ciphertext = feedback.confidential_content_ciphertext
    with pytest.raises(content.FeedbackConfidentialContentUnavailable):
        content.read_feedback_confidential_content(other)
    user.profile_confidential_content_ciphertext = feedback.confidential_content_ciphertext
    with pytest.raises(account_content.AccountProfileConfidentialContentUnavailable):
        account_content.read_account_profile_confidential_content(user)
    feedback.confidential_content_ciphertext = example(NAMES[1]).confidential_content_ciphertext
    with pytest.raises(content.FeedbackConfidentialContentUnavailable):
        content.read_feedback_confidential_content(feedback)


@pytest.fixture
def world(db):
    sync_policy()
    student = make_user("private-student@example.edu")
    head = make_head()
    set_profile(
        student, current_address="PRIVATE-profile address", contact_number="PRIVATE-profile phone"
    )
    return student, head


def submitted(world, family):
    student, _ = world
    client = auth_client(student)
    values = valid_f14_payload() if family == NAMES[0] else valid_csm_payload()
    if family == NAMES[0]:
        values.update(
            additional_feedback=PRIVATE[family]["additional_feedback"],
            future_service_improvement=PRIVATE[family]["future_service_improvement"],
            address=PRIVATE[family]["address_snapshot"],
            mobile_number=PRIVATE[family]["mobile_number_snapshot"],
        )
    else:
        values.update(PRIVATE[family])
    path = "customer-feedback" if family == NAMES[0] else "csm"
    response = post_json(client, "/api/v1/feedback/" + path, values)
    assert response.status_code == 201, response.content
    return apps.get_model("feedback", family).objects.get()


@pytest.mark.parametrize("family", NAMES)
def test_raw_storage_queryable_metadata_content_free_audit_and_authorized_detail(
    world, family, monkeypatch
):
    item = submitted(world, family)
    model = type(item)
    for bad in (None, ""):
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.filter(pk=item.pk).update(**{content.COLUMN: bad})
    assert set(content.FIELDS[family]).isdisjoint(columns(model))
    safe(json.dumps(raw(model), default=str))
    for effect in [AuditEvent, Notification, EmailDelivery]:
        safe(json.dumps(list(effect.objects.values()), default=str))
    path = "customer-feedback" if family == NAMES[0] else "csm"
    client = auth_client(world[1])
    response = client.get(f"/api/v1/feedback/{path}/responses/{item.pk}")
    assert response.status_code == 200
    for f, val in PRIVATE[family].items():
        if f in {"address_snapshot", "mobile_number_snapshot"}:
            continue
        assert response.json()[f] == val
    monkeypatch.setattr(api, "read_feedback_confidential_content", forbid)
    monkeypatch.setattr(content, "read_feedback_confidential_content", forbid)
    search = "search=Feedback" if family == NAMES[0] else "service_availed=Guidance"
    response = client.get(f"/api/v1/feedback/{path}/responses?{search}&page_size=1")
    assert response.status_code == 200 and response.json()["items"][0]["id"] == str(item.pk)


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize(
    "role",
    ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER", "DPO"],
)
def test_denied_detail_never_decrypts(world, family, role, monkeypatch):
    item = submitted(world, family)
    user = make_user(
        f"denied-{role}@example.edu", role="INSTITUTIONAL_OFFICER" if role == "DPO" else role
    )
    if role == "DPO":
        UserDesignation.objects.create(user=user, designation=Designation.objects.get(code="DPO"))
    monkeypatch.setattr(api, "read_feedback_confidential_content", forbid)
    monkeypatch.setattr(content.crypto, "decrypt_bound_json", forbid)
    path = "customer-feedback" if family == NAMES[0] else "csm"
    assert auth_client(user).get(f"/api/v1/feedback/{path}/responses/{item.pk}").status_code == 403


@pytest.mark.parametrize("family", NAMES)
def test_corrupt_head_detail_generic500_no_partial_or_leak(world, family, caplog):
    item = submitted(world, family)
    type(item).objects.filter(pk=item.pk).update(**{content.COLUMN: "PRIVATE-broken"})
    before = raw(type(item))
    path = "customer-feedback" if family == NAMES[0] else "csm"
    response = auth_client(world[1]).get(f"/api/v1/feedback/{path}/responses/{item.pk}")
    assert (
        response.status_code == 500
        and response.json()["error"]["code"] == "feedback_confidential_content_unavailable"
    )
    safe(response.content)
    safe(caplog.text)
    assert raw(type(item)) == before


def test_f14_blank_fallback_once_independent_snapshot_and_explicit_contacts_skip_profile(
    world, monkeypatch
):
    student, _ = world
    client = auth_client(student)
    response = post_json(client, "/api/v1/feedback/customer-feedback", valid_f14_payload())
    assert response.status_code == 201
    item = CustomerFeedbackResponse.objects.get()
    token = item.confidential_content_ciphertext
    assert (
        content.read_feedback_confidential_content(item).address_snapshot
        == "PRIVATE-profile address"
    )
    set_profile(student, current_address="changed", contact_number="changed")
    assert CustomerFeedbackResponse.objects.get().confidential_content_ciphertext == token
    monkeypatch.setattr(services, "get_person_profile_context", forbid)
    payload = valid_f14_payload()
    payload.update(address="explicit", mobile_number="explicit")
    assert post_json(client, "/api/v1/feedback/customer-feedback", payload).status_code == 201


def test_f14_required_unreadable_fallback_is_generic500_without_marker_or_row(world):
    student, _ = world
    User.objects.filter(pk=student.pk).update(
        profile_confidential_content_ciphertext="PRIVATE-corrupt"
    )
    response = post_json(
        auth_client(student), "/api/v1/feedback/customer-feedback", valid_f14_payload()
    )
    assert (
        response.status_code == 500
        and response.json()["error"]["code"] == "feedback_confidential_content_unavailable"
    )
    assert not CustomerFeedbackResponse.objects.exists()
    assert not student.feedback_opportunities.exclude(customer_feedback_submitted_at=None).exists()


@pytest.mark.parametrize("family", NAMES)
def test_rotation_dry_real_timestamp_metadata_idempotence_and_failures(world, family, settings):
    item = submitted(world, family)
    model = type(item)
    before = raw(model)
    meta = metadata(model, content.COLUMN)
    effects = AuditEvent.objects.count()
    settings.FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    command("rotate_feedback_confidential_content", dry_run=True, batch_size=1)
    assert raw(model) == before
    command("rotate_feedback_confidential_content", batch_size=1)
    after = raw(model)
    for new, old in zip(after, before, strict=True):
        assert Fernet(K2).decrypt(new[content.COLUMN].encode()) == Fernet(K1).decrypt(
            old[content.COLUMN].encode()
        )
        assert Fernet(K2).extract_timestamp(new[content.COLUMN].encode()) == Fernet(
            K1
        ).extract_timestamp(old[content.COLUMN].encode())
    assert metadata(model, content.COLUMN) == meta and AuditEvent.objects.count() == effects
    command("rotate_feedback_confidential_content", batch_size=1)
    assert raw(model) == after
    model.objects.update(**{content.COLUMN: "PRIVATE-broken"})
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_feedback_confidential_content", stdout=out, stderr=err)
    safe(out.getvalue() + err.getvalue())
    assert model.objects.get().confidential_content_ciphertext == "PRIVATE-broken"


@pytest.fixture
def legacy(transactional_db):
    initial, registry = setup_legacy("feedback", BEFORE)
    try:
        yield registry
    finally:
        cleanup_legacy("feedback", NAMES, initial)


def old_rows(registry, index=0):
    revision = FormRevision.objects.filter(family__key="customer_feedback").first()
    if revision is None:
        from compass.institutional_forms.models import FormFamily

        family, _ = FormFamily.objects.get_or_create(
            key="customer_feedback", defaults={"title": "Test"}
        )
        revision = FormRevision.objects.create(family=family, internal_schema_version=1)
    values = valid_f14_payload()
    values = {
        k: v
        for k, v in values.items()
        if k not in {"respondent_name", "course_year", "address", "mobile_number"}
    }
    values["accommodated_by"] = ""
    first = registry.get_model("feedback", NAMES[0]).objects.create(
        form_revision_id=revision.pk,
        respondent_name_snapshot=f"Historical {index}",
        course_year_snapshot="BSIS4",
        **{**values, **PRIVATE[NAMES[0]]},
    )
    second = registry.get_model("feedback", NAMES[1]).objects.create(
        instrument_schema_version=1, **{**valid_csm_payload(), **PRIVATE[NAMES[1]]}
    )
    return first, second


def test_forward_phase_a_late_old_inserts_stale_missing_reverse_exact(legacy):
    rows = old_rows(legacy)
    stamps = [r.submitted_at for r in rows]
    migrate(BACKFILLED)
    reg = state(BACKFILLED)
    old_rows(reg, 1)
    for family, row in zip(NAMES, rows, strict=True):
        model = reg.get_model("feedback", family)
        field = next(iter(PRIVATE[family]))
        value = "PRIVATE-late" if field != "other_service" else ""
        model.objects.filter(pk=row.pk).update(**{field: value})
    migrate(AFTER)
    for family, row, stamp in zip(NAMES, rows, stamps, strict=True):
        model = apps.get_model("feedback", family)
        item = model.objects.get(pk=row.pk)
        assert item.submitted_at == stamp and set(PRIVATE[family]).isdisjoint(columns(model))
        content.read_feedback_confidential_content(item)
    migrate(BEFORE)
    reg = state(BEFORE)
    assert (
        reg.get_model("feedback", NAMES[1]).objects.get(pk=rows[1].pk).suggestions == "PRIVATE-late"
    )
    assert (
        reg.get_model("feedback", NAMES[0]).objects.get(pk=rows[0].pk).address_snapshot
        == PRIVATE[NAMES[0]]["address_snapshot"]
    )


@pytest.mark.parametrize("family", NAMES)
@pytest.mark.parametrize("fault", ["tamper", "binding", "schema", "wrong-type"])
def test_present_bad_forward_and_reverse_atomic_no_restoration(legacy, family, fault):
    rows = old_rows(legacy)
    migrate(BACKFILLED)
    model = state(BACKFILLED).get_model("feedback", family)
    item = model.objects.get(pk=rows[NAMES.index(family)].pk)
    token = item.confidential_content_ciphertext
    model.objects.filter(pk=item.pk).update(**{content.COLUMN: mutated(token, fault)})
    before = {n: raw(apps.get_model("feedback", n)) for n in NAMES}
    with pytest.raises(RuntimeError) as caught:
        migrate(AFTER)
    safe(caught.value)
    assert {n: raw(apps.get_model("feedback", n)) for n in NAMES} == before
    model.objects.filter(pk=item.pk).update(**{content.COLUMN: token})
    migrate(AFTER)
    apps.get_model("feedback", family).objects.filter(pk=item.pk).update(
        **{content.COLUMN: mutated(token, fault)}
    )
    before = {n: raw(apps.get_model("feedback", n)) for n in NAMES}
    with pytest.raises(RuntimeError):
        migrate(BEFORE)
    assert {n: raw(apps.get_model("feedback", n)) for n in NAMES} == before
    assert all(set(PRIVATE[n]).isdisjoint(columns(apps.get_model("feedback", n))) for n in NAMES)


@pytest.mark.parametrize("reverse", [False, True])
def test_writer_fence_on_both_tables_before_forward_and_reverse_ddl(legacy, monkeypatch, reverse):
    old_rows(legacy)
    migrate(AFTER if reverse else BACKFILLED)
    calls = fence_probe(
        "compass.feedback.migrations.0004_remove_plaintext_confidential_content",
        "feedback",
        NAMES,
        "submitted_at",
        monkeypatch,
        reverse,
    )
    migrate(BEFORE if reverse else AFTER)
    assert calls


def test_rotation_refuses_legacy_and_migration_does_not_use_runtime(legacy, monkeypatch):
    old_rows(legacy)
    migrate(BACKFILLED)
    for dry in (False, True):
        with pytest.raises(CommandError, match="Legacy"):
            command("rotate_feedback_confidential_content", dry_run=dry)
    monkeypatch.setattr(content, "read_feedback_confidential_content", forbid)
    monkeypatch.setattr(content, "write_feedback_confidential_content", forbid)
    migrate(AFTER)
    migrate(BEFORE)


@pytest.mark.parametrize(
    "family,field,value",
    [
        (NAMES[0], "additional_feedback", "x" * 4001),
        (NAMES[0], "future_service_improvement", "x" * 4001),
        (NAMES[0], "other_service", "x" * 256),
        (NAMES[0], "address", "x" * 2001),
        (NAMES[0], "mobile_number", "x" * 65),
        (NAMES[1], "suggestions", "x" * 4001),
        (NAMES[1], "email", "invalid-address"),
        (NAMES[1], "email", "x" * 321),
        (NAMES[0], "additional_feedback", "x\x00y"),
        (NAMES[1], "suggestions", "x\ud800y"),
    ],
)
def test_private_input_limits_utf8_email_keep_empty_storage_on_rejection(
    world, family, field, value
):
    values = valid_f14_payload() if family == NAMES[0] else valid_csm_payload()
    values[field] = value
    path = "customer-feedback" if family == NAMES[0] else "csm"
    response = post_json(auth_client(world[0]), "/api/v1/feedback/" + path, values)
    assert response.status_code == 422
    assert not apps.get_model("feedback", family).objects.exists()


def test_f14_stale_other_choices_reconciled_missing_csm_and_equal_tokens_retained(legacy):
    first, second = old_rows(legacy)
    first_model = legacy.get_model("feedback", NAMES[0])
    first_model.objects.filter(pk=first.pk).update(
        services_received=["COUNSELING", "OTHER"], other_service="PRIVATE-other original"
    )
    migrate(BACKFILLED)
    reg = state(BACKFILLED)
    model = reg.get_model("feedback", NAMES[0])
    old = model.objects.get(pk=first.pk).confidential_content_ciphertext
    reg.get_model("feedback", NAMES[1]).objects.filter(pk=second.pk).update(
        confidential_content_ciphertext=""
    )
    model.objects.filter(pk=first.pk).update(
        services_received=["COUNSELING"], other_service="", additional_feedback="PRIVATE-late prose"
    )
    equal_first, equal_second = old_rows(reg, 1)
    # Late rows with missing envelopes are backfilled, and valid equal envelopes are preserved.
    for item in [equal_first, equal_second]:
        payload = frozen.plaintext(item, item._meta.object_name)
        token = frozen.encrypt((K1,), item, payload, item._meta.object_name)
        type(item).objects.filter(pk=item.pk).update(confidential_content_ciphertext=token)
        item.confidential_content_ciphertext = token
    migrate(AFTER)
    row = CustomerFeedbackResponse.objects.get(pk=first.pk)
    assert row.confidential_content_ciphertext != old
    assert (
        content.read_feedback_confidential_content(row).additional_feedback == "PRIVATE-late prose"
    )
    for item in [equal_first, equal_second]:
        assert (
            apps.get_model("feedback", item._meta.object_name)
            .objects.get(pk=item.pk)
            .confidential_content_ciphertext
            == item.confidential_content_ciphertext
        )
    content.read_feedback_confidential_content(ClientSatisfactionResponse.objects.get(pk=second.pk))


@pytest.mark.django_db(transaction=True)
def test_feedback_rotation_locks_batches_interruption_resume(settings, monkeypatch):
    import importlib

    from django.db import OperationalError, connection

    sync_policy()
    student = make_user("resume-feedback@example.edu")
    for _ in range(2):
        opportunity = make_feedback_opportunity(student)
        services.create_csm_response(
            student=student,
            opportunity_id=opportunity.pk,
            values=valid_csm_payload(),
            context=AuditContext(actor=student),
        )
    settings.FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    module = importlib.import_module(
        "compass.feedback.management.commands.rotate_feedback_confidential_content"
    )
    original = module.reencrypt_feedback_confidential_content
    seen = []

    def interrupted(item):
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout='100ms'")
                with pytest.raises(OperationalError, match="lock timeout"):
                    cursor.execute(
                        "UPDATE feedback_clientsatisfactionresponse "
                        "SET submitted_at=submitted_at WHERE id=%s",
                        [item.pk],
                    )
        finally:
            writer.close()
        seen.append(item.pk)
        if len(seen) == 2:
            raise RuntimeError("Synthetic interruption")
        return original(item)

    monkeypatch.setattr(module, "reencrypt_feedback_confidential_content", interrupted)
    with pytest.raises(RuntimeError):
        command("rotate_feedback_confidential_content", batch_size=1)
    assert (
        sum(
            content.encrypted_with_primary_key(item.confidential_content_ciphertext)
            for item in ClientSatisfactionResponse.objects.all()
        )
        == 1
    )
    monkeypatch.setattr(module, "reencrypt_feedback_confidential_content", original)
    command("rotate_feedback_confidential_content", batch_size=1)
    assert all(
        content.encrypted_with_primary_key(item.confidential_content_ciphertext)
        for item in ClientSatisfactionResponse.objects.all()
    )


def test_csm_corruption_rolls_back_earlier_f14_reconciliation(legacy):
    first, second = old_rows(legacy)
    migrate(BACKFILLED)
    reg = state(BACKFILLED)
    reg.get_model("feedback", NAMES[0]).objects.filter(pk=first.pk).update(
        additional_feedback="PRIVATE-late edit"
    )
    reg.get_model("feedback", NAMES[1]).objects.filter(pk=second.pk).update(
        confidential_content_ciphertext="PRIVATE-corrupt"
    )
    before = {n: raw(apps.get_model("feedback", n)) for n in NAMES}
    with pytest.raises(RuntimeError):
        migrate(AFTER)
    assert {n: raw(apps.get_model("feedback", n)) for n in NAMES} == before
    assert "additional_feedback" in columns(CustomerFeedbackResponse)
