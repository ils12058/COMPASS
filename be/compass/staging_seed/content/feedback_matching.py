"""Synthetic dataset feedback reconciliation bounded by submission provenance."""

from compass.audit.actions import CUSTOMER_FEEDBACK_SUBMITTED
from compass.audit.models import AuditEvent
from compass.feedback.confidential_content import read_feedback_confidential_content
from compass.feedback.models import CustomerFeedbackResponse


def matching_feedback(queryset, field, value):
    for item in queryset.order_by("pk").iterator(chunk_size=100):
        if getattr(read_feedback_confidential_content(item), field) == value:
            yield item


def matching_customer_feedback(student, values):
    # Optional identity stays blank. Audit provenance bounds reconciliation to this synthetic
    # account even when Feedback opportunities were deleted and subsequently rebuilt.
    response_ids = AuditEvent.objects.filter(
        action=CUSTOMER_FEEDBACK_SUBMITTED,
        actor_user_id=student.pk,
        target_type="feedback.customerfeedbackresponse",
    ).values_list("target_id", flat=True)
    return matching_feedback(
        CustomerFeedbackResponse.objects.filter(
            pk__in=list(response_ids), course_year_snapshot=values["course_year"]
        ),
        "additional_feedback",
        values["additional_feedback"],
    )
