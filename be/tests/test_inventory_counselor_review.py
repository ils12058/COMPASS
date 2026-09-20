from __future__ import annotations

import importlib
import json

import pytest
from django.apps import apps
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.inventory.models import InventoryReopenEvent, StudentInventory
from compass.inventory.services import (
    InventoryConflict,
    ensure_current_inventory,
    reopen_inventory_for_correction,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.notifications.models import Notification
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from compass.reports.services import build_student_profiling_report, resolve_report_access_scope
from compass.student_support.services import get_student_support_context
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    role: str,
    *,
    institutional_id: str | None = None,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        last_name="User",
        institutional_id=institutional_id,
    )


def make_head(email: str = "inventory-head@example.edu") -> User:
    head = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return head


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    session = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = session.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def configure_year(actor: User, label: str = "2026-2027"):
    year = create_academic_year(label=label, context=context(actor))
    return set_current_academic_year(academic_year_id=year.pk, context=context(actor))


def make_org(code: str) -> tuple[Campus, College, Program]:
    campus = Campus.objects.create(code=f"C-{code}", name=f"Campus {code}")
    college = College.objects.create(campus=campus, code=code, name=f"College {code}")
    program = Program.objects.create(
        college=college,
        code=f"P-{code}",
        name=f"Program {code}",
    )
    return campus, college, program


def affiliate(student: User, college: College, counselor: User | None = None) -> None:
    StudentAffiliation.objects.create(student=student, college=college)
    if counselor is not None:
        CounselorResponsibility.objects.create(college=college, counselor=counselor)


def submit_inventory(
    *,
    student: User,
    program: Program,
    year_level: int = 1,
) -> StudentInventory:
    ensure_current_inventory(student=student, context=context(student))
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(
            program_id=program.pk,
            year_level=year_level,
        ),
    )
    return submit_current_inventory(student=student, context=context(student))


