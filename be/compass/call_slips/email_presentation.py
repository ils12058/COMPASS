"""Call Slip-owned issuance/void proof; reporting context stays inside COMPASS."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from compass.accounts.models import User
from compass.common.email_presentation import EmailSourceEligibility, safe_email_display_text
from compass.notifications.policy import NotificationEvent

from .models import CallSlip, CallSlipIssuanceMode, CallSlipLifecycleState
from .services import CallSlipNotFound, CallSlipNotPermitted, get_my_call_slip

CALL_SLIP_EMAIL_EVENTS = frozenset(
    {NotificationEvent.CALL_SLIP_ISSUED, NotificationEvent.CALL_SLIP_VOIDED}
)


class CallSlipEmailRecipient(StrEnum):
    STUDENT = "call_slip_student"


class CallSlipEmailField(StrEnum):
    STATUS = "Status"


@dataclass(frozen=True, slots=True)
class CallSlipEmailDetail:
    field: CallSlipEmailField
    value: str = field(repr=False)

    def __post_init__(self):
        if (
            type(self.field) is not CallSlipEmailField
            or safe_email_display_text(self.value) is None
        ):
            raise ValueError("invalid call slip email detail")

    @property
    def label(self):
        return self.field.value


@dataclass(frozen=True, slots=True, repr=False)
class CallSlipEmailFacts:
    event_code: str
    source_id: UUID
    call_slip_id: UUID
    recipient_class: CallSlipEmailRecipient
    issuance_mode: str
    lifecycle_state: str
    voided_at: datetime | None
    interview_ended_at: datetime | None
    rich_allowed: bool
    rows: tuple[CallSlipEmailDetail, ...]


@dataclass(frozen=True, slots=True)
class CallSlipEmailResolution:
    eligibility: EmailSourceEligibility
    facts: CallSlipEmailFacts | None = field(default=None, repr=False)


def resolve_call_slip_email_facts(
    *, event_code, source_type, source_id, call_slip_id, recipient_id
):
    if (
        event_code not in CALL_SLIP_EMAIL_EVENTS
        or source_type != "call_slip"
        or source_id != call_slip_id
    ):
        return CallSlipEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
    recipient = User.objects.select_related("role").filter(pk=recipient_id).first()
    if recipient is None or not recipient.has_capability("call_slips.view_self"):
        return CallSlipEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    identity = CallSlip.objects.filter(pk=call_slip_id).values("student_id").first()
    if identity is None:
        return CallSlipEmailResolution(EmailSourceEligibility.SOURCE_MISSING)
    if identity["student_id"] != recipient_id:
        return CallSlipEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    try:
        item = get_my_call_slip(actor=recipient, call_slip_id=call_slip_id)
    except (CallSlipNotFound, CallSlipNotPermitted):
        return CallSlipEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    if event_code == NotificationEvent.CALL_SLIP_ISSUED:
        if (
            item.issuance_mode != CallSlipIssuanceMode.LIVE
            or item.lifecycle_state != CallSlipLifecycleState.ACTIVE
        ):
            return CallSlipEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        status = "Call Slip issued"
    else:
        if item.voided_at is None or not item.void_notifies_student:
            return CallSlipEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        status = "Call Slip voided"
    # Existing LEGACY_UNKNOWN void intent remains minimal; never infer LIVE issuance.
    rich_allowed = item.issuance_mode == CallSlipIssuanceMode.LIVE
    return CallSlipEmailResolution(
        EmailSourceEligibility.ALLOWED,
        CallSlipEmailFacts(
            event_code,
            source_id,
            item.pk,
            CallSlipEmailRecipient.STUDENT,
            item.issuance_mode,
            item.lifecycle_state,
            item.voided_at,
            item.interview_ended_at,
            rich_allowed,
            (CallSlipEmailDetail(CallSlipEmailField.STATUS, status),),
        ),
    )
