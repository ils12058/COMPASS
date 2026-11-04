# SAR-5 validation — real commands and results

All commands were run on 2026-11-04 on the local working tree at base `c65b66a8` plus the
uncommitted Workstream A changes. No staging or production contact occurred.

## 1. Focused regression (run first)

From `be/`:

```bash
uv run pytest -q tests/test_organization.py tests/test_appointments.py \
  tests/test_guidance_messages.py tests/test_student_profiling_pdf.py \
  tests/test_student_profiling_report_coverage.py tests/test_student_profiling_reports.py \
  tests/test_student_profiling_xlsx.py
```

Result:

```text
245 passed in 124.67s (0:02:04)
```

## 2. B1 — static and contract

| # | Command (directory) | Result |
|---|---|---|
| 1 | `python3 .github/scripts/backend_ci.py verify` (repository root) | `OK: 212 test files are bundled and each runs exactly once across 6 full-regression shards.` |
| 2 | `uv lock --check` (`be/`) | `Resolved 72 packages in 3ms` |
| 3 | `uv run ruff format --check .` (`be/`) | `888 files already formatted` |
| 4 | `uv run ruff check .` (`be/`) | `All checks passed!` |
| 5 | `uv run python -m compileall -q compass tests` (`be/`) | no output (exit 0) |
| 6 | `uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` (`be/`) | `No changes detected` |
| 7 | `uv run python manage.py check --settings=tests.settings` (`be/`) | `System check identified no issues (0 silenced).` |
| 8 | `uv run python manage.py export_openapi --check --settings=tests.settings` (`be/`) | `OpenAPI contract is current: /Users/reynantlntno/Projects/COMPASS/contracts/openapi.json` |

No migration is added by this slice.

## 3. B2 — full backend suite, six shards

Shard count confirmation from the repository root:

```bash
python3 .github/scripts/backend_ci.py plan
```

Output: six shards, 212 test files total, each labelled `about 22.2 min`:

```text
Shard 1/6: 35 items, about 22.2 min
Shard 2/6: 36 items, about 22.2 min
Shard 3/6: 36 items, about 22.2 min
Shard 4/6: 37 items, about 22.2 min
Shard 5/6: 36 items, about 22.2 min
Shard 6/6: 36 items, about 22.2 min
```

Each shard was run sequentially from `be/` with:

```bash
uv run python ../.github/scripts/backend_ci.py run-shard --index N --total 6
```

**Discrepancy with the slice text:** `run-shard --index` is documented in the script as a
**zero-based** index (`p_run.add_argument("--index", ..., help="Zero-based shard index.")`), so the
literal `--index 1..6` sequence in the slice text would run shard 2 first and then fail on
`--index 6`. The actual commands used `--index 0` through `--index 5`, which the runner labels
`Shard 1/6` through `Shard 6/6`. Every shard ran exactly once; the table uses the runner's labels.

| Shard | Result |
|---|---|
| 1/6 | `1126 passed, 2 skipped, 5 warnings in 584.42s (0:09:44)` |
| 2/6 | `1077 passed, 1 skipped in 493.92s (0:08:13)` |
| 3/6 | `824 passed, 1 warning in 553.21s (0:09:13)` |
| 4/6 | `958 passed, 5 warnings in 600.28s (0:10:00)` |
| 5/6 | `1466 passed, 1 skipped in 671.80s (0:11:11)` |
| 6/6 | `992 passed, 4 warnings in 502.42s (0:08:22)` |

Totals across the six shards: **6,443 passed, 0 failed, 0 errors, 4 skipped**, aggregate pytest
time **3,406.05s (0:56:46)**. The four skips are all explicit opt-ins:
`test_good_moral_authenticated_integration.py:449` (2, loopback Next build/live-server proxy),
`test_good_moral_recovery_rehearsal.py:44` (1, disposable PostgreSQL restore), and
`test_fixed_date_slots.py:917` (1, loopback Next build/live-server proxy). No teardown warning about
`test_compass_test` was emitted this run.

