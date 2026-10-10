# Frontend consistency — Slice 1 audit

## Authority and scope

Initial audit completed before production edits on 2026-10-10, against `origin/staging` at
`4afcc296492d55c6d00c0bae65300d4610c8957f`, in isolated branch
`codex/frontend-consistency-slice1`. This supersedes earlier snapshots. Source inventory covers every
handwritten TSX file, every portal route, direct PageHeader composition, forwarding feature heading,
shared state/list/layout primitive, and the existing structural and browser suites. Role gates were
read at usage sites; no new authority is inferred. Browser evidence and final validation are recorded
below after implementation. This is frontend presentation work; APIs, workflows and institutional
wording remain authoritative.

## Verified findings and decisions

| ID / priority | Affected area and evidence at baseline | Existing comparison / root cause | Canonical correction | Risk and regression |
| --- | --- | --- | --- | --- |
| H1 / P1 | Call Slip detail uses internal IconAction; Referral detail and Exit response PDF use Button | Report downloads and Assessment editing already use PageAction; adoption drift in download helpers | Migrate header commands, preserve URL, filename, pending/error, and self/staff API selection | Low; download/pending/failure browser checks and AST transitive guard |
| H2 / P1 | Service detail, Routine detail, Appointment workspace links, Messages trigger, template Create, Announcement/Resource Edit and lifecycle controls, Privacy Rename/Edit/Publish/Retire/CSV use ordinary commands in headers | Same commands on lists use PageAction; shared wrappers accept arbitrary nodes | Use existing page actions, retain refs, confirmation and disabled/visibility logic; danger surface uses existing danger tokens | Medium for dialog focus/refs; existing workflow suites plus browser action/confirmation checks |
| H3 / P1 | Graduate Tracer submitted date/student status and Exit response status occupy action props | Assessment/E-Counseling already distinguish meta from actions | Forward metadata separately and put it beside/under title; actions hold commands only | Low; AST metadata negatives and real-page browser checks |
| H4 / P2 | Accounts, Availability, Content, Services and Privacy wrappers draw literal arrows and inconsistent destination-only labels; some caller labels already say Back to | Call Slip/Referral shared back text is canonical | Shared text-link styling and Back to destination; preserve guarded links and destinations, remove textual arrows; conversation Back retains its decorative ArrowLeft | Low; back/slot structural and navigation checks |
| H5 / P2 | E-Counseling Help is nested in back region; layout presets share command region | PageHeader already has help; live call workspace legitimately has layout preferences | Help in help slot; keep labeled live layout preference beside commands as a documented exception | Medium; call/contextual Messages suites, no runtime/state changes |
| S1 / P2 | RoutineQueryError duplicates a framed alert with bespoke padding/header/retry | Other query errors delegate Notice | Retain domain error mapping, heading, children and Retry; compose Notice | Low; render test preserves one alert and Retry |
| S3 / P2 | Follow-up raw-heading scan: Student/Counselor Good Moral not-found states duplicate a framed alert | Other unavailable states already use Notice with an H1 | Delegate the unchanged title/role to Notice | Low; existing Good Moral retrieval/preparation tests |
| S2 / P2 | Graduate Tracer detail initial skeleton has bespoke busy wrapper and non-live hidden text | LoadingRegion owns busy/status contract across other records | Adopt LoadingRegion without changing query/error decisions | Low; loading accessibility test and browser pending fixture |
| P1 / P2 | Call Slip, Referral, Assessment Records/Types and Exit access immediately repeat H1 as PanelHeader | Services Results and other meaningful region headings distinguish page from result sheet | Name these result panels Results, retaining IDs and H2 landmarks | Low; AST duplicate-heading guard and list browser checks |
| B1 / P3 | Services and Organization duplicate exactly the same generic Active/Inactive badge; Availability does too except Legacy | Identical text and token grammar | One small shared ActiveStatusBadge; retain domain wrappers and Legacy/Retired distinctions | Low; render equality and domain-label tests |

Confirmed already corrected on this staging baseline: sortable labels are positioned; long-text
containment and collection URL/search ownership have UX-hardening coverage; Exit sibling links
already use WorkspaceTabs. Do not reimplement earlier audit findings that staging has resolved.

## Canonical conventions

