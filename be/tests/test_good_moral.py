from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.documents.rendering import render_document_html
from compass.good_moral.models import GoodMoralRequest, GoodMoralStatus, GoodMoralVariant
from compass.good_moral import services as good_moral_services
from compass.good_moral.services import (
    GoodMoralConfigurationConflict,
    GoodMoralConflict,
    GoodMoralCreationConflict,
    GoodMoralCurrentStudentRequired,
    GoodMoralDocumentUnavailable,
    InvalidGoodMoralInput,
    build_certificate_render_context,
    cancel_request,
    create_my_current_student as create_my_current_student_service,
    create_my_graduate as create_my_graduate_service,
    get_mine,
    issue_request,
    list_mine,
    render_certificate_pdf,
    update_request,
)
from compass.institutional_forms.models import FormRevision
from compass.institutional_forms.services import activate_form_revision
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, Notification, NotificationPreference
from compass.organization.models import AcademicYear, Campus, College, StudentAffiliation


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    role: str = "STUDENT",
    *,
    lifecycle: str | None = None,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        last_name="User",
    )
    if lifecycle is not None:
        user.student_lifecycle_status = lifecycle
        user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def create_my_current_student(**kwargs):
    kwargs.setdefault("idempotency_key", f"good-moral-current-{uuid.uuid4()}")
    kwargs.setdefault("request_fingerprint", "0" * 64)
    return create_my_current_student_service(**kwargs)


def create_my_graduate(**kwargs):
    kwargs.setdefault("idempotency_key", f"good-moral-graduate-{uuid.uuid4()}")
    kwargs.setdefault("request_fingerprint", "1" * 64)
    return create_my_graduate_service(**kwargs)


def good_moral_create_headers(client: Client, key: str | None = None) -> dict[str, str]:
    return {
        **csrf(client),
        "HTTP_IDEMPOTENCY_KEY": key or f"good-moral-api-{uuid.uuid4()}",
    }


def make_affiliation(student: User, *, code: str = "CCMS") -> StudentAffiliation:
    campus, _ = Campus.objects.get_or_create(
        code="MAIN",
        defaults={"name": "Main Campus"},
    )
    college = College.objects.create(
        campus=campus,
        code=code,
        name=f"{code} College",
    )
    return StudentAffiliation.objects.create(student=student, college=college)


def make_academic_year(label: str = "2026-2027", *, current: bool = True) -> AcademicYear:
    return AcademicYear.objects.create(label=label, is_current=current)


def make_inventory(
    student: User,
    academic_year: AcademicYear,
    *,
    submitted: bool = True,
    course: str = "Bachelor of Science in Information Systems",
    major: str = "",
) -> StudentInventory:
    revision = FormRevision.objects.get(
        family__key="individual_inventory",
        status="ACTIVE",
    )
    return StudentInventory.objects.create(
        student=student,
        academic_year=academic_year,
        form_revision=revision,
        submitted_at=timezone.now() if submitted else None,
        course_currently_enrolled=course,
        major=major,
    )


def make_current_request(student: User) -> tuple[GoodMoralRequest, StudentInventory]:
    make_affiliation(student)
    academic_year = make_academic_year()
    inventory = make_inventory(
        student,
        academic_year,
        major="Information Systems",
    )
    item = create_my_current_student(
        student=student,
        year_level="Fourth",
        semester="First",
        context=AuditContext.user(student),
    )
    return item, inventory


def make_graduate_request(student: User) -> GoodMoralRequest:
    return create_my_graduate(
        student=student,
        degree="Bachelor of Science in Information Systems",
        major="Information Systems",
        graduation_date=date(2026, 6, 30),
        context=AuditContext.user(student),
    )


@pytest.mark.django_db
def test_f4_creation_uses_locked_current_student_exact_inventory_and_local_text_snapshots():
    sync_policy()
    student = make_user("current.student@example.edu")
    affiliation = make_affiliation(student)
    academic_year = make_academic_year()
    inventory = make_inventory(
        student,
        academic_year,
        course="BS Information Systems",
        major="Systems Development",
    )

    first = create_my_current_student(
        student=student,
        year_level="  Fifth  ",
        semester="  Special Term  ",
        context=AuditContext.user(student),
    )
    second = create_my_current_student(
        student=student,
        year_level="Fifth",
        semester="Special Term",
        context=AuditContext.user(student),
    )

    assert first.student_id == student.pk
    assert first.variant == GoodMoralVariant.CURRENT_STUDENT
    assert first.status == GoodMoralStatus.REQUESTED
    assert first.inventory_id == inventory.pk
    assert first.academic_year_id == inventory.academic_year_id
    assert first.applicant_name_snapshot == student.get_full_name()
    assert first.college_snapshot == affiliation.college.name
    assert first.course_snapshot == "BS Information Systems"
    assert first.major_snapshot == "Systems Development"
    assert first.year_level_snapshot == "Fifth"
    assert first.semester_snapshot == "Special Term"
    assert second.pk != first.pk
    assert GoodMoralRequest.objects.filter(student=student).count() == 2


