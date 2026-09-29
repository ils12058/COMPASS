"""Printable projection of the currently submitted Exit Interview response."""

from __future__ import annotations

import logging

from compass.common.correlation import get_current_request_id
from compass.documents.rendering import DocumentRenderError, render_document_pdf

from .models import (
    CareerMode,
    CollegeFeedbackItem,
    DelayReason,
    ExitInterviewStatus,
    ProgramCompletion,
    SelfAssessmentItem,
    SignificantLearningExperience,
    StudyCareerChoice,
    WorkCareerChoice,
)
from .services import ExitInterviewError, ExitInterviewNotSubmitted

logger = logging.getLogger(__name__)


class ExitInterviewDocumentUnavailable(ExitInterviewError):
    """The submitted response cannot currently be rendered as a PDF."""


_FEEDBACK_CATEGORIES = (
    ("DEAN", "dean_comments", "DEAN_"),
    ("PROG CHAIR", "program_chair_comments", "PROGRAM_CHAIR_"),
    ("FACULTY", "faculty_comments", "FACULTY_"),
    ("CURRICULUM", "curriculum_comments", "CURRICULUM_"),
    ("GUIDANCE COUNSELOR", "guidance_counselor_comments", "GUIDANCE_COUNSELOR_"),
    ("OFFICE STAFF", "office_staff_comments", "OFFICE_STAFF_"),
    ("FACILITIES", "facilities_comments", "FACILITIES_"),
)


def _choices(choices, selected: list[str]) -> list[dict[str, object]]:
    return [
        {"label": label, "selected": code in selected, "code": code}
        for code, label in choices.choices
    ]


def build_exit_interview_render_context(item) -> dict[str, object]:
    """Use only saved form-local answers and saved child ratings."""
    if item.status != ExitInterviewStatus.SUBMITTED:
        raise ExitInterviewNotSubmitted("Only submitted Exit Interviews have a downloadable PDF.")

    self_ratings = {row.item_code: row.rating for row in item.self_assessment_ratings.all()}
    college_ratings = {row.item_code: row.rating for row in item.college_feedback_ratings.all()}
    categories = []
    for label, comments_field, prefix in _FEEDBACK_CATEGORIES:
        rows = [
            {"label": item_label.split(" — ", 1)[1], "rating": college_ratings.get(code)}
            for code, item_label in CollegeFeedbackItem.choices
            if code.startswith(prefix)
        ]
        categories.append({"label": label, "rows": rows, "comments": getattr(item, comments_field)})

    return {
        "exit_form": {
            "name": item.student_name_snapshot,
            "age": item.age_snapshot if item.age_snapshot is not None else "",
            "civil_status": item.civil_status_snapshot,
            "course": item.course_snapshot,
            "major": item.major_snapshot,
            "email": item.email_snapshot,
            "address": item.home_address_snapshot,
            "contact": item.contact_number_snapshot,
            "completion": _choices(ProgramCompletion, [item.program_completion]),
            "delayed": item.program_completion == ProgramCompletion.WITH_SOME_DELAY,
            "extra_terms": item.extra_terms_count,
            "delay_reasons": _choices(DelayReason, item.delay_reasons),
            "delay_other": item.delay_other,
            "learning": _choices(
                SignificantLearningExperience, item.significant_learning_experiences
            ),
            "learning_other": item.significant_learning_other,
            "career_modes": _choices(CareerMode, item.career_modes),
            "work_choices": _choices(WorkCareerChoice, item.work_choices),
            "study_choices": _choices(StudyCareerChoice, item.study_choices),
            "self_rows": [
                {"label": label, "rating": self_ratings.get(code)}
                for code, label in SelfAssessmentItem.choices
            ],
            "categories": categories,
            "suggestions": item.suggestions_recommendations,
        },
        "self_scale": (5, 4, 3, 2, 1),
        "college_scale": (5, 4, 3, 2, 1, 0),
    }


def render_exit_interview_pdf(item) -> bytes:
    context = build_exit_interview_render_context(item)
    try:
        return render_document_pdf("exit_interview", 1, context=context).pdf_bytes
    except DocumentRenderError as exc:
        logger.warning(
            "Exit Interview PDF rendering failed.",
            extra={
                "event": "exit_interview_pdf_render_failed",
                "request_id": get_current_request_id(),
                "error_type": type(exc).__name__,
            },
        )
        raise ExitInterviewDocumentUnavailable(
            "The submitted Exit Interview PDF is temporarily unavailable."
        ) from exc
