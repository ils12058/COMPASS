from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from importlib.resources import files
from io import BytesIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.authentication.sessions import create_auth_session
from compass.documents.assets import get_print_css
from compass.documents.rendering import (
    DocumentRenderError,
    DocumentRenderResult,
    render_document_html,
)
from compass.documents.template_specs import LayoutFamily, get_template_spec
from compass.organization.models import Campus, College, CounselorResponsibility
from compass.reports import api as reports_api
from compass.reports import pdf as report_pdf
from compass.reports.pdf import (
    MAX_CROSS_TAB_PROGRAMS,
    SECTION_ORDER,
    StudentProfilingDocumentUnavailable,
    StudentProfilingPdfResult,
    build_student_profiling_print_context,
    render_student_profiling_pdf,
    student_profiling_pdf_filename,
)
from compass.reports.services import (
    GLOBAL_REPORT_ACCESS_SCOPE,
    LEGACY_KEY,
    LEGACY_LABEL,
    LEGACY_PROGRAM_KEY,
    InvalidReportFilter,
    ReportAccessScope,
    ReportConfigurationConflict,
    ReportNotFound,
    calculate_percentage,
    parent_income_bracket_legend,
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


# Canonical response categories per section, in canonical row order. LEGACY_KEY rows follow.
SECTION_CATEGORIES = {
    "sex": [("MALE", "Male"), ("FEMALE", "Female")],
    "age": [("18", "18"), ("19", "19"), ("20", "20")],
    "civil_status": [
        ("SINGLE", "Single"),
        ("MARRIED", "Married"),
        ("SOLO_PARENT", "Solo Parent"),
        ("OTHER", "Other"),
        ("NOT_SPECIFIED", "Not specified"),
    ],
    "physical_disadvantage": [
        ("PWD", "PWD"),
        ("NON_PWD", "Non-PWD"),
        ("NOT_SPECIFIED", "Not specified"),
    ],
    "current_religion": [
        ("ROMAN_CATHOLIC", "Roman Catholic"),
        ("BORN_AGAIN", "Born Again"),
        ("NOT_SPECIFIED", "Not specified"),
    ],
    "mother_life_status": [
        ("LIVING", "Living"),
        ("DECEASED", "Deceased"),
        ("NOT_SPECIFIED", "Not specified"),
    ],
    "father_life_status": [
        ("LIVING", "Living"),
        ("DECEASED", "Deceased"),
        ("NOT_SPECIFIED", "Not specified"),
    ],
    "parent_family_status": [("MARRIED", "Married"), ("WIDOWED", "Widowed")],
    "parent_annual_income": [
        ("POOR", "Poor"),
        ("LOW_INCOME", "Low Income"),
        ("NONE", "None"),
        ("NOT_SPECIFIED", "Not specified"),
    ],
    "mother_occupation": [("FARMER", "Farmer"), ("NONE", "None")],
    "father_occupation": [("FARMER", "Farmer"), ("LABORER", "Laborer")],
    "living_condition": [
        ("OWN_HOUSE", "Own House"),
        ("BOARDING_HOUSE", "Boarding House"),
        ("WITH_RELATIVES", "With Relatives"),
    ],
}

SECTION_LABELS = {
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


def _split(total: int, parts: int) -> list[int]:
    """Deterministically spread a Program total over categories, largest share first."""

    base, extra = divmod(total, parts)
    return [base + (1 if index < extra else 0) for index in range(parts)]


def _distribution(
    categories: list[tuple[str, str]],
    programs: list[dict[str, object]],
    population: int,
    *,
    legacy_per_program: int = 0,
    extra: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    counts: dict[str, dict[str, int]] = {key: {} for key, _ in categories}
    counts[LEGACY_KEY] = {}
    for program in programs:
        total = int(program["submitted_inventory_count"])
        legacy = min(legacy_per_program, total)
        for (key, _), count in zip(
            categories, _split(total - legacy, len(categories)), strict=True
        ):
            counts[key][str(program["key"])] = count
        counts[LEGACY_KEY][str(program["key"])] = legacy
    rows = []
    for key, label in [*categories, (LEGACY_KEY, LEGACY_LABEL)]:
        program_counts = [
            {"program_key": str(program["key"]), "count": counts[key].get(str(program["key"]), 0)}
            for program in programs
        ]
        total = sum(item["count"] for item in program_counts)
        row = {
            "key": key,
            "label": label,
            "total_count": total,
            "percentage": calculate_percentage(total, population),
            "program_counts": program_counts,
        }
        if extra is not None:
            row.update(extra)
        rows.append(row)
    return rows


def _geography(
    programs: list[dict[str, object]],
    population: int,
    city_count: int,
) -> list[dict[str, object]]:
    cities = [
        (f"05160{index:02d}000", f"Synthetic Municipality {index + 1:02d}")
        for index in range(city_count)
    ]
    categories = [(f"CITY_MUNICIPALITY:{code}", name) for code, name in cities]
    rows = _distribution(categories, programs, population)
    geography_rows = []
    for row, (code, _) in zip(rows, [*cities, (None, None)], strict=True):
        is_city = code is not None
        geography_rows.append(
            {
                **row,
                "city_municipality_psgc_code": code,
                "province_psgc_code": "0516000000" if is_city else None,
                "province_name": "Synthetic Province" if is_city else None,
                "region_psgc_code": "0500000000" if is_city else None,
                "region_name": "Synthetic Region" if is_city else None,
            }
        )
    return geography_rows


def synthetic_report(
    *,
    program_count: int = 2,
    submitted_count: int | None = None,
    mode: str = "CURRENT",
    colleges: list[tuple[str, int]] | None = None,
    legacy_inventories: int = 0,
    legacy_values_per_program: int = 0,
    city_count: int = 2,
    scope_colleges: list[str] | None = None,
    long_program_codes: bool = False,
) -> dict[str, object]:
    """Return an internally consistent canonical report built only from synthetic data.

    ``colleges`` lists (College code, Program count); by default one College holds
    ``program_count`` Programs. ``submitted_count`` is spread across Programs in order.
    """

    if colleges is None:
        colleges = [("CCMS", program_count)] if program_count else []
    total_programs = sum(count for _, count in colleges)
    if submitted_count is None:
        submitted_count = max(total_programs, 1) + legacy_inventories
    if submitted_count == 0:
        colleges = []
        total_programs = 0
        legacy_inventories = 0

    campus = _organization_reference("MAIN", "Main Campus")
    programs: list[dict[str, object]] = []
    assigned = (
        _split(submitted_count - legacy_inventories, total_programs) if total_programs else []
    )
    index = 0
    college_refs = {}
    for college_code, count in colleges:
        college = _organization_reference(college_code, f"College of Synthetic {college_code}")
        college_refs[college_code] = college
        for program_index in range(count):
            code = f"{college_code}-P{program_index + 1:02d}"
            if long_program_codes:
                code = f"{code}-EXTENDED-CURRICULUM"[:32]
            programs.append(
                {
                    "key": f"program:{uuid4()}",
                    "program_id": uuid4(),
                    "code": code,
                    "name": f"Synthetic Program {college_code} {program_index + 1}",
                    "submitted_inventory_count": assigned[index],
                    "college": college,
                    "campus": campus,
                    "is_legacy": False,
                }
            )
            index += 1
    if legacy_inventories:
        programs.append(
            {
                "key": LEGACY_PROGRAM_KEY,
                "program_id": None,
                "code": None,
                "name": LEGACY_LABEL,
                "submitted_inventory_count": legacy_inventories,
                "college": None,
                "campus": None,
                "is_legacy": True,
            }
        )

    sections = {}
    for key in SECTION_LABELS:
        if key == "city_municipality":
            rows = _geography(programs, submitted_count, city_count)
        else:
            rows = _distribution(
                SECTION_CATEGORIES[key],
                programs,
                submitted_count,
                legacy_per_program=legacy_values_per_program,
            )
        if submitted_count == 0 and key in ("age", "city_municipality"):
            rows = []
        sections[key] = {
            "key": key,
            "label": SECTION_LABELS[key],
            "denominator": submitted_count,
            "rows": rows,
        }

    if mode == "CURRENT":
        coverage = {
            "mode": "CURRENT",
            "eligible_student_count": submitted_count + 3,
            "submitted_count": submitted_count,
            "draft_count": 1,
            "missing_count": 2,
            "applied_filters": ["academic_year_id"],
            "ignored_filters": [],
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
            "ignored_filters": [],
            "scope_note": "CANONICAL HISTORICAL COVERAGE SCOPE NOTE.",
        }
        historical_note = "CANONICAL HISTORICAL METHODOLOGY NOTE."
    coverage["reconciliation"] = {
        "profile_submitted_count": submitted_count,
        "coverage_submitted_count": submitted_count,
        "in_both_count": submitted_count,
        "profile_only_count": 0,
        "coverage_only_count": 0,
    }

    if scope_colleges is None:
        reporting_scope = {"is_global": True, "colleges": []}
    else:
        reporting_scope = {
            "is_global": False,
            "colleges": [
                {**college_refs.get(code, _organization_reference(code, code)), "campus": campus}
                for code in scope_colleges
            ],
        }

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
            "reporting_scope": reporting_scope,
            "generated_at": datetime(2026, 10, 11, 7, 0, tzinfo=UTC),
        },
        "methodology": {
            "profile_population_note": "PROFILE POPULATION NOTE.",
            "coverage_note": "CANONICAL CURRENT COVERAGE NOTE.",
            "historical_coverage_note": historical_note,
            "access_scope_note": "ACCESS SCOPE NOTE SHOULD NOT PRINT.",
        },
        "disclosure_warnings": [],
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
        },
    )


