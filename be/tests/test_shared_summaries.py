from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling.models import CounselingSharedSummary
from compass.counseling.services import create_encounter
from compass.counseling.shared_summaries import (
    CounselingSharedSummaryAlreadyPublished,
    CounselingSharedSummaryEmpty,
    publish_assigned_shared_summary,
    put_assigned_shared_summary,
)
from compass.inventory.services import (
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import Campus, College, Program
from compass.routine_interviews.services import (
    create_direct,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from compass.service_catalog.services import create_service, set_service_active
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def create_counseling_service(actor: User):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON", "ONLINE"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def make_encounter(*, counselor: User, student: User, mode: str = "IN_PERSON"):
    end = timezone.now() - timedelta(minutes=2)
    return create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode=mode,
        started_at=end - timedelta(minutes=45),
        ended_at=end,
        context=context(counselor),
    )


@pytest.mark.django_db
def test_shared_summary_model_one_per_encounter_protect_and_draft_put_is_stable():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    create_counseling_service(admin)
    encounter = make_encounter(counselor=counselor, student=student)

    first = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content="First draft",
    )
    second = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content="Revised draft",
    )

    assert first.pk == second.pk
    assert second.content == "Revised draft"
    assert second.published_at is None
    assert CounselingSharedSummary.objects.filter(encounter=encounter).count() == 1

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CounselingSharedSummary.objects.create(encounter=encounter, content="Duplicate")

    with pytest.raises(ProtectedError):
        encounter.delete()


@pytest.mark.django_db
def test_publish_is_explicit_idempotent_immutable_and_audit_content_free():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    create_counseling_service(admin)
    encounter = make_encounter(counselor=counselor, student=student)

    empty = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content="   \n",
    )
    with pytest.raises(CounselingSharedSummaryEmpty):
        publish_assigned_shared_summary(
            encounter_id=encounter.pk,
            counselor=counselor,
            context=context(counselor),
        )
    empty.refresh_from_db()
    assert empty.published_at is None

    marker = "STUDENT-VISIBLE-UNIQUE-SENSITIVE-MARKER"
    draft = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content=marker,
    )
    published = publish_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        context=context(counselor),
    )
    repeated = publish_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        context=context(counselor),
    )

    assert published.pk == draft.pk == repeated.pk
    assert published.published_at is not None
    events = AuditEvent.objects.filter(action="counseling.shared_summary.published")
    assert events.count() == 1
    event = events.get()
    assert event.target_type == "counseling.sharedsummary"
    assert event.target_id == str(published.pk)
    assert event.metadata == {"counseling_encounter_id": str(encounter.pk)}
    assert marker not in json.dumps(event.metadata)

    notification = Notification.objects.get(
        recipient=student,
        event_code="counseling.shared_summary.published",
        source_type="counseling_shared_summary",
        source_id=published.pk,
    )
    assert notification.policy == "MANDATORY_OPERATIONAL"
    assert notification.target_type == "COUNSELING_SHARED_SUMMARY"
    assert notification.target_id == published.pk
    assert marker not in notification.message
    assert EmailDelivery.objects.filter(notification=notification).exists()
    rendered = render_notification_email(notification.event_code)
    assert marker not in rendered.text_body
    assert marker not in rendered.html_body
    assert (
        Notification.objects.filter(
            recipient=student,
            event_code="counseling.shared_summary.published",
            source_id=published.pk,
        ).count()
        == 1
    )

    with pytest.raises(CounselingSharedSummaryAlreadyPublished):
        put_assigned_shared_summary(
            encounter_id=encounter.pk,
            counselor=counselor,
            content="Silent rewrite attempt",
        )


@pytest.mark.django_db
def test_student_visibility_is_published_only_paginated_and_historical():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    other_student = make_user("other-student@example.edu", "STUDENT")
    create_counseling_service(admin)
    encounter = make_encounter(counselor=counselor, student=student)
    summary = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content="Student-visible message",
    )

    student_client = auth_client(student)
    draft_list = student_client.get("/api/v1/counseling/me/shared-summaries?page=1&page_size=1")
    assert draft_list.status_code == 200
    assert draft_list.json() == {"items": [], "page": 1, "page_size": 1, "has_next": False}
    draft_detail = student_client.get(f"/api/v1/counseling/me/shared-summaries/{summary.pk}")
    assert draft_detail.status_code == 404

    publish_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        context=context(counselor),
    )
    published_list = student_client.get("/api/v1/counseling/me/shared-summaries?page=1&page_size=1")
    assert published_list.status_code == 200
    body = published_list.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["has_next"] is False
    assert len(body["items"]) == 1
    assert body["items"][0]["content"] == "Student-visible message"

    other_client = auth_client(other_student)
    other_detail = other_client.get(f"/api/v1/counseling/me/shared-summaries/{summary.pk}")
    assert other_detail.status_code == 404

    counselor.is_active = False
    counselor.save(update_fields=["is_active", "updated_at"])
    historical = student_client.get(f"/api/v1/counseling/me/shared-summaries/{summary.pk}")
    assert historical.status_code == 200
    assert historical.json()["content"] == "Student-visible message"