@pytest.mark.django_db
def test_f4_uses_resolver_returned_inventory_academic_year_without_second_year_resolution(
    monkeypatch,
):
    sync_policy()
    student = make_user("resolver.student@example.edu")
    make_affiliation(student)
    current_year = make_academic_year("2026-2027", current=True)
    prior_year = make_academic_year("2025-2026", current=False)
    inventory = make_inventory(student, prior_year)

    monkeypatch.setattr(
        "compass.good_moral.services.require_current_submitted_inventory",
        lambda locked_student: inventory,
    )
    item = create_my_current_student(
        student=student,
        year_level="Fourth",
        semester="First",
        context=AuditContext.user(student),
    )

    assert current_year.is_current
    assert item.inventory_id == inventory.pk
    assert item.academic_year_id == prior_year.pk


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["no_current_year", "missing", "draft", "prior_only"])
def test_f4_inventory_prerequisite_failures_are_controlled_good_moral_409(case: str):
    sync_policy()
    student = make_user(f"{case}@example.edu")
    make_affiliation(student)
    revision = FormRevision.objects.get(family__key="individual_inventory", status="ACTIVE")

    if case != "no_current_year":
        current = make_academic_year()
        if case == "draft":
            StudentInventory.objects.create(
                student=student,
                academic_year=current,
                form_revision=revision,
            )
        elif case == "prior_only":
            prior = make_academic_year("2025-2026", current=False)
            StudentInventory.objects.create(
                student=student,
                academic_year=prior,
                form_revision=revision,
                submitted_at=timezone.now(),
            )

    client = auth_client(student)
    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "Fourth", "semester": "First"}),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "good_moral_inventory_required"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lifecycle",
    [StudentLifecycleStatus.GRADUATED, StudentLifecycleStatus.FORMER],
)
def test_f4_rejects_noncurrent_lifecycle_before_inventory_lookup(lifecycle: str):
    sync_policy()
    student = make_user("not.current@example.edu", lifecycle=lifecycle)
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "Fourth", "semester": "First"}),
        content_type="application/json",
        **good_moral_create_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "current_student_required"


