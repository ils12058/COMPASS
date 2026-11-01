# FAC-4 validation — 2026-11-01

All identities/records/evidence in this report are synthetic. The implementation targets
integration `e10671e24a5a222f62e80aebb6ca22a9832fd905`, verified as the current remote base,
with merged #348/#349/#350. There is no institutional activation, UAT or deployment.

## Backend and database evidence

The final administration/linked-domain run passed **146 tests**: 25 FAC-4 functional/API/
privacy/policy tests, 18 actual PostgreSQL concurrency cases, two fresh/populated FAC-4
migration cases, 33 Follow-Up, 46 Call Slip, five canonical baseline and 17 Audit cases.
The separate compatibility run passed **133 tests**, covering FAC-2 intake/idempotency/
concurrency/migrations, existing canonical Referral behavior/encryption/PDF/authorization
and OpenAPI contracts. Together these final runs passed **279 backend tests** with no
overlap between their test files.

The 18 race cases use independent PostgreSQL connections and assert an observed lock
wait via `pg_stat_activity`: duplicate acknowledgment/closure, both orders of transition
versus void, acknowledgment versus closure, role/activity/responsibility/supervision and
Student placement changes. Concurrent evidence never skips prior receipt or creates a
second transition event. The failed-before-receipt race retains an outer transaction gate
while observing contention; a rejected transition itself does not retain rolled-back locks.

Actual account role changes respect existing relationship-removal requirements. The GSS
role race removes its supervision through the supported service before changing the role
within the same transaction; it does not bypass organizational integrity.

The migration rehearsal creates its own PostgreSQL database at the actual FAC-2
`referrals.0002` schema, optionally populates paper and Faculty rows, then upgrades to
0003. Every old field (including receipt, ciphertext, authorship and saved policy/form
references) and every Audit row is compared. Only administrative version/default null
facts are added. Full test database creation also applied all current migrations. Existing
Faculty rollback guards continue to refuse dropping digital history.

Functional cases additionally prove current role/capability/session/Student College policy,
supervised GSS cross-College handling, strict payloads and actual server actor/time,
synchronous Audit rollback, immutable tuples, safe duplicates, separate tracking disclosure,
foreign ownership 404, void omission, unchanged linked pending/confidential Follow-Up and
active Call Slip, existing void restrictions, no automatic receipt from read/render/actions/
Call Slip creation, source-form correctness and an explicitly inactive notice contract.
No Notification is created by transitions even under synthetic positive acknowledgment/
closure evidence. The notice candidate is not a delivery adapter or evidence of delivery.

Static verification: backend Ruff lint/format, migration drift, current OpenAPI export,
canonical migration checks, whitespace, and CI test-inventory verification passed. All
209 backend test files are registered exactly once. The CI planner's 60 self-tests passed.

## Frontend and real browser evidence

**1,032 frontend unit tests passed.** API generation, ESLint, TypeScript and the local
production build passed. Generated clients are not manually modified or committed.
The new browser suite is discovered automatically by the existing CI inventory.

**200 browser checks passed**, 100 each in Chromium and WebKit:

| Suite | Per engine | Evidence |
|---|---:|---|
| FAC-4 administration | 21 | GCO action/review, policy-unavailable and read errors, stale/denied/lost result canonical reconciliation, origin filter, all three Faculty states in Home/list/detail, keyboard cancel/focus and 320/1440px at 100/200% text |
| Actual backend FAC-4 flow | 8 | Actual sessions/CSRF, committed cross-College submission, lost response followed by actual GCO acknowledgment before exact 200 replay, own list/detail, foreign/other-role denial, explicit GCO acknowledgment/closure, safe closed projection and server origin filter |
| Existing FAC-3 | 35 | Form/uncertain-save/expiry/empty/loading/error/role safety, full 320/390/768/1024/1440px and 100/200% matrix |
| Existing FAC-1 | 11 | Faculty foundation, protected deep links, managed affiliation and administrator conflict flow |
| Existing Call Slip permissions | 25 | Existing GCO/Student access, lifecycle, dialogs, uncertain recovery, void and ownership behavior |

