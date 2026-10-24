# Validation

Exact starting integration commit: **`7f0c75e970f26cc832158f4609295f0dd40938c5`**. Date: 2026-10-24, Asia/Manila. Work is isolated on `feature/gm-or-1-receipt-identity-history`.

## Environment and boundaries

Used Python 3.13.12 / Django 6.1.1 / pytest 9.1.1 / psycopg 3.3.5 from the existing local dependency runtime. A clean test environment and dedicated loopback PostgreSQL 17.11/Redis on nondefault ports were created under `/tmp/gm-or-1/`; no deployment environment files or live database connections were used. Test settings generate ephemeral encryption keys. All imported payment/Student facts were synthetic.

Frontend dependencies were installed into this isolated worktree using `CI=true pnpm --dir fe install --frozen-lockfile`, reusing the local content store with no lockfile upgrade. An initial attempt to reuse a dependency symlink was refused by pnpm's dependency check; the symlink was removed and replaced with this isolated installation. No other worktree's dependencies were altered. Generated Orval clients remain ignored and are not hand-edited or committed.

## Development failures and fixes

- First new receipt test run: 35 passed / 1 failed. The F4 duplicate fixture created the same academic-year label twice; it now reuses the current year and creates the second Student's real Inventory/affiliation before request creation. No historical test expectations were tightened or weakened.
- Subsequent foundation/race run: 65 passed. The expanded migration/API/preservation run: 74 passed. These are overlapping focused runs, **not additive unique test counts**.
- Static checks found formatting/unused-variable issues in new source/tests; they were fixed without changing rules.
- The migration's SQL was kept readable/frozen within the additive file, with a guard against reversing nonempty receipt history.

## Final checks

The coherent regression command was:

```sh
python -m pytest tests/test_good_moral.py tests/test_good_moral_assisted.py \
  tests/test_good_moral_preparation.py tests/test_good_moral_receipts.py \
  tests/test_good_moral_receipt_migration.py tests/test_canonical_baseline.py \
  tests/test_openapi_contract.py tests/test_audit.py tests/test_accounts.py \
  tests/test_privacy_release_audit.py -q
```

It produced **322 passed / 1 failed in 165.56s**. The failure was a preexisting `test_accounts.py` hard-coded expectation of 85 capabilities, while the unchanged canonical policy defines 87. The identical test was run against a Git archive of untouched base `7f0c75e9…` and reproduced the same 87-versus-85 failure. The assertion now uses `len(CAPABILITY_CODES)`; the preceding exact capability-set and baseline grant assertions remain, and **no role/grant/capability definition changed**.

After that fix and an inventory-count consistency improvement (classifications/digest/count derive from the same streamed row snapshot), focused receipt/migration/account reruns passed **81 tests in 42.03s**. These include four additional tests proving new self/assisted F4/F6 requests remain receipt-free after synthetic activation and can acquire their first receipt normally. An additional focused test passed for transaction-error redaction in the synthetic import command (the batch stays fenced/resumable and private SQL detail is suppressed). A final database consistency check also rejects new mutation rows whose result revision or request timestamp does not match the corrected request; migration/replay/race-focused reruns passed 11 tests. Final collection identifies **329 distinct backend tests** in the command above; all have passing evidence across the coherent run and focused rerun. Overlapping reruns are not counted again.

| Check | Newly executed result |
| --- | --- |
| Backend CI selection tooling: `python -m pytest ../.github/scripts/test_backend_ci.py -q` | 38 passed, 19 subtests passed; reported separately from the 329 backend domain/contract tests |
| `python -m ruff format --check .` / `python -m ruff check .` from `be/` | Passed |
| `python manage.py check` | Passed |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py export_openapi --check` | Contract current |
| `pnpm api:generate` | Passed; generated clients ignored/uncommitted |
| `pnpm lint` / `pnpm typecheck` / `pnpm build` | Passed; optimized Next build completed |
| Four existing Good Moral frontend unit modules via Node test runner | 27 passed |
| New `good-moral-receipt-correction.browser.mjs` | 5/5 Chromium and 5/5 WebKit: dormant/active contracts, stale draft review, uncertain committed outcome without replay, safe duplicate conflict |
| Existing `good-moral-print.browser.mjs` | 22/22 Chromium and 22/22 WebKit, including F4/F6 at 320px/1440px, uncertain issuance, PDF failures, reprint and owned Student download |

Browser/API fixtures were fully synthetic and intercepted by the repository's local-only harness. Existing backend tests include real Chromium PDF output; new migration tests compare complete persisted issued fields, saved render context and exact HTML for both variants with missing/non-80 receipts. Headless browser print instrumentation is not proof of a native OS print dialog or physical output.

Canonical registry/graph/hash/constraint tests passed. New receipt tests are registered in the Good Moral backend CI group; browser suites are discovered by the existing recursive runner. Git whitespace/scope and final commit/PR checks are completed at handoff. Earlier GM-OR-0 results are not counted as newly executed proof.

No physical inspection, expected-fee enforcement, receipt-preparation/issuance blocker, new capability grant, real-data inventory/import, SSH, deployment, live migration/reset/backfill or automatic merge was performed. Dormant runtime compatibility and synthetic active behavior are separate test cases. Native print-dialog behavior, physical paper/signature/seal and institutional UAT are not claimed by automated tests.
