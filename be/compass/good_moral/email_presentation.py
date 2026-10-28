"""Good Moral-owned status/issuance facts; no certificate or receipt projection."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.utils import timezone

from compass.accounts.models import User
from compass.common.email_presentation import (
    EmailSourceEligibility,
    email_date,
    safe_email_display_text,
)
from compass.notifications.policy import NotificationEvent

from .models import GoodMoralInitiationOrigin, GoodMoralRequest, GoodMoralStatus, GoodMoralVariant
from .services import TEMPLATE_BY_VARIANT, GoodMoralNotFound, GoodMoralNotPermitted, get_mine

GOOD_MORAL_EMAIL_EVENTS = frozenset(
    {NotificationEvent.GOOD_MORAL_REQUEST_INITIATED, NotificationEvent.GOOD_MORAL_ISSUED}
)


class GoodMoralEmailRecipient(StrEnum):
    STUDENT = "good_moral_student"


class GoodMoralEmailField(StrEnum):
    REQUEST = "Request"
    STATUS = "Status"
    ISSUED_DATE = "Issued date"


@dataclass(frozen=True, slots=True)
class GoodMoralEmailDetail:
    field: GoodMoralEmailField
    value: str = field(repr=False)

    def __post_init__(self):
        if (
            type(self.field) is not GoodMoralEmailField
            or safe_email_display_text(self.value) is None
        ):
            raise ValueError("invalid good moral email detail")

    @property
    def label(self):
        return self.field.value


@dataclass(frozen=True, slots=True, repr=False)
class GoodMoralEmailFacts:
    event_code: str
    source_id: UUID
    request_id: UUID
    recipient_class: GoodMoralEmailRecipient
    variant: str
    status: str
    initiation_origin: str
    initiated_by_id: UUID | None
    issued_at: datetime | None
    issued_by_id: UUID | None
    form_revision_id: UUID | None
    document_template_key: str | None
    document_template_version: int | None
    rich_allowed: bool
    rows: tuple[GoodMoralEmailDetail, ...]


@dataclass(frozen=True, slots=True)
class GoodMoralEmailResolution:
    eligibility: EmailSourceEligibility
    facts: GoodMoralEmailFacts | None = field(default=None, repr=False)


def resolve_good_moral_email_facts(*, event_code, source_type, source_id, request_id, recipient_id):
    if (
        event_code not in GOOD_MORAL_EMAIL_EVENTS
        or source_type != "good_moral_request"
        or source_id != request_id
    ):
        return GoodMoralEmailResolution(EmailSourceEligibility.INVALID_SOURCE)
    recipient = User.objects.select_related("role").filter(pk=recipient_id).first()
    if recipient is None:
        return GoodMoralEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    identity = GoodMoralRequest.objects.filter(pk=request_id).values("student_id").first()
    if identity is None:
        return GoodMoralEmailResolution(EmailSourceEligibility.SOURCE_MISSING)
    if identity["student_id"] != recipient_id:
        return GoodMoralEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    try:
        item = get_mine(student=recipient, request_id=request_id)
    except (GoodMoralNotFound, GoodMoralNotPermitted):
        return GoodMoralEmailResolution(EmailSourceEligibility.RECIPIENT_DENIED)
    if event_code == NotificationEvent.GOOD_MORAL_REQUEST_INITIATED:
        if (
            item.status in {GoodMoralStatus.ISSUED, GoodMoralStatus.CANCELLED}
            or item.initiation_origin == GoodMoralInitiationOrigin.STUDENT_SELF
        ):
            return GoodMoralEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        if (
            item.initiation_origin != GoodMoralInitiationOrigin.GCO_ASSISTED
            or item.initiated_by_id is None
        ):
            return GoodMoralEmailResolution(EmailSourceEligibility.PROVENANCE_UNAVAILABLE)
        status = {
            GoodMoralStatus.REQUESTED: "Requested",
            GoodMoralStatus.READY_FOR_ISSUANCE: "Ready for issuance",
        }.get(item.status)
        if status is None:
            return GoodMoralEmailResolution(EmailSourceEligibility.PROVENANCE_UNAVAILABLE)
    else:
        if item.status != GoodMoralStatus.ISSUED:
            return GoodMoralEmailResolution(EmailSourceEligibility.SOURCE_STALE)
        if (
            not item.issued_at
            or timezone.is_naive(item.issued_at)
            or not item.issued_by_id
            or not item.form_revision_id
            or not item.document_template_key
            or not item.document_template_version
        ):
            return GoodMoralEmailResolution(EmailSourceEligibility.PROVENANCE_UNAVAILABLE)
        expected = TEMPLATE_BY_VARIANT.get(item.variant)
        family = {
            GoodMoralVariant.CURRENT_STUDENT: "good_moral_current_student",
            GoodMoralVariant.GRADUATE: "good_moral_graduate",
        }.get(item.variant)
        versions = {1, 2} if item.variant == GoodMoralVariant.CURRENT_STUDENT else {1}
        if (
            expected is None
            or item.form_revision.family.key != family
            or item.document_template_key != expected[0]
            or item.document_template_version not in versions
            or item.issued_at > timezone.now()
        ):
            return GoodMoralEmailResolution(EmailSourceEligibility.PROVENANCE_UNAVAILABLE)
        status = "Certificate issued"
    rows = [
        GoodMoralEmailDetail(GoodMoralEmailField.REQUEST, "Good Moral request"),
        GoodMoralEmailDetail(GoodMoralEmailField.STATUS, status),
    ]
    if event_code == NotificationEvent.GOOD_MORAL_ISSUED:
        rows.append(
            GoodMoralEmailDetail(GoodMoralEmailField.ISSUED_DATE, email_date(item.issued_at))
        )
    return GoodMoralEmailResolution(
        EmailSourceEligibility.ALLOWED,
        GoodMoralEmailFacts(
            event_code,
            source_id,
            item.pk,
            GoodMoralEmailRecipient.STUDENT,
            item.variant,
            item.status,
            item.initiation_origin,
            item.initiated_by_id,
            item.issued_at,
            item.issued_by_id,
            item.form_revision_id,
            item.document_template_key,
            item.document_template_version,
            True,
            tuple(rows),
        ),
    )
