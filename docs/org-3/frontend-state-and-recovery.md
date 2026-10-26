# State ownership and recovery

TanStack Query owns reads/mutations; React owns one editor intent, draft, review and recovery state.
The workspace is keyed by account/session UUID. Editors are keyed by a local intent sequence,
never by server timestamp/version, so refetch cannot erase typed values. No global state framework,
polling, WebSocket, persistent draft or archived editor was added.

Queries use generated operation functions and keys. Catalog presentation queries extend the
corresponding generated key with a suffix so normalized presentation values cannot collide with
Orval's raw transport-response cache. History includes the actual page parameters. Reads disable
retry; arbitrary mutation retry is explicitly false. Shared API transport still owns cookies/CSRF.

After success, invalidate only Campus/College/Program collection keys (including filter variants),
target detail/impact/history. This updates nested parent labels and current-use list selectors
without invalidating the whole application. The mutation's returned persisted record confirms save;
refresh has a distinct result. Refresh failure says exactly: “The change was saved, but the latest
details could not be loaded.” Retry refresh performs reads/invalidation only; submission is gone.

Transient hierarchy refresh failures keep last confirmed reference data marked by
RefreshFailureNotice and disable Catalog actions. Authority/session failures hide cached reference
data through existing safeQueryData behavior. Editor target failure similarly prevents review and
labels any safe retained record Last confirmed record. Impact failure never leaves an enabled
consequential action backed by an old preview.

A stale response closes the confirmation, preserves local input, reloads current details/impact
and shows the latest saved values separately. Review builds a new explicit command only after
successful reads. If the version changes during Review, the editor shows a comparison notice and
requires another Review click. It never silently changes an expected version and resends. No-op
input receives honest feedback.

A transport failure or server 5xx can mean the mutation committed. The editor blocks its mutation
and performs read-only reconciliation: current record and restricted history. Creation first
locates a newly appearing normalized-code identity in the exact parent context, excluding IDs
known when the intent began. History must match actor, basis, action, expected version transition
and proposed safe values; creation also matches initial version, parent and complete policy.
A matching authoritative event triggers a second detail read (including commits between the first
read and history). Only a detail version at least as new as that event confirms the committed
change without sending another request.
The latest record can show subsequent changes, and history remains the accountability evidence.

If no such evidence can be found, the result remains unconfirmed. Check saved state repeats reads
only. There is no blind retry button. First-page history reconciliation is deliberately conservative:
if a matching event is no longer on that bounded page, it stays unconfirmed rather than guessing.
Reconciliation is not backend idempotency and does not replace ORG-2 locks, versions or Audit.

The existing useUnsavedChangesGuard protects navigation/discard. Dirty Cancel requires deliberate
discard; declining keeps values. Review/MFA transitions, recoverable conflicts and refreshes do not
replace the draft. Current actor/session checks prevent an old draft being submitted by a new owner.
