from __future__ import annotations

import inspect
from hashlib import sha256
from io import BytesIO
from uuid import UUID

import pytest
from django.apps import apps
from django.test import Client
from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from compass.audit.actions import DOCUMENT_BRANDING_UPDATED
from compass.documents import rendering
from compass.documents.assets import (
    DocumentAssetError,
    get_asset_bytes,
    get_asset_data_uri,
    get_document_assets,
)
from compass.documents.filenames import institutional_pdf_content_disposition
from compass.documents.rendering import (
    DocumentRenderError,
    DocumentRenderUnavailable,
    DocumentTemplateError,
    render_document_html,
    render_document_pdf,
)
from compass.documents.template_specs import (
    LayoutFamily,
    UnknownDocumentTemplate,
    get_template_spec,
)


def sample_rows(count: int = 60) -> list[dict[str, str]]:
    return [
        {
            "label": f"Row {index:03d}",
            "value": "Deterministic report fixture content for print-safe table behavior.",
        }
        for index in range(1, count + 1)
    ]


def test_institutional_pdf_filenames_use_only_opaque_record_identity():
    record_id = UUID("12345678-1234-4234-8234-123456789abc")
    for kind, prefix in (
        ("individual_inventory", "individual-inventory"),
        ("exit_interview", "exit-interview"),
        ("good_moral", "good-moral"),
        ("referral_slip", "referral-slip"),
        ("call_slip", "call-slip"),
    ):
        assert institutional_pdf_content_disposition(kind, record_id) == (
            f'attachment; filename="{prefix}-{record_id}.pdf"'
        )


@pytest.mark.parametrize("long_content", [False, True])
def test_referral_pdf_footer_uses_rendered_page_count_and_preserves_content(long_content):
    reason = "STARTREASON " + ("source reason " * 300 if long_content else "short") + " ENDREASON"
    remarks = "STARTREMARKS " + ("saved remark " * 350 if long_content else "short") + " ENDREMARKS"
    pdf = render_document_pdf(
        "referral_slip",
        1,
        context={
            "referral": {
                "student_name": "Historical Student",
                "course_year_block": "BSIS 4A",
                "reason": reason,
                "referrer_name": "Source Referrer",
                "reference_code": "REF-2026-001",
                "actions": [
                    {"label": "Call the Parent/Guardian", "recorded": True, "remarks": remarks}
                ],
                "status_note": "SAVED-STATUS-MARKER",
            },
            "controlled_form": {
                "official_code": "CNSC-OP-GTA-01F9",
                "official_revision": "1",
            },
        },
    ).pdf_bytes
    pages = PdfReader(BytesIO(pdf)).pages
    assert (len(pages) > 1) == long_content
    text = "\n".join(page.extract_text() for page in pages)
    for marker in (
        "Historical Student",
        "SOURCE REFERRER",
        "STARTREASON",
        "ENDREASON",
        "STARTREMARKS",
        "ENDREMARKS",
        "SAVED-STATUS-MARKER",
    ):
        assert marker in text
    for number, page in enumerate(pages, start=1):
        page_text = page.extract_text()
        assert f"Page {number} of {len(pages)}" in page_text
        assert "CNSC-OP-GTA-01F9" in page_text
        assert "Revision: 1" in page_text


def test_official_documents_enable_optional_accreditation_footer():
    for key in (
        "exit_interview",
        "good_moral_current_student",
        "good_moral_graduate",
        "referral_slip",
        "call_slip",
        "individual_inventory",
    ):
        spec = get_template_spec(key, 1)
        html, _ = render_document_html(key, 1)
        assert spec.include_accreditation_footer is True
        assert '<footer class="accreditation-footer">' in html

    spec = get_template_spec("foundation_test", 1)
    html, _ = render_document_html("foundation_test", 1)
    assert spec.include_accreditation_footer is True
    assert '<footer class="accreditation-footer">' in html

    report_spec = get_template_spec("student_profiling_report", 1)
    report_html, _ = render_document_html("student_profiling_report", 1)
    assert report_spec.include_accreditation_footer is True
    assert '<footer class="accreditation-footer">' in report_html


