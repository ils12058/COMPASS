"""Code-owned provisional Faculty Referral policies, not institutional approval.

FUP-3A installs an explicit code-owned path so the canonical Faculty Referral journey is
available by default. Every provisional policy is backed by one fixed Audit event whose
metadata records ``decision=PROVISIONAL`` and code ownership as the authority. No setting,
environment variable, database grant or request parameter enables or disables it; changing
this module is the only way.

Approved policies remain separate. An APPROVED event never validates a provisional policy,
and a PROVISIONAL event never validates an approved policy. The provisional digest binds the
fixed constraints and code-owned identity only; live catalog scopes and the rolling validity
window are intentionally not bound, so adding or retiring an eligible Faculty account or
College does not invent a new policy version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar
from uuid import UUID

from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import REFERRAL_FACULTY_POLICY_RECORDED
from compass.audit.models import AuditActorType, AuditEvent, AuditOutcome
from compass.organization.models import College
from compass.referrals import administrative_policy, faculty_policy

PROVISIONAL_DECISION = "PROVISIONAL"
PROVISIONAL_AUTHORITY = "CODE_OWNED_PENDING_INSTITUTIONAL_APPROVAL"
PROVISIONAL_VERSION = "code_owned_provisional_v2"
PROVISIONAL_EVIDENCE_REFERENCE = "CODE_OWNED_PROVISIONAL_NOT_INSTITUTIONAL"
PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE = "CODE_OWNED_PROVISIONAL_CONTRACT"
PROVISIONAL_ELIGIBILITY_REFERENCE = "CODE_OWNED_PROVISIONAL_ELIGIBILITY"
PROVISIONAL_OWN_PROJECTION_REFERENCE = "CODE_OWNED_PROVISIONAL_OWN_PROJECTION"
SCOPE_WINDOW = timedelta(days=1)

STUDENT_CONFIRMATION = "STUDENT_CONFIRMATION"
DIGITAL_SUBMISSION = "DIGITAL_SUBMISSION"
ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
CLOSURE = "CLOSURE"
FACULTY_TRACKING = "FACULTY_TRACKING"
_FACULTY_KINDS = frozenset({STUDENT_CONFIRMATION, DIGITAL_SUBMISSION})
_ADMIN_KINDS = frozenset({ACKNOWLEDGMENT, CLOSURE, FACULTY_TRACKING})

# One fixed, unmistakably synthetic event per policy kind. Audit rows are append-only; a
# future version must use a new fixed id and digest rather than edit these rows. Version 2
# records the Guidance Office Assistant role code; the v1 events stay untouched history.
EVENT_IDS = {
    STUDENT_CONFIRMATION: UUID("f3b00001-0000-4000-8000-000000000001"),
    DIGITAL_SUBMISSION: UUID("f3b00002-0000-4000-8000-000000000002"),
    ACKNOWLEDGMENT: UUID("f3b00003-0000-4000-8000-000000000003"),
    CLOSURE: UUID("f3b00004-0000-4000-8000-000000000004"),
    FACULTY_TRACKING: UUID("f3b00005-0000-4000-8000-000000000005"),
}

_FACULTY_SCOPE = "ALL_ACTIVE_FACULTY"
_STAFF_SCOPE = "ALL_ACTIVE_COUNSELOR_AND_GUIDANCE_OFFICE_ASSISTANT"
_COLLEGE_SCOPE = "ALL_ACTIVE_COLLEGES_WITH_ACTIVE_CAMPUS"

_FIXED_CONSTRAINTS = {
    STUDENT_CONFIRMATION: {
        "maximum_confirmation_age_seconds": 300,
        "actor_attempt_limit": 10,
        "ip_attempt_limit": 30,
        "attempt_window_seconds": 300,
        "identifier_contract": "EXACT_INSTITUTIONAL_ID_V1",
        "disclosure_projection": "STUDENT_DISPLAY_NAME_V1",
        "faculty_scope": _FACULTY_SCOPE,
        "student_college_scope": _COLLEGE_SCOPE,
    },
    ACKNOWLEDGMENT: {
        "contract": "EXPLICIT_RECEIPT_UCN_F3_V1",
        "contract_evidence_reference": PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE,
        "roles": ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"],
        "actor_scope": _STAFF_SCOPE,
        "student_college_scope": _COLLEGE_SCOPE,
    },
    CLOSURE: {
        "contract": "ADMINISTRATIVE_REVIEW_RETAIN_LINKS_V1",
        "contract_evidence_reference": PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE,
        "roles": ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"],
        "actor_scope": _STAFF_SCOPE,
        "student_college_scope": _COLLEGE_SCOPE,
    },
    FACULTY_TRACKING: {
        "contract": "THREE_STAGE_TIMES_V1",
        "contract_evidence_reference": PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE,
        "roles": ["FACULTY"],
        "actor_scope": _FACULTY_SCOPE,
        "student_college_scope": _COLLEGE_SCOPE,
    },
}


def _digest(kind, constraints):
    payload = {
        "decision": PROVISIONAL_DECISION,
        "authority": PROVISIONAL_AUTHORITY,
        "policy_kind": kind,
        "policy_version": PROVISIONAL_VERSION,
        "evidence_reference": PROVISIONAL_EVIDENCE_REFERENCE,
        "fixed_constraints": constraints,
    }
    if kind in _ADMIN_KINDS:
        payload["contract_evidence_reference"] = PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


_DIGESTS = {
    kind: _digest(kind, constraints) for kind, constraints in _FIXED_CONSTRAINTS.items()
}
_FIXED_CONSTRAINTS[DIGITAL_SUBMISSION] = {
    "lookup_policy_digest": _DIGESTS[STUDENT_CONFIRMATION],
    "eligibility_evidence_reference": PROVISIONAL_ELIGIBILITY_REFERENCE,
    "own_projection_evidence_reference": PROVISIONAL_OWN_PROJECTION_REFERENCE,
    "form_code": "UCN-OP-GCO-01F3",
    "form_revision": "1",
    "form_schema": 1,
    "capture_contract": "UCN_F3_DIGITAL_CAPTURE_V1",
    "eligibility_rule": "ACTIVE_FACULTY_WITH_ACTIVE_HOME",
    "own_projection": "REFERENCE_TIME_STUDENT_NAME_V1",
    "faculty_scope": _FACULTY_SCOPE,
    "student_college_scope": _COLLEGE_SCOPE,
}
_DIGESTS[DIGITAL_SUBMISSION] = _digest(
    DIGITAL_SUBMISSION, _FIXED_CONSTRAINTS[DIGITAL_SUBMISSION]
)


def _action(kind):
    return (
        REFERRAL_FACULTY_POLICY_RECORDED
        if kind in _FACULTY_KINDS
        else administrative_policy.POLICY_RECORDED
    )


def metadata_for(kind):
    metadata = {
        "decision": PROVISIONAL_DECISION,
        "provisional": True,
        "authority": PROVISIONAL_AUTHORITY,
        "policy_kind": kind,
        "policy_digest": _DIGESTS[kind],
        "policy_version": PROVISIONAL_VERSION,
        "evidence_reference": PROVISIONAL_EVIDENCE_REFERENCE,
    }
    if kind in _ADMIN_KINDS:
        metadata["contract_evidence_reference"] = PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE
    return metadata


def digest_for(kind):
    return _DIGESTS[kind]


def _ensure_event(kind, now):
    AuditEvent.objects.get_or_create(
        pk=EVENT_IDS[kind],
        defaults={
            "occurred_at": now,
            "actor_type": AuditActorType.SYSTEM,
            "action": _action(kind),
            "outcome": AuditOutcome.SUCCESS,
            "metadata": metadata_for(kind),
        },
    )


def _faculty_scope():
    return (
        frozenset(
            User.objects.filter(is_active=True, role__code="FACULTY").values_list(
                "pk", flat=True
            )
        ),
        frozenset(
            College.objects.filter(is_active=True, campus__is_active=True).values_list(
                "pk", flat=True
            )
        ),
    )


def _staff_scope():
    return (
        frozenset(
            User.objects.filter(
                is_active=True, role__code__in=("COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT")
            ).values_list("pk", flat=True)
        ),
        frozenset(
            College.objects.filter(is_active=True, campus__is_active=True).values_list(
                "pk", flat=True
            )
        ),
    )


class _ProvisionalPolicy:
    _provisional_kind: ClassVar[str] = ""
    _provisional_error: ClassVar[type[Exception]] = faculty_policy.FacultyReferralError

    @property
    def digest(self):
        return _DIGESTS[self._provisional_kind]

    def _validate_activation(self, now, kind):
        expected = metadata_for(self._provisional_kind)
        event = AuditEvent.objects.filter(
            pk=self.activation_event_id,
            action=_action(self._provisional_kind),
            outcome=AuditOutcome.SUCCESS,
        ).first()
        if event is None or any(
            event.metadata.get(key) != value for key, value in expected.items()
        ):
            raise self._provisional_error("policy_unconfirmed")


@dataclass(frozen=True, kw_only=True)
class ProvisionalFacultyStudentLookupPolicy(
    _ProvisionalPolicy, faculty_policy.ApprovedFacultyStudentLookupPolicy
):
    _provisional_kind: ClassVar[str] = STUDENT_CONFIRMATION


@dataclass(frozen=True, kw_only=True)
class ProvisionalFacultySubmissionPolicy(
    _ProvisionalPolicy, faculty_policy.ApprovedFacultySubmissionPolicy
):
    _provisional_kind: ClassVar[str] = DIGITAL_SUBMISSION


@dataclass(frozen=True, kw_only=True)
class ProvisionalAdministrativeAcknowledgmentPolicy(
    _ProvisionalPolicy, administrative_policy.ApprovedAdministrativePolicy
):
    _provisional_kind: ClassVar[str] = ACKNOWLEDGMENT
    _provisional_error: ClassVar[type[Exception]] = (
        administrative_policy.AdministrativeReferralError
    )


@dataclass(frozen=True, kw_only=True)
class ProvisionalAdministrativeClosurePolicy(
    _ProvisionalPolicy, administrative_policy.ApprovedAdministrativePolicy
):
    _provisional_kind: ClassVar[str] = CLOSURE
    _provisional_error: ClassVar[type[Exception]] = (
        administrative_policy.AdministrativeReferralError
    )


@dataclass(frozen=True, kw_only=True)
class ProvisionalAdministrativeTrackingPolicy(
    _ProvisionalPolicy, administrative_policy.ApprovedAdministrativePolicy
):
    _provisional_kind: ClassVar[str] = FACULTY_TRACKING
    _provisional_error: ClassVar[type[Exception]] = (
        administrative_policy.AdministrativeReferralError
    )


def _window(now):
    return now - SCOPE_WINDOW, now + SCOPE_WINDOW


def _event_if_scoped(kind, now, *sets):
    if all(sets):
        _ensure_event(kind, now)


def provisional_lookup_policy(now: datetime | None = None):
    at = now or timezone.now()
    faculty_ids, college_ids = _faculty_scope()
    _event_if_scoped(STUDENT_CONFIRMATION, at, faculty_ids, college_ids)
    valid_from, valid_until = _window(at)
    return ProvisionalFacultyStudentLookupPolicy(
        version=PROVISIONAL_VERSION,
        evidence_reference=PROVISIONAL_EVIDENCE_REFERENCE,
        valid_from=valid_from,
        valid_until=valid_until,
        faculty_ids=faculty_ids,
        student_college_ids=college_ids,
        activation_event_id=EVENT_IDS[STUDENT_CONFIRMATION],
        maximum_confirmation_age_seconds=300,
        actor_attempt_limit=10,
        ip_attempt_limit=30,
        attempt_window_seconds=300,
    )


def provisional_submission_policy(now: datetime | None = None):
    at = now or timezone.now()
    faculty_ids, college_ids = _faculty_scope()
    _event_if_scoped(DIGITAL_SUBMISSION, at, faculty_ids, college_ids)
    valid_from, valid_until = _window(at)
    return ProvisionalFacultySubmissionPolicy(
        version=PROVISIONAL_VERSION,
        evidence_reference=PROVISIONAL_EVIDENCE_REFERENCE,
        valid_from=valid_from,
        valid_until=valid_until,
        faculty_ids=faculty_ids,
        student_college_ids=college_ids,
        activation_event_id=EVENT_IDS[DIGITAL_SUBMISSION],
        lookup_policy_digest=_DIGESTS[STUDENT_CONFIRMATION],
        eligibility_evidence_reference=PROVISIONAL_ELIGIBILITY_REFERENCE,
        own_projection_evidence_reference=PROVISIONAL_OWN_PROJECTION_REFERENCE,
    )


def _administrative_policy(kind, policy_class, now):
    at = now or timezone.now()
    actor_ids, college_ids = _staff_scope() if kind != FACULTY_TRACKING else _faculty_scope()
    _event_if_scoped(kind, at, actor_ids, college_ids)
    valid_from, valid_until = _window(at)
    return policy_class(
        version=PROVISIONAL_VERSION,
        evidence_reference=PROVISIONAL_EVIDENCE_REFERENCE,
        contract_evidence_reference=PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE,
        kind=kind,
        contract=administrative_policy.CONTRACTS[kind],
        valid_from=valid_from,
        valid_until=valid_until,
        actor_ids=actor_ids,
        student_college_ids=college_ids,
        roles=frozenset(
            {"FACULTY"} if kind == FACULTY_TRACKING else {"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"}
        ),
        activation_event_id=EVENT_IDS[kind],
    )


def provisional_acknowledgment_policy(now: datetime | None = None):
    return _administrative_policy(
        ACKNOWLEDGMENT, ProvisionalAdministrativeAcknowledgmentPolicy, now
    )


def provisional_closure_policy(now: datetime | None = None):
    return _administrative_policy(CLOSURE, ProvisionalAdministrativeClosurePolicy, now)


def provisional_tracking_disclosure_policy(now: datetime | None = None):
    return _administrative_policy(
        FACULTY_TRACKING, ProvisionalAdministrativeTrackingPolicy, now
    )
