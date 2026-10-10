# ADR-107: Guidance operations dashboard

Date: 2026-10-10
Status: Accepted

## Context

Overview is the quick landing and its At a glance counts are context ([ADR-058](ADR-058-portal-overview-summary-projection.md)).
My work identifies exact records requiring the actor's action ([ADR-105](ADR-105-guidance-work-queue-and-messages-operations.md)).
My actions is personal Student self-service ([ADR-106](ADR-106-student-action-center.md)). Reports
owns historical/analytical questions. Guidance staff need a compact current operational summary
without merging these products or evaluating anyone's performance.

## Decision

`GET /api/v1/guidance-operations`, operation `guidanceOperationsGet`, serves a freshly checked
active COUNSELOR or GUIDANCE_SERVICES_STAFF. `/portal/operations`, Guidance operations, follows
My work in Daily work navigation and the shared command palette. No capability is added. Each
metric independently requires its source's current effective authority. Null means unavailable
or inapplicable; a zero is an authorized empty population. Null rows are hidden; zeros are shown.

There is no universal Guidance Office scope. Assignment is ownership, never ACL. Head designation
broadens only domains that explicitly grant it. GSS inherits legitimate operational workload
through current supervision, never Counselor-only relationships or powers. Aggregates do not
permit scope expansion. Neither the composition nor frontend reconstructs resource policy.

### Closed actionable backlog

Each source supplies direct SQL COUNT and MIN over the same internal query as its My work prefix.
No Work Queue page, serialized row, or page length supplies a total.

| Metric | Current canonical population | Oldest fact |
| --- | --- | --- |
| Messages awaiting reply | OPEN, current manage authorization, OFFICE assigned to actor within current operational scope or COUNSELING with exact persisted Counselor; latest structural sender is Student | MIN(last_message_at) |
| Routine evaluations pending | exact Counselor, view/manage assigned, submitted intake, unfinalized evaluation, canonical parent not CANCELLED/NO_SHOW | MIN(intake_submitted_at) |
| Good Moral needs preparation | REQUESTED, active Guidance operational good_moral.prepare | MIN(created_at) |
| Good Moral ready for issuance | READY_FOR_ISSUANCE, active Counselor good_moral.issue | MIN(prepared_at) |
| Call Slips due | canonical operational view scope, ACTIVE, report_at <= request now | MIN(report_at) |

The domain helpers share narrow predicates, and retain bounded ordered prefixes for My work.
Count zero requires a null oldest instant; a positive count requires its structurally required
aware timestamp. Strict wire schemas validate that relationship and forbid additional fields.
Message queries select no body/ciphertext, decrypt nothing, and never advance read state. Unread
does not define reply work. Unauthorized assignments, unassigned Office threads and other
handlers' authorized Office threads contribute no personal reply backlog.

Head retains institution-wide Call Slip oversight and existing Good Moral office-wide policy.
Head receives no universal Counseling Message, Routine or Counseling Appointment population.
Multiple active Heads preserve the operational resolver's fail-closed fallback. GSS has scoped
Office work, preparation, Call Slips and managed organizational scheduling where authorized;
Routine, Counseling Messages, Good Moral issuance and personal-provider scheduling stay unavailable.
An issuance capability override alone does not turn GSS into a Counselor.

### Schedule and Overview

Schedule contains only Counselor own upcoming Appointments, GSS managed upcoming Appointments,
and canonical scoped active Call Slips. Counselor managed and GSS own Appointment metrics are
null. Counseling management remains RELATIONSHIP_ONLY; organizational management retains its
existing scope. Head's organizational oversight does not broaden Counseling. All helpers receive
one aware server now, also used for generated_at and the inclusive Call Slip due boundary.
The existing Appointment helper uses SCHEDULED and starts_at >= now; equality is retained,
and an instant after starts_at removes it from upcoming. Future ACTIVE Call Slips are schedule
context even when absent from due backlog. No Appointment row/time/identity is returned.

Overview remains the landing, with At a glance and Needs your attention intact. Its pending
Routine count now shares canonical actionability, excluding cancelled/no-show parents rather
than disagreeing with My work and operations. Overview's Good Moral view-authorized state counts
remain contextual; the new backlog independently requires prepare/issue action authority.
This is a subsequent refinement of ADR-058/090, not a rewrite of their historical decisions.

### Presentation and freshness

Two compact semantic definition-list panels show separate facts, zeroes and associated plain
oldest waiting/due times in Philippine Time. There is no universal sum, urgency color, SLA,
aging bucket, score, target or chart library. Empty wording is confined to the workflows available
to the actor; failed refresh of an empty result does not assert a current empty office.

Only exact existing destinations link from a count: REQUESTED/READY Good Moral, UPCOMING own/
managed Appointments, ACTIVE Call Slips. Messages and due Call Slips have no exact filter. The
existing Routine submitted/DRAFT filter also includes closed parents, so that metric stays
informational rather than claiming a matching population. Open My work is the general action.
No source filter is added merely to make a number clickable. Source-list history remains intact.

HTTP owns every metric in the account-owned QueryClient. Existing messages.thread_changed and
new ready generations invalidate the summary; no event/socket/store is added. Visible/online
60-second safety polling, focus and reconnect heal missed hints and time transitions. Relevant
confirmed same-tab source mutations invalidate My work and Guidance operations through one small
query-family helper, including Message send/assignment/status, Routine finalization, Good Moral
preparation/correction/issuance/cancellation, Call Slip changes and Appointment changes.
Transient refresh failures retain confirmed facts with a stale notice; first load has Retry;
authority/session failures hide protected data and identity changes discard the previous cache.
Unexpected source failure fails the whole request, never masquerades as an unauthorized null.

## Boundaries and deferred scope

No model, migration, metric cache, snapshot, background worker or scheduled aggregation exists.
The fixed aggregate queries have bounded query cost and load no Student records/content.
No Student/Counselor/source IDs, identities, Message previews, confidential answers or record
details are in this API. Reports builders, exports, year/campus/College/program selectors and
small-cell advisory policy are not reused.

Staff performance/productivity, response/handling rates, leaderboards, per-Counselor distribution,
College breakdown, Counseling case counts and Student Support counts remain outside V1.
Supervised Activity ([ADR-073](ADR-073-curated-activity-retrieval-and-supervision.md)) is not an
analytics grant; no Audit Event KPI is built. Student Actions are not aggregated. Referral pending
states, Exit office backlog, Graduate Tracer/Feedback analytics require separate domain decisions.
Messages retention/disposition remains deferred. This phase performs no deployment or secret
provisioning and adds no migration/sync command.
