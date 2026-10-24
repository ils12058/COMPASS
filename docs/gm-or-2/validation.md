# Validation evidence

Date: 2026-10-24 Asia/Manila. Base verified again before handoff: `ef2ba91777ce75391876c36211b2cde83f02188f`. Branch `feature/gm-or-2-receipt-verification`, isolated managed worktree. Original checkout, staging, main and other worktrees were not edited.

## Environment

Python 3.13.12 / Django 6.1.1 / pytest 9.1.1 / psycopg 3.3.5 from the existing dependency runtime, dedicated loopback PostgreSQL 17.11 and Redis on nondefault ports under `/tmp/gm-or-2/`. Clean test-only environment with ephemeral encryption keys, no deployment environment files or live database. `manage.py migrate --noinput` exercised the complete empty local graph including 0003; test database creation and migration-executor tests exercised the finalized SQL. All data, policies and inspector grants are synthetic.

Isolated frontend dependencies: `CI=true pnpm --dir fe install --frozen-lockfile`, using the existing content store without lockfile upgrades. Optimized Next 16.3.4 build and loopback-only frontend server. Browser harness intercepts API requests with synthetic fixtures. Generated Orval clients remain ignored/uncommitted. Next build's generated `next-env.d.ts` path changes were restored to HEAD; final typecheck passed after restoration.

## Backend evidence and distinct counts

The broad command was:

```sh
python -m pytest tests/test_good_moral.py tests/test_good_moral_assisted.py \
  tests/test_good_moral_preparation.py tests/test_good_moral_receipts.py \
  tests/test_good_moral_receipt_migration.py tests/test_good_moral_verification.py \
  tests/test_good_moral_verification_concurrency.py \
  tests/test_good_moral_verification_migration.py tests/test_canonical_baseline.py \
  tests/test_openapi_contract.py tests/test_audit.py tests/test_accounts.py \
  tests/test_privacy_release_audit.py tests/test_notifications.py tests/test_feedback.py \
  -q --reuse-db
```

It completed **543 passed / 2 failed in 270.38s**, collecting 545 distinct tests at that point. Both failures were explicit contract snapshots still expecting 416 operations and the previous capability list. Their exact expected sets now include the new inspection operation and capability; strict uniqueness, approved tags and sensitive-field assertions remain intact.

After the active F4 actor/Student lock-order refinement and two new independent-connection lifecycle tests, a focused selection covering all verification/action/race tests, the six adapted GM-OR-1 lifecycle races and both failed snapshots passed **129 tests in 57.98s**. The expanded preparation/inspection payload contract test separately passed **1 test in 2.60s**. A final fail-closed fee check adds one missing-applicability-range case; **14 relevant positive/policy-change tests passed in 7.29s**. A further focused check of **11 tests passed in 6.23s**, ensuring approved expected fees remain visible on amount mismatch without enabling verification. Final broad-command collection is **548 distinct backend tests**, all with passing evidence across the broad run and focused checks. This is **not** a claim that a single latest 548-test run occurred. Repeated executions are not added to the unique count.

New verification modules comprise **124 distinct tests**: 99 domain/API/authorization/fee/guard tests, 23 multi-connection concurrency tests and two verification-migration tests. Existing Good Moral core/assisted/preparation, receipt identity/migration, accounts, Audit, notification, feedback, PDF/release and canonical/contract tests are counted once in the 548 total. CI selection tooling is separate: **38 tests and 19 subtests passed** (final 4.73s).

## Development failures and repairs

