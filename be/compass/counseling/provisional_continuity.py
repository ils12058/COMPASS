"""Always-on, Audit-backed code-owned policies; no institutional approval is claimed.

ID sets resolve afresh under each caller's authority fences. Digests bind the membership
rule and fixed constraints, never the current roster. Office selection checks live handled
responsibility; completed approvals survive staff turnover. New versions need new event IDs.
"""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import CONTINUITY_POLICY_RECORDED
from compass.audit.models import AuditActorType, AuditEvent, AuditOutcome
from compass.counseling.case_communication_policy import ApprovedCaseCommunicationPolicy
from compass.counseling.continuity_disclosure import (
    ENCOUNTER_METADATA_FIELDS_V1,
    ApprovedDisclosurePolicy,
    ApprovedSourceProjection,
)
from compass.counseling.continuity_models import ContinuityCommunicationPurpose, ContinuityReason
from compass.counseling.continuity_policy import ApprovedContinuityPolicy, ContinuityError
from compass.counseling.coverage_policy import ApprovedCoverageWorkflowPolicy
from compass.organization.models import College

VERSION = "code_owned_provisional_v1"
EVIDENCE = "CODE_OWNED_PROVISIONAL_NOT_INSTITUTIONAL"
MEMBERSHIP_RULE = "LIVE_ROLES_AND_COLLEGES"
VALID_FROM = datetime(2026, 1, 1, tzinfo=UTC)
VALID_UNTIL = datetime(2030, 1, 1, tzinfo=UTC)
EVENT_IDS = {
    kind: UUID(f"c02b000{i}-0000-4000-8000-00000000000{i}")
    for i, kind in enumerate(("CONTINUITY", "DISCLOSURE", "COVERAGE", "COMMUNICATION"), 1)
}


def _serialize(value):
    if isinstance(value, frozenset):
        return sorted(str(item) for item in value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    raise TypeError("Unsupported policy field")


class _ProvisionalPolicy:
    @property
    def digest(self):
        fields = asdict(self)
        for key in ("college_ids", "approver_ids", "office_requester_ids"):
            fields.pop(key, None)
        fields.update(
            decision="PROVISIONAL",
            authority="CODE_OWNED_PENDING_INSTITUTIONAL_APPROVAL",
            policy_kind=self.kind,
        )
        return hashlib.sha256(
            json.dumps(fields, default=_serialize, sort_keys=True).encode()
        ).hexdigest()

    @property
    def event_metadata(self):
        return dict(
            decision="PROVISIONAL",
            provisional=True,
            authority="CODE_OWNED_PENDING_INSTITUTIONAL_APPROVAL",
            policy_kind=self.kind,
            policy_version=self.version,
            policy_digest=self.digest,
            evidence_reference=self.evidence_reference,
        )

    def validate(self, now):
        super().validate(now)
        event = AuditEvent.objects.filter(
            pk=EVENT_IDS[self.kind],
            actor_type=AuditActorType.SYSTEM,
            action=CONTINUITY_POLICY_RECORDED,
            outcome=AuditOutcome.SUCCESS,
        ).first()
        if event is None or event.metadata != self.event_metadata:
            raise ContinuityError(self.error)


class ProvisionalContinuityPolicy(_ProvisionalPolicy, ApprovedContinuityPolicy):
    kind = "CONTINUITY"
    error = "policy_unconfirmed"


class ProvisionalDisclosurePolicy(_ProvisionalPolicy, ApprovedDisclosurePolicy):
    kind = "DISCLOSURE"
    error = "disclosure_policy_unconfirmed"


class ProvisionalCoveragePolicy(_ProvisionalPolicy, ApprovedCoverageWorkflowPolicy):
    kind = "COVERAGE"
    error = "workflow_policy_unconfirmed"


class ProvisionalCommunicationPolicy(_ProvisionalPolicy, ApprovedCaseCommunicationPolicy):
    kind = "COMMUNICATION"
    error = "communication_policy_unconfirmed"


def _record(policy):
    AuditEvent.objects.get_or_create(
        pk=EVENT_IDS[policy.kind],
        defaults={
            "occurred_at": timezone.now(),
            "actor_type": AuditActorType.SYSTEM,
            "action": CONTINUITY_POLICY_RECORDED,
            "outcome": AuditOutcome.SUCCESS,
            "metadata": policy.event_metadata,
        },
    )
    return policy


def _colleges():
    return frozenset(
        College.objects.filter(is_active=True, campus__is_active=True).values_list("pk", flat=True)
    )


def _common():
    return dict(
        version=VERSION, evidence_reference=EVIDENCE, valid_from=VALID_FROM, valid_until=VALID_UNTIL
    )


def disclosure_policy():
    return _record(
        ProvisionalDisclosurePolicy(
            **_common(),
            basis_evidence_reference=EVIDENCE,
            transparency_evidence_reference=EVIDENCE,
            retention_evidence_reference=EVIDENCE,
            monitoring_evidence_reference=EVIDENCE,
            coordination_evidence_reference=EVIDENCE,
            college_ids=_colleges(),
            membership_rule=MEMBERSHIP_RULE,
            projections=(
                ApprovedSourceProjection(
                    "ENCOUNTER", "ENCOUNTER_METADATA_V1", ENCOUNTER_METADATA_FIELDS_V1
                ),
                ApprovedSourceProjection(
                    "ROUTINE_EVALUATION",
                    "FINALIZED_EVALUATION_V1",
                    frozenset({"academic_adjustment_rating", "recommendations"}),
                ),
            ),
        )
    )


def workflow_policy():
    return _record(
        ProvisionalCoveragePolicy(
            **_common(),
            selection_evidence=EVIDENCE,
            handoff_basis_evidence=EVIDENCE,
            retention_evidence=EVIDENCE,
            author_qualification_evidence=EVIDENCE,
            client_safety_evidence=EVIDENCE,
            college_ids=_colleges(),
            membership_rule=MEMBERSHIP_RULE,
            source_kinds=frozenset({"ENCOUNTER", "ROUTINE_EVALUATION"}),
        )
    )


def continuity_policy():
    heads = frozenset(
        User.objects.filter(
            is_active=True,
            role__code="COUNSELOR",
            designation_assignments__designation__code="HEAD_GUIDANCE_COUNSELOR",
        ).values_list("pk", flat=True)
    )
    assistants = frozenset(
        User.objects.filter(is_active=True, role__code="GUIDANCE_OFFICE_ASSISTANT").values_list(
            "pk", flat=True
        )
    )
    return _record(
        ProvisionalContinuityPolicy(
            **_common(),
            maximum_duration=timedelta(days=30),
            maximum_advance=timedelta(days=14),
            college_ids=_colleges(),
            approver_ids=heads,
            office_requester_ids=heads | assistants,
            reason_categories=frozenset(ContinuityReason.values),
            overlap_rule="REJECT_ALL_RECEIVERS",
            student_transfer_rule="REQUIRE_NEW_REQUEST",
            metadata_review_approved=True,
            disclosure_policy_digest=disclosure_policy().digest,
            workflow_policy_digest=workflow_policy().digest,
            membership_rule=MEMBERSHIP_RULE,
        )
    )


def communication_policy():
    return _record(
        ProvisionalCommunicationPolicy(
            **_common(),
            permitted_purposes=frozenset(ContinuityCommunicationPurpose.values),
        )
    )
