from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.policy import (
    CAPABILITY_DEFINITIONS,
    DESIGNATION_CAPABILITY_GRANTS,
    ROLE_CAPABILITY_GRANTS,
    required_capabilities,
    resolve_capability_dependencies,
)
from compass.accounts.services import effective_capabilities
from compass.audit.models import AuditEvent
from compass.authentication.models import TOTPFactor
from compass.authentication.sessions import create_auth_session
from compass.organization.models import Campus, College, Program
from compass.student_academics.models import (
    PlacementVerificationStatus,
    StudentAcademicProfile,
)

BASE = "/api/v1/student-academics"
HEADER = "institutional_id,campus_code,college_code"
IMPORT_PERMISSION_MESSAGE = "The student_academics.import capability is required."


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    institutional_id: str,
    *,
    role: str = "STUDENT",
    active: bool = True,
    first_name: str = "Test",
    last_name: str = "Student",
) -> User:
    return User.objects.create_user(
        email=f"{institutional_id.lower()}@example.edu",
        institutional_id=institutional_id,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=first_name,
        last_name=last_name,
        is_active=active,
    )


def auth_client(user: User, *, recent_mfa: bool = True) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def admin_client(*, recent_mfa: bool = True) -> tuple[Client, User]:
    admin = make_user("UCN-ADMIN", role="IT_ADMIN")
    return auth_client(admin, recent_mfa=recent_mfa), admin


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def upload(
    client: Client,
    content: bytes,
    *,
    dry_run: bool,
    name: str = "roster.csv",
):
    return client.post(
        f"{BASE}/imports/csv?dry_run={'true' if dry_run else 'false'}",
        data={"file": SimpleUploadedFile(name, content, content_type="text/csv")},
        **csrf(client),
    )


def roster_csv(*rows: str) -> bytes:
    return ("\n".join([HEADER, *rows]) + "\n").encode()


