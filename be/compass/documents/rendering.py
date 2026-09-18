"""Trusted Django-template to PDF rendering through local Playwright Chromium."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .assets import DocumentAssetError, get_document_assets, get_print_css
from .services import DocumentBrandingConfigurationError, get_branding_profile
from .template_specs import (
    DocumentTemplateSpec,
    UnknownDocumentTemplate,
    get_template_spec,
)


class DocumentRenderError(RuntimeError):
    pass


class DocumentRenderUnavailable(DocumentRenderError):
    pass


class DocumentTemplateError(DocumentRenderError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentRenderResult:
    pdf_bytes: bytes
    template_key: str
    template_version: int


def _safe_template_spec(key: str, version: int) -> DocumentTemplateSpec:
    try:
        return get_template_spec(key, version)
    except UnknownDocumentTemplate as exc:
        raise DocumentTemplateError("The requested document template is not available.") from exc


def _page_footer_template() -> str:
    return (
        '<div style="width:100%;font-family:Arial,Helvetica,sans-serif;'
        'font-size:8px;color:#333;text-align:right;padding:0 10mm;">'
        'Page <span class="pageNumber"></span> of <span class="totalPages"></span>'
        "</div>"
    )


def render_document_html(
    template_key: str,
    template_version: int,
    *,
    context: dict[str, Any] | None = None,
) -> tuple[str, DocumentTemplateSpec]:
    spec = _safe_template_spec(template_key, template_version)
    try:
        branding = get_branding_profile()
        assets = get_document_assets(include_accreditation_footer=spec.include_accreditation_footer)
        print_css = get_print_css()
    except (DocumentBrandingConfigurationError, DocumentAssetError) as exc:
        raise DocumentTemplateError("Document presentation resources are not configured.") from exc

    caller_context = dict(context or {})
    reserved = {
        "document_branding": branding,
        "document_assets": assets,
        "document_print_css": mark_safe(print_css),
        "document_template_spec": spec,
        "document_layout_family": spec.layout_family.value,
    }
    caller_context.update(reserved)

    try:
        html = render_to_string(spec.template_name, caller_context)
    except TemplateDoesNotExist as exc:
        raise DocumentTemplateError("The requested document template is unavailable.") from exc
    return html, spec


def render_document_pdf(
    template_key: str,
    template_version: int,
    *,
    context: dict[str, Any] | None = None,
) -> DocumentRenderResult:
    html, spec = render_document_html(
        template_key,
        template_version,
        context=context,
    )
    timeout_ms = int(settings.DOCUMENT_RENDER_TIMEOUT_SECONDS * 1000)
    blocked_urls: list[str] = []
    browser = None

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=True,
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError as exc:
                raise DocumentRenderUnavailable(
                    "Chromium did not become available before the render timeout."
                ) from exc
            except PlaywrightError as exc:
                raise DocumentRenderUnavailable(
                    "Chromium is unavailable for document rendering."
                ) from exc

            browser_context = browser.new_context(
                java_script_enabled=False,
                service_workers="block",
            )
            page = browser_context.new_page()
            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(timeout_ms)

            def _route(request_route):
                request_url = request_route.request.url
                if request_url.startswith(("http://", "https://")):
                    blocked_urls.append(request_url)
                    request_route.abort()
                    return
                request_route.continue_()

            page.route("**/*", _route)
            try:
                page.set_content(
                    html,
                    wait_until="load",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError as exc:
                raise DocumentRenderError(
                    "Document HTML did not load before the render timeout."
                ) from exc
            except PlaywrightError as exc:
                raise DocumentRenderError("Document HTML could not be rendered.") from exc

            if blocked_urls:
                raise DocumentRenderError("Document rendering attempted to load a remote resource.")

            try:
                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    display_header_footer=spec.show_page_numbers,
                    header_template="<span></span>",
                    footer_template=(
                        _page_footer_template() if spec.show_page_numbers else "<span></span>"
                    ),
                )
            except PlaywrightError as exc:
                raise DocumentRenderError("Chromium could not generate the PDF.") from exc
            finally:
                browser_context.close()

    finally:
        if browser is not None and browser.is_connected():
            browser.close()

    if not pdf_bytes.startswith(b"%PDF-") or len(pdf_bytes) < 1024:
        raise DocumentRenderError("Chromium returned an invalid PDF payload.")

    return DocumentRenderResult(
        pdf_bytes=pdf_bytes,
        template_key=spec.key,
        template_version=spec.version,
    )