Maintainable rules live in [ui-guidelines.md](ui-guidelines.md) and fe/AGENTS.md, using the existing
primitives. Headers separate back, identity, context, metadata, help and genuine commands. A header
command has a square icon surface, a visible label on every pointer/viewport, a complete accessible
name, native button/link semantics and visible focus. Actions wrap; no icon-only fallback.
Forms/rows/region commands and confirmation actions remain Buttons. Consequential header triggers
keep explicit action labels and existing review dialogs; danger remains visually distinct.

Back is a text link reading Back to destination. Preserve actual destination/query and unsaved-change
guards. Cancel/Close/Return to review retain their workflow meaning. A page owns H1; a distinct
results/form/record region owns H2; named subsections keep their existing heading levels/landmarks.
No nested panels or duplicate H1/H2 for the same results region. Noncollections keep pageSheetWidth;
collections use workspace width, with bounded local table scrolling and wrapping text.

Collection search/filters use FloatingListTools; sorting and result context stay in PanelHeader or
sortable table heads. Public/report/workflow parameters remain in flow. Preserve explicit versus
immediate submission, defaults, query keys, pagination, server filtering and ordering. LoadingRegion
and RowsSkeleton name initial loading; existing content stays during refresh according to existing
freshness decisions. PanelMessage belongs inside results; Notice describes a standalone contextual
error/warning; WorkspaceUnavailable describes the whole inaccessible workspace. Empty and filtered
empty differ. Generic Active/Inactive reuses shared presentation; workflow badges retain domain
semantics and non-color labels. Phones stack/wrap without dropping information or table columns.

## Intentional exceptions and deferred findings

* E-Counseling layout presets are labeled view preferences for a live workspace, not record commands;
  preserve their specialized preset controls and existing wide-workspace visibility. Call/media controls remain
  CallControl and contextual Messages retains its backend-offered availability and unread fact.
* Feature headings stay where they provide domain back navigation, metadata, help or local naming.
  Thin forwarding wrappers alone are not a defect; no mass deletion or universal conditional header.
* Privacy Active/Retired, Availability Legacy, publication/routine/appointment/consent statuses are
  meaningful domain distinctions, not generic Inactive. Do not erase them.
* Inventory PDFs belong to their submitted-record region; retention approval/holds, Call Slip void/end,
  Good Moral issuance, form Save/Cancel, conversation controls and report filter Apply stay in context.
* Reports use in-flow criteria; Messages uses a directory/conversation, Availability uses schedule
  editors and embedded pickers. They are not ordinary record tables. No forced floating filters.
* Raw H1s in auth, public/editorial headers, maintenance, whole-page failures and terminal form outcomes
  retain their distinct anatomy. Conversation headers are section controls, not normal PageHeaders.
* Copy density, capitalization, safe error vocabulary and explanatory prose belong to Slice 2.
  Controlled questions/official form labels, confidentiality and consequences remain unchanged.
* Server-only visibility, authority, freshness and state-transition concerns require a separate domain
  investigation; this PR changes no query policy or lifecycle. Live provider/backend and real-device
  testing are outside synthetic browser evidence.

## Inventory

109 portal page routes; 41 feature areas; 482 handwritten TSX files (generated excluded); 190 header compositions. The static inventory is exhaustive; browser sampling is representative.