def profile_of(report: dict[str, object]) -> dict[str, object]:
    return build_student_profiling_print_context(report)["student_profile"]


def rendered_html(report: dict[str, object]) -> str:
    html, _ = render_document_html(
        "student_profiling_report",
        1,
        context=build_student_profiling_print_context(report),
    )
    return html


def cell_texts(row: dict[str, object]) -> list[str]:
    return [str(cell["text"]) for cell in row["cells"]]


def all_tables(profile: dict[str, object]) -> list[dict[str, object]]:
    tables = [table for part in profile["parts"] for table in part["tables"]]
    for group in profile["appendix"]:
        tables.extend(group["tables"])
    return tables


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
def test_rendered_html_is_table_first_with_branding_overview_and_numbered_tables():
    report = synthetic_report(program_count=2, submitted_count=10)
    html = rendered_html(report)
    profile = profile_of(report)

    spec = get_template_spec("student_profiling_report", 1)
    assert spec.layout_family is LayoutFamily.REPORT
    assert spec.include_accreditation_footer is True
    assert spec.show_page_numbers is True
    assert "University of Camarines Norte" in html
    assert "Guidance and Counseling Office" in html
    assert "STUDENT PROFILE REPORT" in html
    assert "Individual Inventory-Based Student Profiling" in html
    for heading in (
        "1. Report Overview",
        "2. Populations in This Report",
        "2.1 Submitted Inventory Profile Population (n = 10)",
        "2.2 Current Student Inventory Coverage",
        "3. Methodology and Data Notes",
        "4. Demographics",
        "5. Family and Household",
        "6. Geographic Distribution",
        "Appendix A. Program Breakdown",
    ):
        assert heading in html
    metadata = {cell_texts(row)[0]: cell_texts(row)[1] for row in profile["metadata"]["rows"]}
    assert metadata["Academic Year"] == "2026-2027 (current Academic Year)"
    assert metadata["Campus filter"] == "All Campuses"
    assert metadata["College filter"] == "All Colleges"
    assert metadata["Program filter"] == "All Programs"
    assert metadata["Year Level filter"] == "All Year Levels"
    assert metadata["Reporting Scope"] == "Institution-wide"
    assert metadata["Submitted Inventory Profile Population"] == (
        "10 submitted Individual Inventories"
    )
    # Institutional civil time, not the runtime or UTC clock.
    assert metadata["Generated At"] == "11 October 2026, 3:00 PM (Asia/Manila)"
    assert build_student_profiling_print_context(report)["document_pdf_footer_label"] == (
        "Student Profile Report · Academic Year 2026-2027 · "
        "Generated 11 October 2026, 3:00 PM (Asia/Manila)"
    )

    titles = [table["title"] for part in profile["parts"] for table in part["tables"]]
    assert titles[0] == "Distribution of Students by Sex"
    assert len(titles) == len(SECTION_ORDER) == 13
    assert [table["number"] for part in profile["parts"] for table in part["tables"]] == [
        f"Table {index}." for index in range(1, 14)
    ]
    assert "(continued)" not in html
    assert "PROFILE POPULATION NOTE." in html
    assert "ACCESS SCOPE NOTE SHOULD NOT PRINT." not in html
    assert html.count("CANONICAL CURRENT COVERAGE NOTE.") == 1


