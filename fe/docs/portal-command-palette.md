# Portal command palette: implementation and validation

The portal top bar now provides **Go to…**, a local index of authorized, stable COMPASS
destinations. It opens through the visible Search button or Cmd/Ctrl+K. This is feature
navigation; existing collection filters and record search remain separate.

Branch: `feature/portal-command-palette`.
Final fetched staging base: `aebde9cc740f964702653efdbf2322b82c9d3fd8`.
Staging did not move during reconciliation. The changes preserve #165's shell/design primitives
and #166's existing console warning/provider composition. No merge or deployment was performed.

## Files and architecture

- `src/features/portal/components/portal-command-destinations.ts`: static destination construction,
  aliases, normalization, deterministic matching.
- `src/features/portal/components/portal-command-keyboard.ts`: shortcut registration/cleanup,
  foreign-modal detection, active-result movement.
- `src/features/portal/components/portal-command-palette.tsx`: current Dialog/Input primitives,
  accessible search/results, focus handling, actual guarded navigation.
- `src/features/portal/components/portal-shell.tsx`: mounts one palette in the authenticated
  portal header, between navigation controls and accessibility/notification/account controls.
- `tests/portal-command-palette.test.mjs`: 29 focused tests using existing Node/TypeScript/React
  test infrastructure, including the real GuardedPortalLink and UnsavedChangesProvider.
- `AGENTS.md`: concise reusable portal feature-navigation rule.
- `docs/portal-command-palette.md`: this inventory and validation report.

`portalCommandDestinations(user)` reads `portalWorkspaceGroups(user)` directly. Every dock
workspace retains its canonical label, href, icon, group and existing visibility gate. It adds
Overview, Notifications and the five universal Account destinations. The returned authorized
array is memoized for the current session in the palette; query/result state stays local.

Every deep entry requires its visible parent workspace. Where a page has a narrower rule,
the registry uses that feature's existing access helper. Where the workspace layout already
governs the whole static page, the entry inherits that same visible parent gate. There is no
second root capability matrix or new role/designation policy.

## Complete indexed inventory

The audited portal contains 100 route pages: 68 static and 32 dynamic. The index has 63 possible
commands across 61 distinct static routes; each session receives only its authorized subset.
Organization/Structure and Platform Operations/Health deliberately share their canonical href:
the dock label and the local page label are both searchable. No particular session is assumed
to have every command.