| Feature area | TSX files | Headers and collection/state/layout review |
| --- | ---: | --- |
| `accessibility` | 1 | Shared/embedded composition |
| `account` | 15 | PageHeader × 9 |
| `accounts` | 9 | PageHeader × 5 |
| `activity` | 1 | Shared/embedded composition |
| `announcements` | 8 | ContentPageHeading × 5 |
| `appointments` | 6 | AppointmentsPageHeading × 4, PageHeader × 2 |
| `assessment-records` | 5 | PageHeader × 4 |
| `auth` | 10 | Shared/embedded composition |
| `availability` | 5 | AvailabilityPageHeading × 4, PageHeader × 2 |
| `call-slips` | 7 | CallSlipHeading × 9, PageHeader × 1 |
| `content` | 5 | PageHeader × 1 |
| `counseling` | 11 | PageHeader × 1, CounselingPageHeading × 7 |
| `ecounseling` | 15 | PageHeader × 2 |
| `exit-interviews` | 14 | ExitInterviewHeading × 5, PageHeader × 1 |
| `feedback` | 6 | FeedbackPageHeading × 9, PageHeader × 1 |
| `form-safety` | 2 | Shared/embedded composition |
| `freshness` | 1 | Shared/embedded composition |
| `good-moral` | 14 | GoodMoralHeading × 6, PageHeader × 1 |
| `graduate-tracer` | 10 | GraduateTracerHeading × 12, PageHeader × 1 |
| `guidance-messages` | 15 | Heading × 1, PageHeader × 1 |
| `guidance-operations` | 1 | PageHeader × 1 |
| `institution-configuration` | 6 | PageHeader × 2 |
| `institutional-forms` | 1 | Shared/embedded composition |
| `inventory` | 20 | InventoryHeading × 17, PageHeader × 1 |
| `notifications` | 5 | PageHeader × 1 |
| `organization` | 9 | PageHeader × 1, PageHeading × 5 |
| `platform` | 12 | PlatformPageHeader × 5, PageHeader × 1 |
| `portal` | 14 | PageHeader × 1 |
| `privacy-governance` | 17 | PrivacyPageHeader × 10, PageHeader × 2 |
| `public` | 21 | Shared/embedded composition |
| `pwa` | 1 | Shared/embedded composition |
| `realtime` | 1 | Shared/embedded composition |
| `referrals` | 7 | ReferralHeading × 4, PageHeader × 1 |
| `reports` | 15 | ReportsPageHeading × 17, PageHeader × 1 |
| `resources` | 8 | ContentPageHeading × 5 |
| `routine-interviews` | 8 | RoutinePageHeading × 6, PageHeader × 1 |
| `security` | 1 | Shared/embedded composition |
| `services` | 7 | ServicesPageHeading × 5, PageHeader × 1 |
| `student-actions` | 1 | PageHeader × 1 |
| `student-support` | 1 | Shared/embedded composition |
| `work-queue` | 1 | PageHeader × 1 |

Shared usage counts: `PageHeader` 48, `PageAction` 14, `PageActionLink` 15, `PageActionGroup` 3, `IconAction` 3, `Panel` 197, `PanelHeader` 134, `PanelSection` 61, `PanelFooter` 31, `PanelMessage` 139, `Notice` 125, `WorkspaceUnavailable` 39, `LoadingRegion` 42, `RowsSkeleton` 41, `FloatingListTools` 24, `FilterToolbar` 4, `WorkspaceTabs` 9.


Inspection included account/security/access/import, institution configuration, organization structure/
responsibilities/affiliations, office/self/provider Availability, content lists/details/editors,
appointments/self/managed/booking/rescheduling, Counselor/GSS operational records, Student histories/
forms/actions, work queue/Guidance Operations, reports and privacy/platform administration. Read each
header action producer and forwarding wrapper in context. The result-region scan checked duplicate
literal titles, loading framing, list tool/sort position, pagination and one-off state/badge code.

## Implementation and validation

The fixes in H1–H5, S1–S3, P1 and B1 are implemented. PageHeader separates its wrapping command
region from Help; PageAction keeps a visible wrapping label and supports existing danger tokens.
PageActionLink can use the existing GuardedPortalLink renderer, preserving draft navigation guards.
Feature command producers, metadata/back forwarding, result titles and duplicate generic badges
are corrected at their source. API calls, role predicates, destinations, stale-data decisions,
confirmation content, form questions and mutation handlers are unchanged. All tracked changes
are under `fe/`; generated clients, contracts and Next-generated declarations are excluded.

Regression protection now uses TypeScript symbols to discover headers and forwarding wrappers,
following action imports, aliases, re-exports, conditional returns and local values. It checks all
header usage sites, including files that never import PageAction. The 21 guard tests include
negative raw button/link/IconAction, missing/empty/hidden label, metadata, disguised dialog,
arbitrary forwarding wrapper, imported alias, renderer override, misplaced back/help, and repeated
heading cases. Dialog contents and the named live-layout exception remain separate contexts.
Render tests check shared badges/Legacy, one Routine alert with heading/content/Retry, metadata
placement, guarded link rendering and danger presentation. Existing download, confirmation,
disabled-export and navigation tests retain their behavior assertions; selectors now recognize
the canonical label span and Service's complete accessible name.