def test_template_is_portrait_local_without_continuation_markers():
    templates = files("compass.documents").joinpath("templates", "documents", "reports")
    source = templates.joinpath("student_profile.html").read_text(encoding="utf-8")
    partial = templates.joinpath("_student_profile_table.html").read_text(encoding="utf-8")
    shared_css = get_print_css()
    spec = get_template_spec("student_profiling_report", 1)

    assert "size: A4 portrait;" in source
    assert "landscape" not in shared_css.lower()
    assert "@page" in shared_css
    assert spec.layout_family is LayoutFamily.REPORT
    assert spec.show_page_numbers is True
    assert spec.include_accreditation_footer is True
    for template in (source, partial):
        assert "continued" not in template.lower()
        assert "CAMARINES NORTE STATE COLLEGE" not in template
        assert "CNSC" not in template
    # Long tables repeat headers instead of printing continuation chunks.
    assert "display: table-header-group;" in source

    good_moral = get_template_spec("good_moral_current_student", 1)
    assert good_moral.layout_family is LayoutFamily.CERTIFICATE
    assert good_moral.show_page_numbers is False


def test_overall_tables_print_canonical_counts_total_row_and_omit_zero_legacy():
    report = synthetic_report(program_count=2, submitted_count=7)
    profile = profile_of(report)
    sex = profile["parts"][0]["tables"][0]
    rows = [cell_texts(row) for row in sex["rows"]]

    canonical = {row["key"]: row for row in report["sections"]["sex"]["rows"]}
    assert rows == [
        ["Male", "4", f"{canonical['MALE']['percentage']:.2f}%"],
        ["Female", "3", f"{canonical['FEMALE']['percentage']:.2f}%"],
        ["Total", "7", "100.00%"],
    ]
    assert sex["rows"][-1]["kind"] == "total"
    assert sex["population_note"] == "Population: submitted Individual Inventories (n = 7)"
    assert [column["label"] for column in sex["columns"]] == ["Sex", "Frequency", "Percentage"]

    # Every controlled response prints, including zero rows; legacy appears only when it occurs.
    civil = profile["parts"][0]["tables"][2]
    civil_labels = [cell_texts(row)[0] for row in civil["rows"]]
    assert civil_labels == ["Single", "Married", "Solo Parent", "Other", "Not specified", "Total"]
    assert LEGACY_LABEL not in civil_labels

    with_legacy = profile_of(
        synthetic_report(program_count=2, submitted_count=8, legacy_values_per_program=1)
    )
    labels = [cell_texts(row)[0] for row in with_legacy["parts"][0]["tables"][2]["rows"]]
    assert labels[-2:] == [LEGACY_LABEL, "Total"]