The actual-backend fixture creates a unique loopback-only disposable PostgreSQL database,
migrates and seeds synthetic identity/form/organization records, installs synthetic providers
only in that test process, and uses actual API transactions through the existing Next proxy.
The lost-response case first verifies 201 commit, explicitly records a real authorized GCO
receipt, drops the Faculty response, then verifies an identical original key/body retry returns
200 with the current Received by GCO projection. Neither submit nor administration repeats
automatically. No actual institutional, Student or external message is sent.

Both engines cover OS light/dark preferences and reduced motion while preserving the
intentional application light palette. Status announcements, labeled dialogs/checkboxes,
keyboard entry/cancel/focus and actual persisted timestamps are checked. Real screen-reader
and device UAT remain FAC-5 work. No human usability study is inferred from automation.

Validation found and corrected narrow enlarged-text wrapping in the new review. The shared
consequence dialog's confirmation/cancel buttons now stay within their container. No unrelated
behavior assertion was weakened. One initial Chromium Call Slip focus assertion failed during
parallel validation; the unchanged assertion passed on the full final rerun (25/25). Treat this
as observed intermittent focus timing, not proof of an inherited deterministic failure.

Passing case reports are committed in [browser-results.json](browser-results.json).
Representative screenshots, inspected after the final run:

- [GCO list with actual origin/state](screenshots/gco-list.png)
- [GCO acknowledged intake](screenshots/gco-received.png)
- [Closure review at 320px/200% text](screenshots/closure-review-320-200.png)
- [Faculty closed detail on phone](screenshots/faculty-closed-phone.png)
- [Faculty Home with closed state](screenshots/faculty-home-closed.png)

## Reproduction

From `be/`:

```sh
.venv/bin/pytest tests/test_referral_administration.py tests/test_referral_administration_concurrency.py tests/test_referral_administration_migration.py tests/test_guidance_followups.py tests/test_call_slips.py tests/test_canonical_baseline.py tests/test_audit.py --reuse-db -q
.venv/bin/pytest tests/test_faculty_referrals.py tests/test_faculty_referral_concurrency.py tests/test_faculty_referral_migration.py tests/test_openapi_contract.py tests/test_referrals.py --reuse-db -q
.venv/bin/python manage.py export_openapi --check --settings=tests.settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
```

Run pytest invocations sequentially against the shared test database. The first creation
run used `--create-db --reuse-db` to apply the additional schema. For actual browser proof,
start the owned isolated fixture in a separate terminal:

```sh
.venv/bin/python -m tests.faculty_portal_server /tmp/compass-fac4-session.json
```

From `fe/`, build/start against that fixture and run each command with Chromium and
`COMPASS_UI_BROWSER=webkit`:

```sh
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm test
COMPASS_API_BASE_URL=http://127.0.0.1:8033 pnpm build
pnpm start --hostname 127.0.0.1 --port 3107
node tests/referral-administration.browser.mjs
node tests/integration/faculty-referral-administration.live.mjs
node tests/faculty-referrals.browser.mjs
node tests/faculty-foundation.browser.mjs
node tests/call-slip-permissions.browser.mjs
```

Do not overwrite an existing fixture manifest. It is mode 0600 with synthetic session
cookies only. Stop the owned fixture afterward; its finally block removes its own database
and manifest. Generic mocked browser suites remain isolated from actual APIs/providers.

## Hosted and release limits

The PR records exact-head workflow dispatch links and actual status, because automatic
workflow triggers do not include integration PRs. Local targeted success does not establish
a complete hosted/backend/browser pass. No hosted completion is claimed while jobs run.

FAC-2/FAC-3 already document broad inherited CI failures: privacy-notice query budget,
Counseling joined-lock scope, session-revocation helper inventory, irreversible Organization
rollback rehearsal and unchanged browser/runtime/layout/copy suites. FAC-4 does not weaken
them. Any failure from this change must be corrected independently; unrelated known failures
remain release blockers until resolved and revalidated. See [FAC-5 handoff](handoff.md).
