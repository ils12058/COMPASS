# ADR-090: Collection ordering, queue prioritization, and sortable list contracts

## Status

Accepted. Refines the Overview attention and preview rules of
[ADR-058](ADR-058-portal-overview-summary-projection.md). Other ADRs keep their domain ordering
decisions; this ADR names the family each one belongs to.

## Context

COMPASS lists were deterministic but followed no shared rule:

- **Defaults:** some lists were newest-first, some alphabetical, some chronological.
- **Queues:** operational queues used `created_at DESC`, so new work buried older unfinished
  work.
- **Sorting:** only Appointments exposed a sort. Its API default (`START_DESC`) disagreed with the
  Portal default (`START_ASC`), and the Portal counted it as a filter.
- **Overview:** "Needs your attention" was ordered by the sequence in which frontend code assembled
  it. Its previews read the first three rows of newest-first endpoints, so they showed the newest
  pending work rather than the work that had waited longest.
- **Shared UI:** there was no common sortable header and no common Sort control.

A reader should be able to answer "why is this row first?" without knowing the implementation.

## Decision

### Semantic collection families

Every collection belongs to one family, and the family decides its default.

| Family | Meaning | Default |
| --- | --- | --- |
| SCHEDULE | Future or actionable time-bound events | soonest first |
| ACTION_QUEUE | Work awaiting someone's action | most urgent, then oldest waiting |
| HISTORY | Completed, submitted, or already-occurred records | newest occurrence first |
| DIRECTORY | People lookup | name A–Z |
| CATALOG | Configuration and reference entities | code or name A–Z |
| CURATED_FEED | Editorially ranked content | the editorial ranking |
| ATTENTION | Cross-domain items needing the reader | priority, deadline, waiting age |
| ANALYTICS | Report datasets | report-owned (out of scope) |

A list can contain several populations. Its default then follows the population that its filters
select: scheduled Appointments read as a schedule, while completed ones read as history.

### Contract

1. **Server-side, before paging.** User-selected ordering is applied in SQL before
   `OFFSET/LIMIT`. Nothing sorts a page that has already been paginated.
2. **Closed enums.** Each sortable endpoint takes `ordering: <Domain>Ordering | null`. Values are
   upper-case business meanings, such as `OLDEST_WAITING`, `NAME_ASC`, or `RECOMMENDED`.
   - There is no generic `sort`/`direction`/`order_by`, and field names are never exposed.
   - An invalid value is a typed 422.
   - `compass.common.ordering.parse_ordering` only parses against the closed enum. Each domain owns
     its ORDER BY.
3. **Population defaults resolved by the backend.** An omitted `ordering` resolves to the default
   for the filtered population. Every sortable page response carries the applied `ordering`, so the
   frontend never re-derives a default that could disagree with the server.
4. **Unique tie-breakers.** Every ordering ends in a unique key, usually `id`, in the same direction
   as the primary chronology where practical, so equal primary values never move rows between
   pages.
5. **Order of operations.** Authorization and scope come first, then filters and search, then
   ordering, then paging. Ordering never widens visibility. Search narrows the population and keeps
   the chosen ordering; there is no relevance ranking.
6. **Indexes.** No new indexes or migrations. Existing indexes already cover the new query shapes:
   - Appointments `(provider|student, status, starts_at)`;
   - Good Moral `(status, created_at)`;
   - Referrals `(referred_on, created_at)`;
   - Call Slips `(student|issuer, report_at)`;
   - Announcements `(is_pinned, -published_at)` and `(status, -published_at)`;
   - Resources `(status, display_order)`.

   Routine queues are per Counselor, and the account directory is one bounded user table, so neither
   needs an index for these orders.

### Frontend contract

- **URL state.** The URL holds `ordering=<value>` only when the reader chose one. Changing it keeps
  search and filters and returns to page 1. GET filter forms carry it as a hidden field, and Clear
  filters keeps it, because sorting is a view preference rather than a filter.
- **No filter count.** Ordering never counts toward the Filters badge.
- **`SortField`.** One labelled Sort select sits with the results it orders, in the results panel
  header or above a public list. It is available on every screen size, including where tables turn
  into cards on phones.
- **`SortableColumnHeader`.** It renders a real `<button>` in a `<th>` whose `aria-sort` reports the
  applied order. An arrow shows the direction, so meaning never depends on color, and the button
  names the current order and the order a press applies.
  - Only columns that are a real way to read the records are sortable.
  - Status, delivery mode, category, and other categorical columns stay filters.
