# Student Home experience audit

Audited against integration `613525bf9c7ed41dca8869fd717b5baf360f2f70`. The initial experience
findings and plan were recorded before implementation; exact metric populations were additionally
cross-checked against domain count helpers during final review.

## Verified behavior

`PortalHome` owns one Overview summary query and the shared `useOverviewAttention` adapter.
Its current hierarchy is greeting/date and authorized Book command, attention and Announcements
in a main column, then At a glance in a 20rem companion column. On phones Announcements precede
the summary. This same composition serves all roles.

- `useStudentActions(user, 1, 5)` reads the canonical Student Actions first page. It already keeps
  server inclusion, order, source IDs, timestamps and routes, using `presentStudentAction`.
  `/portal/actions` owns the full paginated list. ADR-106 supersedes the historical Student
  aggregation described in ADR-090; no client ranking should be introduced.
- Student Actions uses generated queries, account-owned QueryClient state, 60-second safety
  polling, focus/reconnect/visibility reconciliation and existing Message/Notification hints.
  `safeQueryData` retains confirmed data only after transient errors and hides it on 401/403.
  Only successful empty results establish that no actions remain.
- Overview's backend composes exact domain counts. Null is unavailable/inapplicable, not zero.
  Student counts mean upcoming Appointments, unfinished Routine intakes for Current Students,
  open Good Moral requests (REQUESTED or READY_FOR_ISSUANCE) and active Call Slips. The Good Moral
  number does not distinguish those two states and is not a certificate-ready count. These are
  context, not schedules or new obligations. Non-Current Routine draft counts are null.
- Counselor and Guidance Services Staff attention reads My work. Head Guidance Counselor remains
  a Counselor designation. IT Administrator email status/attention uses the Overview platform
  section and capability; Institutional Officer/DPO has no added confidential queue or metrics.
- Announcements reads the visible-audience endpoint at page 1/size 3. The backend controls
  recommended publication order and pinning. Links open public reader routes with signed-in
  visibility checks; there is no Home-specific audience filtering.
- The dock and command palette already provide complete authorized navigation. Appointment
  booking requires Student/manage_self/CURRENT. Inventory reading is distinct from CURRENT-only
  editing; Graduate Tracer self access requires GRADUATED. Good Moral and Messages use their
  existing self-view gates. The Services workspace requires catalog management; a catalog-read
  capability does not make `/portal/services` a Student browse destination.

## Journeys and shortcomings

New Current Students already receive an Inventory action when the backend establishes one.
Intake, Call Slip, consent, join and unread communication belong to the same canonical preview.
However, the preview discards the presenter’s visible time-sensitive label, places View all in
its own extra band, and gives no retry beside stale confirmed data. After a failed refresh of an
empty result the region gives freshness copy but little orientation.

Students with completed work have no service discovery within Home beyond Book and count links.
Relying on counts for navigation makes discovery depend on a successful summary query. Existing
counts are useful but have equal visual framing to actionable work, and the fixed companion
column can squeeze the main region beside the expanded dock. Announcements interrupt the mobile
path from actions to supporting status.

Graduated and Former accounts must keep their actual read access without receiving Current
booking or inferred Inventory obligations. Tracer availability is voluntary: only an existing
draft enters the action projection. A failed source must never masquerade as completed work.

At 320px/200% root text, the Announcements heading's intrinsic word width exceeds its PanelHeader
region. PanelHeader already wraps its flex children and gives them min-width zero; the missing
piece is emergency word wrapping in this local panel. No global clipping or shared Panel change
is justified. The separate 1024px/200% Inventory defect remains out of scope.

## Design decisions and plan recorded before source changes

1. Keep shared queries, ordering, freshness, navigation, backend eligibility and mutation owners.
2. Extract only Student presentation: attention first, a compact four-destination service list,
   supporting counts, then Announcements. Keep professional composition intact.
3. Retain greeting, institutional date, Overview identity and authorized Book PageAction. Use
   container width to place supporting counts beside work only when both fit comfortably.
4. Keep five server-ordered preview rows, moving View all into the title band. Show only the
   presenter's real time-sensitive label; provide explicit loading, empty, failure and stale retry.
5. Discovery offers Appointments, Guidance Messages, Good Moral and Inventory (or Graduate
   Tracer when authorized). These links open workspaces; they promise no availability or required
   task. Group Sessions and other destinations remain discoverable in the existing dock/search.
6. Apply local Announcements wrapping, preserving its query, audience, list and destination rules.
7. Capture synthetic baseline/final views and measure all requested widths/root text sizes in
   Chromium and WebKit. Test access/lifecycle/state transitions and professional non-regression.

All identified production changes can remain frontend-only. No new read model, API, permission,
form engine, action aggregation, dashboard framework or backend migration is needed.
