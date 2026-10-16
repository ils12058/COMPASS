# BACKLOG-GM-ASSIST-1 — GCO-assisted Good Moral initiation

## A. Baseline

- Repository: `ils12058/COMPASS`; target: `staging`.
- Fetched base: `9531269c0d34cb99a472a1c6b8c243ab260eb1dd`.
- Isolated managed worktree: `/Users/reynantlntno/.codex/worktrees/backlog-gm-assist/COMPASS`.
- Branch: `feat/backlog-gco-assisted-good-moral`.
- Reviewed Good Moral models, creation identity, current/graduate validation, preparation, issuance, cancellation, PDF/release auditing and work projections; accounts policy; audit action/context; Activity domain selection and projection; Notification policy, intent, EmailDelivery, rendering and asynchronous delivery; operational Student-selection services and picker; existing frontend request/detail/history/print flows; related focused tests and frontend architecture guidance.
- Inspected concurrent worktrees. PG-1A, the primary checkout and other workstreams were not changed. No merge or deployment performed.

## B. Implementation

### Backend and contract

- Added explicit `good_moral.initiate`, granted to Counselor/GSS with a dependency on `good_moral.view`. Role, active-account and effective-capability checks apply independently, both at API and service boundaries. The staff actor is reloaded under a row lock before creation.
- Added strict operational `POST /api/v1/good-moral/requests/current-student` and `POST /api/v1/good-moral/requests/graduate`, plus `GET /api/v1/good-moral/student-options`. Static routes precede UUID routes. Payloads accept the target Student and variant-specific request facts; extra server-owned fields are rejected.
- Extracted the existing current/graduate creation implementations behind thin self-service wrappers. Canonical validations, snapshots, prerequisites and persistent creation-identity handling stay shared. Self-service retains its prior audit metadata, inputs, multiple-request behavior and notification expectations.
- Regenerated the canonical OpenAPI contract and Orval client. Generated client files remain uncommitted.

### Student selection and scope

- Reused `EligibleStudentPicker` presentation, with a Good Moral-specific generated option type.
- Existing selection endpoints have separate authorization purposes, College scopes and/or CURRENT-only populations. None was broadened.
- The new endpoint requires initiation and operational read authority. It returns active CURRENT/GRADUATED Students, bounded to 50 per page (UI uses 10), searched by supported name fields or Institutional ID; a 160-character maximum and deterministic pagination apply.
- **Actual Good Moral scope is office-wide:** the existing operational list/detail/work and Activity authorization do not restrict Counselors or GSS by College. The selector follows that policy and adds no College restriction or `accounts.manage` access.
- Options expose only UUID, name, authorized Institutional ID, active College summary and the lifecycle-derived variant. No email, answers, confidential content or eligibility trust flags are returned. Candidates can still lack a prerequisite: submission revalidates the authoritative Student under its row lock.

### Provenance and migration

- Added `initiation_origin` (`STUDENT_SELF`, `GCO_ASSISTED`, `LEGACY_UNSPECIFIED`) and nullable protected `initiated_by` in additive migration `good_moral.0006_initiation_provenance`.
- Existing rows become `LEGACY_UNSPECIFIED` with no invented initiator. No historical attribution backfill is attempted.
- A persistent database default lets an older backend omit the new columns during INSERT. A shape constraint requires a Student self-service initiator to equal the owner, an assisted initiator to be present, and legacy attribution to remain unspecified.
- New self-service requests store the Student as initiator; assisted requests store the authenticated Counselor/GSS. The selected Student remains canonical owner. Strict schemas/correction allowlists and transition update fields exclude initiation provenance, so correction, preparation, cancellation and issuance retain it.
- Student history/detail show office-level provenance without returning the initiating staff identity. Authorized operational detail additionally returns the initiator's ID and display name.

### Frontend

