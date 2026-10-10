from __future__ import annotations

from datetime import UTC, date, datetime
from io import BytesIO

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone
from pypdf import PdfReader

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.documents.rendering import render_document_html, render_document_pdf
from compass.inventory.confidential_content import (
    read_confidential_content,
    read_inventory_private_projection,
)
from compass.inventory.documents import (
    build_inventory_render_context,
    render_inventory_pdf,
)
from compass.inventory.models import StudentInventory
from compass.inventory.services import (
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import (
    create_academic_year,
    set_current_academic_year,
)
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from tests.inventory_encryption_helpers import update_inventory_private
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-long-enough",
        role=Role.objects.get(code=role),
        first_name="Alex",
        last_name="Student",
    )


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def make_submitted_inventory(*, student: User, actor: User, code: str) -> StudentInventory:
    year = create_academic_year(label="2026-2027", context=context(actor))
    set_current_academic_year(academic_year_id=year.pk, context=context(actor))
    campus = Campus.objects.create(code=f"C-{code}", name="Main Campus")
    college = College.objects.create(campus=campus, code=f"COL-{code}", name="College")
    program = Program.objects.create(
        college=college, code=f"P-{code}", name="BS Information Systems"
    )
    StudentAffiliation.objects.create(student=student, college=college)
    ensure_current_inventory(student=student, context=context(student))
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(
        {
            "full_name_snapshot": "Alex Student",
            "nickname": "Alex",
            "student_number": "2026-001",
            "place_of_birth": "Daet, Camarines Norte",
            "nationality": "Filipino",
            "birth_order_among_siblings": "2nd",
            "current_address": "Daet, Camarines Norte",
            "permanent_address": "Basud, Camarines Norte",
            "contact_number": "09170000000",
            "email_address": "alex@example.edu",
            "friends_in_school": "Jamie Cruz",
            "special_interest": "Reading",
            "living_arrangement": "BOARDING_HOUSE",
            "boarding_exclusive": True,
            "boarding_landlord_name": "Maria Reyes",
            "boarding_address": "Daet, Camarines Norte",
            "accidents_experienced": "None",
            "height": "160 cm",
            "weight": "55 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE"],
            "interests": ["PAINTING", "SINGING"],
            "current_concerns": (
                "Balancing classes, transportation, family responsibilities, and school "
                "expenses while adapting to a new schedule is challenging. I am learning "
                "to ask for help, manage my time, and keep up with coursework while "
                "supporting my family responsibilities."
            ),
            "current_fears": (
                "I worry about falling behind in class, missing important deadlines, and "
                "being unable to support my family while I complete my studies."
            ),
            "handedness": "RIGHT",
            "ideal_monthly_allowance": "FROM_100_TO_499",
            "intended_work_field": "PROFESSIONAL",
            "prior_counseling_experience": False,
            "siblings": [
                {"sort_order": 0, "name": "Alex Student", "sex": "MALE", "age": 19, "is_self": True}
            ],
            "education_entries": [
                {
                    "level": "SENIOR_HIGH",
                    "school_attended_address": "Camarines Norte Senior High School, Daet",
                    "inclusive_years": "2022-2024",
                    "awards_received": "With Honors",
                }
            ],
            "organization_memberships": [
                {
                    "scope": "INSIDE_SCHOOL",
                    "sort_order": 0,
                    "organization_name": "Student Council",
                    "position_title": "Member",
                }
            ],
            "transportation_entries": [
                {
                    "mode": "TRICYCLE",
                    "frequency_category": "DAILY",
                    "frequency": "Daily",
                    "fare": "20.00",
                }
            ],
        }
    )
    replace_current_inventory(student=student, values=values)
    return submit_current_inventory(student=student, context=context(student))


