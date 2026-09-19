from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.good_moral.services import GoodMoralDocumentUnavailable
from compass.reports.pdf import (
    StudentProfilingDocumentUnavailable,
    StudentProfilingPdfResult,
)
from compass.reports.graduate_tracer_xlsx import (
    GraduateTracerWorkbookUnavailable,
    GraduateTracerXlsxResult,
)
from compass.reports.xlsx import StudentProfilingXlsxResult


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name="Release",
        last_name="Operator",
    )


def make_head() -> User:
    user = make_user("report-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def make_dpo() -> User:
    user = make_user("release-dpo@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="DPO"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def release_context() -> dict[str, object]:
    return {
        "academic_year_id": str(uuid4()),
        "academic_year_label": "2026-2027",
        "campus_id": str(uuid4()),
        "campus_code": "MAIN",
        "college_id": str(uuid4()),
        "college_code": "CCMS",
        "program_id": str(uuid4()),
        "program_code": "BSIS",
        "year_level": 4,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "patch_target", "result", "artifact_format"),
    [
        (
            "/api/v1/reports/student-profile/pdf",
            "compass.reports.api.render_student_profiling_pdf",
            StudentProfilingPdfResult(
                pdf_bytes=b"%PDF synthetic",
                filename="student-profile.pdf",
                release_context=release_context(),
            ),
            "PDF",
        ),
        (
            "/api/v1/reports/student-profile/xlsx",
            "compass.reports.api.render_student_profiling_xlsx",
            StudentProfilingXlsxResult(
                xlsx_bytes=b"PK synthetic",
                filename="student-profile.xlsx",
                release_context=release_context(),
            ),
            "XLSX",
        ),
    ],
)
def test_student_profiling_successful_release_records_safe_audit_event(
    monkeypatch,
    path,
    patch_target,
    result,
    artifact_format,
):
    sync_policy()
    head = make_head()
    monkeypatch.setattr(patch_target, lambda **kwargs: result)

    response = auth_client(head).get(path)

    assert response.status_code == 200
    event = AuditEvent.objects.get(action="report.export_released")
    assert event.actor_user_id == head.pk
    assert event.target_type == "reports.studentprofiling"
    assert event.target_id == result.release_context["academic_year_id"]
    assert event.metadata == {
        "report_type": "student_profiling",
        "format": artifact_format,
        "academic_year_id": result.release_context["academic_year_id"],
        "academic_year_label": "2026-2027",
        "campus_id": result.release_context["campus_id"],
        "campus_code": "MAIN",
        "college_id": result.release_context["college_id"],
        "college_code": "CCMS",
        "program_id": result.release_context["program_id"],
        "program_code": "BSIS",
        "year_level": 4,
    }
    serialized = str(event.metadata).lower()
    assert "submitted_inventory_count" not in serialized
    assert "aggregate" not in serialized
    assert "inventory" not in serialized


@pytest.mark.django_db
def test_student_profiling_failed_authorization_or_render_does_not_log_release(monkeypatch):
    sync_policy()
    dpo = make_dpo()
    denied = auth_client(dpo).get("/api/v1/reports/student-profile/pdf")
    assert denied.status_code == 403
    assert not AuditEvent.objects.filter(action="report.export_released").exists()

    head = make_head()
    monkeypatch.setattr(
        "compass.reports.api.render_student_profiling_pdf",
        lambda **kwargs: (_ for _ in ()).throw(
            StudentProfilingDocumentUnavailable("synthetic render failure")
        ),
    )
    failed = auth_client(head).get("/api/v1/reports/student-profile/pdf")
    assert failed.status_code == 503
    assert not AuditEvent.objects.filter(action="report.export_released").exists()


@pytest.mark.django_db
def test_student_profiling_audit_failure_prevents_file_response(monkeypatch):
    sync_policy()
    head = make_head()
    result = StudentProfilingPdfResult(
        pdf_bytes=b"%PDF must not be released",
        filename="blocked.pdf",
        release_context=release_context(),
    )
    monkeypatch.setattr(
        "compass.reports.api.render_student_profiling_pdf",
        lambda **kwargs: result,
    )
    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit database unavailable")),
    )

    response = auth_client(head).get("/api/v1/reports/student-profile/pdf")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "release_audit_unavailable"
    assert response["Content-Type"].startswith("application/json")
    assert b"must not be released" not in response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("access_mode", "path_kind"),
    [("SELF", "self"), ("GCO", "gco")],
)
def test_good_moral_successful_pdf_release_records_safe_metadata(
    monkeypatch,
    access_mode,
    path_kind,
):
    sync_policy()
    request_id = uuid4()
    item = SimpleNamespace(pk=request_id, variant="GRADUATE")

    if path_kind == "self":
        actor = make_user("good-moral-student@example.edu", "STUDENT")
        path = f"/api/v1/good-moral/me/{request_id}/pdf"
        monkeypatch.setattr(
            "compass.good_moral.api.get_mine",
            lambda **kwargs: item,
        )
    else:
        actor = make_user("good-moral-counselor@example.edu", "COUNSELOR")
        path = f"/api/v1/good-moral/requests/{request_id}/pdf"
        monkeypatch.setattr(
            "compass.good_moral.api.get_request",
            lambda **kwargs: item,
        )

    monkeypatch.setattr(
        "compass.good_moral.api.render_certificate_pdf",
        lambda _item: b"%PDF synthetic certificate",
    )

    response = auth_client(actor).get(path)

    assert response.status_code == 200
    event = AuditEvent.objects.get(action="document.download_released")
    assert event.actor_user_id == actor.pk
    assert event.target_type == "goodmoral.request"
    assert event.target_id == str(request_id)
    assert event.metadata == {
        "document_type": "good_moral_certificate",
        "variant": "GRADUATE",
        "access_mode": access_mode,
    }
    serialized = str(event.metadata).lower()
    for forbidden in ("applicant", "receipt", "student", "certificate_contents"):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_good_moral_render_or_audit_failure_does_not_create_successful_release(monkeypatch):
    sync_policy()
    student = make_user("good-moral-failure@example.edu", "STUDENT")
    request_id = uuid4()
    item = SimpleNamespace(pk=request_id, variant="CURRENT_STUDENT")
    monkeypatch.setattr("compass.good_moral.api.get_mine", lambda **kwargs: item)

    monkeypatch.setattr(
        "compass.good_moral.api.render_certificate_pdf",
        lambda _item: (_ for _ in ()).throw(
            GoodMoralDocumentUnavailable("synthetic certificate render failure")
        ),
    )
    render_failed = auth_client(student).get(f"/api/v1/good-moral/me/{request_id}/pdf")
    assert render_failed.status_code == 503
    assert not AuditEvent.objects.filter(action="document.download_released").exists()

    monkeypatch.setattr(
        "compass.good_moral.api.render_certificate_pdf",
        lambda _item: b"%PDF must not escape",
    )
    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit write failed")),
    )
    audit_failed = auth_client(student).get(f"/api/v1/good-moral/me/{request_id}/pdf")
    assert audit_failed.status_code == 503
    assert audit_failed.json()["error"]["code"] == "release_audit_unavailable"
    assert audit_failed["Content-Type"].startswith("application/json")
    assert b"must not escape" not in audit_failed.content


