"""Small domain policy boundary. No approved institutional policy is deployed.

A future reviewed provider must resolve verified evidence, effective dates, exact office
scope, authorized identities and bounds. Environment flags/overrides are not evidence.
Tests replace the provider with explicit isolated synthetic fixtures.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.utils import timezone

from compass.counseling.continuity_models import ContinuityReason


class ContinuityError(Exception):
    def __init__(self, code, status=403):
        self.code = "continuity_" + code
        self.status = status
        super().__init__("Continuity operation is unavailable (" + code + ").")


@dataclass(frozen=True, slots=True)
class ApprovedContinuityPolicy:
    version: str
    evidence_reference: str
    valid_from: datetime
    valid_until: datetime
    maximum_duration: timedelta
    maximum_advance: timedelta
    college_ids: frozenset[UUID]
    approver_ids: frozenset[UUID]
    office_requester_ids: frozenset[UUID]
    reason_categories: frozenset[str]
    overlap_rule: str
    student_transfer_rule: str
    metadata_review_approved: bool
    disclosure_policy_digest: str = ""

    @property
    def digest(self):
        values = asdict(self)
        # Preserve every pre-CONT-2B metadata-only policy digest byte-for-byte.
        if not self.disclosure_policy_digest:
            values.pop("disclosure_policy_digest")
        for k, v in values.items():
            if isinstance(v, frozenset):
                values[k] = sorted(str(x) for x in v)
            elif isinstance(v, datetime):
                values[k] = v.astimezone(UTC).isoformat()
            elif isinstance(v, timedelta):
                values[k] = v.total_seconds()
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def validate(self, now):
        token = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
        if (
            not token.fullmatch(self.version)
            or len(self.version) > 64
            or not token.fullmatch(self.evidence_reference)
            or len(self.evidence_reference) > 128
            or timezone.is_naive(self.valid_from)
            or timezone.is_naive(self.valid_until)
            or not self.valid_from <= now < self.valid_until
            or self.maximum_duration <= timedelta(0)
            or self.maximum_advance < timedelta(0)
            or not self.college_ids
            or not self.approver_ids
            or not self.reason_categories
            or not self.reason_categories <= set(ContinuityReason.values)
            or self.overlap_rule not in {"REJECT_ALL_RECEIVERS", "ALLOW_DIFFERENT_RECEIVERS"}
            or self.student_transfer_rule != "REQUIRE_NEW_REQUEST"
            or (
                self.disclosure_policy_digest != ""
                and (
                    not isinstance(self.disclosure_policy_digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", self.disclosure_policy_digest)
                )
            )
            or self.metadata_review_approved is not True
        ):
            raise ContinuityError("policy_unconfirmed")


def get_approved_policy() -> ApprovedContinuityPolicy | None:
    # Deliberately no settings-based activation, invented duration or delegation fallback.
    return None


def require_policy(now):
    policy = get_approved_policy()
    if not isinstance(policy, ApprovedContinuityPolicy):
        raise ContinuityError("policy_unconfirmed")
    policy.validate(now)
    return policy
