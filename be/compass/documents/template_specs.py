"""Small code-owned registry of approved document presentation templates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LayoutFamily(StrEnum):
    STANDARD_LETTERHEAD = "STANDARD_LETTERHEAD"
    COMPACT_FORM = "COMPACT_FORM"
    CERTIFICATE = "CERTIFICATE"
    REPORT = "REPORT"


@dataclass(frozen=True, slots=True)
class DocumentTemplateSpec:
    key: str
    version: int
    template_name: str
    layout_family: LayoutFamily
    include_accreditation_footer: bool = False
    show_page_numbers: bool = False


class UnknownDocumentTemplate(RuntimeError):
    pass


_TEMPLATE_SPECS = {
    ("good_moral_current_student", 1): DocumentTemplateSpec(
        key="good_moral_current_student",
        version=1,
        template_name="documents/good_moral/current_student.html",
        layout_family=LayoutFamily.CERTIFICATE,
        include_accreditation_footer=False,
        show_page_numbers=False,
    ),
    ("good_moral_graduate", 1): DocumentTemplateSpec(
        key="good_moral_graduate",
        version=1,
        template_name="documents/good_moral/graduate.html",
        layout_family=LayoutFamily.CERTIFICATE,
        include_accreditation_footer=False,
        show_page_numbers=False,
    ),
    ("referral_slip", 1): DocumentTemplateSpec(
        key="referral_slip",
        version=1,
        template_name="documents/referrals/referral_slip.html",
        layout_family=LayoutFamily.COMPACT_FORM,
        include_accreditation_footer=False,
        show_page_numbers=False,
    ),
    ("call_slip", 1): DocumentTemplateSpec(
        key="call_slip",
        version=1,
        template_name="documents/call_slips/call_slip.html",
        layout_family=LayoutFamily.COMPACT_FORM,
        include_accreditation_footer=False,
        show_page_numbers=False,
    ),
    ("student_profiling_report", 1): DocumentTemplateSpec(
        key="student_profiling_report",
        version=1,
        template_name="documents/reports/student_profile.html",
        layout_family=LayoutFamily.REPORT,
        include_accreditation_footer=False,
        show_page_numbers=True,
    ),
    ("foundation_test", 1): DocumentTemplateSpec(
        key="foundation_test",
        version=1,
        template_name="documents/test/foundation_fixture.html",
        layout_family=LayoutFamily.REPORT,
        include_accreditation_footer=True,
        show_page_numbers=True,
    ),
    ("foundation_test_no_footer", 1): DocumentTemplateSpec(
        key="foundation_test_no_footer",
        version=1,
        template_name="documents/test/foundation_fixture.html",
        layout_family=LayoutFamily.REPORT,
        include_accreditation_footer=False,
        show_page_numbers=True,
    ),
}


def get_template_spec(key: str, version: int) -> DocumentTemplateSpec:
    try:
        return _TEMPLATE_SPECS[(key, version)]
    except (KeyError, TypeError) as exc:
        raise UnknownDocumentTemplate(
            f"Unknown document template key/version: {key!r}/{version!r}."
        ) from exc
