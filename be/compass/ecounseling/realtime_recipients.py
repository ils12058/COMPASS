"""Current E-Counseling participants; workspace and consent authority stay distinct."""

from uuid import UUID

from .services import (
    ECounselingError,
    ECounselingNotPermitted,
    _load_workspace_appointment,
    _require_counselor_relationship,
    _require_student_relationship,
)


def workspace_participant_id(
    appointment_id: UUID, *, student: bool, consent: bool = False
) -> UUID | None:
    try:
        appointment = _load_workspace_appointment(appointment_id)
    except ECounselingError:
        return None
    actor = appointment.student if student else appointment.provider
    check = _require_student_relationship if student else _require_counselor_relationship
    capabilities = ["ecounseling.view_self" if student else "ecounseling.view_assigned"]
    if consent:
        capabilities.append(
            "ecounseling.consent_self" if student else "ecounseling.manage_media_assigned"
        )
    try:
        for capability in capabilities:
            check(actor=actor, appointment=appointment, capability=capability)
    except ECounselingNotPermitted:
        return None
    return actor.pk
