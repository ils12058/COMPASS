# CENC-4 validation

Targeted + static only, exactly as the slice specifies. Full suites, the browser gate and UAT are
CENC-5. All commands were run on 2026-11-06 from the repository root, `be/` or `fe/` as noted.

## 1. Start-state gate (verbatim)

```
$ git log --oneline -1
494a7e2a Add CENC-3 E-Counseling Finish counseling and record parity
$ git branch --show-current
integration/ux15-modernization
$ git status --short
?? "Claude outputs/"
?? outputs/paper-screenshots/
$ ls docs
cenc-0 cenc-1 cenc-2 cenc-3 cont-0 cont-1a cont-1b cont-2a cont-2b cont-3 cont-4 evidence fac-1 fac-2
fac-3 fac-4 fac-5 fup-0 fup-1 fup-1c-2a fup-2b-3a gm-or-0 gm-or-1 gm-or-2 gm-or-3 gm-or-4 handoffs
notif-01 notif-02 notif-03 notif-04 ops-1a org-0 org-1 org-2 org-3 org-4 sar-0 sar-1 sar-2a sar-2b-2c
sar-3-4 sar-5 sar-6 sar-7 simplify-0 simplify-2a simplify-2b simplify-2c simplify-3a simplify-3b
simplify-3b-auth simplify-3b-pagination simplify-3b-public-shell simplify-3b-typography
simplify-3c-booking svc-ux-0 svc-ux-1 svc-ux-2 svc-ux-3 ux15-accessibility-1 ux15-consolidation-1
ux15-counselor-evaluation ux15-exit-interview ux15-feedback-csm ux15-final-consolidation
ux15-graduate-tracer ux15-hardening-1 ux15-home-1 ux15-home-2 ux15-home-3 ux15-pilot
ux15-routine-intake
```

Gate satisfied: HEAD `494a7e2a`, the required branch, only the two pre-existing untracked entries,
`docs/cenc-0/`–`docs/cenc-3/` present and no `docs/cenc-4/`. Neither pre-existing entry was touched:
both still appear unmodified in the final `git status` below.

## 2. §2 current-state verification

Checked before editing, and each claim held:

| Claim | Evidence |
|---|---|
| `CounselingEncounter.appointment` is `OneToOneField(Appointment, PROTECT, related_name="counseling_encounter", null=True, blank=True)` | `be/compass/counseling/models.py` |
| Exposure gate, statuses and capability as described | `be/compass/counseling/services.py` (`appointment_encounter_recorded`) |
| Strict write-side identity check inside the finish transaction | `be/compass/counseling/finish_service.py:75-93` |
| ONLINE access period `ends_at + ECOUNSELING_REJOIN_GRACE_SECONDS` (default `900`), OPEN while `current <= available_until` | `be/compass/ecounseling/services.py:198-228`, `be/config/settings.py:312` |
| A linked Encounter failing the rule yields `recorded=false` | `be/tests/test_counseling_context.py:1132-1153` |
| The E-Counseling workspace already reports `MISMATCH` | `fe/src/features/ecounseling/encounter-section-state.ts:78-87` |
| Pagination idiom `_validate_page` / `page_size + 1` / `DEFAULT_PAGE_SIZE = 20` | `be/compass/counseling/services.py` (`list_appointment_candidates`) |
| The canonical COUNSELING Service cannot be deactivated through `set_service_active` | `be/compass/service_catalog/services.py` (`CanonicalServiceRequired`) |
| Static-render harness signature `withNextRouter(element, {pathname, search, params, navigations})` | `fe/tests/support/next-router.mjs:13` |

One prompt detail was a typo and was followed against the code, as the prompt itself instructed:
`list_documentation_review`'s `page` default is `1` (matching `list_appointment_candidates`), not
`DEFAULT_PAGE_SIZE`.

## 3. First-run failures (verbatim) and their fixes

### 3.1 Backend worklist matrix, first run

```
compass.service_catalog.services.CanonicalServiceRequired: The canonical Counseling Service is
required by COMPASS and cannot be disabled.
1 failed, 13 passed in 21.92s
```

The deactivation case called `set_service_active(..., is_active=False)` on the canonical Service, which
the catalog forbids by design. **Fix:** the test flips `is_active` through the ORM directly (with a
comment saying why) and drops the now-unused import. Result: `14 passed in 22.28s`.

### 3.2 Contract test, first run

```
assert 'summary' not in '{"operation...
  'summary' is contained here: ... "summary": "counseling list documentation review"
1 failed, 1 passed, 42 deselected in 4.39s
```

The forbidden-key scan serialized the whole path entry, so it matched django-ninja's generated
per-operation `summary`. **Fix:** serialize only the three schema objects (the existing pattern in
this file), keeping the scan over `title` / `description` / `enum` keys. Result:
`2 passed, 42 deselected`.

### 3.3 Frontend panel tests, first run

```
ℹ pass 5
ℹ fail 2
```

