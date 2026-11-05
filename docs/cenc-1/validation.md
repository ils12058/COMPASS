# CENC-1 — Validation evidence

**Date:** 2026-11-05
**Working tree:** uncommitted on `integration/ux15-modernization` at `b3318637`
**Environment:** Django 6.1, Django Ninja, PostgreSQL 17, `uv`, `DJANGO_SETTINGS_MODULE=tests.settings`
**Commands run from:** `/Users/reynantlntno/Projects/COMPASS/be`

Only the slice's targeted checks were run. The full backend regression is reserved for CENC-5.

## 1. Targeted test commands and final results

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest \
  tests/test_counseling_finish.py tests/test_counseling_finish_concurrency.py \
  tests/test_openapi_contract.py -q
```

**Final result:** `74 passed in 103.24s (0:01:43)`.

| File | Tests | Result |
|---|---:|---|
| `tests/test_counseling_finish.py` | 22 | Passed |
| `tests/test_counseling_finish_concurrency.py` | 10 | Passed |
| `tests/test_openapi_contract.py` | 42 | Passed |

The service/API file includes a two-parameter capability-revocation test, so 21 test functions
produce 22 cases.

Adjacent regression guard (existing file, not modified):

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run pytest tests/test_counseling.py -q
```

**Result:** `23 passed, 1 warning in 30.11s`. The warning is the pre-existing Ninja
`DeprecationWarning` for returning `(status_code, response)` tuples in
`test_api_assignment_privacy_student_lookup_and_no_idempotency_requirement`; this slice did not
introduce or change it.

## 2. First-run failures and resolutions

| # | Check | First-run result | Cause | Resolution |
|---|---|---|---|---|
| 1 | `pytest tests/test_counseling_finish.py` | `22 passed, 1 error` — fixture `prefix` not found at line 127 | Helper `test_domain_with_routine(prefix)` was collected as a test because of its `test_` prefix | Renamed the helper to `setup_domain_with_routine` and updated its three call sites; re-run `22 passed` |
| 2 | `pytest tests/test_counseling_finish_concurrency.py` | `1 failed, 9 passed` — expected `('not_found', 'reassigned')`, got `('error:CounselingNotFound', 'reassigned')` | After a concurrent reassignment the finishing Counselor is no longer the provider, so the service raises `CounselingNotFound`, not `CounselingAppointmentClosed` | Widened the test's not-found branch to catch `(CounselingAppointmentClosed, CounselingNotFound)`; re-run `10 passed` |
| 3 | `ruff check` on the new concurrency file | `I001` unsorted import block | Import order inside `compass.counseling.finish_service` | Applied `ruff check --fix`; clean |
| 4 | `ruff check` on `test_openapi_contract.py` | `F821` undefined `options`, `appointment`, `appointment_student`, `correction` | The new finish contract test had been inserted in the middle of `test_counseling_frontend_readiness_openapi_contract`, splitting its tail | Moved the new test after the complete frontend-readiness test; clean |

No production-code behavior was changed to make a test pass. The only production changes after the
first implementation pass were none; failures 1–4 were test organization/expectation and import
issues.

## 3. Contract and migration checks

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi \
  --output ../contracts/openapi.json
```

**Result:** `Exported OpenAPI contract: ../contracts/openapi.json`

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi \
  --check --output ../contracts/openapi.json
```

**Result:** `OpenAPI contract is current: ../contracts/openapi.json`

**Contract diff summary:** `contracts/openapi.json` +184 lines, insertions only. It adds:

- Path `/api/v1/counseling/appointments/{appointment_id}/finish` with operation ID
  `counselingFinishAppointment`, tag `counseling`, `OpaqueSessionAuth`, and `200`/`401`/`403`/`404`/
  `409`/`422` responses.
- Component schemas `CounselingFinishRequest`, `CounselingFinishResponse`,
  `CounselingFinishEncounterResult` (`CREATED`/`EXISTING`).

No existing path or schema was removed or modified. The artifact was generated, never hand-edited.

```bash
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run
```

**Result:** `No changes detected` — no model or migration change.

## 4. Static checks

```bash
uv run ruff check compass/counseling/finish_service.py compass/counseling/api.py \
  tests/test_counseling_finish.py tests/test_counseling_finish_concurrency.py \
  tests/test_openapi_contract.py
```

**Result:** `All checks passed!`

`ruff format --check` on the same five files: `5 files already formatted`.

## 5. Contract test coverage added

`test_openapi_contract.py` adds the operation ID to `EXPECTED_OPERATION_IDS` and a dedicated test
(`test_counseling_finish_contract_is_closed_identifier_only_and_idempotent`, line 2968) that
asserts:

- operation ID, tag, session auth, status set, and `APIErrorResponse` on every error status;
- strict request schema (`additionalProperties: false`) with exactly the three required fields and
  no `request_key`;
- strict response schema with exactly the seven identifier/flag fields, all required;
- `encounter_result` enum `["CREATED", "EXISTING"]` only;
- no Student, email, phone, address, history, reason, or audit content in the schemas.

## 6. Working tree evidence

```text
 M be/compass/counseling/api.py
 M be/tests/test_openapi_contract.py
 M contracts/openapi.json
?? be/compass/counseling/finish_service.py
?? be/tests/test_counseling_finish.py
?? be/tests/test_counseling_finish_concurrency.py
?? docs/cenc-1/
?? outputs/paper-screenshots/
```

Diff stat for tracked files: `be/compass/counseling/api.py` +69,
`be/tests/test_openapi_contract.py` +49, `contracts/openapi.json` +184; total +302 insertions, no
deletions. `outputs/paper-screenshots/` is the pre-existing untracked directory and was left
untouched.

## 7. Deliberately not run

| Item | Why |
|---|---|
| Full backend regression suite | Reserved for CENC-5, the family's final slice, per the slice-validation rule |
| Frontend build, typecheck, browser/E2E tests | No frontend or generated-client file changed; CENC-2 owns UI |
| UAT execution | Not authorized; D-CENC decisions remain Open |
| GCO / institutional / security / privacy review | Outside implementation scope; no approval is claimed |
| Load or multi-process stress beyond the real-thread concurrency tests | Slice budget; concurrency invariants are covered by `TransactionTestCase` with real connections |
| `makemigrations` without `--check --dry-run` | Explicitly forbidden by the slice prompt |
| Commit, push, amend, rebase, branch creation | Explicitly forbidden unless asked |

## 8. Conclusion

All CENC-1 targeted checks pass: 74 targeted tests, 23 adjacent counseling regressions, a current
and verified OpenAPI artifact, an empty migration check, and clean ruff lint/format. No full-suite,
frontend, browser, UAT, or approval claim is made, and no Git mutation was performed.