def make_campus_with_college(
    campus_code: str = "MAIN",
    college_code: str = "CCMS",
    *,
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


def academic_audits():
    return AuditEvent.objects.filter(action__startswith="student_academics.")


def place(
    student: User,
    college: College,
    *,
    verification: str = PlacementVerificationStatus.UNVERIFIED,
    program: Program | None = None,
    effective_at=None,
) -> StudentAcademicProfile:
    return StudentAcademicProfile.objects.create(
        student=student,
        current_college=college,
        current_program=program,
        placement_verification_status=verification,
        placement_effective_at=effective_at,
    )


def test_import_capability_policy_definition_grants_and_dependencies():
    definitions = {item.code: item for item in CAPABILITY_DEFINITIONS}
    definition = definitions["student_academics.import"]
    assert definition.name == "Import Student academic roster"
    assert definition.description == (
        "Validate and apply approved CSV College placements for existing Student accounts."
    )
    assert len(CAPABILITY_DEFINITIONS) == 104
    assert sum(len(grants) for grants in ROLE_CAPABILITY_GRANTS.values()) == 124
    assert sum(len(grants) for grants in DESIGNATION_CAPABILITY_GRANTS.values()) == 24

    assert "student_academics.import" in ROLE_CAPABILITY_GRANTS["IT_ADMIN"]
    for role_code, grants in ROLE_CAPABILITY_GRANTS.items():
        if role_code != "IT_ADMIN":
            assert "student_academics.import" not in grants
    assert "student_academics.import" in DESIGNATION_CAPABILITY_GRANTS["HEAD_GUIDANCE_COUNSELOR"]
    for designation_code, grants in DESIGNATION_CAPABILITY_GRANTS.items():
        if designation_code != "HEAD_GUIDANCE_COUNSELOR":
            assert "student_academics.import" not in grants

    assert required_capabilities("student_academics.import") == frozenset(
        {"student_academics.view"}
    )
    assert resolve_capability_dependencies({"student_academics.import"}) == frozenset()
    assert resolve_capability_dependencies(
        {"student_academics.import", "student_academics.view"}
    ) == frozenset({"student_academics.import", "student_academics.view"})
    assert required_capabilities("student_academics.manage") == frozenset(
        {"student_academics.view"}
    )


@pytest.mark.django_db
def test_import_effective_grants_are_limited_to_admin_and_head_with_view():
    sync_policy()
    assert RoleCapability.objects.count() == 124
    assert DesignationCapability.objects.count() == 24

    admin = make_user("UCN-POLICY-ADMIN", role="IT_ADMIN")
    assert "student_academics.import" in effective_capabilities(admin)

    head = make_user("UCN-POLICY-HEAD", role="COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    assert "student_academics.import" in effective_capabilities(head)

    for role_code in (
        "STUDENT",
        "COUNSELOR",
        "GUIDANCE_OFFICE_ASSISTANT",
        "INSTITUTIONAL_OFFICER",
    ):
        user = make_user(f"UCN-POLICY-{role_code}", role=role_code)
        assert "student_academics.import" not in effective_capabilities(user)

    delegated = make_user("UCN-POLICY-DELEGATED", role="INSTITUTIONAL_OFFICER")
    UserCapabilityOverride.objects.create(
        user=delegated,
        capability=Capability.objects.get(code="student_academics.import"),
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Synthetic import-only grant",
        created_by=delegated,
    )
    assert "student_academics.import" not in effective_capabilities(delegated)
    assert "student_academics.view" not in effective_capabilities(delegated)


@pytest.mark.django_db
def test_import_requires_authentication_and_the_import_capability():
    sync_policy()
    _campus, _college = make_campus_with_college()
    content = roster_csv("UCN-STUDENT-1,MAIN,CCMS")

    assert upload(Client(), content, dry_run=True).status_code == 401

    student = make_user("UCN-STUDENT-1")
    denied = upload(auth_client(student), content, dry_run=True)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"
    assert denied.json()["error"]["message"] == IMPORT_PERMISSION_MESSAGE

    delegated = make_user("UCN-IMPORT-ONLY", role="INSTITUTIONAL_OFFICER")
    UserCapabilityOverride.objects.create(
        user=delegated,
        capability=Capability.objects.get(code="student_academics.import"),
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Synthetic import-only grant",
        created_by=delegated,
    )
    delegated_client = auth_client(delegated)
    for dry_run in (True, False):
        response = upload(delegated_client, content, dry_run=dry_run)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_import_requires_recent_mfa_for_dry_run_and_commit():
    sync_policy()
    _campus, _college = make_campus_with_college()
    admin, admin_user = admin_client(recent_mfa=False)
    TOTPFactor.objects.create(
        user=admin_user,
        encrypted_secret="synthetic-secret",
        confirmed_at=timezone.now(),
    )
    content = roster_csv("UCN-MFA-1,MAIN,CCMS")
    make_user("UCN-MFA-1")

    for dry_run in (True, False):
        response = upload(admin, content, dry_run=dry_run)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "recent_mfa_required"
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_admin_and_head_can_dry_run_and_commit():
    sync_policy()
    _campus, _college = make_campus_with_college()
    make_user("UCN-AUTH-ADMIN-STUDENT")
    make_user("UCN-AUTH-HEAD-STUDENT")

    admin, _admin_user = admin_client()
    admin_content = roster_csv("UCN-AUTH-ADMIN-STUDENT,MAIN,CCMS")
    assert upload(admin, admin_content, dry_run=True).status_code == 200
    committed = upload(admin, admin_content, dry_run=False)
    assert committed.status_code == 200
    assert committed.json()["committed"] is True
    assert committed.json()["set_count"] == 1

    head = make_user("UCN-AUTH-HEAD", role="COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    head_client = auth_client(head)
    head_content = roster_csv("UCN-AUTH-HEAD-STUDENT,MAIN,CCMS")
    assert upload(head_client, head_content, dry_run=True).status_code == 200
    head_committed = upload(head_client, head_content, dry_run=False)
    assert head_committed.status_code == 200
    assert head_committed.json()["committed"] is True
    assert head_committed.json()["set_count"] == 1

    assert (
        StudentAcademicProfile.objects.filter(
            student__institutional_id__in=["UCN-AUTH-ADMIN-STUDENT", "UCN-AUTH-HEAD-STUDENT"]
        ).count()
        == 2
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("content", "code", "fragment"),
    [
        (b"", "csv_import_malformed", "empty"),
        (HEADER.encode() + b"\n", "csv_import_malformed", "at least one roster row"),
        (
            b"institutional_id,campus_code\nUCN-H1,MAIN\n",
            "csv_import_unsupported_headers",
            "missing required headers: college_code",
        ),
        (
            b"institutional_id,campus_code,college_code,college_code\nUCN-H2,MAIN,CCMS,CCMS\n",
            "csv_import_unsupported_headers",
            "duplicate headers",
        ),
        (
            b"institutional_id,campus_code,college_code,program_code\nUCN-H3,MAIN,CCMS,BSIS\n",
            "csv_import_unsupported_headers",
            "unsupported headers: program_code",
        ),
        (
            b"institutional_id,campus_code,college_code,email\nUCN-H4,MAIN,CCMS,a@example.edu\n",
            "csv_import_unsupported_headers",
            "unsupported headers: email",
        ),
        (
            HEADER.encode() + b"\nUCN-H5,MAIN,CCMS\n\xff",
            "csv_import_malformed",
            "UTF-8",
        ),
        (
            HEADER.encode() + b"\nUCN-H6,MAIN,CCMS\x00\n",
            "csv_import_malformed",
            "NUL",
        ),
        (
            HEADER.encode() + b"\nUCN-H7,MAIN\n",
            "csv_import_malformed",
            "does not match the header column count",
        ),
        (
            HEADER.encode() + b'\nUCN-H8,"MAIN,CCMS\n',
            "csv_import_malformed",
            "could not be parsed",
        ),
    ],
)
def test_roster_csv_structure_errors(content, code, fragment):
    sync_policy()
    client, _admin = admin_client()

    response = upload(client, content, dry_run=True)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert fragment in response.json()["error"]["message"]
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_roster_csv_row_limit_accepts_1000_and_rejects_1001_rows():
    sync_policy()
    client, _admin = admin_client()
    rows = [f"UCN-LIMIT-{index},MAIN,CCMS" for index in range(1_000)]

    accepted = upload(client, roster_csv(*rows), dry_run=True)
    assert accepted.status_code == 200
    assert accepted.json()["total_rows"] == 1_000
    assert accepted.json()["conflict_count"] == 1_000

    too_many = upload(client, roster_csv(*rows, "UCN-LIMIT-OVER,MAIN,CCMS"), dry_run=False)
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "csv_import_too_large"
    assert "more than 1000 rows" in too_many.json()["error"]["message"]


@pytest.mark.django_db
def test_roster_csv_byte_limit_accepts_exactly_one_mib_and_rejects_one_byte_over():
    sync_policy()
    _campus, _college = make_campus_with_college()
    make_user("UCN-BYTE-1")
    client, _admin = admin_client()
    base = roster_csv("UCN-BYTE-1,MAIN,CCMS")
    exact = base + b"\n" * (1_048_576 - len(base))
    assert len(exact) == 1_048_576

    accepted = upload(client, exact, dry_run=True)
    assert accepted.status_code == 200
    assert accepted.json()["valid"] is True
    assert accepted.json()["set_count"] == 1

    rejected = upload(client, exact + b"\n", dry_run=False)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "csv_import_too_large"
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_blank_lines_are_skipped_and_physical_row_numbers_are_reported():
    sync_policy()
    _campus, _college = make_campus_with_college()
    make_user("UCN-ROWS-1")
    client, _admin = admin_client()
    content = HEADER.encode() + b"\n\nUCN-ROWS-1,MAIN,CCMS\n\n\n ,MAIN,CCMS\n"

    response = upload(client, content, dry_run=True)

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 2
    rows = {row["row_number"]: row for row in body["rows"]}
    assert sorted(rows) == [3, 6]
    assert rows[3]["institutional_id"] == "UCN-ROWS-1"
    assert rows[3]["action"] == "SET"
    assert rows[6]["action"] == "INVALID"
    assert rows[6]["message"] == "institutional_id is required"


@pytest.mark.django_db
def test_duplicate_normalized_institutional_id_is_invalid_and_rejected_on_commit():
    sync_policy()
    _campus, _college = make_campus_with_college()
    make_user("UCN-DUPLICATE-1")
    client, _admin = admin_client()
    content = roster_csv(
        "UCN-DUPLICATE-1,MAIN,CCMS",
        "ucn-duplicate-1,MAIN,CCMS",
    )

    dry = upload(client, content, dry_run=True)
    assert dry.status_code == 200
    body = dry.json()
    assert body["valid"] is False
    assert body["invalid_count"] == 1
    assert body["set_count"] == 1
    assert [row["action"] for row in body["rows"]] == ["SET", "INVALID"]
    assert body["rows"][1]["row_number"] == 3
    assert body["rows"][1]["message"] == (
        "duplicate institutional_id in CSV; first occurrence is row 2"
    )

    committed = upload(client, content, dry_run=False)
    assert committed.status_code == 422
    assert committed.json()["error"]["code"] == "csv_import_duplicate_identity"
    assert committed.json()["error"]["details"] == [
        {
            "row_number": 3,
            "institutional_id": "UCN-DUPLICATE-1",
            "message": "duplicate institutional_id in CSV; first occurrence is row 2",
        }
    ]
    assert not StudentAcademicProfile.objects.exists()


@pytest.mark.django_db
def test_dry_run_classifies_every_row_and_writes_nothing():
    sync_policy()
    _main_campus, ccms = make_campus_with_college("MAIN", "CCMS")
    _north_campus, cea = make_campus_with_college("NORTH", "CEA")
    make_campus_with_college("SOUTH", "SBA", campus_active=False)
    make_campus_with_college("EAST", "ENG", college_active=False)

    make_user("UCN-CLASS-NEW", first_name="New", last_name="Student")
    same = make_user("UCN-CLASS-SAME", first_name="Same", last_name="Student")
    different = make_user("UCN-CLASS-DIFF", first_name="Different", last_name="Student")
    verified_same = make_user("UCN-CLASS-VSAME", first_name="Verified", last_name="Same")
    verified_different = make_user("UCN-CLASS-VDIFF", first_name="Verified", last_name="Different")
    program_student = make_user("UCN-CLASS-PROG", first_name="Program", last_name="Student")
    effective_student = make_user("UCN-CLASS-EFF", first_name="Effective", last_name="Student")
    make_user("UCN-CLASS-NONSTUDENT", role="COUNSELOR")
    make_user("UCN-CLASS-INACTIVE", active=False)
    for institutional_id in (
        "UCN-CLASS-INACTIVE-CAMPUS",
        "UCN-CLASS-INACTIVE-COLLEGE",
        "UCN-CLASS-UNKNOWN-CAMPUS",
        "UCN-CLASS-PAIR",
        "UCN-CLASS-BLANK-CAMPUS",
        "UCN-CLASS-BLANK-COLLEGE",
    ):
        make_user(institutional_id)
    unrelated = make_user("UCN-CLASS-UNRELATED")
    place(same, ccms)
    place(different, ccms)
    place(verified_same, cea, verification=PlacementVerificationStatus.VERIFIED)
    place(verified_different, ccms, verification=PlacementVerificationStatus.VERIFIED)
    program = Program.objects.create(college=ccms, code="BSIS", name="BS IS")
    place(program_student, ccms, program=program)
    place(effective_student, ccms, effective_at=timezone.now() - timedelta(days=3))
    place(unrelated, ccms)

    content = roster_csv(
        "UCN-CLASS-NEW,MAIN,CCMS",
        "UCN-CLASS-SAME,MAIN,CCMS",
        "UCN-CLASS-DIFF,NORTH,CEA",
        "UCN-CLASS-VSAME,NORTH,CEA",
        "UCN-CLASS-VDIFF,NORTH,CEA",
        "UCN-CLASS-PROG,NORTH,CEA",
        "UCN-CLASS-EFF,NORTH,CEA",
        "UCN-CLASS-MISSING,MAIN,CCMS",
        "UCN-CLASS-NONSTUDENT,MAIN,CCMS",
        "UCN-CLASS-INACTIVE,MAIN,CCMS",
        "UCN-CLASS-INACTIVE-CAMPUS,SOUTH,SBA",
        "UCN-CLASS-INACTIVE-COLLEGE,EAST,ENG",
        "UCN-CLASS-UNKNOWN-CAMPUS,NOWHERE,CCMS",
        "UCN-CLASS-PAIR,NORTH,CCMS",
        "UCN-CLASS-BLANK-CAMPUS,,CCMS",
        "UCN-CLASS-BLANK-COLLEGE,MAIN,",
    )
    before_profiles = {
        profile.student.institutional_id: (
            profile.current_college_id,
            profile.current_program_id,
            profile.placement_verification_status,
            profile.placement_effective_at,
            profile.updated_at,
        )
        for profile in StudentAcademicProfile.objects.select_related("student", "current_college")
    }
    before_audits = AuditEvent.objects.count()
    client, _admin = admin_client()

    response = upload(client, content, dry_run=True)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["committed"] is False
    assert body["total_rows"] == 16
    assert body["set_count"] == 2
    assert body["noop_count"] == 2
    assert body["conflict_count"] == 10
    assert body["invalid_count"] == 2
    rows = {row["institutional_id"]: row for row in body["rows"]}
    assert rows["UCN-CLASS-NEW"]["action"] == "SET"
    assert rows["UCN-CLASS-NEW"]["message"] == "the placement will be assigned"
    assert rows["UCN-CLASS-NEW"]["current_college_code"] is None
    assert rows["UCN-CLASS-NEW"]["student_name"] == "New Student"
    assert rows["UCN-CLASS-SAME"]["action"] == "NOOP"
    assert rows["UCN-CLASS-SAME"]["message"] == "the placement already matches"
    assert rows["UCN-CLASS-SAME"]["current_college_code"] == "CCMS"
    assert rows["UCN-CLASS-DIFF"]["action"] == "SET"
    assert rows["UCN-CLASS-DIFF"]["message"] == "the placement will be updated"
    assert rows["UCN-CLASS-DIFF"]["current_college_code"] == "CCMS"
    assert rows["UCN-CLASS-VSAME"]["action"] == "NOOP"
    assert rows["UCN-CLASS-VSAME"]["message"] == (
        "the placement already matches; verified placement unchanged"
    )
    assert rows["UCN-CLASS-VSAME"]["current_college_code"] == "CEA"
    assert rows["UCN-CLASS-VDIFF"]["action"] == "CONFLICT"
    assert rows["UCN-CLASS-VDIFF"]["message"] == (
        "the current placement is verified and cannot be overwritten by roster import"
    )
    for institutional_id in ("UCN-CLASS-PROG", "UCN-CLASS-EFF"):
        assert rows[institutional_id]["action"] == "CONFLICT"
        assert rows[institutional_id]["message"] == (
            "the current placement contains facts this import cannot safely replace"
        )
        assert rows[institutional_id]["current_college_code"] == "CCMS"
    assert rows["UCN-CLASS-MISSING"]["action"] == "CONFLICT"
    assert rows["UCN-CLASS-MISSING"]["message"] == (
        "institutional_id does not resolve to an existing account"
    )
    assert rows["UCN-CLASS-MISSING"]["student_id"] is None
    assert rows["UCN-CLASS-MISSING"]["student_name"] == ""
    assert rows["UCN-CLASS-NONSTUDENT"]["action"] == "CONFLICT"
    assert rows["UCN-CLASS-NONSTUDENT"]["message"] == ("the account does not have the STUDENT role")
    assert rows["UCN-CLASS-INACTIVE"]["action"] == "CONFLICT"
    assert rows["UCN-CLASS-INACTIVE"]["message"] == "the Student account is inactive"
    for institutional_id in (
        "UCN-CLASS-INACTIVE-CAMPUS",
        "UCN-CLASS-UNKNOWN-CAMPUS",
    ):
        assert rows[institutional_id]["action"] == "CONFLICT"
        assert rows[institutional_id]["message"] == (
            "campus_code does not resolve to an active Campus"
        )
    for institutional_id in ("UCN-CLASS-INACTIVE-COLLEGE", "UCN-CLASS-PAIR"):
        assert rows[institutional_id]["action"] == "CONFLICT"
        assert rows[institutional_id]["message"] == (
            "college_code does not resolve to an active College beneath that Campus"
        )
    assert rows["UCN-CLASS-BLANK-CAMPUS"]["action"] == "INVALID"
    assert rows["UCN-CLASS-BLANK-CAMPUS"]["message"] == "campus_code is required"
    assert rows["UCN-CLASS-BLANK-COLLEGE"]["action"] == "INVALID"
    assert rows["UCN-CLASS-BLANK-COLLEGE"]["message"] == "college_code is required"
    assert body["rows"] == sorted(body["rows"], key=lambda row: row["row_number"])

    after_profiles = {
        profile.student.institutional_id: (
            profile.current_college_id,
            profile.current_program_id,
            profile.placement_verification_status,
            profile.placement_effective_at,
            profile.updated_at,
        )
        for profile in StudentAcademicProfile.objects.select_related("student", "current_college")
    }
    assert after_profiles == before_profiles
    assert AuditEvent.objects.count() == before_audits
    assert StudentAcademicProfile.objects.get(student=unrelated).current_college_id == ccms.pk


@pytest.mark.django_db
def test_blank_codes_are_invalid_rows_and_never_clear_placements():
    sync_policy()
    _campus, college = make_campus_with_college()
    blank_campus = make_user("UCN-BLANK-1")
    blank_college = make_user("UCN-BLANK-2")
    place(blank_campus, college)
    place(blank_college, college)
    client, _admin = admin_client()
    content = roster_csv("UCN-BLANK-1,,CCMS", "UCN-BLANK-2,MAIN,")

    dry = upload(client, content, dry_run=True)
    assert dry.status_code == 200
    body = dry.json()
    assert body["valid"] is False
    assert body["invalid_count"] == 2
    assert {row["action"] for row in body["rows"]} == {"INVALID"}
    assert {row["message"] for row in body["rows"]} == {
        "campus_code is required",
        "college_code is required",
    }

    committed = upload(client, content, dry_run=False)
    assert committed.status_code == 422
    assert committed.json()["error"]["code"] == "csv_import_invalid_rows"
    assert [set(detail) for detail in committed.json()["error"]["details"]] == [
        {"row_number", "institutional_id", "message"}
    ] * 2
    for student in (blank_campus, blank_college):
        assert StudentAcademicProfile.objects.get(student=student).current_college_id == college.pk
    assert not AuditEvent.objects.filter(action="student_academics.placement.set").exists()


@pytest.mark.django_db
def test_commit_sets_placement_audits_each_set_row_and_one_summary():
    sync_policy()
    _campus, ccms = make_campus_with_college("MAIN", "CCMS")
    _other_campus, cea = make_campus_with_college("NORTH", "CEA")
    new = make_user("UCN-COMMIT-NEW", first_name="New", last_name="Placed")
    moving = make_user("UCN-COMMIT-MOVE", first_name="Moving", last_name="Student")
    same = make_user("UCN-COMMIT-SAME")
    unrelated = make_user("UCN-COMMIT-UNRELATED")
    place(moving, ccms)
    place(same, ccms)
    place(unrelated, ccms)
    client, admin = admin_client()
    content = roster_csv(
        "UCN-COMMIT-NEW,MAIN,CCMS",
        "UCN-COMMIT-MOVE,NORTH,CEA",
        "UCN-COMMIT-SAME,MAIN,CCMS",
    )

    response = upload(client, content, dry_run=False)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["committed"] is True
    assert body["total_rows"] == 3
    assert body["set_count"] == 2
    assert body["noop_count"] == 1
    assert body["conflict_count"] == 0
    assert body["invalid_count"] == 0
    assert [row["action"] for row in body["rows"]] == ["SET", "SET", "NOOP"]

    created = StudentAcademicProfile.objects.get(student=new)
    assert created.current_college_id == ccms.pk
    assert created.current_program_id is None
    assert created.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert created.placement_effective_at is None
    assert created.updated_by == admin
    moved = StudentAcademicProfile.objects.get(student=moving)
    assert moved.current_college_id == cea.pk
    assert moved.current_program_id is None
    assert moved.placement_verification_status == PlacementVerificationStatus.UNVERIFIED
    assert moved.placement_effective_at is None
    assert moved.updated_by == admin
    assert StudentAcademicProfile.objects.get(student=same).current_college_id == ccms.pk
    assert StudentAcademicProfile.objects.get(student=unrelated).current_college_id == ccms.pk

    placement_events = AuditEvent.objects.filter(action="student_academics.placement.set").order_by(
        "target_id"
    )
    assert placement_events.count() == 2
    events_by_student = {event.target_id: event for event in placement_events}
    assert events_by_student[str(new.pk)].metadata == {
        "previous_college_id": None,
        "new_college_id": str(ccms.pk),
    }
    assert events_by_student[str(moving.pk)].metadata == {
        "previous_college_id": str(ccms.pk),
        "new_college_id": str(cea.pk),
    }
    summary = AuditEvent.objects.get(action="student_academics.roster.imported")
    assert summary.target_type is None
    assert summary.target_id is None
    assert summary.metadata == {
        "total_rows": 3,
        "set_count": 2,
        "noop_count": 1,
    }
    serialized = str(
        list(
            AuditEvent.objects.filter(action="student_academics.roster.imported").values_list(
                "metadata", flat=True
            )
        )
    )
    for sensitive in (
        "UCN-COMMIT",
        "@example.edu",
        "Placed",
        "MAIN",
        "CCMS",
        "CEA",
    ):
        assert sensitive not in serialized


@pytest.mark.django_db
def test_reimport_of_same_file_is_all_noop_without_new_audit_events():
    sync_policy()
    _campus, college = make_campus_with_college()
    student = make_user("UCN-REIMPORT-1")
    client, _admin = admin_client()
    content = roster_csv("UCN-REIMPORT-1,MAIN,CCMS")

    first = upload(client, content, dry_run=False)
    assert first.status_code == 200
    assert first.json()["set_count"] == 1
    assert StudentAcademicProfile.objects.get(student=student).current_college_id == college.pk
    placement_count = AuditEvent.objects.filter(action="student_academics.placement.set").count()
    summary_count = AuditEvent.objects.filter(action="student_academics.roster.imported").count()

    second = upload(client, content, dry_run=False)

    assert second.status_code == 200
    body = second.json()
    assert body["committed"] is True
    assert body["set_count"] == 0
    assert body["noop_count"] == 1
    assert [row["action"] for row in body["rows"]] == ["NOOP"]
    assert (
        AuditEvent.objects.filter(action="student_academics.placement.set").count()
        == placement_count
    )
    assert (
        AuditEvent.objects.filter(action="student_academics.roster.imported").count()
        == summary_count
    )


@pytest.mark.django_db
def test_all_noop_commit_is_committed_without_a_summary_event():
    sync_policy()
    _campus, college = make_campus_with_college()
    student = make_user("UCN-ALL-NOOP")
    place(student, college)
    client, _admin = admin_client()

    response = upload(client, roster_csv("UCN-ALL-NOOP,MAIN,CCMS"), dry_run=False)

    assert response.status_code == 200
    body = response.json()
    assert body["committed"] is True
    assert body["set_count"] == 0
    assert body["noop_count"] == 1
    assert body["valid"] is True
    assert not academic_audits().exists()


@pytest.mark.django_db
def test_commit_conflict_rolls_back_every_row_and_reports_minimal_details():
    sync_policy()
    _campus, ccms = make_campus_with_college("MAIN", "CCMS")
    _other_campus, cea = make_campus_with_college("NORTH", "CEA")
    would_set = make_user("UCN-ROLLBACK-SET")
    verified = make_user("UCN-ROLLBACK-VERIFIED")
    place(verified, ccms, verification=PlacementVerificationStatus.VERIFIED)
    client, _admin = admin_client()
    content = roster_csv(
        "UCN-ROLLBACK-SET,MAIN,CCMS",
        "UCN-ROLLBACK-VERIFIED,NORTH,CEA",
    )

    response = upload(client, content, dry_run=False)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "csv_import_conflict"
    assert error["details"] == [
        {
            "row_number": 3,
            "institutional_id": "UCN-ROLLBACK-VERIFIED",
            "message": (
                "the current placement is verified and cannot be overwritten by roster import"
            ),
        }
    ]
    assert set(error["details"][0]) == {"row_number", "institutional_id", "message"}
    assert "UCN-ROLLBACK-SET" not in str(error["details"])
    assert not StudentAcademicProfile.objects.filter(student=would_set).exists()
    unchanged = StudentAcademicProfile.objects.get(student=verified)
    assert unchanged.current_college_id == ccms.pk
    assert unchanged.placement_verification_status == PlacementVerificationStatus.VERIFIED
    assert not academic_audits().exists()


@pytest.mark.django_db
def test_commit_reclassifies_when_a_college_becomes_inactive_after_dry_run():
    sync_policy()
    _campus, college = make_campus_with_college()
    student = make_user("UCN-RECLASSIFY-1")
    client, _admin = admin_client()
    content = roster_csv("UCN-RECLASSIFY-1,MAIN,CCMS")

    dry = upload(client, content, dry_run=True)
    assert dry.status_code == 200
    assert dry.json()["valid"] is True

    college.is_active = False
    college.save(update_fields=["is_active", "updated_at"])

    committed = upload(client, content, dry_run=False)

    assert committed.status_code == 409
    assert committed.json()["error"]["code"] == "csv_import_conflict"
    assert committed.json()["error"]["details"][0]["row_number"] == 2
    assert not StudentAcademicProfile.objects.filter(student=student).exists()
    assert not academic_audits().exists()


@pytest.mark.django_db
def test_commit_audit_failure_rolls_back_the_entire_import():
    sync_policy()
    _campus, _college = make_campus_with_college()
    make_user("UCN-AUDIT-ROLLBACK")
    client, _admin = admin_client()

    with patch(
        "compass.student_academics.roster_import.record_event",
        side_effect=IntegrityError("synthetic summary audit failure"),
    ):
        response = upload(client, roster_csv("UCN-AUDIT-ROLLBACK,MAIN,CCMS"), dry_run=False)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "csv_import_conflict"
    assert response.json()["error"]["details"] == [
        {
            "row_number": 0,
            "institutional_id": "",
            "message": ("student academic state changed while the roster import was committing"),
        }
    ]
    assert not StudentAcademicProfile.objects.exists()
    assert not academic_audits().exists()


@pytest.mark.django_db
def test_commit_never_creates_accounts_or_clears_missing_rows():
    sync_policy()
    _campus, ccms = make_campus_with_college("MAIN", "CCMS")
    _other_campus, cea = make_campus_with_college("NORTH", "CEA")
    listed = make_user("UCN-MISSING-LISTED")
    unlisted = make_user("UCN-MISSING-UNLISTED")
    place(unlisted, cea)
    client, _admin = admin_client()
    before_users = User.objects.count()

    response = upload(client, roster_csv("UCN-MISSING-LISTED,MAIN,CCMS"), dry_run=False)

    assert response.status_code == 200
    assert response.json()["set_count"] == 1
    assert User.objects.count() == before_users
    assert not User.objects.filter(institutional_id="UCN-NOT-IN-CSV").exists()
    assert StudentAcademicProfile.objects.get(student=listed).current_college_id == ccms.pk
    assert StudentAcademicProfile.objects.get(student=unlisted).current_college_id == cea.pk
