# Cross-channel validation

## Event meaning and currentness

All 15 admitted events are exercised under minimal and operational_v1 with the same
Notification ID/event/target through real list/count/read APIs and locmem transport.
HTML/text event meanings and actions are checked by existing presentation suites.
Transport does not mark the in-app item read. Push policy remains fixed/minimal.

Source-owned tests cover exact reschedule/reassignment events, multiple revisions,
manual/automatic reminders, cancelled/past sources, F4/F6 issuance provenance,
Group registration ownership/re-registration/timestamps, Call Slip LIVE/HISTORICAL/
LEGACY_UNKNOWN and void/completion. New joined tests prove suppressed Scheduled,
issued Call Slip and superseded Group emails retain appropriate in-app history;
stale Group notices use changed-again copy. Existing reminder/Follow-Up list/count
filters remain intact rather than globally applying email suppression to history.

## Destinations and authentication

A 22-row shared fixture checks all 11 operational target kinds with UUID/missing-ID
cases in Python and TypeScript. Account Security separately requires recipient
identity; operational email excludes it. Feedback opportunity query, Group fallback,
Inventory current-year route and E-Counseling Appointment identity are preserved.
Route support for confidential/generic families does not enable new email links.

Actual frontend Student journeys open four representative family records from the
Center and from signed-out email routes, then confirm read history and already-read
navigation. Assigned Counselor, former Counselor denial and GSS denial use the
same existing record pages. All browser APIs are intercepted synthetic fixtures;
actual backend role/scope authorization is tested independently.

Login/MFA browser cases cover signed-in/password/ordinary MFA/mandatory setup,
session expiry, refresh before verification, refresh after starting setup, explicit
restart after expired verification, original-link reopening and malicious returns.
The verified defect lost nextPath on refresh because auth state was in memory.
Five production files now carry only validated next in the URL and restart links.
Reload does not restore a challenge, secret, codes or an authenticated session.
Normal MFA completion still uses the existing in-memory flow and backend challenge.
The two Back scenarios leave an MFA/setup challenge, return to the preceding public
page and deliberately reopen the original link; no protected record is fetched, and
a fresh password challenge is required. Arbitrary browser history is not exhaustively
certified. A lost/expired challenge still requires fresh login.

## Read state, identity and failures

Unread rows mark-read before navigation. A failed mutation shows an alert, keeps
unread/cache/count, and does not navigate. Explicit retry succeeds; successful
mark-all reconciles count/list. Already-read rows remain navigable without another
mutation. Empty/error/retry/long-text states are exercised. Session 401 reconciles
authentication; a same-tab account replacement evicts old Notification queries.
The existing account-ownership tests include late reads/mutations after switching.

## Access and privacy

Real Appointment GETs cover Student, assigned Counselor, former Counselor, Head,
GSS, IT Administrator, unrelated Counselor, inactive user and revoked capabilities.
Synthetic Notification ownership never creates a record grant. The rich-policy
negative cases also resolve no protected target/facts. Good Moral/Call Slip own
versus other Student APIs and Group self-registration/roster boundaries are tested.
Existing domain scope tests cover handled colleges, Head restrictions and supervision.
No UI capability fixture is accepted as proof of backend authorization.

No new Student identifiers, narratives, receipts/payments, Group titles/venues/
rosters, Call Slip reporting instructions or E-Counseling credentials enter email,
Push or realtime. Security events and independent OTP/address-change transport
retain their established purpose-specific contracts.

## Delivery, Push and realtime

Existing worker tests cover claim locks, duplicate/concurrent claims, lease expiry,
recovery, retries/backoff/limit, enqueue/SMTP/zero-return failures and source/account/
policy/origin changes after rendering. Invalid permanent source meaning produces
safe fallback or cancellation rather than invented retryable SMTP errors. Three
Appointment and three added-family committed-concurrency tests remain included.
Legacy missing sources, source/target mismatch, old Group revisions, old issued Good
Moral and historical Call Slips retain documented fallback/cancellation semantics.
No queue rewrite, historical replay or duplicate producer was introduced.

Push remains opt-in/session-bound; content comes from push_policy, with generic
service-worker fallback and a fixed Notifications Center click path. Realtime hints
carry no Notification facts. Existing browser runtime scenarios and focused Node
freshness tests cover HTTP reconciliation, coalesced/duplicate hints, account change,
session expiry and reconnect/fallback. HTTP remains authoritative.

SMTP is at-least-once; final DB read and transport are not atomic, and accepted mail
cannot be recalled. SENT proves transport handoff only. Browser Push has its existing
transport race semantics; this slice does not claim atomic revocation across channels.
See validation for exact execution status; no live delivery/UAT acceptance is inferred.