- Authorized operational users see **Start request for Student** in Good Moral. Its form offers explicit selection, canonical F4 inputs or explicit F6 facts, and a consequential review dialog naming the Student, College, variant and request details.
- Confirmation explains Student ownership and in-app/email delivery, and uses **Start Good Moral request**. Creation enters REQUESTED, with no preparation, issuance or printing.
- Confirmed success reports queued notification/email intent and provides **Open request** to the existing operational detail; affected queue/work/overview query keys are invalidated.
- An in-flight guard and disabled confirmation prevent double submission. An uncertain response retains the exact payload and key, locks selection/details, and offers explicit **Retry same request**. Known prerequisite and authorization errors remain in review with safe, operational copy. Search refreshes the same query and requires re-selection; choosing a Student clears details belonging to another target.

### Notifications and Activity

- Added catalog event `good_moral.request_initiated`, `MANDATORY_OPERATIONAL`, channels IN_APP and EMAIL, using existing Notification/EmailDelivery services and GOOD_MORAL target.
- Request, audit event, notification and pending EmailDelivery commit together. Existing post-commit enqueue handling catches broker failures, preserving durable recovery. No email is described as delivered merely because it was queued.
- Logical notification uniqueness remains recipient/event/source type/source UUID. An identical successful creation replay returns before audit/notification production. Self-service never emits this event; issuance still emits its separate existing event.
- Fixed text/HTML emails receive no source-domain context, staff details, request facts, identifiers, receipt data or confidential answers.
- Reused `GOOD_MORAL_REQUEST_CREATED` with the actual staff AuditContext and minimal assisted-origin metadata. My Activity distinguishes Student self-service, affected Student and actual staff actor. Selection verifies current source read authority, canonical ownership, persisted assisted origin and matching initiator. Pagination and output minimization remain unchanged. No Security, Supervised, Privacy or Platform Activity registry was extended.

## C. Business-rule validation

- **F4:** active CURRENT Student; submitted current-year Inventory; active College/campus affiliation; required submitted graduation Exit Interview when its graduation opportunity exists; canonical year/semester; existing profile/Inventory/Academic Year snapshots.
- **F6:** active GRADUATED Student; explicit degree, optional major and historical non-future graduation date. No facts are invented.
- No Inventory or Exit Interview is opened, completed or edited through this feature.
- Existing preparation, correction/version fences, frozen FormRevision, Counselor-only issuance, certificate templates, physical signature/dry-seal, PDF release audit and cancellation rights remain in place. GSS initiation does not grant issuance.
- **Duplicate strategy:** no global pending uniqueness constraint. Under the shared Student row fence, a *new assisted intent* is rejected while any REQUESTED/READY_FOR_ISSUANCE request exists, including a self-service request. Identical successful replay is resolved first. A new assisted request is possible after cancellation/issuance. Existing self-service policy still permits multiple legitimate requests.
- Staff creation key digest is scoped to authenticated actor and assisted namespace, independently of target or route. The fingerprint additionally binds actor, target Student, variant, wire fingerprint and request facts. Reusing a key with a different Student, variant or payload conflicts; another actor cannot retrieve the first actor's result. Actor and Student row locks serialize same-key and competing-staff creation.

## D. Security and privacy

- Role overrides do not bypass the Counselor/GSS source boundary. Inactive actors, denied initiation/read capabilities, invalid targets and changed Student eligibility fail safely.
- Student self/detail/PDF APIs remain owner-scoped; assisted requests preserve existing Student cancellation/download rights. Other Students cannot read the request.
- No impersonation or trusted initiator payload field exists. The authenticated actor must match AuditContext. Staff identity is limited to existing operational authorization; Student responses carry only the origin.
- Activity content contains neither actor identity nor sensitive audit metadata. A forged actor/source relationship cannot create assisted activity visibility. Unrelated staff, IT and DPO gain no new professional feed access.
- Tests use synthetic identities and intercepted browser APIs. Email enqueue/transport is mocked in assisted tests; no real email is sent.

## E. Testing