def test_geography_overall_table_keeps_province_and_region_context():
    profile = profile_of(synthetic_report(program_count=1, submitted_count=4, city_count=3))
    table = profile["parts"][2]["tables"][0]
    assert [column["label"] for column in table["columns"]] == [
        "City / Municipality",
        "Province",
        "Region",
        "Frequency",
        "Percentage",
    ]
    first = cell_texts(table["rows"][0])
    assert first[:3] == ["Synthetic Municipality 01", "Synthetic Province", "Synthetic Region"]
    assert cell_texts(table["rows"][-1]) == ["Total", "", "", "4", "100.00%"]


def test_college_cross_tab_matches_programs_by_key_and_uses_college_denominator():
    report = synthetic_report(colleges=[("CCMS", 3)], submitted_count=10)
    programs = report["program_columns"]
    expected_male = {
        str(program["key"]): _split(int(program["submitted_inventory_count"]), 2)[0]
        for program in programs
    }
    # Canonical identity is the Program key; array position carries no meaning.
    for section in report["sections"].values():
        for row in section["rows"]:
            row["program_counts"] = list(reversed(row["program_counts"]))

    profile = profile_of(report)
    assert len(profile["appendix"]) == 1
    sex_table = profile["appendix"][0]["tables"][0]
    headers = [column["label"] for column in sex_table["columns"]]
    assert headers == ["Sex", "CCMS-P01", "CCMS-P02", "CCMS-P03", "CCMS Total", "% of CCMS"]
    male = cell_texts(sex_table["rows"][0])
    assert male[1:4] == [str(expected_male[str(program["key"])]) for program in programs]
    male_total = sum(expected_male.values())
    assert male[4] == str(male_total)
    assert male[5] == f"{calculate_percentage(male_total, 10):.2f}%"
    assert cell_texts(sex_table["rows"][-1]) == [
        "Total",
        *[str(program["submitted_inventory_count"]) for program in programs],
        "10",
        "100.00%",
    ]
    assert sex_table["population_note"] == "College population: n = 10"


def test_programs_are_never_chunked_and_many_programs_use_long_form():
    at_limit = profile_of(
        synthetic_report(colleges=[("WIDE", MAX_CROSS_TAB_PROGRAMS)], submitted_count=40)
    )
    tables = at_limit["appendix"][0]["tables"]
    assert len(tables) == len(SECTION_ORDER)
    program_headers = [
        column["label"] for column in tables[0]["columns"] if column["label"].startswith("WIDE-P")
    ]
    assert len(program_headers) == MAX_CROSS_TAB_PROGRAMS

    many = MAX_CROSS_TAB_PROGRAMS + 3
    report = synthetic_report(colleges=[("MANY", many)], submitted_count=64)
    profile = profile_of(report)
    tables = profile["appendix"][0]["tables"]
    assert len(tables) == 2 * len(SECTION_ORDER)
    summary, long_form = tables[0], tables[1]
    assert summary["title"] == "MANY — Sex (College total)"
    assert [column["label"] for column in summary["columns"]] == [
        "Sex",
        "MANY Total",
        "% of MANY",
    ]
    assert long_form["title"] == "MANY — Sex by Program"
    assert [column["label"] for column in long_form["columns"]] == [
        "Program",
        "Sex",
        "Frequency",
        "Program n",
        "% of Program",
    ]
    # One unbreakable block per Program, each ending with its own total.
    assert len(long_form["row_blocks"]) == many
    for program, block in zip(report["program_columns"], long_form["row_blocks"], strict=True):
        n = int(program["submitted_inventory_count"])
        assert cell_texts(block[-1]) == [program["code"], "Total", str(n), str(n), "100.00%"]
        assert sum(int(cell_texts(row)[2]) for row in block[:-1]) == n
        for row in block[:-1]:
            frequency = int(cell_texts(row)[2])
            assert cell_texts(row)[4] == f"{calculate_percentage(frequency, n):.2f}%"