@pytest.mark.django_db
def test_student_creation_schemas_do_not_accept_server_owned_good_moral_fields():
    sync_policy()
    student = make_user("strict.student@example.edu")
    client = auth_client(student)
    headers = good_moral_create_headers(client)

    f4 = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps(
            {
                "year_level": "Fourth",
                "semester": "First",
                "variant": "GRADUATE",
                "student_id": str(student.pk),
                "inventory_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000002",
                "official_receipt_number": "NOPE",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert f4.status_code == 422

    student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    f6 = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "BS Information Systems",
                "major": "",
                "graduation_date": "2026-06-30",
                "status": "ISSUED",
                "form_revision_id": "00000000-0000-0000-0000-000000000003",
                "issued_at": "2026-09-18T10:00:00+08:00",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert f6.status_code == 422


@pytest.mark.django_db
def test_graduate_f6_uses_same_student_account_without_current_context():
    sync_policy()
    student = make_user(
        "graduate.student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    before_users = User.objects.count()

    item = make_graduate_request(student)

    assert User.objects.count() == before_users
    assert item.student_id == student.pk
    assert item.variant == GoodMoralVariant.GRADUATE
    assert item.inventory_id is None
    assert item.academic_year_id is None
    assert item.degree_snapshot == "Bachelor of Science in Information Systems"
    assert item.major_snapshot == "Information Systems"
    assert item.graduation_date == date(2026, 6, 30)
    assert not Role.objects.filter(code="ALUMNI").exists()
    assert not apps.is_installed("compass.registrar")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lifecycle",
    [StudentLifecycleStatus.CURRENT, StudentLifecycleStatus.FORMER],
)
def test_f6_rejects_non_graduated_student(lifecycle: str):
    sync_policy()
    student = make_user("not.graduate@example.edu", lifecycle=lifecycle)
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "BS Information Systems",
                "major": "",
                "graduation_date": "2026-06-30",
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "graduated_student_required"


@pytest.mark.django_db
def test_historical_self_access_survives_lifecycle_changes_and_remains_owner_only():
    sync_policy()
    student = make_user(
        "history.student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    other = make_user("other.student@example.edu")
    item = make_graduate_request(student)

    student.student_lifecycle_status = StudentLifecycleStatus.FORMER
    student.save(update_fields=["student_lifecycle_status", "updated_at"])

    assert [row.pk for row in list_mine(student)] == [item.pk]
    assert get_mine(student=student, request_id=item.pk).pk == item.pk
    with pytest.raises(Exception) as exc_info:
        get_mine(student=other, request_id=item.pk)
    assert exc_info.type.__name__ == "GoodMoralNotFound"

    client = auth_client(student)
    response = client.get(f"/api/v1/good-moral/me/{item.pk}")
    assert response.status_code == 200
    assert response.json()["variant"] == "GRADUATE"


@pytest.mark.django_db
def test_structural_database_constraints_do_not_replace_issuance_completeness():
    sync_policy()
    student = make_user("constraints.student@example.edu")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            GoodMoralRequest.objects.create(
                student=student,
                variant=GoodMoralVariant.CURRENT_STUDENT,
                applicant_name_snapshot="Allowed to be incomplete while requested",
            )

    graduate = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.GRADUATE,
        applicant_name_snapshot="Incomplete Graduate",
        degree_snapshot="",
        graduation_date=None,
    )
    assert graduate.status == GoodMoralStatus.REQUESTED


@pytest.mark.django_db
def test_counselor_corrections_are_variant_local_private_and_locked_after_issue():
    sync_policy()
    student = make_user(
        "correction.student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)

    updated = update_request(
        actor=counselor,
        request_id=item.pk,
        changes={
            "degree_snapshot": "Bachelor of Science in Information Technology",
            "official_receipt_number": "OR-123",
            "official_receipt_amount": Decimal("250.00"),
        },
        context=AuditContext.user(counselor),
    )
    assert updated.degree_snapshot == "Bachelor of Science in Information Technology"
    assert updated.official_receipt_number == "OR-123"
    assert updated.official_receipt_amount == Decimal("250.00")

    event = AuditEvent.objects.filter(action="good_moral.request_updated").latest("occurred_at")
    assert event.metadata == {
        "variant": "GRADUATE",
        "changed_fields": [
            "degree_snapshot",
            "official_receipt_amount",
            "official_receipt_number",
        ],
    }
    assert "OR-123" not in json.dumps(event.metadata)

    with pytest.raises(InvalidGoodMoralInput):
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"course_snapshot": "Forbidden Graduate Field"},
            context=AuditContext.user(counselor),
        )
    with pytest.raises(InvalidGoodMoralInput):
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"official_receipt_amount": Decimal("-1.00")},
            context=AuditContext.user(counselor),
        )

    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    with pytest.raises(GoodMoralConflict):
        update_request(
            actor=counselor,
            request_id=issued.pk,
            changes={"degree_snapshot": "Cannot Change"},
            context=AuditContext.user(counselor),
        )


