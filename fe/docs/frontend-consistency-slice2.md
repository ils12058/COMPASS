# Frontend communication audit — Slice 2

Initial audit and canonical conventions established before production edits on 2026-10-10.
Base: `staging` at `8ad8f86e6727a54a68f9ff0b80b2c8a0725114d5` (merged Slice 1).
Branch: `codex/frontend-consistency-slice2`, reusing the clean isolated Slice 1 checkout.

## Method and coverage

Screened all handwritten frontend TS/TSX with a TypeScript AST inventory: JSX text, strings, template fragments, attributes, constants, mappings, validation and mutation producers. Candidate strings include non-copy identifiers; inventory counts are discovery coverage, not a claim that every candidate is product text. Followed significant signals to actual component conditions and handlers, and read shared/domain error producers. Checked relevant backend code read-only for authority and controlled exceptions. Generated clients, external/user-authored data and official wording are excluded from editorial changes.

Baseline: **613 source files, 483 TSX, 119 page routes, 41 feature areas, 8,275 candidate text fragments**. Coverage includes public pages, authentication, portal chrome, Student, Counselor, GSS, institution/IT/privacy administration. Shared UI/loading/action/pagination labels and library error boundaries were considered alongside feature code. See the coverage table and significant findings below; browser evidence is representative, not every route or live backend.

## Initial inventory and decisions

Locations are baseline `fe/src/features/` paths. Each row records audience, current wording, condition, problem, replacement, safety, and required coverage. P1 means a confirmed path permits inappropriate internal diagnostics; it does not establish a live confidential-data incident. P2 is clarity/consistency; P3 is editorial/accessibility quality.