| Group | Feature / breadcrumb | Static destination |
| --- | --- | --- |
| General | Overview | `/portal` |
| General | Notifications | `/portal/notifications` |
| Account | Account › Profile | `/portal/account/profile` |
| Account | Account › Security | `/portal/account/security` |
| Account | Account › Activity | `/portal/account/activity` |
| Account | Account › Preferences | `/portal/account/preferences` |
| Account | Account › Privacy | `/portal/account/privacy` |
| Scheduling | Appointments | `/portal/appointments` |
| Scheduling | Appointments › My appointments | `/portal/appointments/my` |
| Scheduling | Appointments › Book appointment | `/portal/appointments/book` |
| Scheduling | Appointments › Manage appointments | `/portal/appointments/manage` |
| Scheduling | Availability | `/portal/availability` |
| Scheduling | Availability › My availability | `/portal/availability/me` |
| Scheduling | Services | `/portal/services` |
| Scheduling | Availability › Office | `/portal/availability/office` |
| Scheduling | Availability › Counselors | `/portal/availability/providers` |
| Scheduling | Services › Create Service | `/portal/services/new` |
| Communication | Messages | `/portal/messages` |
| Communication | Messages › New message | `/portal/messages/new` |
| Records | Routine Interviews | `/portal/routine-interviews` |
| Records | Counseling | `/portal/counseling` |
| Records | Call Slips | `/portal/call-slips` |
| Records | Individual Inventory | `/portal/inventory` |
| Records | Individual Inventory › Current Individual Inventory | `/portal/inventory/current` |
| Records | Referrals | `/portal/referrals` |
| Records | Referrals › Record referral | `/portal/referrals/new` |
| Records | Call Slips › Issue Call Slip | `/portal/call-slips/new` |
| Requests and surveys | Good Moral | `/portal/good-moral` |
| Requests and surveys | Exit Interviews | `/portal/exit-interviews` |
| Requests and surveys | Feedback | `/portal/feedback` |
| Requests and surveys | Good Moral › Request Good Moral | `/portal/good-moral/request` |
| Requests and surveys | Graduate Tracer | `/portal/graduate-tracer` |
| Requests and surveys | Feedback › Customer Feedback responses | `/portal/feedback/customer-feedback/responses` |
| Requests and surveys | Feedback › CSM responses | `/portal/feedback/csm/responses` |
| Content | Announcements | `/portal/announcements` |
| Content | Resources | `/portal/resources` |
| Content | Announcements › Create Announcement | `/portal/announcements/new` |
| Content | Resources › Create Resource | `/portal/resources/new` |
| Reports | Reports | `/portal/reports` |
| Reports | Reports › Student Profiling | `/portal/reports/student-profile` |
| Reports | Reports › Graduate Tracer | `/portal/reports/graduate-tracer` |
| Institution | Academic Years | `/portal/academic-years` |
| Institution | Institutional Forms | `/portal/institutional-forms` |
| Institution | Organization | `/portal/organization` |
| Institution | Organization › Structure | `/portal/organization` |
| Institution | Organization › Responsibilities | `/portal/organization/responsibilities` |
| Institution | Organization › Student affiliations | `/portal/organization/student-affiliations` |
| Identity & Access | Accounts | `/portal/accounts` |
| Identity & Access | Accounts › Create account | `/portal/accounts/new` |
| Identity & Access | Accounts › Import accounts | `/portal/accounts/import` |
| Privacy | Privacy Governance | `/portal/privacy` |
| Privacy | Privacy Governance › Privacy Notices | `/portal/privacy/notices` |
| Privacy | Privacy Governance › Create Privacy Notice | `/portal/privacy/notices/new` |
| Privacy | Privacy Governance › Retention & Disposition | `/portal/privacy/retention` |
| Privacy | Privacy Governance › Retention Rules | `/portal/privacy/retention/rules` |
| Privacy | Privacy Governance › Create Retention Rule | `/portal/privacy/retention/rules/new` |
| Privacy | Privacy Governance › Privacy & Security Activity | `/portal/privacy/activity` |
| Platform | Platform Operations | `/portal/platform/health` |
| Platform | Platform Operations › Health | `/portal/platform/health` |
| Platform | Platform Operations › Maintenance | `/portal/platform/maintenance` |
| Platform | Platform Operations › Email delivery | `/portal/platform/email-delivery` |
| Platform | Platform Operations › Environment | `/portal/platform/environment` |
| Platform | Platform Operations › Technical activity | `/portal/platform/activity` |

## Deep-destination access rules

All rules below additionally require the visible parent from `portalWorkspaceGroups`.

| Destinations | Existing rule reused |
| --- | --- |
| My appointments / Book appointment / Manage appointments | `getAppointmentAccess`: `canViewSelf` / `canBook` / `canManage` |
| My availability | `canUseSelfAvailability` |
| Office / Counselors | `canManageAvailability` |
| Create Service | Services workspace/layout gate (`hasServicesWorkspace`) |
| New message | `getGuidanceMessagesAccess()`: `canManageSelf` or `canManageStaff` |
| Record referral | `getReferralAccess().canManage` |
| Issue Call Slip | `getCallSlipAccess().canManageOperational` |
| Current Individual Inventory | `getInventoryAccess().canViewSelf` |
| Request Good Moral | `getGoodMoralAccess().canRequestSelf` |
| Customer Feedback / CSM responses | `getFeedbackAccess().canViewCustomerFeedback` / `.canViewCsm` |
| Create Announcement / Create Resource | Parent gates (`canManageAnnouncements` / `canManageResources`) |
| Student Profiling / Graduate Tracer reports | Reports workspace/layout gate (`canAttemptReports`) |
| Structure | Organization workspace gate plus `canViewOrganizationStructure` |
| Responsibilities / Student affiliations | Organization workspace/layout gate (`canManageOrganization`) |
| Create account / Import accounts | Accounts workspace/layout gate (`accounts.manage`, inherited rather than duplicated) |
| Privacy Notices / Privacy & Security Activity | `canViewPrivacyGovernance` |
| Create Privacy Notice | `canViewPrivacyGovernance` and `canManagePrivacyGovernance` |
| Retention & Disposition / Retention Rules | `canViewRetention` |
| Create Retention Rule | `canViewRetention` and `canManageRetention` |
| Health / Maintenance / Email delivery / Environment / Technical activity | Platform workspace/layout gate (`platform_operations.view`, inherited rather than duplicated) |

