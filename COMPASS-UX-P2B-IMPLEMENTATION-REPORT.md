# COMPASS-UX-P2B Implementation Report

## Delivery

- **Branch:** `codex/ux-p2b-portal-collections`
- **Base:** `origin/staging` at `bb59ee249e206bbac011b7c64f40d710dfc02db5` (includes UX-P1 PR #273)
- **PR target:** `staging`
- **Scope:** frontend collection tables only; no UX-P2A-owned detail pages or shared UI primitives changed

The managed appointment, referral, and operational Call Slip tables now expose their horizontal scrolling region to keyboard and assistive technology users. They have a visible scroll hint, keyboard focus, Left/Right scrolling, and a pinned primary identity column. The appointment selection column remains pinned alongside its identity column for authorized reminder senders. Existing mobile summaries stay in place.

Services already uses a responsive record list instead of a table, so that page needed no layout change. Its URL-backed search, booking filter, manager-only inactive toggle, sorting, and empty state were preserved.

## Audit matrix

Criteria are grouped as follows: **1–3** search, filter organization, and applied-filter awareness; **4** sorting; **5–7** columns, responsive behavior, and record identity; **8–9** row and bulk actions; **10–12** loading/error/empty states and pagination; **13–14** surface density and copy; **15** keyboard, assistive technology, and role/capability behavior.

### Priority A

| Collection | 1–3 Search and filters | 4 Sorting | 5–7 Columns, responsive layout, identity | 8–9 Row and bulk actions | 10–12 States and pagination | 13–14 Density and copy | 15 Keyboard and role behavior | Decision |
|---|---|---|---|---|---|---|---|---|
| Managed Appointments | Search and structured filters share one explicit Apply action; the applied filter count excludes the default scheduled status. URL state is retained. | Sort field and date header show the active order; header reports `aria-sort`. | Eight useful columns at desktop, mobile record summaries below `md`. The reference code is the row identity. At narrow workspace widths the table previously scrolled without keeping identity visible. | Detail link is the row action. Counselor/GSS reminder selection has a count, a 25-item limit, Send reminders, and Clear selection. | Skeleton, retry, distinct filtered/empty messages, and canonical pager are present. | One results panel; status and dates have clear emphasis. | Reminder controls remain role-gated. Implemented a named, keyboard-scrollable table region; pinned the selection and appointment identity columns. | **Implement** |
| Referrals | Search and filters share explicit Apply; date-range validation stays in the panel; active structured filters are counted. URL state and browser history are retained. | Sort field plus sortable Student and Referred headers show active ordering. | Referral identity and student context lead a 760px table; mobile summaries preserve the same facts. The desktop table previously lacked a focusable scroll region and pinned identity. | Referral code opens the record. Record action remains capability-gated. No bulk operation exists. | Skeleton, retry, filtered-empty clear action, and canonical pager are present. | One results panel; status notes are capped at two lines in the table and fully available in the record. | Manage/view capability checks are unchanged. Implemented the named, keyboard-scrollable region and pinned referral identity. | **Implement** |
| Call Slips | Student filters and operational search/filter flows remain distinct. The operational filter count reflects applied criteria; invalid date ranges remain blocked. | Operational list has an active Sort field and sortable Student/Report headers. The self-service list has no sorting parameter. | Operational list uses an 850px table and mobile summaries; Student list is already a compact responsive list. Student is the operational row identity. | Issue action, referral link visibility, and self-service navigation continue to follow existing capabilities. No bulk operation exists. | Skeleton, refresh failure, retry, distinct empty states, and canonical pager are present. | Results panel keeps status, destination, referral, and timestamps grouped for scanning. | Student vs. operational access remains separate. Implemented the named, keyboard-scrollable operational table region and pinned Student identity. | **Implement operational table** |
| Service Catalog | Debounced search remains URL-backed and browser history-aware; booking and manager-only inactive filters remain available with clear state. | Sort field shows the applied service ordering. | Responsive semantic list presents service name/code, delivery, booking, and relevant status without a wide table. | Service name opens its record; Create remains manager-only. No bulk operation exists. | Skeleton, retry, distinct no-service/no-match copy, and canonical pager are present. | Service rows stay as one list, without extra cards or a second filter surface. | Existing search field, filter dialog, links, and capability gates remain unchanged. | **No change needed** |

### Priority B

| Collection | Audit | Decision |
|---|---|---|
| Assessment Records | URL-backed search, filters, ordering, and the selected-student constraint are preserved. Student identity and the assessment/date columns are concise; record and type-management actions are capability-gated. Loading, error, filtered-empty states, and canonical pagination exist. This is a confidential workflow with its own tested table and filter semantics. | **No change.** Keep the sensitive list and its specialized controls outside this focused PR. |
| Good Moral | Search/filter count, active sort, sticky applicant identity, row links, state labels, loading/error/empty states, and canonical pagination are already present. The operational action stays capability-gated. | **No change.** Its existing table hierarchy already meets the main scannability goals. |
| My Work | The API presents a ranked work queue, not an independently searchable or sortable directory. Rows carry the task, Student, detail, and source-workspace action; loading/error/empty copy and page controls are present. Access remains guidance-staff-only. | **No change.** No filters or sorting were invented for the queue. |

## Implementation details

- Added a named `role="region"` and `tabIndex={0}` to the desktop scrollers for Managed Appointments, Referrals, and operational Call Slips.
- Added a concise visible scroll hint, visible focus ring, and Left/Right keyboard scrolling when the region itself has focus.
- Applied the existing `dataTable.stickyHeaderCell` and `dataTable.stickyCell` styles to referral and Call Slip identities. Managed Appointments pins its checkbox column and the reference-code identity column together.
- Reused `FloatingListTools`, `ListSearchField`, `FilterField`, `SortField`, `SortableColumnHeader`, `CanonicalPagination`, and existing mobile summaries. No shared primitive was changed.
- No query names, search/filter semantics, sorting values, pagination state, authorization rules, API contracts, or data visibility changed.

## Changed files

- `fe/src/features/appointments/appointments-managed-page.tsx`
- `fe/src/features/referrals/referrals-page.tsx`
- `fe/src/features/call-slips/call-slips-page.tsx`
- `fe/tests/portal-collections.browser.mjs`
- `fe/docs/evidence/ux-p2b/` (synthetic before/after browser captures and run results)
- `COMPASS-UX-P2B-IMPLEMENTATION-REPORT.md`

## Visual evidence

The before captures use the unmodified base commit with the same synthetic records as the after captures. After captures are available from Chromium and WebKit; before captures are from Chromium. The before images are a visual comparison only: the baseline browser run could not verify the three table pages because the local server was unavailable. The after browser checks were rerun against the production build and passed in both engines.

| Collection | Desktop 1440px | Mobile 375px | Narrow desktop 1024px |
|---|---|---|---|
| Managed Appointments | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/appointments-desktop-1440.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/appointments-desktop-1440.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/appointments-mobile-375.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/appointments-mobile-375.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/appointments-narrow-desktop-1024.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/appointments-narrow-desktop-1024.png) |
| Referrals | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/referrals-desktop-1440.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/referrals-desktop-1440.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/referrals-mobile-375.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/referrals-mobile-375.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/referrals-narrow-desktop-1024.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/referrals-narrow-desktop-1024.png) |
| Call Slips | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/call-slips-desktop-1440.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/call-slips-desktop-1440.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/call-slips-mobile-375.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/call-slips-mobile-375.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/call-slips-narrow-desktop-1024.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/call-slips-narrow-desktop-1024.png) |
| Service Catalog | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/service-catalog-desktop-1440.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/service-catalog-desktop-1440.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/service-catalog-mobile-375.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/service-catalog-mobile-375.png) | [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/service-catalog-narrow-desktop-1024.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/service-catalog-narrow-desktop-1024.png) |

