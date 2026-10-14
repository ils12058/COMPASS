# ADR-111: E-Counseling media lifecycle realtime synchronization (RT-1B)

Status: Implementation proposed for owner review. Extends ADR-092/094/100/101/102/110.
PostgreSQL and authenticated HTTP remain authoritative. No deployment or enablement.

## Closed hint and current recipients

The existing Django-free backend registry and frontend parser register exactly:

```json
{"v":1,"type":"ecounseling.media.changed","appointment_id":"<canonical UUID>"}
```

The existing version, canonical UUID, exact-field and frame-size checks apply. No state, identity,
provider identifier, room, session, artifact identifier, location, link, timestamp, error or content
is carried. A frame requests a canonical read; it never changes permissions or issues provider
commands. Notification, Guidance Messages and consent contracts are preserved.

`media_changed_on_commit` uses the existing user publisher after the outermost SQL commit.
Rollback, including a nested savepoint rollback, discards its callback. Disabled realtime skips
recipient work. Publication errors cannot undo committed domain state; safe logs contain only
a closed event and exception type. There are no provider calls or SQL row locks during Redis IO.

The shared `workspace_participant_id` reloads canonical workspace authority before each recipient,
including again after the Student publication. Media delivery requires an active exact-role Student
owner with `ecounseling.view_self`, or the active currently assigned exact-role Counselor with
`ecounseling.view_assigned`. It requires no consent, media-management or download capability merely
to view a workspace hint. Consent delivery explicitly retains ADR-110's stricter capabilities.
No unrelated user or administrative designation is enumerated or broadcast to. Historical saved
rooms retain the existing canonical read policy. A race after recipient lookup remains possible;
every HTTP read and media action independently checks current authority.

## Explicit authoritative boundaries

Hooks are attached to existing domain transactions, never model signals:

| Boundary | Meaningful persisted change | Publication |
| --- | --- | --- |
| Recording/transcription Start | `NOT_STARTED` to `START_REQUESTED` | After intent commit, before provider IO |
| Known Start rejection | `START_REQUESTED` to `ERROR` | After rejection commit |
| Transcription configuration/mitigation | `storage_enabled` boolean changes | After that existing separate commit |
| Explicit Stop | Eligible capture to `STOP_REQUESTED` | After intent commit; unchanged repeated Stop is silent |
| Consent withdrawal | One or both new Stop intents | One media hint per recipient for the transaction, independently of consent hint |
| Verified webhook/replay | Legal capture transition and/or newly eligible `PENDING` artifact | One combined hint after application commit |
| Trusted metadata reconciliation | Legal capture transition and/or newly eligible `PENDING` artifact | One combined hint after application commit |
| Standalone artifact creation | No row to `PENDING` | Created row only, after commit |
| Ingestion claim | `PENDING`/`FAILED` to `PROCESSING` | After commit; unchanged reclaim is silent |
| Ingestion failure | `PROCESSING` to `FAILED` | After commit; unchanged failure is silent |
| Verified institutional custody | `PROCESSING` to `STORED` | After storage/integrity verification and SQL commit |
| Approved verified V1/V2 disposition | Disposed timestamp/availability, V2 `DISPOSED` | After successful final disposition commit |
| New provider room | `room_provisioned` false to true | After provisioning/audit commit, independent of later token failure |

Start acknowledgment does not establish `ACTIVE`. Stop acknowledgment/failure does not establish
`STOPPED` or `READY`. Uncertain provider failure changing only internal diagnostics creates no extra
hint. Provider binding/provenance, HMAC, terminal reduction, replay bounds, retry budgets and command
ordering remain unchanged. Duplicate, foreign, mismatched, malformed, quarantined or superseded
evidence is never promoted to trusted media. Current quarantine bookkeeping does not change the
ordinary workspace projection, so it creates no public anomaly hint or field.

