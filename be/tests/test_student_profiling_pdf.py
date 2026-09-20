from __future__ import annotations

from decimal import Decimal
from importlib.resources import files
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.documents.assets import get_print_css
from compass.documents.rendering import (
    DocumentRenderError,
    DocumentRenderResult,
    render_document_html,
)
from compass.documents.services import update_branding_profile
from compass.documents.template_specs import LayoutFamily, get_template_spec
from compass.organization.models import Campus, College, CounselorResponsibility
from compass.reports import api as reports_api
from compass.reports import pdf as report_pdf
from compass.reports.pdf import (
    MAX_PROGRAM_COLUMNS_PER_TABLE,
    StudentProfilingDocumentUnavailable,
    StudentProfilingPdfResult,
    build_student_profiling_print_context,
    render_student_profiling_pdf,
    student_profiling_pdf_filename,
)
from compass.reports.services import (
    GLOBAL_REPORT_ACCESS_SCOPE,
    InvalidReportFilter,
    ReportConfigurationConflict,
    ReportNotFound,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Synthetic",
        last_name="User",
    )


def make_head(email: str = "head-pdf@example.edu") -> User:
    user = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def _organization_reference(code: str, name: str) -> dict[str, object]:
    return {"id": uuid4(), "code": code, "name": name}


def synthetic_report(
    *,
    program_count: int = 2,
    submitted_count: int | None = None,
    mode: str = "CURRENT",
) -> dict[str, object]:
    if submitted_count is None:
        submitted_count = max(program_count, 1)
    if submitted_count == 0:
        program_count = 0

    campus = _organization_reference("MAIN", "Main Campus")
    college = _organization_reference("CCMS", "College of Computing and Multimedia Studies")
    programs: list[dict[str, object]] = []
    for index in range(program_count):
        programs.append(
            {
                "key": f"program:{uuid4()}",
                "program_id": uuid4(),
                "code": f"P-{index + 1:02d}",
                "name": f"Synthetic Program {index + 1}",
                "college": college,
                "campus": campus,
                "is_legacy": False,
            }
        )

    program_counts = [{"program_key": program["key"], "count": 1} for program in programs]
    generic_row = {
        "key": "SYNTHETIC",
        "label": "Synthetic category",
        "total_count": submitted_count,
        "percentage": Decimal("100.00") if submitted_count else Decimal("0.00"),
        "program_counts": program_counts,
    }
    geography_row = {
        **generic_row,
        "key": "CITY_MUNICIPALITY:0517010000",
        "label": "Synthetic City",
        "city_municipality_psgc_code": "0517010000",
        "province_psgc_code": "0517000000",
        "province_name": "Synthetic Province",
        "region_psgc_code": "0500000000",
        "region_name": "Bicol Region",
    }

    section_labels = {
        "sex": "Distribution of Students based on Sex",
        "age": "Distribution of Students based on Age",
        "civil_status": "Distribution of Students based on Civil Status",
        "physical_disadvantage": "Distribution of Students based on PWD Status",
        "current_religion": "Distribution of Students based on Current Religion",
        "mother_life_status": "Distribution of Students based on Mother Life Status",
        "father_life_status": "Distribution of Students based on Father Life Status",
        "parent_family_status": "Distribution of Students based on Parent Family Status",
        "city_municipality": "Distribution of Students based on City / Municipality",
        "parent_annual_income": "Distribution of Students based on Parent Annual Income",
        "mother_occupation": "Distribution of Students based on Mother Occupation",
        "father_occupation": "Distribution of Students based on Father Occupation",
        "living_condition": "Distribution of Students based on Living Condition",
    }
    sections = {
        key: {
            "key": key,
            "label": label,
            "denominator": submitted_count,
            "rows": [dict(geography_row) if key == "city_municipality" else dict(generic_row)],
        }
        for key, label in section_labels.items()
    }

    if mode == "CURRENT":
        coverage = {
            "mode": "CURRENT",
            "eligible_student_count": max(submitted_count + 2, 2),
            "submitted_count": submitted_count,
            "draft_count": 1,
            "missing_count": 1,
            "applied_filters": ["academic_year_id"],
            "ignored_filters": ["program_id", "year_level"],
            "scope_note": "CANONICAL CURRENT COVERAGE SCOPE NOTE.",
        }
        historical_note = None
    else:
        coverage = {
            "mode": "HISTORICAL_LIMITED",
            "eligible_student_count": None,
            "submitted_count": submitted_count,
            "draft_count": 1,
            "missing_count": None,
            "applied_filters": ["academic_year_id"],
            "ignored_filters": ["campus_id", "college_id", "program_id", "year_level"],
            "scope_note": "CANONICAL HISTORICAL COVERAGE SCOPE NOTE.",
        }
        historical_note = "DUPLICATE HISTORICAL METHODOLOGY NOTE SHOULD NOT PRINT."

    return {
        "report_context": {
            "academic_year": {
                "id": uuid4(),
                "label": "2026-2027" if mode == "CURRENT" else "2025-2026",
                "is_current": mode == "CURRENT",
            },
            "campus": None,
            "college": None,
            "program": None,
            "year_level": None,
            "year_level_label": None,
            "submitted_inventory_count": submitted_count,
            "generated_at": timezone.now(),
        },
        "methodology": {
            "profile_population_note": "PROFILE POPULATION NOTE.",
            "coverage_note": "DUPLICATE GENERIC COVERAGE NOTE SHOULD NOT PRINT.",
            "historical_coverage_note": historical_note,
        },
        "program_columns": programs,
        "inventory_coverage": coverage,
        "sections": sections,
    }