@pytest.mark.django_db
def test_individual_inventory_html_and_chromium_pdf_are_source_shaped_and_three_pages(caplog):
    call_command("sync_identity_policy", verbosity=0)
    student = make_user("inventory-pdf-student@example.edu", "STUDENT")
    actor = make_user("inventory-pdf-admin@example.edu", "IT_ADMIN")
    item = make_submitted_inventory(student=student, actor=actor, code="INVPDF")

    context_data = build_inventory_render_context(
        item, private=read_inventory_private_projection(item)
    )
    html, spec = render_document_html("individual_inventory", 1, context=context_data)
    for label in (
        "INDIVIDUAL INVENTORY",
        "TO THE STUDENTS:",
        "PERSONAL DATA",
        "FAMILY DATA",
        "PERSON TO CONTACT IN CASE OF EMERGENCY",
        "UNIQUE",
        "LIVING CONDITIONS",
        "HEALTH CONDITIONS",
        "EDUCATIONAL BACKGROUND",
        "INTEREST",
        "MEMBERSHIP IN ORGANIZATIONS",
        "MODE OF TRANSPORTATION TO AND FROM CNSC",
        "PERCEPTION",
    ):
        assert label in html
    assert html.count('class="individual-inventory-page') == 3
    assert "Page 1 of 3" in html and "Page 2 of 3" in html and "Page 3 of 3" in html
    assert "CNSC-OP-GCO-01F5" in html and "Revision: 0" in html
    assert "StudentSupportProfile" not in html
    assert "student_number" not in html
    assert "Alex" in html
    assert ".inventory-source-body .generated-value" in html
    assert ".generated-value {\n  color: #0000ff;" in html
    assert spec.include_accreditation_footer is False
    assert '<footer class="accreditation-footer">' not in html

    pdf_bytes = render_inventory_pdf(item)
    pages = PdfReader(BytesIO(pdf_bytes)).pages
    assert len(pages) == 3
    assert all(round(float(page.mediabox.width)) == 595 for page in pages)
    assert all(round(float(page.mediabox.height)) == 842 for page in pages)
    text = "\n".join(page.extract_text() or "" for page in pages)
    assert "Alex Student" in text
    assert "Student Council" in text
    assert "Camarines Norte" in text
    assert "Senior High" in text
    assert "Camarines Norte Senior High School, Daet" in text
    assert "Current Concerns" in text
    assert "Balancing classes, transportation" in text
    assert "I worry about falling behind" in text
    assert (
        html.count('class="inventory-answer-rule inventory-answer-rule-first" aria-hidden="true"')
        == 2
    )
    assert (
        html.count(
            'class="inventory-answer-rule inventory-answer-rule-continuation" aria-hidden="true"'
        )
        == 2
    )
    assert "FourPs" not in text and "Indigenous Peoples" not in text

    blank_context = {
        **context_data,
        "inventory_form": {**context_data["inventory_form"], "concerns": "", "fears": ""},
    }
    blank_pdf = render_document_pdf(
        "individual_inventory",
        item.form_revision.internal_schema_version,
        context=blank_context,
    ).pdf_bytes
    assert len(PdfReader(BytesIO(blank_pdf)).pages) == 3

    long_answer = "A lengthy answer that should wrap before truncation. " * 40
    long_concern_context = {
        **context_data,
        "inventory_form": {
            **context_data["inventory_form"],
            "concerns": long_answer,
            "fears": long_answer,
        },
    }
    with caplog.at_level("WARNING", logger="compass.documents.rendering"):
        long_concern_pdf = render_document_pdf(
            "individual_inventory",
            item.form_revision.internal_schema_version,
            context=long_concern_context,
        ).pdf_bytes
    long_concern_pages = PdfReader(BytesIO(long_concern_pdf)).pages
    assert len(long_concern_pages) == 3
    long_answer_text = long_concern_pages[2].extract_text() or ""
    assert "Current Concerns" in long_answer_text
    assert "Current Fears" in long_answer_text
    assert long_answer_text.count("…") == 2
    assert (
        0 < long_answer_text.count("A lengthy answer") < 2 * long_answer.count("A lengthy answer")
    )
    assert "A lengthy answer" not in caplog.text
    item.refresh_from_db()
    assert (
        read_confidential_content(item).current_concerns
        == context_data["inventory_form"]["concerns"]
    )
    assert read_confidential_content(item).current_fears == context_data["inventory_form"]["fears"]

    school = item.education_entries.get(level="SENIOR_HIGH")
    update_inventory_private(school, school_attended_address="Very long school address " * 40)
    item.refresh_from_db()
    with caplog.at_level("WARNING", logger="compass.documents.rendering"):
        long_school_pdf = render_inventory_pdf(item)
    long_school_pages = PdfReader(BytesIO(long_school_pdf)).pages
    assert len(long_school_pages) == 3
    assert "…" in "\n".join(page.extract_text() or "" for page in long_school_pages)
    assert "Very long school address" not in caplog.text
    assert any(
        getattr(record, "event", None) == "inventory_pdf_values_truncated"
        for record in caplog.records
    )
    assert "Very long school address" in read_confidential_content(school).school_attended_address


@pytest.mark.django_db
@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_printed_submission_date_and_age_use_the_manila_day_under_a_utc_runtime():
    call_command("sync_identity_policy", verbosity=0)
    student = make_user("inventory-day-student@example.edu", "STUDENT")
    actor = make_user("inventory-day-admin@example.edu", "IT_ADMIN")
    item = make_submitted_inventory(student=student, actor=actor, code="INVDAY")
    # Submitted at 00:30 on 9 October in Manila, still 8 October in UTC: the birthday.
    StudentInventory.objects.filter(pk=item.pk).update(
        submitted_at=datetime(2026, 10, 8, 16, 30, tzinfo=UTC),
        date_of_birth=date(2006, 10, 9),
    )
    item.refresh_from_db()

    form = build_inventory_render_context(item, private=read_inventory_private_projection(item))[
        "inventory_form"
    ]
    assert form["submitted_date"] == "October 9, 2026"
    assert form["age"] == 20


