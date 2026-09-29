"""Trusted Django-template to PDF rendering through local Playwright Chromium."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

from .assets import DocumentAssetError, get_document_assets, get_print_css
from .services import get_document_branding
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
        'font-size:8px;color:#333;padding:0 7mm;">'
        '<div style="text-align:right;margin-top:2mm;">'
        'Page <span class="pageNumber"></span> of <span class="totalPages"></span>'
        "</div></div>"
    )


def _repeat_accreditation_footer(pdf_bytes: bytes, overlay_bytes: bytes) -> bytes:
    overlay = PdfReader(BytesIO(overlay_bytes)).pages[0]
    writer = PdfWriter()
    for page in PdfReader(BytesIO(pdf_bytes)).pages:
        page.merge_page(deepcopy(overlay))
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def render_document_html(
    template_key: str,
    template_version: int,
    *,
    context: dict[str, Any] | None = None,
) -> tuple[str, DocumentTemplateSpec]:
    spec = _safe_template_spec(template_key, template_version)
    branding = get_document_branding()
    try:
        assets = get_document_assets(include_accreditation_footer=spec.include_accreditation_footer)
        print_css = get_print_css()
    except DocumentAssetError as exc:
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
    pdf_context = dict(context or {})
    if template_key == "student_profiling_report":
        pdf_context["document_pdf_footer"] = True
    html, spec = render_document_html(
        template_key,
        template_version,
        context=pdf_context,
    )
    show_report_pagination = spec.show_page_numbers and not (context or {}).get("controlled_form")
    timeout_ms = int(settings.DOCUMENT_RENDER_TIMEOUT_SECONDS * 1000)
    blocked_urls: list[str] = []
    accreditation_uri = None
    if spec.key == "student_profiling_report" and spec.include_accreditation_footer:
        try:
            accreditation_uri = get_document_assets(include_accreditation_footer=True)[
                "accreditation_footer"
            ]
        except DocumentAssetError as exc:
            raise DocumentTemplateError(
                "Document presentation resources are not configured."
            ) from exc

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

        try:
            browser_context = browser.new_context(
                java_script_enabled=False,
                service_workers="block",
            )
            try:
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
                    raise DocumentRenderError(
                        "Document rendering attempted to load a remote resource."
                    )

                if spec.key == "individual_inventory":
                    fit = page.evaluate(
                        """() => {
                          const pages = [...document.querySelectorAll(
                            '.individual-inventory-page')];
                          if (pages.length !== 3) return { ok: false, reason: 'page count' };
                          const answerFields = [...document.querySelectorAll(
                            '.inventory-answer-lines')];
                          if (answerFields.length !== 2) {
                            return { ok: false, reason: 'answer field count' };
                          }
                          for (const field of answerFields) {
                            const rules = [...field.querySelectorAll('.inventory-answer-rule')];
                            if (rules.length !== 2 || rules.some(rule => {
                              const style = window.getComputedStyle(rule);
                              return rule.getBoundingClientRect().width <= 0 ||
                                parseFloat(style.borderBottomWidth) <= 0;
                            })) {
                              return { ok: false, reason: 'answer rules' };
                            }
                          }
                          for (const field of document.querySelectorAll('.inventory-fit')) {
                            const value = field.querySelector('.generated-value') || field;
                            const wraps = field.classList.contains('inventory-answer-lines');
                            const fieldStyle = window.getComputedStyle(field);
                            const availableWidth = field.clientWidth -
                              parseFloat(fieldStyle.paddingLeft) -
                              parseFloat(fieldStyle.paddingRight);
                            if (value !== field) {
                              value.style.display = wraps ? 'block' : 'inline-block';
                              value.style.width = wraps ? '100%' : 'max-content';
                              value.style.maxWidth = wraps ? `${availableWidth}px` : 'none';
                              value.style.verticalAlign = 'top';
                              value.style.overflow = 'visible';
                            }
                            value.style.overflow = 'visible';
                            value.style.whiteSpace = wraps ? 'normal' : 'nowrap';
                            value.style.overflowWrap = wraps ? 'anywhere' : 'normal';
                            for (let size = 8.5; size >= 7.1; size -= 0.2) {
                              value.style.fontSize = `${size.toFixed(1)}pt`;
                              const textWidth = value.getBoundingClientRect().width;
                              if ((wraps || textWidth <= availableWidth) &&
                                  field.scrollHeight <= field.clientHeight + 1) break;
                            }
                            const widthOverflow =
                              !wraps && value.getBoundingClientRect().width > availableWidth + 0.1;
                            if (widthOverflow ||
                                field.scrollHeight > field.clientHeight + 1) {
                              return { ok: false, reason: 'field overflow', tag: field.tagName,
                                fieldClass: field.className,
                                width: availableWidth,
                                textWidth: value.getBoundingClientRect().width,
                                height: field.clientHeight, scrollHeight: field.scrollHeight };
                            }
                          }
                          for (const section of pages) {
                            const body = section.querySelector('.inventory-source-body');
                            const metadata = section.querySelector('.controlled-form-metadata');
                            if (body.getBoundingClientRect().bottom >
                                  metadata.getBoundingClientRect().top - 4) {
                              return { ok: false, reason: 'page overflow',
                                bodyBottom: body.getBoundingClientRect().bottom,
                                metadataTop: metadata.getBoundingClientRect().top };
                            }
                          }
                          return { ok: true };
                        }"""
                    )
                    if not fit["ok"]:
                        raise DocumentRenderError(
                            "The Individual Inventory content does not fit the controlled form: "
                            f"{fit}."
                        )

                try:
                    pdf_bytes = page.pdf(
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        display_header_footer=show_report_pagination,
                        header_template="<span></span>",
                        footer_template=(
                            _page_footer_template() if show_report_pagination else "<span></span>"
                        ),
                    )
                except PlaywrightError as exc:
                    raise DocumentRenderError("Chromium could not generate the PDF.") from exc
                if spec.key == "individual_inventory":
                    try:
                        if len(PdfReader(BytesIO(pdf_bytes)).pages) != 3:
                            raise DocumentRenderError(
                                "The Individual Inventory PDF did not fit exactly three pages."
                            )
                    except ValueError as exc:
                        raise DocumentRenderError(
                            "Chromium returned an invalid Individual Inventory PDF."
                        ) from exc
                if accreditation_uri:
                    overlay_html = (
                        "<style>@page{size:A4;margin:0}body{margin:0}"
                        ".recognition{position:absolute;left:7mm;bottom:16mm;"
                        "width:196mm;border-top:0.75mm solid #750000;padding-top:1mm}"
                        ".recognition img{display:block;width:100%;height:12mm}</style>"
                        f'<div class="recognition"><img src="{accreditation_uri}"></div>'
                    )
                    page.set_content(overlay_html, wait_until="load", timeout=timeout_ms)
                    try:
                        overlay_bytes = page.pdf(
                            format="A4", print_background=True, prefer_css_page_size=True
                        )
                        pdf_bytes = _repeat_accreditation_footer(pdf_bytes, overlay_bytes)
                    except (PlaywrightError, ValueError) as exc:
                        raise DocumentRenderError(
                            "The report recognition footer could not be placed."
                        ) from exc
            finally:
                browser_context.close()
        finally:
            browser.close()

    if not pdf_bytes.startswith(b"%PDF-") or len(pdf_bytes) < 1024:
        raise DocumentRenderError("Chromium returned an invalid PDF payload.")

    return DocumentRenderResult(
        pdf_bytes=pdf_bytes,
        template_key=spec.key,
        template_version=spec.version,
    )