- *the worklist reports a failure instead of pretending to be empty* — the panel rendered the loading
  skeleton (`<p role="status" class="sr-only">Loading appointments that need documentation…</p>`)
  instead of the alert, so `/Needs documentation could not be loaded\./` failed. Cause: with
  `data === undefined` and `retryOnMount` at its default, TanStack optimistically reports an errored
  query as `isPending` during a static render, where no mount effect can ever run. **Fix:** the
  harness QueryClient pins `retryOnMount: false, refetchOnMount: false` (the repo's existing idiom in
  `tests/service-group-sessions.test.mjs:137` and `tests/retention-policies.test.mjs`), with a comment
  that these are harness settings, not the panel's.
- *the panel pages its own list without disturbing the encounters* — `assert.ok(html.includes("review_page=2") ||
  html.includes("review_page=3"))` failed because `CanonicalPagination` renders buttons plus an
  `onPageChange` callback, never hrefs; the wiring is already covered by the pure `reviewHref` test.
  **Fix:** the case now pins `aria-label="Needs documentation pages"`, `Page 2 · 3 appointments on
  this page`, both pager controls, the absence of any `review_page` href, and that the row links stay
  plain hrefs.

### 3.4 Ruff check, first run

```
E501 Line too long (101 > 100)  --> compass/counseling/services.py:842:101
E501 Line too long (106 > 100)  --> tests/test_counseling_documentation_review.py:185:101
E501 Line too long (102 > 100)  --> tests/test_counseling_documentation_review.py:300:101
Found 3 errors.
```

**Fix:** the grace comment is rewrapped over three lines; the `create_service(...)` call and the
online-boundary assertion are wrapped. No behavior change.

### 3.5 Ruff format check, first run

```
3 files would be reformatted, 2 files already formatted
```

(`compass/counseling/api.py:508`, `tests/test_counseling_documentation_review.py:339` and `:541`,
`tests/test_openapi_contract.py:3511` and `:3552` — all inside the slices added by this work.)
**Fix:** `uv run ruff format` on exactly those three files, then the whole targeted pytest block was
re-run (§4). `git diff --numstat` afterwards confirms `be/compass/counseling/api.py` (73/0) and
`be/tests/test_openapi_contract.py` (80/0) contain **zero deletions**, so no pre-existing line in
either file was reformatted.

### 3.6 Caught before any run

The first draft of `be/tests/test_counseling_documentation_review.py` contained placeholder artifacts
(a mangled `CounselingEntryModeREFERRED` identifier, a no-op `assert (admin, service) == (admin,
service)`, a helper defined after its first use, and missing `@pytest.mark.django_db` marks). It was
rewritten wholesale before being executed, so no failure of that draft is recorded above.

## 4. Targeted backend suite (final)

```
$ cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run pytest \
    tests/test_counseling_documentation_review.py tests/test_counseling_context.py \
    tests/test_counseling.py tests/test_openapi_contract.py -q
112 passed, 1 warning in 167.10s (0:02:47)
```

The single warning is pre-existing: `ninja/operation.py:220 DeprecationWarning: Returning tuple
(status_code, response) is deprecated` from `tests/test_counseling.py`, unrelated to this slice.

Per-file counts (same command, files run individually):

| File | Result |
|---|---|
| `tests/test_counseling_documentation_review.py` | `14 passed in 22.28s` |
| `tests/test_counseling_context.py` | `31 passed in 61.62s (0:01:01)` |
| `tests/test_counseling.py` | `23 passed, 1 warning in 30.76s` |
| `tests/test_openapi_contract.py` | `44 passed in 72.83s (0:01:12)` |

`14 + 31 + 23 + 44 = 112`. The first full-block run of the same command, before the ruff fixes, was
`112 passed, 1 warning in 189.00s (0:03:08)`.

## 5. Contract, migrations, client

```
$ cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi --output ../contracts/openapi.json
Exported OpenAPI contract: ../contracts/openapi.json
$ DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi --check --output ../contracts/openapi.json
OpenAPI contract is current: ../contracts/openapi.json
$ DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run
No changes detected
$ cd fe && pnpm api:generate
🍻 orval v8.29.0 - A swagger client generator for typescript
compass Cleaning output folder
🎉 compass - Your OpenAPI spec has been converted into ready to use orval!
```

Both `--check` lines were re-run after the ruff reformatting; the contract stayed current without a
second regeneration, and `makemigrations --check --dry-run` still reports no changes. No hand edit was
made to `contracts/openapi.json` or `fe/src/lib/api/generated/**`.

```
$ git diff --stat contracts/openapi.json
 contracts/openapi.json | 204 ++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 203 insertions(+), 1 deletion(-)
```

The single deletion is the `required` entry `"counseling_encounter_recorded"`, re-emitted with a
trailing comma so the new `counseling_encounter_linked` can follow it. Additions are exactly the
expected shape: one new GET path `/api/v1/counseling/documentation-review` (operation
`counselingListDocumentationReview`, responses 200/401/403/409/422, params `page` and `page_size`),
three new schemas (`CounselingDocumentationReviewReason`, `…ItemResponse`, `…PageResponse`), and the
two `AppointmentDetailResponse` lines. No other path, operation, error code or schema line changed.

