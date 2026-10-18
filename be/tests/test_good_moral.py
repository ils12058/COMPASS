from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.utils import timezone
from pypdf import PdfReader

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
from compass.common.institutional_time import institution_today
from compass.documents.rendering import render_document_html
from compass.feedback.models import (
    CustomerFeedbackService,
    FeedbackOpportunity,
    FeedbackOpportunitySourceType,
)
from compass.good_moral import services as good_moral_services
from compass.good_moral.models import (
    CANONICAL_SEMESTERS,
    CANONICAL_YEAR_LEVELS,
    GoodMoralRequest,
    GoodMoralStatus,
    GoodMoralVariant,
)
from compass.good_moral.services import (
    GoodMoralCertificateDateInFuture,
    GoodMoralConfigurationConflict,
    GoodMoralConflict,
    GoodMoralCreationConflict,
    GoodMoralCurrentStudentRequired,
    GoodMoralDocumentUnavailable,
    InvalidGoodMoralInput,
    build_certificate_render_context,
    cancel_request,
    get_mine,
    issue_request,
    list_mine,
    prepare_request,
    render_certificate_pdf,
    update_request,
)
from compass.good_moral.services import (
    create_my_current_student as create_my_current_student_service,
)
from compass.good_moral.services import (
    create_my_graduate as create_my_graduate_service,
)
from compass.institutional_forms.bootstrap import sync_institutional_forms
from compass.institutional_forms.models import FormRevision
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, Notification, NotificationPreference
from compass.organization.canonical import canonical_program_metadata
from compass.organization.models import AcademicYear, Campus, College, Program, StudentAffiliation
from tests.inventory_encryption_helpers import create_inventory_row


def prepare_and_issue(**kwargs):
    item = GoodMoralRequest.objects.get(pk=kwargs["request_id"])
    if item.status == GoodMoralStatus.REQUESTED:
        prepare_request(actor=kwargs["actor"], request_id=item.pk, context=kwargs["context"])
    return issue_request(**kwargs)


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
    college, _ = College.objects.get_or_create(
        campus=campus,
        code=code,
        defaults={"name": f"{code} College"},
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
    year_level: int | None = 4,
    program_code: str | None = "BSIS",
    program_college_code: str = "CCMS",
) -> StudentInventory:
    revision = FormRevision.objects.get(
        family__key="individual_inventory",
        status="ACTIVE",
    )
    program = None
    if program_code is not None:
        metadata = canonical_program_metadata("MAIN", program_college_code, program_code)
        assert metadata is not None
        campus, _ = Campus.objects.get_or_create(code="MAIN", defaults={"name": "Main Campus"})
        college, _ = College.objects.get_or_create(
            campus=campus,
            code=program_college_code,
            defaults={"name": f"{program_college_code} College"},
        )
        program, _ = Program.objects.get_or_create(
            college=college,
            code=program_code,
            defaults={"name": metadata.name},
        )
    return create_inventory_row(
        StudentInventory,
        student=student,
        academic_year=academic_year,
        form_revision=revision,
        program=program,
        year_level=year_level,
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
        year_level="4th Year",
        semester="First Semester",
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
def test_f4_creation_uses_locked_current_student_inventory_year_and_local_text_snapshots():
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
        year_level="  4th Year  ",
        semester="  First Semester  ",
        context=AuditContext.user(student),
    )
    second = create_my_current_student(
        student=student,
        year_level="4th Year",
        semester="First Semester",
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
    assert first.year_level_snapshot == "4th Year"
    assert first.semester_snapshot == "First Semester"
    assert second.pk != first.pk
    assert GoodMoralRequest.objects.filter(student=student).count() == 2


@pytest.mark.django_db
def test_f4_year_level_is_derived_from_inventory_and_explicit_mismatch_is_rejected():
    sync_policy()
    student = make_user("inventory.year.level@example.edu")
    make_affiliation(student)
    make_inventory(student, make_academic_year(), year_level=2)
    client = auth_client(student)

    mismatch = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "4th Year", "semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client, "gm-f4-level-mismatch"),
    )
    assert mismatch.status_code == 422
    assert (
        "must match the Year Level on the submitted Individual Inventory"
        in mismatch.json()["error"]["message"]
    )

    derived = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client, "gm-f4-level-derived"),
    )
    assert derived.status_code == 201
    assert derived.json()["year_level"] == "2nd Year"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("program_code", "college_code", "inventory_year", "expected_status"),
    [
        ("MIT", "CCMS", 1, "POSTGRADUATE_PROGRAM"),
        ("MBA", "GS", None, "POSTGRADUATE_PROGRAM"),
        ("DBA", "GS", None, "POSTGRADUATE_PROGRAM"),
        (None, "CCMS", 4, "UNCLASSIFIED_PROGRAM"),
        ("BSIS", "CCMS", 5, "UNSUPPORTED_YEAR_LEVEL"),
    ],
)
def test_f4_rejects_postgraduate_unclassified_and_unsupported_inventory_facts(
    program_code, college_code, inventory_year, expected_status
):
    sync_policy()
    student = make_user(f"f4-{expected_status.lower()}-{program_code}@example.edu")
    make_affiliation(student)
    make_inventory(
        student,
        make_academic_year(),
        year_level=inventory_year,
        program_code=program_code,
        program_college_code=college_code,
    )
    client = auth_client(student)

    context = client.get("/api/v1/good-moral/me/academic-context")
    assert context.status_code == 200
    assert context.json()["status"] == expected_status
    assert set(context.json()) == {"status", "academic_classification", "year_level"}

    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "good_moral_f4_academic_eligibility_required"
    assert not GoodMoralRequest.objects.filter(student=student).exists()


