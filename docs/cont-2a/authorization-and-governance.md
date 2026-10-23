# Actor authorization and unapproved policy

The [CONT-0 institutional decision register](../cont-0/institutional-decisions.md) remains unapproved. Technical state-machine tests are not GCO/UCN sign-off.

Canonical capabilities registered in `accounts/policy.py`:

| Capability | Additional authoritative conditions |
| --- | --- |
| counseling.continuity.view | Active canonical COUNSELOR; current approved policy; own requester/receiver identity, or explicitly named current Head inside approved office/College scope |
| counseling.continuity.request | View dependency; current Student/affiliation; eligible named receiver; exact sources supported by ordinary authorship/capability or explicitly named office-requester policy; approved reason and duration |
| counseling.continuity.approve | View dependency; active Counselor, current HEAD_GUIDANCE_COUNSELOR assignment, explicit policy approver ID, office scope; actor differs from requester and receiver |
| counseling.continuity.revoke | View dependency; same current Head/approval authority and separation, plus effective revoke capability |
| counseling.continuity.read_selected | View dependency; future receiver eligibility only, with no content-read endpoint or bypass |

No role/designation automatically receives these codes. Ordinary capability evaluation preserves explicit REVOKE, dependency closure and exact override expiry. GSS, IT Admin, Students and institutional officers remain denied even with all codes. A frontend session's stale role/designation/capabilities never establishes authority; services reload and lock identities, then query current effective capabilities/designations. Existing account/session invalidation remains intact. The low-level override writer now also takes its target User lock inside its transaction, aligning it with administrative account changes and the new foundation.

`ApprovedContinuityPolicy` is a small internal validated value, not a stored policy-management subsystem or caller payload. It requires opaque non-narrative policy version/evidence reference, valid-from/until, positive maximum duration, non-negative maximum advance, exact College IDs, exact approver IDs, explicit office-requester IDs (possibly empty), allowed reason subset, approved metadata review, overlap rule and Student-transfer rule. Its complete digest binds requests to the reviewed policy snapshot. Missing, expired or changed evidence fails closed. Finite dates alone cannot activate an unconfirmed approval. There is no production policy configuration, feature flag or arbitrary override that replaces institutional evidence.

Supported synthetic policy strategies are strict new-request-on-affiliation-change, plus either reject all overlapping receivers or permit different receiver/kind coverage while still rejecting duplicate same-Student/receiver/kind overlaps. No institutional duration or overlap choice is selected by default. The tests' eight-hour duration is fixture data only.

Acting Head is deliberately unavailable. Existing overrides record effect/reason/expiry/creator but lack verified delegation start, office scope and authenticated institutional provenance. No role, delegation table or invented approval evidence is added. A Head's own request/receipt requires another independent, currently designated, policy-named legitimate Head; otherwise approval is blocked. No emergency self-approval or IT impersonation exists.

Outstanding activation evidence:

- D01: authorized requester relationships and office/College scope, including absent-author metadata procedure.
- D02/D03: named approving offices/people, self-approval separation, legitimate backup and formal delegation representation if adopted.
- D04: maximum duration, advance interval, renewal procedure and evidence effective dates.
- D05/D07: exact metadata selector fields/actors and approved operational reason/evidence codes.
- D10: current-Student/lifecycle and transfer rules; supported implementation requires a new request after affiliation changes.
- D12: approved overlap strategy across different receivers/kinds.
- D13: audit/monitoring inspection authority and escalation/retention procedure (no new Audit browser is created).

A reviewed provider must resolve and verify these institutional approvals. Its concurrency/invalidation contract must also be specified before operational activation. The default provider returns None, so all metadata and lifecycle APIs remain unavailable after deployment of this slice alone. Policy invalidation makes existing approvals ineffective; old-policy requests cannot be silently re-approved under a new digest. Current source-revision or receiver changes still permit a reduction in principle, but the transition's current actor/policy and sealed metadata checks must pass. No policy-free emergency mutation route exists.
