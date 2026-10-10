# ADR-105: Guidance Work Queue and Messages operational hardening

Date: 2026-10-10
Status: Accepted

## Context

[ADR-058](ADR-058-portal-overview-summary-projection.md) introduced role-aware Overview counts;
[ADR-090](ADR-090-collection-ordering-and-sortable-list-contracts.md) established actionable
attention ordering. Guidance Messages now has immutable sender provenance and explicit Office
handlers ([ADR-102](ADR-102-guidance-messages-backend-foundation.md),
[ADR-104](ADR-104-guidance-messages-staff-operations.md)). Staff need one actionable list derived
from those existing domains. A second persisted task lifecycle would drift from their truth.

## Decision

### Messages operations

Live-staging host preflight requires the independent `guidance_message_encryption_keys` file to
be non-empty, regular, correctly owned, and `0444` inside the protected secrets directory. This
is a deployment gate, not a global Django requirement: only web receives the Messages content
keyring; worker, beat and realtime remain intentionally keyless. No deployment, key generation,
provisioning, or key retirement is automated by this slice. Operators follow
[runtime-secrets.md](../runtime-secrets.md) before deploying the Messages-enabled web service.

`rotate_guidance_message_encryption --dry-run --batch-size 100` verifies each existing bound
envelope through the domain content accessor: stored schema, thread and Message UUIDs, sequence,
sender UUID, exact payload shape and valid body. The real command locks batches of 1–1000 rows
and uses shared MultiFernet rotation for older-key tokens. Current-primary tokens write nothing.
It updates only `GuidanceMessage.body_ciphertext`, preserving immutable Message facts, token
timestamp, thread business metadata, read states, assignment and resolution. It emits no Audit,
Notification or realtime hint. Invalid rows stay unchanged; at most twenty safe structural
failures are listed and the command ultimately exits nonzero. Interruption and reruns are safe.

Template PATCH requires the exact timezone-aware `expected_updated_at` opened by the editor.
The service requires that keyword and compares it under the template lock. Stale versions return
409 without overwrite. The browser keeps unsaved name/text, reads the current active template
separately, blocks Save and requires deliberate review before continuing the draft. It never
replays the rejected mutation. Archive/restore policy is unchanged.

### Read-only Guidance work

`GET /api/v1/work`, operation `workQueueList`, serves active Counselors and Guidance Services
Staff. No new capability, model, migration, assignment table, WorkItem, Task, Case or FollowUp
state exists. Head receives this workspace through the Counselor role. Each domain-owned helper
checks its existing current action authority and scope; capability removal removes that source.
Unexpected source failures fail the request, never return a partial 'caught up' projection.

The closed source set is:

| Kind | Canonical action predicate | Time |
| --- | --- | --- |
| GUIDANCE_MESSAGE_REPLY | OPEN Office assigned to actor, or Counseling with exact persisted Counselor; current manage policy; latest Message at last_sequence sent by Student | last_message_at |
| ROUTINE_EVALUATION | Assigned Counselor with view/manage authority, submitted intake, unfinalized evaluation, parent Appointment not CANCELLED/NO_SHOW | intake_submitted_at |
| GOOD_MORAL_PREPARATION | REQUESTED and canonical operational good_moral.prepare authority | created_at |
| GOOD_MORAL_ISSUANCE | READY_FOR_ISSUANCE and canonical Counselor good_moral.issue authority | prepared_at |
| CALL_SLIP_DUE | Current Call Slip operational view scope, ACTIVE and report_at <= aware server now | report_at |

Unread/read cursors never determine reply work. Assignment is ownership, never ACL. No Message
body, preview, ciphertext or inferred subject is selected or returned. Opening the owning
conversation performs its normal authorized content read. Good Moral stays office-wide;
issuance remains Counselor-only even if GSS has an issue capability override. Call Slips retain
their intentional Head oversight; GSS inherits only the supervisor's finite workload. Messages
and Routine keep their narrower workload/exact-provider rules (ADR-099).

Strict item schemas expose stable kind+source UUID identity, closed kind/priority enums, source
UUID, Student UUID/display name, optional conversation kind and due/waiting instants. They contain
no metadata dictionary, frontend route or confidential content. Priority is TIME_SENSITIVE for
due Call Slips and ACTION_REQUIRED for the other sources. Global ordering is priority class,
earliest present due instant, earliest present waiting instant, then lexical stable identity.
Missing instants sort after present instants. Source SQL uses the same timestamp and UUID order.

Pagination defaults to page 1, size 20; size is at most 50 and page at most 100. Ending at N reads
only N+1 rows per fixed source, merges at most five such prefixes, sorts and slices. `has_next`
is an actual extra-row fact; no total is invented. Invalid/deep pages return typed 422. At the
page limit the UI states that more work remains and directs staff to owning workspaces. This
bound caps source prefixes at 5001; it is an execution bound, never a promise that all work fits.

`/portal/work` (My work) is the first daily staff navigation workspace. Its semantic ranked list
has visible domain links and no inline mutations. Empty is shown only after a confirmed complete
query. Transient refresh failures preserve confirmed account-owned data with a stale notice;
authorization/session boundaries hide or discard it. Overview staff 'Needs your attention'
uses the same first-five projection and links to View all work. The old independent staff
Routine/Good Moral previews are removed; Student self-service attention, IT email attention and
the separate Overview count contract stay intact.

The existing shared realtime runtime's `messages.thread_changed` invalidates canonical Work Queue
queries; a new ready generation reconciles missed hints. No new event or socket is added. HTTP
remains authoritative with visible/online safety polling around 60 seconds and focus/reconnect
refresh. Same-tab successful domain actions invalidate the same query family where practical.

## Consequences and deferred scope

Work disappears because its source domain changes. There is no queue dismiss, snooze, manual
priority, reminder, completion state, SLA or AI. Future Call Slips remain schedule context.
Appointments and Referrals acquire no invented task/follow-up states. Student Action Center is
deferred; existing Student attention remains. Messages retention/disposition remains governed
by ADR-072/102 and requires adopted human policy; encryption rotation establishes no retention
duration or deletion behavior. No deployment is performed by this implementation.