@pytest.mark.parametrize(
    ("template_key", "context", "static_selector"),
    [
        (
            "good_moral_current_student",
            {"certificate": {"applicant_name": "Filled Student"}},
            ".good-moral-certificate h1",
        ),
        (
            "good_moral_graduate",
            {"certificate": {"applicant_name": "Filled Graduate"}},
            ".good-moral-certificate h1",
        ),
        (
            "referral_slip",
            {"referral": {"student_name": "Filled Referral"}},
            ".official-form-label",
        ),
        (
            "call_slip",
            {"call_slip": {"student_name": "Filled Call Slip"}},
            ".official-form-label",
        ),
    ],
)
def test_controlled_forms_color_only_filled_values_blue_and_use_arial(
    template_key, context, static_selector
):
    html, _ = render_document_html(template_key, 1, context=context)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html)
            filled = page.locator(".generated-value").first
            assert filled.evaluate("element => getComputedStyle(element).color") == "rgb(0, 0, 255)"
            assert filled.evaluate("element => getComputedStyle(element).fontFamily").startswith(
                "Arial"
            )
            static = page.locator(static_selector).first
            assert static.evaluate("element => getComputedStyle(element).color") != "rgb(0, 0, 255)"
            if template_key.startswith("good_moral_"):
                assert (
                    page.locator(".good-moral-certificate")
                    .evaluate("element => getComputedStyle(element).fontFamily")
                    .startswith("Arial")
                )
        finally:
            browser.close()


@pytest.mark.django_db
def test_document_branding_api_is_removed():
    assert Client().get("/api/v1/document-branding/profile").status_code == 404


def test_historical_branding_audit_action_remains_stable():
    assert DOCUMENT_BRANDING_UPDATED == "document_branding.updated"


@pytest.mark.django_db
def test_html_uses_static_branding_local_assets_and_autoescaping():
    html, spec = render_document_html(
        "foundation_test",
        1,
        context={
            "title": "Trusted test report",
            "sample_body": "<script>alert('body')</script>",
            "document_branding": {"institution_name": "<script>caller override</script>"},
            "rows": sample_rows(3),
            "controlled_form": {
                "official_code": "CNSC-OP-GTA-01F8",
                "official_revision": "0",
                "page_label": "Page 1 of 1",
            },
        },
    )

    assert spec.layout_family is LayoutFamily.REPORT
    assert '<header class="institution-masthead">' in html
    assert '<section class="office-heading">' not in html
    assert '<footer class="accreditation-footer">' in html
    assert "data:image/png;base64," in html
    assert "University of Camarines Norte" in html
    assert "Guidance and Counseling Office" not in html
    assert "F. Pimentel Ave., Brgy. II, Daet, Camarines Norte – 4600, Philippines" not in html
    assert "https://www.ucn.edu.ph" not in html
    assert "president@ucn.edu.ph" not in html
    assert "https://www.facebook.com/UCNofficial" not in html
    assert "guidance@compass-gco.com" not in html
    assert "<script>caller override</script>" not in html
    assert "CNSC-OP-GTA-01F8" in html
    assert "Revision: 0" in html
    assert "Page 1 of 1" in html
    assert "<script>alert('body')</script>" not in html
    assert "&lt;script&gt;alert" in html
    assert "http://minio" not in html
    assert "https://example" not in html


@pytest.mark.django_db
def test_code_owned_layout_can_omit_accreditation_footer_and_spec_rejects_unknown_paths():
    html, spec = render_document_html(
        "foundation_test_no_footer",
        1,
        context={
            "title": "No footer fixture",
            "sample_body": "Body",
            "rows": sample_rows(2),
        },
    )
    assert spec.include_accreditation_footer is False
    assert '<footer class="accreditation-footer">' not in html
    assert '<footer class="controlled-form-metadata">' not in html
    assert get_document_assets(include_accreditation_footer=False)["accreditation_footer"] is None

    known = get_template_spec("foundation_test", 1)
    assert known.template_name == "documents/test/foundation_fixture.html"
    with pytest.raises(UnknownDocumentTemplate):
        get_template_spec("../../arbitrary/template.html", 1)
    with pytest.raises(DocumentTemplateError):
        render_document_html("../../arbitrary/template.html", 1)

    assert set(apps.all_models["documents"]) == set()