## 4. B3 — frontend unit and build

From `fe/`:

| Command | Result |
|---|---|
| `pnpm api:generate` | Orval v8.29.0; `🎉 compass - Your OpenAPI spec has been converted into ready to use orval!` |
| `pnpm lint` | `eslint .` completed with no findings (exit 0) |
| `pnpm typecheck` | `tsc --noEmit` completed with no findings (exit 0) |
| `pnpm test` | `tests 1033`, `pass 1033`, `fail 0`, `cancelled 0`, `skipped 0`, `todo 0`, duration `42304.284542ms` |
| `pnpm build` | Next.js 16.3.4 (Turbopack); compiled successfully; TypeScript finished; 99/99 static pages generated |

Orval regenerated `fe/src/lib/api/generated/` with no contract-visible change; that directory is
gitignored. `next build` rewrote the committed, Next-generated `fe/next-env.d.ts` reference from
`.next/dev/types` to `.next/types`; this artifact was restored to the committed content before the
final status check and is not a SAR change.

## 5. B4 — full browser inventory, both engines

Build and servers:

```bash
cd fe
NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1 pnpm build
nohup node tests/support/ssr-api-fallback.mjs > /tmp/sar5-ssr.log 2>&1 &
nohup pnpm start --port 3107 > /tmp/sar5-next.log 2>&1 &
```

Readiness: `curl --max-time 5 -fsS -o /dev/null http://localhost:3107/login` succeeded; SSR health
`curl -fsS http://127.0.0.1:8000/__health` returned `ok`. The inventory contains exactly 84
`*.browser.mjs` suites (`node tests/run-browser-regressions.mjs --list | wc -l` → `84`).

Run:

```bash
COMPASS_UI_BASE_URL=http://localhost:3107 COMPASS_UI_ARTIFACTS=/tmp/sar5-browser pnpm test:ui
```

| Engine | Result |
|---|---|
| chromium | `82/84 suites passed.` — 1,683/1,694 checks |
| webkit | `81/84 suites passed.` — 1,681/1,693 checks |

Across both engines: **168 suite runs, 163 passed, 3,364/3,387 checks passed**. `pnpm test:ui` exited
non-zero because suites failed; the counts above come from each suite's `results.json` and the
runner's final lines.

Failing suites, verbatim runner output:

| Engine | Suite | Checks | Failing checks | Message |
|---|---|---|---|---|
| chromium | `public-illustrations.browser.mjs` | 11/13 | `landing-desktop`, `landing-tablet` | `page.waitForFunction: Timeout 12000ms exceeded.` |
| chromium | `simplify-2c-illustrations.browser.mjs` | 28/37 | `student-320/390/1024/1440`, `gss-320/390/1024/1440`, `home-delayed-artwork` | `page.waitForFunction: Timeout 12000ms exceeded.` |
| webkit | `public-illustrations.browser.mjs` | 11/13 | `landing-desktop`, `landing-tablet` | `page.waitForFunction: Timeout 12000ms exceeded.` |
| webkit | `simplify-2c-illustrations.browser.mjs` | 28/37 | same checks as chromium | `page.waitForFunction: Timeout 12000ms exceeded.` |
| webkit | `ux15-feedback-csm.browser.mjs` | 26/27 | `customer Browser Back asks before discarding the response` | `The input did not match the regular expression /Discard your unfinished Customer Feedback response/. Input:` |

No first traceback exists beyond these Playwright messages. The illustration failures come from the
explicit image-decode `page.waitForFunction` in those suites; the WebKit feedback failure is the
`assert.match` on a dialog captured only 100 ms after `window.history.back()`.
The other 163 suite runs include the SAR-3/4 provisioning suites
(`student-placement-provisioning.browser.mjs`, `faculty-foundation.browser.mjs`), which passed on
both engines.