@pytest.mark.django_db
def test_degree_suggestions_are_bachelor_only_and_capability_scoped():
    sync_policy()
    student = make_user(
        "degree-suggestions.student@example.edu", lifecycle=StudentLifecycleStatus.CURRENT
    )
    counselor = make_user("degree-suggestions.counselor@example.edu", role="COUNSELOR")
    staff = make_user("degree-suggestions.gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    it_user = make_user("degree-suggestions.it@example.edu", role="IT_ADMIN")

    response = auth_client(student).get("/api/v1/good-moral/degree-options")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items == sorted(set(items))
    assert "Bachelor of Science in Information Systems" in items
    assert "Master in Information Technology" not in items
    assert "Master in Business Administration" not in items
    assert "Doctor in Business Administration" not in items
    assert auth_client(counselor).get("/api/v1/good-moral/degree-options").status_code == 200
    assert auth_client(staff).get("/api/v1/good-moral/degree-options").status_code == 200
    assert auth_client(it_user).get("/api/v1/good-moral/degree-options").status_code == 403


@pytest.mark.django_db
def test_f4_academic_context_is_student_self_service_only():
    sync_policy()
    student = make_user("f4-context.student@example.edu")
    counselor = make_user("f4-context.counselor@example.edu", role="COUNSELOR")
    staff = make_user("f4-context.gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    it_user = make_user("f4-context.it@example.edu", role="IT_ADMIN")

    assert auth_client(student).get("/api/v1/good-moral/me/academic-context").status_code == 200
    for actor in (counselor, staff, it_user):
        assert auth_client(actor).get("/api/v1/good-moral/me/academic-context").status_code == 403


@pytest.mark.django_db
def test_f4_uses_submitted_inventory_for_current_academic_year():
    sync_policy()
    student = make_user("resolver.student@example.edu")
    make_affiliation(student)
    current_year = make_academic_year("2026-2027", current=True)
    prior_year = make_academic_year("2025-2026", current=False)
    inventory = make_inventory(student, current_year)
    make_inventory(student, prior_year)
    item = create_my_current_student(
        student=student,
        year_level="4th Year",
        semester="First Semester",
        context=AuditContext.user(student),
    )

    assert current_year.is_current
    assert item.inventory_id == inventory.pk
    assert item.academic_year_id == current_year.pk


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
            create_inventory_row(
                StudentInventory,
                student=student,
                academic_year=current,
                form_revision=revision,
            )
        elif case == "prior_only":
            prior = make_academic_year("2025-2026", current=False)
            create_inventory_row(
                StudentInventory,
                student=student,
                academic_year=prior,
                form_revision=revision,
                submitted_at=timezone.now(),
            )

    client = auth_client(student)
    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "4th Year", "semester": "First Semester"}),
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
        data=json.dumps({"year_level": "4th Year", "semester": "First Semester"}),
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
                "year_level": "4th Year",
                "semester": "First Semester",
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
def test_f6_claim_submission_is_not_blocked_by_lifecycle_alone(lifecycle: str):
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

    assert response.status_code == 201
    assert response.json()["degree"] == "BS Information Systems"


@pytest.mark.django_db
def test_f6_ucn_undergraduate_claim_remains_available_during_local_postgraduate_reenrollment():
    sync_policy()
    student = make_user(
        "local-postgraduate-alumnus@example.edu", lifecycle=StudentLifecycleStatus.CURRENT
    )
    make_affiliation(student)
    make_inventory(
        student,
        make_academic_year(),
        program_code="MIT",
        program_college_code="CCMS",
        year_level=None,
    )
    client = auth_client(student)

    assert (
        client.get("/api/v1/good-moral/me/academic-context").json()["status"]
        == "POSTGRADUATE_PROGRAM"
    )
    f4 = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client, "local-postgraduate-f4"),
    )
    assert f4.status_code == 409

    f6 = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "Bachelor of Science in Information Systems",
                "major": "Systems Development",
                "graduation_date": "2020-06-30",
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client, "local-postgraduate-f6"),
    )
    assert f6.status_code == 201
    item = GoodMoralRequest.objects.get(pk=f6.json()["id"])
    assert item.student_id == student.pk
    assert item.variant == GoodMoralVariant.GRADUATE
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.inventory_id is None
    assert item.degree_snapshot == "Bachelor of Science in Information Systems"
    assert item.prepared_at is None and item.issued_at is None


@pytest.mark.django_db
def test_ucn_postgraduate_record_does_not_verify_reported_external_bachelor_qualification():
    sync_policy()
    student = make_user(
        "external-degree-claim@example.edu", lifecycle=StudentLifecycleStatus.CURRENT
    )
    make_affiliation(student)
    make_inventory(
        student,
        make_academic_year(),
        program_code="MIT",
        program_college_code="CCMS",
        year_level=None,
    )
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "Bachelor of Science completed at another institution",
                "major": "Computing",
                "graduation_date": "2021-06-30",
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert response.status_code == 201
    item = GoodMoralRequest.objects.get(pk=response.json()["id"])
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.inventory_id is None
    assert item.degree_snapshot == "Bachelor of Science completed at another institution"
    assert item.prepared_at is None and item.issued_at is None