def test_multiple_colleges_reconcile_to_college_and_institution_totals():
    report = synthetic_report(
        colleges=[("CAS", 1), ("CCMS", 2), ("COED", 3)],
        submitted_count=30,
        legacy_inventories=3,
    )
    profile = profile_of(report)
    summary_rows = [cell_texts(row) for row in profile["college_summary"]["rows"]]
    assert [row[0] for row in summary_rows] == [
        "CAS — College of Synthetic CAS",
        "CCMS — College of Synthetic CCMS",
        "COED — College of Synthetic COED",
        "Unclassified / Legacy",
        "Total",
    ]
    assert sum(int(row[3]) for row in summary_rows[:-1]) == int(summary_rows[-1][3]) == 30
    assert summary_rows[-1][4] == "100.00%"

    by_college: dict[str, int] = {}
    for program in report["program_columns"]:
        college = program["college"]["code"] if program["college"] else "Unclassified / Legacy"
        by_college[college] = by_college.get(college, 0) + int(program["submitted_inventory_count"])
    assert [
        group["heading"].split(". ", 1)[1].split(" — ")[0] for group in profile["appendix"]
    ] == [
        "CAS",
        "CCMS",
        "COED",
        "Unclassified / Legacy",
    ]
    for group in profile["appendix"]:
        code = group["heading"].split(". ", 1)[1].split(" — ")[0]
        for table in group["tables"]:
            total_row = cell_texts(table["rows"][-1])
            # The College table total is the College population, never the institution total.
            assert total_row[-2] == str(by_college[code])
            assert total_row[-1] == "100.00%"

    program_table = profile["program_population"]
    assert program_table["title"] == "Submitted Inventory Profile Population by College and Program"
    assert cell_texts(program_table["rows"][-1])[2:] == ["30", "100.00%"]
    unclassified = [
        row for row in program_table["rows"] if cell_texts(row)[0] == "Unclassified / Legacy"
    ]
    assert cell_texts(unclassified[0])[1:3] == ["No Program recorded", "3"]


def test_unclassified_legacy_group_is_kept_and_not_attributed_to_a_college():
    profile = profile_of(
        synthetic_report(colleges=[("CCMS", 2)], submitted_count=12, legacy_inventories=4)
    )
    legacy = profile["appendix"][-1]
    assert legacy["heading"].endswith("Unclassified / Legacy — Inventories without a Program")
    table = legacy["tables"][0]
    assert [column["label"] for column in table["columns"]] == ["Sex", "Inventories", "% of group"]
    assert cell_texts(table["rows"][-1]) == ["Total", "4", "100.00%"]
    assert table["population_note"] == (
        "Population: Inventories without a recorded Program (n = 4)"
    )


def test_single_program_report_skips_redundant_appendix():
    profile = profile_of(synthetic_report(program_count=1, submitted_count=6))
    assert profile["appendix"] == []
    assert profile["program_population"] is None
    html = rendered_html(synthetic_report(program_count=1, submitted_count=6))
    assert "Appendix A. Program Breakdown" not in html
    terms = [item["term"] for item in profile["methodology"]]
    assert "Program breakdown" in terms


def test_current_and_historical_coverage_never_fabricate_historical_counts():
    current = profile_of(synthetic_report(program_count=2, submitted_count=5))
    assert current["coverage"]["title"] == "Current Student Inventory Coverage"
    status = [cell_texts(row) for row in current["coverage"]["status"]["rows"]]
    assert status == [
        ["Eligible current Students", "8"],
        ["Submitted", "5"],
        ["Draft", "1"],
        ["Without Individual Inventory", "2"],
    ]

    historical_report = synthetic_report(
        program_count=2, submitted_count=5, mode="HISTORICAL_LIMITED"
    )
    historical_report["methodology"]["historical_coverage_note"] = "HISTORICAL NOTE."
    historical = profile_of(historical_report)
    assert historical["coverage"]["title"] == (
        "Inventory Coverage — Historical Academic Year (limited)"
    )
    rows = {
        cell_texts(row)[0]: cell_texts(row)[1] for row in historical["coverage"]["status"]["rows"]
    }
    assert rows["Submitted"] == "5"
    assert rows["Eligible Students"] == "Not available — no historical eligibility roster"
    assert rows["Without Individual Inventory"] == (
        "Not available — no historical eligibility roster"
    )
    assert historical["coverage"]["note"] == "HISTORICAL NOTE."
    html = rendered_html(historical_report)
    assert "HISTORICAL NOTE." in html
    assert "CANONICAL CURRENT COVERAGE NOTE." not in html


