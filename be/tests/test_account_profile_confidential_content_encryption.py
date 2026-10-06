"""ADR-085 explicit storage, failure, disclosure, migration and rotation evidence."""

import importlib
import json
from dataclasses import FrozenInstanceError, asdict
from datetime import date
from io import StringIO

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction

from compass.account_management.services import serialize_account
from compass.accounts import confidential_profile as content
from compass.accounts.migrations import _account_profile_confidential_content_v1 as frozen
from compass.accounts.models import User
from compass.accounts.profiles import get_person_profile_context, update_my_profile
from compass.accounts.services import effective_capabilities
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.api import _person
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
from tests.test_profiles import auth_client, csrf_headers, make_user, patch_profile, sync_policy

BEFORE = [("accounts", "0006_rename_reference_capabilities")]
BACKFILLED = [("accounts", "0007_encrypt_confidential_content")]
AFTER = [("accounts", "0008_remove_plaintext_confidential_content")]
PAYLOAD = {
    "date_of_birth": "2000-01-02",
    "civil_status": "PRIVATE-civil 雪",
    "contact_number": "PRIVATE-mobile",
    "current_address": "PRIVATE-address\n café 🎓",
    "permanent_address": "PRIVATE-permanent",
}


@pytest.fixture(autouse=True)
def ring(settings):
    settings.ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


def example():
    user = User()
    write(user)
    return user


def write(user):
    content.write_account_profile_confidential_content(
        user,
        content.AccountProfileConfidentialContent(**{**PAYLOAD, "date_of_birth": date(2000, 1, 2)}),
    )


def safe(value, *tokens):
    text = str(value)
    assert all(x not in text for x in [K1, K2, "PRIVATE-", *tokens])


def forbid(*args, **kwargs):
    pytest.fail("Profile decryption reached an identity-only surface")


def test_exact_schema_immutable_projection_frozen_roundtrip():
    user = example()
    token = getattr(user, content.COLUMN)
    data = envelope(token)
    assert data == {"schema_version": 1, "user_id": str(user.pk), "payload": PAYLOAD}
    assert type(data["schema_version"]) is int
    assert frozen.decrypt((K1,), user, token, "User") == PAYLOAD
    setattr(user, content.COLUMN, frozen.encrypt((K1,), user, PAYLOAD, "User"))
    private = content.read_account_profile_confidential_content(user)
    assert private.date_of_birth == date(2000, 1, 2)
    with pytest.raises(FrozenInstanceError):
        private.civil_status = "changed"
    assert not any(hasattr(user, k) for k in PAYLOAD)


@pytest.mark.parametrize("fault", FAULTS)
def test_bounded_fail_closed_errors(fault):
    user = example()
    setattr(user, content.COLUMN, mutated(getattr(user, content.COLUMN), fault))
    with pytest.raises(content.AccountProfileConfidentialContentUnavailable) as caught:
        content.read_account_profile_confidential_content(user)
    assert set(vars(caught.value)) == {"user_id", "reason"}
    safe(caught.value)


@pytest.mark.parametrize("birthday", ["20000102", "2000-1-2", "2000-02-30", False, 4, ""])
def test_strict_canonical_date_payload(birthday):
    user = example()
    data = envelope(getattr(user, content.COLUMN))
    data["payload"]["date_of_birth"] = birthday
    setattr(user, content.COLUMN, Fernet(K1).encrypt(json.dumps(data).encode()).decode())
    with pytest.raises(content.AccountProfileConfidentialContentUnavailable):
        content.read_account_profile_confidential_content(user)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]
)
def test_all_roles_create_default_before_insert_and_constraints(role):
    sync_policy()
    user = make_user(f"default-{role}@example.edu", role=role)
    assert asdict(content.read_account_profile_confidential_content(user)) == asdict(
        content.AccountProfileConfidentialContent()
    )
    assert content.encrypted_with_primary_key(getattr(user, content.COLUMN))
    for bad in (None, ""):
        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(**{content.COLUMN: bad})