- **One state.** Headers and the Sort field read and write the same URL value.
- **Labels.** Human labels live beside each feature's presentation helpers ("Oldest waiting first",
  "Last name A–Z"). Enum names are never shown.

### Collection matrix

**Changed defaults:**

| Surface | Family | Default | Alternatives | Tie-breaker |
| --- | --- | --- | --- | --- |
| Appointments: scheduled or upcoming | SCHEDULE | `EARLIEST_START` | `LATEST_START` | `reference_code`, `id` |
| Appointments: completed, cancelled, no-show, or all | HISTORY | `LATEST_START` | `EARLIEST_START` | `reference_code`, `id` |
| Routine Interviews: submitted intake, evaluation pending | ACTION_QUEUE | `OLDEST_WAITING` (intake submission) | `NEWEST_SUBMITTED`, `RECENTLY_FINALIZED`, `NEWEST_CREATED`, `STUDENT_ASC/DESC` | `created_at`, `id` |
| Routine Interviews: finalized | HISTORY | `RECENTLY_FINALIZED` | same | `id` |
| Routine Interviews: other filters | HISTORY | `NEWEST_CREATED` (unchanged) | same | `id` |
| Good Moral: requested or ready for issuance | ACTION_QUEUE | `OLDEST_FIRST` (time in current status) | `NEWEST_FIRST`, `APPLICANT_ASC/DESC` | `created_at`, `id` |
| Good Moral: issued, cancelled, or all | HISTORY | `NEWEST_FIRST` | same | `created_at`, `id` |
| Call Slips: active | SCHEDULE | `EARLIEST_REPORT` | `LATEST_REPORT`, `STUDENT_ASC/DESC` | `created_at`, `id` |
| Call Slips: completed, voided, or mixed | HISTORY | `LATEST_REPORT` (unchanged) | same | `created_at`, `id` |
| Referrals | HISTORY | `NEWEST_REFERRED` (`referred_on`) | `OLDEST_REFERRED`, `STUDENT_ASC/DESC` | `created_at`, `id` |
| Exit Interviews: submitted | HISTORY | `NEWEST_SUBMITTED` | `OLDEST_SUBMITTED`, `RECENTLY_UPDATED`, `STUDENT_ASC/DESC` | `updated_at`, `id` |
| Exit Interviews: draft or all | HISTORY | `RECENTLY_UPDATED` | same | `id` |
| Accounts | DIRECTORY | `NAME_ASC` (last, first, middle) | `NAME_DESC`, `NEWEST_CREATED`, `OLDEST_CREATED`, `RECENTLY_UPDATED` | `id` |
| Email deliveries: pending, processing, or failed | ACTION_QUEUE | `OLDEST` | `NEWEST` | `id` |
| Email deliveries: sent, cancelled, or all | HISTORY | `NEWEST` (unchanged) | `OLDEST` | `id` |

Notes on these choices:

- **Good Moral.** The time in current status is `created_at` for requested, `prepared_at` for ready,
  `issued_at` for issued, and `cancelled_at` for cancelled.
- **Call Slips.** `report_at` is when the Student is expected to report. A Student's own Call Slips
  use the same population default and offer no other order.
- **Referrals.** `referred_on` is the canonical chronology: the date on the form, which the date
  filters already use. Back-entered Referrals therefore sit at their real date, and entry time
  breaks ties. `received_at` is a separate workflow fact, not a sort.

**Unchanged defaults, with useful alternatives added:**

| Surface | Family | Default | Alternatives |
| --- | --- | --- | --- |
| Counseling Encounters | HISTORY | `LATEST_ENCOUNTER` | `OLDEST_ENCOUNTER`, `STUDENT_ASC/DESC` |
| Graduate Tracer responses | HISTORY | `NEWEST_SUBMITTED` | `OLDEST_SUBMITTED`, `GRADUATE_ASC/DESC` |
| Customer Feedback and CSM responses | HISTORY | `NEWEST_SUBMITTED` | `OLDEST_SUBMITTED` |
| Inventory roster | DIRECTORY | `STUDENT_ASC` | `STUDENT_DESC`, `RECENTLY_SUBMITTED` |
| Services | CATALOG | `CODE_ASC` | `CODE_DESC`, `NAME_ASC/DESC` |
| Announcements: public and signed-in readers | CURATED_FEED | `RECOMMENDED` (pinned, newest published) | `NEWEST`, `OLDEST`, `TITLE_ASC/DESC` |
| Announcements: management | HISTORY | `RECENTLY_UPDATED` | `OLDEST_UPDATED`, `NEWEST/OLDEST_PUBLISHED`, `TITLE_ASC/DESC` |
| Resources: public and signed-in readers | CURATED_FEED | `RECOMMENDED` (`display_order`, newest published) | `NEWEST`, `OLDEST`, `TITLE_ASC/DESC` |
| Resources: management | HISTORY | `RECENTLY_UPDATED` | `DISPLAY_ORDER`, `OLDEST_UPDATED`, `NEWEST/OLDEST_PUBLISHED`, `TITLE_ASC/DESC` |