def test_reconciliation_table_explains_population_differences():
    report = synthetic_report(program_count=2, submitted_count=10)
    report["inventory_coverage"].update(
        {"eligible_student_count": 14, "submitted_count": 9, "draft_count": 2, "missing_count": 3}
    )
    report["inventory_coverage"]["reconciliation"] = {
        "profile_submitted_count": 10,
        "coverage_submitted_count": 9,
        "in_both_count": 8,
        "profile_only_count": 2,
        "coverage_only_count": 1,
    }
    rows = [cell_texts(row) for row in profile_of(report)["coverage"]["reconciliation"]["rows"]]
    assert [row[1] for row in rows] == ["10", "8", "2", "9", "8", "1"]
    assert rows[2][0].startswith("Student not counted in Current Coverage")
    assert rows[5][0].startswith("Inventory outside the profile population")

    report["inventory_coverage"]["reconciliation"]["in_both_count"] = 7
    with pytest.raises(StudentProfilingDocumentUnavailable, match="reconciliation"):
        build_student_profiling_print_context(report)


def test_filter_table_and_metadata_distinguish_selected_filters_from_reporting_scope():
    report = synthetic_report(
        colleges=[("CAS", 1), ("CCMS", 2)],
        submitted_count=9,
        scope_colleges=["CAS", "CCMS"],
    )
    report["report_context"]["year_level"] = 2
    report["report_context"]["year_level_label"] = "2nd Year"
    report["inventory_coverage"]["applied_filters"] = ["academic_year_id", "access_scope"]
    report["inventory_coverage"]["ignored_filters"] = ["year_level"]
    profile = profile_of(report)

    metadata = {cell_texts(row)[0]: cell_texts(row)[1] for row in profile["metadata"]["rows"]}
    assert metadata["College filter"] == "All Colleges within the reporting scope"
    assert metadata["Reporting Scope"] == (
        "Limited to assigned Colleges: CAS — College of Synthetic CAS (Main Campus); "
        "CCMS — College of Synthetic CCMS (Main Campus)"
    )
    filters = {cell_texts(row)[0]: cell_texts(row)[1:] for row in profile["filters"]["rows"]}
    assert filters["Reporting scope"] == [
        "Applied — College of the Program recorded on the Inventory",
        "Applied — Student's current Guidance affiliation",
    ]
    assert filters["Year Level"] == [
        "Applied — Year Level recorded on the Inventory",
        "Not applied — cannot classify Students without an Inventory",
    ]
    assert filters["College"] == ["Not selected", "Not selected"]


def test_empty_report_prints_context_and_coverage_without_tables_or_percentages():
    report = synthetic_report(program_count=0, submitted_count=0)
    profile = profile_of(report)
    assert profile["parts"] == []
    assert profile["appendix"] == []
    assert profile["income_legend"] is None
    assert profile["empty_message"].startswith(
        "No submitted Individual Inventories matched the selected profile filters."
    )
    assert [item["term"] for item in profile["methodology"]] == [
        "Population basis",
        "Coverage basis",
        "Empty population",
    ]
    html = rendered_html(report)
    assert profile["empty_message"] in html
    assert "Current Student Inventory Coverage" in html
    assert "100.00%" not in html
    assert "Table 1." not in html


@pytest.mark.parametrize(
    "corrupt",
    [
        "row_total",
        "program_total",
        "percentage",
        "missing_program_key",
        "denominator",
        "coverage_states",
    ],
)
def test_inconsistent_canonical_values_are_never_printed(corrupt):
    report = synthetic_report(colleges=[("CCMS", 2)], submitted_count=10)
    row = report["sections"]["sex"]["rows"][0]
    if corrupt == "row_total":
        row["total_count"] += 1
    elif corrupt == "program_total":
        report["program_columns"][0]["submitted_inventory_count"] += 1
        report["program_columns"][1]["submitted_inventory_count"] -= 1
    elif corrupt == "percentage":
        row["percentage"] = Decimal("12.34")
    elif corrupt == "missing_program_key":
        row["program_counts"] = row["program_counts"][:1]
    elif corrupt == "denominator":
        report["sections"]["age"]["denominator"] = 11
    elif corrupt == "coverage_states":
        report["inventory_coverage"]["missing_count"] = 9
    with pytest.raises(StudentProfilingDocumentUnavailable):
        build_student_profiling_print_context(report)


def test_income_legend_reuses_canonical_brackets_after_income_table():
    profile = profile_of(synthetic_report(program_count=1, submitted_count=3))
    legend = [cell_texts(row) for row in profile["income_legend"]["rows"]]
    assert legend == [list(item) for item in parent_income_bracket_legend()]
    assert legend[0] == ["Poor", "Below ₱131,484"]
    assert legend[5] == ["Upper Income", "₱1,577,808 through ₱2,626,680"]
    assert legend[6] == ["Rich", "Above ₱2,626,680"]
    assert "Spouse income is excluded" in profile["income_legend"]["notes"][0]
    assert "poverty" not in " ".join(profile["income_legend"]["notes"]).lower()

    html = rendered_html(synthetic_report(program_count=1, submitted_count=3))
    assert html.index("Combined Parent Annual Income</h4>") < html.index(
        "Parent Annual Income Brackets"
    )