def test_supplied_packaged_assets_resolve_locally_without_static_storage_urls():
    for key in ("institution_header", "accreditation_footer"):
        data_uri = get_asset_data_uri(key)
        assert data_uri.startswith("data:image/png;base64,")
        assert "http://" not in data_uri
        assert "https://" not in data_uri


@pytest.mark.django_db
def test_real_chromium_renders_nontrivial_local_pdf_with_report_table():
    result = render_document_pdf(
        "foundation_test",
        1,
        context={
            "title": "Multipage report-capability fixture",
            "sample_body": "Local deterministic HTML and packaged assets only.",
            "rows": sample_rows(90),
            "controlled_form": {
                "official_code": "CNSC-OP-GTA-01F8",
                "official_revision": "0",
                "page_label": "Historical metadata fixture",
            },
        },
    )
    assert result.template_key == "foundation_test"
    assert result.template_version == 1
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert len(result.pdf_bytes) > 10_000


@pytest.mark.django_db
def test_renderer_blocks_unexpected_remote_resource():
    with pytest.raises(DocumentRenderError, match="remote resource"):
        render_document_pdf(
            "foundation_test_no_footer",
            1,
            context={
                "title": "Remote block fixture",
                "sample_body": "The remote image must never be fetched.",
                "rows": sample_rows(1),
                "test_remote_asset": True,
            },
        )


@pytest.mark.django_db
def test_renderer_maps_chromium_unavailable_and_timeout_without_leaking_browser_error(monkeypatch):
    class FakeChromium:
        def __init__(self, error):
            self.error = error

        def launch(self, **kwargs):
            raise self.error

    class FakePlaywright:
        def __init__(self, error):
            self.chromium = FakeChromium(error)

    class FakeContext:
        def __init__(self, error):
            self.error = error

        def __enter__(self):
            return FakePlaywright(self.error)

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        rendering,
        "sync_playwright",
        lambda: FakeContext(PlaywrightError("PRIVATE-CHROMIUM-INTERNAL")),
    )
    with pytest.raises(DocumentRenderUnavailable) as unavailable:
        render_document_pdf(
            "foundation_test_no_footer",
            1,
            context={"title": "Unavailable", "sample_body": "Body", "rows": []},
        )
    assert "PRIVATE-CHROMIUM-INTERNAL" not in str(unavailable.value)

    monkeypatch.setattr(
        rendering,
        "sync_playwright",
        lambda: FakeContext(PlaywrightTimeoutError("PRIVATE-TIMEOUT-INTERNAL")),
    )
    with pytest.raises(DocumentRenderUnavailable, match="render timeout") as timed_out:
        render_document_pdf(
            "foundation_test_no_footer",
            1,
            context={"title": "Timeout", "sample_body": "Body", "rows": []},
        )
    assert "PRIVATE-TIMEOUT-INTERNAL" not in str(timed_out.value)


def test_renderer_never_uses_caller_url_navigation():
    source = inspect.getsource(rendering.render_document_pdf)
    assert ".goto(" not in source
    assert "page.set_content(" in source


@pytest.mark.parametrize(
    ("key", "dimensions"),
    [("institution_header", (6473, 1083)), ("accreditation_footer", (6614, 500))],
)
def test_official_artwork_is_valid_original_png(key, dimensions):
    payload = get_asset_bytes(key)
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    expected_hashes = {
        "institution_header": "daba7f6bc9cfd03814debe00cb180a642447a5f7209734deac2a223c9b0ffad2",
        "accreditation_footer": "86ba43c33f19c3b9e478de28cce48851a093023b9adc103b14297bb0aab2e8b0",
    }
    assert sha256(payload).hexdigest() == expected_hashes[key]
    with Image.open(BytesIO(payload)) as image:
        assert image.format == "PNG"
        assert image.size == dimensions
        assert image.mode == "RGBA"
        image.verify()