@pytest.mark.django_db
def test_f4_issue_rechecks_current_lifecycle_and_duplicate_issue_is_idempotent():
    sync_policy()
    student = make_user("issue.current@example.edu")
    counselor = make_user("issue.counselor@example.edu", role="COUNSELOR")
    item, inventory = make_current_request(student)

    student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    with pytest.raises(GoodMoralCurrentStudentRequired):
        issue_request(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
        )
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.inventory_id == inventory.pk
    assert not AuditEvent.objects.filter(action="good_moral.issued").exists()

    student.student_lifecycle_status = StudentLifecycleStatus.CURRENT
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    first_state = (
        issued.issued_at,
        issued.issued_by_id,
        issued.issued_by_name_snapshot,
        issued.form_revision_id,
        issued.document_template_key,
        issued.document_template_version,
    )
    assert issued.status == GoodMoralStatus.ISSUED
    assert issued.form_revision.family.key == "good_moral_current_student"
    assert issued.form_revision.official_code == "CNSC-OP-GCO-01F4"
    assert issued.form_revision.official_revision == "0"
    assert issued.document_template_key == "good_moral_current_student"
    assert issued.document_template_version == 1

    issued_notification = Notification.objects.get(
        recipient=student,
        event_code="good_moral.issued",
        source_type="good_moral_request",
        source_id=item.pk,
    )
    feedback_notification = Notification.objects.get(
        recipient=student,
        event_code="feedback.invitation",
        source_type="good_moral_request",
        source_id=item.pk,
    )
    assert issued_notification.policy == "MANDATORY_OPERATIONAL"
    assert issued_notification.target_type == "GOOD_MORAL"
    assert issued_notification.target_id == item.pk
    assert feedback_notification.policy == "OPTIONAL_INFORMATIONAL"
    assert feedback_notification.target_type == "FEEDBACK"
    assert feedback_notification.target_id is None
    assert EmailDelivery.objects.filter(notification=issued_notification).exists()
    assert EmailDelivery.objects.filter(notification=feedback_notification).exists()

    repeated = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    assert (
        repeated.issued_at,
        repeated.issued_by_id,
        repeated.issued_by_name_snapshot,
        repeated.form_revision_id,
        repeated.document_template_key,
        repeated.document_template_version,
    ) == first_state
    assert (
        AuditEvent.objects.filter(
            action="good_moral.issued",
            target_id=str(item.pk),
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(
            recipient=student,
            event_code="good_moral.issued",
            source_id=item.pk,
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(
            recipient=student,
            event_code="feedback.invitation",
            source_id=item.pk,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_feedback_invitation_email_respects_optional_preference_but_issuance_email_does_not():
    sync_policy()
    student = make_user("issue.preference@example.edu")
    counselor = make_user("issue.preference.counselor@example.edu", role="COUNSELOR")
    item, _inventory = make_current_request(student)
    NotificationPreference.objects.create(user=student, optional_email_enabled=False)

    issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )

    issued_notification = Notification.objects.get(
        recipient=student,
        event_code="good_moral.issued",
        source_id=item.pk,
    )
    feedback_notification = Notification.objects.get(
        recipient=student,
        event_code="feedback.invitation",
        source_id=item.pk,
    )
    assert EmailDelivery.objects.filter(notification=issued_notification).exists()
    assert not EmailDelivery.objects.filter(notification=feedback_notification).exists()


@pytest.mark.django_db
def test_good_moral_issuance_requires_active_supported_variant_revision():
    sync_policy()
    student = make_user(
        "unsupported.form@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("unsupported.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    revision = FormRevision.objects.get(
        family__key="good_moral_graduate",
        status="ACTIVE",
    )
    FormRevision.objects.filter(pk=revision.pk).update(internal_schema_version=999)

    with pytest.raises(GoodMoralConfigurationConflict):
        issue_request(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
        )
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.form_revision_id is None


@pytest.mark.django_db
def test_issue_api_requires_counselor_capability_and_recent_mfa():
    sync_policy()
    student = make_user(
        "mfa.student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("mfa.counselor@example.edu", role="COUNSELOR")
    gss = make_user("mfa.gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    admin = make_user("mfa.admin@example.edu", role="IT_ADMIN")
    dpo = make_user("mfa.dpo@example.edu", role="IT_ADMIN")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    item = make_graduate_request(student)

    stale = auth_client(counselor)
    response = stale.post(
        f"/api/v1/good-moral/requests/{item.pk}/issue",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(stale),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "recent_mfa_required"

    for user in (student, gss, admin, dpo):
        client = auth_client(user, recent_mfa=True)
        denied = client.post(
            f"/api/v1/good-moral/requests/{item.pk}/issue",
            data=json.dumps({}),
            content_type="application/json",
            **csrf(client),
        )
        assert denied.status_code == 403

    fresh = auth_client(counselor, recent_mfa=True)
    issued = fresh.post(
        f"/api/v1/good-moral/requests/{item.pk}/issue",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(fresh),
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "ISSUED"


@pytest.mark.django_db
def test_saved_render_provenance_drives_html_after_current_data_and_revision_change():
    sync_policy()
    student = make_user("render.student@example.edu")
    counselor = make_user("render.counselor@example.edu", role="COUNSELOR")
    item, inventory = make_current_request(student)
    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    saved_revision_id = issued.form_revision_id
    saved_name = issued.applicant_name_snapshot
    saved_course = issued.course_snapshot

    student.first_name = "Changed"
    student.save(update_fields=["first_name", "updated_at"])
    inventory.course_currently_enrolled = "Changed Course"
    inventory.save(update_fields=["course_currently_enrolled", "updated_at"])

    future_revision = FormRevision.objects.create(
        family=issued.form_revision.family,
        official_code="CNSC-OP-GCO-01F4",
        official_revision="1",
        internal_schema_version=1,
        status="INACTIVE",
    )
    activate_form_revision(
        revision_id=future_revision.pk,
        context=AuditContext.system(),
    )

    issued = GoodMoralRequest.objects.select_related(
        "academic_year",
        "form_revision",
        "form_revision__family",
    ).get(pk=item.pk)
    assert issued.form_revision_id == saved_revision_id
    assert issued.applicant_name_snapshot == saved_name
    assert issued.course_snapshot == saved_course

    context = build_certificate_render_context(issued)
    html, spec = render_document_html(
        issued.document_template_key,
        issued.document_template_version,
        context=context,
    )
    assert spec.show_page_numbers is False
    assert "University of Camarines Norte" in html
    assert "GOOD MORAL CHARACTER" in html
    assert saved_name in html
    assert saved_course in html
    assert "Changed Course" not in html
    assert "CNSC-OP-GCO-01F4" in html
    assert "Revision: 0" in html
    assert "Page 1 of 1" in html


@pytest.mark.django_db
def test_pdf_endpoints_require_issued_state_and_use_safe_pdf_response(monkeypatch):
    sync_policy()
    student = make_user(
        "pdf.student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("pdf.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    client = auth_client(student)

    pending = client.get(f"/api/v1/good-moral/me/{item.pk}/pdf")
    assert pending.status_code == 409

    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    fake_pdf = b"%PDF-" + (b"x" * 2048)
    monkeypatch.setattr(
        "compass.good_moral.api.render_certificate_pdf",
        lambda requested: fake_pdf,
    )

    response = client.get(f"/api/v1/good-moral/me/{issued.pk}/pdf")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content == fake_pdf
    assert response["Content-Disposition"] == (f'attachment; filename="good-moral-{issued.pk}.pdf"')


@pytest.mark.django_db
def test_saved_missing_template_fails_closed_instead_of_switching_versions():
    sync_policy()
    student = make_user(
        "missing.template@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("template.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )

    GoodMoralRequest.objects.filter(pk=issued.pk).update(
        document_template_key="missing_historical_template"
    )
    issued = GoodMoralRequest.objects.select_related(
        "academic_year",
        "form_revision",
    ).get(pk=issued.pk)
    with pytest.raises(GoodMoralDocumentUnavailable):
        render_certificate_pdf(issued)


@pytest.mark.django_db
def test_real_chromium_smoke_renders_issued_graduate_certificate():
    sync_policy()
    student = make_user(
        "chromium.student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("chromium.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )

    pdf = render_certificate_pdf(issued)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1024


@pytest.mark.django_db
def test_good_moral_operational_list_supports_student_filter_and_safe_identity_search():
    sync_policy()
    counselor = make_user("good-moral-search-counselor@example.edu", role="COUNSELOR")
    alpha = make_user(
        "good-moral-alpha@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    beta = make_user(
        "good-moral-beta@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    alpha.institutional_id = "GM-ALPHA-001"
    beta.institutional_id = "GM-BETA-001"
    alpha.save(update_fields=["institutional_id", "updated_at"])
    beta.save(update_fields=["institutional_id", "updated_at"])
    alpha_request = make_graduate_request(alpha)
    make_graduate_request(beta)

    client = auth_client(counselor)
    searched = client.get("/api/v1/good-moral/requests", {"search": "GM-ALPHA-001"})
    assert searched.status_code == 200
    assert [row["id"] for row in searched.json()["items"]] == [str(alpha_request.pk)]

    filtered = client.get(
        "/api/v1/good-moral/requests",
        {"student_id": str(alpha.pk), "status": "REQUESTED"},
    )
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == [str(alpha_request.pk)]

    assert (
        client.get(
            "/api/v1/good-moral/requests",
            {"search": "x" * 161},
        ).status_code
        == 422
    )


@pytest.mark.django_db
def test_f4_persistent_replay_precedes_lifecycle_inventory_affiliation_and_snapshot_refresh(
    monkeypatch,
):
    sync_policy()
    student = make_user("idem-f4@example.edu")
    affiliation = make_affiliation(student, code="F4IDEM")
    academic_year = make_academic_year()
    inventory = make_inventory(
        student,
        academic_year,
        course="Original Course",
        major="Original Major",
    )
    client = auth_client(student)
    payload = {"year_level": "Fourth Year", "semester": "First Semester"}
    key = "gm-f4-1"

    first = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert first.status_code == 201
    request_id = first.json()["id"]
    item = GoodMoralRequest.objects.get(pk=request_id)
    assert item.variant == GoodMoralVariant.CURRENT_STUDENT
    assert item.creation_key_digest
    assert len(item.creation_key_digest) == 64
    assert item.creation_key_digest != key
    assert len(item.creation_request_fingerprint) == 64
    assert set(item.creation_request_fingerprint) <= set("0123456789abcdef")
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=str(item.pk),
        ).count()
        == 1
    )

    original = {
        "inventory_id": item.inventory_id,
        "academic_year_id": item.academic_year_id,
        "applicant_name": item.applicant_name_snapshot,
        "college": item.college_snapshot,
        "course": item.course_snapshot,
        "major": item.major_snapshot,
        "year_level": item.year_level_snapshot,
        "semester": item.semester_snapshot,
    }

    student.first_name = "Changed"
    student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    student.save(update_fields=["first_name", "student_lifecycle_status", "updated_at"])
    inventory.course_currently_enrolled = "Changed Course"
    inventory.major = "Changed Major"
    inventory.save(update_fields=["course_currently_enrolled", "major", "updated_at"])
    affiliation.college.name = "Changed College"
    affiliation.college.save(update_fields=["name", "updated_at"])

    def fail_inventory(_student):
        raise AssertionError("exact replay must not resolve current Inventory")

    def fail_affiliation(_student):
        raise AssertionError("exact replay must not resolve current affiliation")

    monkeypatch.setattr(
        "compass.good_moral.services.require_current_submitted_inventory",
        fail_inventory,
    )
    monkeypatch.setattr(
        "compass.good_moral.services._current_affiliation",
        fail_affiliation,
    )

    replay = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == request_id
    item.refresh_from_db()
    assert {
        "inventory_id": item.inventory_id,
        "academic_year_id": item.academic_year_id,
        "applicant_name": item.applicant_name_snapshot,
        "college": item.college_snapshot,
        "course": item.course_snapshot,
        "major": item.major_snapshot,
        "year_level": item.year_level_snapshot,
        "semester": item.semester_snapshot,
    } == original
    assert GoodMoralRequest.objects.filter(student=student).count() == 1
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=str(item.pk),
        ).count()
        == 1
    )

    new_intent = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, "gm-f4-new-intent"),
    )
    assert new_intent.status_code == 409
    assert new_intent.json()["error"]["code"] == "current_student_required"


@pytest.mark.django_db
def test_f6_persistent_replay_precedes_lifecycle_and_profile_refresh():
    sync_policy()
    student = make_user(
        "idem-f6@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    client = auth_client(student)
    payload = {
        "degree": "Bachelor of Science in Information Systems",
        "major": "Information Systems",
        "graduation_date": "2026-06-30",
    }
    key = "gm-f6-1"

    first = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert first.status_code == 201
    request_id = first.json()["id"]
    item = GoodMoralRequest.objects.get(pk=request_id)
    saved_name = item.applicant_name_snapshot
    assert item.variant == GoodMoralVariant.GRADUATE
    assert item.inventory_id is None
    assert item.academic_year_id is None
    assert item.creation_key_digest
    assert item.creation_request_fingerprint
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=str(item.pk),
        ).count()
        == 1
    )

    student.first_name = "Changed"
    student.student_lifecycle_status = StudentLifecycleStatus.FORMER
    student.save(update_fields=["first_name", "student_lifecycle_status", "updated_at"])

    replay = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == request_id
    assert replay.json()["applicant_name"] == saved_name
    assert GoodMoralRequest.objects.filter(student=student).count() == 1
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=str(item.pk),
        ).count()
        == 1
    )

    new_intent = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, "gm-f6-new-intent"),
    )
    assert new_intent.status_code == 409
    assert new_intent.json()["error"]["code"] == "graduated_student_required"