@pytest.mark.django_db
def test_ucn_bachelor_alumnus_can_request_f6_while_pursuing_postgraduate_studies_elsewhere():
    sync_policy()
    # External postgraduate enrollment is not represented in COMPASS; FORMER is the account's
    # recorded UCN lifecycle state. This keeps historical self-service access without treating
    # the degree text or lifecycle state as verified graduation evidence.
    student = make_user(
        "external-postgraduate-alumnus@example.edu", lifecycle=StudentLifecycleStatus.FORMER
    )
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "Bachelor of Science in Information Systems (UCN)",
                "major": "Systems Development",
                "graduation_date": "2020-06-30",
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client),
    )

    assert response.status_code == 201
    item = GoodMoralRequest.objects.get(pk=response.json()["id"])
    assert item.student_id == student.pk
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.inventory_id is None
    assert item.degree_snapshot == "Bachelor of Science in Information Systems (UCN)"
    assert item.prepared_at is None and item.issued_at is None


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

    issued = prepare_and_issue(
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
def test_graduation_date_on_request_creation_may_be_historical_but_not_future():
    sync_policy()
    student = make_user("dated.graduate@example.edu", lifecycle=StudentLifecycleStatus.GRADUATED)
    today = institution_today()

    def create(graduation_date):
        return create_my_graduate(
            student=student,
            degree="Bachelor of Arts in Psychology",
            major="",
            graduation_date=graduation_date,
            context=AuditContext.user(student),
        )

    before = timezone.now()
    historical = create(date(2019, 4, 12))
    assert historical.graduation_date == date(2019, 4, 12)
    # The request records when it entered COMPASS, not when the Student graduated.
    assert historical.created_at >= before
    assert create(today).graduation_date == today
    with pytest.raises(InvalidGoodMoralInput, match="graduation_date must not be in the future"):
        create(today + timedelta(days=1))

    client = auth_client(student)
    response = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "Bachelor of Arts in Psychology",
                "graduation_date": (today + timedelta(days=1)).isoformat(),
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_good_moral_request"
    assert GoodMoralRequest.objects.filter(student=student).count() == 2


@pytest.mark.django_db
def test_corrections_reject_future_graduation_and_receipt_dates_but_keep_historical_ones():
    sync_policy()
    student = make_user("dated.correction@example.edu", lifecycle=StudentLifecycleStatus.GRADUATED)
    counselor = make_user("dated.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    today = institution_today()
    tomorrow = today + timedelta(days=1)

    def correct(**changes):
        return update_request(
            actor=counselor,
            request_id=item.pk,
            changes=changes,
            context=AuditContext.user(counselor),
        )

    with pytest.raises(InvalidGoodMoralInput, match="graduation_date must not be in the future"):
        correct(graduation_date=tomorrow)
    with pytest.raises(
        InvalidGoodMoralInput, match="official_receipt_date must not be in the future"
    ):
        correct(official_receipt_date=tomorrow)
    item.refresh_from_db()
    assert item.graduation_date == date(2026, 6, 30)
    assert item.official_receipt_date is None

    assert correct(graduation_date=date(2018, 3, 28)).graduation_date == date(2018, 3, 28)
    assert correct(graduation_date=today).graduation_date == today
    assert correct(official_receipt_date=date(2025, 1, 6)).official_receipt_date == date(2025, 1, 6)
    assert correct(official_receipt_date=today).official_receipt_date == today
    assert correct(official_receipt_date=None).official_receipt_date is None

    # A stored date is not re-judged when another field is corrected.
    GoodMoralRequest.objects.filter(pk=item.pk).update(graduation_date=tomorrow)
    assert correct(official_receipt_number="OR-2026-77").official_receipt_number == "OR-2026-77"

    client = auth_client(counselor)
    for field in ("graduation_date", "official_receipt_date"):
        response = client.patch(
            f"/api/v1/good-moral/requests/{item.pk}",
            data=json.dumps({field: (tomorrow + timedelta(days=1)).isoformat()}),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_good_moral_request"


@pytest.mark.django_db
@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_issuance_refuses_a_legacy_future_graduation_date_until_corrected():
    sync_policy()
    student = make_user("legacy.graduate@example.edu", lifecycle=StudentLifecycleStatus.GRADUATED)
    counselor = make_user("legacy.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    # 15:30 UTC is still 8 October in Manila; 16:30 UTC is already 9 October.
    before_midnight = datetime(2026, 10, 8, 15, 30, tzinfo=UTC)
    after_midnight = datetime(2026, 10, 8, 16, 30, tzinfo=UTC)
    # A row saved before ADR-096 write validation, bypassing today's checks.
    GoodMoralRequest.objects.filter(pk=item.pk).update(graduation_date=date(2026, 10, 9))

    with pytest.raises(GoodMoralCertificateDateInFuture, match="Graduation date cannot be"):
        prepare_request(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
            now=before_midnight,
        )
    # A request already marked ready before the rule existed is refused at issuance itself.
    GoodMoralRequest.objects.filter(pk=item.pk).update(
        status=GoodMoralStatus.READY_FOR_ISSUANCE,
        prepared_at=before_midnight,
        prepared_by=counselor,
    )
    with pytest.raises(GoodMoralCertificateDateInFuture, match="Correct the certificate details"):
        issue_request(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
            now=before_midnight,
        )
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.READY_FOR_ISSUANCE
    assert item.graduation_date == date(2026, 10, 9)
    assert item.issued_at is None

    # Through the API, issuance uses the real clock: a stored date after today is refused.
    GoodMoralRequest.objects.filter(pk=item.pk).update(
        graduation_date=institution_today() + timedelta(days=1)
    )
    client = auth_client(counselor)
    blocked = client.post(
        f"/api/v1/good-moral/requests/{item.pk}/issue",
        data=json.dumps({"expected_preparation_version": item.prepared_at.isoformat()}),
        content_type="application/json",
        **csrf(client),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "good_moral_certificate_date_in_future"

    GoodMoralRequest.objects.filter(pk=item.pk).update(graduation_date=date(2026, 10, 9))
    # On the Manila graduation day itself the same certificate may be issued.
    issued = issue_request(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
        now=after_midnight,
    )
    assert issued.status == GoodMoralStatus.ISSUED
    assert build_certificate_render_context(issued)["certificate"]["issued_on"] == date(2026, 10, 9)


@pytest.mark.django_db
@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_issuance_accepts_historical_dates_and_refuses_a_future_receipt_date():
    sync_policy()
    student = make_user("receipt.graduate@example.edu", lifecycle=StudentLifecycleStatus.GRADUATED)
    counselor = make_user("receipt.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    update_request(
        actor=counselor,
        request_id=item.pk,
        changes={"graduation_date": date(2019, 4, 12), "official_receipt_date": date(2025, 1, 6)},
        context=AuditContext.user(counselor),
    )
    # 16:30 UTC on 31 December is already 1 January 2027 in Manila.
    new_year = datetime(2026, 12, 31, 16, 30, tzinfo=UTC)
    GoodMoralRequest.objects.filter(pk=item.pk).update(official_receipt_date=date(2027, 1, 2))

    with pytest.raises(GoodMoralCertificateDateInFuture, match="Official Receipt date cannot be"):
        prepare_request(
            actor=counselor, request_id=item.pk, context=AuditContext.user(counselor), now=new_year
        )

    GoodMoralRequest.objects.filter(pk=item.pk).update(official_receipt_date=date(2027, 1, 1))
    prepare_request(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor), now=new_year
    )
    issued = issue_request(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor), now=new_year
    )
    certificate = build_certificate_render_context(issued)["certificate"]
    assert certificate["graduation_date"] == date(2019, 4, 12)
    assert certificate["official_receipt_date"] == date(2027, 1, 1)
    # The certificate is dated on the Manila day of issuance, not the UTC day.
    assert certificate["issued_on"] == date(2027, 1, 1)
    assert issued.issued_at == new_year


@pytest.mark.django_db
def test_f4_issue_rechecks_current_lifecycle_and_duplicate_issue_is_idempotent():
    sync_policy()
    student = make_user("issue.current@example.edu")
    counselor = make_user("issue.counselor@example.edu", role="COUNSELOR")
    item, inventory = make_current_request(student)

    student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    with pytest.raises(GoodMoralCurrentStudentRequired):
        prepare_and_issue(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
        )
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.READY_FOR_ISSUANCE
    assert item.inventory_id == inventory.pk
    assert not AuditEvent.objects.filter(action="good_moral.issued").exists()

    student.student_lifecycle_status = StudentLifecycleStatus.CURRENT
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    issued = prepare_and_issue(
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
    assert issued.form_revision.official_code == "UCN-OP-GCO-01F4"
    assert issued.form_revision.official_revision == "1"
    assert issued.document_template_key == "good_moral_current_student"
    assert issued.document_template_version == 2

    issued_notification = Notification.objects.get(
        recipient=student,
        event_code="good_moral.issued",
        source_type="good_moral_request",
        source_id=item.pk,
    )
    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
        source_id=item.pk,
    )
    assert opportunity.student_id == student.pk
    assert opportunity.service_kind == CustomerFeedbackService.REQUEST_FOR_CERTIFICATION
    assert opportunity.service_label_snapshot == "Issuance of Good Moral Certificate"
    assert opportunity.service_completed_at == issued.issued_at
    feedback_notification = Notification.objects.get(
        recipient=student,
        event_code="feedback.invitation",
        source_type="feedback_opportunity",
        source_id=opportunity.pk,
    )
    assert issued_notification.policy == "MANDATORY_OPERATIONAL"
    assert issued_notification.target_type == "GOOD_MORAL"
    assert issued_notification.target_id == item.pk
    assert feedback_notification.policy == "OPTIONAL_INFORMATIONAL"
    assert feedback_notification.target_type == "FEEDBACK"
    assert feedback_notification.target_id == opportunity.pk
    assert EmailDelivery.objects.filter(notification=issued_notification).exists()
    assert EmailDelivery.objects.filter(notification=feedback_notification).exists()

    repeated = prepare_and_issue(
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
            source_id=opportunity.pk,
        ).count()
        == 1
    )
    assert (
        FeedbackOpportunity.objects.filter(
            source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
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

    prepare_and_issue(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )

    issued_notification = Notification.objects.get(
        recipient=student,
        event_code="good_moral.issued",
        source_id=item.pk,
    )
    opportunity = FeedbackOpportunity.objects.get(
        source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
        source_id=item.pk,
    )
    feedback_notification = Notification.objects.get(
        recipient=student,
        event_code="feedback.invitation",
        source_id=opportunity.pk,
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
    revision.status = "INACTIVE"
    revision.save(update_fields=["status", "updated_at"])
    FormRevision.objects.create(
        family=revision.family,
        official_code="UNCONFIRMED-GOOD-MORAL",
        official_revision="1",
        internal_schema_version=1,
        status="ACTIVE",
    )

    with pytest.raises(GoodMoralConfigurationConflict):
        prepare_and_issue(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
        )
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.READY_FOR_ISSUANCE
    assert item.form_revision_id is None


@pytest.mark.django_db
def test_issue_api_requires_counselor_capability_but_not_step_up():
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
    item = prepare_request(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)
    )

    for user in (student, gss, admin, dpo):
        client = auth_client(user, recent_mfa=True)
        denied = client.post(
            f"/api/v1/good-moral/requests/{item.pk}/issue",
            data=json.dumps({"expected_preparation_version": item.prepared_at.isoformat()}),
            content_type="application/json",
            **csrf(client),
        )
        assert denied.status_code == 403

    # Issuance is routine Guidance Office work: the capability, confirmation, and issuer
    # provenance protect it, so a session without a recent step-up can issue.
    without_step_up = auth_client(counselor)
    issued = without_step_up.post(
        f"/api/v1/good-moral/requests/{item.pk}/issue",
        data=json.dumps({"expected_preparation_version": item.prepared_at.isoformat()}),
        content_type="application/json",
        **csrf(without_step_up),
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "ISSUED"


@pytest.mark.django_db
def test_saved_render_provenance_drives_html_after_current_data_and_revision_change():
    sync_policy()
    student = make_user("render.student@example.edu")
    counselor = make_user("render.counselor@example.edu", role="COUNSELOR")
    item, inventory = make_current_request(student)
    issued = prepare_and_issue(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    saved_revision_id = issued.form_revision_id
    saved_name = issued.applicant_name_snapshot
    saved_course = issued.course_snapshot
    saved_issuer = issued.issued_by_name_snapshot

    student.first_name = "Changed"
    student.save(update_fields=["first_name", "updated_at"])
    counselor.first_name = "Renamed"
    counselor.save(update_fields=["first_name", "updated_at"])
    inventory.course_currently_enrolled = "Changed Course"
    inventory.save(update_fields=["course_currently_enrolled", "updated_at"])

    canonical_revision = issued.form_revision
    canonical_revision.status = "INACTIVE"
    canonical_revision.save(update_fields=["status", "updated_at"])
    historical_revision = FormRevision.objects.create(
        family=canonical_revision.family,
        official_code="CNSC-OP-GCO-01F4",
        official_revision="1",
        internal_schema_version=1,
        status="ACTIVE",
    )
    sync_institutional_forms()
    historical_revision.refresh_from_db()
    assert historical_revision.status == "INACTIVE"

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
    assert spec.show_page_numbers is True
    assert "University of Camarines Norte" in html
    assert "GOOD MORAL CHARACTER" in html
    assert saved_name in html
    assert context["certificate"]["course"] == saved_course
    assert "Changed Course" not in html
    assert "UCN-OP-GCO-01F4" in html
    assert "Revision: 1" in html
    assert "Page 1 of 1" in html
    assert saved_issuer.upper() in html
    assert counselor.get_full_name().upper() not in html
    signature_area = html.split('<div class="good-moral-signature">', 1)[1].split(
        '<div class="good-moral-receipt">', 1
    )[0]
    assert '<div class="good-moral-signature-line"><span class="generated-value">' in signature_area
    assert saved_issuer.upper() in signature_area
    assert context["certificate"]["issuer_name"] == saved_issuer
    assert "<img" not in signature_area
    pdf_pages = PdfReader(BytesIO(render_certificate_pdf(issued))).pages
    assert len(pdf_pages) == 1
    pdf_text = "\n".join(page.extract_text() for page in pdf_pages)
    assert saved_issuer.upper() in pdf_text
    assert counselor.get_full_name().upper() not in pdf_text


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "year_level",
        "college_name",
        "semester",
        "expected_year",
        "expected_college",
        "expected_term",
    ),
    [
        (
            "3rd Year",
            "College of Computing and Multimedia Studies",
            "First Semester",
            "3rd",
            "Computing and Multimedia Studies",
            "First",
        ),
        (
            "Fourth",
            "Computing and Multimedia Studies",
            "First",
            "Fourth",
            "Computing and Multimedia Studies",
            "First",
        ),
        (
            " third YEAR ",
            " cOLLeGe of Visual Arts ",
            " 1st semester ",
            "third",
            "Visual Arts",
            "1st",
        ),
    ],
)
def test_f4_render_uses_full_labels_and_fragments_without_changing_snapshots(
    year_level, college_name, semester, expected_year, expected_college, expected_term
):
    sync_policy()
    student = make_user("f4.labels@example.edu")
    counselor = make_user("f4.issuer@example.edu", role="COUNSELOR")
    affiliation = make_affiliation(student)
    affiliation.college.name = college_name
    affiliation.college.save(update_fields=["name", "updated_at"])
    academic_year = make_academic_year()
    inventory = make_inventory(student, academic_year)
    item = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.CURRENT_STUDENT,
        inventory=inventory,
        academic_year=inventory.academic_year,
        applicant_name_snapshot=student.get_full_name(),
        year_level_snapshot=year_level,
        college_snapshot=college_name,
        course_snapshot=inventory.course_currently_enrolled,
        major_snapshot=inventory.major,
        semester_snapshot=semester,
    )
    issued = prepare_and_issue(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )
    saved = (
        issued.year_level_snapshot,
        issued.college_snapshot,
        issued.semester_snapshot,
    )
    context = build_certificate_render_context(issued)
    html, _ = render_document_html(
        issued.document_template_key,
        issued.document_template_version,
        context=context,
    )
    rendered_text = " ".join(re.sub(r"<[^>]+>", " ", html).split())

    assert f"{expected_year} year student" in rendered_text
    assert f"College of {expected_college}" in rendered_text
    assert f"{expected_term} semester of academic year {academic_year.label}" in rendered_text
    assert "Year year" not in rendered_text
    assert "College of College of" not in rendered_text
    assert "Semester semester" not in rendered_text
    issued.refresh_from_db()
    assert (
        issued.year_level_snapshot,
        issued.college_snapshot,
        issued.semester_snapshot,
    ) == saved

    detail = auth_client(student).get(f"/api/v1/good-moral/me/{issued.pk}")
    assert detail.status_code == 200
    assert (
        detail.json()["year_level"],
        detail.json()["college"],
        detail.json()["semester"],
    ) == saved


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

    issued = prepare_and_issue(
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
    operational = auth_client(counselor).get(f"/api/v1/good-moral/requests/{issued.pk}/pdf")
    assert operational.status_code == 200
    assert operational["Content-Disposition"] == response["Content-Disposition"]
    other_student = make_user("pdf.other@example.edu", lifecycle=StudentLifecycleStatus.GRADUATED)
    assert (
        auth_client(other_student).get(f"/api/v1/good-moral/me/{issued.pk}/pdf").status_code == 404
    )

    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    for url, actor in (
        (f"/api/v1/good-moral/me/{issued.pk}/pdf", student),
        (f"/api/v1/good-moral/requests/{issued.pk}/pdf", counselor),
    ):
        blocked = auth_client(actor).get(url)
        assert blocked.status_code == 503
        assert blocked.json()["error"]["code"] == "release_audit_unavailable"
        assert b"%PDF-" not in blocked.content


@pytest.mark.django_db
def test_saved_missing_template_fails_closed_instead_of_switching_versions():
    sync_policy()
    student = make_user(
        "missing.template@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED,
    )
    counselor = make_user("template.counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)
    issued = prepare_and_issue(
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
    issued = prepare_and_issue(
        actor=counselor,
        request_id=item.pk,
        context=AuditContext.user(counselor),
    )

    saved_issuer = issued.issued_by_name_snapshot
    counselor.first_name = "Renamed"
    counselor.save(update_fields=["first_name", "updated_at"])
    html, _ = render_document_html(
        issued.document_template_key,
        issued.document_template_version,
        context=build_certificate_render_context(issued),
    )
    assert '<div class="good-moral-signature-line"><span class="generated-value">' in html
    assert saved_issuer.upper() in html
    assert counselor.get_full_name().upper() not in html
    pdf = render_certificate_pdf(issued)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1024
    pdf_pages = PdfReader(BytesIO(pdf)).pages
    assert len(pdf_pages) == 1
    pdf_text = "\n".join(page.extract_text() for page in pdf_pages)
    assert saved_issuer.upper() in pdf_text
    assert counselor.get_full_name().upper() not in pdf_text


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
    assert searched.json()["items"][0]["student_institutional_id"] == "GM-ALPHA-001"

    original_name = alpha_request.applicant_name_snapshot
    alpha.first_name = "Renamed"
    alpha.save(update_fields=["first_name", "updated_at"])
    detail = client.get(f"/api/v1/good-moral/requests/{alpha_request.pk}")
    assert detail.status_code == 200
    assert detail.json()["applicant_name"] == original_name
    assert detail.json()["student"]["display_name"] == alpha.get_full_name()
    assert detail.json()["student_institutional_id"] == "GM-ALPHA-001"
    mine = auth_client(alpha).get("/api/v1/good-moral/me")
    assert mine.status_code == 200
    assert "student_institutional_id" not in mine.json()["items"][0]

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
    payload = {"year_level": "4th Year", "semester": "First Semester"}
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
        "compass.good_moral.services._require_submitted_inventory",
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
    assert new_intent.status_code == 201
    assert new_intent.json()["degree"] == payload["degree"]


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
        data=json.dumps({"year_level": "4th Year", "semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert first.status_code == 201

    changed = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "4th Year", "semester": "Second Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_key_conflict"

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
    assert cross_variant.json()["error"]["code"] == "idempotency_key_conflict"
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
    assert graduate_changed.json()["error"]["code"] == "idempotency_key_conflict"
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
    assert not FeedbackOpportunity.objects.filter(
        source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
        source_id=uuid.UUID(cancelled_id),
    ).exists()
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
    prepare_and_issue(
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
    issued = prepare_and_issue(
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


@pytest.mark.django_db
@pytest.mark.parametrize("graduate", [False, True])
def test_legacy_certificate_reprint_preserves_saved_form_and_template(graduate):
    sync_policy()
    student = make_user(
        "legacy-cert-student@example.edu",
        lifecycle=StudentLifecycleStatus.GRADUATED if graduate else StudentLifecycleStatus.CURRENT,
    )
    counselor = make_user("legacy-cert-counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student) if graduate else make_current_request(student)[0]
    issued = prepare_and_issue(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)
    )
    legacy = FormRevision.objects.get(
        family=issued.form_revision.family, official_code__startswith="CNSC-"
    )
    issued.form_revision = legacy
    issued.document_template_version = 1
    issued.save(update_fields=["form_revision", "document_template_version"])
    sync_institutional_forms()
    issued.refresh_from_db()
    pages = PdfReader(BytesIO(render_certificate_pdf(issued))).pages
    assert len(pages) == 1
    assert legacy.official_code in pages[0].extract_text()
    assert "Revision: 0" in pages[0].extract_text()
    assert issued.form_revision_id == legacy.pk


# ==============================================================================
# FORM-INPUT-1A: Good Moral Year Level & Semester Standardization Tests
# ==============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize("year_level", CANONICAL_YEAR_LEVELS)
def test_form_input_1a_creation_accepts_inventory_derived_bachelors_year_levels(year_level: str):
    sync_policy()
    student = make_user(f"year.{year_level.replace(' ', '.').lower()}@example.edu")
    make_affiliation(student)
    academic_year = make_academic_year()
    make_inventory(student, academic_year, year_level=CANONICAL_YEAR_LEVELS.index(year_level) + 1)
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": year_level, "semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client, f"gm-year-{year_level}"),
    )
    assert response.status_code == 201
    item = GoodMoralRequest.objects.get(pk=response.json()["id"])
    assert item.year_level_snapshot == year_level
    assert item.semester_snapshot == "First Semester"


@pytest.mark.django_db
@pytest.mark.parametrize("semester", CANONICAL_SEMESTERS)
def test_form_input_1a_creation_accepts_both_canonical_semesters(semester: str):
    sync_policy()
    student = make_user(f"sem.{semester.replace(' ', '.').lower()}@example.edu")
    make_affiliation(student)
    academic_year = make_academic_year()
    make_inventory(student, academic_year, year_level=3)
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "3rd Year", "semester": semester}),
        content_type="application/json",
        **good_moral_create_headers(client, f"gm-sem-{semester}"),
    )
    assert response.status_code == 201
    item = GoodMoralRequest.objects.get(pk=response.json()["id"])
    assert item.year_level_snapshot == "3rd Year"
    assert item.semester_snapshot == semester


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_year",
    [
        "Fourth",
        "1st",
        "11th Year",
        "0 Year",
        "First Year",
        "Fifth",
        "Senior",
        "Grade 12",
        "random string",
    ],
)
def test_form_input_1a_creation_rejects_unsupported_year_level(invalid_year: str):
    sync_policy()
    student = make_user("bad.year@example.edu")
    make_affiliation(student)
    academic_year = make_academic_year()
    make_inventory(student, academic_year)
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": invalid_year, "semester": "First Semester"}),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_good_moral_request"
    assert "year_level must be between 1st and 4th Year" in response.json()["error"]["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_sem",
    [
        "Summer",
        "Midyear",
        "Summer/Midyear",
        "Third Semester",
        "First",
        "Second",
        "1st Semester",
        "Special Term",
        "random term",
    ],
)
def test_form_input_1a_creation_rejects_unsupported_semester(invalid_sem: str):
    sync_policy()
    student = make_user("bad.sem@example.edu")
    make_affiliation(student)
    academic_year = make_academic_year()
    make_inventory(student, academic_year, year_level=3)
    client = auth_client(student)

    response = client.post(
        "/api/v1/good-moral/me/requests/current-student",
        data=json.dumps({"year_level": "3rd Year", "semester": invalid_sem}),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_good_moral_request"
    assert "semester is not supported" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_form_input_1a_idempotent_replay_preserves_older_accepted_fifth_year_requests(monkeypatch):
    sync_policy()
    student = make_user("idem.legacy@example.edu")
    make_affiliation(student)
    academic_year = make_academic_year()
    inventory = make_inventory(student, academic_year)

    key = "gm-legacy-idem-1"
    digest = good_moral_services._creation_digest(student_id=student.pk, key=key)
    fingerprint = "a" * 64

    # Simulate an older accepted request stored with legacy free-text values
    legacy_item = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.CURRENT_STUDENT,
        inventory=inventory,
        academic_year=academic_year,
        applicant_name_snapshot=student.get_full_name(),
        year_level_snapshot="5th Year",
        college_snapshot="College of Arts",
        course_snapshot="BA History",
        major_snapshot="",
        semester_snapshot="First",
        creation_key_digest=digest,
        creation_request_fingerprint=fingerprint,
    )

    def fail_inventory(_student):
        raise AssertionError("an exact historical replay must not revalidate the Inventory")

    monkeypatch.setattr(good_moral_services, "_require_submitted_inventory", fail_inventory)
    replayed = good_moral_services.create_my_current_student(
        student=student,
        year_level="5th Year",
        semester="First",
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=AuditContext.user(student),
    )
    assert replayed.pk == legacy_item.pk
    assert replayed.year_level_snapshot == "5th Year"
    assert replayed.semester_snapshot == "First"


@pytest.mark.django_db
def test_form_input_1a_counselor_and_gss_corrections_match_the_linked_inventory():
    sync_policy()
    student = make_user("correction.student@example.edu")
    counselor = make_user("correction.counselor@example.edu", role="COUNSELOR")
    staff = make_user("correction.gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    UserDesignation.objects.create(
        user=staff,
        designation=Designation.objects.create(code="STAFF_PREP", name="Preparation Staff"),
    )

    item, _ = make_current_request(student)
    assert item.year_level_snapshot == "4th Year"
    assert item.semester_snapshot == "First Semester"
    # Historical certificates can carry a legacy value that needs an explicit correction.
    item.year_level_snapshot = "5th Year"
    item.save(update_fields=["year_level_snapshot", "updated_at"])

    # A changed value is accepted when it matches the linked submitted Inventory.
    updated_by_counselor = update_request(
        actor=counselor,
        request_id=item.pk,
        changes={"year_level_snapshot": "4th Year", "semester_snapshot": "Second Semester"},
        context=AuditContext.user(counselor),
    )
    assert updated_by_counselor.year_level_snapshot == "4th Year"
    assert updated_by_counselor.semester_snapshot == "Second Semester"

    # GSS retains authorized clerical correction access for a request linked to 1st Year.
    other_student = make_user("correction.gss.student@example.edu")
    make_affiliation(other_student)
    make_inventory(
        other_student,
        AcademicYear.objects.get(pk=item.academic_year_id),
        year_level=1,
    )
    staff_item = create_my_current_student(
        student=other_student,
        year_level="1st Year",
        semester="Second Semester",
        context=AuditContext.user(other_student),
    )
    staff_item.year_level_snapshot = "5th Year"
    staff_item.save(update_fields=["year_level_snapshot", "updated_at"])
    updated_by_staff = update_request(
        actor=staff,
        request_id=staff_item.pk,
        changes={"year_level_snapshot": "1st Year", "semester_snapshot": "First Semester"},
        context=AuditContext.user(staff),
    )
    assert updated_by_staff.year_level_snapshot == "1st Year"
    assert updated_by_staff.semester_snapshot == "First Semester"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "legacy_level", ["5th Year", "6th Year", "7th Year", "8th Year", "9th Year", "10th Year"]
)
def test_form_input_1a_operational_correction_preserves_untouched_legacy_values(legacy_level):
    sync_policy()
    student = make_user("legacy.preserve@example.edu")
    counselor = make_user("legacy.counselor@example.edu", role="COUNSELOR")
    make_affiliation(student)
    academic_year = make_academic_year()
    inventory = make_inventory(student, academic_year)

    # Legacy request with historical free-text
    item = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.CURRENT_STUDENT,
        inventory=inventory,
        academic_year=academic_year,
        applicant_name_snapshot=student.get_full_name(),
        year_level_snapshot=legacy_level,
        college_snapshot="College of Engineering",
        course_snapshot="BS Civil Engineering",
        major_snapshot="",
        semester_snapshot="First",
    )

    # Unrelated correction (course and receipt) must preserve legacy values without error
    updated = update_request(
        actor=counselor,
        request_id=item.pk,
        changes={
            "course_snapshot": "BS Electrical Engineering",
            "official_receipt_number": "OR-2026-9999",
        },
        context=AuditContext.user(counselor),
    )
    assert updated.course_snapshot == "BS Electrical Engineering"
    assert updated.official_receipt_number == "OR-2026-9999"
    assert updated.year_level_snapshot == legacy_level
    assert updated.semester_snapshot == "First"

    # Providing the exact same legacy values unchanged in changes also succeeds
    updated_same = update_request(
        actor=counselor,
        request_id=item.pk,
        changes={
            "year_level_snapshot": legacy_level,
            "semester_snapshot": "First",
            "official_receipt_number": "OR-2026-1000",
        },
        context=AuditContext.user(counselor),
    )
    assert updated_same.year_level_snapshot == legacy_level
    assert updated_same.semester_snapshot == "First"
    assert updated_same.official_receipt_number == "OR-2026-1000"


@pytest.mark.django_db
def test_form_input_1a_operational_correction_rejects_unsupported_values_when_changed():
    sync_policy()
    student = make_user("correction.bad@example.edu")
    counselor = make_user("correction.bad.counselor@example.edu", role="COUNSELOR")
    item, _ = make_current_request(student)

    # Attempt to change year_level to unsupported value
    with pytest.raises(InvalidGoodMoralInput, match="year_level is not supported"):
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"year_level_snapshot": "Senior Year"},
            context=AuditContext.user(counselor),
        )

    with pytest.raises(InvalidGoodMoralInput, match="must match the linked submitted Inventory"):
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"year_level_snapshot": "3rd Year"},
            context=AuditContext.user(counselor),
        )

    # Attempt to change semester to unsupported value
    with pytest.raises(InvalidGoodMoralInput, match="semester is not supported"):
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"semester_snapshot": "Summer"},
            context=AuditContext.user(counselor),
        )

    # Stored values are untouched
    item.refresh_from_db()
    assert item.year_level_snapshot == "4th Year"
    assert item.semester_snapshot == "First Semester"


