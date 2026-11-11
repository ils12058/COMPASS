from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Role,
    StudentLifecycleStatus,
    User,
    UserCapabilityOverride,
)
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.models import Campus, College
from compass.student_academics.models import StudentAcademicProfile


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
    institutional_id: str | None = None,
) -> User:
    return User.objects.create_user(
        email=email,
        institutional_id=institutional_id,
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


def make_campus_with_college(
    *,
    campus_code: str = "MAIN",
    college_code: str = "CCMS",
    campus_active: bool = True,
    college_active: bool = True,
) -> tuple[Campus, College]:
    campus = Campus.objects.create(
        code=campus_code,
        name=f"{campus_code} Campus",
        is_active=campus_active,
    )
    college = College.objects.create(
        campus=campus,
        code=college_code,
        name=f"{college_code} College",
        is_active=college_active,
    )
    return campus, college


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
    b"institutional_id,email,first_name,last_name,role,middle_name,suffix\n"
    b"UCN-CSV-101,student.one@example.edu,Student,One,STUDENT,,\n"
    b"EMP-CSV-201,officer.one@example.edu,Officer,One,INSTITUTIONAL_OFFICER,,\n"
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
            b"email,first_name,last_name,role,designation\na@example.edu,A,User,STUDENT,HEAD_GUIDANCE_COUNSELOR\n",
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
        b"institutional_id,email,email,first_name,last_name,role\nUCN-X,a@example.edu,a@example.edu,A,U,STUDENT\n",
        dry_run=True,
    )
    assert duplicate_header.status_code == 422
    assert duplicate_header.json()["error"]["code"] == "csv_import_unsupported_headers"

    bad_utf8 = upload(
        client, b"institutional_id,email,first_name,last_name,role\n\xff", dry_run=True
    )
    assert bad_utf8.status_code == 422
    assert bad_utf8.json()["error"]["code"] == "csv_import_malformed"

    malformed = upload(
        client,
        b"institutional_id,email,first_name,last_name,role\nUCN-X,a@example.edu,A,User\n",
        dry_run=True,
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "csv_import_malformed"


@pytest.mark.django_db
def test_csv_dry_run_reports_invalid_rows_and_commit_rejects_them_without_writes():
    sync_policy()
    client, _admin = admin_client()
    invalid = (
        b"institutional_id,email,first_name,last_name,role\n"
        b"UCN-INV-1,not-an-email,A,User,STUDENT\n"
        b"UCN-INV-2,valid@example.edu,Valid,User,NOT_CANONICAL\n"
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
        b"institutional_id,email,first_name,last_name,role\n"
        b"UCN-DUPEMAIL-1,Duplicate@Example.edu,First,User,STUDENT\n"
        b"UCN-DUPEMAIL-2,duplicate@example.edu,Second,User,STUDENT\n"
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
        b"institutional_id,email,first_name,middle_name,last_name,suffix,role\n"
        b"UCN-EXIST-1,existing@example.edu,Existing,,User,,COUNSELOR\n"
        b"UCN-NEW-1,new@example.edu,New,,User,,STUDENT\n"
    )
    make_user(
        email="existing@example.edu",
        institutional_id="UCN-EXIST-1",
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
            "role": "GUIDANCE_OFFICE_ASSISTANT",
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
    make_user(
        email="conflict@example.edu",
        institutional_id="UCN-CONFLICT-1",
        **existing_kwargs,
    )
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role\n"
        b"UCN-CONFLICT-1,conflict@example.edu,Same,User,COUNSELOR\n"
        b"UCN-WOULD-1,would-create@example.edu,Would,Create,STUDENT\n"
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
        b"institutional_id,email,first_name,last_name,role\n"
        b"UCN-RACY-1,racy@example.edu,Racy,User,COUNSELOR\n"
        b"UCN-OTHER-1,other@example.edu,Other,User,STUDENT\n"
    )
    dry = upload(client, csv_bytes, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is True

    make_user(
        email="racy@example.edu",
        institutional_id="UCN-RACY-1",
        role="GUIDANCE_OFFICE_ASSISTANT",
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
        b"institutional_id,email,first_name,last_name,role\n"
        b"UCN-ROLLBACK-1,one.rollback@example.edu,One,Rollback,STUDENT\n"
        b"UCN-ROLLBACK-2,two.rollback@example.edu,Two,Rollback,COUNSELOR\n"
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
    assert step_up.json()["error"]["code"] == "mfa_setup_required"


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
    rows = ["institutional_id,email,first_name,last_name,role"]
    rows.extend(
        f"UCN-LIMIT-{index},user{index}@example.edu,User,{index},STUDENT" for index in range(1001)
    )
    content = ("\n".join(rows) + "\n").encode()

    response = upload(client, content, dry_run=False)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "csv_import_too_large"
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_csv_accepts_and_previews_optional_student_placement():
    sync_policy()
    client, _admin = admin_client()
    campus, college = make_campus_with_college(campus_code="MAIN", college_code="CCMS")
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-101,preview.placed@example.edu,Preview,Placed,STUDENT,main,ccms\n"
        b"UCN-SAR4-102,preview.unplaced@example.edu,Preview,Unplaced,STUDENT,,\n"
    )

    response = upload(client, csv_bytes, dry_run=True)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["committed"] is False
    assert body["create_count"] == 2
    rows = {row["institutional_id"]: row for row in body["rows"]}
    assert rows["UCN-SAR4-101"]["action"] == "CREATE"
    assert rows["UCN-SAR4-101"]["campus_code"] == "MAIN"
    assert rows["UCN-SAR4-101"]["college_code"] == "CCMS"
    assert rows["UCN-SAR4-102"]["campus_code"] is None
    assert rows["UCN-SAR4-102"]["college_code"] is None
    assert not User.objects.filter(email="preview.placed@example.edu").exists()


@pytest.mark.django_db
def test_csv_commit_creates_student_placement_and_reimport_is_skip():
    sync_policy()
    client, admin = admin_client()
    _campus, college = make_campus_with_college()
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-201,committed.placed@example.edu,Committed,Placed,STUDENT,MAIN,CCMS\n"
    )

    first = upload(client, csv_bytes, dry_run=False)

    assert first.status_code == 200
    body = first.json()
    assert body["committed"] is True
    assert body["create_count"] == 1
    student = User.objects.get(email="committed.placed@example.edu")
    profile = StudentAcademicProfile.objects.get(student=student)
    assert profile.current_college_id == college.pk
    assert profile.updated_by == admin
    placement_event = AuditEvent.objects.get(
        action="student_academics.placement.set", target_id=str(student.pk)
    )
    assert placement_event.metadata == {
        "previous_college_id": None,
        "new_college_id": str(college.pk),
    }

    second = upload(client, csv_bytes, dry_run=False)
    assert second.status_code == 200
    assert second.json()["create_count"] == 0
    assert second.json()["skip_count"] == 1
    assert StudentAcademicProfile.objects.filter(student=student).count() == 1


@pytest.mark.django_db
def test_csv_existing_student_with_different_placement_is_conflict():
    sync_policy()
    client, _admin = admin_client()
    _campus, college = make_campus_with_college(campus_code="MAIN", college_code="CCMS")
    _other_campus, other_college = make_campus_with_college(campus_code="NORTH", college_code="CEA")
    existing = make_user(
        email="placed.existing@example.edu",
        institutional_id="UCN-SAR4-301",
        first_name="Placed",
        last_name="Existing",
    )
    StudentAcademicProfile.objects.create(student=existing, current_college=college)
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-301,placed.existing@example.edu,Placed,Existing,STUDENT,NORTH,CEA\n"
    )

    dry = upload(client, csv_bytes, dry_run=True)

    assert dry.status_code == 200
    assert dry.json()["valid"] is False
    assert dry.json()["conflict_count"] == 1
    row = dry.json()["rows"][0]
    assert row["action"] == "CONFLICT"
    assert row["message"] == "existing account has a different academic placement"

    committed = upload(client, csv_bytes, dry_run=False)
    assert committed.status_code == 409
    assert committed.json()["error"]["code"] == "csv_import_conflict"
    existing.refresh_from_db()
    assert StudentAcademicProfile.objects.get(student=existing).current_college_id == college.pk