- Applied filter: [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/referrals-applied-filter-1440.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/referrals-applied-filter-1440.png)
- Applied filter panel: [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/referrals-applied-filter-panel-1440.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/referrals-applied-filter-panel-1440.png)
- No results and accessible Clear filters: [Before](fe/docs/evidence/ux-p2b/before/chromium/portal-collections/service-catalog-no-results-375.png) · [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/service-catalog-no-results-375.png)
- Student Call Slips self-service mobile list after the role-specific regression check: [After](fe/docs/evidence/ux-p2b/after/chromium/portal-collections/student-call-slips-mobile-375.png)

## Validation

- `pnpm lint` — passed with no warnings.
- `pnpm typecheck` — passed.
- `pnpm test` — **816 passed, 0 failed**.
- `pnpm build` — passed; all 92 static pages generated.
- `portal-collections.browser.mjs` — **7/7 checks passed in Chromium and 7/7 in WebKit**. Covers 320, 375, 768, 1024, and 1440px; keyboard focus/scrolling; pinned identity; active sorting; reminder selection; applied filters; no-results/Clear filters; and the Student Call Slips list.
- `frontend-consistency.browser.mjs` — **46/46 Chromium and 46/46 WebKit checks passed**. One earlier WebKit run had a navigation timeout on `referral-list-320`; the isolated rerun and subsequent full WebKit rerun both passed.
- Page-level horizontal overflow was checked at the five required widths. No horizontal page overflow was found.

## Accessibility, mobile, and limitations

- Desktop table regions have descriptive accessible names, keyboard focus, visible focus treatment, and Left/Right scrolling. The first column remains pinned while horizontally scrolling; Appointment selection stays available with it for authorized staff.
- Sortable headers retain their button names and `aria-sort`; sorting and pager behavior are covered by existing unit/browser checks.
- The existing mobile record summaries remain the single visible presentation below `md`; both viewport states were checked for page overflow. Student Call Slips were checked separately.
- The table remains horizontally scrollable at narrow workspace widths so useful comparison columns stay available. The visible hint explains how to reach the remaining columns. This PR does not convert the tables to card layouts.
- No UX-P2A detail-page files, `PageAction`, `PageHeader`, `Panel`, or disclosure primitives were touched. No integration conflict is known. The next integration check is to fetch `staging` before merge and rebase only this branch if staging advanced.

## Deferred candidates

Assessment Records, Good Moral, and My Work received audit-only review and are unchanged. Assessment Records and Good Moral may be considered for the same keyboard-scroll region treatment in a later scoped pass; My Work remains a ranked queue without invented search or sorting.

## Known limitations

- Browser evidence is synthetic and is not evidence of authenticated role sign-in against a deployed environment.
- The scroll hint is visible on desktop viewports below `2xl`, including some wider workspaces where the table may fit; it is intentionally concise and avoids a runtime measurement layer.