@pytest.mark.django_db
def test_student_inventory_pdf_is_owned_submitted_only_and_audited_safely(monkeypatch):
    call_command("sync_identity_policy", verbosity=0)
    student = make_user("inventory-pdf-owner@example.edu", "STUDENT")
    other_student = make_user("inventory-pdf-other@example.edu", "STUDENT")
    actor = make_user("inventory-pdf-access-admin@example.edu", "IT_ADMIN")
    submitted = make_submitted_inventory(student=student, actor=actor, code="PDFACCESS")
    school = submitted.education_entries.get(level="SENIOR_HIGH")
    update_inventory_private(school, school_attended_address="Very long school address " * 40)
    client = auth_client(student)

    own_response = client.get(f"/api/v1/inventory/me/{submitted.pk}/pdf")
    assert own_response.status_code == 200
    assert own_response["Content-Type"] == "application/pdf"
    own_pages = PdfReader(BytesIO(own_response.content)).pages
    assert len(own_pages) == 3
    assert "…" in "\n".join(page.extract_text() or "" for page in own_pages)
    assert own_response["Content-Disposition"] == (
        f'attachment; filename="individual-inventory-{submitted.pk}.pdf"'
    )
    event = AuditEvent.objects.get(
        action="document.download_released",
        target_id=str(submitted.pk),
    )
    assert event.metadata == {
        "document_type": "individual_inventory",
        "access_mode": "SELF",
        "form_revision_id": str(submitted.form_revision_id),
        "official_code": "CNSC-OP-GCO-01F5",
        "official_revision": "0",
    }
    assert "Alex Student" not in str(event.metadata)
    next_year = create_academic_year(label="2027-2028", context=context(actor))
    set_current_academic_year(academic_year_id=next_year.pk, context=context(actor))
    draft = ensure_current_inventory(student=student, context=context(student))
    draft_response = client.get(f"/api/v1/inventory/me/{draft.pk}/pdf")
    assert draft_response.status_code == 409
    assert draft_response.json()["error"]["code"] == ("inventory_not_submitted")

    foreign = auth_client(other_student).get(f"/api/v1/inventory/me/{submitted.pk}/pdf")
    assert foreign.status_code == 404

    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("private audit failure")),
    )
    blocked = client.get(f"/api/v1/inventory/me/{submitted.pk}/pdf")
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "release_audit_unavailable"
    assert blocked["Content-Type"].startswith("application/json")
    assert b"%PDF" not in blocked.content


@pytest.mark.django_db
def test_counselor_inventory_pdf_uses_existing_contextual_review_authority(monkeypatch):
    call_command("sync_identity_policy", verbosity=0)
    student = make_user("inventory-pdf-scoped-student@example.edu", "STUDENT")
    actor = make_user("inventory-pdf-scoped-admin@example.edu", "IT_ADMIN")
    counselor = make_user("inventory-pdf-scoped-counselor@example.edu", "COUNSELOR")
    other_counselor = make_user("inventory-pdf-other-counselor@example.edu", "COUNSELOR")
    unrelated_role = make_user("inventory-pdf-unrelated@example.edu", "IT_ADMIN")
    submitted = make_submitted_inventory(student=student, actor=actor, code="PDFSCOPE")
    CounselorResponsibility.objects.create(
        college=submitted.program.college,
        counselor=counselor,
    )

    allowed = auth_client(counselor).get(f"/api/v1/inventory/records/{submitted.pk}/pdf")
    assert allowed.status_code == 200
    assert allowed["Content-Type"] == "application/pdf"
    assert allowed["Content-Disposition"] == (
        f'attachment; filename="individual-inventory-{submitted.pk}.pdf"'
    )
    assert PdfReader(BytesIO(allowed.content)).pages

    hidden = auth_client(other_counselor).get(f"/api/v1/inventory/records/{submitted.pk}/pdf")
    assert hidden.status_code == 404
    denied = auth_client(unrelated_role).get(f"/api/v1/inventory/records/{submitted.pk}/pdf")
    assert denied.status_code == 403

    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    blocked = auth_client(counselor).get(f"/api/v1/inventory/records/{submitted.pk}/pdf")
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "release_audit_unavailable"
    assert b"%PDF-" not in blocked.content