@pytest.mark.django_db
def test_csv_existing_student_with_same_placement_is_skip():
    sync_policy()
    client, _admin = admin_client()
    _campus, college = make_campus_with_college()
    existing = make_user(
        email="same.placement@example.edu",
        institutional_id="UCN-SAR4-401",
        first_name="Same",
        last_name="Placement",
    )
    StudentAcademicProfile.objects.create(student=existing, current_college=college)
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-401,same.placement@example.edu,Same,Placement,STUDENT,MAIN,CCMS\n"
    )

    dry = upload(client, csv_bytes, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is True
    assert dry.json()["skip_count"] == 1

    committed = upload(client, csv_bytes, dry_run=False)
    assert committed.status_code == 200
    assert committed.json()["skip_count"] == 1
    assert StudentAcademicProfile.objects.filter(student=existing).count() == 1


@pytest.mark.django_db
def test_csv_rejects_incomplete_unknown_inactive_or_nonstudent_placement():
    sync_policy()
    client, _admin = admin_client()
    _campus, _college = make_campus_with_college(campus_code="MAIN", college_code="CCMS")
    _inactive_campus, inactive_campus_college = make_campus_with_college(
        campus_code="SOUTH", college_code="SBA", campus_active=False
    )
    _active_campus, inactive_college = make_campus_with_college(
        campus_code="EAST", college_code="ENG", college_active=False
    )
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-501,only.campus@example.edu,Only,Campus,STUDENT,MAIN,\n"
        b"UCN-SAR4-502,only.college@example.edu,Only,College,STUDENT,,CCMS\n"
        b"UCN-SAR4-503,unknown.campus@example.edu,Unknown,Campus,STUDENT,NOPE,CCMS\n"
        b"UCN-SAR4-504,unknown.college@example.edu,Unknown,College,STUDENT,MAIN,NOPE\n"
        b"UCN-SAR4-505,nonstudent.placed@example.edu,Nonstudent,Placed,COUNSELOR,MAIN,CCMS\n"
        b"UCN-SAR4-506,inactive.campus@example.edu,Inactive,Campus,STUDENT,SOUTH,SBA\n"
        b"UCN-SAR4-507,inactive.college@example.edu,Inactive,College,STUDENT,EAST,ENG\n"
    )

    dry = upload(client, csv_bytes, dry_run=True)

    assert dry.status_code == 200
    body = dry.json()
    assert body["valid"] is False
    assert body["invalid_count"] == 7
    message_by_id = {
        row["institutional_id"]: row["message"]
        for row in body["rows"]
        if row["action"] == "INVALID"
    }
    assert message_by_id["UCN-SAR4-501"] == "Choose both a Campus and College, or leave both blank."
    assert message_by_id["UCN-SAR4-502"] == "Choose both a Campus and College, or leave both blank."
    assert message_by_id["UCN-SAR4-503"] == "Choose an active Campus."
    assert message_by_id["UCN-SAR4-504"] == "Choose an active College in the selected Campus."
    assert message_by_id["UCN-SAR4-505"] == (
        "Only Student accounts accept an initial academic placement."
    )
    assert message_by_id["UCN-SAR4-506"] == "Choose an active Campus."
    assert message_by_id["UCN-SAR4-507"] == "Choose an active College in the selected Campus."

    committed = upload(client, csv_bytes, dry_run=False)
    assert committed.status_code == 422
    assert committed.json()["error"]["code"] == "csv_import_invalid_rows"
    assert not User.objects.filter(
        email__in=[
            "only.campus@example.edu",
            "only.college@example.edu",
            "unknown.campus@example.edu",
            "unknown.college@example.edu",
            "nonstudent.placed@example.edu",
            "inactive.campus@example.edu",
            "inactive.college@example.edu",
        ]
    ).exists()
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_csv_rejects_program_code_header():
    sync_policy()
    client, _admin = admin_client()
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,program_code\n"
        b"UCN-SAR4-601,program.code@example.edu,Program,Code,STUDENT,BSIS\n"
    )

    response = upload(client, csv_bytes, dry_run=True)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "csv_import_unsupported_headers"
    assert "program_code" in response.json()["error"]["message"]
    assert not User.objects.filter(email="program.code@example.edu").exists()