Executed in this isolated checkout with Node 26.7 and pnpm 11.19.0:

| Command / check | Result |
| --- | --- |
| `pnpm install --frozen-lockfile` | Passed; lockfile unchanged |
| `pnpm api:generate` | Passed; no generated/contract changes included |
| `pnpm lint` | Passed; zero errors or warnings |
| `pnpm typecheck` | Passed |
| `pnpm test` | 476/476 passed |
| `node --import ./tests/support/register-tsx.mjs --test tests/page-header-contract.test.mjs` | 21/21 passed after final symbol-resolution refinement |
| Focused Good Moral, record-retrieval and header regression run | 34/34 passed after the final state/back adoption changes |
| `pnpm build` | Passed |
| `pnpm test:ui:consistency` | Chromium 46/46; WebKit 46/46 |
| Existing `pnpm test:ui` chain, resumed and affected suites rerun | 584/584 checks across its constituent suites; per-engine counts below |
| `git diff --check` | Passed |

| Browser suite | Chromium | WebKit |
| --- | ---: | ---: |
| Assessment Records | 32/32 | 32/32 |
| Student Actions | 22/22 | 22/22 |
| Guidance Operations | 20/20 | 20/20 |
| Work Queue | 19/19 | 19/19 |
| Draft/session safety | 20/20 | Not in existing script |
| Realtime runtime | 11/11 | 11/11 |
| Guidance Messages | 41/41 | 41/41 |
| Contextual Messages | 24/24 | 24/24 |
| Staff Messages operations | 26/26 | 26/26 |
| Information hierarchy | 14/14 | Not in existing script |
| E-Counseling call | 31/31 | Not in existing script |
| E-Counseling runtime | 17/17 | Not in existing script |
| UX hardening | 56/56 | 56/56 |
| New consistency suite | 46/46 | 46/46 |

Total unique suite/engine checks: 676/676, excluding extra focused reruns. This is a passed
constituent-suite matrix, not a claim that the first uninterrupted `pnpm test:ui` invocation passed.

Browser checks use the actual Next application at `http://localhost:3127` with existing synthetic
API fixtures, headless Chromium/WebKit, and viewport emulation. The new suite checks 320, 393 and
1440px Call Slip/Referral/Service lists and details, Assessment list/detail, Routine workspace,
Graduate Tracer detail, long-title Announcement actions, and Counselor/GSS Guidance Operations.
It also checks Student Tracer metadata, Student/Counselor download pending/disabled/filename and
self/staff API selection, persistent failure/retry, shared Routine error/Retry, shared Tracer busy/live
loading, and Privacy danger/confirmation/keyboard activation/focus return. It asserts visible labels
below icons, focus rings, canonical command anatomy and no page overflow.

Artifacts: `/tmp/compass-slice1-browser/frontend-consistency-{chromium,webkit}/results.json`
and screenshots; existing suites use `/tmp/compass-slice1-browser/`. Logs are
`/tmp/compass-slice1-final-consistency.log`, `/tmp/compass-slice1-existing-browser.log` and
`/tmp/compass-slice1-existing-browser-resumed.log`, `/tmp/compass-slice1-existing-browser-final.log`
and `/tmp/compass-slice1-header-layout-regressions.log`.
These are local verification artifacts, not
repository assets. Mobile Call Slip, Announcement and Tracer detail screenshots and the desktop
Assessment Types results screenshot were visually inspected, as was the corrected 320px live-call
workspace. Browser sampling is representative;
the source inventory covers the whole frontend. No physical devices, live backend/provider,
production deployment or actual confidential records were used.

The first existing browser chain stopped on its obsolete exact `Edit` selector; the Service link is
now named `Edit Service`. The corrected draft suite passed its full Back/unload/confirmation checks
and the remaining chain resumed from there. New-fixture development failures were corrected before
the final 92/92 run. Privacy focus-return coverage activates via keyboard, so its assertion tests
keyboard focus restoration consistently in both engines. No workflow assertion was removed to
accommodate a production failure.

