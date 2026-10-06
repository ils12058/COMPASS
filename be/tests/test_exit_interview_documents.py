from __future__ import annotations

import json
from dataclasses import replace
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import Client
from pypdf import PdfReader

from compass.accounts.models import Designation, UserDesignation
from compass.audit.models import AuditEvent
from compass.documents.rendering import DocumentRenderError, render_document_html
from compass.exit_interviews.confidential_content import (
    read_exit_interview_confidential_content,
    write_exit_interview_confidential_content,
)
from compass.exit_interviews.documents import (
    build_exit_interview_render_context,
    render_exit_interview_pdf,
)
from compass.exit_interviews.models import ExitInterview, ExitInterviewStatus
from tests.test_exit_interviews import (
    auth_client,
    csrf,
    ensure_api,
    make_head,
    make_inventory,
    make_user,
    make_year,
    put_api,
    submit_api,
    valid_payload,
)


def _submitted(*, feedback_zero: bool = False):
    call_command("sync_identity_policy", verbosity=0)
    student = make_user("exit-pdf-student@example.edu")
    year = make_year()
    make_inventory(student, year)
    client = auth_client(student)
    assert ensure_api(client).status_code == 200
    payload = valid_payload(feedback_zero=feedback_zero)
    assert put_api(client, payload).status_code == 200
    assert submit_api(client).status_code == 200
    return student, client, ExitInterview.objects.get(student=student)


@pytest.mark.django_db
def test_submitted_pdf_uses_saved_snapshots_and_all_source_rows(tmp_path):
    student, _, item = _submitted(feedback_zero=True)
    student.first_name = "Changed"
    student.email = "changed-account@example.edu"
    student.save(update_fields=["first_name", "email", "updated_at"])
    item.inventory.course_currently_enrolled = "Changed Inventory Course"
    item.inventory.save(update_fields=["course_currently_enrolled"])

    context = build_exit_interview_render_context(
        item, read_exit_interview_confidential_content(item)
    )
    form = context["exit_form"]
    assert form["name"] == "Form Local Student"
    assert form["email"] == "form-local@example.edu"
    assert form["course"] == "BS Information Systems"
    assert len(form["self_rows"]) == 15
    assert sum(len(category["rows"]) for category in form["categories"]) == 26
    assert form["categories"][0]["rows"][0]["rating"] == 0
    assert [(category["label"], category["comments"]) for category in form["categories"]] == [
        ("DEAN", "Dean comment"),
        ("PROG CHAIR", "Program Chair comment"),
        ("FACULTY", "Faculty comment"),
        ("CURRICULUM", "Curriculum comment"),
        ("GUIDANCE COUNSELOR", "Guidance comment"),
        ("OFFICE STAFF", "Office Staff comment"),
        ("FACILITIES", "Facilities comment"),
    ]
    html, spec = render_document_html("exit_interview", 1, context=context)
    assert spec.include_accreditation_footer is False
    assert "Pride and confidence in being from CNSC" in html
    assert "SUGGESTIONS/RECOMMENDATIONS (if any):" in html
    assert "N/A" not in html and "No opinion" not in html
    assert '<span class="exit-selected">0</span>' in html
    assert "Changed Inventory Course" not in html
    assert "changed-account@example.edu" not in html
    assert "CNSC-OP-GCO" not in html and "UCN-OP-GCO" not in html

    pdf = render_exit_interview_pdf(item)
    assert pdf.startswith(b"%PDF-")
    (tmp_path / "submitted-exit-interview.pdf").write_bytes(pdf)
    pages = PdfReader(BytesIO(pdf)).pages
    assert len(pages) == 2
    assert all(round(float(page.mediabox.width)) == 595 for page in pages)
    assert all(round(float(page.mediabox.height)) == 842 for page in pages)
    page_one, page_two = [page.extract_text() or "" for page in pages]
    assert "SELF-ASSESSMENT" in page_one
    assert "FEEDBACK TO THE COLLEGE" not in page_one
    assert "FEEDBACK TO THE COLLEGE" in page_two
    assert "Suggestion" in page_two
    assert "Pride and confidence in being from CNSC" in page_one
    assert "Form Local Student" in page_one


@pytest.mark.django_db
def test_long_comments_flow_to_additional_pages_without_losing_text(tmp_path):
    _, _, item = _submitted()
    write_exit_interview_confidential_content(
        item,
        replace(
            read_exit_interview_confidential_content(item),
            dean_comments="\n".join(f"Dean comment line {index:02d}" for index in range(60)),
            suggestions_recommendations="\n".join(
                f"Suggestion line {index:02d}" for index in range(60)
            ),
        ),
    )
    item.save(update_fields=["confidential_content_ciphertext", "updated_at"])

    pdf = render_exit_interview_pdf(item)
    (tmp_path / "long-exit-interview.pdf").write_bytes(pdf)
    pages = PdfReader(BytesIO(pdf)).pages
    assert len(pages) >= 3
    text = "\n".join(page.extract_text() or "" for page in pages)
    assert "Dean comment line 59" in text
    assert "Suggestion line 59" in text