| ID / severity | Feature / location | Audience | Current wording | Condition | Problem | Replacement / decision | Semantic safeguards | Regression |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C01 P1 | Activity · `activity/activity-errors.ts:17` | Staff/admin | readApiErrorMessage(error.body) || fallback | Invalid filters/export/release | Unbounded diagnostics (including invalid bounded ISO date) are rendered | Code-owned filter, export-limit, and release guidance | Preserve no export and no release; no raw detail | Translation injection tests |
| C02 P1 | Privacy retention · `privacy-governance/privacy-governance-errors.ts:86` | Privacy administrator | return message || ... | Broad retention conflicts and rule/hold validation | Raw operational reasons; one code covers several causes | Safe review guidance; explicit rule values and hold reason | No inferred duplicate-code or lifecycle reason; maintain field guidance | Code matrix and unknown diagnostics |
| C03 P1 | Exit access · `exit-interviews/exit-interview-shared.tsx:58` | Students/staff | return readApiErrorMessage(error.body) ?? fallback | Required/not-open/conflicting access | Conflict may expose admission provenance diagnostics | Distinct office opening, closed access, and review guidance | No invented reopen/eligibility bypass; concealment unchanged | Three-code mapping and injection |
| C04 P2 | Inventory · `inventory/editor/inventory-editor.tsx:131` | Students | Raw conflict reason + Your answers are kept on this page. | Blocked save/submit with preserved input | Diagnostic override; generic changed claim is not always true | Review inventory details/status; preserve answers notice | Keep queries, input, and submission mechanics | Conflict render/source and producer tests |
| C05 P2 | Referrals · `referrals/referrals-shared.tsx:23` | Counselor/GSS | The Referral request contains a value that was not accepted. | Known invalid input | Backend request vocabulary | Some referral details need attention. Review them and try again. | Same code; no new field inference | Mapping rejection test |
| C06 P2 | Call Slips · `call-slips/call-slips-shared.tsx:28` | Counselor/GSS | The Call Slip request contains a value that was not accepted. | Known invalid input | Backend request vocabulary | Some call slip details need attention. Review them and try again. | Issuance and retry unchanged | Mapping and browser issuance |
| C07 P2 | Routine · `routine-interviews/routine-interviews-shared.tsx:149` | Counselor | configured ... form revision is not supported | Unsupported form | No useful next step | Current form cannot start new interview; contact administrator | No form replacement or editing of instrument | Mapping/browser dialog |
| C08 P2 | Appointments · `appointments/appointments-shared.tsx:43` | Student/staff | A Counselor could not be resolved. | Default provider unresolved | Implementation verb | A counselor could not be selected. Choose an eligible counselor and try again. | Existing selection and slot conflict unchanged | Booking producer and browser |
| C09 P2 | Services/Availability · `services/services-shared.tsx:51; availability/availability-shared.tsx:34` | Administrator/counselor | request contains a value ... | Invalid values | Implementation vocabulary | Review service/schedule details | No validation changes; admin terms remain where useful | Mappings; existing editor/guard tests |
| C10 P2 | Guidance Operations · `guidance-operations/guidance-operations-page.tsx:48` | Counselor/GSS | Current operational workload ... authorized scope. | Page description | Narrates internal authority | View the work you can act on and the current schedule. | Keep scope, counts, routing, zero values | Both-role browser rendering |
| C11 P3 | Assessment actions · `assessment-records/assessment-records-list.tsx:134; assessment-record-detail.tsx:44` | Staff | Record result assessment / Manage types assessment / Edit record assessment | Suffix-built accessible names | Object order is unnatural | Record assessment result / Manage assessment types / Edit assessment record | Visible labels retain Slice 1 marker; real links unchanged | Rendered PageActionLink and browsers |
| C12 P3 | Loading/list prose · `referrals/referrals-shared.tsx:82; services/services-shared.tsx:370; assessment-records/assessment-records-shared.tsx:89` | All roles | Loading Referrals / Services / Assessment Records | Initial load | Unnecessary title case; assessment missing ellipsis | Loading referrals… / services… / assessment records… | One status; formal instrument names preserved | Render tests and browser labels |
| C13 P3 | Services empty · `services/services-list-page.tsx:259` | Administrator | No Services are configured yet. | Unfiltered include-inactive zero records | Added records described as configuration | No services have been added yet. | Other branch remains no active services available | Separate empty predicates; browser |
| C14 P2 | Workspace access · `referrals/referrals-shared.tsx:97; student-actions/student-actions-page.tsx:39` | All roles | unavailable to this account / account can no longer open | Confirmed access or role gate | Indirect user instructions | Contextual access wording | Records remain neutrally unavailable; no new role inference | Denied/hidden fixtures |
| C15 P2 | Feedback · `feedback/feedback-shared.tsx:38` | Respondent | This submission key was already used ... | Known key conflict | Internal identity vocabulary | This submission attempt no longer matches its original response details. | Do not change in-progress/unavailable same-response recovery | Outcome/recovery tests |
| C16 P2 | Counseling · `counseling/counseling-shared.tsx:38` | Counselor | The Counseling request was not valid. | Rejected input | Request narration | Some counseling details need attention. Review them and try again. | Keep linked finalized evaluation and uncertain recording consequences | Mapping and dialog regressions |
| C17 P2 | Authentication/security · `auth/utils/errors.ts:5; account/components/account-errors.ts:4` | All users | Your security token expired. | CSRF rejection | Technical token phrasing | The security check expired. Submit the form again. | Explicit resubmission only; no replay | Mapping and security browser |
| C18 P3 | Shared/public Retry · `public/shared/public-state.tsx:45; inventory/inventory-shared.tsx:107` | Public/student | Try again (button) | Retry current read | Shared recovery labels drift | Retry | Handler/announcement/focus unchanged | Rendered buttons and public error fixture |
| C19 P2 | Reports/Platform · `reports/reports-shared.tsx:24; platform/platform-actions.tsx:27` | Admin/report reader | configuration unavailable or conflicting / request contains | Setup conflict/validation | Unhelpful phrasing | Review academic-year setup / maintenance details | Retain reporting-area boundaries and maintenance consequences | Producer mapping tests |
| C20 P3 | Organization/institution · `organization/responsibilities/responsibilities-page.tsx:308; institution-configuration/academic-years-page.tsx:197` | Administrator | No ... configured / Loading Campuses | Unassigned or absent reference records | Ordinary capitalization/verbs drift | No college counselor responsibilities assigned / academic years added | Preserve hierarchy, assignment meaning, legacy identities | Existing admin/browser tests |
| C21 P2 | Good Moral/Tracer · `good-moral/good-moral-shared.tsx:96; graduate-tracer/graduate-tracer-shared.tsx:31` | Student/staff | approved document configuration ... / action with this account | Blocked issuance/access | Indirect next step/access | Approved certificate setup unavailable; contact administrator / contextual action denial | Official certificate wording and prerequisites untouched | Date, prerequisite, uncertainty matrix |

