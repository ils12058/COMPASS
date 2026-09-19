from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, StudentLifecycleStatus, User
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    *,
    email: str,
    role: str = "STUDENT",
    active: bool = True,
    first_name: str = "Test",
    middle_name: str = "",
    last_name: str = "User",
    suffix: str = "",
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        suffix=suffix,
        is_active=active,
    )


def admin_client(*, recent_mfa: bool = True) -> tuple[Client, User]:
    admin = make_user(email="csv-admin@example.edu", role="IT_ADMIN")
    now = timezone.now()
    issued = create_auth_session(
        admin,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client, admin


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def upload(
    client: Client,
    content: bytes,
    *,
    dry_run: bool,
    name: str = "accounts.csv",
):
    return client.post(
        f"/api/v1/accounts/imports/csv?dry_run={'true' if dry_run else 'false'}",
        data={"file": SimpleUploadedFile(name, content, content_type="text/csv")},
        **csrf(client),
    )


VALID_CSV = (
    b"email,first_name,last_name,role,middle_name,suffix\n"
    b"student.one@example.edu,Student,One,STUDENT,,\n"
    b"officer.one@example.edu,Officer,One,INSTITUTIONAL_OFFICER,,\n"
)



@pytest.mark.django_db
def test_csv_dry_run_is_bounded_validation_only_and_performs_zero_writes():
    sync_policy()
    client, _admin = admin_client()
    before = User.objects.count()

    response = upload(client, b"\xef\xbb\xbf" + VALID_CSV, dry_run=True)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["committed"] is False
    assert body["total_rows"] == 2
    assert body["create_count"] == 2
    assert body["skip_count"] == 0
    assert {row["action"] for row in body["rows"]} == {"CREATE"}
    assert User.objects.count() == before
    assert not AuditEvent.objects.filter(action="account.csv_imported").exists()



@pytest.mark.django_db
def test_csv_commit_creates_multiple_unverified_unpassworded_accounts_and_student_defaults():
    sync_policy()
    client, admin = admin_client()

    response = upload(client, VALID_CSV, dry_run=False)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["committed"] is True
    assert body["create_count"] == 2

    student = User.objects.get(email="student.one@example.edu")
    officer = User.objects.get(email="officer.one@example.edu")
    assert not student.has_usable_password()
    assert not officer.has_usable_password()
    assert student.email_verified_at is None
    assert officer.email_verified_at is None
    assert student.is_active is True
    assert officer.is_active is True
    assert student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert officer.student_lifecycle_status is None
    assert officer.role.code == "INSTITUTIONAL_OFFICER"

    created_events = AuditEvent.objects.filter(
        action="account.created",
        actor_user=admin,
    )
    assert created_events.count() == 2
    summary = AuditEvent.objects.get(action="account.csv_imported", actor_user=admin)
    assert summary.target_type is None
    assert summary.target_id is None
    assert summary.metadata == {
        "created_count": 2,
        "skipped_count": 0,
        "total_validated_rows": 2,
    }
    serialized_audit = str(list(AuditEvent.objects.values_list("metadata", flat=True)))
    assert "student.one@example.edu" not in serialized_audit
    assert "officer.one@example.edu" not in serialized_audit



@pytest.mark.django_db
@pytest.mark.parametrize(
    ("header", "code"),
    [
        (
            b"email,first_name,last_name,role,password\na@example.edu,A,User,STUDENT,secret\n",
            "csv_import_unsupported_headers",
        ),
        (
            b"email,first_name,last_name,role,designation\na@example.edu,A,User,STUDENT,DPO\n",
            "csv_import_unsupported_headers",
        ),
        (
            b"email,first_name,last_name,role,capability\n"
            b"a@example.edu,A,User,STUDENT,accounts.manage\n",
            "csv_import_unsupported_headers",
        ),
        (
            b"email,first_name,last_name,role,is_active\na@example.edu,A,User,STUDENT,false\n",
            "csv_import_unsupported_headers",
        ),
        (
            b"email,first_name,last_name,role,unexpected\na@example.edu,A,User,STUDENT,x\n",
            "csv_import_unsupported_headers",
        ),
        (
            b"email,first_name,role\na@example.edu,A,STUDENT\n",
            "csv_import_unsupported_headers",
        ),
    ],
)
def test_csv_rejects_password_designation_capability_state_unknown_and_missing_headers(
    header, code
):
    sync_policy()
    client, _admin = admin_client()

    response = upload(client, header, dry_run=True)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert User.objects.filter(email="a@example.edu").count() == 0



@pytest.mark.django_db
def test_csv_rejects_duplicate_headers_bad_utf8_and_malformed_rows():
    sync_policy()
    client, _admin = admin_client()

    duplicate_header = upload(
        client,
        b"email,email,first_name,last_name,role\na@example.edu,a@example.edu,A,U,STUDENT\n",
        dry_run=True,
    )
    assert duplicate_header.status_code == 422
    assert duplicate_header.json()["error"]["code"] == "csv_import_unsupported_headers"

    bad_utf8 = upload(client, b"email,first_name,last_name,role\n\xff", dry_run=True)
    assert bad_utf8.status_code == 422
    assert bad_utf8.json()["error"]["code"] == "csv_import_malformed"

    malformed = upload(
        client,
        b"email,first_name,last_name,role\na@example.edu,A,User\n",
        dry_run=True,
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "csv_import_malformed"



@pytest.mark.django_db
def test_csv_dry_run_reports_invalid_rows_and_commit_rejects_them_without_writes():
    sync_policy()
    client, _admin = admin_client()
    invalid = (
        b"email,first_name,last_name,role\n"
        b"not-an-email,A,User,STUDENT\n"
        b"valid@example.edu,Valid,User,NOT_CANONICAL\n"
    )

    dry = upload(client, invalid, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is False
    assert dry.json()["invalid_count"] == 2
    assert {row["action"] for row in dry.json()["rows"]} == {"INVALID"}

    committed = upload(client, invalid, dry_run=False)
    assert committed.status_code == 422
    assert committed.json()["error"]["code"] == "csv_import_invalid_rows"
    assert not User.objects.filter(email__in=["not-an-email", "valid@example.edu"]).exists()



@pytest.mark.django_db
def test_csv_rejects_case_insensitive_duplicate_email_rows():
    sync_policy()
    client, _admin = admin_client()
    duplicate = (
        b"email,first_name,last_name,role\n"
        b"Duplicate@Example.edu,First,User,STUDENT\n"
        b"duplicate@example.edu,Second,User,STUDENT\n"
    )

    dry = upload(client, duplicate, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is False
    assert dry.json()["invalid_count"] == 1

    committed = upload(client, duplicate, dry_run=False)
    assert committed.status_code == 422
    assert committed.json()["error"]["code"] == "csv_import_duplicate_identity"
    assert not User.objects.filter(email="duplicate@example.edu").exists()



@pytest.mark.django_db
def test_csv_existing_identical_active_account_is_skip_and_reimport_is_idempotent():
    sync_policy()
    client, _admin = admin_client()
    csv_bytes = (
        b"email,first_name,middle_name,last_name,suffix,role\n"
        b"existing@example.edu,Existing,,User,,COUNSELOR\n"
        b"new@example.edu,New,,User,,STUDENT\n"
    )
    make_user(
        email="existing@example.edu",
        role="COUNSELOR",
        first_name="Existing",
        last_name="User",
    )

    first = upload(client, csv_bytes, dry_run=False)
    assert first.status_code == 200
    assert first.json()["create_count"] == 1
    assert first.json()["skip_count"] == 1

    second = upload(client, csv_bytes, dry_run=False)
    assert second.status_code == 200
    assert second.json()["create_count"] == 0
    assert second.json()["skip_count"] == 2
    assert User.objects.filter(email="existing@example.edu").count() == 1
    assert User.objects.filter(email="new@example.edu").count() == 1



@pytest.mark.django_db
@pytest.mark.parametrize(
    "existing_kwargs",
    [
        {"role": "COUNSELOR", "first_name": "Different", "last_name": "User", "active": True},
        {
            "role": "GUIDANCE_SERVICES_STAFF",
            "first_name": "Same",
            "last_name": "User",
            "active": True,
        },
        {"role": "COUNSELOR", "first_name": "Same", "last_name": "User", "active": False},
    ],
)
def test_csv_existing_conflict_blocks_complete_commit(existing_kwargs):
    sync_policy()
    client, _admin = admin_client()
    make_user(email="conflict@example.edu", **existing_kwargs)
    csv_bytes = (
        b"email,first_name,last_name,role\n"
        b"conflict@example.edu,Same,User,COUNSELOR\n"
        b"would-create@example.edu,Would,Create,STUDENT\n"
    )

    dry = upload(client, csv_bytes, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is False
    assert dry.json()["conflict_count"] == 1

    committed = upload(client, csv_bytes, dry_run=False)
    assert committed.status_code == 409
    assert committed.json()["error"]["code"] == "csv_import_conflict"
    assert not User.objects.filter(email="would-create@example.edu").exists()



@pytest.mark.django_db
def test_csv_commit_revalidates_after_dry_run_and_does_not_use_persisted_batch_state():
    sync_policy()
    client, _admin = admin_client()
    csv_bytes = (
        b"email,first_name,last_name,role\n"
        b"racy@example.edu,Racy,User,COUNSELOR\n"
        b"other@example.edu,Other,User,STUDENT\n"
    )
    dry = upload(client, csv_bytes, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is True

    make_user(
        email="racy@example.edu",
        role="GUIDANCE_SERVICES_STAFF",
        first_name="External",
        last_name="Change",
    )
    committed = upload(client, csv_bytes, dry_run=False)

    assert committed.status_code == 409
    assert not User.objects.filter(email="other@example.edu").exists()



@pytest.mark.django_db
def test_csv_audit_failure_rolls_back_whole_batch():
    sync_policy()
    client, _admin = admin_client()
    csv_bytes = (
        b"email,first_name,last_name,role\n"
        b"one.rollback@example.edu,One,Rollback,STUDENT\n"
        b"two.rollback@example.edu,Two,Rollback,COUNSELOR\n"
    )

    with patch(
        "compass.account_management.csv_import.record_event",
        side_effect=IntegrityError("synthetic audit failure"),
    ):
        response = upload(client, csv_bytes, dry_run=False)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "csv_import_conflict"
    assert not User.objects.filter(email__contains=".rollback@example.edu").exists()



@pytest.mark.django_db
def test_csv_requires_accounts_manage_and_recent_mfa():
    sync_policy()
    student = make_user(email="not-manager@example.edu", role="STUDENT")
    student_session = create_auth_session(student)
    student_client = Client()
    student_client.cookies["compass_session"] = student_session.token
    denied = upload(student_client, VALID_CSV, dry_run=True)
    assert denied.status_code == 403

    manager_client, _admin = admin_client(recent_mfa=False)
    step_up = upload(manager_client, VALID_CSV, dry_run=True)
    assert step_up.status_code == 403
    assert step_up.json()["error"]["code"] == "recent_mfa_required"



@pytest.mark.django_db
def test_csv_size_limit_is_enforced_before_any_account_write():
    sync_policy()
    client, _admin = admin_client()
    oversized = b"x" * (1_048_576 + 1)

    response = upload(client, oversized, dry_run=False)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "csv_import_too_large"
    assert User.objects.count() == 1




@pytest.mark.django_db
def test_csv_row_limit_is_enforced_without_persisting_any_rows():
    sync_policy()
    client, _admin = admin_client()
    rows = ["email,first_name,last_name,role"]
    rows.extend(f"user{index}@example.edu,User,{index},STUDENT" for index in range(1001))
    content = ("\n".join(rows) + "\n").encode()

    response = upload(client, content, dry_run=False)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "csv_import_too_large"
    assert User.objects.count() == 1
