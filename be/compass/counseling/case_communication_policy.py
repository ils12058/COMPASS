"""Policy contract with a code-owned provisional production provider."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from django.utils import timezone

from compass.counseling.continuity_models import ContinuityCommunicationPurpose
from compass.counseling.continuity_policy import ContinuityError


@dataclass(frozen=True, slots=True)
class ApprovedCaseCommunicationPolicy:
    version: str
    evidence_reference: str
    valid_from: datetime
    valid_until: datetime
    permitted_purposes: frozenset[str]

    @property
    def digest(self):
        values = asdict(self)
        for key, value in values.items():
            if isinstance(value, frozenset):
                values[key] = sorted(str(item) for item in value)
            elif isinstance(value, datetime):
                values[key] = value.astimezone(UTC).isoformat()
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
            or not self.permitted_purposes
            or not self.permitted_purposes <= set(ContinuityCommunicationPurpose.values)
        ):
            raise ContinuityError("communication_policy_unconfirmed")


def get_approved_case_communication_policy() -> ApprovedCaseCommunicationPolicy | None:
    from compass.counseling.provisional_continuity import communication_policy

    return communication_policy()


def require_case_communication_policy(now):
    policy = get_approved_case_communication_policy()
    if not isinstance(policy, ApprovedCaseCommunicationPolicy):
        raise ContinuityError("communication_policy_unconfirmed")
    policy.validate(now)
    return policy