Additional semantic review and validation found:

| ID / severity | Feature / location | Audience | Current wording | Condition | Problem | Replacement / decision | Semantic safeguards | Regression |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C22 P1 | Appointments · `appointments/appointment-booking-outcome.ts:44` | Student/staff | The Appointment could not be booked; uncertain=false | Generic server error/timeout | Does not establish failed booking | Unconfirmed result and same-details Retry label | Existing keepIntent=true and all slot/rejection handling remain | Actual classifier status matrix and browser same-key Retry |
| C23 P1 | Feedback · `feedback/csm-form.tsx:259`; `customer-feedback-form.tsx:279` | Respondent | Could not be submitted | Generic server error/timeout | Outcome may be uncertain; existing recovery clears intent | Unconfirmed result; check feedback status before trying again; contact office if unclear | No change to submission/idempotency mechanics; same-identity recovery enhancement deferred | Submission message producer and actual form browser |
| C24 P1 | Good Moral · `good-moral/good-moral-request-page.tsx:119` | Student/graduate | Request could not be created | Network/server error | Doesn't describe the existing uncertain recovery | Request result unconfirmed; Retry same request | Existing uncertain intent and key retained | Actual request browser and uncertainty producer tests |
| C25 P2 | Availability · `availability/availability-shared.tsx:37` | Counselor/admin | Availability change conflicts with current configuration | Unavailable timezone or required database support | The code does not prove the user entered conflicting hours | Schedule unavailable; retry or contact institutional administrator | Backend raises this code for infrastructure prerequisites, not overlapping hours; no guessed correction | Code-owned mapping and diagnostic injection |
| C26 P2/P3 | Referral action · `referrals/referral-action-section.tsx:205,269,301`; catalog · `assessment-records/assessment-types-page.tsx:241`; delivery · `services/service-detail-page.tsx:300; counseling/record-encounter-form.tsx:319`; year · `institution-configuration/academic-years-page.tsx:182` | Counselor/admin | source action / No Assessment Types configured / no delivery mode configured | Recorded historical action or empty setup | Implementation narration and inconsistent ordinary prose | Referral action; types added; selected/available delivery mode; current year not set | Retain permanent-history and no-call/letter/notification consequences; empty predicates unchanged | Actual action browser and existing catalog regressions |

## Feature coverage

Every discovered area was screened; areas without a verified correction retain their effective copy. Counts are handwritten TS/TSX files at the audited base.

