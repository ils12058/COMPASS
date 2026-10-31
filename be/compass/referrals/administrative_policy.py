"""Independent institutional authority; no production approval adapters are installed."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from django.utils import timezone

from compass.audit.models import AuditEvent, AuditOutcome
from compass.referrals.errors import ReferralError

POLICY_RECORDED = "referral.administration.policy.recorded"
CONTRACTS = {
    "ACKNOWLEDGMENT": "EXPLICIT_RECEIPT_UCN_F3_V1",
    "CLOSURE": "ADMINISTRATIVE_REVIEW_RETAIN_LINKS_V1",
    "FACULTY_TRACKING": "THREE_STAGE_TIMES_V1",
    "FACULTY_NOTICES": "MINIMAL_REFERENCE_EVENT_LINK_V1",
}


class AdministrativeReferralError(ReferralError):
    def __init__(self, code, status=403):
        self.code = "referral_administration_" + code
        self.status = status
        super().__init__("The Referral administrative operation is unavailable.")


@dataclass(frozen=True, kw_only=True)
class ApprovedAdministrativePolicy:
    version: str
    evidence_reference: str
    contract_evidence_reference: str
    kind: str
    contract: str
    valid_from: datetime
    valid_until: datetime
    actor_ids: frozenset[UUID]
    student_college_ids: frozenset[UUID]
    roles: frozenset[str]
    activation_event_id: UUID

    @property
    def digest(self):
        values = asdict(self)
        values.pop("activation_event_id")
        for key, value in values.items():
            if isinstance(value, frozenset):
                values[key] = sorted(str(item) for item in value)
            elif isinstance(value, datetime):
                values[key] = value.astimezone(UTC).isoformat()
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def validate(self, now, kind):
        references = (self.version, self.evidence_reference, self.contract_evidence_reference)
        scopes = (self.actor_ids, self.student_college_ids)
        permitted_roles = (
            {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
            if kind in {"ACKNOWLEDGMENT", "CLOSURE"}
            else {"FACULTY"}
        )
        if (
            self.kind != kind
            or self.contract != CONTRACTS.get(kind)
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value)
                for value in references
            )
            or len(self.version) > 64
            or any(
                not isinstance(value, datetime) or timezone.is_naive(value)
                for value in (self.valid_from, self.valid_until)
            )
            or not self.valid_from <= now < self.valid_until
            or any(
                not isinstance(value, frozenset)
                or not value
                or any(not isinstance(item, UUID) for item in value)
                for value in scopes
            )
            or not isinstance(self.roles, frozenset)
            or not self.roles
            or not self.roles <= permitted_roles
            or not isinstance(self.activation_event_id, UUID)
        ):
            raise AdministrativeReferralError("policy_unconfirmed")
        event = AuditEvent.objects.filter(
            pk=self.activation_event_id,
            action=POLICY_RECORDED,
            outcome=AuditOutcome.SUCCESS,
            occurred_at__lte=now,
        ).first()
        expected = {
            "decision": "APPROVED",
            "policy_kind": kind,
            "policy_digest": self.digest,
            "policy_version": self.version,
            "evidence_reference": self.evidence_reference,
        }
        if event is None or any(
            event.metadata.get(key) != value for key, value in expected.items()
        ):
            raise AdministrativeReferralError("policy_unconfirmed")


def get_approved_acknowledgment_policy() -> ApprovedAdministrativePolicy | None:
    return None


def get_approved_closure_policy() -> ApprovedAdministrativePolicy | None:
    return None


def get_approved_tracking_disclosure_policy() -> ApprovedAdministrativePolicy | None:
    return None


def get_approved_faculty_notice_policy() -> ApprovedAdministrativePolicy | None:
    return None


def require_policy(kind, now):
    provider = {
        "ACKNOWLEDGMENT": get_approved_acknowledgment_policy,
        "CLOSURE": get_approved_closure_policy,
        "FACULTY_TRACKING": get_approved_tracking_disclosure_policy,
        "FACULTY_NOTICES": get_approved_faculty_notice_policy,
    }[kind]
    policy = provider()
    if not isinstance(policy, ApprovedAdministrativePolicy):
        raise AdministrativeReferralError("policy_unconfirmed")
    policy.validate(now, kind)
    return policy


def require_admitted(actor, college_id, policy):
    if (
        actor.pk not in policy.actor_ids
        or actor.role.code not in policy.roles
        or college_id not in policy.student_college_ids
    ):
        raise AdministrativeReferralError("not_permitted")