Read-only Organization structure access does not grant the Organization management workspace.
Services catalog reads do not grant Services management. Feedback submission does not grant
operational response lists. Privacy and Retention view capabilities are independently checked;
the DPO designation itself grants no palette visibility. A Counselor receives no IT/DPO pages
merely from the role. A graduated Student cannot book an appointment through this index.

## Exclusions

These seven static routes are deliberately excluded:

| Routes | Reason / replacement |
| --- | --- |
| `/portal/account/security/password`, `/email`, `/authenticator`, `/sessions` (all under Security) | Credential-state-specific actions; aliases lead to `/portal/account/security` |
| `/portal/feedback/csm`, `/portal/feedback/customer-feedback` | Submission forms require an opportunity/context; enter through Feedback |
| `/portal/platform` | Redirect only; the existing dock opens `/portal/platform/health` |

All 30 dynamic routes are excluded because they require a record identifier and the palette
has no record context:

```text
/portal/accounts/[userId]
/portal/accounts/[userId]/access
/portal/accounts/[userId]/security
/portal/announcements/[announcementId]
/portal/announcements/[announcementId]/edit
/portal/appointments/[appointmentId]
/portal/call-slips/[callSlipId]
/portal/counseling/encounters/[encounterId]
/portal/counseling/summaries/[summaryId]
/portal/counseling/workspace/appointment/[appointmentId]
/portal/counseling/workspace/routine-interview/[routineInterviewId]
/portal/e-counseling/[appointmentId]
/portal/exit-interviews/[exitInterviewId]
/portal/feedback/csm/responses/[responseId]
/portal/feedback/customer-feedback/responses/[responseId]
/portal/good-moral/[requestId]
/portal/graduate-tracer/responses/[responseId]
/portal/inventory/history/[inventoryId]
/portal/inventory/records/[inventoryId]
/portal/privacy/notice-revisions/[revisionId]
/portal/privacy/notices/[noticeId]
/portal/privacy/retention/cases/[caseId]
/portal/privacy/retention/rules/[ruleId]
/portal/referrals/[referralId]
/portal/referrals/[referralId]/issue-call-slip
/portal/resources/[resourceId]
/portal/resources/[resourceId]/edit
/portal/routine-interviews/[routineInterviewId]
/portal/services/[serviceId]
/portal/services/[serviceId]/edit
```

Selected Counselor schedules are also excluded: the current API cannot resolve the required
Counselor summary independently by ID. Availability › Counselors remains the authorized entry
for managers. This existing backend limitation was not changed.

## Search and interaction

Matching trims, lowercases, and collapses whitespace. It ranks exact label, label prefix, label
substring, breadcrumb/group substring, then static keyword substring. Original registry order
breaks ties. An empty query shows Overview, visible dock workspaces, Notifications, Account,
then stable deep entries. No results reads “No COMPASS features match your search.”

Aliases include calendar/schedule/booking, profile/account details, password/mfa/2fa/authenticator/
sessions/sign in, forms/form revision/controlled form, retention/disposition/hold, privacy notice/
activity, student affiliation/college/program, responsibility/supervision/staff assignment,
email delivery/smtp/mail, worker/celery/diagnostic, maintenance, build/runtime, and technical/
platform activity. Aliases are not rendered as new feature names. There is no fuzzy or AI search.

The desktop trigger shows the Search icon, Go to… and a supplemental `⌘ / Ctrl K` hint. Narrow
mobile shows the compact Search icon with the full accessible name “Go to a COMPASS feature”;
the shortcut hint is hidden. Existing dock, mobile drawer and account/accessibility controls remain.

The shortcut listener exists only while PortalShell is mounted and is removed on unmount. It
accepts exactly Ctrl+K or Meta+K, prevents the handled shortcut's default, and toggles the palette.
Repeats, composition, unrelated modifiers and already-handled events are ignored. Any other open
Radix Dialog/AlertDialog or native HTML dialog prevents opening; it is not dismissed by the palette.

The current Radix Dialog provides modal focus containment and Escape/overlay/close-button
behavior. Opening focuses the labeled combobox. Arrow Down/Up wraps through results; Enter
clicks the selected actual guarded link. `aria-controls`, `aria-activedescendant`, listbox/options
and `aria-selected` communicate that selection. Mouse/touch selects the same links. Input focus
is retained during ordinary mouse selection so a declined guard leaves search usable. Closing
restores the opening control; a disconnected opener falls back to the top-bar trigger.