@pytest.mark.django_db
def test_graduate_tracer_xlsx_release_records_only_safe_report_context(monkeypatch):
    sync_policy()
    head = make_head()
    result = GraduateTracerXlsxResult(
        xlsx_bytes=b"PK synthetic graduate tracer",
        filename="graduate-tracer-schema-v1.xlsx",
        release_context={
            "instrument_schema_version": 1,
            "submitted_from": "2026-01-01",
            "submitted_to": "2026-12-31",
        },
    )
    monkeypatch.setattr(
        "compass.reports.api.render_graduate_tracer_xlsx",
        lambda **kwargs: result,
    )

    response = auth_client(head).get(
        "/api/v1/reports/graduate-tracer/xlsx?submitted_from=2026-01-01&submitted_to=2026-12-31"
    )

    assert response.status_code == 200
    event = AuditEvent.objects.get(action="report.export_released")
    assert event.actor_user_id == head.pk
    assert event.target_type == "reports.graduatetracer"
    assert event.target_id == "1"
    assert event.metadata == {
        "report_type": "graduate_tracer",
        "format": "XLSX",
        "instrument_schema_version": 1,
        "submitted_from": "2026-01-01",
        "submitted_to": "2026-12-31",
    }
    serialized = str(event.metadata).lower()
    for forbidden in (
        "respondent",
        "employment",
        "salary",
        "student_id",
        "percentage",
        "count",
    ):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_graduate_tracer_denial_or_render_failure_creates_no_release_event(monkeypatch):
    sync_policy()
    dpo = make_dpo()
    denied = auth_client(dpo).get("/api/v1/reports/graduate-tracer/xlsx")
    assert denied.status_code == 403
    assert not AuditEvent.objects.filter(action="report.export_released").exists()

    head = make_head()
    monkeypatch.setattr(
        "compass.reports.api.render_graduate_tracer_xlsx",
        lambda **kwargs: (_ for _ in ()).throw(
            GraduateTracerWorkbookUnavailable("synthetic workbook failure")
        ),
    )
    failed = auth_client(head).get("/api/v1/reports/graduate-tracer/xlsx")
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "report_workbook_unavailable"
    assert not AuditEvent.objects.filter(action="report.export_released").exists()


@pytest.mark.django_db
def test_graduate_tracer_audit_failure_blocks_workbook_bytes(monkeypatch):
    sync_policy()
    head = make_head()
    result = GraduateTracerXlsxResult(
        xlsx_bytes=b"PK must not be released",
        filename="blocked.xlsx",
        release_context={
            "instrument_schema_version": 1,
            "submitted_from": None,
            "submitted_to": None,
        },
    )
    monkeypatch.setattr(
        "compass.reports.api.render_graduate_tracer_xlsx",
        lambda **kwargs: result,
    )
    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit database unavailable")),
    )

    response = auth_client(head).get("/api/v1/reports/graduate-tracer/xlsx")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "release_audit_unavailable"
    assert response["Content-Type"].startswith("application/json")
    assert b"must not be released" not in response.content
