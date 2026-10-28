"""Evidence-bound field projections. Both deployed policy providers remain empty."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from django.utils import timezone

from compass.counseling.continuity_policy import ContinuityError

# Independent immutable V1 inventories: future ordinary DTO/content additions cannot expand them.
ENCOUNTER_METADATA_FIELDS_V1 = frozenset(
    {
        "id",
        "started_at",
        "ended_at",
        "entry_mode",
        "delivery_mode",
        "counselor_id",
    }
)
EVALUATION_FIELDS_V1 = frozenset(
    {
        "academic_adjustment_rating",
        "physical_adjustment_rating",
        "social_adjustment_rating",
        "spiritual_adjustment_rating",
        "financial_adjustment_rating",
        "emotional_adjustment_rating",
        "other_adjustment",
        "special_concern",
        "recommendations",
    }
)
PROJECTION_FIELDS_V1 = {
    ("ENCOUNTER", "ENCOUNTER_METADATA_V1"): ENCOUNTER_METADATA_FIELDS_V1,
    ("ROUTINE_EVALUATION", "FINALIZED_EVALUATION_V1"): EVALUATION_FIELDS_V1,
}


@dataclass(frozen=True, slots=True)
class ApprovedSourceProjection:
    resource_kind: str
    projection: str
    fields: frozenset[str]
    lifecycle_rule: str = "FINALIZED_COMPLETED_V1"
    revision_rule: str = "SEALED_STRUCTURAL_REVISION_V1"


@dataclass(frozen=True, slots=True)
class ApprovedDisclosurePolicy:
    version: str
    evidence_reference: str
    basis_evidence_reference: str
    transparency_evidence_reference: str
    retention_evidence_reference: str
    monitoring_evidence_reference: str
    coordination_evidence_reference: str
    valid_from: datetime
    valid_until: datetime
    college_ids: frozenset[UUID]
    projections: tuple[ApprovedSourceProjection, ...]

    def validate(self, now):
        tokens = [
            self.version,
            self.evidence_reference,
            self.basis_evidence_reference,
            self.transparency_evidence_reference,
            self.retention_evidence_reference,
            self.monitoring_evidence_reference,
            self.coordination_evidence_reference,
        ]
        if (
            any(
                not isinstance(t, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", t)
                for t in tokens
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
            or not isinstance(self.projections, tuple)
            or not self.projections
        ):
            raise ContinuityError("disclosure_policy_unconfirmed")
        seen = set()
        for item in self.projections:
            if not isinstance(item, ApprovedSourceProjection):
                raise ContinuityError("disclosure_policy_unconfirmed")
            pair = item.resource_kind, item.projection
            allowed = PROJECTION_FIELDS_V1.get(pair)
            if (
                pair in seen
                or allowed is None
                or not isinstance(item.fields, frozenset)
                or not item.fields
                or not item.fields <= allowed
                or item.lifecycle_rule != "FINALIZED_COMPLETED_V1"
                or item.revision_rule != "SEALED_STRUCTURAL_REVISION_V1"
                or (item.resource_kind == "ENCOUNTER" and item.fields != allowed)
            ):
                raise ContinuityError("disclosure_policy_unconfirmed")
            seen.add(pair)

    @property
    def digest(self):
        data = {
            name: getattr(self, name)
            for name in (
                "version",
                "evidence_reference",
                "basis_evidence_reference",
                "transparency_evidence_reference",
                "retention_evidence_reference",
                "monitoring_evidence_reference",
                "coordination_evidence_reference",
            )
        }
        data.update(
            valid_from=self.valid_from.astimezone(UTC).isoformat(),
            valid_until=self.valid_until.astimezone(UTC).isoformat(),
            college_ids=sorted(str(i) for i in self.college_ids),
            projections=sorted(
                (p.resource_kind, p.projection, sorted(p.fields), p.lifecycle_rule, p.revision_rule)
                for p in self.projections
            ),
        )
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def selected_projection(self, resource_kind, projection):
        for item in self.projections:
            if (item.resource_kind, item.projection) == (resource_kind, projection):
                return item
        raise ContinuityError("disclosure_policy_unconfirmed")


def get_approved_disclosure_policy() -> ApprovedDisclosurePolicy | None:
    # No verified institutional field/basis/retention/monitoring approval exists.
    return None


def require_disclosure_policy(now):
    policy = get_approved_disclosure_policy()
    if not isinstance(policy, ApprovedDisclosurePolicy):
        raise ContinuityError("disclosure_policy_unconfirmed")
    policy.validate(now)
    return policy