@pytest.mark.django_db
def test_csv_placement_requires_student_academics_manage_in_dry_run_and_commit():
    sync_policy()
    client, admin = admin_client()
    _campus, _college = make_campus_with_college()
    UserCapabilityOverride.objects.create(
        user=admin,
        capability=Capability.objects.get(code="student_academics.manage"),
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Temporary separation of duties",
        created_by=admin,
    )
    placed_csv = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-701,denied.csv.placed@example.edu,Denied,Placed,STUDENT,MAIN,CCMS\n"
    )
    unplaced_csv = (
        b"institutional_id,email,first_name,last_name,role\n"
        b"UCN-SAR4-702,allowed.csv.unplaced@example.edu,Allowed,Unplaced,STUDENT\n"
    )

    dry = upload(client, placed_csv, dry_run=True)
    assert dry.status_code == 403
    assert dry.json()["error"]["code"] == "academic_placement_permission_denied"

    committed = upload(client, placed_csv, dry_run=False)
    assert committed.status_code == 403
    assert committed.json()["error"]["code"] == "academic_placement_permission_denied"
    assert not User.objects.filter(email="denied.csv.placed@example.edu").exists()

    allowed = upload(client, unplaced_csv, dry_run=True)
    assert allowed.status_code == 200
    assert allowed.json()["valid"] is True


