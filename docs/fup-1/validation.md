> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-1 validation record

**Branch:** `integration/ux15-modernization`
**HEAD:** `4614b228482336c100ec5363871c4303e013cedd`
**Validation date:** 2026-11-05
**Scope:** FUP-1A and FUP-1B only
**Authority:** D-FUP-01 Option A and all copy are **Provisional — pending GCO**. This record is
engineering regression evidence, not UAT or institutional acceptance.

## 1. Commands and results

| Purpose | Exact command | Result |
|---|---|---|
| Confirm base | `git rev-parse HEAD` | `4614b228482336c100ec5363871c4303e013cedd` |
| Targeted backend | `cd be && .venv/bin/python -m pytest tests/test_guidance_followups.py -q` | **39 passed in 62.44s (0:01:02)** |
| Follow-Up browser (Chromium) | `cd fe && node tests/guidance-followups.browser.mjs` | **21/21 browser checks passed** |
| Contract drift | `git diff --exit-code -- contracts/openapi.json fe/src/lib/api/generated` | empty diff (exit 0) |
| Working tree | `git status --short` | see §4 |

The backend result includes the six new FUP-1A tests. The browser result includes the two new
source-unavailable checks and the extended Help check.

All 21 browser check names passed, including:

- `An unavailable related record is explained without a broken link and the task stays actionable`
- `An unavailable linked source shows a generic context message without count, task link or create link`
- `Follow-Up Help is supplementary and keyboard accessible` (now also asserts the new help section)

Artifacts from the run: `/var/folders/tc/9pcbpb_j057_gf64sf1pfgn00000gn/T/compass-guidance-followups`.

## 2. Temporary server disclosure

The browser harness requires a local Next server at `localhost:3107`. A temporary development server
was started only for the required browser command:

```text
./node_modules/.bin/next dev -p 3107
```

Readiness was confirmed with an HTTP 200 from `http://localhost:3107/portal/follow-ups`. The server was
stopped after the browser run. No manual UI session, backend server, dev database, seed or institutional
environment was used. This does not constitute dev-server feature verification or UAT.

## 3. Evidence limits

- Only `tests/test_guidance_followups.py` was executed on the backend; no full-suite or shard result is
  claimed.
- The browser suite uses synthetic accounts and HTTP fixtures. It does not exercise a live backend,
  database, notification provider, storage provider or institutional record.
- The detailed UI behavior was exercised only through the required Chromium harness. WebKit was not
  run.
- No performance, accessibility-audit, load, security-scan or penetration result is claimed.
- No GCO review, UAT sign-off, privacy review or records acceptance is claimed.
- The backend database engine used by the targeted pytest run was not independently recorded in this
  slice.

## 4. Repository state

`git status --short` after all changes:

```text
 M be/tests/test_guidance_followups.py
 M fe/src/features/guidance-followups/followups-context.tsx
 M fe/src/features/guidance-followups/followups-detail.tsx
 M fe/src/features/guidance-followups/followups-help.tsx
 M fe/tests/guidance-followups.browser.mjs
?? outputs/paper-screenshots/
```

- Only the five allowed files were modified.
- `docs/fup-1/` is newly created and untracked.
- `outputs/paper-screenshots/` pre-existed and was left untouched.
- No other file was edited, including `models.py`, `services.py`, `policy.py`, `api.py`, migrations,
  notifications, OpenAPI, generated client, seeds or package files.
- Changes remain uncommitted. No commit, merge, push, rebase, stash or reset was run.

## 5. Audit divergence

None. All six characterization tests passed against unchanged production code, and the browser checks
confirmed the existing source-unavailable state. No production code was changed to match the audit.

## 6. Not run

- Full backend pytest suite and shards.
- `pnpm test` (frontend unit suite). It was not needed because no shared copy helper was introduced and
  `fe/tests/guidance-followups.test.mjs` was not changed.
- Full browser regression matrix (`pnpm test:ui`) and every other browser suite.
- WebKit matrix (`COMPASS_UI_BROWSER=webkit`).
- `pnpm lint`.
- `pnpm typecheck`.
- `pnpm build`.
- OpenAPI export.
- Orval/generated-client regeneration.
- Migrations, migration checks, seed and database queries.
- Manual dev-server feature verification, staging and production.
- FUP-1C, FUP-1D, FUP-2 and all FUP-3 work.
- Full regression is deferred to FUP-4.