@pytest.mark.django_db
def test_inventory_policy_is_counselor_baseline_only_for_raw_review():
    sync_policy()
    counselor = make_user("inventory-policy-counselor@example.edu", "COUNSELOR")
    head = make_head("inventory-policy-head@example.edu")
    student = make_user("inventory-policy-student@example.edu", "STUDENT")
    gss = make_user("inventory-policy-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    admin = make_user("inventory-policy-admin@example.edu", "IT_ADMIN")
    officer = make_user("inventory-policy-officer@example.edu", "INSTITUTIONAL_OFFICER")

    for actor in (counselor, head):
        assert actor.has_capability("inventory.view")
        assert actor.has_capability("inventory.reopen")

    assert student.has_capability("inventory.view_self")
    assert student.has_capability("inventory.manage_self")
    for actor in (student, gss, admin, officer):
        assert not actor.has_capability("inventory.view")
        assert not actor.has_capability("inventory.reopen")


@pytest.mark.django_db
def test_inventory_reopen_resubmit_preserves_history_and_hides_draft_from_guidance_surfaces():
    sync_policy()
    admin = make_user("inventory-admin@example.edu", "IT_ADMIN")
    counselor = make_user("inventory-counselor@example.edu", "COUNSELOR")
    student = make_user(
        "inventory-student@example.edu",
        "STUDENT",
        institutional_id="2026-0001",
    )
    _, college, program = make_org("A1")
    affiliate(student, college, counselor)
    first_year = configure_year(admin)

    submitted = submit_inventory(student=student, program=program)
    first_timestamp = submitted.submitted_at
    assert first_timestamp is not None
    assert submitted.first_submitted_at == first_timestamp
    assert submitted.last_submitted_at == first_timestamp

    counselor_client = auth_client(counselor)
    detail = counselor_client.get(f"/api/v1/inventory/records/{submitted.pk}")
    assert detail.status_code == 200
    assert detail.json()["student"]["id"] == str(student.pk)

    support_before = get_student_support_context(actor=counselor, student_id=student.pk)
    assert support_before.inventory_status == "SUBMITTED"
    assert support_before.available is True
    access_scope = resolve_report_access_scope(counselor)
    report_before = build_student_profiling_report(access_scope=access_scope)
    assert report_before["report_context"]["submitted_inventory_count"] == 1

    reopened = counselor_client.post(
        f"/api/v1/inventory/records/{submitted.pk}/reopen",
        data=json.dumps({"reason": "Please correct the annual record."}),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "DRAFT"
    assert reopened.json()["correction_pending"] is True

    submitted.refresh_from_db()
    assert submitted.submitted_at is None
    assert submitted.first_submitted_at == first_timestamp
    assert submitted.last_submitted_at == first_timestamp
    assert InventoryReopenEvent.objects.filter(inventory=submitted).count() == 1

    notification = Notification.objects.get(
        recipient=student,
        event_code="inventory.reopened",
    )
    assert notification.source_type == "inventory_reopen_event"
    assert "Please correct" not in notification.message

    with pytest.raises(InventoryConflict):
        reopen_inventory_for_correction(
            actor=counselor,
            inventory_id=submitted.pk,
            reason="Duplicate reopen must fail.",
            context=context(counselor),
        )
    assert InventoryReopenEvent.objects.filter(inventory=submitted).count() == 1

    hidden = counselor_client.get(f"/api/v1/inventory/records/{submitted.pk}")
    assert hidden.status_code == 409
    assert hidden.json()["error"]["code"] == "inventory_not_submitted"

    support_draft = get_student_support_context(actor=counselor, student_id=student.pk)
    assert support_draft.inventory_status == "DRAFT"
    assert support_draft.available is False
    report_draft = build_student_profiling_report(access_scope=access_scope)
    assert report_draft["report_context"]["submitted_inventory_count"] == 0

    replace_current_inventory(student=student, values={"nickname": "Corrected"})
    resubmitted = submit_current_inventory(student=student, context=context(student))
    assert resubmitted.first_submitted_at == first_timestamp
    assert resubmitted.last_submitted_at is not None
    assert resubmitted.submitted_at == resubmitted.last_submitted_at
    assert (
        AuditEvent.objects.filter(
            action="inventory.resubmitted",
            target_id=str(resubmitted.pk),
        ).count()
        == 1
    )

    support_after = get_student_support_context(actor=counselor, student_id=student.pk)
    assert support_after.inventory_status == "SUBMITTED"
    assert support_after.available is True
    report_after = build_student_profiling_report(access_scope=access_scope)
    assert report_after["report_context"]["submitted_inventory_count"] == 1

    next_year = create_academic_year(label="2027-2028", context=context(admin))
    set_current_academic_year(academic_year_id=next_year.pk, context=context(admin))
    historical = counselor_client.get(f"/api/v1/inventory/records/{resubmitted.pk}")
    assert historical.status_code == 200

    denied_reopen = counselor_client.post(
        f"/api/v1/inventory/records/{resubmitted.pk}/reopen",
        data=json.dumps({"reason": "Historical correction should remain locked."}),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert denied_reopen.status_code == 409
    resubmitted.refresh_from_db()
    assert resubmitted.submitted_at is not None
    assert resubmitted.academic_year_id == first_year.pk


@pytest.mark.django_db
def test_inventory_roster_scope_missing_filters_search_and_draft_privacy():
    sync_policy()
    admin = make_user("roster-admin@example.edu", "IT_ADMIN")
    counselor_a = make_user("roster-counselor-a@example.edu", "COUNSELOR")
    counselor_b = make_user("roster-counselor-b@example.edu", "COUNSELOR")
    head = make_head("roster-head@example.edu")
    current = configure_year(admin)
    historical = create_academic_year(label="2025-2026", context=context(admin))

    campus_a = Campus.objects.create(code="ROSTER-A", name="Roster Campus A")
    college_a1 = College.objects.create(campus=campus_a, code="A1", name="College A1")
    college_a2 = College.objects.create(campus=campus_a, code="A2", name="College A2")
    program_a1 = Program.objects.create(college=college_a1, code="PA1", name="Program A1")
    program_a2 = Program.objects.create(college=college_a2, code="PA2", name="Program A2")
    _, college_b1, program_b1 = make_org("B1")
    CounselorResponsibility.objects.create(college=college_a1, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=college_b1, counselor=counselor_b)

    submitted_student = make_user(
        "alpha.student@example.edu",
        "STUDENT",
        institutional_id="A1-001",
    )
    missing_student = make_user(
        "missing.student@example.edu",
        "STUDENT",
        institutional_id="A1-002",
    )
    draft_student = make_user(
        "draft.student@example.edu",
        "STUDENT",
        institutional_id="A1-003",
    )
    a2_student = make_user("a2.student@example.edu", "STUDENT", institutional_id="A2-001")
    b1_student = make_user("b1.student@example.edu", "STUDENT", institutional_id="B1-001")
    for student, college in (
        (submitted_student, college_a1),
        (missing_student, college_a1),
        (draft_student, college_a1),
        (a2_student, college_a2),
        (b1_student, college_b1),
    ):
        StudentAffiliation.objects.create(student=student, college=college)

    submitted = submit_inventory(student=submitted_student, program=program_a1)
    ensure_current_inventory(student=draft_student, context=context(draft_student))
    replace_current_inventory(
        student=draft_student,
        values=minimum_normalized_inventory_values(program_id=program_a1.pk),
    )
    submit_inventory(student=a2_student, program=program_a2)
    submit_inventory(student=b1_student, program=program_b1)

    client = auth_client(counselor_a)
    listing = client.get("/api/v1/inventory/students", {"page_size": 2})
    assert listing.status_code == 200
    assert listing.json()["page"] == 1
    assert listing.json()["page_size"] == 2
    assert listing.json()["has_next"] is True
    assert all(
        row["student"]["institutional_id"].startswith("A1-") for row in listing.json()["items"]
    )

    searched = client.get("/api/v1/inventory/students", {"search": "A1-001"})
    assert searched.status_code == 200
    assert [row["inventory_id"] for row in searched.json()["items"]] == [str(submitted.pk)]

    missing = client.get("/api/v1/inventory/students", {"status": "MISSING"})
    assert missing.status_code == 200
    assert [row["student"]["id"] for row in missing.json()["items"]] == [str(missing_student.pk)]

    draft = client.get("/api/v1/inventory/students", {"status": "DRAFT"})
    assert draft.status_code == 200
    assert [row["student"]["id"] for row in draft.json()["items"]] == [str(draft_student.pk)]
    draft_inventory_id = draft.json()["items"][0]["inventory_id"]
    draft_detail = client.get(f"/api/v1/inventory/records/{draft_inventory_id}")
    assert draft_detail.status_code == 409

    assert (
        client.get(
            "/api/v1/inventory/students",
            {"college_id": str(college_a2.pk)},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/inventory/students",
            {"program_id": str(program_b1.pk)},
        ).status_code
        == 403
    )

    historical_missing = client.get(
        "/api/v1/inventory/students",
        {"academic_year_id": str(historical.pk), "status": "MISSING"},
    )
    assert historical_missing.status_code == 409

    head_listing = auth_client(head).get("/api/v1/inventory/students", {"page_size": 50})
    assert head_listing.status_code == 200
    assert {row["student"]["id"] for row in head_listing.json()["items"]} == {
        str(submitted_student.pk),
        str(missing_student.pk),
        str(draft_student.pk),
        str(a2_student.pk),
        str(b1_student.pk),
    }

    assert current.is_current is True


@pytest.mark.django_db
def test_inventory_submission_history_backfill_uses_existing_submitted_at_only():
    sync_policy()
    admin = make_user("migration-admin@example.edu", "IT_ADMIN")
    student = make_user("migration-student@example.edu", "STUDENT")
    _, college, program = make_org("MIG")
    StudentAffiliation.objects.create(student=student, college=college)
    configure_year(admin)
    item = submit_inventory(student=student, program=program)
    original = item.submitted_at
    StudentInventory.objects.filter(pk=item.pk).update(
        first_submitted_at=None,
        last_submitted_at=None,
    )

    migration = importlib.import_module(
        "compass.inventory.migrations.0005_submission_history_reopen"
    )
    migration.backfill_submission_history(apps, None)

    item.refresh_from_db()
    assert item.first_submitted_at == original
    assert item.last_submitted_at == original