@pytest.mark.django_db
def test_partial_noop_token_timestamp_audit_and_zero_query_context(django_assert_num_queries):
    sync_policy()
    user = make_user("profile-test@example.edu")
    write(user)
    user.save(update_fields=[content.COLUMN])
    before = raw(User)
    count = AuditEvent.objects.count()
    result = update_my_profile(
        user=user,
        changes={"civil_status": "  PRIVATE-civil 雪  "},
        context=AuditContext(actor=user),
    )
    assert not result.changed and raw(User) == before and AuditEvent.objects.count() == count
    with django_assert_num_queries(0):
        profile = get_person_profile_context(user)
    assert profile.current_address == PAYLOAD["current_address"]
    result = update_my_profile(
        user=user,
        changes={"contact_number": " new phone ", "date_of_birth": None},
        context=AuditContext(actor=user),
    )
    assert result.changed_fields == ("contact_number", "date_of_birth")
    private = content.read_account_profile_confidential_content(result.user)
    assert private.contact_number == "new phone" and private.date_of_birth is None
    assert private.current_address == PAYLOAD["current_address"]
    event = AuditEvent.objects.latest("occurred_at")
    assert event.metadata == {"changed_fields": ["contact_number", "date_of_birth"]}
    safe(event.metadata)


@pytest.mark.django_db
@pytest.mark.parametrize("operation", ["get", "patch"])
def test_corrupt_owner_api_generic500_does_not_overwrite(operation, caplog):
    sync_policy()
    user = make_user("broken-profile@example.edu")
    client, _ = auth_client(user)
    User.objects.filter(pk=user.pk).update(**{content.COLUMN: "PRIVATE-corrupt"})
    before = raw(User)
    events = AuditEvent.objects.count()
    response = (
        client.get("/api/v1/me/profile")
        if operation == "get"
        else patch_profile(client, {"civil_status": "valid"})
    )
    assert (
        response.status_code == 500
        and response.json()["error"]["code"] == "profile_confidential_content_unavailable"
    )
    safe(response.content, "PRIVATE-corrupt")
    safe(caplog.text)
    assert raw(User) == before and AuditEvent.objects.count() == events


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("civil_status", "x\x00y"),
        ("contact_number", "x\ud800y"),
        ("current_address", "x" * 2001),
        ("permanent_address", "x" * 2001),
        ("civil_status", "x" * 81),
        ("contact_number", "x" * 65),
    ],
)
def test_invalid_text_does_not_mutate(field, value):
    sync_policy()
    user = make_user("invalid-profile@example.edu")
    client, _ = auth_client(user)
    before = raw(User)
    assert patch_profile(client, {field: value}).status_code == 422
    assert raw(User) == before


@pytest.mark.django_db
def test_raw_private_sentinels_absent_identity_queryable_and_operations_do_not_decrypt(monkeypatch):
    sync_policy()
    user = make_user("queryable@example.edu")
    write(user)
    user.save(update_fields=[content.COLUMN])
    assert set(PAYLOAD).isdisjoint(columns(User))
    safe(json.dumps(raw(User), default=str))
    assert (
        User.objects.filter(
            email__iexact="QUERYABLE@example.edu", first_name__icontains="Profile"
        ).get()
        == user
    )
    monkeypatch.setattr(content, "read_account_profile_confidential_content", forbid)
    monkeypatch.setattr(content.crypto, "decrypt_bound_json", forbid)
    assert User.objects.get_by_natural_key(user.email) == user
    assert user.check_password("a-test-password")
    assert serialize_account(user)["email"] == user.email
    assert _person(user)["full_name"] == user.get_full_name()
    assert effective_capabilities(user)
    assert create_auth_session(user).session.user_id == user.pk
    client, _ = auth_client(user)
    assert client.delete("/api/v1/me/profile/photo", **csrf_headers(client)).status_code in {
        200,
        503,
    }


