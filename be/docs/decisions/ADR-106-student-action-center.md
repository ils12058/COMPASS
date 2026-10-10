# ADR-106: Student Action Center

Date: 2026-10-10
Status: Accepted

## Context

Students need one truthful next-action list. Overview previously assembled partial attention from
independent Inventory, Routine, current Exit and Graduate Tracer calls. This missed admitted Exit
opportunities and historical corrections and could leave closed-parent Routine drafts visible.
[ADR-058](ADR-058-portal-overview-summary-projection.md) and
[ADR-090](ADR-090-collection-ordering-and-sortable-list-contracts.md) establish cross-domain
projection and attention ranking; [ADR-105](ADR-105-guidance-work-queue-and-messages-operations.md)
introduces the sibling Guidance staff Work Queue.

## Decision

`GET /api/v1/student-actions` (`studentActionsList`) is an active-Student-only, read-only composition.
Source domains remain the authoritative workflow. There is no StudentAction, Task, Case, FollowUp,
manual completion/priority/assignment, capability, model, migration, cache or new realtime event.
Capability overrides and source lifecycle/resource ineligibility contribute zero. Unexpected source
failures fail the complete request; a partial projection cannot claim the Student is caught up.

The closed V1 sources and kinds are:

| Source | Kind and eligibility | Truthful time |
| --- | --- | --- |
| Individual Inventory | INVENTORY_START missing current year; INVENTORY_CONTINUE draft (including reopen); active/current Student and manage_self; submitted absent | draft creation; no deadline |
| Routine intake | ROUTINE_INTAKE owned/current/manage_self, unsubmitted, canonical parent actionable; CANCELLED/NO_SHOW absent | creation; no deadline |
| Exit opportunity | EXIT_INTERVIEW_START canonical can_start: OPEN current-year opportunity, current/manage_self, submitted Inventory, no current response | opportunity opened_at |
| Exit drafts | EXIT_INTERVIEW_CONTINUE admitted legacy/OPEN initial draft; EXIT_INTERVIEW_CORRECTION first-submitted response reopened into draft, including historical years; owned/current/manage_self, matching opportunity provenance | latest reopen (fallback creation), otherwise creation |
| Graduate Tracer | GRADUATE_TRACER_CONTINUE only existing personal DRAFT, GRADUATED/manage_self, not anonymized/disposed; mere availability absent | creation |
| Call Slip | CALL_SLIP_ACTIVE owned/view_self, LIVE, no end/void; HISTORICAL and LEGACY_UNKNOWN absent | report_at deadline and creation |
| E-Counseling consent | ECOUNSELING_CONSENT owned ONLINE Counseling, consent_self, PENDING/unwithdrawn, grouped per Appointment; denial remains canonical after graduation | earliest pending requested_at |
| E-Counseling join | ECOUNSELING_JOIN exact active/current Student/join_self, canonical active Counseling service, ONLINE/SCHEDULED, eligible active Counselor provider, Daily enabled, inclusive local window OPEN | window end deadline, window start |
| Guidance Messages | GUIDANCE_MESSAGE_UNREAD authorized own threads, view and manage_self to read/advance cursor, inbound sequence after own cursor; includes RESOLVED | oldest inbound unread created_at |

Inventory submission precedes startable Exit; graduation Good Moral dependency is represented by
that Exit action, never an additional obligation. Graduate Tracer availability is voluntary.
Call Slip recordkeeping never becomes a live instruction. Generic future Appointments are schedule
context; the currently open online Counseling window is the sole join exception. Listing calls no
Daily API and exposes no token, room URL, provider identifier or secret. Messages selects only
structural facts, never body/ciphertext or decryption, and listing never advances a read cursor.
Unread means read communication, never required reply. Multiple scopes/messages give one row per
Appointment/thread with an optional structural pending count.

Strict item schemas contain stable kind plus source UUID identity, closed eleven-kind and
three-priority enums, source UUID, nullable due/waiting timestamps, conversation kind and positive
pending count. No generic metadata/payload, Student identity/content or frontend route is returned.
Priority is TIME_SENSITIVE (open join, report time reached), ACTION_REQUIRED (Routine, Exit,
consent, unread, future LIVE Call Slip), INCOMPLETE_SELF_SERVICE (Inventory/Tracer).
Ordering is priority, earliest present due, earliest present waiting, lexical stable ID; absent
instants sort last. One aware server now drives the request and generated_at.

Default page 1/size 20; maximum size 50/page 100. Each multi-row source applies eligibility and its
matching rank in SQL before LIMIT N+1 (N = page * size); bounded source prefixes prove the global
N+1 before merge/slice. No authoritative total is invented. Page 100 is an execution bound, not a
promise all histories fit. The UI directs Students to source workspaces if more remain. Live
paging does not promise a frozen snapshot while underlying actions change.

`/portal/actions` (My actions) is the Student daily workspace: one semantic ranked list with one
owning-domain link per item, human copy, truthful institutional Asia/Manila times, visible focus
and usable touch targets. It has no inline completion. Empty follows a confirmed complete result;
transient failure retains confirmed account-owned data with a stale notice; first load shows Retry;
authority/session failures hide or discard protected data. Overview uses the same first-five
projection plus View all actions. Its old independent Student attention calls are removed; At a
glance counts and staff/IT attention retain their separate contracts.

The portal's single socket supplies `messages.thread_changed` and `notifications.changed` freshness
hints. HTTP determines all items. A new ready generation, visibility/focus, online recovery and
visible/online 60-second safety polling heal missed hints and time-window transitions. Same-tab
successful Inventory/Routine/Exit/Tracer/consent/read-state mutations invalidate the same Query
family. The account-owned QueryClient discards data at identity boundaries. No new socket/store.

## Deferred scope

Unread Notifications themselves are not actions. Good Moral REQUESTED/READY states belong to
staff; issued downloads have no acknowledgement completion state. Feedback remains optional
informational; shared summaries have no canonical Student-read state. Referrals receive no
invented Student lifecycle. Manual reminders/follow-ups, generic tasks, AI prioritization,
Messages retention/disposition, Good Moral retention and deployment are outside this phase.
Historical ADRs remain historical and are not rewritten by this decision.
