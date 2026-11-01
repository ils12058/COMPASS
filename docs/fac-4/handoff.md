# FAC-5 release and UAT handoff

## Implemented and reviewable

FAC-4 supplies canonical persisted acknowledgment and administrative closure, actual
actors/server timestamps, independent policy gates, strict GCO APIs, scope/session/version
revalidation, PostgreSQL immutability/chronology guards, synchronous Audit, derived Faculty
three-state projection, authoritative GCO origin filtering, contextual GCO review dialogs,
Faculty Home/list/detail tracking and an explicitly inactive notice-intent contract.
See [architecture](architecture.md) and [validation](validation.md).

## Synthetic-only and unavailable live behavior

Positive intake remains FAC-2 synthetic-only. Positive acknowledgment, closure and new
tracking disclosure use isolated explicit synthetic evidence; all real providers return
None. No actual GCO/UCN/privacy decision has been inferred. Closure criteria are a proposed
review-and-retain-links test contract. FAC-D8 has no live producer, catalog entry, channel,
email/push/task or Student notice. No staging/main change, deployment or UAT is performed.

## Required institutional work

1. Record FAC-D1–D4 eligibility, exact lookup, digital form/intake authority and Faculty
   ownership decisions, with current authoritative organizational placement.
2. Record FAC-D5 receipt responsibility, real Counselor/GSS admission, Student College
   routing and approved use of F3 `received_at`. Check actual paper/digital workflows.
3. Record FAC-D6 closure criteria and review obligations, whether any minimal classification
   is necessary, independent linked-work treatment and who may attest. Review the proposed
   contract; change it explicitly if obligations must be mechanically satisfied.
4. Record FAC-D7 state/timestamp wording, continued read eligibility, void/exception
   communication, retention and safe historic access. Keep void omit/404 until approved.
5. Record FAC-D8 events, recipients, channels and disclosure. If approved, implement a
   separate reviewed adapter to existing Notification catalog/currentness/idempotency and
   trusted-origin deep links. Recheck current recipient and source at delivery. A candidate
   intent is not authorization to send. Do not automatically notify the Student concerned.

## UAT matrix and acceptance

Use provisioned synthetic accounts first, then institution-authorized test participants
and disposable records. Verify CAS Faculty referring a CCMS Student: appropriate CCMS GCO
scope, supervised GSS access, other College and other Faculty denial, current revoked/expired
sessions, role/activity/supervision/placement changes, duplicate/stale actions and void races.
Check submitted/received/closed wording with Faculty and GCO; show actual timestamps only,
confirm closure does not communicate clinical resolution, and verify source/PDF history.

Manually check pending and completed Follow-Ups, active/completed/voided Call Slips and
Referral Action history across acknowledgment/closure/void. Linked work retains its own
lifecycle and original void restrictions. Confirm no hidden confidential fields in Faculty
responses, links, browser storage, errors, screenshots or external messages.

Run Chromium/WebKit plus real mobile devices, 320px/200% text, keyboard focus and an actual
screen reader. Automated status/dialog semantics and keyboard checks are evidence, not a
substitute for institutional accessibility UAT. Check slow/offline reads, lost write responses,
canonical reconciliation, session expiry and approval withdrawal while dialogs are open.
No automatic retries or optimistic clinical interpretations are permitted.

## Release operations

Rehearse the registered additive migration on an authorized staging clone and compare old
identifiers, ciphertext, provenance, old receipt values, revisions and Audit. Fresh and
populated synthetic PostgreSQL upgrades are covered here. Reversal after Faculty records is
intentionally blocked before dropping immutable history; deploy compatible code or roll
forward. Do not bypass the guard or remove provenance to make a rollback command succeed.

Run exact-head hosted backend/frontend/static/browser checks and classify each failure by
owning change and base evidence. Resolve inherited failures before claiming release readiness.
The workflows currently require manual dispatch for integration PRs. Verify deployment
configuration, trusted origins, storage/backups, operational monitoring, incident/recovery and
actual policy adapter review independently. Promote/deploy only under a separately authorized
release decision. FAC-4 itself is neither activation nor release certification.
