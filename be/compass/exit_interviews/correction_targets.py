"""Backend-owned Exit Interview correction-target catalog (FORM-CORR-1).

A correction target names the part of an Exit Interview that Head Guidance asks the Student to
review again. It is advisory: it never blocks saving or resubmission, and it does not mean the
answer is wrong. The required written reason stays the primary instruction.

Compatibility rules:

- Codes are stable and append-only. Never rename, reuse, or remove a released code: encrypted
  correction events may reference it after the code leaves the catalog.
- Rating rows use the fixed source item codes. Codes never contain answer values or frontend
  element ids.
- The catalog spans every supported saved answer contract. ``allowed_correction_targets`` narrows
  it to one record's saved Form Revision: UCN F9 has no Program Chair questions, while legacy
  null-revision records keep them.
- A College Feedback rating of ``0`` is a valid saved answer without a defined meaning. Targeting
  a row never depends on or interprets its value.
- Enum order is the canonical order; stored lists are normalized to it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType

from .errors import InvalidExitInterviewInput
from .form_contract import college_feedback_codes
from .models import CollegeFeedbackItem, SelfAssessmentItem

MAX_CORRECTION_TARGETS = 30


class ExitInterviewCorrectionTarget(StrEnum):
    SECTION_GENERAL_INFORMATION = "section.general_information"
    GENERAL_STUDENT_NAME = "general.student_name"
    GENERAL_AGE = "general.age"
    GENERAL_CIVIL_STATUS = "general.civil_status"
    GENERAL_COURSE = "general.course"
    GENERAL_MAJOR = "general.major"
    GENERAL_EMAIL_ADDRESS = "general.email_address"
    GENERAL_CONTACT_NUMBER = "general.contact_number"
    GENERAL_HOME_ADDRESS = "general.home_address"

    SECTION_PROGRAM_COMPLETION_AND_PLANS = "section.program_completion_and_plans"
    COMPLETION_PROGRAM_COMPLETION = "completion.program_completion"
    COMPLETION_EXTRA_TERMS_COUNT = "completion.extra_terms_count"
    COMPLETION_DELAY_REASONS = "completion.delay_reasons"
    LEARNING_SIGNIFICANT_LEARNING_EXPERIENCES = "learning.significant_learning_experiences"
    CAREER_WORK = "career.work"
    CAREER_STUDY = "career.study"

    SECTION_SELF_ASSESSMENT = "section.self_assessment"
    SELF_ASSESSMENT_PRIDE_CONFIDENCE_CNSC = "self_assessment.PRIDE_CONFIDENCE_CNSC"
    SELF_ASSESSMENT_ACADEMIC_RECREATION_BALANCE = "self_assessment.ACADEMIC_RECREATION_BALANCE"
    SELF_ASSESSMENT_HOLISTIC_PERSONAL_WELL_BEING = "self_assessment.HOLISTIC_PERSONAL_WELL_BEING"
    SELF_ASSESSMENT_INTEGRATE_KNOWLEDGE_EXPERIENCE = (
        "self_assessment.INTEGRATE_KNOWLEDGE_EXPERIENCE"
    )
    SELF_ASSESSMENT_CAREER_GOAL_CLARITY = "self_assessment.CAREER_GOAL_CLARITY"
    SELF_ASSESSMENT_SELF_ESTEEM = "self_assessment.SELF_ESTEEM"
    SELF_ASSESSMENT_SELF_AWARENESS = "self_assessment.SELF_AWARENESS"
    SELF_ASSESSMENT_COPE_WITH_PRESSURES = "self_assessment.COPE_WITH_PRESSURES"
    SELF_ASSESSMENT_DEAL_WITH_DIFFERENT_WALKS = "self_assessment.DEAL_WITH_DIFFERENT_WALKS"
    SELF_ASSESSMENT_LEADERSHIP = "self_assessment.LEADERSHIP"
    SELF_ASSESSMENT_COMMUNICATION_SKILLS = "self_assessment.COMMUNICATION_SKILLS"
    SELF_ASSESSMENT_CIVIC_MINDEDNESS = "self_assessment.CIVIC_MINDEDNESS"
    SELF_ASSESSMENT_INITIATIVE = "self_assessment.INITIATIVE"
    SELF_ASSESSMENT_DECISION_MAKING = "self_assessment.DECISION_MAKING"
    SELF_ASSESSMENT_RELATIONSHIP_WITH_GOD = "self_assessment.RELATIONSHIP_WITH_GOD"

    SECTION_COLLEGE_FEEDBACK = "section.college_feedback"
    COLLEGE_FEEDBACK_DEAN_AVAILABILITY = "college_feedback.DEAN_AVAILABILITY"
    COLLEGE_FEEDBACK_DEAN_OPEN_MINDEDNESS = "college_feedback.DEAN_OPEN_MINDEDNESS"
    COLLEGE_FEEDBACK_DEAN_CONCERN_FOR_STUDENTS = "college_feedback.DEAN_CONCERN_FOR_STUDENTS"
    COLLEGE_FEEDBACK_DEAN_COMMITMENT = "college_feedback.DEAN_COMMITMENT"
    COLLEGE_FEEDBACK_DEAN_APPROACHABILITY = "college_feedback.DEAN_APPROACHABILITY"
    COLLEGE_FEEDBACK_COMMENTS_DEAN = "college_feedback.comments.dean"
    COLLEGE_FEEDBACK_PROGRAM_CHAIR_AVAILABILITY = "college_feedback.PROGRAM_CHAIR_AVAILABILITY"
    COLLEGE_FEEDBACK_PROGRAM_CHAIR_APPROACHABILITY = (
        "college_feedback.PROGRAM_CHAIR_APPROACHABILITY"
    )
    COLLEGE_FEEDBACK_PROGRAM_CHAIR_CONCERN_FOR_STUDENTS = (
        "college_feedback.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS"
    )
    COLLEGE_FEEDBACK_COMMENTS_PROGRAM_CHAIR = "college_feedback.comments.program_chair"
    COLLEGE_FEEDBACK_FACULTY_AVAILABILITY = "college_feedback.FACULTY_AVAILABILITY"
    COLLEGE_FEEDBACK_FACULTY_APPROACHABILITY = "college_feedback.FACULTY_APPROACHABILITY"
    COLLEGE_FEEDBACK_FACULTY_KNOWLEDGE_SUBJECT_MATTER = (
        "college_feedback.FACULTY_KNOWLEDGE_SUBJECT_MATTER"
    )
    COLLEGE_FEEDBACK_FACULTY_TEACHING_SKILLS = "college_feedback.FACULTY_TEACHING_SKILLS"
    COLLEGE_FEEDBACK_COMMENTS_FACULTY = "college_feedback.comments.faculty"
    COLLEGE_FEEDBACK_CURRICULUM_RELEVANCE_SUBJECTS = (
        "college_feedback.CURRICULUM_RELEVANCE_SUBJECTS"
    )
    COLLEGE_FEEDBACK_CURRICULUM_SYSTEMATIC_SEQUENCING = (
        "college_feedback.CURRICULUM_SYSTEMATIC_SEQUENCING"
    )
    COLLEGE_FEEDBACK_CURRICULUM_COMPLETENESS = "college_feedback.CURRICULUM_COMPLETENESS"
    COLLEGE_FEEDBACK_COMMENTS_CURRICULUM = "college_feedback.comments.curriculum"
    COLLEGE_FEEDBACK_GUIDANCE_COUNSELOR_AVAILABILITY = (
        "college_feedback.GUIDANCE_COUNSELOR_AVAILABILITY"
    )
    COLLEGE_FEEDBACK_GUIDANCE_COUNSELOR_APPROACHABILITY = (
        "college_feedback.GUIDANCE_COUNSELOR_APPROACHABILITY"
    )
    COLLEGE_FEEDBACK_GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS = (
        "college_feedback.GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS"
    )
    COLLEGE_FEEDBACK_GUIDANCE_COUNSELOR_EFFICIENCY = (
        "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY"
    )
    COLLEGE_FEEDBACK_COMMENTS_GUIDANCE_COUNSELOR = "college_feedback.comments.guidance_counselor"
    COLLEGE_FEEDBACK_OFFICE_STAFF_SERVICE_ORIENTED = (
        "college_feedback.OFFICE_STAFF_SERVICE_ORIENTED"
    )
    COLLEGE_FEEDBACK_OFFICE_STAFF_AVAILABILITY = "college_feedback.OFFICE_STAFF_AVAILABILITY"
    COLLEGE_FEEDBACK_OFFICE_STAFF_CONCERN_FOR_STUDENTS = (
        "college_feedback.OFFICE_STAFF_CONCERN_FOR_STUDENTS"
    )
    COLLEGE_FEEDBACK_OFFICE_STAFF_APPROACHABILITY = "college_feedback.OFFICE_STAFF_APPROACHABILITY"
    COLLEGE_FEEDBACK_COMMENTS_OFFICE_STAFF = "college_feedback.comments.office_staff"
    COLLEGE_FEEDBACK_FACILITIES_MAINTENANCE_CONDITION = (
        "college_feedback.FACILITIES_MAINTENANCE_CONDITION"
    )
    COLLEGE_FEEDBACK_FACILITIES_AVAILABILITY = "college_feedback.FACILITIES_AVAILABILITY"
    COLLEGE_FEEDBACK_FACILITIES_COMPLETENESS = "college_feedback.FACILITIES_COMPLETENESS"
    COLLEGE_FEEDBACK_COMMENTS_FACILITIES = "college_feedback.comments.facilities"

    SECTION_SUGGESTIONS = "section.suggestions"
    SUGGESTIONS_SUGGESTIONS_RECOMMENDATIONS = "suggestions.suggestions_recommendations"


_T = ExitInterviewCorrectionTarget

# College Feedback rating targets and the fixed item each one names.
_RATING_ITEMS: Mapping[ExitInterviewCorrectionTarget, CollegeFeedbackItem] = MappingProxyType(
    {_T(f"college_feedback.{code}"): CollegeFeedbackItem(code) for code in CollegeFeedbackItem}
)
# Each comment belongs to the category whose rating items carry this prefix.
_COMMENT_CATEGORIES: Mapping[ExitInterviewCorrectionTarget, str] = MappingProxyType(
    {
        _T.COLLEGE_FEEDBACK_COMMENTS_DEAN: "DEAN_",
        _T.COLLEGE_FEEDBACK_COMMENTS_PROGRAM_CHAIR: "PROGRAM_CHAIR_",
        _T.COLLEGE_FEEDBACK_COMMENTS_FACULTY: "FACULTY_",
        _T.COLLEGE_FEEDBACK_COMMENTS_CURRICULUM: "CURRICULUM_",
        _T.COLLEGE_FEEDBACK_COMMENTS_GUIDANCE_COUNSELOR: "GUIDANCE_COUNSELOR_",
        _T.COLLEGE_FEEDBACK_COMMENTS_OFFICE_STAFF: "OFFICE_STAFF_",
        _T.COLLEGE_FEEDBACK_COMMENTS_FACILITIES: "FACILITIES_",
    }
)


def _coverage() -> dict[ExitInterviewCorrectionTarget, frozenset[str]]:
    coverage: dict[ExitInterviewCorrectionTarget, frozenset[str]] = {
        target: frozenset() for target in _T if target.value.startswith("section.")
    }
    for name in (
        "student_name",
        "age",
        "civil_status",
        "course",
        "major",
        "email_address",
        "contact_number",
        "home_address",
    ):
        coverage[_T(f"general.{name}")] = frozenset({name})
    coverage.update(
        {
            _T.COMPLETION_PROGRAM_COMPLETION: frozenset({"program_completion"}),
            _T.COMPLETION_EXTRA_TERMS_COUNT: frozenset({"extra_terms_count"}),
            _T.COMPLETION_DELAY_REASONS: frozenset({"delay_reasons", "delay_other"}),
            _T.LEARNING_SIGNIFICANT_LEARNING_EXPERIENCES: frozenset(
                {"significant_learning_experiences", "significant_learning_other"}
            ),
            _T.CAREER_WORK: frozenset({"career_modes.WORK", "work_choices"}),
            _T.CAREER_STUDY: frozenset({"career_modes.STUDY", "study_choices"}),
            _T.SUGGESTIONS_SUGGESTIONS_RECOMMENDATIONS: frozenset({"suggestions_recommendations"}),
        }
    )
    for code in SelfAssessmentItem:
        coverage[_T(f"self_assessment.{code}")] = frozenset({f"self_assessment_ratings.{code}"})
    for target, code in _RATING_ITEMS.items():
        coverage[target] = frozenset({f"college_feedback_ratings.{code}"})
    for target in _COMMENT_CATEGORIES:
        coverage[target] = frozenset({f"{target.value.rsplit('.', 1)[1]}_comments"})
    return coverage


# The payload answers each code stands for. Section codes cover a whole section rather than keys.
# ``career_modes`` is split by mode because Work and Study are separate questions on the form.
TARGET_COVERAGE: Mapping[ExitInterviewCorrectionTarget, frozenset[str]] = MappingProxyType(
    _coverage()
)

_ORDER = {target: index for index, target in enumerate(ExitInterviewCorrectionTarget)}


def allowed_correction_targets(item) -> frozenset[ExitInterviewCorrectionTarget]:
    """Targets that exist on this record's saved answer contract.

    Raises the domain conflict for an unsupported saved Form Revision, exactly as edits do.
    """

    feedback = set(college_feedback_codes(item))
    unavailable = {target for target, code in _RATING_ITEMS.items() if code not in feedback}
    unavailable.update(
        target
        for target, prefix in _COMMENT_CATEGORIES.items()
        if not any(code.startswith(prefix) for code in feedback)
    )
    return frozenset(target for target in _T if target not in unavailable)


def normalize_correction_targets(
    values: object,
    *,
    allowed: frozenset[ExitInterviewCorrectionTarget],
) -> tuple[ExitInterviewCorrectionTarget, ...]:
    """Validate submitted codes against one record, drop repeats, and return catalog order.

    Messages never repeat a submitted value.
    """

    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise InvalidExitInterviewInput("Correction targets must be a list.")
    if len(values) > MAX_CORRECTION_TARGETS:
        raise InvalidExitInterviewInput(
            f"Select at most {MAX_CORRECTION_TARGETS} parts of the Exit Interview to review."
        )
    selected: set[ExitInterviewCorrectionTarget] = set()
    for value in values:
        try:
            target = ExitInterviewCorrectionTarget(value)
        except (ValueError, TypeError):
            target = None
        if target is None or target not in allowed:
            raise InvalidExitInterviewInput(
                "One or more selected parts are not part of this Exit Interview form."
            )
        selected.add(target)
    return tuple(sorted(selected, key=_ORDER.__getitem__))


def project_stored_targets(
    codes: Iterable[str],
) -> tuple[tuple[ExitInterviewCorrectionTarget, ...], int]:
    """Keep stored codes this build recognizes, in stored order, and count the others."""

    known: list[ExitInterviewCorrectionTarget] = []
    omitted = 0
    for code in codes:
        try:
            known.append(ExitInterviewCorrectionTarget(code))
        except ValueError:
            omitted += 1
    return tuple(known), omitted
