# FUP-1C + FUP-2A validation record

**Branch:** `integration/ux15-modernization`
**HEAD:** `1e3c34c7228b6e19d1b46f1ad7f737e17ff6bf64`
**Validation date:** 2026-11-05
**Scope:** FUP-1C and FUP-2A only
**Authority:** D-FUP-01 Option A, D-FUP-03 guidance-only copy and all D-FUP-07 wording are
**Provisional — pending GCO**. This record is engineering regression evidence, not UAT or
institutional acceptance.

## 1. Base confirmation

```bash
git rev-parse HEAD
git status --short
```

Result: `1e3c34c7228b6e19d1b46f1ad7f737e17ff6bf64`; only the pre-existing untracked
`outputs/paper-screenshots/` was present.

## 2. Commands and results

| Purpose | Exact command | Result |
|---|---|---|
| Targeted Follow-Up file | `cd be && .venv/bin/python -m pytest tests/test_guidance_followups.py -q` | **43 passed in 70.12s (0:01:10)** |
| Targeted Follow-Up + contract | `cd be && .venv/bin/python -m pytest tests/test_guidance_followups.py tests/test_openapi_contract.py -q` | **84 passed in 137.87s (0:02:17)** |
| Contract export | `DJANGO_SETTINGS_MODULE=tests.settings PYTHONPATH=be be/.venv/bin/python be/manage.py export_openapi` | `Exported OpenAPI contract: /Users/reynantlntno/Projects/COMPASS/contracts/openapi.json` |
| Contract check | `DJANGO_SETTINGS_MODULE=tests.settings PYTHONPATH=be be/.venv/bin/python be/manage.py export_openapi --check` | `OpenAPI contract is current: /Users/reynantlntno/Projects/COMPASS/contracts/openapi.json` |
| Client regeneration | `pnpm --dir fe api:generate` | Orval v8.29.0 completed successfully |
| Diff scope | `git diff --stat -- contracts/openapi.json fe/src/lib/api/generated` | `contracts/openapi.json \| 7 ++++++-` (6 insertions, 1 deletion) |
| Follow-Up browser (Chromium) | `cd fe && node tests/guidance-followups.browser.mjs` | **23/23 browser checks passed** |
| Working tree | `git status --short` | see §5 |

### 2.1 Backend counts

The Follow-Up file increased from 39 to 43 tests: the four FUP-1C tests were added. The combined run
contains 43 Follow-Up tests plus 41 contract tests.

The four new tests passed by name within both runs:

- `test_list_projects_source_unavailable_for_voided_referral`
- `test_list_source_unavailable_false_for_readable_and_source_free`
- `test_list_and_detail_agree_on_source_unavailable`
- `test_source_unavailable_projection_does_not_leak_source_identity`

### 2.2 Browser checks

All 23 checks passed, including the two new checks:

- `Follow-Up list marks only an unavailable related record without exposing source identity`
- `Follow-Up report explains source availability without a per-task projection`

The completed-task assertion was extended with the completion paragraph, and the Help check was
extended with the `Completion and further action` section.

Artifacts from the run:
`/var/folders/tc/9pcbpb_j057_gf64sf1pfgn00000gn/T/compass-guidance-followups`.

## 3. Contract and generated client

The tracked contract diff is limited to the new boolean:

- `source_unavailable` added to `FollowUpSummary.properties` and `FollowUpSummary.required`;
- the field moved into the inherited position in `FollowUpDetail.required`; it remains present in the
  detail schema.

Both generated models were verified on disk after Orval:

```text
fe/src/lib/api/generated/model/followUpSummary.ts:22:  source_unavailable: boolean;
fe/src/lib/api/generated/model/followUpDetail.ts:33:  source_unavailable: boolean;
```

`fe/src/lib/api/generated/` is gitignored (`.gitignore:23`), so the generated client produces no
tracked diff even though it was regenerated. No unrelated contract drift and no unrelated generated
drift were observed. No generated file was hand-edited.

## 4. Temporary server disclosure

The browser harness requires a local Next server at `localhost:3107`. A temporary development server
was started only for the required browser command:

```text
./node_modules/.bin/next dev -p 3107
```

Readiness was confirmed with an HTTP 200 from `http://localhost:3107/portal/follow-ups`. The server was
stopped after the browser run. No manual UI session, live backend, dev database, seed or institutional
environment was used. This does not constitute dev-server feature verification or UAT.

## 5. Repository state

`git status --short` after all changes:

```text
 M be/compass/guidance_followups/api.py
 M be/compass/guidance_followups/policy.py
 M be/tests/test_guidance_followups.py
 M contracts/openapi.json
 M fe/src/features/guidance-followups/followups-detail.tsx
 M fe/src/features/guidance-followups/followups-help.tsx
 M fe/src/features/guidance-followups/followups-list.tsx
 M fe/src/features/guidance-followups/followups-report.tsx
 M fe/tests/guidance-followups.browser.mjs
?? docs/fup-1c-2a/
?? outputs/paper-screenshots/
```

- Only the allowed handwritten files were modified.
- `contracts/openapi.json` is the only tracked generated file changed, through the export command.
- `fe/src/lib/api/generated/**` was regenerated but is gitignored.
- `outputs/paper-screenshots/` pre-existed and was left untouched.
- Changes remain uncommitted. No commit, merge, push, rebase, stash or reset was run.

## 6. First-run notes and audit divergence

- The first authoring run of `tests/test_guidance_followups.py` reported **3 failed, 40 passed**:
  three new synthetic Referral fingerprints used non-hex letters (`g`, `h`, `i`). The fingerprints
  were corrected to `7`, `8`, `9`, and the final run passed 43/43. This was a test-fixture authoring
  error, not a production behavior failure.
- No audit divergence was found. The implementation matches the existing source-visibility rule.
- One projection consistency change is intentional: the minimized creation receipt now computes the
  real source visibility instead of returning `true` for every source-bearing task. This is not an
  authorization change; it keeps the new summary field truthful at every `_summary` call site.

## 7. Evidence limits

- Only the Follow-Up test file and the contract test file were executed on the backend; no full-suite
  or shard result is claimed.
- The browser suite uses synthetic accounts and HTTP fixtures. It does not exercise a live backend,
  database, notification provider, storage provider or institutional record.
- The detailed UI behavior was exercised only through the Chromium harness. WebKit was not run.
- No performance, accessibility-audit, load, security-scan or penetration result is claimed.
- No GCO review, UAT sign-off, privacy review or records acceptance is claimed.
- The backend database engine used by the targeted pytest run was not independently recorded in this
  slice.

## 8. Not run

- Full backend pytest suite and shards.
- `pnpm test` (frontend unit suite). It was not needed because no pure copy/access helper was
  introduced and `fe/tests/guidance-followups.test.mjs` was not changed.
- Full browser regression matrix (`pnpm test:ui`) and every other browser suite.
- WebKit matrix (`COMPASS_UI_BROWSER=webkit`).
- `pnpm lint`.
- `pnpm typecheck`.
- `pnpm build`.
- Migrations, migration checks, seed and database queries.
- Manual dev-server feature verification, staging and production.
- FUP-1D, FUP-2B, FUP-2C and all FUP-3 work.
- Full regression is deferred to FUP-4.