@pytest.mark.django_db
def test_print_context_drops_unexpected_student_level_private_values():
    report = synthetic_report(program_count=2)
    report["private_student_number"] = "PRIVATE-STUDENT-NUMBER"
    report["private_email"] = "private-student@example.edu"
    report["sections"]["sex"]["rows"][0]["private_narrative"] = "PRIVATE COUNSELING NARRATIVE"

    html = rendered_html(report)
    for secret in (
        "PRIVATE-STUDENT-NUMBER",
        "private-student@example.edu",
        "PRIVATE COUNSELING NARRATIVE",
    ):
        assert secret not in html


@pytest.mark.django_db
def test_pdf_does_not_reintroduce_historical_report_terms_or_fake_qms_identity():
    report = synthetic_report(program_count=2)
    html = rendered_html(report)

    for stale in (
        "Freshmen",
        "Freshman",
        "Sophomore",
        "Junior",
        "Senior",
        "Gender",
        "Nort specified",
        "20 &amp; Above",
        "Boarding House / Dormitory",
        "CNSC-OP-GCO-01F5",
        "Rev. 0",
        "Prepared by",
        "Approved by",
    ):
        assert stale not in html
    assert all(
        cell_texts(row)[0] != "Without Individual Inventory"
        for table in all_tables(profile_of(report))
        for row in table["rows"]
    )