## 6. Frontend tests (final)

```
$ cd fe && node --import ./tests/support/register-tsx.mjs --test \
    tests/counseling-documentation-review.test.mjs tests/counseling-finish.test.mjs
ℹ tests 20
ℹ pass 20
ℹ fail 0
ℹ skipped 0
```

- `counseling-documentation-review.test.mjs`: 7 tests (2 pure copy/parameter, 5 panel static renders —
  rows and links, no-authoring, management-gated viewer, empty first page and stranded page, error
  with no data and stale-data refresh, own pager).
- `counseling-finish.test.mjs`: 13 tests — the 9 pre-existing ones **unchanged** (append-only edit,
  61 insertions and 0 deletions) plus the 4 cases this slice adds.

## 6.1 Extra targeted regressions beyond the protocol

The protocol's file list does not cover every surface this slice touches, so these were run too. Both
were green on the first attempt.

```
$ cd be && DJANGO_SETTINGS_MODULE=tests.settings uv run pytest tests/test_appointments.py \
    tests/test_counseling_finish.py tests/test_ecounseling.py \
    tests/test_appointment_action_projection.py -q
71 passed in 71.51s (0:01:11)

$ cd fe && node --import ./tests/support/register-tsx.mjs --test \
    tests/appointment-slot-freshness.test.mjs tests/counseling-online-delivery.test.mjs \
    tests/date-semantics.test.mjs tests/page-action.test.mjs
ℹ tests 36
ℹ pass 36
ℹ fail 0
```

The backend group covers the Appointment projections and Detail payload, the CENC-1 finish path, and
the E-Counseling context that shares `appointment_encounter_matches`. The frontend group covers every
other test file that imports `AppointmentDetailPage` or `CounselorEncounters`.

## 7. Static checks

```
$ cd fe && pnpm lint        → $ eslint .          (no output, exit 0)
$ cd fe && pnpm typecheck   → $ tsc --noEmit      (no output, exit 0)
$ cd fe && pnpm build       → production build completed, route table emitted, exit 0
```

`pnpm build` churned `fe/next-env.d.ts` (its `./.next/dev/types/*.d.ts` imports became
`./.next/types/*.d.ts`). That is Next's own build rewrite, not a source change, and it was restored
alone:

```
$ git checkout -- fe/next-env.d.ts
```

```
$ cd be && uv run ruff check compass/counseling/services.py compass/counseling/api.py \
    compass/appointments/api.py tests/test_counseling_documentation_review.py \
    tests/test_openapi_contract.py
All checks passed!
$ uv run ruff format --check <same five files>
5 files already formatted
$ uv run ruff check .
Found 4 errors.
```

The four errors are the unchanged pre-existing baseline, none in a file this slice touches:

| Location | Error |
|---|---|
| `compass/referrals/provisional_activation.py:334` | E501 (111 > 100) |
| `tests/test_fup3a_faculty_referral_journey.py:7` | I001 import block is un-sorted or un-formatted |
| `tests/test_guidance_followups.py:464` | E501 (102 > 100) |
| `tests/test_guidance_followups.py:565` | E501 (102 > 100) |

## 8. Final tree state

```
$ git status --short
 M be/compass/appointments/api.py
 M be/compass/counseling/api.py
 M be/compass/counseling/services.py
 M be/tests/test_openapi_contract.py
 M contracts/openapi.json
 M fe/src/features/appointments/appointment-detail-page.tsx
 M fe/src/features/counseling/counselor-encounters.tsx
 M fe/src/features/counseling/finish-counseling-availability.ts
 M fe/tests/counseling-finish.test.mjs
?? "Claude outputs/"
?? be/tests/test_counseling_documentation_review.py
?? docs/cenc-4/
?? fe/src/features/counseling/documentation-review-panel.tsx
?? fe/src/features/counseling/documentation-review.ts
?? fe/tests/counseling-documentation-review.test.mjs
?? outputs/paper-screenshots/
```

`fe/next-env.d.ts` is absent because it was restored. `docs/cenc-4/` is this package. Nothing was
committed and nothing was pushed; the tree is left for review. Tracked totals, excluding the new
untracked files and the generated contract: 654 insertions / 22 deletions across the nine modified
files.

## 9. Deliberately not run

- The full backend suite (`uv run pytest` over everything) and the whole-`pnpm test` frontend glob.
- Every `*.browser.mjs` case and `run-browser-regressions.mjs`; the browser gate is CENC-5.
- WebKit and any real-browser pass; accessibility tooling; screenshots; real E-Counseling or Daily
  rooms.
- No UAT, no clinical, privacy, security or institutional review, and no GCO decision.
- Concurrency/stress: this slice adds no write path, so no lock-order or idempotency stress was run;
  CENC-1's finish tests remain the authority there.