def test_asset_errors_reject_unknown_and_missing_packaged_files(monkeypatch, tmp_path):
    from compass.documents import assets

    with pytest.raises(DocumentAssetError, match="Unknown document asset"):
        get_asset_bytes("../../private-student-record")
    monkeypatch.setattr(assets, "_resource", lambda name: tmp_path / "missing")
    with pytest.raises(DocumentAssetError, match="institution_header"):
        get_asset_bytes("institution_header")
    with pytest.raises(DocumentTemplateError, match="presentation resources"):
        render_document_html("foundation_test", 1)


def _image_placements(page):
    placements = []
    resources = page["/Resources"]["/XObject"]

    def visit(operator, operands, cm, tm):
        if operator == b"Do":
            obj = resources[operands[0]].get_object()
            if obj.get("/Subtype") == "/Image":
                placements.append(((int(obj["/Width"]), int(obj["/Height"])), cm[:]))

    page.extract_text(visitor_operand_before=visit)
    return placements


@pytest.mark.parametrize(
    "key",
    [
        "individual_inventory",
        "exit_interview",
        "referral_slip",
        "call_slip",
        "good_moral_current_student",
        "good_moral_graduate",
        "student_profiling_report",
        "foundation_test",
        "foundation_test_no_footer",
    ],
)
def test_every_registered_pdf_repeats_full_width_artwork_and_dynamic_metadata(key):
    # Source consumers have dedicated populated/provenance tests. This checks the
    # shared physical-page contract, including continuation pages and opt-out.
    controlled = (
        {}
        if key in {"exit_interview", "student_profiling_report"}
        else {
            "official_code": "HISTORICAL-CODE",
            "official_revision": "0",
            "page_label": "Page 1 of 1",
        }
    )
    context = {
        "title": "Synthetic branding regression",
        "rows": sample_rows(100),
        "controlled_form": controlled,
        "document_branding": {"institution_name": "UNTRUSTED-MASTHEAD"},
        "document_assets": {"institution_header": "https://example.invalid/override"},
    }
    pdf = render_document_pdf(key, 1, context=context).pdf_bytes
    pages = PdfReader(BytesIO(pdf)).pages
    if key == "individual_inventory":
        assert len(pages) == 3
    if key.startswith("foundation_test"):
        assert len(pages) > 1
    for number, page in enumerate(pages, 1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        assert width == pytest.approx(210 * 72 / 25.4, abs=0.8)
        assert height == pytest.approx(297 * 72 / 25.4, abs=0.8)
        images = _image_placements(page)
        header = [cm for dims, cm in images if dims == (6473, 1083)]
        footer = [cm for dims, cm in images if dims == (6614, 500)]
        assert len(header) == 1
        assert len(footer) == (0 if key == "foundation_test_no_footer" else 1)
        for cm, ratio in [(header[0], 1083 / 6473)] + ([(footer[0], 500 / 6614)] if footer else []):
            assert abs(cm[0]) == pytest.approx(width, abs=0.8)
            assert abs(cm[3] / cm[0]) == pytest.approx(ratio, abs=0.001)
            assert cm[4] == pytest.approx(0, abs=0.8)
        assert header[0][5] + abs(header[0][3]) == pytest.approx(height - 5 * 72 / 25.4, abs=0.8)
        if footer:
            assert footer[0][5] == pytest.approx(14 * 72 / 25.4, abs=0.8)
        text_positions = []

        def visit_text(text, cm, tm, font, font_size, positions=text_positions):
            if text.strip():
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                positions.append((text, y))

        text = page.extract_text(visitor_text=visit_text)
        for fragment, y in text_positions:
            # Body baselines stay above the 34 mm bottom reserve. Metadata
            # sits below the artwork (which starts 14 mm above the page edge).
            if y > 20 * 72 / 25.4:
                assert y >= 34 * 72 / 25.4 - 2, (fragment, y)
                assert y <= height - 45 * 72 / 25.4 + 2, (fragment, y)
            else:
                assert y < 14 * 72 / 25.4, (fragment, y)
        assert text.count(f"Page {number} of {len(pages)}") == 1
        if len(pages) > 1:
            assert "Page 1 of 1" not in text
        assert "UNTRUSTED-MASTHEAD" not in text
        assert "University of Camarines Norte" not in text  # embedded artwork only
        if controlled:
            assert text.count("HISTORICAL-CODE") == 1
            assert "Revision: 0" in text
        else:
            assert "Revision:" not in text


def test_optional_footer_does_not_require_the_footer_asset(monkeypatch):
    from compass.documents import assets

    monkeypatch.setitem(assets.BRANDING_ASSETS, "accreditation_footer", "missing-footer.png")
    html, _ = render_document_html("foundation_test_no_footer", 1)
    assert '<header class="institution-masthead">' in html
    assert '<footer class="accreditation-footer">' not in html
    with pytest.raises(DocumentTemplateError, match="presentation resources"):
        render_document_html("foundation_test", 1)


def test_native_page_metadata_escapes_identity_and_report_labels():
    footer = rendering._page_footer_template(
        {
            "official_code": '<img src="https://example.invalid/code">',
            "official_revision": "<script>revision</script>",
        },
        label=None,
        show_page_numbers=True,
    )
    assert "<img" not in footer and "<script>" not in footer
    assert "&lt;img" in footer and "&lt;script&gt;" in footer
    report = rendering._page_footer_template(
        {},
        label="<script>report</script>",
        show_page_numbers=True,
    )
    assert "<script>" not in report and "&lt;script&gt;" in report
    assert 'class="pageNumber"' in footer and 'class="totalPages"' in footer
    assert "</strong><br>Revision:" in footer


@pytest.mark.parametrize(
    ("template_key", "context_key", "field", "selector"),
    [
        ("good_moral_current_student", "certificate", "issuer_name", ".good-moral-signature-line"),
        ("good_moral_graduate", "certificate", "issuer_name", ".good-moral-signature-line"),
        ("referral_slip", "referral", "referrer_name", ".signature-line"),
        ("call_slip", "call_slip", "issued_by_name", ".signature-line"),
    ],
)
def test_printed_signature_names_are_uppercase_and_above_the_rule(
    template_key, context_key, field, selector
):
    original_name = "Dr. Lea de la Cruz"
    context = {context_key: {field: original_name}}
    html, _ = render_document_html(template_key, 1, context=context)
    assert context[context_key][field] == original_name
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html)
            line = page.locator(selector).first
            assert line.inner_text() == original_name.upper()
            assert (
                line.evaluate("element => parseFloat(getComputedStyle(element).borderBottomWidth)")
                > 0
            )
            name_box = line.locator(".generated-value").bounding_box()
            line_box = line.bounding_box()
            assert name_box["y"] + name_box["height"] <= line_box["y"] + line_box["height"]
        finally:
            browser.close()


