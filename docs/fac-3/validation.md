# FAC-3 validation

Validated on 2026-11-01 against integration base `1a8f9aa3`. All accounts,
approval decisions, Students and Referral contents used here are synthetic.
No production record, institutional approval, UAT or deployment is represented.

## Observed results

| Check | Result |
| --- | --- |
| Faculty backend and canonical OpenAPI integration | **100 passed**, 78.84 seconds |
| Final strict availability/intake/own DTO schema check | **1 passed**; overlaps the consolidated contract suite |
| Complete frontend node suite | **1,032 passed**, 42.16 seconds |
| Faculty contract/layout/error browser suite | **35/35 Chromium; 35/35 WebKit** |
| Disposable real-backend browser suite | **5/5 Chromium; 5/5 WebKit** |
| Existing FAC-1 browser regression suite | **11/11 Chromium; 11/11 WebKit** |
| API generation, ESLint, TypeScript, production build | Passed |
| Backend Ruff lint/format, OpenAPI freshness, model/migration drift, whitespace | Passed |

The six browser result files record **102 passing checks** and are committed under
[browser-results](browser-results). [Screenshots](screenshots.md) were inspected for
Home composition, review/reflow, minimal detail and actual canonical success.

Backend cases exercise independent lookup/submission/own-read availability,
default-denied providers, active form, capability revocation, managed home,
role/session revalidation and the strict allowlisted DTO. The existing FAC-2 intake,
encryption, cross-College, idempotency, privacy, ownership and audit cases still pass.
No new schema migration or GCO processing change is introduced.

## Browser coverage and fixes

The Faculty suite covers 320, 390, 768, 1024 and 1440px, each at 100% and 200% text,
with long unbroken names/reason text. It verifies no document horizontal overflow
in form, review, success and detail; primary/secondary actions remain reachable
without fixed overlays. The enlarged form fieldset and review labels/actions needed
explicit shrink/wrap bounds; these were corrected and the full matrix rerun.

Both OS light/dark preferences and reduced motion are exercised. COMPASS continues
to render its intentional light interface; no unrequested dark theme is added.
Labels, inline error announcements, first-invalid-field focus, review-heading focus,
and a complete keyboard confirm/review/submit path are checked. macOS WebKit uses Safari's
Option-Tab traversal for controls; Chromium uses Tab. This is browser accessibility
evidence, not a completed assistive-technology user study.

Behavior cases cover unavailable/approved/read-only Home, uniform negative Student
confirmation, form validation, policy 403, conflict 409, confirmation 429/503,
expiry/reconfirmation, frozen uncertain retry, pending duplicate prevention,
deliberate discard/cancel, loading/error/retry, empty and paged own lists, safe 404,
foreign/non-Faculty/GCO routes, and role/session transitions without unsafe replay.
The filled workflow verifies that identifiers, confirmation values and reason text
do not enter URLs or browser persistent storage. Source review confirms no feature
logging/analytics or persistent draft mechanism.

The existing FAC-1 suite also preserves managed provisioning, stale affiliation
review and CSV references. Full node tests preserve GCO/Student command/navigation
semantics. Existing Notifications and read-only Profile integration are reused.

## Actual PostgreSQL-backed browser proof

`be/tests/faculty_portal_server.py` creates a uniquely named disposable database on
loopback, migrates it, and installs only the isolated FAC-2 synthetic approved-policy
fixture in that test process. Its Faculty home is CAS and Student placement is CCMS.
The app's normal session/CSRF/Faculty APIs handle the browser interaction. No
production provider, feature flag, approval endpoint or permission bypass is added.

The live browser suite performs real confirmation and creation, reads canonical own
records, and verifies another Faculty's safe 404 and Student route denial. For the
uncertain case, the test lets the actual backend commit a **201**, drops the browser
response, verifies no automatic replay, and deliberately retries the same exact
body/key. The backend returns **200 canonical replay**. The UI then shows its actual
generated reference and Submitted time; no reason appears in own detail.

The server's 0600 temporary manifest contains synthetic session cookies only. It is
never committed, copied into screenshots or printed. Shutdown removes the manifest
and the database created by that process. Ordinary local/deployed providers remain
`None` and default availability remains all false.

## Reproduction

Backend, from `be/`, using the existing test PostgreSQL/Redis dependencies:

```sh
.venv/bin/pytest tests/test_faculty_referrals.py tests/test_openapi_contract.py --reuse-db -q
.venv/bin/python manage.py export_openapi --check --settings=tests.settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
```

Frontend, from `fe/`:

```sh
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
pnpm test
```

For synthetic contract/browser checks, start a local production build on port 3107
then run each suite with `COMPASS_UI_BROWSER=chromium` and `webkit`:

```sh
pnpm start --hostname 127.0.0.1 --port 3107
node tests/faculty-referrals.browser.mjs
node tests/faculty-foundation.browser.mjs
```

For actual backend proof, use a separate terminal in `be/`:

```sh
.venv/bin/python -m tests.faculty_portal_server /tmp/compass-fac3-session.json
```

In `fe/`, build/start the existing proxy against that isolated server, then run the
live suite in each engine:

```sh
COMPASS_API_BASE_URL=http://127.0.0.1:8033 pnpm build
pnpm start --hostname 127.0.0.1 --port 3107
node tests/integration/faculty-portal.live.mjs
```

Stop both local servers afterward. Do not overwrite an existing manifest. The live
suite is deliberately separate from the generic browser inventory because it needs
this disposable backend; the contract/error suite is automatically discovered by
the normal browser runner.

## Inherited CI and release limits

FAC-2's [merge validation](../fac-2/validation.md#merge-validation--2026-11-01)
records broad backend/browser failures compared to the parent FAC-1 runs. The
remaining backend cases concern privacy-notice query budget, Counseling joined-lock
scope, session-revocation helper inventory and an irreversible Organization rollback
rehearsal. Broad browser failures concern unchanged E-Counseling, public shell/assets,
email change, copy/information hierarchy and old action-layout assertions.

FAC-3 changes none of those owning workflows or assertions. No complete hosted
backend/browser pass is inferred from targeted local results. Integration PRs need
manual workflow dispatch under the repository's current trigger configuration;
the PR records those run links and their actual status. No deployment, release
readiness, real institutional approval or UAT is claimed.