def fake_pdf_result() -> StudentProfilingPdfResult:
    return StudentProfilingPdfResult(
        pdf_bytes=b"%PDF-" + (b"x" * 2048),
        filename="student-profile-2026-2027.pdf",
        release_context={
            "academic_year_id": str(uuid4()),
            "academic_year_label": "2026-2027",
            "campus_id": None,
            "campus_code": None,
            "college_id": None,
            "college_code": None,
            "program_id": None,
            "program_code": None,
            "year_level": None,
            "access_scope": GLOBAL_REPORT_ACCESS_SCOPE,
        },
    )


@pytest.mark.django_db
def test_pdf_endpoint_reuses_reports_view_without_recent_mfa(monkeypatch):
    sync_policy()
    monkeypatch.setattr(
        reports_api, "render_student_profiling_pdf", lambda **kwargs: fake_pdf_result()
    )

    head = make_head()
    counselor = make_user("ordinary-pdf@example.edu", "COUNSELOR")
    staff = make_user("staff-pdf@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student-pdf@example.edu", "STUDENT")
    admin = make_user("admin-pdf@example.edu", "IT_ADMIN")
    dpo = make_user("dpo-pdf@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )

    allowed = auth_client(head).get("/api/v1/reports/student-profile/pdf")
    assert allowed.status_code == 200
    assert allowed["Content-Type"] == "application/pdf"
    assert allowed["Content-Disposition"] == (
        'attachment; filename="student-profile-2026-2027.pdf"'
    )
    assert allowed.content.startswith(b"%PDF-")

    for user in (counselor, staff, student, admin, dpo):
        assert auth_client(user).get("/api/v1/reports/student-profile/pdf").status_code == 403
    assert Client().get("/api/v1/reports/student-profile/pdf").status_code == 401


@pytest.mark.django_db
def test_pdf_endpoint_forwards_same_report_filters(monkeypatch):
    sync_policy()
    head = make_head("head-pdf-filters@example.edu")
    client = auth_client(head)
    academic_year_id = uuid4()
    campus_id = uuid4()
    college_id = uuid4()
    program_id = uuid4()
    captured: list[dict[str, object]] = []

    def fake_render(**kwargs):
        captured.append(kwargs)
        return fake_pdf_result()

    monkeypatch.setattr(reports_api, "render_student_profiling_pdf", fake_render)
    response = client.get(
        "/api/v1/reports/student-profile/pdf",
        {
            "academic_year_id": academic_year_id,
            "campus_id": campus_id,
            "college_id": college_id,
            "program_id": program_id,
            "year_level": 3,
            "access_scope": GLOBAL_REPORT_ACCESS_SCOPE,
        },
    )
    assert response.status_code == 200
    assert captured == [
        {
            "academic_year_id": academic_year_id,
            "campus_id": campus_id,
            "college_id": college_id,
            "program_id": program_id,
            "year_level": 3,
            "access_scope": GLOBAL_REPORT_ACCESS_SCOPE,
        }
    ]

    captured.clear()
    assert client.get("/api/v1/reports/student-profile/pdf").status_code == 200
    assert captured == [
        {
            "academic_year_id": None,
            "campus_id": None,
            "college_id": None,
            "program_id": None,
            "year_level": None,
            "access_scope": GLOBAL_REPORT_ACCESS_SCOPE,
        }
    ]


@pytest.mark.django_db
def test_pdf_endpoint_passes_regular_counselor_college_scope(monkeypatch):
    sync_policy()
    counselor = make_user("scoped-pdf@example.edu", "COUNSELOR")
    campus = Campus.objects.create(code="PDF-SCOPE", name="PDF Scope Campus")
    college = College.objects.create(campus=campus, code="PDF-COL", name="PDF Scope College")
    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    captured: list[dict[str, object]] = []

    def fake_render(**kwargs):
        captured.append(kwargs)
        return fake_pdf_result()

    monkeypatch.setattr(reports_api, "render_student_profiling_pdf", fake_render)
    response = auth_client(counselor).get("/api/v1/reports/student-profile/pdf")
    assert response.status_code == 200
    scope = captured[0]["access_scope"]
    assert scope.is_global is False
    assert scope.college_ids == (college.pk,)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("exc", "status_code", "error_code"),
    [
        (ReportNotFound("missing filter"), 404, "report_filter_not_found"),
        (
            ReportConfigurationConflict("configuration conflict"),
            409,
            "report_configuration_conflict",
        ),
        (InvalidReportFilter("contradictory filters"), 422, "invalid_report_filter"),
        (
            StudentProfilingDocumentUnavailable("private renderer detail"),
            503,
            "report_document_unavailable",
        ),
    ],
)
def test_pdf_endpoint_maps_report_and_render_errors(
    monkeypatch,
    exc,
    status_code,
    error_code,
):
    sync_policy()
    head = make_head(f"head-pdf-error-{status_code}@example.edu")

    def fail(**kwargs):
        raise exc

    monkeypatch.setattr(reports_api, "render_student_profiling_pdf", fail)
    response = auth_client(head).get("/api/v1/reports/student-profile/pdf")
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    if status_code == 503:
        assert "private renderer detail" not in response.content.decode()