@pytest.mark.django_db
def test_authorization_requires_capability_and_actual_encounter_relationship():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    other = make_user("other@example.edu", "COUNSELOR")
    head = make_user("head@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    dpo = make_user("dpo@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    create_counseling_service(admin)
    encounter = make_encounter(counselor=counselor, student=student)
    summary = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content="Assigned only",
    )

    assert student.has_capability("shared_summaries.view_self")
    assert counselor.has_capability("shared_summaries.view_assigned")
    assert counselor.has_capability("shared_summaries.manage_assigned")
    assert head.has_capability("shared_summaries.view_assigned")
    assert not gss.has_capability("shared_summaries.view_assigned")
    assert not admin.has_capability("shared_summaries.view_assigned")
    assert not dpo.has_capability("shared_summaries.view_assigned")

    for actor in (other, head):
        response = auth_client(actor).get(
            f"/api/v1/counseling/encounters/{encounter.pk}/shared-summary"
        )
        assert response.status_code == 404

    for actor in (gss, admin, dpo):
        response = auth_client(actor).get(
            f"/api/v1/counseling/encounters/{encounter.pk}/shared-summary"
        )
        assert response.status_code == 403

    student_client = auth_client(student)
    student_response = student_client.put(
        f"/api/v1/counseling/encounters/{encounter.pk}/shared-summary",
        data=json.dumps({"content": "not allowed"}),
        content_type="application/json",
        **csrf(student_client),
    )
    assert student_response.status_code == 403

    counselor_client = auth_client(counselor)
    assigned = counselor_client.get(f"/api/v1/counseling/encounters/{encounter.pk}/shared-summary")
    assert assigned.status_code == 200
    assert assigned.json()["id"] == str(summary.pk)

    head_encounter = make_encounter(counselor=head, student=student)
    put_assigned_shared_summary(
        encounter_id=head_encounter.pk,
        counselor=head,
        content="Head as assigned counselor",
    )
    head_assigned = auth_client(head).get(
        f"/api/v1/counseling/encounters/{head_encounter.pk}/shared-summary"
    )
    assert head_assigned.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("delivery_mode", ["IN_PERSON", "ONLINE"])
def test_shared_summary_supports_both_delivery_modes_without_daily(delivery_mode):
    sync_policy()
    admin = make_user(f"admin-{delivery_mode.lower()}@example.edu", "IT_ADMIN")
    counselor = make_user(f"counselor-{delivery_mode.lower()}@example.edu", "COUNSELOR")
    student = make_user(f"student-{delivery_mode.lower()}@example.edu", "STUDENT")
    create_counseling_service(admin)
    encounter = make_encounter(
        counselor=counselor,
        student=student,
        mode=delivery_mode,
    )

    draft = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content=f"Visible after {delivery_mode} counseling",
    )
    published = publish_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        context=context(counselor),
    )

    assert draft.pk == published.pk
    assert published.encounter.delivery_mode == delivery_mode


@pytest.mark.django_db
def test_student_response_never_copies_routine_private_content():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")

    year = create_academic_year(label="2026-2027", context=context(admin))
    set_current_academic_year(academic_year_id=year.pk, context=context(admin))
    ensure_current_inventory(student=student, context=context(student))
    campus = Campus.objects.create(code="MAIN", name="Main Campus")
    college = College.objects.create(campus=campus, code="CCMS", name="CCMS")
    program = Program.objects.create(
        college=college,
        code="TEST-IS",
        name="Test Information Systems Program",
    )
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )
    submit_current_inventory(student=student, context=context(student))
    create_counseling_service(admin)

    routine = create_direct(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        idempotency_key="shared-summary-privacy-test",
        request_fingerprint="a" * 64,
        context=context(counselor),
    )
    replace_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        values={"coping_with_college_challenges": "PRIVATE STUDENT INTAKE"},
    )
    submit_my_intake(
        student=student,
        routine_interview_id=routine.pk,
        context=context(student),
    )
    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        values={
            "special_concern": "PRIVATE SPECIAL CONCERN",
            "recommendations": "PRIVATE RECOMMENDATION",
            "academic_adjustment_rating": 7,
        },
    )

    encounter = make_encounter(counselor=counselor, student=student)
    summary = put_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        content="Student-visible message",
    )
    publish_assigned_shared_summary(
        encounter_id=encounter.pk,
        counselor=counselor,
        context=context(counselor),
    )

    response = auth_client(student).get(f"/api/v1/counseling/me/shared-summaries/{summary.pk}")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "id",
        "content",
        "published_at",
        "counseling_ended_at",
        "delivery_mode",
    }
    assert payload["content"] == "Student-visible message"
    encoded = json.dumps(payload)
    assert "PRIVATE STUDENT INTAKE" not in encoded
    assert "PRIVATE SPECIAL CONCERN" not in encoded
    assert "PRIVATE RECOMMENDATION" not in encoded
    assert "academic_adjustment_rating" not in encoded