@pytest.mark.parametrize("key", ["good_moral_current_student", "good_moral_graduate"])
@pytest.mark.parametrize("filled", [False, True])
def test_good_moral_receipt_fields_keep_short_rules_for_blank_and_filled_values(key, filled):
    from datetime import date

    certificate = {
        "official_receipt_number": "OR-001" if filled else "",
        "official_receipt_date": date(2026, 10, 15) if filled else None,
        "official_receipt_amount": 0 if filled else None,
    }
    html, _ = render_document_html(key, 1, context={"certificate": certificate})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html)
            lines = page.locator(".good-moral-receipt-value")
            assert lines.count() == 3
            boxes = [line.bounding_box() for line in lines.all()]
            assert max(box["x"] for box in boxes) - min(box["x"] for box in boxes) < 0.5
            assert max(box["width"] for box in boxes) - min(box["width"] for box in boxes) < 0.5
            for line in lines.all():
                metrics = line.evaluate("""element => ({
                    width: element.getBoundingClientRect().width,
                    border: parseFloat(getComputedStyle(element).borderBottomWidth),
                })""")
                assert metrics["width"] >= 30 * 96 / 25.4 - 1
                assert metrics["border"] > 0
            if filled:
                assert lines.nth(0).inner_text() == "OR-001"
                assert lines.nth(1).inner_text() == "October 15, 2026"
                assert lines.nth(2).inner_text() == "0.00"
            else:
                assert lines.all_inner_texts() == ["", "", ""]
        finally:
            browser.close()