### 5.1 Diagnostic evidence for the illustration failures

These diagnostics were run after the inventory and are **not** a substitute for it. No test file was
edited.

1. **The image element exists and is visible but never resolves a source.** A harness-based
   diagnostic on Student, GSS and Counselor home (1024×1000) reported the same component in all
   three: one `img` with `alt=""`, `aria-hidden="true"`, `tabIndex=-1`, `loading="lazy"`,
   `width=512 height=512`. On Counselor home the image completed
   (`naturalWidth=80`, `currentSrc=/_next/image?...guidance-messages-3d.png&w=96&q=75`). On Student
   and GSS home the image stayed `complete=false`, `naturalWidth=0`, `currentSrc=""` even after
   `scrollIntoViewIfNeeded()` and a 4-second wait.
2. **The browser only requests the `w=96` variant and that request never completes.** For
   `appointment-calendar-3d`, the `<img>` carries a full `srcset` and a `src` ending in
   `w=3840&q=75`, but the browser selects and requests
   `/_next/image?url=%2Fillustrations%2Fappointment-calendar-3d.png&w=96&q=75`. The request event
   fired; no response event followed; `img.decode()` did not settle within 5 seconds.
3. **The local Next image optimizer hangs for specific (asset, width) pairs.** Direct probes of the
   same URLs:

   ```text
   Accept: */*                        appointment-calendar-3d w=96  -> 200 image/png  0.05s
   Accept: image/webp,*/*             appointment-calendar-3d w=96  -> no response   >8s (one probe >60s)
   Accept: image/avif                 appointment-calendar-3d w=96  -> 200 image/png  0.002s
   Accept: image/webp,*/*             appointment-calendar-3d w=256 -> 200 0.017s
   Accept: image/webp,*/*             appointment-calendar-3d w=384 -> 200 0.022s
   Accept: image/webp,*/*             gco-characters        w=384 -> no response   >8s (one probe >60s)
   Accept: image/webp,*/*             gco-characters        w=256 -> 200 0.001s
   ```

   With the browser Accept header at `w=96`, 13 of the 14 illustration PNGs responded quickly;
   only `appointment-calendar-3d.png` hung. `gco-characters.png` hangs at the landing hero's
   `w=384`. The landing hero uses `sizes="...304px"` (desktop/tablet → `w=384`) while the phone
   layouts use 240px (`w=256`), which matches exactly the desktop/tablet-only landing failures. The
   home shortcut images use `sizes="80px"` (`w=96`), which matches the Student/GSS home failures;
   Counselor home's image is the same component at the same width but a different asset, and it
   loads.

   The PNGs themselves are ordinary 8-bit RGBA, non-interlaced files (`file`), unchanged since the
   illustration slice. SAR-5 changes no frontend file; therefore this is a pre-existing local
   Next.js 16.3.4 (Turbopack) image-optimizer/WebP-encoding defect for these asset/width pairs, not
   a Workstream A or SAR-domain defect. It was recorded, not patched.

### 5.2 Diagnostic evidence for the webkit feedback failure

`ux15-feedback-csm.browser.mjs` waits 100 ms after `window.history.back()` before asserting that a
discard dialog appeared. Chromium passed 27/27 in the inventory. WebKit failed only that check.
Re-running the single check on WebKit twice (`COMPASS_UI_CHECK='^customer Browser Back'`) produced
`1/1 browser checks passed` both times. This is a WebKit timing flake in a committed suite outside
the SAR domain; it was recorded, not patched, and it does not replace the failing inventory result.

All build and browser servers were stopped after the inventory.

## 6. B5 — reset-only baseline, seed and verification

A disposable local database `compass_sar5_validation` was created, used, and dropped afterwards.
No shared database was touched and `issue-credentials` was never run.

Environment notes:

- `uv run` does not load `be/.env` here, so every command used `uv run --env-file .env`.
- `POSTGRES_HOST=localhost` and `POSTGRES_DB=compass_sar5_validation` overrode the compose
  service/host values in `.env`.
- The local `.env` predates the required `STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS` setting; settings
  failed at import with `ValueError: STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS is required`. A
  disposable local Fernet key was generated for this run (kept in `/tmp`, never committed).
- The `.env` Redis URLs target the compose host `redis`. They were overridden to
  `redis://127.0.0.1:6379/{0..3}` (the local Redis accepts unauthenticated loopback). Without this,
  the seed attempted mail enqueue and logged `notification_email_enqueue_failed` plus
  `Connection to Redis lost: Retry (20/20)`; that first attempt was abandoned, the database was
  dropped and recreated, and the recorded run below started from an empty database.

Recorded run (script `/tmp/sar5-b5.sh`, log `/tmp/sar5-b5.log`):

```bash
cd be
export POSTGRES_HOST=localhost POSTGRES_DB=compass_sar5_validation
export STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS="$(cat /tmp/sar5_sss_key)"
export REDIS_URL=redis://127.0.0.1:6379/0 REDIS_CACHE_URL=redis://127.0.0.1:6379/1
export REDIS_RATE_LIMIT_URL=redis://127.0.0.1:6379/2 REDIS_IDEMPOTENCY_URL=redis://127.0.0.1:6379/3
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0 CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
export APP_ENV=local-staging STAGING_SEED_ENABLED=true

uv run --env-file .env python manage.py migrate --noinput
uv run --env-file .env python manage.py sync_identity_policy
uv run --env-file .env python manage.py sync_canonical_services
uv run --env-file .env python manage.py sync_institutional_forms
uv run --env-file .env python manage.py initialize_organization_catalog --seed
uv run --env-file .env python manage.py seed_staging_dataset seed
uv run --env-file .env python manage.py seed_staging_dataset verify
```

Results — every stage exited 0:

| Stage | Result |
|---|---|
| `migrate --noinput` | all migrations applied, no error |
| `sync_identity_policy` | roles created=6; designations created=2; capabilities created=91; role grants created=101; designation grants created=20 |
| `sync_canonical_services` | `Canonical Counseling Service created` |
| `sync_institutional_forms` | families created=8; revisions created=13 activated=8 |
| `initialize_organization_catalog --seed` | `Catalog SEEDED; changed=True; baseline=ucn-2026-09-27-v1` |
| `seed_staging_dataset seed` | `Manifest: 116 accounts, 102 Students`; `624 item(s) created, 100 already present and reused`; Student placements created=86, Student academic periods created=111, Student graduations created=12; `No credential was set.` |
| `seed_staging_dataset verify` | `Verification PASSED.` |

Verification detail: Schema readiness 5, Canonical configuration 21, Account readiness 1,112,
Organization routing 12, Scenario initial states 122, Workflow integrity 40, Privacy and security
149, External side effects 5 — **1,466 passed, 0 failed, 0 warnings**. The synthetic dataset needed
no object-storage upload; no external provider was contacted. The database was dropped after the
run.

## 7. B6 — zero-reference checks

From the repository root:

| Command | Result |
|---|---|
| `rg -n "StudentAffiliation" be/compass` | only `organization/migrations/0001_canonical_baseline.py:95` and `organization/migrations/0005_delete_studentaffiliation.py:14` |
| `rg -n "NO_AFFILIATION\|Guidance affiliation\|Guidance College affiliation" be/compass fe/src` | no matches |
| `rg -n "program_code" be/compass/account_management fe/src/features/accounts` | only `fe/src/features/accounts/import/import-accounts.tsx:178` — the line saying it is not supported |
| `rg -n "StudentAcademicProfile\.objects\.(create\|update\|delete\|bulk_create\|bulk_update\|get_or_create\|update_or_create)" be/compass` | no matches |
| `git diff --check` | no output (exit 0) |
| `git status --short` | recorded in §8 |