@pytest.mark.django_db
def test_rendered_html_uses_current_branding_report_context_and_required_sections():
    update_branding_profile(
        changes={
            "institution_name": "Synthetic Current University",
            "institution_short_name": "SCU",
            "former_institution_name": None,
        },
        context=AuditContext.system(),
    )
    report = synthetic_report(program_count=2)
    context = build_student_profiling_print_context(report)
    html, spec = render_document_html(
        "student_profiling_report",
        1,
        context=context,
    )

    assert spec.layout_family is LayoutFamily.REPORT
    assert spec.include_accreditation_footer is False
    assert spec.show_page_numbers is True
    assert "Synthetic Current University" in html
    assert "Guidance and Counseling Office" in html
    assert "Camarines Norte State College" not in html
    assert "STUDENTS&#x27; PROFILE" in html or "STUDENTS' PROFILE" in html
    assert "2026-2027" in html
    assert "All Campuses" in html
    assert "All Colleges" in html
    assert "All Programs" in html
    assert "All Year Levels" in html
    assert "Inventory Coverage" in html
    assert "Methodology / Coverage Note" in html
    assert "PROFILE POPULATION NOTE." in html
    assert html.count("CANONICAL CURRENT COVERAGE SCOPE NOTE.") == 1
    assert "DUPLICATE GENERIC COVERAGE NOTE SHOULD NOT PRINT." not in html
    assert "P-01" in html
    assert "P-02" in html
    assert "Total" in html
    assert "Percentage" in html

    for section in context["student_profile"]["sections"]:
        assert section["title"] in html


def test_template_is_portrait_local_and_registry_does_not_change_global_orientation():
    source = (
        files("compass.documents")
        .joinpath("templates")
        .joinpath("documents")
        .joinpath("reports")
        .joinpath("student_profile.html")
        .read_text(encoding="utf-8")
    )
    shared_css = get_print_css()
    spec = get_template_spec("student_profiling_report", 1)

    assert "size: A4 portrait;" in source
    assert "landscape" not in shared_css.lower()
    assert "@page" in shared_css
    assert spec.layout_family is LayoutFamily.REPORT
    assert spec.show_page_numbers is True
    assert spec.include_accreditation_footer is False
    assert "CAMARINES NORTE STATE COLLEGE" not in source
    assert "CNSC" not in source

    good_moral = get_template_spec("good_moral_current_student", 1)
    assert good_moral.layout_family is LayoutFamily.CERTIFICATE
    assert good_moral.show_page_numbers is False


