"""Faculty domain approval, independent of capabilities and paper-form identity.

No approved provider is deployed. A future reviewed adapter must resolve actual
institutional evidence and its matching Audit decision; a flag, database GRANT,
or an arbitrary Audit row cannot install that adapter. Tests use isolated policies.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from django.utils import timezone

from compass.audit.actions import REFERRAL_FACULTY_POLICY_RECORDED
from compass.audit.models import AuditEvent, AuditOutcome
from compass.referrals.errors import ReferralError


class FacultyReferralError(ReferralError):
    def __init__(self, code, status=403):
        self.code = "faculty_referral_" + code
        self.status = status
        super().__init__("The Faculty Referral operation is unavailable.")


@dataclass(frozen=True, kw_only=True)
class FacultyPolicyEvidence:
    version: str
    evidence_reference: str
    valid_from: datetime
    valid_until: datetime
    faculty_ids: frozenset[UUID]
    student_college_ids: frozenset[UUID]
    activation_event_id: UUID

    @property
    def digest(self):
        values = asdict(self)
        values.pop(
            "activation_event_id"
        )  # Decision records this digest, avoiding circular binding.
        for key, value in values.items():
            if isinstance(value, frozenset):
                values[key] = sorted(str(item) for item in value)
            elif isinstance(value, datetime):
                values[key] = value.astimezone(UTC).isoformat()
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def validate_evidence(self, now, kind):
        identifiers = (self.version, self.evidence_reference)
        dates = (self.valid_from, self.valid_until)
        scopes = (self.faculty_ids, self.student_college_ids)
        if (
            any(
                not isinstance(value, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value)
                for value in identifiers
            )
            or len(self.version) > 64
            or any(not isinstance(value, datetime) or timezone.is_naive(value) for value in dates)
            or not self.valid_from <= now < self.valid_until
            or any(
                not isinstance(value, frozenset)
                or not value
                or any(not isinstance(item, UUID) for item in value)
                for value in scopes
            )
            or not isinstance(self.activation_event_id, UUID)
        ):
            raise FacultyReferralError("policy_unconfirmed")
        event = AuditEvent.objects.filter(
            pk=self.activation_event_id,
            action=REFERRAL_FACULTY_POLICY_RECORDED,
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
            raise FacultyReferralError("policy_unconfirmed")


@dataclass(frozen=True, kw_only=True)
class ApprovedFacultyStudentLookupPolicy(FacultyPolicyEvidence):
    maximum_confirmation_age_seconds: int
    actor_attempt_limit: int
    ip_attempt_limit: int
    attempt_window_seconds: int
    identifier_contract: str = "EXACT_INSTITUTIONAL_ID_V1"
    disclosure_projection: str = "STUDENT_DISPLAY_NAME_V1"

    def validate(self, now):
        bounds = (self.actor_attempt_limit, self.ip_attempt_limit, self.attempt_window_seconds)
        if (
            self.identifier_contract != "EXACT_INSTITUTIONAL_ID_V1"
            or self.disclosure_projection != "STUDENT_DISPLAY_NAME_V1"
            or type(self.maximum_confirmation_age_seconds) is not int
            or not 1 <= self.maximum_confirmation_age_seconds <= 900
            or any(type(value) is not int or not 1 <= value <= 3600 for value in bounds)
        ):
            raise FacultyReferralError("lookup_policy_unconfirmed")
        self.validate_evidence(now, "STUDENT_CONFIRMATION")


@dataclass(frozen=True, kw_only=True)
class ApprovedFacultySubmissionPolicy(FacultyPolicyEvidence):
    lookup_policy_digest: str
    eligibility_evidence_reference: str
    own_projection_evidence_reference: str
    form_code: str = "UCN-OP-GCO-01F3"
    form_revision: str = "1"
    form_schema: int = 1
    capture_contract: str = "UCN_F3_DIGITAL_CAPTURE_V1"
    eligibility_rule: str = "ACTIVE_FACULTY_WITH_ACTIVE_HOME"
    own_projection: str = "REFERENCE_TIME_STUDENT_NAME_V1"

    def validate(self, now):
        refs = (self.eligibility_evidence_reference, self.own_projection_evidence_reference)
        if (
            type(self.form_schema) is not int
            or (self.form_code, self.form_revision, self.form_schema) != ("UCN-OP-GCO-01F3", "1", 1)
            or self.capture_contract != "UCN_F3_DIGITAL_CAPTURE_V1"
            or self.eligibility_rule != "ACTIVE_FACULTY_WITH_ACTIVE_HOME"
            or self.own_projection != "REFERENCE_TIME_STUDENT_NAME_V1"
            or not isinstance(self.lookup_policy_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", self.lookup_policy_digest)
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{1,127}", value)
                for value in refs
            )
        ):
            raise FacultyReferralError("submission_policy_unconfirmed")
        self.validate_evidence(now, "DIGITAL_SUBMISSION")


def get_approved_lookup_policy() -> ApprovedFacultyStudentLookupPolicy | None:
    return None


def get_approved_submission_policy() -> ApprovedFacultySubmissionPolicy | None:
    return None


def require_lookup_policy(now):
    policy = get_approved_lookup_policy()
    if not isinstance(policy, ApprovedFacultyStudentLookupPolicy):
        raise FacultyReferralError("lookup_policy_unconfirmed")
    policy.validate(now)
    return policy


def require_submission_policy(now):
    policy = get_approved_submission_policy()
    if not isinstance(policy, ApprovedFacultySubmissionPolicy):
        raise FacultyReferralError("submission_policy_unconfirmed")
    policy.validate(now)
    return policy