Every result uses GuardedPortalLink with `prefetch={false}`. Its existing unsaved-navigation
confirmation runs before the close callback. Rejecting preserves the route, form and open palette;
accepting closes and permits navigation. Selecting the current pathname closes without navigation,
preserving current query parameters, editor state and scroll. The palette never calls `router.push`.

## Validation

Local commands completed successfully on the reconciled base:

| Check | Result |
| --- | --- |
| `pnpm api:generate` | Passed; no tracked contract/generated changes |
| `pnpm lint` | Passed, including final reconciliation rerun |
| `pnpm typecheck` | Passed, including final reconciliation rerun |
| `pnpm test` | **210 passed, 0 failed** |
| Focused palette tests after final fetch | **29 passed, 0 failed** |
| `pnpm build` | Passed, optimized production build |
| `git diff --check` | Passed |

Focused coverage includes six representative sessions (Student, GSS, Counselor, Head Guidance,
IT Admin, DPO), effective-capability overrides, lifecycle restrictions, static-route existence,
root parity, aliases/ranking/ties, shortcut/cleanup/modal rules, actual component key handlers,
current-path handling, actual guard reject/accept order, accessible markup, focus callbacks,
and local/private query behavior. Handler tests use small hook storage and SSR with the existing
test tooling; they do not substitute for the browser checks below.

### Browser review with synthetic current-policy sessions

The running frontend used a temporary local read-only mock API and synthetic sessions derived
from current backend policy. No real account, record, credential or remote environment was changed.
This establishes frontend visibility/interaction behavior, not live backend authorization or deployment.

| Session | Queries and observed scope |
| --- | --- |
| Student | appointment, book, inventory, security, profile; self destinations only; retention/platform/forms produced no results |
| Counselor | appointments, availability, counseling, referral, reports; My/Manage appointments, My availability, assigned/operational workspaces and reports; no IT/DPO commands |
| IT Admin | accounts, platform, email delivery, maintenance, environment, forms; management/platform entries; **forms correctly absent** from the default baseline without institutional_forms.view |
| DPO | privacy, retention, activity; notices/retention/rules/privacy activity per effective capabilities, with distinct Account activity; no IT platform commands |

Screenshots were inspected at 1440×900, 1280×900 with expanded and collapsed docks, 768×1024,
and 375×812. The trigger preserves surrounding controls, the modal fits, no horizontal clipping
was visible, long breadcrumbs wrap, and mobile rows remain usable. Mobile keyboard footer/hint
is hidden; the full accessible trigger name remains.

In the browser: Cmd/Ctrl+K opened and focused search from an ordinary Profile control; query
filtering and Arrow Down/Up changed the active option; Enter selected destinations; Escape returned
focus both to that ordinary control and to the visible trigger. Selecting the current Profile route
preserved `?kept=1`. Navigation to Notifications completed with the palette closed. Cmd+K while
the mobile drawer was open left that drawer as the only modal and did not open the palette.
A unique no-results query was absent from all mock API request URLs.

**Manual limitation:** the dirty Profile form did trigger the existing native unsaved-change
confirmation, but the in-app browser automation timed out while it was open and did not expose
it through its documented JavaScript-dialog interface. Manual rejection/acceptance was therefore
not verified. The automated regression invokes the real GuardedPortalLink and UnsavedChangesProvider
with a registered dirty guard and verifies rejection versus acceptance, route/close ordering and
preserved form data. No guard was weakened to work around the browser limitation. Synthetic
generic collection payloads do not validate all domain page contents. No assistive-technology
screen-reader session or real-provider end-to-end run is claimed.

## Explicit scope/privacy confirmations

- No record data is searched.
- No backend search endpoint was added.
- No record IDs are indexed.
- No unauthorized feature is rendered and merely hidden with CSS.
- Top-level visibility reuses the existing portal workspace registry.
- Deep destinations use current access helpers and the actual workspace/layout gates.
- Dynamic record routes are excluded.
- Palette navigation cannot bypass the existing unsaved-change protection.
- No mutation can be executed directly from the palette; action entries navigate to pages.
- No new cmdk/search dependency was added, and Next.js was not upgraded.
- No backend/OpenAPI/schema/migration/generated API contract changes were made.
- Search queries cause no backend request, analytics, logging, storage or search history.