def test_presentation_chunks_programs_by_key_not_positional_alignment():
    report = synthetic_report(program_count=5, submitted_count=5)
    programs = report["program_columns"]
    section = report["sections"]["sex"]
    row = section["rows"][0]

    expected = {str(program["key"]): 100 + index for index, program in enumerate(programs)}
    row["program_counts"] = list(
        reversed([{"program_key": key, "count": value} for key, value in expected.items()])
    )
    row["total_count"] = 777
    row["percentage"] = Decimal("32.72")

    context = build_student_profiling_print_context(report)
    sex = next(item for item in context["student_profile"]["sections"] if item["key"] == "sex")
    chunks = sex["chunks"]

    assert MAX_PROGRAM_COLUMNS_PER_TABLE == 2
    assert len(chunks) == 3
    seen: list[str] = []
    for chunk in chunks:
        for program, count in zip(
            chunk["programs"],
            chunk["rows"][0]["program_counts"],
            strict=True,
        ):
            assert count["program_key"] == program["key"]
            assert count["count"] == expected[program["key"]]
            seen.append(program["key"])
        assert chunk["rows"][0]["total_count"] == 777
        assert chunk["rows"][0]["percentage"] == "32.72%"

    assert seen == [program["key"] for program in context["student_profile"]["program_legend"]]
    assert len(seen) == len(set(seen)) == 5


def test_current_and_historical_coverage_are_mode_specific_and_deduplicated():
    current = build_student_profiling_print_context(
        synthetic_report(program_count=2, submitted_count=2, mode="CURRENT")
    )["student_profile"]
    current_rows = {row["label"]: row["value"] for row in current["coverage"]["rows"]}
    assert current_rows["Eligible Students"] == 4
    assert current_rows["Submitted"] == 2
    assert current_rows["Draft"] == 1
    assert current_rows["Without Individual Inventory"] == 1
    assert "Program" in current["coverage"]["ignored_filter_note"]
    assert "Year Level" in current["coverage"]["ignored_filter_note"]

    historical = build_student_profiling_print_context(
        synthetic_report(program_count=2, submitted_count=2, mode="HISTORICAL_LIMITED")
    )["student_profile"]
    historical_rows = {row["label"]: row["value"] for row in historical["coverage"]["rows"]}
    assert "Eligible Students" not in historical_rows
    assert historical_rows["Submitted"] == 2
    assert historical_rows["Draft"] == 1
    assert historical_rows["Without Individual Inventory"] == (
        "Not available from current COMPASS data"
    )
    assert historical["coverage"]["scope_note"] == ("CANONICAL HISTORICAL COVERAGE SCOPE NOTE.")
    assert "Campus" in historical["coverage"]["ignored_filter_note"]
    assert "College" in historical["coverage"]["ignored_filter_note"]


@pytest.mark.django_db
def test_historical_html_prints_scope_once_without_duplicate_methodology():
    report = synthetic_report(program_count=2, mode="HISTORICAL_LIMITED")
    html, _ = render_document_html(
        "student_profiling_report",
        1,
        context=build_student_profiling_print_context(report),
    )
    assert html.count("CANONICAL HISTORICAL COVERAGE SCOPE NOTE.") == 1
    assert "DUPLICATE GENERIC COVERAGE NOTE SHOULD NOT PRINT." not in html
    assert "DUPLICATE HISTORICAL METHODOLOGY NOTE SHOULD NOT PRINT." not in html
    assert "Not available from current COMPASS data" in html


@pytest.mark.django_db
def test_empty_report_renders_context_coverage_and_methodology_without_tables():
    report = synthetic_report(program_count=0, submitted_count=0)
    context = build_student_profiling_print_context(report)
    profile = context["student_profile"]

    assert profile["sections"] == []
    assert profile["empty_message"] == (
        "No submitted Individual Inventories matched the selected profile filters."
    )

    html, _ = render_document_html(
        "student_profiling_report",
        1,
        context=context,
    )
    assert profile["empty_message"] in html
    assert "Inventory Coverage" in html
    assert "PROFILE POPULATION NOTE." in html
    assert '<table class="report-table">' not in html