Claims, attempts, backoff, receipt metadata, provider cleanup and unchanged diagnostics are silent.
Daily `READY` alone cannot make a file available: institutional integrity verification must precede
`STORED`. Cleanup failure after custody cannot erase or republish `STORED`. Disposition retains all
existing approvals, holds, claim checks, provider deletion and local deletion verification. No new
worker, schedule, outbox, model, migration or OpenAPI change is needed.

## One account-owned frontend coordinator

Extend ADR-110's existing coordinator with distinct consent/workspace work bits and freshness fences.
The existing provider subscribes once to the shared portal socket and wraps the persistent call
provider, preserving its confirmed-account key and lifetime. Media hints select only an already
known canonical appointment's exact Student or Counselor workspace key. They never allocate unknown
queries, refresh consent lists, touch another appointment or invalidate a whole query family.
Inactive/disabled queries become stale without forced HTTP. Resource denial suppresses reconciliation.

Page and persistent-call observers share one workspace query and one polling owner. Existing Daily
callbacks and settled Stop refreshes await the same coalesced workspace work. Synchronous bursts
collapse; `cancelRefetch:false` reuses an in-flight read. A read begun before a hint requires a fresh
trailing read. Each flush has at most one leading and one trailing pass; new hints during the latter
retain one pending bit for another invocation. Consent reconciliation and its complete post-hint
workspace read remain independent; a media event cannot clear the consent fence.

Pending media reconciliation, fetching, stale or failed workspace reads cannot authorize Start and
close stale confirmation. Existing consent/capability/backend authorization still applies. No hint
starts capture automatically. Existing Stop controls remain governed by capture state: legitimate
`ACTIVE` Stop remains usable during consent/workspace uncertainty, while `STOP_REQUESTED` retains
disabled **Stopping** pending confirmation. Permission loss never claims physical cessation.

## Recovery and bounded load

Active workspace policy is 7 seconds when transport is unavailable, and 60 seconds while live for
healthy calls/captures, joinable preparation and artifact safety. Unresolved `START_REQUESTED`,
`STOP_REQUESTED`, `ERROR` and legacy transcription `STOPPED` retain 7 seconds even while live.
Inactive historical settled workspaces have no media timer. Consent retains its independent 7/60
clock. A consent-only read cannot starve a due workspace poll; an already pending workspace read
prevents timer ticks from producing endless trailing work.

Initial/advanced socket-ready generation, focus/visibility return and online recovery reconcile
active canonical queries. Hidden/offline tabs initiate no coordinator HTTP and retain pending hints;
already in-flight requests may complete. Account uncertainty/change and unmount clear timers,
subscriptions and pending work and fence late responses using existing account ownership.

Expected additions are zero sockets and zero Redis subscriptions. Each genuine domain transition
publishes at most one frame per eligible participant (at most two); combined webhook/artifact and
withdrawal transitions avoid duplicate frames in the same transaction. One media hint normally reads
one active workspace, with one pending trailing read when required. Multiple tabs retain one shared
socket per tab and each tab's own active HTTP reads. SQL recipient checks, Redis publication and safety
polls incur overhead; no guaranteed delivery, production latency or measured production load reduction
is claimed. Local tests prove request bounds and recovery, not a production performance benchmark.

## Validation and scope

Synthetic real PostgreSQL transaction/concurrency tests and real Redis/ASGI authenticated HTTP/socket
tests cover lifecycle, authority, rollback and refused transport. Frontend Node and Chromium/WebKit
tests cover two participants, truthful states, custody, shared queries/socket, polling, coalescing,
recovery, access denial and RT-1A/persistent-call compatibility. The handoff report records exact
commands, results and CI state; CI results remain independent of local verification.

General Appointment/Encounter/Routine/referral/dashboard synchronization and unrelated UI/UX are
deferred. The separate Turbopack/Outfit issue is not remediated or bypassed here. No infrastructure,
keys, live Daily artifacts, real Student data, worker activation, merge or deployment is authorized
by this implementation. Open one focused PR against `staging` and stop for owner review.
