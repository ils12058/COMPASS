"""Batch term-record and graduation imports: preview, fingerprinted all-or-nothing apply, audit."""

from __future__ import annotations

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from compass.accounts.models import Designation, StudentLifecycleStatus, UserDesignation
from compass.audit.models import AuditEvent
from compass.organization.models import AcademicYear
from compass.student_academics.models import (
    StudentAcademicPeriodRecord,
    StudentAcademicProfile,
    StudentGraduationRecord,
)
from tests.test_student_academic_roster_import import (
    BASE,
    admin_client,
    auth_client,
    csrf,
    make_campus_with_college,
    make_user,
    place,
    sync_policy,
)

PERIOD_HEADER = "institutional_id,campus_code,college_code,year_level,enrollment_status"
GRADUATION_HEADER = "institutional_id,campus_code,college_code,graduation_date"
SOURCE = "Registrar's list of graduates, 2nd Semester 2025-2026"


def csv_bytes(header: str, *rows: str) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode()


def post_periods(
    client: Client,
    content: bytes,
    *,
    year: AcademicYear,
    term="FIRST_SEMESTER",
    dry_run=True,
    fingerprint=None,
):
    data = {
        "file": SimpleUploadedFile("terms.csv", content, content_type="text/csv"),
        "academic_year_id": str(year.pk),
        "term": term,
    }
    if fingerprint is not None:
        data["preview_fingerprint"] = fingerprint
    return client.post(
        f"{BASE}/imports/periods/csv?dry_run={'true' if dry_run else 'false'}",
        data=data,
        **csrf(client),
    )


def post_graduations(
    client: Client, content: bytes, *, source=SOURCE, dry_run=True, fingerprint=None, confirmed=None
):
    data = {
        "file": SimpleUploadedFile("graduates.csv", content, content_type="text/csv"),
        "verification_source": source,
    }
    if fingerprint is not None:
        data["preview_fingerprint"] = fingerprint
    if confirmed is not None:
        data["confirmed_count"] = str(confirmed)
    return client.post(
        f"{BASE}/imports/graduations/csv?dry_run={'true' if dry_run else 'false'}",
        data=data,
        **csrf(client),
    )


def actions(payload) -> dict[str, str]:
    return {row["institutional_id"]: row["action"] for row in payload["rows"]}


@pytest.fixture
def world(db):
    sync_policy()
    _main, ccms = make_campus_with_college("MAIN", "CCMS")
    _north, cea = make_campus_with_college("NORTH", "CEA")
    make_campus_with_college("EAST", "ENG", college_active=False)
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    client, admin = admin_client()
    return {"ccms": ccms, "cea": cea, "year": year, "client": client, "admin": admin}


# ── Access ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_both_imports_require_the_import_capability_and_recent_mfa(world):
    content = csv_bytes(PERIOD_HEADER, "UCN-A,MAIN,CCMS,1,ENROLLED")
    grads = csv_bytes(GRADUATION_HEADER, "UCN-A,MAIN,CCMS,2026-06-30")
    anonymous = Client()
    assert post_periods(anonymous, content, year=world["year"]).status_code in {401, 403}
    assert post_graduations(anonymous, grads).status_code in {401, 403}

    counselor = auth_client(make_user("UCN-COUNSELOR", role="COUNSELOR"))
    assert post_periods(counselor, content, year=world["year"]).status_code == 403
    assert post_graduations(counselor, grads).status_code == 403

    stale_admin = auth_client(make_user("UCN-ADMIN-2", role="IT_ADMIN"), recent_mfa=False)
    assert post_periods(stale_admin, content, year=world["year"]).status_code == 403
    assert post_graduations(stale_admin, grads).status_code == 403

    head = make_user("UCN-HEAD", role="COUNSELOR")
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    make_user("UCN-A")
    assert post_periods(auth_client(head), content, year=world["year"]).status_code == 200
    assert post_graduations(auth_client(head), grads).status_code == 200


