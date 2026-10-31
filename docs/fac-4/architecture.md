# FAC-4 architecture

## One canonical record

Referral `administrative_version` is 1 on submission, 2 after acknowledgment, 3 after
administrative closure. There is no independently editable administrative state.
`administrative_state.py` derives it from `acknowledged_by` and
`administratively_closed_at`; voided and non-Faculty records have no normal Faculty
state. Existing encrypted free-text status notes retain their separate meaning.

Acknowledgment owns the existing `received_at`, the actual actor and a bound approval
policy digest/Audit reference. Closure owns its actual timestamp/actor and independent
approval evidence. PostgreSQL checks require complete chronological tuples; a trigger
refuses skipped acknowledgment, transition on voided rows, rewritten history or deletion
of an acknowledged record. Original FAC-2 provenance guards remain unchanged.

The additive `referrals.0003` migration is registered in the canonical manifest. It
backfills only version 1. It never invents an actor or derives acknowledgment from old
GCO receipt dates. Historical source content, identifiers, receipt timestamps, form
revisions and Audit records retain their original values. Reverse migration refuses
any Faculty-origin record before dropping columns, consistently with FAC-2. Roll forward.

## Authority and transaction order

`administration.transition` reloads the current Counselor/GSS actor and requires both
`referrals.view` and `referrals.manage`. The separately approved institutional policy
must bind kind, contract, criteria evidence, current validity, actor IDs/roles and Student
Colleges to a matching activation Audit. Providers return None in application code;
creating an Audit row does not install a provider.

After early policy denial, a short exclusive organization catalog advisory gate fences
supported identity, placement, responsibility, supervision and Head fallback changes.
GSS supervision set/remove now join that existing gate. Account rows are locked in UUID
order with `FOR NO KEY UPDATE OF self`, then the actual session, then the Referral.
Current operational scope is the Student's current College, never the Faculty home
College. Current Student placement, policy admission and session validity are checked
again after locks; expiry is rechecked after the Referral wait. The existing Head
oversight rule does not broaden institutional actor/College admission.

The weaker account row lock still blocks role/activity changes while allowing existing
void/Audit foreign-key key-share locks. It avoids the inversion of old void's Referral
lock and new administration's account lock. Acknowledgment/closure serialize on the
Referral. No linked Follow-Up or Call Slip is locked or modified by closure.

The database mutation and synchronous actual-actor Audit share one transaction. Audit
failure rolls back every transition fact/version. Audit metadata is version, policy
reference/digest, contract and review attestation, with no source reason or internal
justification. Duplicate/stale writes return 409 and produce no new event.

## API and UI contracts

All endpoints retain current authenticated GCO role/capability/resource scope:

| Method | Path under `/api/v1/referrals/{id}` | Operation |
|---|---|---|
| GET | `/administration` | Safe GCO intake facts and advisory eligible actions |
| POST | `/acknowledgment` | Strict integer `expected_version` |
| POST | `/administrative-closure` | Version plus strict boolean `obligations_reviewed: true` |

Server actor/time cannot be supplied. Extra request fields are refused. Availability
is advisory, bounded by actual session/policy expiry and revalidated on every write.
Submitted/received/closed facts remain readable to authorized GCO users even when
policy is unavailable; actions remain unavailable. Read/PDF/list/Notification paths
never acknowledge or close. Closure criteria under the synthetic contract mean explicit
review and retention of independent linked work, not a claim that all linked tasks or
clinical care are finished.

The existing GCO list has authoritative server-side submission-channel filtering before
pagination, saved submission dates/origin and derived handling state. Detail adds a
compact Faculty intake section with saved provenance, real actors/times and contextual
review dialogs. Historical records do not mount this section or its extra query.

Uncertain/stale/denied GCO writes block resubmission, refresh canonical reads and require
closing the old review and an explicit intake refresh before a new decision. They do not
claim the current user succeeded merely because someone else's event is now visible.
No mutation retries run automatically. FAC-3 exact submission retry retains its original
body/key and can now accept an approved current state after intervening acknowledgment.

Faculty response allowlist is exactly `id`, `reference_code`, `submitted_at`, `student`
(display name only), `state`, `received_at`, `closed_at`. New states/timestamps require
independent FAC-D7 disclosure evidence. If that is unavailable for a transition-bearing
own record, detail/list fail closed; availability disables own-read/new submission
instead of rendering false Submitted facts. Unacknowledged own reads retain FAC-2
projection authority. No GCO actor, reason, note, action, task, contact or clinical field
is exposed. Another owner's record remains 404 before disclosure checks.

Home/list/detail use canonical persisted states, with actual timestamps on detail and
closure Help explaining its limited meaning. Existing account-owned query caches,
loading/errors, responsiveness and role gates remain in place. Canonical OpenAPI is
exported and Orval-generated clients are regenerated, never manually edited/committed.

## Void and inactive Notifications

Existing GCO voiding can follow acknowledgment/closure if its original Call Slip
restrictions permit it. Past facts remain immutable. Void first refuses transitions.
Faculty own lists omit voids and detail returns 404, without a false Closed label or
confidential void explanation. No Rejected/Withdrawn state is introduced.

`notification_contract.prepare_candidate_intent` is deliberately disconnected from all
producers, the active event catalog, Notification rows, EmailDelivery, tasks and channels.
Under isolated notice/disclosure/intake fixtures it checks current active Faculty owner,
capability, affiliation, policy admission and actual event; superseded Received events,
voids and ineligible recipients yield no candidate. Its immutable intent contains only
recipient/referral IDs, reference, event/time, authenticated Faculty route and a stable
event identity key. It authorizes no delivery and sends no Student notice. Any future
adapter must use the existing trusted-origin link, current recipient/event rechecks and
per-recipient delivery deduplication at send time; this PR does not change them.