@pytest.mark.django_db
def test_same_good_moral_key_changed_body_and_cross_variant_conflict():
    sync_policy()
    current = make_user("same-key-current@example.edu")
    make_affiliation(current, code="SAMEKEY")
    make_inventory(current, make_academic_year(), course="BSIS")
    client = auth_client(current)
    key = "gm-shared-intent"

    first = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "Fourth", "semester": "First"}),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert first.status_code == 201

    changed = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "Fourth", "semester": "Second"}),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "good_moral_conflict"

    current.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    current.save(update_fields=["student_lifecycle_status", "updated_at"])
    cross_variant = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "BS Information Systems",
                "major": "",
                "graduation_date": "2026-06-30",
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert cross_variant.status_code == 409
    assert cross_variant.json()["error"]["code"] == "good_moral_conflict"
    assert GoodMoralRequest.objects.filter(student=current).count() == 1

    graduate = make_user(
        "same-key-graduate@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    graduate_client = auth_client(graduate)
    graduate_key = "gm-graduate-change"
    graduate_payload = {
        "degree": "BS Information Systems",
        "major": "",
        "graduation_date": "2026-06-30",
    }
    assert (
        graduate_client.post(
            "/api/v1/good-moral/me/requests/graduate",
            data=json.dumps(graduate_payload),
            content_type="application/json",
            **good_moral_create_headers(graduate_client, graduate_key),
        ).status_code
        == 201
    )
    graduate_changed = graduate_client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps({**graduate_payload, "degree": "BS Information Technology"}),
        content_type="application/json",
        **good_moral_create_headers(graduate_client, graduate_key),
    )
    assert graduate_changed.status_code == 409
    assert graduate_changed.json()["error"]["code"] == "good_moral_conflict"
    assert GoodMoralRequest.objects.filter(student=graduate).count() == 1


