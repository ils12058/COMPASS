"""Separate evidence for metadata selection and confidential Handoff; never enabled by flags."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import UUID

from django.utils import timezone

from compass.counseling.continuity_policy import ContinuityError


@dataclass(frozen=True, slots=True)
class ApprovedOfficeCase:
    requester_id: UUID
    student_id: UUID
    original_counselor_id: UUID


@dataclass(frozen=True, slots=True)
class ApprovedCoverageWorkflowPolicy:
    version: str
    evidence_reference: str
    selection_evidence: str
    handoff_basis_evidence: str
    retention_evidence: str
    author_qualification_evidence: str
    client_safety_evidence: str
    valid_from: datetime
    valid_until: datetime
    college_ids: frozenset[UUID]
    office_cases: tuple[ApprovedOfficeCase, ...]
    source_kinds: frozenset[str]
    author_rule: str = "ACTIVE_ORIGINAL_ONLY"
    post_expiry_rule: str = "DENY_ALL"
    acknowledgment_rule: str = "DEFERRED"
    notification_rule: str = "DEFERRED"

    def validate(self, now):
        refs = [
            self.version,
            self.evidence_reference,
            self.selection_evidence,
            self.handoff_basis_evidence,
            self.retention_evidence,
            self.author_qualification_evidence,
            self.client_safety_evidence,
        ]
        if (
            any(
                not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", v)
                for v in refs
            )
            or len(self.version) > 64
            or not isinstance(self.valid_from, datetime)
            or not isinstance(self.valid_until, datetime)
            or timezone.is_naive(self.valid_from)
            or timezone.is_naive(self.valid_until)
            or not self.valid_from <= now < self.valid_until
            or not isinstance(self.college_ids, frozenset)
            or not self.college_ids
            or any(not isinstance(i, UUID) for i in self.college_ids)
            or not isinstance(self.office_cases, tuple)
            or len(self.office_cases) > 200
            or any(
                not isinstance(c, ApprovedOfficeCase)
                or any(not isinstance(i, UUID) for i in asdict(c).values())
                for c in self.office_cases
            )
            or len(set(self.office_cases)) != len(self.office_cases)
            or not isinstance(self.source_kinds, frozenset)
            or not self.source_kinds
            or not self.source_kinds <= {"ENCOUNTER", "ROUTINE_EVALUATION"}
            or self.author_rule != "ACTIVE_ORIGINAL_ONLY"
            or self.post_expiry_rule != "DENY_ALL"
            or self.acknowledgment_rule != "DEFERRED"
            or self.notification_rule != "DEFERRED"
        ):
            raise ContinuityError("workflow_policy_unconfirmed")

    @property
    def digest(self):
        values = asdict(self)
        values["college_ids"] = sorted(str(i) for i in self.college_ids)
        values["source_kinds"] = sorted(self.source_kinds)
        values["office_cases"] = sorted(
            tuple(str(v) for v in asdict(c).values()) for c in self.office_cases
        )
        return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()


def get_approved_workflow_policy() -> ApprovedCoverageWorkflowPolicy | None:
    return None


def require_workflow_policy(policy, now):
    workflow = get_approved_workflow_policy()
    if not isinstance(workflow, ApprovedCoverageWorkflowPolicy):
        raise ContinuityError("workflow_policy_unconfirmed")
    workflow.validate(now)
    if not policy.workflow_policy_digest or policy.workflow_policy_digest != workflow.digest:
        raise ContinuityError("workflow_policy_unconfirmed")
    return workflow