These checks were re-run against the final working tree after B4/B5 cleanup with identical results.
The only `program_code` match is the frontend sentence stating it is not supported; the only
`StudentAffiliation` matches are the historical migration files that created and deleted the old
model.

## 8. Repository state, discrepancies, residual risks and not-run list

### 8.1 Repository state

Branch `integration/ux15-modernization`, base `c65b66a8`. After validation:

- `fe/next-env.d.ts` was restored to its committed content (the production build had rewritten its
  generated type reference).
- The local Next/SSR servers used for B4 were stopped.
- The disposable database `compass_sar5_validation` was dropped.
- No commit, merge, push, PR, deployment, staging contact or external-provider contact occurred.

Final `git status --short`:

```text
 M be/compass/organization/services.py
 M be/compass/reports/pdf.py
 M be/compass/reports/services.py
 M be/tests/test_organization.py
 M be/tests/test_student_profiling_pdf.py
 M be/tests/test_student_profiling_report_coverage.py
?? docs/sar-5/
```

### 8.2 Discrepancy with `docs/sar-3-4/validation.md`

- That document's "Explicitly not run" section states the full backend pytest suite and the full
  browser inventory (`pnpm test:ui`) were not run. SAR-5 ran both: 6,443 backend tests passed with
  4 explicit skips, and 168 browser suite runs completed with 163 passing.
- Its targeted browser evidence (4/4 `student-placement-provisioning`, 11/11
  `faculty-foundation`, both engines) is included in this inventory and passes, so the earlier
  claims are not contradicted.
- Its 212-file / six-shard claim matches B1 `backend_ci.py verify` and B2 `plan`; no discrepancy.
- The slice text's literal `--index 1..6` differs from the zero-based runner (`--index 0..5`); see
  §3. This is a documentation discrepancy in the task text, not a test-count difference.

### 8.3 Residual risks

- **Illustration rendering in this local build.** The Next 16.3.4 image optimizer does not complete
  WebP encoding for `appointment-calendar-3d.png` at `w=96` and `gco-characters.png` at `w=384`.
  Under a browser, the landing hero at ≥1024px and the Student/GSS home shortcut artwork
  consequently never render. The assets and frontend code predate this slice and are unchanged, but
  the user-visible effect is real for this build and needs a separate Next/asset investigation.
- **WebKit feedback timing.** The Browser Back discard check failed once under full-suite load and
  passed twice in isolation; it remains a committed-suite flake.
- **Synthetic browser fixtures.** The 84-suite inventory proves UI behavior against synthetic API
  responses, not authenticated backend integration.
- **Disposable B5 configuration.** The reset/seed run used a generated local keyring and loopback
  Redis, not a shared-environment configuration; `issue-credentials` was deliberately not run.
- **Backend suite scope.** The six shards use `tests.settings` and the `test_compass_test` database,
  consistent with CI; no staging database was used.
- **Four explicit skips** remain in the backend suite (loopback Next build/live-server proxies and a
  disposable PostgreSQL restore), by design.

### 8.4 Explicitly not run

- `seed_staging_dataset issue-credentials` — deliberately not run; no credential file was created.
- Staging or production deployment, shared-environment migration, and any external provider
  (email, SMS, Daily/E-Counseling, push, webhook) — none occurred.
- The three failing browser suites were not re-run as full suites after diagnosis, and no test,
  lint, type or build rule was changed to obtain a green result.
- The literal `--index 1..6` invocation from the slice text — replaced by the runner's zero-based
  `--index 0..5`.
- The literal `uv run python manage.py ...` commands without `--env-file` — those fail settings
  import because uv does not load `be/.env`; the actual invocations are recorded in §6.
- No UI, model, migration, capability, endpoint or API-field change was attempted or validated
  beyond the two record-residue renames and wording change in Workstream A.