| Area | Files | Reviewed communication / decision |
| --- | ---: | --- |
| accessibility | 3 | Control names and preferences; retain clear labels |
| account | 18 | Profile, MFA, sessions, trusted browsers, email change; consequences preserved |
| accounts | 10 | Account administration, import, last-manager safeguards; preserve contracts |
| activity | 2 | Code translations for filters, large exports, release failures |
| announcements | 12 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| appointments | 9 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| assessment-records | 6 | Record/type names, confidentiality, actions/errors |
| auth | 12 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| availability | 6 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| call-slips | 8 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| content | 11 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| counseling | 13 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| ecounseling | 24 | Call, media, consent, pending/rejoin state; controlled consequences retained |
| exit-interviews | 16 | Access/eligibility/submission/chrome/errors; official responses untouched |
| feedback | 7 | Response/chrome/errors and same-submission recovery; instruments untouched |
| form-safety | 3 | Dirty-draft and discard consequences; preserve |
| freshness | 5 | Last-confirmed data and retry warnings; preserve |
| good-moral | 15 | Prerequisites, preparation, issuance, dates, uncertain retry; certificate source untouched |
| graduate-tracer | 12 | Survey chrome/loading/access; official questions and anonymization consequences untouched |
| guidance-messages | 25 | Send/retry/edited-new-intent, assignment, resolution and templates; authored messages untouched |
| guidance-operations | 4 | Both staff roles, scope and stale/zero-result descriptions |
| institution-configuration | 7 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| institutional-forms | 1 | Revision metadata and selector; controlled identities preserved |
| inventory | 24 | Editor/conflict/retained answers and roster; official questions untouched |
| notifications | 11 | Mark-read and push recovery; no trigger/recipient edits |
| organization | 9 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| platform | 14 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| portal | 24 | Dock, command palette, overview and account ownership; destinations unchanged |
| privacy-governance | 21 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| public | 24 | Announcement/resource errors, retry, downloads; approved privacy content untouched |
| pwa | 1 | Install/update wording; preserve |
| realtime | 5 | Connection recovery; no user data in hints |
| referrals | 9 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| reports | 17 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| resources | 12 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| routine-interviews | 9 | Intake/evaluation/create/errors; instrument and finalization rules untouched |
| security | 1 | Turnstile/security boundary; no behavior edits |
| services | 8 | Titles, descriptions, action names, fields, status, loading, empty/error, confirmations and recovery reviewed in context |
| student-actions | 4 | Student role gate, denied/empty/later-page and source links |
| student-support | 2 | Read-only support context and unavailable/loading copy |
| work-queue | 4 | Priority, boundaries, empty/later-page, denied and stale results |

## Canonical conventions

[User-copy guide](user-copy-guide.md) is the contributor reference. It establishes task language, formal names versus sentence case, complete accessible suffixes, safe code-based errors, uncertain results, precise workflow verbs, role-aware copy, empty/success distinctions, and controlled wording boundaries. Existing UI hierarchy and Slice 1 structure remain authoritative.

## Preserved and deferred findings

- Appointment time conflicts already say "That time was just taken. Choose another available time." Preserve them.
- Booking, Good Moral, Referral and Call Slip recovery already retains the intended identity; Feedback does so for network and known in-progress/unavailable paths; Counseling requires checking encounters to avoid a duplicate; Messages preserves same-ID Retry and explicit edited-new-message consequences. Preserve all guards/handlers.
- Backend Announcement/Resource/Privacy validation codes aggregate several reasons. Existing exact known-message translations remain bounded and safe; more precise structured subcodes are deferred backend work. No new English-message inference is introduced.
- Password-policy structured detail messages are intentionally user-safe validation from the backend password validators. Good Moral's two controlled future-date errors identify the wrong certificate date. Preserve useful field-specific authority.
- Feedback generic server errors currently clear the submission identity, unlike known idempotency-unavailable/in-progress errors. Copy now directs status checking before another attempt. Extending the same-identity recovery is a separate submission-mechanics change, explicitly excluded here.
- Broad retention, Inventory and Exit access conflicts lack structured subtype/field details. Use accurate safe guidance, not a guessed cause; structured specificity is deferred contract work.
- Official Inventory/Exit/Routine/Graduate Tracer/Feedback instruments, privacy/legal/consent text, certificates, controlled record/form identifiers, user messages, imported answers, historical snapshots, and operator messages stay unchanged. Editorial concerns inside them require institutional/legal review.
- Reports' "authorized reporting area", retention/disposition, MFA, capability overrides and deployment diagnostics are meaningful administrative concepts. They are intentional exceptions, not prohibited vocabulary.
- No localization, new copy dictionary, UI library, redesign, backend/API/schema/auth/capability/lifecycle/rule change is needed.

## Implementation and validation

Changes span **97 handwritten production files in 31 feature areas**, plus this audit, the contributor guide, existing guidance links and regression tests. Most production changes are strings. Narrow presentation logic handles server/timeout uncertainty in booking, Good Moral and Feedback; raw diagnostic paths are replaced by code-owned copy. No handler, request payload, key generation, recovery guard, permission check, validation rule, query, destination, notification trigger or controlled source was changed.

Representative corrections:

| Before | After | Why |
| --- | --- | --- |
| Call Slip request contains a value ... | Some call slip details need attention. Review them and try again. | Explain validation in task language |
| configured Routine Interview form revision is not supported ... | The current Routine Interview form can't be used to start a new interview. Contact the Guidance Office administrator. | Accurate prerequisite with no workaround |
| Record result + assessment; Manage types + assessment | Record + assessment result; Manage + assessment types | Natural complete accessible names; Slice 1 visible markers and real destinations retained |
| No Services are configured yet. | No services have been added yet. | Only the successful unfiltered include-inactive zero-record branch |
| Raw Inventory conflict reason | Review answers/status; Your answers are kept on this page. | No internal diagnostic disclosure; unsaved editor retained |
| Appointment could not be booked (generic 500) | Booking response could not be confirmed; Retry booking | Existing same-details identity retained; no false failure claim |
| Feedback could not be submitted (generic 500) | Submission result unconfirmed; check status before another attempt | Avoid duplicate guidance without promising unavailable same-key recovery |

Semantic review confirms stable codes remain authoritative, unknown diagnostics use safe fallbacks, concealment remains neutral and existing confidential-data gates remain. Known rejection, slot conflict, in-progress, already submitted and unconfirmed outcomes stay distinct. Permanent-history, linked-record, notification, cancellation and privacy consequences remain at the decision. Official instruments, consent/legal disclosures and user/historical content remain faithful to their sources. Booking's uncertainty flag changes only alert tone and button wording; its existing keepIntent=true path and payload/key remain.

New `tests/user-copy.test.mjs` contains **74 checks** of actual message producers across 23 domains, known/unknown diagnostic injection, structured-field allowlists, compatibility exceptions, concealed records, code/status authority, uncertain booking/message/submission recovery, prerequisites, linked records, rendered alerts/loading and real Assessment action props. The raw-message import guard is scoped to verified producers, with no indiscriminate vocabulary ban.

New `tests/user-copy.browser.mjs` exercises **18 scenarios at 320px and 1440px in Chromium and WebKit (72 checks)**: validation and hidden-record states; Exit/retention conflicts; Referral creation/historical-action consequences; Call Slip issuance rejection; Routine prerequisite/focus return; Inventory retained answers; Good Moral and booking same-request retries; both Feedback forms' unconfirmed guidance; sign-in security rejection. Assertions verify labels, single announcements, no raw diagnostics or horizontal overflow, retained inputs, no extra submissions and original booking payload/key. `test:ui:copy` is included in both full and CI regression scripts. Eleven existing test files keep their precise assertions with updated expected copy.

Validation results and limits are recorded below. Local synthetic validation does not establish GitHub CI, live-backend, deployment, real-device or assistive-technology proof.

| Command / evidence | Result |
| --- | --- |
| `pnpm api:generate` | Passed; generated clients, contracts and lockfile have no diff |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm test` | 550/550 passed (476 existing + 74 new) |
| Focused copy checks after formatting | 74/74 passed |
| `pnpm test:ui` | All 676 existing checks passed; first new-suite run had two 320px WebKit clicks intercepted by the Next.js development toolbar (746/748). No browser runtime errors. Retained the submission assertions and switched those activations to real keyboard focus/Enter. |
| `pnpm test:ui:copy` after keyboard adjustment | 72/72 passed, 36/36 in each engine; combined executed coverage 748/748 |
| `pnpm build` | Passed; optimized compile, TypeScript and prerendering completed |
| `git diff --check` | Passed |

Browser logs and screenshots are local artifacts under `/tmp/compass-slice2-full-browser` and `/tmp/compass-slice2-copy-verified`. Existing suites cover Counselor/GSS/Student/admin permissions, Assessment catalog and corrections, messaging retry/privacy/assignment, Call Slip download/retry, security/session and draft retention, operations and queues, public/admin routes, E-Counseling and the Slice 1 visual/interaction guards. Chromium/WebKit are synthetic desktop browsers at representative viewport sizes; no live institutional records, provider sessions or notifications were used. Assessment live-test selectors were updated, but no live test was run.

GitHub CI status is reported separately in the PR handoff. No merge or deployment is part of this slice.