def test_pdf_context_includes_privacy_warning_without_suppressing_data():
    report = synthetic_report(program_count=1, submitted_count=2)
    report["disclosure_warnings"] = [
        {
            "code": "SMALL_POPULATION",
            "message": (
                "This report includes results from a small population or category. "
                "Use and share these results carefully because some aggregate results "
                "may be easier to associate with individual respondents."
            ),
        }
    ]
    profile = profile_of(report)
    html = rendered_html(report)
    assert profile["disclosure_warning_messages"] == [report["disclosure_warnings"][0]["message"]]
    assert "Small-population disclosure notice" in html
    assert "no value has been suppressed or changed" in html
    assert cell_texts(profile["parts"][0]["tables"][0]["rows"][0]) == ["Male", "1", "50.00%"]
    confidentiality = next(
        item["text"] for item in profile["methodology"] if item["term"] == "Confidentiality"
    )
    assert "not guaranteed to be anonymous" in confidentiality
    assert "comparing reports generated with different filters" in confidentiality


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
        assert context["student_profile"]["parts"]
        assert context["document_pdf_footer_label"].startswith("Student Profile Report")
        return DocumentRenderResult(
            pdf_bytes=b"%PDF-" + (b"x" * 2048),
            template_key=template_key,
            template_version=template_version,
        )

    monkeypatch.setattr(report_pdf, "build_student_profiling_report", fake_builder)
    monkeypatch.setattr(report_pdf, "render_document_pdf", fake_renderer)

    scope = ReportAccessScope(is_global=False, college_ids=(uuid4(),))
    result = render_student_profiling_pdf(**ids, access_scope=scope)
    assert calls == [{**ids, "access_scope": scope}]
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
        render_student_profiling_pdf(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    assert "/private/path" not in str(raised.value)


# Rendered-PDF verification -------------------------------------------------------------------


def _historical(report: dict[str, object]) -> dict[str, object]:
    report["report_context"]["academic_year"]["is_current"] = False
    report["report_context"]["academic_year"]["label"] = "2025-2026"
    coverage = report["inventory_coverage"]
    coverage.update(
        {
            "mode": "HISTORICAL_LIMITED",
            "eligible_student_count": None,
            "missing_count": None,
            "scope_note": "CANONICAL HISTORICAL COVERAGE SCOPE NOTE.",
        }
    )
    report["methodology"]["historical_coverage_note"] = "CANONICAL HISTORICAL METHODOLOGY NOTE."
    return report


def _warned(report: dict[str, object]) -> dict[str, object]:
    report["disclosure_warnings"] = [
        {"code": "SMALL_POPULATION", "message": "SMALL POPULATION ADVISORY."}
    ]
    return report


RENDER_SCENARIOS = {
    "empty": lambda: synthetic_report(program_count=0, submitted_count=0),
    "single_program": lambda: synthetic_report(program_count=1, submitted_count=12),
    "two_programs": lambda: synthetic_report(colleges=[("CCMS", 2)], submitted_count=60),
    "multiple_colleges": lambda: synthetic_report(
        colleges=[("CAS", 1), ("CCMS", 2), ("COED", 3)], submitted_count=120
    ),
    "many_programs": lambda: synthetic_report(
        colleges=[("COED", MAX_CROSS_TAB_PROGRAMS + 3)],
        submitted_count=96,
        long_program_codes=True,
    ),
    "long_municipality_list": lambda: synthetic_report(
        colleges=[("CCMS", 2)], submitted_count=150, city_count=70
    ),
    "historical": lambda: _historical(synthetic_report(colleges=[("CCMS", 2)], submitted_count=30)),
    "legacy_unclassified": lambda: synthetic_report(
        colleges=[("CCMS", 2)],
        submitted_count=40,
        legacy_inventories=5,
        legacy_values_per_program=1,
    ),
    "narrow_scope": lambda: synthetic_report(
        colleges=[("CAS", 1), ("CCMS", 2)], submitted_count=24, scope_colleges=["CAS", "CCMS"]
    ),
    "small_population_warning": lambda: _warned(
        synthetic_report(program_count=1, submitted_count=3)
    ),
}


def _structural_lines(context: dict[str, object]) -> set[str]:
    """Headings and table captions that must never be the last line on a page."""

    profile = context["student_profile"]
    lines = {
        "1. Report Overview",
        "2. Populations in This Report",
        "3. Methodology and Data Notes",
        "Appendix A. Program Breakdown",
    }
    for part in profile["parts"]:
        lines.add(part["title"])
    for table in all_tables(profile):
        lines.add(f"{table['number']} {table['title']}".strip())
        if table["population_note"]:
            lines.add(table["population_note"])
    for group in profile["appendix"]:
        lines.add(group["heading"])
    return lines


def _render(report: dict[str, object], monkeypatch) -> tuple[list[str], list[object]]:
    monkeypatch.setattr(report_pdf, "build_student_profiling_report", lambda **kwargs: report)
    result = render_student_profiling_pdf(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    pages = PdfReader(BytesIO(result.pdf_bytes)).pages
    return [page.extract_text() or "" for page in pages], list(pages)


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", sorted(RENDER_SCENARIOS))
def test_real_chromium_pdf_pagination_footer_and_structure(scenario, monkeypatch):
    report = RENDER_SCENARIOS[scenario]()
    context = build_student_profiling_print_context(report)
    texts, pages = _render(report, monkeypatch)
    page_count = len(pages)
    structural = _structural_lines(context)

    assert all(round(float(page.mediabox.width)) == 595 for page in pages)
    assert all(round(float(page.mediabox.height)) == 842 for page in pages)
    assert all(page.images for page in pages), "branding strip missing from a page"
    for number, text in enumerate(texts, start=1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        assert lines[-1].endswith(f"Page {number} of {page_count}")
        assert lines[-1].startswith("Student Profile Report · Academic Year")
        body = [line for line in lines[:-1] if len(line) > 2]
        assert len(body) >= 3, f"page {number} is effectively blank"
        assert body[-1] not in structural, f"page {number} ends with heading {body[-1]!r}"
        assert "(continued)" not in text
    joined = "\n".join(texts)
    assert "STUDENT PROFILE REPORT" in texts[0]

    if scenario == "empty":
        assert page_count <= 3
        assert "Table 1." not in joined
    if scenario == "historical":
        assert "Not available — no historical eligibility roster" in joined
    if scenario == "narrow_scope":
        assert "Limited to assigned Colleges" in joined
    if scenario == "small_population_warning":
        assert "SMALL POPULATION ADVISORY." in joined
    if scenario == "legacy_unclassified":
        assert "Unclassified / Legacy — Inventories without a Program" in joined
    if scenario == "many_programs":
        assert "by Program" in joined
    if scenario == "long_municipality_list":
        header = "City / Municipality Province Region Frequency Percentage"
        spanned = [
            text
            for text in texts
            if "Synthetic Municipality" in text and "Synthetic Region" in text
        ]
        assert len(spanned) >= 2
        assert all(header in text for text in spanned)


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", ["many_programs", "long_municipality_list", "narrow_scope"])
def test_rendered_tables_fit_the_printable_width(scenario):
    """No table may be wider than the A4 printable area, which would clip printed values."""

    html = rendered_html(RENDER_SCENARIOS[scenario]())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 741, "height": 1000})
            page.emulate_media(media="print")
            page.set_content(html, wait_until="load")
            overflow = page.evaluate(
                """() => [...document.querySelectorAll('.sp-table')]
                  .filter(table => table.scrollWidth > table.parentElement.clientWidth + 1)
                  .length"""
            )
            clipped = page.evaluate(
                """() => [...document.querySelectorAll('.sp-table th, .sp-table td')]
                  .filter(cell => cell.scrollWidth > cell.clientWidth + 1).length"""
            )
        finally:
            browser.close()
    assert overflow == 0
    assert clipped == 0


def test_colleges_sharing_a_code_on_different_campuses_stay_distinct():
    report = synthetic_report(colleges=[("CAS", 1), ("CAS", 1)], submitted_count=6)
    second = report["program_columns"][1]
    second["college"] = {**second["college"], "id": uuid4()}
    second["campus"] = {"id": uuid4(), "code": "NORTH", "name": "North Campus"}
    profile = profile_of(report)
    headings = [group["heading"] for group in profile["appendix"]]
    assert headings == [
        "A1. CAS (MAIN) — College of Synthetic CAS",
        "A2. CAS (NORTH) — College of Synthetic CAS",
    ]