@pytest.mark.django_db
def test_csv_placement_rejects_manager_without_student_academics_manage():
    sync_policy()
    manager = make_user(email="csv-placement-manager@example.edu", role="COUNSELOR")
    for code in ("accounts.manage", "organization.manage"):
        UserCapabilityOverride.objects.create(
            user=manager,
            capability=Capability.objects.get(code=code),
            effect=UserCapabilityOverride.Effect.GRANT,
            reason="Temporary CSV duty",
            created_by=manager,
        )
    now = timezone.now()
    issued = create_auth_session(manager, now=now, mfa_verified_at=now)
    client = Client()
    client.cookies["compass_session"] = issued.token
    make_campus_with_college()
    placed_csv = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-711,denied.csv.manager@example.edu,Denied,Manager,STUDENT,MAIN,CCMS\n"
    )

    dry = upload(client, placed_csv, dry_run=True)
    assert dry.status_code == 403
    assert dry.json()["error"]["code"] == "academic_placement_permission_denied"
    assert dry.json()["error"]["message"] == (
        "You don't have permission to assign a Student's first academic placement."
    )

    committed = upload(client, placed_csv, dry_run=False)
    assert committed.status_code == 403
    assert committed.json()["error"]["code"] == "academic_placement_permission_denied"
    assert not User.objects.filter(email="denied.csv.manager@example.edu").exists()
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_csv_placement_failure_rolls_back_whole_batch(monkeypatch):
    from compass.student_academics.services import StudentAcademicError

    sync_policy()
    client, _admin = admin_client()
    _campus, _college = make_campus_with_college()
    csv_bytes = (
        b"institutional_id,email,first_name,last_name,role,campus_code,college_code\n"
        b"UCN-SAR4-801,fails.placed@example.edu,Fails,Placed,STUDENT,MAIN,CCMS\n"
        b"UCN-SAR4-802,fails.unplaced@example.edu,Fails,Unplaced,STUDENT,,\n"
    )

    def failing_writer(**kwargs):
        raise StudentAcademicError("placement writer unavailable")

    monkeypatch.setattr(
        "compass.account_management.csv_import.set_current_placement", failing_writer
    )

    response = upload(client, csv_bytes, dry_run=False)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "csv_import_conflict"
    assert "placement writer unavailable" in response.json()["error"]["details"][0]["message"]
    assert not User.objects.filter(
        email__in=["fails.placed@example.edu", "fails.unplaced@example.edu"]
    ).exists()
    assert not StudentAcademicProfile.objects.exists()
    assert not AuditEvent.objects.filter(action="account.created").exists()
    assert not AuditEvent.objects.filter(action="account.csv_imported").exists()