@pytest.mark.django_db
def test_rotation_preserves_bytes_timestamp_metadata_idempotence_and_safe_failure(settings):
    sync_policy()
    users = [make_user(f"rotate-{n}@example.edu") for n in range(3)]
    for user in users:
        write(user)
        user.save(update_fields=[content.COLUMN])
    before = raw(User)
    meta = metadata(User, content.COLUMN)
    events = AuditEvent.objects.count()
    settings.ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    out, _ = command("rotate_account_profile_confidential_content", dry_run=True, batch_size=1)
    assert "needing rotation 3" in out and raw(User) == before
    command("rotate_account_profile_confidential_content", batch_size=1)
    for row, old in zip(raw(User), before, strict=True):
        assert Fernet(K2).decrypt(row[content.COLUMN].encode()) == Fernet(K1).decrypt(
            old[content.COLUMN].encode()
        )
        assert Fernet(K2).extract_timestamp(row[content.COLUMN].encode()) == Fernet(
            K1
        ).extract_timestamp(old[content.COLUMN].encode())
    assert metadata(User, content.COLUMN) == meta and AuditEvent.objects.count() == events
    after = raw(User)
    out, _ = command("rotate_account_profile_confidential_content", batch_size=2)
    assert "rotated 0" in out and raw(User) == after
    User.objects.filter(pk=users[0].pk).update(**{content.COLUMN: "PRIVATE-broken"})
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_account_profile_confidential_content", stdout=out, stderr=err)
    safe(out.getvalue() + err.getvalue())
    assert (
        User.objects.get(pk=users[0].pk).profile_confidential_content_ciphertext == "PRIVATE-broken"
    )
    for size in (0, 1001):
        with pytest.raises(CommandError):
            command("rotate_account_profile_confidential_content", batch_size=size)


@pytest.fixture
def legacy(transactional_db):
    initial, registry = setup_legacy("accounts", BEFORE)
    try:
        yield registry
    finally:
        cleanup_legacy("accounts", ("User",), initial)


def old_user(registry, index=0):
    role = registry.get_model("accounts", "Role").objects.create(code=f"TEST-{index}", name="Test")
    return registry.get_model("accounts", "User").objects.create(
        role=role,
        email=f"legacy-{index}@example.edu",
        first_name="Historical",
        last_name="Identity",
        password="!",
        **{**PAYLOAD, "date_of_birth": date(2000, 1, 2)},
    )


def test_migration_backfill_late_insert_stale_and_missing_exact_reverse(legacy):
    first = old_user(legacy)
    stamp = first.updated_at
    migrate(BACKFILLED)
    reg = state(BACKFILLED)
    model = reg.get_model("accounts", "User")
    model.objects.filter(pk=first.pk).update(current_address="PRIVATE-late change")
    second = old_user(reg, 1)
    third = old_user(reg, 2)
    equal = old_user(reg, 3)
    model.objects.filter(pk=equal.pk).update(
        date_of_birth=None,
        civil_status="",
        contact_number="",
        current_address="",
        permanent_address="",
    )
    equal = model.objects.get(pk=equal.pk)
    equal_token = frozen.encrypt((K1,), equal, frozen.plaintext(equal, "User"), "User")
    model.objects.filter(pk=equal.pk).update(**{content.COLUMN: equal_token})
    model.objects.filter(pk=third.pk).update(**{content.COLUMN: ""})
    migrate(AFTER)
    assert "current_address" not in columns(User)
    assert User.objects.get(pk=equal.pk).profile_confidential_content_ciphertext == equal_token
    assert (
        content.read_account_profile_confidential_content(User.objects.get(pk=equal.pk))
        == content.AccountProfileConfidentialContent()
    )
    row = User.objects.get(pk=first.pk)
    assert row.updated_at == stamp
    assert (
        content.read_account_profile_confidential_content(row).current_address
        == "PRIVATE-late change"
    )
    assert (
        content.read_account_profile_confidential_content(
            User.objects.get(pk=second.pk)
        ).contact_number
        == PAYLOAD["contact_number"]
    )
    migrate(BEFORE)
    reg = state(BEFORE)
    row = reg.get_model("accounts", "User").objects.get(pk=first.pk)
    assert row.current_address == "PRIVATE-late change" and row.updated_at == stamp
    restored_empty = reg.get_model("accounts", "User").objects.get(pk=equal.pk)
    assert restored_empty.date_of_birth is None and restored_empty.current_address == ""