@pytest.mark.django_db
def test_form_input_1a_operational_correction_issued_remains_locked():
    sync_policy()
    student = make_user("locked.student@example.edu")
    counselor = make_user("locked.counselor@example.edu", role="COUNSELOR")
    item, _ = make_current_request(student)

    issued = prepare_and_issue(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)
    )
    with pytest.raises(GoodMoralConflict, match="Issued and cancelled"):
        update_request(
            actor=counselor,
            request_id=issued.pk,
            changes={"year_level_snapshot": "1st Year"},
            context=AuditContext.user(counselor),
        )


@pytest.mark.django_db
def test_form_input_1a_operational_correction_cancelled_remains_locked():
    sync_policy()
    student = make_user("locked.student2@example.edu")
    counselor = make_user("locked.counselor2@example.edu", role="COUNSELOR")
    item, _ = make_current_request(student)

    cancelled = cancel_request(
        actor=counselor,
        request_id=item.pk,
        reason="No longer needed",
        self_service=False,
        context=AuditContext.user(counselor),
    )
    with pytest.raises(GoodMoralConflict, match="Issued and cancelled"):
        update_request(
            actor=counselor,
            request_id=cancelled.pk,
            changes={"year_level_snapshot": "1st Year"},
            context=AuditContext.user(counselor),
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "scenario_name",
        "year_level",
        "semester",
        "expected_year_text",
        "expected_sem_text",
        "renderer_version",
    ),
    [
        # Scenario 1: 1st Year / First Semester
        ("canonical_1st", "1st Year", "First Semester", "1st year student", "First semester", 2),
        # Scenario 2: 2nd Year / Second Semester
        ("canonical_2nd", "2nd Year", "Second Semester", "2nd year student", "Second semester", 2),
        # Scenario 3: 10th Year / First Semester
        ("canonical_10th", "10th Year", "First Semester", "10th year student", "First semester", 2),
        # Scenario 4: Historical Year Level text with trailing year
        ("legacy_year", "3rd Year", "First Semester", "3rd year student", "First semester", 2),
        # Scenario 5: Historical Semester text with trailing semester
        ("legacy_sem", "4th Year", "1st semester", "4th year student", "1st semester", 2),
        # Scenario 6: Historical renderer version 1
        (
            "legacy_renderer_v1",
            "3rd Year",
            "First Semester",
            "3rd year student",
            "First semester",
            1,
        ),
        # Scenario 7: Current UCN F4 renderer version 2
        (
            "current_ucn_v2",
            "4th Year",
            "Second Semester",
            "4th year student",
            "Second semester",
            2,
        ),
    ],
)
def test_form_input_1a_official_f4_pdf_rendering_scenarios(
    scenario_name,
    year_level,
    semester,
    expected_year_text,
    expected_sem_text,
    renderer_version,
):
    sync_policy()
    student = make_user(f"pdf.{scenario_name}@example.edu")
    counselor = make_user(f"pdf.counselor.{scenario_name}@example.edu", role="COUNSELOR")
    make_affiliation(student)
    academic_year = make_academic_year()
    inventory = make_inventory(student, academic_year)

    item = GoodMoralRequest.objects.create(
        student=student,
        variant=GoodMoralVariant.CURRENT_STUDENT,
        inventory=inventory,
        academic_year=academic_year,
        applicant_name_snapshot=student.get_full_name(),
        year_level_snapshot=year_level,
        college_snapshot="College of Science",
        course_snapshot=inventory.course_currently_enrolled,
        major_snapshot=inventory.major,
        semester_snapshot=semester,
    )
    issued = prepare_and_issue(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)
    )

    if renderer_version != issued.document_template_version:
        issued.document_template_version = renderer_version
        if renderer_version == 1:
            issued.document_template_key = "good_moral_current_student"
            legacy_rev = FormRevision.objects.get(
                family__key="good_moral_current_student", official_code__startswith="CNSC-"
            )
            issued.form_revision = legacy_rev
        issued.save(
            update_fields=["document_template_key", "document_template_version", "form_revision"]
        )

    # Render PDF
    pdf_bytes = render_certificate_pdf(issued)
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
    pdf_text = " ".join(reader.pages[0].extract_text().split())

    # Verify expected text fragments
    assert expected_year_text in pdf_text
    assert expected_sem_text in pdf_text

    # Strict check: NO duplicate word repetitions
    assert "year year" not in pdf_text.lower()
    assert "semester semester" not in pdf_text.lower()

    # Verify database snapshots were never mutated by rendering
    issued.refresh_from_db()
    assert issued.year_level_snapshot == year_level
    assert issued.semester_snapshot == semester