@pytest.mark.django_db
def test_same_raw_key_is_actor_scoped_and_new_key_preserves_multiple_legitimate_requests():
    sync_policy()
    first_student = make_user(
        "actor-scope-a@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    second_student = make_user(
        "actor-scope-b@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    payload = {
        "degree": "BS Information Systems",
        "major": "",
        "graduation_date": "2026-06-30",
    }
    raw_key = "student-local-intent"

    responses = []
    for student in (first_student, second_student):
        client = auth_client(student)
        response = client.post(
            "/api/v1/good-moral/me/requests/graduate",
            data=json.dumps(payload),
            content_type="application/json",
            **good_moral_create_headers(client, raw_key),
        )
        assert response.status_code == 201
        responses.append(response.json()["id"])

    first_request = GoodMoralRequest.objects.get(pk=responses[0])
    second_request = GoodMoralRequest.objects.get(pk=responses[1])
    assert first_request.creation_key_digest != second_request.creation_key_digest

    first_client = auth_client(first_student)
    another = first_client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(first_client, "student-local-second-intent"),
    )
    assert another.status_code == 201
    assert another.json()["id"] != responses[0]
    assert GoodMoralRequest.objects.filter(student=first_student).count() == 2
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id__in=[str(responses[0]), str(another.json()["id"])],
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_create_replay_returns_current_cancelled_and_issued_resource_state():
    sync_policy()
    cancelled_student = make_user(
        "replay-cancelled@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    cancelled_client = auth_client(cancelled_student)
    payload = {
        "degree": "BS Information Systems",
        "major": "",
        "graduation_date": "2026-06-30",
    }
    cancelled_key = "gm-replay-cancelled"
    created = cancelled_client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(cancelled_client, cancelled_key),
    )
    assert created.status_code == 201
    cancelled_id = created.json()["id"]
    cancel_request(
        actor=cancelled_student,
        request_id=uuid.UUID(cancelled_id),
        reason="No longer needed",
        self_service=True,
        context=AuditContext.user(cancelled_student),
    )
    replay_cancelled = cancelled_client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(cancelled_client, cancelled_key),
    )
    assert replay_cancelled.status_code == 201
    assert replay_cancelled.json()["id"] == cancelled_id
    assert replay_cancelled.json()["status"] == GoodMoralStatus.CANCELLED
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=cancelled_id,
        ).count()
        == 1
    )

    issued_student = make_user(
        "replay-issued@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("replay-issued-counselor@example.edu", role="COUNSELOR")
    issued_client = auth_client(issued_student)
    issued_key = "gm-replay-issued"
    created_issued = issued_client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(issued_client, issued_key),
    )
    assert created_issued.status_code == 201
    issued_id = created_issued.json()["id"]
    issue_request(
        actor=counselor,
        request_id=uuid.UUID(issued_id),
        context=AuditContext.user(counselor),
    )
    notification_count = Notification.objects.filter(
        source_type="good_moral_request",
        source_id=uuid.UUID(issued_id),
    ).count()

    replay_issued = issued_client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(issued_client, issued_key),
    )
    assert replay_issued.status_code == 201
    assert replay_issued.json()["id"] == issued_id
    assert replay_issued.json()["status"] == GoodMoralStatus.ISSUED
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=issued_id,
        ).count()
        == 1
    )
    assert (
        AuditEvent.objects.filter(
            action="good_moral.issued",
            target_id=issued_id,
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(
            source_type="good_moral_request",
            source_id=uuid.UUID(issued_id),
        ).count()
        == notification_count
    )


@pytest.mark.django_db
def test_good_moral_idempotency_key_validation_missing_header_and_privacy():
    sync_policy()
    student = make_user(
        "key-validation@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    client = auth_client(student)
    payload = {
        "degree": "BS Information Systems",
        "major": "",
        "graduation_date": "2026-06-30",
    }

    missing = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )
    assert missing.status_code == 422
    assert GoodMoralRequest.objects.count() == 0

    for index, invalid_key in enumerate(
        (" bad-key ", "x" * 256),
        start=1,
    ):
        response = client.post(
            "/api/v1/good-moral/me/requests/graduate",
            data=json.dumps(payload),
            content_type="application/json",
            **good_moral_create_headers(client, invalid_key),
        )
        assert response.status_code == 422, index
        assert response.json()["error"]["code"] == "invalid_good_moral_request"
    assert GoodMoralRequest.objects.count() == 0

    with pytest.raises(InvalidGoodMoralInput):
        create_my_graduate_service(
            student=student,
            degree="BS Information Systems",
            major="",
            graduation_date=date(2026, 6, 30),
            idempotency_key="good-key",
            request_fingerprint="NOT-A-SHA256",
            context=AuditContext.user(student),
        )

    raw_key = "raw-good-moral-key-must-not-persist"
    success = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(payload),
        content_type="application/json",
        **good_moral_create_headers(client, raw_key),
    )
    assert success.status_code == 201
    item = GoodMoralRequest.objects.get(pk=success.json()["id"])
    assert raw_key not in str(item.__dict__)
    assert "creation_key" not in json.dumps(success.json())
    assert "fingerprint" not in json.dumps(success.json())
    event = AuditEvent.objects.get(
        action="good_moral.request_created",
        target_id=str(item.pk),
    )
    assert event.metadata == {
        "variant": GoodMoralVariant.GRADUATE,
        "transition": "NONE -> REQUESTED",
    }
    assert raw_key not in json.dumps(event.metadata)
    assert "creation" not in json.dumps(event.metadata).lower()