@pytest.mark.parametrize("fault", ["tamper", "binding", "schema", "wrong-type"])
def test_present_bad_token_aborts_forward_and_reverse_atomically(legacy, fault):
    first = old_user(legacy)
    migrate(BACKFILLED)
    model = state(BACKFILLED).get_model("accounts", "User")
    item = model.objects.get(pk=first.pk)
    token = getattr(item, content.COLUMN)
    model.objects.filter(pk=item.pk).update(**{content.COLUMN: mutated(token, fault)})
    before = raw(User)
    with pytest.raises(RuntimeError) as caught:
        migrate(AFTER)
    safe(caught.value)
    assert raw(User) == before and "current_address" in columns(User)
    model.objects.filter(pk=item.pk).update(**{content.COLUMN: token})
    migrate(AFTER)
    User.objects.filter(pk=item.pk).update(**{content.COLUMN: mutated(token, fault)})
    before = raw(User)
    with pytest.raises(RuntimeError):
        migrate(BEFORE)
    assert raw(User) == before and "current_address" not in columns(User)


@pytest.mark.parametrize("reverse", [False, True])
def test_writer_fence_precedes_data_and_ddl(legacy, monkeypatch, reverse):
    old_user(legacy)
    migrate(AFTER if reverse else BACKFILLED)
    calls = fence_probe(
        "compass.accounts.migrations.0008_remove_plaintext_confidential_content",
        "accounts",
        ("User",),
        "is_active",
        monkeypatch,
        reverse,
    )
    migrate(BEFORE if reverse else AFTER)
    assert calls


def test_rotation_refuses_transitional_plaintext_and_frozen_is_independent(legacy, monkeypatch):
    old_user(legacy)
    migrate(BACKFILLED)
    for dry in (False, True):
        with pytest.raises(CommandError, match="Legacy"):
            command("rotate_account_profile_confidential_content", dry_run=dry)
    monkeypatch.setattr(content, "read_account_profile_confidential_content", forbid)
    monkeypatch.setattr(content, "write_account_profile_confidential_content", forbid)
    migrate(AFTER)
    migrate(BEFORE)


@pytest.mark.parametrize(
    "target,source",
    [
        (target, source)
        for target in [content.KEYRING_SETTING, "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"]
        for source in [
            "SECRET_KEY",
            "AUTH_TOTP_ENCRYPTION_KEY",
            "WEB_PUSH_STORAGE_KEY",
            "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
            "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
            "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
            "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
            "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
            "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
            "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        ]
        if target != source
    ],
)
@pytest.mark.parametrize("position", [0, 1])
def test_settings_reject_each_existing_current_previous_key_and_new_domain_reuse(
    monkeypatch, target, source, position
):
    import runpy
    from pathlib import Path

    rings = [
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        content.KEYRING_SETTING,
        "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    ]
    values = {name: Fernet.generate_key().decode() for name in rings}
    values.update(
        SECRET_KEY=Fernet.generate_key().decode(),
        AUTH_TOTP_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        WEB_PUSH_STORAGE_KEY=Fernet.generate_key().decode(),
    )
    reused = Fernet.generate_key().decode() if position and source in rings else values[source]
    if source in rings and position:
        values[source] += "," + reused
    fresh = Fernet.generate_key().decode()
    values[target] = fresh + "," + reused if position else reused + "," + fresh
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError) as caught:
        runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))
    assert (
        target in str(caught.value)
        and "reuse" in str(caught.value)
        and reused not in str(caught.value)
    )


