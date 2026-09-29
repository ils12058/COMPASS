from __future__ import annotations

import inspect

import pytest
from django.apps import apps
from django.test import Client
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from compass.audit.actions import DOCUMENT_BRANDING_UPDATED
from compass.documents import rendering
from compass.documents.assets import get_asset_data_uri, get_document_assets
from compass.documents.rendering import (
    DocumentRenderError,
    DocumentRenderUnavailable,
    DocumentTemplateError,
    render_document_html,
    render_document_pdf,
)
from compass.documents.services import CANONICAL_DOCUMENT_BRANDING, get_document_branding
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


def test_canonical_branding_contains_only_confirmed_identity():
    branding = get_document_branding()
    assert branding is CANONICAL_DOCUMENT_BRANDING
    assert branding.country_line == "Republic of the Philippines"
    assert branding.institution_name == "University of Camarines Norte"
    assert branding.institution_short_name == "UCN"
    assert branding.former_institution_name == "Camarines Norte State College"
    assert branding.office_name == "Guidance and Counseling Office"

    assert branding.institution_address == (
        "F. Pimentel Ave., Brgy. II, Daet, Camarines Norte – 4600, Philippines"
    )
    assert branding.institution_website_url == "https://www.ucn.edu.ph"
    assert branding.institution_contact_email == "president@ucn.edu.ph"
    assert branding.institution_social_url == "https://www.facebook.com/UCNofficial"
    assert branding.office_parent_unit_name is None
    assert branding.office_email == "guidance@compass-gco.com"
    assert branding.office_phone is None
    assert branding.office_location is None


def test_accreditation_footer_stays_opt_in_for_real_documents():
    for key in (
        "good_moral_current_student",
        "good_moral_graduate",
        "referral_slip",
        "call_slip",
        "student_profiling_report",
    ):
        spec = get_template_spec(key, 1)
        html, _ = render_document_html(key, 1)
        assert spec.include_accreditation_footer is False
        assert '<footer class="accreditation-footer">' not in html

    spec = get_template_spec("foundation_test", 1)
    html, _ = render_document_html("foundation_test", 1)
    assert spec.include_accreditation_footer is True
    assert '<footer class="accreditation-footer">' in html


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
def test_html_uses_canonical_branding_partials_local_assets_and_autoescaping():
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
    assert '<section class="office-heading">' in html
    assert '<footer class="accreditation-footer">' in html
    assert "data:image/png;base64," in html
    assert "University of Camarines Norte" in html
    assert "Guidance and Counseling Office" in html
    assert "F. Pimentel Ave., Brgy. II, Daet, Camarines Norte – 4600, Philippines" in html
    assert "https://www.ucn.edu.ph" in html
    assert "president@ucn.edu.ph" in html
    assert "https://www.facebook.com/UCNofficial" in html
    assert "guidance@compass-gco.com" in html
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
    for key in ("ucn_logo", "bagong_pilipinas_logo", "accreditation_footer"):
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