@pytest.mark.django_db
def test_historical_null_creation_identity_rows_keep_existing_workflows(monkeypatch):
    sync_policy()
    student = make_user(
        "historical-null@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("historical-null-counselor@example.edu", role="COUNSELOR")

    correctable = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.GRADUATE,
        applicant_name_snapshot=student.get_full_name(),
        degree_snapshot="BS Information Systems",
        major_snapshot="",
        graduation_date=date(2026, 6, 30),
    )
    assert correctable.creation_key_digest is None
    assert correctable.creation_request_fingerprint is None
    assert get_mine(student=student, request_id=correctable.pk).pk == correctable.pk
    assert [item.pk for item in list_mine(student)] == [correctable.pk]

    updated = update_request(
        actor=counselor,
        request_id=correctable.pk,
        changes={"degree_snapshot": "BS Information Technology"},
        context=AuditContext.user(counselor),
    )
    assert updated.degree_snapshot == "BS Information Technology"
    cancelled = cancel_request(
        actor=student,
        request_id=correctable.pk,
        reason="Historical cancellation",
        self_service=True,
        context=AuditContext.user(student),
    )
    assert cancelled.status == GoodMoralStatus.CANCELLED
    assert cancelled.creation_key_digest is None

    issuable = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.GRADUATE,
        applicant_name_snapshot=student.get_full_name(),
        degree_snapshot="BS Information Systems",
        major_snapshot="",
        graduation_date=date(2026, 6, 30),
    )
    issued = issue_request(
        actor=counselor,
        request_id=issuable.pk,
        context=AuditContext.user(counselor),
    )
    assert issued.status == GoodMoralStatus.ISSUED
    assert issued.creation_key_digest is None
    assert issued.creation_request_fingerprint is None

    fake_pdf = b"%PDF-" + b"x" * 2048
    monkeypatch.setattr(
        "compass.good_moral.api.render_certificate_pdf",
        lambda requested: fake_pdf,
    )
    response = auth_client(student).get(f"/api/v1/good-moral/me/{issued.pk}/pdf")
    assert response.status_code == 200
    assert response.content == fake_pdf