@pytest.mark.parametrize(
    "setting", [content.KEYRING_SETTING, "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"]
)
@pytest.mark.parametrize("bad", ["", "not-a-key", " , ", "missing,,entry"])
def test_both_settings_required_no_fallback_or_material_echo(monkeypatch, setting, bad):
    import runpy
    from pathlib import Path

    monkeypatch.setenv(setting, bad)
    with pytest.raises(ValueError) as caught:
        runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))
    assert setting in str(caught.value)
    if bad.strip():
        assert bad not in str(caught.value)


@pytest.mark.django_db(transaction=True)
def test_account_rotation_locks_real_rows_commits_batches_and_resumes(settings, monkeypatch):
    from django.db import OperationalError

    module = importlib.import_module(
        "compass.accounts.management.commands.rotate_account_profile_confidential_content"
    )
    sync_policy()
    for n in range(2):
        make_user(f"resume-{n}@example.edu")
    settings.ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    original = module.reencrypt_account_profile_confidential_content
    seen = []

    def interrupted(user):
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout='100ms'")
                with pytest.raises(OperationalError, match="lock timeout"):
                    cursor.execute(
                        "UPDATE accounts_user SET is_active=is_active WHERE id=%s", [user.pk]
                    )
        finally:
            writer.close()
        seen.append(user.pk)
        if len(seen) == 2:
            raise RuntimeError("Synthetic interruption")
        return original(user)

    monkeypatch.setattr(module, "reencrypt_account_profile_confidential_content", interrupted)
    with pytest.raises(RuntimeError, match="Synthetic interruption"):
        command("rotate_account_profile_confidential_content", batch_size=1)
    assert (
        sum(
            content.encrypted_with_primary_key(getattr(u, content.COLUMN))
            for u in User.objects.all()
        )
        == 1
    )
    monkeypatch.setattr(module, "reencrypt_account_profile_confidential_content", original)
    command("rotate_account_profile_confidential_content", batch_size=1)
    assert all(
        content.encrypted_with_primary_key(getattr(u, content.COLUMN)) for u in User.objects.all()
    )


def test_corrupt_later_user_rolls_back_earlier_stale_rewrite(legacy):
    from uuid import UUID

    first, second = old_user(legacy), old_user(legacy, 1)
    model = legacy.get_model("accounts", "User")
    model.objects.filter(pk=first.pk).update(id=UUID(int=1))
    model.objects.filter(pk=second.pk).update(id=UUID(int=2))
    migrate(BACKFILLED)
    model = state(BACKFILLED).get_model("accounts", "User")
    model.objects.filter(pk=UUID(int=1)).update(current_address="PRIVATE-new plaintext")
    model.objects.filter(pk=UUID(int=2)).update(
        profile_confidential_content_ciphertext="PRIVATE-corrupt"
    )
    before = raw(User)
    with pytest.raises(RuntimeError):
        migrate(AFTER)
    assert raw(User) == before and "current_address" in columns(User)


@pytest.mark.django_db
def test_rotation_caps_failure_contexts_and_never_prints_tokens():
    from compass.accounts.models import Role
    from tests.profile_fixtures import create_initialized_user

    sync_policy()
    role = Role.objects.get(code="STUDENT")
    for n in range(25):
        user = create_initialized_user(
            email=f"fail-{n}@example.edu",
            password="!",
            role=role,
            first_name="Safe",
            last_name="User",
        )
        User.objects.filter(pk=user.pk).update(
            profile_confidential_content_ciphertext="PRIVATE-corrupt"
        )
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_account_profile_confidential_content", stdout=out, stderr=err)
    assert err.getvalue().count("Account profile ") == 20 and "5 more" in err.getvalue()
    safe(out.getvalue() + err.getvalue())