- Initial test collection referenced the wrong capability-grant constant; corrected to the owning canonical `ROLE_CAPABILITY_GRANTS` interface.
- New SQL request-provenance guard had a PL/pgSQL variable/table-alias collision. Distinct SQL aliases fixed it; a freshly recreated disposable test database exercised the corrected migration.
- An Audit privacy assertion searched for digits `80` anywhere, including random UUIDs. Replaced with exact allowed metadata keys and absence of receipt/amount keys/raw OR; no application privacy rule was weakened.
- Legacy future/negative anomalies are intentionally noncurrent in GM-OR-1. Eligibility now reports future-date incompleteness before the noncurrent anomaly blocker while retaining ownership/ambiguity refusal. Dormant/FENCED test intent construction now tolerates no ledger revision.
- Populated migration fixtures initially omitted required historical issuance metadata and then tried runtime models after removing new columns. Fixtures now issue valid synthetic historical records while DORMANT, use historical fields for comparisons, downgrade, upgrade and restore the latest graph. Focused migration rehearsal: **2 passed in 4.89s**.
- A privileged synthetic wrong-owner fixture had pending FK trigger events while re-enabling a temporarily disabled identity guard. It now drains deferred constraints first; all four identity-eligibility cases passed. This trigger manipulation exists only in isolated future-state tests, not runtime/release tools.
- The new stale-receipt browser assertion initially matched the app's route announcer as well as its error. The locator now targets the controlled receipt-change message. Both engines passed the focused case; product mutation behavior was already correct.

## Repository and frontend checks

| Check | Executed result |
| --- | --- |
| Ruff lint / format from `be/` | Passed; 836 Python files formatted |
| `compileall -q compass/good_moral` | Passed |
| Django system check | No issues |
| `makemigrations --check --dry-run` | No changes |
| `export_openapi` and `export_openapi --check` | Exported and current |
| Canonical registry/graph/baseline hashes/constraints | Passed in backend regression; historical migrations unchanged |
| `pnpm --dir fe api:generate` | Passed, ignored generated clients |
| Frontend lint, final typecheck, optimized build | Passed |
| Good Moral preparation/print/assisted/request-standardization unit modules | 27 distinct passed (22 plus five; no repeated count) |
| Issuance/print browser suite | 24 distinct per engine: 48 passing checks across Chromium/WebKit coherent plus focused reruns |
| Existing receipt-correction browser suite | 5 per engine: ten passing checks |
| Git whitespace and scope checks | Passed; no historical docs, baseline/0002 migration, generated client or dependency lockfile changes |

**58 distinct browser checks** across both engines. Print tests include F4/F6 at 320px/1440px, uncertain issuance, PDF retry, Student downloads, authorized GSS reprint, finalized PDF print instrumentation, active receipt tokens and stale receipt refresh without resubmission. The coherent expanded print runs each passed 23/24; each remaining locator-only failure passed its focused rerun. Do not count the earlier 22-check run again.

Backend core tests generate actual Chromium PDFs. Existing import tests compare saved issued facts/render contexts/exact HTML before and after source observation for both variants; new migration tests preserve duplicates, blanks/non-80 amounts and cancelled/issued provenance without fabricated inspections. No binary PDF identity, native OS print dialog, physical paper/signature/dry seal, actual receipt inspection, production load or manual accessibility/UAT is claimed.

## Hosted CI and activation limits

The owning backend-targeted, frontend-targeted and backend-full workflows select PR bases `staging` and `canon/compass-clean-baseline`, excluding `integration/ux15-modernization`. Automatic hosted runs are therefore not expected for this PR. Exact candidate SHA/check diagnostics and mergeability are reported in the PR handoff; no workflow filters, dispatch or deployment are changed to manufacture CI success.

DORMANT runtime remains compatible. ACTIVE without an approved provider fails closed. Test-injected policy versions/ranges/authority are explicitly fictional. Policy changes within a transaction, account revocation/deactivation lock orders, stale revisions, exact replay, operation races, Audit failure and database bypass attempts are exercised with committed-row assertions. General privileged direct writers and mixed-policy process rollouts still need controlled writer fencing; see the concurrency/release documents.

No deployment, SSH, live-data inspection, real-data migration/backfill, live ledger transition, inspector grant, institutional fee activation or automatic merge occurred. Test-owned local services are stopped at handoff. GM-OR-3 full workflow/accessibility UX and institution-approved GM-OR-4 release/UAT remain follow-ups.