The existing E-Counseling suite caught a 320px regression during validation: putting Help on a
separate mobile row pushed the stage to 274px, beyond the unchanged `<260px` assertion. PageHeader
now places its separate Help slot beside Back when Back is present, preserving a compact navigation
row. The original call suite passed 31/31 afterward; a render regression also protects single Help
rendering and its separation from the Back link. The affected browser suites and checks were rerun.

## Portal route inventory

* `/portal/academic-years` — `@/features/institution-configuration/academic-years-page`.
* `/portal/account/activity` — `@/features/account/activity/activity-page`.
* `/portal/account/preferences` — `@/features/account/preferences/preferences-page`.
* `/portal/account/privacy` — `@/features/account/privacy/account-privacy-page`.
* `/portal/account/profile` — `@/features/account/profile/profile-page`.
* `/portal/account/security/authenticator` — `@/features/account/security/authenticator/authenticator-page`.
* `/portal/account/security/email` — `@/features/account/security/email/email-change-page`.
* `/portal/account/security` — `@/features/account/security/security-overview`.
* `/portal/account/security/password` — `@/features/account/security/password/password-change-page`.
* `/portal/account/security/sessions` — `@/features/account/security/sessions/sessions-page`.
* `/portal/accounts/[userId]/access` — `@/features/accounts/detail/access/account-access`.
* `/portal/accounts/[userId]` — `@/features/accounts/detail/overview/account-overview`.
* `/portal/accounts/[userId]/security` — `@/features/accounts/detail/security/account-security`.
* `/portal/accounts/import` — `@/features/accounts/import/import-accounts`.
* `/portal/accounts/new` — `@/features/accounts/create/create-account`.
* `/portal/accounts` — `@/features/accounts/list/accounts-list`.
* `/portal/actions` — `@/features/student-actions/student-actions-page`.
* `/portal/announcements/[announcementId]/edit` — `@/features/announcements/announcement-edit-page`.
* `/portal/announcements/[announcementId]` — `@/features/content/content-shared`, `@/features/announcements/announcement-detail-page`.
* `/portal/announcements/new` — `@/features/announcements/announcement-create-page`.
* `/portal/announcements` — `@/features/content/content-shared`, `@/features/announcements/announcements-list-page`.
* `/portal/appointments/[appointmentId]` — `@/features/appointments/appointments-shared`, `@/features/appointments/appointment-detail-page`.
* `/portal/appointments/book` — `@/features/appointments/appointment-booking-page`.
* `/portal/appointments/manage` — `@/features/appointments/appointments-shared`, `@/features/appointments/appointments-managed-page`.
* `/portal/appointments/my` — `@/features/appointments/appointments-shared`, `@/features/appointments/appointments-my-page`.
* `/portal/appointments` — `@/features/appointments/appointments-entry-page`.
* `/portal/assessment-records/[recordId]/edit` — `@/features/assessment-records/assessment-record-editor`.
* `/portal/assessment-records/[recordId]` — `@/features/assessment-records/assessment-record-detail`.
* `/portal/assessment-records/new` — `@/features/assessment-records/assessment-record-editor`.
* `/portal/assessment-records` — `@/features/assessment-records/assessment-records-list`, `@/features/assessment-records/assessment-records-shared`.
* `/portal/assessment-records/types` — `@/features/assessment-records/assessment-types-page`.
* `/portal/availability/me` — `@/features/availability/availability-pages`.
* `/portal/availability/office` — `@/features/availability/availability-pages`.
* `/portal/availability` — `@/features/availability/availability-shared`.
* `/portal/availability/providers/[providerId]` — `@/features/availability/availability-shared`, `@/features/availability/availability-pages`.
* `/portal/availability/providers` — `@/features/availability/availability-shared`, `@/features/availability/availability-pages`.
* `/portal/call-slips/[callSlipId]` — `@/features/call-slips/call-slips-shared`, `@/features/call-slips/call-slip-detail-page`.
* `/portal/call-slips/new` — `@/features/call-slips/call-slips-shared`, `@/features/call-slips/call-slip-create-page`.
* `/portal/call-slips` — `@/features/call-slips/call-slips-shared`, `@/features/call-slips/call-slips-page`, `@/features/portal/components/list-ordering-params`.
* `/portal/counseling/encounters/[encounterId]` — `@/features/counseling/counseling-shared`, `@/features/counseling/encounter-detail-page`.
* `/portal/counseling` — `@/features/counseling/counseling-shared`, `@/features/counseling/counseling-entry-page`.
* `/portal/counseling/summaries/[summaryId]` — `@/features/counseling/counseling-shared`, `@/features/counseling/student-shared-summaries`.
* `/portal/counseling/workspace/appointment/[appointmentId]` — `@/features/counseling/counseling-shared`, `@/features/counseling/counseling-workspace`.
* `/portal/counseling/workspace/routine-interview/[routineInterviewId]` — `@/features/counseling/counseling-shared`, `@/features/counseling/counseling-workspace`.
* `/portal/e-counseling/[appointmentId]` — `@/features/ecounseling/ecounseling-workspace`.
* `/portal/exit-interviews/[exitInterviewId]` — `@/features/exit-interviews/exit-interview-shared`, `@/features/exit-interviews/exit-interview-detail-page`.
* `/portal/exit-interviews` — `@/features/exit-interviews/exit-interview-shared`, `@/features/exit-interviews/exit-interview-workspace-page`, `@/features/exit-interviews/exit-interview-operational-list`, `@/features/portal/components/list-ordering-params`.
* `/portal/feedback/csm` — `@/features/feedback/feedback-shared`, `@/features/feedback/csm-form`.
* `/portal/feedback/csm/responses/[responseId]` — `@/features/feedback/feedback-response-details`.
* `/portal/feedback/csm/responses` — `@/features/feedback/feedback-shared`, `@/features/feedback/feedback-response-lists`.
* `/portal/feedback/customer-feedback` — `@/features/feedback/feedback-shared`, `@/features/feedback/customer-feedback-form`.
* `/portal/feedback/customer-feedback/responses/[responseId]` — `@/features/feedback/feedback-response-details`.
* `/portal/feedback/customer-feedback/responses` — `@/features/feedback/feedback-shared`, `@/features/feedback/feedback-response-lists`.
* `/portal/feedback` — `@/features/feedback/feedback-shared`, `@/features/feedback/feedback-entry-page`.
* `/portal/good-moral/[requestId]` — `@/features/good-moral/good-moral-shared`, `@/features/good-moral/good-moral-detail-page`.
* `/portal/good-moral` — `@/features/good-moral/good-moral-shared`, `@/features/good-moral/good-moral-page`, `@/features/good-moral/good-moral-operational-list`, `@/features/portal/components/list-ordering-params`.
* `/portal/good-moral/request` — `@/features/good-moral/good-moral-request-page`.
* `/portal/graduate-tracer` — `@/features/graduate-tracer/graduate-tracer-student-workspace`, `@/features/graduate-tracer/graduate-tracer-workspace-page`, `@/features/graduate-tracer/graduate-tracer-operational-list`, `@/features/portal/components/list-ordering-params`.
* `/portal/graduate-tracer/responses/[responseId]` — `@/features/graduate-tracer/graduate-tracer-detail-page`.
* `/portal/institutional-forms` — `@/features/institution-configuration/institutional-forms-page`.
* `/portal/inventory/current` — `@/features/inventory/student/current-inventory-page`.
* `/portal/inventory/history/[inventoryId]` — `@/features/inventory/student/inventory-history-detail`.
* `/portal/inventory` — `@/features/inventory/inventory-home`.
* `/portal/inventory/records/[inventoryId]` — `@/features/inventory/counselor/inventory-record-detail`.
* `/portal/messages/[threadId]` — `@/features/guidance-messages/guidance-conversation`.
* `/portal/messages/new` — `@/features/guidance-messages/guidance-new-message`.
* `/portal/messages` — `@/features/guidance-messages/guidance-conversation-placeholder`.
* `/portal/messages/templates` — `@/features/guidance-messages/guidance-message-templates-page`.
* `/portal/notifications` — `@/features/notifications/notification-center/notification-center`.
* `/portal/operations` — `@/features/guidance-operations/guidance-operations-page`.
* `/portal/organization` — `@/features/organization/components/organization-gate`, `@/features/organization/structure/organization-structure-page`.
* `/portal/organization/responsibilities` — `@/features/organization/responsibilities/responsibilities-page`.
* `/portal/organization/student-affiliations` — `@/features/organization/components/organization-shared`, `@/features/organization/student-affiliations/student-affiliations-page`.
* `/portal` — `@/features/portal/home/portal-home`.
* `/portal/platform/activity` — `@/features/platform/activity/platform-activity-page`.
* `/portal/platform/email-delivery` — `@/features/platform/email-delivery/platform-email-delivery-page`.
* `/portal/platform/environment` — `@/features/platform/environment/platform-environment-page`.
* `/portal/platform/health` — `@/features/platform/health/platform-health-page`.
* `/portal/platform/maintenance` — `@/features/platform/maintenance/platform-maintenance-page`.
* `/portal/platform` — redirect to `/portal/platform/health`.
* `/portal/privacy/activity` — `@/features/privacy-governance/privacy-governance-shared`, `@/features/privacy-governance/activity/privacy-activity-page`.
* `/portal/privacy/notice-revisions/[revisionId]` — `@/features/privacy-governance/privacy-governance-shared`, `@/features/privacy-governance/notices/notice-revision-page`.
* `/portal/privacy/notices/[noticeId]` — `@/features/privacy-governance/privacy-governance-shared`, `@/features/privacy-governance/notices/notice-detail-page`.
* `/portal/privacy/notices/new` — `@/features/privacy-governance/notices/notice-create-page`.
* `/portal/privacy/notices` — `@/features/privacy-governance/privacy-governance-shared`, `@/features/privacy-governance/notices/notices-page`.
* `/portal/privacy` — `@/features/privacy-governance/privacy-landing`.
* `/portal/privacy/retention/cases/[caseId]` — `@/features/privacy-governance/retention/disposition-case-page`.
* `/portal/privacy/retention` — `@/features/privacy-governance/retention/retention-page`.
* `/portal/privacy/retention/rules/[ruleId]` — `@/features/privacy-governance/retention/retention-rule-editor`.
* `/portal/privacy/retention/rules/new` — `@/features/privacy-governance/retention/retention-rule-editor`.
* `/portal/privacy/retention/rules` — `@/features/privacy-governance/retention/retention-rules-page`.
* `/portal/referrals/[referralId]/issue-call-slip` — `@/features/call-slips/call-slips-shared`, `@/features/call-slips/call-slip-from-referral-page`.
* `/portal/referrals/[referralId]` — `@/features/referrals/referrals-shared`, `@/features/referrals/referral-detail-page`.
* `/portal/referrals/new` — `@/features/referrals/referral-create-page`.
* `/portal/referrals` — `@/features/portal/components/list-ordering-params`, `@/features/referrals/referrals-shared`, `@/features/referrals/referrals-page`.
* `/portal/reports/graduate-tracer` — `@/features/reports/reports-shared`, `@/features/reports/graduate-tracer-report-page`.
* `/portal/reports` — `@/features/reports/reports-index`.
* `/portal/reports/student-profile` — `@/features/reports/reports-shared`, `@/features/reports/student-profile-report-page`.
* `/portal/resources/[resourceId]/edit` — `@/features/resources/resource-edit-page`.
* `/portal/resources/[resourceId]` — `@/features/content/content-shared`, `@/features/resources/resource-detail-page`.
* `/portal/resources/new` — `@/features/resources/resource-create-page`.
* `/portal/resources` — `@/features/content/content-shared`, `@/features/resources/resources-list-page`.
* `/portal/routine-interviews/[routineInterviewId]` — `@/features/routine-interviews/routine-interviews-shared`, `@/features/routine-interviews/routine-interview-detail-page`.
* `/portal/routine-interviews` — `@/features/routine-interviews/routine-interviews-shared`, `@/features/routine-interviews/routine-interviews-entry-page`.
* `/portal/services/[serviceId]/edit` — `@/features/services/service-editor-page`.
* `/portal/services/[serviceId]` — `@/features/services/services-shared`, `@/features/services/service-detail-page`.
* `/portal/services/new` — `@/features/services/service-editor-page`.
* `/portal/services` — `@/features/services/services-shared`, `@/features/services/services-list-page`.
* `/portal/work` — `@/features/work-queue/work-queue-page`.