# ── Term records ────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_term_preview_classifies_rows_and_writes_nothing(world):
    year, ccms = world["year"], world["ccms"]
    make_user("UCN-NEW")
    make_user("UCN-INACTIVE", active=False)
    same = make_user("UCN-SAME")
    changed = make_user("UCN-CHANGED")
    make_user("UCN-COUNSELOR", role="COUNSELOR")
    for student, level in ((same, 2), (changed, 2)):
        StudentAcademicPeriodRecord.objects.create(
            student=student,
            academic_year=year,
            term="FIRST_SEMESTER",
            college=ccms,
            year_level=level,
            enrollment_status="ENROLLED",
        )
    content = csv_bytes(
        PERIOD_HEADER,
        "UCN-NEW,MAIN,CCMS,1,",
        "UCN-INACTIVE,NORTH,CEA,,not_enrolled",
        "UCN-SAME,MAIN,CCMS,2,ENROLLED",
        "UCN-CHANGED,MAIN,CCMS,3,ENROLLED",
        "UCN-MISSING,MAIN,CCMS,1,ENROLLED",
        "UCN-COUNSELOR,MAIN,CCMS,1,ENROLLED",
        "UCN-NEW,MAIN,CCMS,1,ENROLLED",
        "UCN-BADLEVEL,MAIN,CCMS,9,ENROLLED",
        "UCN-BADSTATUS,MAIN,CCMS,1,GRADUATED",
        "UCN-CLOSED,EAST,ENG,1,ENROLLED",
    )
    before = AuditEvent.objects.count()
    response = post_periods(world["client"], content, year=year)
    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["valid"] is False and payload["committed"] is False
    assert (payload["create_count"], payload["update_count"], payload["noop_count"]) == (2, 1, 1)
    assert (payload["conflict_count"], payload["invalid_count"]) == (3, 3)
    by_row = {row["row_number"]: row for row in payload["rows"]}
    assert by_row[2]["action"] == "CREATE" and by_row[2]["enrollment_status"] == "UNKNOWN"
    assert by_row[3]["action"] == "CREATE", (
        "an inactive Student account is allowed, as in the single-record form"
    )
    assert by_row[3]["enrollment_status"] == "NOT_ENROLLED"
    assert by_row[4]["action"] == "NOOP"
    assert by_row[5]["action"] == "UPDATE"
    assert (by_row[5]["current_year_level"], by_row[5]["year_level"]) == (2, 3)
    assert [by_row[n]["action"] for n in (6, 7, 11)] == ["CONFLICT", "CONFLICT", "CONFLICT"]
    assert "duplicate" in by_row[8]["message"]
    assert "1 to 8" in by_row[9]["message"]
    assert "ENROLLED" in by_row[10]["message"]
    assert StudentAcademicPeriodRecord.objects.count() == 2
    assert AuditEvent.objects.count() == before


@pytest.mark.django_db
def test_term_apply_writes_each_record_keeps_placement_and_audits_counts(world):
    year, ccms, cea = world["year"], world["ccms"], world["cea"]
    placed = make_user("UCN-PLACED")
    place(placed, ccms)
    make_user("UCN-OTHER")
    content = csv_bytes(PERIOD_HEADER, "UCN-PLACED,NORTH,CEA,4,ENROLLED", "UCN-OTHER,MAIN,CCMS,,")
    preview = post_periods(world["client"], content, year=year).json()
    assert preview["valid"] is True

    response = post_periods(
        world["client"],
        content,
        year=year,
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
    )
    assert response.status_code == 200, response.content
    assert response.json()["committed"] is True
    record = StudentAcademicPeriodRecord.objects.get(student=placed)
    assert (record.college_id, record.year_level, record.enrollment_status) == (
        cea.pk,
        4,
        "ENROLLED",
    )
    assert (
        StudentAcademicPeriodRecord.objects.get(
            student__institutional_id="UCN-OTHER"
        ).enrollment_status
        == "UNKNOWN"
    )
    assert StudentAcademicProfile.objects.get(student=placed).current_college_id == ccms.pk, (
        "placement is untouched"
    )
    assert AuditEvent.objects.filter(action="student_academics.period.recorded").count() == 2
    summary = AuditEvent.objects.get(action="student_academics.periods.imported")
    assert summary.metadata == {
        "academic_year_id": str(year.pk),
        "term": "FIRST_SEMESTER",
        "total_rows": 2,
        "create_count": 2,
        "update_count": 0,
        "noop_count": 0,
    }

    again = post_periods(world["client"], content, year=year).json()
    assert again["noop_count"] == 2
    post_periods(
        world["client"], content, year=year, dry_run=False, fingerprint=again["preview_fingerprint"]
    )
    assert AuditEvent.objects.filter(action="student_academics.periods.imported").count() == 1, (
        "all-no-change apply adds no summary"
    )


