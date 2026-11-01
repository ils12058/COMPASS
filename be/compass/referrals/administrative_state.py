"""Normal administrative labels derived from canonical transition facts."""

from enum import StrEnum


class FacultyReferralSubmissionState(StrEnum):
    SUBMITTED = "SUBMITTED"
    RECEIVED_BY_GCO = "RECEIVED_BY_GCO"
    ADMINISTRATIVELY_CLOSED = "ADMINISTRATIVELY_CLOSED"


def administrative_state(item):
    if item.submission_channel != "FACULTY_PORTAL" or item.voided_at is not None:
        return None
    if item.administratively_closed_at is not None:
        return FacultyReferralSubmissionState.ADMINISTRATIVELY_CLOSED
    if item.acknowledged_by_id is not None:
        return FacultyReferralSubmissionState.RECEIVED_BY_GCO
    return FacultyReferralSubmissionState.SUBMITTED
