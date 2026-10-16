# CANON-1C — Regression report

Base: `origin/staging` `3ae47817923849eef6cd3fd1ad15e0a43bd79568`. All local runs used disposable
containers; no shared or live service was used. CI results are cited by run ID.

## WebKit Guidance Messages regression (Deliverable K)

Failing case from CANON-1B run [38895355439](https://github.com/ils12058/COMPASS/actions/runs/38895355439),
job `browser webkit 4/4`: `guidance-messages-contextual` → "Appointment, Counseling, E-Counseling
and the full workspace share one thread". The thread-sharing assertions had passed; the
`pageerror` assertion failed after `page.goto` between surfaces.

**Root cause.** The CI fingerprints all pointed at `04q6897mgfp2r.js:1:18682`, which in the same
synthetic build is the `fetch(...)` call in Next's RSC fetch helper; their first source was a
portal route (sidebar links and `/portal/messages/<thread>`). Reproduced locally on the production
synthetic build (2 of 3 runs failed). The raw message, captured with a temporary local probe, was
WebKit's `Fetch API cannot load …?_rsc=… due to access control checks.`: the router's in-flight
RSC link prefetches cancelled by the test's own document navigation, which Playwright's WebKit
backend reports as a page error. No application exception was thrown.

**Fix** ([#249](https://github.com/ils12058/COMPASS/pull/249) → `staging`; cherry-picked as
`703909b8` on the CANON-1C branch): the harness tracks each page's in-flight fetch/XHR requests and
`navigate(page, path)` waits until they have been quiet for 500 ms (measured from the call, so a
just-shown link's prefetch can start), bounded at 12 s (a page that never settles fails the
check). The failing check uses it. The `pageerror` assertion and every thread-sharing assertion
are unchanged. Test-only change; no application, contract or dependency change.

| Validation step | Result |
| --- | --- |
| 1. Reproduce the single WebKit case | Failed 2/3 at baseline |
| 2. Inspect fingerprints and request evidence | RSC prefetch fetches cancelled by document navigation (see above) |
| 3–4. Focused fix; rerun the same WebKit case | 10/10 pass |
| Negative probe: inject a `throw` on the Counseling page in the same flow | Still fails with a page error |
| 5. Containing suite, WebKit | 29/29 |
| 6. Chromium counterpart | 29/29 |
| 7. Affected shard `webkit 4/4` | 7/7 suites |
| Harness unit tests (`browser-registration`, `browser-test-runtime`, `browser-diagnostics`) | 8/8 |
| 8. Full browser matrix (#249 CI, run [38902560551](https://github.com/ils12058/COMPASS/actions/runs/38902560551), head `27336d87`) | **success** — all 8 browser jobs (4 shards × Chromium/WebKit), browser build, unit tests, lint, typecheck, build |

No browser suite was disabled or made optional, and no error was suppressed.

## Backend

Full local regression of the CANON-1C backend at `c50b53e4` (later commits changed only
documentation and the deploy workflow), using the CI shard planner (`backend_ci.py run-shard`,
3 shards, separate test databases and Redis DBs):

| Shard | Result | Duration |
| --- | --- | --- |
| 1/3 | 1,329 passed | 16 m 41 s |
| 2/3 | 1,512 passed | 19 m 42 s |
| 3/3 | 1,611 passed | 16 m 28 s |
| **Total** | **4,452 passed, 0 failed, 0 errors** | |

Warnings: 3 pre-existing Django Ninja tuple-response deprecations, 1 `override_settings(DATABASES)`
warning, and one session-teardown warning in shard 1/3 ("test database is being accessed by 2 other
sessions", reported on that shard's last test). The teardown happened after every test had passed;
it is not attributable to a single test from this output. `tests/test_staging_seed.py` run alone
passes 38/38 with no teardown warning.

Other backend checks at the final revision: `ruff format --check` (733 files) and `ruff check`
clean; `manage.py check` clean; `makemigrations --check --dry-run` no changes; CI selector
`verify` (160 files, each exactly once across 6 shards) and its self-tests pass.

Test inventory changes versus base (test functions, before parametrization): 554 → 454 in the
changed files (129 removed, 29 module-level functions added). Removed: 12 whole-file
historical-migration tests, 62 migration tests in mixed files, 21 tombstone/fallback/ledger tests
(`test_operational_retention.py`), 5 retired-executor or hold tests in media/realtime/Graduate
Tracer suites, and 29 old demo-seed tests. Added: `test_canonical_baseline.py` (5),
`test_disposition_decommission.py` (13; absence plus preserved fences) and `test_staging_seed.py`
(11 functions and 11 `TestCase` methods; 38 tests with parametrization). Retirement was limited to tests that
replay deleted migrations, exercise removed code or seed the retired dataset; runtime behavior in
the same files is unchanged and passing.

## Frontend

No application, contract (OpenAPI) or generated-client change. The only frontend change is the
browser-test harness above, covered by #249's CI.

## Remaining failures

None observed in the local full backend run or in #249's browser matrix. The reset-only PR's own
CI (targeted and full backend, frontend targeted) is the record for its exact head; CANON-1D owns
the final complete matrix on the reviewed reset-only revision.
