"""GM-INV-1: Registrar snapshots, document confirmation, and College consistency."""

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.good_moral.graduation_basis import request_graduation_evidence
from compass.good_moral.models import GoodMoralVariant
from compass.good_moral.services import (
    GoodMoralGraduateDocumentCheckRequired,
    GoodMoralInventoryCollegeMismatch,
    correction_fields,
    create_assisted_request,
    get_f4_academic_context,
    prepare_request,
)
from compass.inventory.services import (
    InventoryProgramCollegeMismatch,
    reopen_inventory_for_correction,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.models import Campus, College, CounselorResponsibility, Program
from compass.student_academics.models import StudentAcademicProfile
from compass.student_academics.services import InvalidStudentAcademicInput, record_graduation
from tests.test_good_moral import (
    auth_client,
    create_my_current_student,
    create_my_graduate,
    csrf,
    issue_request,
    make_academic_year,
    make_current_request,
    make_graduate_request,
    make_inventory,
    make_placement,
    make_user,
    record_inspected_receipt,
    sync_policy,
)
from tests.test_student_academic_batch_import import (
    GRADUATION_HEADER,
    csv_bytes,
    post_graduations,
)
from tests.test_student_academic_batch_import import world as world
from tests.test_student_academic_roster_import import make_user as import_user

pytestmark = pytest.mark.django_db


def program(college=None, code="OTHER", active=True):
    if college is None:
        campus = Campus.objects.create(code="OTHER", name="Other Campus")
        college = College.objects.create(campus=campus, code="OTHER", name="Other College")
    return Program.objects.create(
        college=college, code=code, name=f"Bachelor {code}", is_active=active
    )


@pytest.mark.parametrize("state", ["valid", "blank", "wrong_college", "inactive"])
def test_graduation_csv_optional_program(world, state):
    student = import_user("GM-CSV")
    picked = program(
        world["cea"] if state == "wrong_college" else world["ccms"], active=state != "inactive"
    )
    text = csv_bytes(
        GRADUATION_HEADER + ",program_code",
        f"GM-CSV,MAIN,CCMS,2026-06-30,{'' if state == 'blank' else picked.code}",
    )
    response = post_graduations(world["client"], text)
    assert response.status_code == 200
    preview = response.json()
    if state in {"wrong_college", "inactive"}:
        assert preview["rows"][0]["action"] == "INVALID"
        assert "active Program under this row's College" in preview["rows"][0]["message"]
        assert (
            post_graduations(
                world["client"],
                text,
                dry_run=False,
                fingerprint=preview["preview_fingerprint"],
                confirmed=1,
            ).status_code
            == 422
        )
        return
    assert preview["valid"]
    applied = post_graduations(
        world["client"],
        text,
        dry_run=False,
        fingerprint=preview["preview_fingerprint"],
        confirmed=1,
    )
    assert applied.status_code == 200
    student.refresh_from_db()
    assert student.graduation_record.graduated_program_id == (
        None if state == "blank" else picked.pk
    )


def test_graduation_program_fingerprint_covers_column_and_saved_record(world):
    import_user("GM-HASH")
    first, second = program(world["ccms"], "ONE"), program(world["ccms"], "TWO")

    def text(code):
        return csv_bytes(
            GRADUATION_HEADER + ",program_code", f"GM-HASH,MAIN,CCMS,2026-06-30,{code}"
        )

    one = post_graduations(world["client"], text(first.code)).json()
    two = post_graduations(world["client"], text(second.code)).json()
    assert one["preview_fingerprint"] != two["preview_fingerprint"]
    assert (
        post_graduations(
            world["client"],
            text(second.code),
            dry_run=False,
            fingerprint=one["preview_fingerprint"],
            confirmed=1,
        ).status_code
        == 409
    )


@pytest.mark.parametrize("invalid", [False, True])
def test_manual_graduation_program_validation_and_noop(invalid):
    sync_policy()
    student = make_user("manual-gm@example.test")
    profile = make_placement(student)
    picked = program(None if invalid else profile.current_college)
    values = dict(
        student_id=student.pk,
        graduated_college_id=profile.current_college_id,
        graduated_program_id=picked.pk,
        graduation_date=date(2026, 6, 30),
        verification_source="Registrar confirmation",
        context=AuditContext.user(student),
    )
    if invalid:
        with pytest.raises(InvalidStudentAcademicInput):
            record_graduation(**values)
        return
    record = record_graduation(**values)
    timestamp = record.verified_at
    assert record_graduation(**values).verified_at == timestamp
    events = AuditEvent.objects.filter(action="student_academics.graduation.recorded")
    assert events.count() == 1
    assert events.get().metadata["new_program_id"] == str(picked.pk)


@pytest.mark.parametrize("assisted", [False, True])
@pytest.mark.parametrize("has_program", [False, True])
def test_graduate_uses_registrar_facts_and_frozen_staff_evidence(assisted, has_program):
    sync_policy()
    student = make_user("record-gm@example.test")
    counselor = make_user("record-staff@example.test", role="COUNSELOR")
    profile = make_placement(student)
    picked = program(profile.current_college) if has_program else None
    record = record_graduation(
        student_id=student.pk,
        graduated_college_id=profile.current_college_id,
        graduated_program_id=picked.pk if picked else None,
        graduation_date=date(2026, 6, 30),
        verification_source="Registrar list",
        context=AuditContext.user(counselor),
    )
    student.refresh_from_db()
    details = dict(
        degree="Typed legacy degree", major="Optional major", graduation_date=date(2025, 1, 1)
    )
    if assisted:
        item = create_assisted_request(
            actor=counselor,
            student_id=student.pk,
            variant=GoodMoralVariant.GRADUATE,
            details=details,
            idempotency_key=str(uuid4()),
            request_fingerprint="a" * 64,
            context=AuditContext.user(counselor),
        )
    else:
        item = create_my_graduate(student=student, **details, context=AuditContext.user(student))
    assert item.graduation_date == record.graduation_date
    assert item.degree_snapshot == (picked.name if picked else details["degree"])
    evidence = request_graduation_evidence(item)
    assert evidence["record_id"] == str(record.pk)
    assert evidence["graduated_college"]["id"] == str(record.graduated_college_id)
    assert "graduation_date" not in correction_fields(counselor, item)
    assert ("degree_snapshot" not in correction_fields(counselor, item)) == has_program
    record.graduation_date = date(2024, 1, 1)
    record.verification_source = "Edited source"
    record.save()
    mine = auth_client(student).get(f"/api/v1/good-moral/me/{item.pk}").json()
    assert mine["graduation_date"] == "2026-06-30"
    assert mine["graduation_basis"] == "REGISTRAR_RECORD"
    assert "graduation_verified_at" not in mine and "graduation_verification_source" not in mine
    staff = auth_client(counselor).get(f"/api/v1/good-moral/requests/{item.pk}").json()
    assert staff["graduation_verification_source"] == "Registrar list"
    context = auth_client(student).get("/api/v1/good-moral/me/graduation-context")
    assert context.status_code == 200
    assert "verification_source" not in context.json()
    assert auth_client(counselor).get("/api/v1/good-moral/me/graduation-context").status_code == 403


@pytest.mark.parametrize("offset_hours", [0, 8])
def test_no_record_prepare_requires_explicit_document_check_and_records_actor(offset_hours):
    sync_policy()
    student = make_user("documents-gm@example.test", lifecycle="GRADUATED")
    staff = make_user("documents-staff@example.test", role="COUNSELOR")
    item = record_inspected_receipt(make_graduate_request(student), staff)
    values = dict(
        actor=staff,
        request_id=item.pk,
        context=AuditContext.user(staff),
        expected_resource_version=item.updated_at.isoformat(),
        now=datetime.now(timezone(timedelta(hours=offset_hours))),
    )
    with pytest.raises(GoodMoralGraduateDocumentCheckRequired):
        prepare_request(**values)
    item = prepare_request(**values, diploma_tor_checked=True)
    event = AuditEvent.objects.get(action="good_moral.prepared", target_id=str(item.pk))
    assert event.actor_user_id == staff.pk
    assert event.metadata["document_checked_by_id"] == str(staff.pk)
    assert event.metadata["document_checked_at"] == item.prepared_at.isoformat()


def test_inventory_save_submit_and_no_placement_behavior():
    sync_policy()
    student = make_user("college-inventory@example.test")
    profile = make_placement(student)
    inventory = make_inventory(student, make_academic_year(), submitted=False)
    other = program()
    with pytest.raises(InventoryProgramCollegeMismatch):
        replace_current_inventory(student=student, values={"program_id": other.pk})
    # A legacy saved value/placement change is checked again at submit, before private validation.
    inventory.program = other
    inventory.save(update_fields=["program"])
    with pytest.raises(InventoryProgramCollegeMismatch):
        submit_current_inventory(student=student, context=AuditContext.user(student))
    profile.current_college = None
    profile.save()
    inventory.program = None
    inventory.save(update_fields=["program"])
    assert (
        replace_current_inventory(student=student, values={"program_id": other.pk}).program_id
        == other.pk
    )
    assert (
        auth_client(student).get("/api/v1/inventory/me/current").json()["current_college"] is None
    )


def test_legacy_ready_graduate_requires_and_can_record_document_confirmation():
    sync_policy()
    student = make_user("legacy-documents@example.test", lifecycle="GRADUATED")
    staff = make_user("legacy-documents-staff@example.test", role="COUNSELOR")
    item = record_inspected_receipt(make_graduate_request(student), staff)
    verification = item.receipt_revisions.get(is_current=True).verifications.get(
        invalidated_at__isnull=True
    )
    type(item).objects.filter(pk=item.pk).update(
        status="READY_FOR_ISSUANCE",
        prepared_by=staff,
        prepared_at=item.updated_at,
        prepared_receipt_verification=verification,
    )
    item.refresh_from_db()
    with pytest.raises(GoodMoralGraduateDocumentCheckRequired):
        issue_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    client = auth_client(staff)
    url = f"/api/v1/good-moral/requests/{item.pk}"
    actions = client.get(url).json()["actions"]
    assert actions["can_prepare"] and not actions["can_issue"]
    payload = {"expected_resource_version": item.updated_at.isoformat()}
    refused = client.post(
        url + "/prepare", data=json.dumps(payload), content_type="application/json", **csrf(client)
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "good_moral_graduate_document_check_required"
    payload["diploma_tor_checked"] = True
    confirmed = client.post(
        url + "/prepare", data=json.dumps(payload), content_type="application/json", **csrf(client)
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["document_checked_by_id"] == str(staff.pk)
    assert body["document_checked_at"] == body["prepared_at"]
    assert body["actions"]["can_issue"] and not body["actions"]["can_prepare"]
    mine = auth_client(student).get(f"/api/v1/good-moral/me/{item.pk}").json()
    assert "document_checked_at" not in mine and "document_checked_by_id" not in mine
    replay = prepare_request(
        actor=staff,
        request_id=item.pk,
        context=AuditContext.user(staff),
        expected_resource_version=body["actions"]["request_version"],
    )
    assert replay.prepared_at == datetime.fromisoformat(body["actions"]["preparation_version"])


def test_inventory_correction_reuses_college_guard_and_staff_cannot_self_edit():
    sync_policy()
    student = make_user("correction-inventory@example.test")
    counselor = make_user("correction-staff@example.test", role="COUNSELOR")
    profile = make_placement(student)
    inventory = make_inventory(student, make_academic_year())
    CounselorResponsibility.objects.create(counselor=counselor, college=profile.current_college)
    reopen_inventory_for_correction(
        actor=counselor,
        inventory_id=inventory.pk,
        reason="Correct the Program",
        context=AuditContext.user(counselor),
    )
    other = program()
    with pytest.raises(InventoryProgramCollegeMismatch):
        replace_current_inventory(student=student, values={"program_id": other.pk})
    client = auth_client(counselor)
    refused = client.put(
        "/api/v1/inventory/me/current", data="{}", content_type="application/json", **csrf(client)
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "permission_denied"
    inventory.refresh_from_db()
    assert inventory.program.college_id == profile.current_college_id


@pytest.mark.parametrize("stage", ["create", "prepare"])
def test_current_good_moral_college_change_is_refused(stage):
    sync_policy()
    student = make_user("mismatch-gm@example.test")
    counselor = make_user("mismatch-staff@example.test", role="COUNSELOR")
    item, inventory = make_current_request(student)
    other = program()
    StudentAcademicProfile.objects.filter(student=student).update(current_college=other.college)
    assert get_f4_academic_context(student).status == "COLLEGE_MISMATCH"
    if stage == "create":
        with pytest.raises(GoodMoralInventoryCollegeMismatch):
            create_my_current_student(
                student=student, semester="First Semester", context=AuditContext.user(student)
            )
        picker = auth_client(counselor).get("/api/v1/good-moral/student-options").json()["items"][0]
        assert picker["f4_eligibility"]["status"] == "COLLEGE_MISMATCH"
    else:
        item = record_inspected_receipt(item, counselor)
        with pytest.raises(GoodMoralInventoryCollegeMismatch):
            prepare_request(
                actor=counselor,
                request_id=item.pk,
                context=AuditContext.user(counselor),
                expected_resource_version=item.updated_at.isoformat(),
            )