@pytest.mark.django_db
def test_print_context_drops_unexpected_student_level_private_values():
    report = synthetic_report(program_count=2)
    report["private_student_number"] = "PRIVATE-STUDENT-NUMBER"
    report["private_email"] = "private-student@example.edu"
    report["sections"]["sex"]["rows"][0]["private_narrative"] = "PRIVATE COUNSELING NARRATIVE"

    html, _ = render_document_html(
        "student_profiling_report",
        1,
        context=build_student_profiling_print_context(report),
    )
    for secret in (
        "PRIVATE-STUDENT-NUMBER",
        "private-student@example.edu",
        "PRIVATE COUNSELING NARRATIVE",
    ):
        assert secret not in html


@pytest.mark.django_db
def test_pdf_does_not_reintroduce_historical_report_terms_or_fake_qms_identity():
    report = synthetic_report(program_count=2)
    context = build_student_profiling_print_context(report)
    html, _ = render_document_html(
        "student_profiling_report",
        1,
        context=context,
    )

    for stale in (
        "Freshmen",
        "Freshman",
        "Sophomore",
        "Junior",
        "Senior",
        "Gender",
        "Nort specified",
        "20 & Above",
        "Boarding House / Dormitory",
        "CNSC-OP-GCO-01F5",
        "Rev. 0",
    ):
        assert stale not in html

    assert "Distribution of Students based on Sex" in html
    assert all(
        row["label"] != "Without Individual Inventory"
        for section in context["student_profile"]["sections"]
        for chunk in section["chunks"]
        for row in chunk["rows"]
    )


def test_filename_is_deterministic_sanitized_and_non_pii():
    assert student_profiling_pdf_filename("2026-2027") == "student-profile-2026-2027.pdf"
    assert student_profiling_pdf_filename(" AY 2026/2027 ") == ("student-profile-AY-2026-2027.pdf")
    assert "/" not in student_profiling_pdf_filename("2026/2027")
    assert "PRIVATE-STUDENT" not in student_profiling_pdf_filename("2026-2027")


def test_render_service_calls_canonical_builder_once_and_preserves_filter_arguments(monkeypatch):
    report = synthetic_report(program_count=2)
    calls: list[dict[str, object]] = []
    ids = {
        "academic_year_id": uuid4(),
        "campus_id": uuid4(),
        "college_id": uuid4(),
        "program_id": uuid4(),
        "year_level": 4,
    }

    def fake_builder(**kwargs):
        calls.append(kwargs)
        return report

    def fake_renderer(template_key, template_version, *, context):
        assert template_key == "student_profiling_report"
        assert template_version == 1
        assert context["student_profile"]["sections"]
        return DocumentRenderResult(
            pdf_bytes=b"%PDF-" + (b"x" * 2048),
            template_key=template_key,
            template_version=template_version,
        )

    monkeypatch.setattr(report_pdf, "build_student_profiling_report", fake_builder)
    monkeypatch.setattr(report_pdf, "render_document_pdf", fake_renderer)

    result = render_student_profiling_pdf(**ids)
    assert calls == [ids]
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.filename == "student-profile-2026-2027.pdf"


def test_render_service_wraps_document_errors_without_exposing_renderer_detail(monkeypatch):
    monkeypatch.setattr(
        report_pdf,
        "build_student_profiling_report",
        lambda **kwargs: synthetic_report(program_count=2),
    )

    def fail_renderer(*args, **kwargs):
        raise DocumentRenderError("/private/path/chromium stack detail")

    monkeypatch.setattr(report_pdf, "render_document_pdf", fail_renderer)
    with pytest.raises(
        StudentProfilingDocumentUnavailable,
        match="temporarily unavailable",
    ) as raised:
        render_student_profiling_pdf()
    assert "/private/path" not in str(raised.value)


@pytest.mark.django_db
def test_real_chromium_renders_portrait_multi_chunk_student_profile_pdf(monkeypatch):
    report = synthetic_report(program_count=5, submitted_count=5)
    monkeypatch.setattr(
        report_pdf,
        "build_student_profiling_report",
        lambda **kwargs: report,
    )

    result = render_student_profiling_pdf()
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert len(result.pdf_bytes) > 10_000
    assert result.filename == "student-profile-2026-2027.pdf"