- **Announcements.** Pinning is an editorial state shown on each record and is not a sort.
- **Previews.** The Overview and landing previews always use `RECOMMENDED` and have no Sort control.
- **Resource management.** `DISPLAY_ORDER` is the sortable Order column. While it is applied, the
  list says that readers see Resources in that order.

**Preserved as they are, with no user sort:**

| Surface | Family | Ordering |
| --- | --- | --- |
| Activity, platform, privacy, and supervised activity | HISTORY | `occurred_at DESC, id DESC` |
| Notifications | HISTORY | newest first |
| Privacy retention rules and notices | CATALOG | `code` |
| Privacy disposition cases | ACTION_QUEUE | `eligible_at ASC` (the reference queue) |
| Organization structure | CATALOG | campus code, then college code, then program code |
| Organization people, candidates, and affiliations | DIRECTORY | last name, then first name |
| Service provider candidates and eligible-Student pickers | DIRECTORY | last name, then first name |
| Availability | SCHEDULE | providers by name; windows by weekday and time; exceptions by time |
| Academic Years | CATALOG | `label DESC` (see below) |
| Institutional Forms | CATALOG | family key, then current revision, then revision chronology |
| Sessions and trusted browsers | HISTORY | `last_used_at DESC`; the current one is labelled |
| A Student's own Routine Interviews, Good Moral requests, and Inventory history | HISTORY | newest first |
| Reports | ANALYTICS | report-owned |

**Academic Years:** labels are validated only for length, not format, so `label DESC` relies on
the institution's chronological labels (`2026-2027`). There is no date field to order by, and none
is added solely for sorting. The current Academic Year is marked explicitly wherever it appears,
whatever its position.

### Overview "Needs your attention"

Attention items are ranked, not assembled in order. Each item carries internal ranking facts that
the reader never sees:

```
priority      CRITICAL | TIME_SENSITIVE | ACTION_REQUIRED | INCOMPLETE_SELF_SERVICE
due_at        a real business deadline, when one exists
waiting_since the owning domain's queue anchor
stable_key    deterministic fallback, which also keeps a domain's own preview order
```

Items rank by priority class, then the earliest `due_at`, then the oldest `waiting_since`, then
`stable_key`. A missing time sorts after a present one.

**Classes:**

- **CRITICAL:** failed email deliveries. Only a real failed operation qualifies.
- **TIME_SENSITIVE:** reserved. No current item has a business deadline.
- **ACTION_REQUIRED:**
  - pending Routine evaluations (waiting since intake submission);
  - requested Good Moral certificates (waiting since the request);
  - email deliveries that are due but not failed.
- **INCOMPLETE_SELF_SERVICE:** the reader's own Inventory, Routine intake, Exit Interview, and
  Graduate Tracer drafts.

**Previews and failures:**

- Previews request each queue's own order (`OLDEST_WAITING`, `OLDEST_FIRST`). The Overview
  therefore shows the work that has waited longest, without rebuilding domain rules.
- A source that cannot be read keeps an error row within its own class.
- Stale-data notices stay apart from the ranked items.
- Ranking only reorders items the domain APIs already authorized. It cannot add an item or widen
  visibility.
- The metric tiles and the order of Overview sections remain designed information architecture,
  not a sortable collection.

### Exclusions

The following are out of scope:

- relevance search, saved views, and persisted cross-device preferences;
- drag-and-drop ordering and column customization;
- report or analytics ranking;
- a priority or SLA engine;
- changes to pagination architecture.

## Consequences

- Queues no longer starve old work, history reads newest first, directories read A–Z, and curated
  feeds keep their editorial order.
- The backend and frontend cannot disagree about a default, because the backend reports what it
  applied.
- Renaming `START_ASC`/`START_DESC` to `EARLIEST_START`/`LATEST_START`, and adding a required
  `ordering` field to sortable page responses, are contract changes. The generated client follows
  them.
- Adding a sortable collection means:
  - a closed enum and a population default in the owning domain;
  - a unique tie-breaker;
  - the applied ordering in the response;
  - a `SortField`, plus headers only where a column is a real reading order;
  - pagination-stability tests.