@pytest.mark.django_db
def test_unique_creation_digest_race_recovers_existing_resource_without_raw_integrity_error(
    monkeypatch,
):
    sync_policy()
    student = make_user(
        "race-recovery@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    key = "gm-race-key"
    fingerprint = "2" * 64
    existing = create_my_graduate_service(
        student=student,
        degree="BS Information Systems",
        major="",
        graduation_date=date(2026, 6, 30),
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=AuditContext.user(student),
    )

    original_lookup = good_moral_services._existing_creation_locked
    calls = {"count": 0}

    def hide_first_lookup(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original_lookup(**kwargs)

    monkeypatch.setattr(
        good_moral_services,
        "_existing_creation_locked",
        hide_first_lookup,
    )
    recovered = create_my_graduate_service(
        student=student,
        degree="BS Information Systems",
        major="",
        graduation_date=date(2026, 6, 30),
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=AuditContext.user(student),
    )
    assert recovered.pk == existing.pk
    assert GoodMoralRequest.objects.filter(student=student).count() == 1
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request_created",
            target_id=str(existing.pk),
        ).count()
        == 1
    )

    calls["count"] = 0
    with pytest.raises(GoodMoralCreationConflict):
        create_my_graduate_service(
            student=student,
            degree="BS Information Technology",
            major="",
            graduation_date=date(2026, 6, 30),
            idempotency_key=key,
            request_fingerprint="3" * 64,
            context=AuditContext.user(student),
        )
    assert GoodMoralRequest.objects.filter(student=student).count() == 1

