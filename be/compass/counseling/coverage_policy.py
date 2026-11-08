"""Policy contract with a code-owned provisional production provider."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import UUID

from django.utils import timezone

from compass.counseling.continuity_policy import ContinuityError


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
    source_kinds: frozenset[str]
    author_rule: str = "ACTIVE_ORIGINAL_ONLY"
    post_expiry_rule: str = "DENY_ALL"
    acknowledgment_rule: str = "DEFERRED"
    notification_rule: str = "DEFERRED"
    membership_rule: str = "EXPLICIT_IDS"
    office_selection_rule: str = "REQUESTER_RESPONSIBILITY"

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
            or self.membership_rule not in {"EXPLICIT_IDS", "LIVE_ROLES_AND_COLLEGES"}
            or (self.membership_rule == "EXPLICIT_IDS" and not self.college_ids)
            or any(not isinstance(i, UUID) for i in self.college_ids)
            or self.office_selection_rule != "REQUESTER_RESPONSIBILITY"
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
        return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()


def get_approved_workflow_policy() -> ApprovedCoverageWorkflowPolicy | None:
    from compass.counseling.provisional_continuity import workflow_policy

    return workflow_policy()


def require_workflow_policy(policy, now):
    workflow = get_approved_workflow_policy()
    if not isinstance(workflow, ApprovedCoverageWorkflowPolicy):
        raise ContinuityError("workflow_policy_unconfirmed")
    workflow.validate(now)
    if not policy.workflow_policy_digest or policy.workflow_policy_digest != workflow.digest:
        raise ContinuityError("workflow_policy_unconfirmed")
    return workflow


def office_college_ids(actor, policy, workflow):
    """Live responsibility only; designation/role never grants confidential content."""
    from compass.organization.access_scope import resolve_operational_responsibility_scope

    if not actor.is_active or actor.pk not in policy.office_requester_ids:
        return frozenset()
    return frozenset(resolve_operational_responsibility_scope(actor).college_ids).intersection(
        policy.college_ids, workflow.college_ids
    )


def office_can_select(actor, student_id, policy, workflow):
    from compass.student_academics.models import StudentAcademicProfile

    return StudentAcademicProfile.objects.filter(
        student_id=student_id,
        current_college_id__in=office_college_ids(actor, policy, workflow),
        student__is_active=True,
        student__role__code="STUDENT",
        student__student_lifecycle_status="CURRENT",
    ).exists()