@pytest.mark.django_db
def test_term_apply_needs_the_preview_and_refuses_when_records_changed(world):
    year, ccms = world["year"], world["ccms"]
    student = make_user("UCN-RACE")
    content = csv_bytes(
        PERIOD_HEADER, "UCN-RACE,MAIN,CCMS,1,ENROLLED", "UCN-SECOND,MAIN,CCMS,1,ENROLLED"
    )
    make_user("UCN-SECOND")
    missing = post_periods(world["client"], content, year=year, dry_run=False)
    assert (
        missing.status_code == 422
        and missing.json()["error"]["code"] == "csv_import_preview_required"
    )

    preview = post_periods(world["client"], content, year=year).json()
    StudentAcademicPeriodRecord.objects.create(
        student=student,
        academic_year=year,
        term="FIRST_SEMESTER",
        college=ccms,
        year_level=2,
        enrollment_status="ENROLLED",
    )
    stale = post_periods(
        world["client"],
        content,
        year=year,
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "csv_import_stale"
    assert StudentAcademicPeriodRecord.objects.count() == 1, "nothing from the file was saved"

    other_term = post_periods(
        world["client"],
        content,
        year=year,
        term="SECOND_SEMESTER",
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
    )
    assert other_term.status_code == 409, "a preview for one term never confirms another"


@pytest.mark.django_db
def test_term_import_input_and_structure_errors(world):
    make_user("UCN-A")
    ok = csv_bytes("institutional_id,campus_code,college_code", "UCN-A,MAIN,CCMS")
    assert post_periods(world["client"], ok, year=world["year"]).json()["create_count"] == 1, (
        "optional columns may be omitted"
    )
    unknown_year = AcademicYear(label="2099-2100")
    assert post_periods(world["client"], ok, year=unknown_year).status_code == 404
    assert post_periods(world["client"], ok, year=world["year"], term="SUMMER").status_code == 422
    bad = post_periods(
        world["client"],
        csv_bytes(PERIOD_HEADER + ",email", "UCN-A,MAIN,CCMS,1,ENROLLED,a@b.c"),
        year=world["year"],
    )
    assert (
        bad.status_code == 422 and bad.json()["error"]["code"] == "csv_import_unsupported_headers"
    )
    invalid = post_periods(
        world["client"],
        csv_bytes(PERIOD_HEADER, "UCN-A,MAIN,CCMS,0,ENROLLED"),
        year=world["year"],
        dry_run=False,
        fingerprint="x",
    )
    assert (
        invalid.status_code == 422 and invalid.json()["error"]["code"] == "csv_import_invalid_rows"
    )


# ── Graduation records ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_graduation_preview_states_consequences_and_writes_nothing(world):
    ccms = world["ccms"]
    current = make_user("UCN-CURRENT")
    current.student_lifecycle_status = StudentLifecycleStatus.CURRENT
    current.save()
    place(current, ccms)
    done = make_user("UCN-DONE")
    done.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    done.save()
    StudentGraduationRecord.objects.create(
        student=done,
        graduated_college=ccms,
        graduation_date=date(2026, 6, 30),
        verification_source=SOURCE,
        verified_at="2026-07-01T00:00Z",
    )
    moved = make_user("UCN-MOVED")
    moved.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    moved.save()
    StudentGraduationRecord.objects.create(
        student=moved,
        graduated_college=ccms,
        graduation_date=date(2025, 6, 30),
        verification_source=SOURCE,
        verified_at="2025-07-01T00:00Z",
    )
    content = csv_bytes(
        GRADUATION_HEADER,
        "UCN-CURRENT,MAIN,CCMS,2026-06-30",
        "UCN-DONE,MAIN,CCMS,2026-06-30",
        "UCN-MOVED,MAIN,CCMS,2026-06-30",
        "UCN-NOBODY,MAIN,CCMS,2026-06-30",
        "UCN-BADDATE,MAIN,CCMS,06/30/2026",
        "UCN-NODATE,MAIN,CCMS,2026-02-30",
    )
    response = post_graduations(world["client"], content)
    assert response.status_code == 200, response.content
    payload = response.json()
    assert actions(payload) == {
        "UCN-CURRENT": "GRADUATE",
        "UCN-DONE": "NOOP",
        "UCN-MOVED": "UPDATE",
        "UCN-NOBODY": "CONFLICT",
        "UCN-BADDATE": "INVALID",
        "UCN-NODATE": "INVALID",
    }
    assert (payload["write_count"], payload["placement_cleared_count"]) == (2, 1)
    current_row = next(row for row in payload["rows"] if row["institutional_id"] == "UCN-CURRENT")
    assert (
        current_row["current_placement_college_code"] == "CCMS"
        and "leave the CCMS placement" in current_row["message"]
    )
    moved_row = next(row for row in payload["rows"] if row["institutional_id"] == "UCN-MOVED")
    assert (moved_row["previous_graduation_date"], moved_row["graduation_date"]) == (
        "2025-06-30",
        "2026-06-30",
    )
    current.refresh_from_db()
    assert current.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert StudentAcademicProfile.objects.get(student=current).current_college_id == ccms.pk


@pytest.mark.django_db
def test_graduation_apply_requires_the_typed_count_then_graduates_and_clears_placement(world):
    ccms = world["ccms"]
    students = [make_user(f"UCN-GRAD-{n}") for n in range(3)]
    for student in students:
        student.student_lifecycle_status = StudentLifecycleStatus.CURRENT
        student.save()
        place(student, ccms)
    content = csv_bytes(
        GRADUATION_HEADER, *(f"{s.institutional_id},MAIN,CCMS,2026-06-30" for s in students)
    )
    preview = post_graduations(world["client"], content).json()
    assert preview["write_count"] == 3

    wrong = post_graduations(
        world["client"],
        content,
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
        confirmed=2,
    )
    assert (
        wrong.status_code == 422
        and wrong.json()["error"]["code"] == "csv_import_confirmation_mismatch"
    )
    assert StudentGraduationRecord.objects.count() == 0

    applied = post_graduations(
        world["client"],
        content,
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
        confirmed=3,
    )
    assert applied.status_code == 200, applied.content
    for student in students:
        student.refresh_from_db()
        assert student.student_lifecycle_status == StudentLifecycleStatus.GRADUATED
        assert StudentAcademicProfile.objects.get(student=student).current_college_id is None
        assert StudentGraduationRecord.objects.get(student=student).verification_source == SOURCE
    assert AuditEvent.objects.filter(action="student_academics.graduation.recorded").count() == 3
    assert AuditEvent.objects.filter(action="student_academics.placement.cleared").count() == 3
    summary = AuditEvent.objects.get(action="student_academics.graduations.imported")
    assert summary.metadata == {
        "total_rows": 3,
        "graduate_count": 3,
        "update_count": 0,
        "noop_count": 0,
        "placement_cleared_count": 3,
    }


@pytest.mark.django_db
def test_graduation_apply_is_all_or_nothing_when_a_row_turns_into_a_conflict(world):
    ccms = world["ccms"]
    first, second = make_user("UCN-ONE"), make_user("UCN-TWO")
    content = csv_bytes(
        GRADUATION_HEADER, "UCN-ONE,MAIN,CCMS,2026-06-30", "UCN-TWO,MAIN,CCMS,2026-06-30"
    )
    preview = post_graduations(world["client"], content).json()
    ccms.is_active = False
    ccms.save()
    refused = post_graduations(
        world["client"],
        content,
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
        confirmed=2,
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "csv_import_conflict"
    assert StudentGraduationRecord.objects.count() == 0
    for student in (first, second):
        student.refresh_from_db()
        assert student.student_lifecycle_status != StudentLifecycleStatus.GRADUATED


@pytest.mark.django_db
def test_graduation_source_is_required_and_bounded(world):
    make_user("UCN-A")
    content = csv_bytes(GRADUATION_HEADER, "UCN-A,MAIN,CCMS,2026-06-30")
    assert post_graduations(world["client"], content, source="  ").status_code == 422
    assert post_graduations(world["client"], content, source="x" * 201).status_code == 422
    assert post_graduations(world["client"], content, source="x" * 200).status_code == 200
    missing_date_column = csv_bytes("institutional_id,campus_code,college_code", "UCN-A,MAIN,CCMS")
    response = post_graduations(world["client"], missing_date_column)
    assert (
        response.status_code == 422
        and response.json()["error"]["code"] == "csv_import_unsupported_headers"
    )