@pytest.mark.django_db
def test_form_input_1a_graduate_f6_strict_non_regression():
    sync_policy()
    student = make_user("f6.regression@example.edu", lifecycle=StudentLifecycleStatus.GRADUATED)
    counselor = make_user("f6.counselor@example.edu", role="COUNSELOR")

    # Graduate request creation succeeds with its own fields
    grad = make_graduate_request(student)
    assert grad.variant == GoodMoralVariant.GRADUATE
    assert grad.year_level_snapshot == ""
    assert grad.semester_snapshot == ""
    assert grad.degree_snapshot == "Bachelor of Science in Information Systems"

    # Graduate creation payload does not accept year_level or semester
    client = auth_client(student)
    bad_grad = client.post(
        "/api/v1/good-moral/me/requests/graduate",
        data=json.dumps(
            {
                "degree": "BS Biology",
                "major": "",
                "graduation_date": "2026-06-30",
                "year_level": "4th Year",
            }
        ),
        content_type="application/json",
        **good_moral_create_headers(client),
    )
    assert bad_grad.status_code == 422

    # Graduate correction works for degree/major
    updated_grad = update_request(
        actor=counselor,
        request_id=grad.pk,
        changes={"degree_snapshot": "Bachelor of Science in Computer Science"},
        context=AuditContext.user(counselor),
    )
    assert updated_grad.degree_snapshot == "Bachelor of Science in Computer Science"

    # Graduate issuance and PDF work cleanly
    issued = prepare_and_issue(
        actor=counselor, request_id=updated_grad.pk, context=AuditContext.user(counselor)
    )
    pdf_bytes = render_certificate_pdf(issued)
    pages = PdfReader(BytesIO(pdf_bytes)).pages
    assert len(pages) == 1
    assert "Computer Science" in pages[0].extract_text()
