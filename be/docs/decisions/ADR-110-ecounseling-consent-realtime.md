# ADR-110: E-Counseling consent realtime synchronization (RT-1A)

Status: Implementation proposed for owner review. Extends ADR-100/101/102 using their existing
transport, authenticated HTTP authority and lossy-hint recovery. No deployment or enablement.

## Contract and authority

The closed backend and frontend registries add exactly:

```json
{"v":1,"type":"ecounseling.consent.changed","appointment_id":"<canonical UUID>"}
```

`appointment_id` is the only identifier. Missing, malformed or extra fields, unsupported versions
and unregistered types are rejected. There is no decision, scope, consent ID, timestamp, user ID,
room, session, media state or content. The hint means that canonical consent data may have changed;
the browser must read the existing authenticated HTTP APIs. It never patches permissions.

`request_consents` schedules one callback only when one or more scopes create new rows, preserving
the existing one durable Student Notification and its independent Notification/email/push policy.
An idempotent request schedules none. `decide_my_consent` schedules only a committed PENDING to
APPROVED/DENIED transition. `withdraw_my_consent` schedules inside the existing consent/audit/Stop
intent transaction, before the subsequent provider Stop/storage operations. A provider failure
does not undo that withdrawal or suppress its hint. No capture/provider behavior changes.

The callback runs after the outermost successful commit; any enclosing/savepoint rollback drops
it. It reloads the appointment/current participant immediately before each publication, including
again after the first recipient’s Redis round trip, applying the same workspace
eligibility and exact active account, role, ownership/assignment gates as the canonical reads:

| Participant | Required capabilities | Relationship |
| --- | --- | --- |
| Student | `ecounseling.view_self`, `ecounseling.consent_self` | Current appointment owner in STUDENT role |
| Counselor | `ecounseling.view_assigned`, `ecounseling.manage_media_assigned` | Current assigned provider in COUNSELOR role |
| Other accounts/designations | None grant an exception | Never enumerated or broadcast to |

A reassignment before the callback selects the new eligible provider, never an unrelated former
one. Saved rooms retain the existing historical read policy: a current Student lifecycle is
required to approve, not newly imposed on historical read/withdraw access. A relationship or
capability change after recipient calculation remains possible; content-free hints cannot grant
access, and the next HTTP read still enforces current authority.

Recipient lookup failures are caught and logged using a closed event/error type, without IDs,
exception text or consent data. Redis publication uses ADR-100's short timeout, safe errors and
unique user channels; it holds no transaction/row lock. No transport failure can undo a committed
consent/audit/Notification write. Disabled realtime skips callback/recipient work. There is no
outbox, new task, Beat schedule, Redis subscription, table, migration or OpenAPI change.

## Browser synchronization and safety

One `ECounselingConsentFreshnessProvider` inside `PortalBoundary` subscribes to the shared portal
socket, independent of Daily connection state. It belongs to the confirmed account, is stopped
during session uncertainty/account changes/unmount, and stores only pending appointment IDs and
booleans in its own lifetime. Existing account cache ownership discards protected data and late
responses on an account change. No browser storage, arbitrary subscriptions or extra socket.

For an appointment already represented in the account's QueryClient, hints invalidate exactly
these generated, role/capability-appropriate keys:

| Account | Consent list | Workspace |
| --- | --- | --- |
| Student | `getECounselingListMyConsentsQueryKey(id)` | `getECounselingGetMyWorkspaceQueryKey(id)` |
| Counselor | `getECounselingListAssignedConsentsQueryKey(id)` | `getECounselingGetAssignedWorkspaceQueryKey(id)` |

No other appointment or cache family is invalidated. Existing enabled active queries refetch;
inactive/disabled ones become stale without issuing requests. Page and persistent-call observers
share the canonical query, and there is only one hint subscriber. `cancelRefetch:false` reuses an
existing read. If that read began before the hint, one necessary post-hint read runs before the
Start fence lifts. Synchronous bursts collapse before fetching; further hints during a read set one
pending trailing reconciliation. New changes during that trailing read can request another; no
delivery/version/order guarantee is inferred from a hint.

An unresolved hint fences previous APPROVED data immediately, including while hidden/offline or
while an older read completes. Counselor Start requires a successful, idle, non-invalidated consent
query, no pending reconciliation, matching APPROVED workspace consent projections and the
existing confirmed workspace checks. A previously open
Start confirmation closes when its authorization becomes unconfirmed/invalid. Failed refreshes
retain only the existing last-known/error presentation and Retry; they cannot authorize Start.
Stop eligibility is independent of consent freshness and remains governed by existing capture
state/capabilities. Withdrawal never displays physical cessation merely from permission loss.
The backend still authorizes every Start; approval does not start media automatically.

## Healing and load

The single coordinator polls active **consent lists** every **7 seconds** while transport is not
live and every **60 seconds** while live. Seven seconds preserves the prior active-call fallback
and extends it to pre-call workspaces; sixty seconds follows Notification/Messages live safety
cadence. These are bounded UI freshness targets, not permission validity or delivery promises.

Normal safety polls do not add a workspace polling loop. TanStack structural sharing compares the
previous/current canonical consent item references: a confirmed change refreshes that appointment's
workspace once. The existing workspace/media lifecycle polling intervals remain unchanged.
Each advanced ready generation (including the initial ready), visible/focus return and online
return reconciles active consent/workspace keys. Hidden/offline tabs issue no coordinator requests;
pending hints wait for foreground recovery. Existing in-flight reads may finish. Unmount stops
timers/listeners and prevents trailing reads. A lost hint/Redis outage heals through these paths.

Expected additions: zero sockets and zero Redis subscribers. Each newly committed mutation
publishes one compact consent hint per currently eligible participant (at most two); request
Notifications retain their separate existing hint. A relevant hint reads at most one enabled active
consent list and one workspace, plus at most one pending trailing read at a time. Multiple tabs
retain ADR-100's one socket and their own active HTTP queries per tab. Database/Redis and safety
poll work are real overhead; no measured production latency/load reduction or guaranteed delivery
is claimed.

## Compatibility and deferred work

Consent rules, Daily command ordering, capture reducers, webhook provenance, reconciliation,
artifact/transcript custody, retention/deletion, lifecycle/assignment policy, Notification delivery
and Guidance Messages behavior remain authoritative and unchanged. RT-1B owns media Start/Stop,
webhook/reconciliation transitions, artifact readiness/custody and session lifecycle hints. None
of those publication paths is added here. The unrelated Encounter Institutional ID fix is excluded.

Local verification uses synthetic data, isolated PostgreSQL and Redis, normal authenticated
HTTP/session/ticket handling and the standalone ASGI socket boundary. Chromium/WebKit browser
fixtures demonstrate cross-account pre-call decisions, active-call stale confirmations, polling,
reconnect and access loss. They do not contact Daily or staging and do not prove live deployment.
Ship compatible registry/backend/frontend binaries through a separately authorized deployment;
missing hints during a mixed rollout are healed by polling. A code rollback restores the previous
consent polling policy without a data/schema reversal.
