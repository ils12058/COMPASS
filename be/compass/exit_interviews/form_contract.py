"""Saved-revision answer contracts for Exit Interview, including unlabelled legacy records."""

from compass.institutional_forms.services import is_supported_form_revision

from .models import CollegeFeedbackItem


def college_feedback_codes(item) -> tuple[str, ...]:
    revision = item.form_revision
    if revision is None:
        return tuple(CollegeFeedbackItem.values)
    if revision.family.key != "exit_interview" or not is_supported_form_revision(revision):
        # Import here to avoid a services/contract cycle.
        from .services import ExitInterviewConflict

        raise ExitInterviewConflict("The saved Exit Interview Form Revision is unsupported.")
    return tuple(
        code for code in CollegeFeedbackItem.values if not code.startswith("PROGRAM_CHAIR_")
    )
