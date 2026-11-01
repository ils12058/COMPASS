# FAC-4 implementation decisions — before schema changes

Base verified: integration `e10671e2`, containing FAC-1 #348, FAC-2 #349 and FAC-3
#350. Branch `codex/fac-4-gco-referral-tracking`; target is integration only.
Reviewed FAC-2/3 handoffs, architecture/privacy/validation, Proposal #7 in the
15-proposal notes, current Referral/source template/voiding/scope, Follow-Ups,
Call Slip lifecycle, Notification catalog/currentness/delivery/link helpers and
ADRs 027/081/113, FUP-1A and Notification foundation/integration decisions.
The proposal is background product direction; the FAC-4 request defines this slice.

## Canonical facts and receipt

Keep one Referral. Add immutable acknowledgment actor and closure actor/time,
matching approval Audit references/digests, and an administrative version. Derive
Submitted → Received by GCO → Administratively Closed from those facts; no editable
status column or parallel lifecycle model. The new acknowledgment uses existing
`received_at` as its single server-derived timestamp under an explicit approved
digital receipt mapping. No second received clock is introduced.

Paper/GCO/historical receipt timestamps keep their existing meaning. They acquire
no acknowledgment actor, Faculty ownership or invented event. New Faculty records
remain unacknowledged. Existing source dates/content/actions and saved form revisions
are retained; acknowledgment is never backdated to infer a first page view/action.
Later source actions retain the existing known-receipt chronology checks.

Administrative version starts at 1, becomes 2 on acknowledgment and 3 on closure.
Stale/already-performed transitions return a defined 409 without duplicate evidence
or Audit. Canonical reads reconcile uncertain results; no blind mutation replay.
Checks and database update guards preserve complete, chronological, immutable facts.
Additive migration and canonical manifest registration preserve populated integration
records. Once any Faculty-origin record exists, reversal is refused consistently
with FAC-2's digital-history boundary; use compatible code/roll-forward.

## Authority, closure criteria and disclosure

Existing Counselor/GSS role, effective Referral capability and current Student
College scope remain necessary. New explicit evidence providers independently govern
acknowledgment, closure and Faculty tracking disclosure. Their real implementations
return None. FAC-2 submission/lookup providers stay unchanged. A raw grant, Audit row
or environment variable cannot install an approval adapter.

The synthetic closure contract is explicit review of administrative obligations,
with independently governed linked work retained. A strict reviewed-obligations
attestation is required; the approved policy must bind its actual criteria evidence.
It does not certify that every Follow-Up is complete or that clinical care succeeded.
No confidential closure narrative or guessed classification is added. GCO/UCN must
approve these semantics before any real provider exists.

Locks: a short exclusive catalog gate for transitions (shared for advisory reads),
current actor/Student accounts in UUID order using NO KEY
UPDATE (compatible with existing Audit FK inserts), actual session, then Referral.
This serializes identity/placement/transition changes and the existing row-locked
void path without a new linked-task lock inversion. Voiding may follow an actual
transition under existing safeguards, retaining its historical facts. Void first
refuses acknowledgment/closure. Faculty void behavior remains omit/404, never Closed.
The exclusive write gate also fences supported responsibility/supervision and
unique-Head fallback changes; policy denial occurs before acquiring it. It is never
held while a person reviews a dialog, and no shared-to-exclusive upgrade is used.

New Faculty states/timestamps need separate approved disclosure. Without it,
transition-bearing own records are unavailable rather than falsely labeled Submitted.
No internal actors, justification, Actions, Follow-Ups or clinical information enter
Faculty DTOs. GCO list/detail remain within their existing resource authority.

## Notifications and UI

FAC-D8 is unresolved. Prepare/test an explicitly inactive, minimal recipient/event/
reference/time/Faculty-route intent contract, with separate evidence and currentness
checks. Do not hook a producer into transitions, extend the active delivery catalog,
send a Student alert or change current delivery behavior. FAC-5 must review the
adapter to the existing Notification idempotency/current-recipient/trusted-link
machinery before enabling any approved event.

Extend the existing GCO workspace, generated contract and Faculty views. Contextual
review dialogs appear only under current action availability. Reads/refreshes/PDFs
never acknowledge. Persisted transitions alone drive the three labels; closure Help
explains the administrative meaning. No deployment, staging/main modification,
institutional activation or merge is included in this implementation request.
