"""Bounded synthetic demo reconciliation after ordinary metadata selection."""

from compass.feedback.confidential_content import read_feedback_confidential_content


def matching_feedback(queryset, field, value):
    for item in queryset.order_by("pk").iterator(chunk_size=100):
        if getattr(read_feedback_confidential_content(item), field) == value:
            yield item
