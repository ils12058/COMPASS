# Implemented Student Home information architecture

## Understand and act

The header keeps the existing time-of-day greeting and appropriate name, calculated in the
institution's Asia/Manila timezone. The date uses the same zone even when the browser is in another
zone. A small Overview context establishes page identity. Book appointment remains the one primary
PageAction, visible only when `getAppointmentAccess(user).canBook` permits it. It opens booking;
it does not assert that a slot exists or create an Appointment.

Needs your attention is the first full-width working region. Its existing canonical query asks for
page 1/size 5; source rows stay in exactly the returned order. View all actions opens the existing
`/portal/actions` workspace. There is no Home pagination, reconstructed total or client ranking.

Each row has a heading, existing domain-owned presentation copy/timing and one link to the owning
workflow. The presenter's Time sensitive label is shown only for server `TIME_SENSITIVE` priority;
ordinary due timestamps never acquire invented urgency. Source links retain their UUID context.
There are no inline workflow mutations. Shortlist length, action kinds, eligibility and timing
remain governed by ADR-106 and the backend source domains.

## Explore and check context

Guidance services is a selection of at most four workspace links, not a task queue or another
complete navigation system:

| Destination | Existing gate | Meaning |
| --- | --- | --- |
| `/portal/appointments/my` | `getAppointmentAccess().canViewSelf` | Read one's scheduling workspace, without implying booking eligibility. |
| `/portal/messages` | `getGuidanceMessagesAccess().canViewSelf` | Open one's conversations, without marking read on Home. |
| `/portal/graduate-tracer` | `getGraduateTracerAccess().canViewSelf` | Open a graduate's voluntary survey workspace. |
| `/portal/inventory` | `getInventoryAccess().canViewSelf`, when Tracer is not selected | Open one's Inventory and historical records; no new required Inventory is inferred. |
| `/portal/good-moral` | `getGoodMoralAccess().canViewSelf` | Read requests/status, without claiming a certificate is ready or initiating a request. |

The Tracer/Inventory position adapts to the existing lifecycle-aware gate; this keeps the selection
small. A Current Student does not receive graduate access from a capability alone. Graduated and
Former Students do not receive Current-only Book commands. Historical Inventory reading remains
available where its existing helper allows it. Missing self-view capabilities remove corresponding
links. Student role alone authorizes none of these shortcuts.

Group Sessions, Exit Interviews, Routine Interviews and other applicable destinations remain in
the dock and feature search. Canonical pending actions still link directly to them when appropriate.
The management Services workspace is not advertised as a Student service catalog.

At a glance reuses OverviewSummary and the existing exact metric helper:

| Metric | Meaning retained | Destination retained |
| --- | --- | --- |
| Upcoming appointments | Scheduled self Appointments that have not started | `/portal/appointments/my?status=UPCOMING` |
| Routine Interview drafts | Unfinished self intakes for Current Students with manage_self; otherwise null | `/portal/routine-interviews` when authorized |
| Good Moral requests | Open self requests in REQUESTED or READY_FOR_ISSUANCE; the count does not distinguish readiness | `/portal/good-moral` when authorized |
| Active Call Slips | Domain-counted active self Call Slips | `/portal/call-slips?state=ACTIVE` when authorized |

Null metrics are omitted, not rendered as zero. Successful zero remains zero. A count is not a
schedule, readiness state or required action. Missing summary content never hides confirmed actions
or discovery. Summary loading, initial failure/Retry and stale-count copy retain their shared behavior.

## Stay informed

Announcements follows action/discovery/status information and remains a semantic list of up to
three visible records. Its existing authenticated visible feed decides audience and recommended
publication ordering. Pins and published dates are preserved. All announcements and record links
continue to use the existing reader routes. A backend failure is not a confirmed empty feed.

## Responsive and accessible structure

The DOM and keyboard content order is header command → attention/View all and source links →
service discovery → summary links → Announcement links. There is one existing shell `main`, one
page h1, h2 panel headings and h3 action titles. Native links navigate and Retry buttons refetch.
Focus rings and established rem-based minimum targets remain visible.

The action preview always spans the content region. At 58rem of available container width,
discovery and the 21rem summary region share a row. Discovery itself uses two columns only at
32rem of its own width. Narrower regions stack. Thus an expanded dock or enlarged root text can
restore the single-column layout without JavaScript viewport state.

Action labels move alongside details only when their own region has 38rem available; otherwise
they sit below them and wrap. Announcements pairs its date badge and title only above 22rem of
its own width; below that they stack so titles retain reading space. Local emergency wrapping
handles an oversized heading/long word, including the known 320px/200% case. No document clipping
or horizontal overflow suppression is used.

Reduced motion continues to use the existing shared CSS; no animation was introduced. Home has no
live announcement of every refresh or new action count. Initial action loading gives one bounded
LoadingRegion status; stale notices use the existing persistent status pattern.

## State model and ownership

| State | Presentation |
| --- | --- |
| Initial action read pending | Bounded skeleton with busy region; no completion claim. Other projections remain independent. |
| Confirmed actions | Actual first-five rows in server order, with existing source links. |
| Successful empty action response | Shallow confirmation that no current actions need attention; discovery and Announcements remain. |
| Failed refresh with confirmed rows | Last confirmed rows plus explicit freshness uncertainty and Retry. |
| Failed refresh after empty result | Freshness uncertainty, Retry and “Your last confirmed result had no actions.” No current caught-up claim. |
| Initial action failure | Existing unavailable row, Open My actions and Retry; no implied zero. |
| Permission/session refusal | Existing safe-data helper hides protected rows; session verification/sign-in behavior remains owned by the shared boundary. |
| Account switch/sign-out | Existing QueryClient ownership discards previous account data before showing the next account; no browser-persisted Home state. |

StudentHome and StudentHomeAttention own presentation only. PortalHome retains the queries and
selects the Student composition; professional Home retains its previous composition. Domain APIs,
generated clients, navigation, freshness/invalidation and mutation workspaces retain ownership.