@pytest.mark.django_db
def test_pdf_endpoints_enforce_owner_head_scope_and_fail_closed_release(monkeypatch):
    student, client, item = _submitted(feedback_zero=True)
    student_url = f"/api/v1/exit-interviews/me/{item.pk}/pdf"
    head_url = f"/api/v1/exit-interviews/{item.pk}/pdf"
    assert Client().get(student_url).status_code == 401

    own = client.get(student_url)
    assert own.status_code == 200
    assert own["Content-Type"] == "application/pdf"
    assert own["Content-Disposition"] == f'attachment; filename="exit-interview-{item.pk}.pdf"'
    assert b"%PDF-" in own.content
    event = AuditEvent.objects.get(action="document.download_released", target_id=str(item.pk))
    assert event.target_type == "exitinterviews.exitinterview"
    assert event.metadata == {"document_type": "exit_interview", "access_mode": "SELF"}
    assert "Dean comment" not in str(event.metadata)

    other = auth_client(make_user("exit-pdf-other-student@example.edu"))
    assert other.get(student_url).status_code == 404
    assert (
        auth_client(make_user("exit-pdf-counselor@example.edu", role="COUNSELOR"))
        .get(head_url)
        .status_code
        == 403
    )
    assert (
        auth_client(make_user("exit-pdf-gss@example.edu", role="GUIDANCE_SERVICES_STAFF"))
        .get(head_url)
        .status_code
        == 403
    )
    assert (
        auth_client(make_user("exit-pdf-admin@example.edu", role="IT_ADMIN"))
        .get(head_url)
        .status_code
        == 403
    )
    dpo = make_user("exit-pdf-dpo@example.edu", role="COUNSELOR")
    UserDesignation.objects.create(user=dpo, designation=Designation.objects.get(code="DPO"))
    assert auth_client(dpo).get(head_url).status_code == 403

    head = auth_client(make_head("exit-pdf-head@example.edu"))
    reviewed = head.get(head_url)
    assert reviewed.status_code == 200
    assert reviewed["Content-Type"] == "application/pdf"
    assert reviewed["Content-Disposition"] == own["Content-Disposition"]
    assert (
        AuditEvent.objects.filter(
            action="document.download_released", target_id=str(item.pk)
        ).count()
        == 2
    )

    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    blocked = client.get(student_url)
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "release_audit_unavailable"
    assert b"%PDF-" not in blocked.content
    blocked_head = head.get(head_url)
    assert blocked_head.status_code == 503
    assert blocked_head.json()["error"]["code"] == "release_audit_unavailable"
    assert b"%PDF-" not in blocked_head.content
    assert (
        AuditEvent.objects.filter(
            action="document.download_released", target_id=str(item.pk)
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_draft_reopen_resubmit_and_render_failure_have_no_stale_release():
    student, client, item = _submitted()
    student_url = f"/api/v1/exit-interviews/me/{item.pk}/pdf"
    head_url = f"/api/v1/exit-interviews/{item.pk}/pdf"
    head = auth_client(make_head("exit-pdf-reopen-head@example.edu"))

    reopened = head.post(
        f"/api/v1/exit-interviews/{item.pk}/reopen",
        data='{"reason":"Correction requested"}',
        content_type="application/json",
        **csrf(head),
    )
    assert reopened.status_code == 200
    item.refresh_from_db()
    assert item.status == ExitInterviewStatus.DRAFT
    assert client.get(student_url).status_code == 409
    assert head.get(head_url).status_code == 409
    assert not AuditEvent.objects.filter(
        action="document.download_released", target_id=str(item.pk)
    ).exists()

    corrected = valid_payload()
    corrected["dean_comments"] = "Corrected Dean response"
    assert put_api(client, corrected).status_code == 200
    assert (
        client.post(f"/api/v1/exit-interviews/me/{item.pk}/submit", **csrf(client)).status_code
        == 200
    )
    with patch(
        "compass.exit_interviews.documents.render_document_pdf",
        side_effect=DocumentRenderError("private rendering detail"),
    ):
        unavailable = client.get(student_url)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "exit_interview_document_unavailable"
    assert "private rendering detail" not in unavailable.content.decode()
    assert not AuditEvent.objects.filter(
        action="document.download_released", target_id=str(item.pk)
    ).exists()
    latest = client.get(student_url)
    assert latest.status_code == 200
    assert "Corrected Dean response" in "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(latest.content)).pages
    )


def test_pdf_openapi_retains_binary_success_and_error_schemas():
    from compass.api.v1.router import api

    schema = json.loads(json.dumps(api.get_openapi_schema()))
    for path in (
        "/api/v1/exit-interviews/me/{exit_interview_id}/pdf",
        "/api/v1/exit-interviews/{exit_interview_id}/pdf",
    ):
        responses = schema["paths"][path]["get"]["responses"]
        assert responses["200"]["content"]["application/pdf"]["schema"] == {
            "type": "string",
            "format": "binary",
        }
        for status in (401, 403, 404, 409, 503):
            assert responses[str(status)]["content"]["application/json"]["schema"]["$ref"].endswith(
                "/APIErrorResponse"
            )
