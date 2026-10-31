# FAC-2 implementation contract and policy decisions

FAC-1 implements identity and institutional affiliation only. There is no digital
Faculty Referral submission, Student search, receipt, acknowledgment or closure
workflow. Provisioning a Faculty account is not approval of any of those policies.

## Verified implementation route

1. Reuse `be/compass/referrals/models.py:Referral`, `ReferralReferenceCounter`,
   `ReferralAction`, the existing confidential-content envelope, and protected
   `FormRevision` relationships. Do not create a parallel FacultyReferral database.
   Retain `UCN-OP-GCO-01F3`, revision 1, as recorded in
   `institutional_forms/canonical.py` and ADR-113. An accepted digital form mapping
   and authority decision must precede an enabled submission route.
2. Add a separate Faculty submission service/API and narrow capabilities (e.g.
   submission and own-projection authority only after their services exist).
   Deliberately revise FAC-1's empty Faculty capability ceiling at that time.
   Never grant `referrals.manage` or reuse the GCO creation API for Faculty.
3. Under the catalog gate, reload and lock the current active Faculty identity,
   affiliation and eligible Student. Do not trust session-cached affiliation or a
   client-supplied submitter, College, name, timestamps, role or actor UUID.
   Store authenticated submitter identity, server time, source=Faculty, home
   College UUID and appropriate immutable snapshots. Keep GCO `recorded_by` and
   operational processing provenance distinct. Role changes clear the current
   home assignment; submitted provenance must remain immutable afterward.
4. Preserve `_allocate_reference`, Philippine-calendar annual counters, actor-bound
   creation-key digest, request fingerprint and transactional rollback/replay
   handling in `referrals/services.py`. Factor shared reference/encryption creation
   machinery beneath separate actor authorization; do not bypass
   `_validate_operational_actor` or relax GCO scope. A retried Faculty request must
   resolve to the same immutable submission without allocating another reference.
5. Encrypt the Referral reason and controlled referrer content with the existing
   `referrals/confidential.py` writer. Neither Student confirmation nor error,
   activity, notification or own-list projections may expose reason plaintext or
   internal actions. Existing operational document rendering remains GCO-only
   until Faculty-safe document authority and content are explicitly decided.
6. Build bounded exact Student identity confirmation as a separate privacy-reviewed
   service: no Account directory, global substring discovery or enumerable roster;
   rate limits, minimal confirmation fields, uniform negative responses and no
   information from Guidance records. The exact identifiers and confirmation
   fields require policy decisions below. Enrollment/teaching eligibility cannot
   be fabricated from a home College.
7. Support cross-College referrals. Faculty home College is provenance only; it is
   not Student placement and never a GCO destination or same-College restriction.
   GCO scope and default Counselor resolution continue to follow the Student.
   Existing submitted Referrals must not move with later affiliation changes.
8. Expose Faculty own-submission DTOs through a distinct read service constrained by
   immutable authenticated submitter ID on every query. Allowlist only the approved
   submission reference/date, Student confirmation and receipt state. Never reuse
   the internal Referral detail, encrypted reasons, operational actions, Follow-Up
   links, Counseling context, processing remarks or administrative decisions.
9. Preserve all existing GCO Referral creation, references, status-note correction,
   actions, Call Slips, void safeguards and documents. A Faculty submission is not
   a GCO receipt, approved action, Student notification, acknowledgment or closure.
   `received_at` stays unset until a separately authorized real receipt event.
   Do not synthesize `ReferralAction` rows to represent submission.

## Student Academic Records compatibility boundary

Proposal #1 SAR is absent. FAC-1 adds no Student model migration, academic fields,
roster, Program/Year writer, Student transfer or catalog seeder behavior. The
existing `StudentAffiliation` routing relationship and inventory academic facts
are unchanged. FAC-2 must isolate Student placement reads behind a domain-owned
resolver whose first implementation uses the current authoritative relationship;
SAR may later replace that resolver under a separately reviewed migration.

Do not create a second placement writer inside Faculty provisioning or submission.
Do not use the Faculty home College when Student placement is absent. Keep an
explicit unresolved state; fail closed or route to an approved real GCO triage
process only after the institution decides. No automatic Head fallback for a
Faculty submission is authorized merely because an operational service offers a
Head fallback in another context.

## Policy decision register — unresolved, no activation authority

| ID | Decision | Required owner / evidence | Safe state until decided |
| --- | --- | --- | --- |
| FAC-D1 | Whether the digital form is an authorized institutional Referral Slip; signatures, attestation and exact rendering | UCN form authority/QMS and GCO-approved revision mapping | No digital submission |
| FAC-D2 | Which active institutional Faculty may refer; temporary appointments, College-less Faculty and delegated actors | UCN identity/HR authority and GCO | Provisioned identity only; no invented roster or teaching verification |
| FAC-D3 | Student confirmation identifiers, minimum displayed fields, limits, abuse response and eligibility | GCO and privacy authority | No Faculty Student search/directory |
| FAC-D4 | Missing, conflicting or retired Student placement; real triage destination and ownership | GCO and future SAR authority | Unresolved state; no home-College routing assumption |
| FAC-D5 | Receipt responsibility, timing, acknowledgment meaning and Faculty-visible status wording | GCO | Submission does not imply receipt/approval |
| FAC-D6 | Administrative closure responsibility and what Faculty may learn about outcomes | GCO and privacy authority | No fabricated closure, clinical status or acknowledgment |
| FAC-D7 | Faculty own-submission/PDF fields, retention, continued visibility after deactivation or role change | GCO and privacy authority | No own-submission API or document |
| FAC-D8 | Whether/when any Student or Faculty Referral notifications are appropriate and what they disclose | GCO and privacy authority, NOTIF review | No automatic Student Referral notification |

These are institutional decisions, not implementation defaults. FAC-2 remains a
separate reviewed slice; FAC-3 owns the eventual complete Faculty portal.