| Validation | Result |
| --- | --- |
| New assisted backend suite | **46 passed**; authorization, source eligibility, F4/F6, provenance, strict payloads, key/target/payload conflicts, pending duplicates, concurrency, notification atomicity, durable email retry, Activity isolation and historical/default/migration compatibility |
| Existing Good Moral + preparation suite | Initially 98 passed, 3 failed. The added self-service audit metadata regression was corrected; its existing test passes in the subsequent regression run. The two remaining preparation failures reproduce unchanged on base staging; details below. |
| Activity + notifications + self-service audit regression | Initial combined run: 80 passed, 1 fixture failure for newly supported staff creation. The fixture now supplies persisted assisted provenance. **29 corrected Activity relationship tests, including the new forged-origin/actor negative test, pass separately.** |
| Frontend components | **44 passed** across assisted creation, preparation, print, canonical inputs and Activity retrieval suites |
| Assisted browser workflow | **12 passed per engine**, Chromium and WebKit; final production build, synthetic intercepted APIs |
| Existing issuance/print browser workflow | **20 passed per engine**, Chromium and WebKit; F4/F6, 320/1440 widths, uncertainty/staleness, authorization, reprint and Student download |
| API generation | `pnpm api:generate` passed; backend `export_openapi --check` passed |
| Migration drift | `makemigrations --check --dry-run` reports no changes; the new suite also migrates 0005 → 0006 and verifies an old-model INSERT after migration |
| Backend lint | Ruff check/format for changed backend files passed |
| Frontend quality | **`pnpm lint`, `pnpm typecheck`, `pnpm build` passed.** Lint has four pre-existing unused-variable warnings in untouched `tests/portal-navigation-attention.browser.mjs`, no errors. |
| Diff integrity | `git diff --check` passed |

Reproduction (from this worktree; use an isolated PostgreSQL test database name):

```sh
cd be
POSTGRES_DB=compass_gm_assist_new .venv/bin/pytest tests/test_good_moral_assisted.py --reuse-db -q
POSTGRES_DB=compass_gm_assist_new .venv/bin/pytest tests/test_domain_activity.py::test_allowlisted_actions_have_exact_viewer_relationships tests/test_domain_activity.py::test_assisted_creation_requires_persisted_initiator_and_origin --reuse-db -q
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python manage.py export_openapi --check
cd ../fe
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
node --import ./tests/support/register-tsx.mjs --test tests/good-moral-assisted.test.mjs tests/good-moral-preparation.test.mjs tests/good-moral-print.test.mjs tests/good-moral-request-standardization.test.mjs tests/activity-retrieval.test.mjs
# Start a local server, then run each suite with Chromium and COMPASS_UI_BROWSER=webkit.
COMPASS_UI_BASE_URL=http://localhost:3137 node tests/good-moral-assisted.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3137 node tests/good-moral-print.browser.mjs
```

**Inherited failures, deliberately unchanged:**

1. `test_good_moral_preparation.py::test_safe_corrections_preserve_sources_and_ready_requires_reconfirmation` writes noncanonical year level `Third`.
2. `test_good_moral_preparation.py::test_prepare_validates_completeness_and_rejects_stale_review` writes an empty semester.

Both fail the canonical validation introduced before this slice. The same two tests fail on an archived, unmodified copy of `9531269c` in an independent test database (2 failed). This is evidence of inherited fixture drift, not a claim that repository CI is green. No shard or unrelated validation rule was changed.

Browser evidence: `outputs/gm-assist-browser/good-moral-assisted-{chromium,webkit}/results.json` and phone/tablet PNGs. Screenshots were visually reviewed for layout, accessible controls, selected identity, readable details and responsive overflow. Headless print tests validate application/browser behavior with synthetic PDF bytes, not physical paper output.

## F. Deferred issues and operational notes

- Deployment must apply the additive migration and run the repository's existing explicit `sync_identity_policy` procedure to persist the new capability/grants. This task performs no deployment.
- Historical initiation identity remains unspecified. A separate evidence-backed attribution exercise would be needed before any backfill.
- Physical printing, signature and dry seal cannot be proven by headless browser tests; existing issued-PDF preview/download/print workflow is exercised with synthetic PDFs.
- The repository's consolidated CI stabilization remains deferred by owner instruction. No unrelated CI fixes or shard changes are included.
