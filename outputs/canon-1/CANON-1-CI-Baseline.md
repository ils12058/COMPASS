# COMPASS-CANON-1 — CI Infrastructure & Regression Baseline Report

## 1. Verified Baseline Metadata
- **Repository:** `ils12058/COMPASS`
- **Main Integration Branch:** `staging`
- **Verified Staging Commit SHA:** `d353108d1f757386b9020c4d1297e081258d2e4e` (`refactor(privacy): finalize legacy disposition retirement (PG-1A PR 3) (#246)`)
- **Inspection Date / Local Time:** 2026-10-16 13:30:00+08:00
- **Live-Staging Target State:** `build_id: "0512e9ec3533f59b9a90038a50b2d5b122b2e5ee"` (deployed 2026-10-11, 28 commits behind staging; to be cleanly rebuilt on canonical release).
- **Active Git Worktrees:** Clean master worktree created at `/Users/reynantlntno/Projects/COMPASS-CANON-1` on branch `canon/compass-clean-baseline`.
- **Open Pull Requests:** 0 open PRs on `ils12058/COMPASS`.

---

## 2. CI Workflow Health & Failure Reproduction

### 2.1 Backend CI Workflow (`.github/workflows/backend-full-regression.yml`)
The backend workflow consists of 10 jobs:
1. `backend-static-analysis` (Python 3.13)
2. `backend-shards` (8 matrix test shards across domain bundles)
3. `backend-migrations` (Migration integrity, graph linearity, forward/reverse execution)

#### Job 1: `backend-static-analysis` — **FAILING**
- **Command 1: `python3 .github/scripts/backend_ci.py verify`**
  - **Status:** **FAILED**
  - **Error Output:**
    ```
    ERROR: 3 test file(s) are not registered in any bundle:
      - tests/test_domain_activity.py
      - tests/test_good_moral_assisted.py
      - tests/test_graduate_tracer_graduation_classification.py
    ```
  - **Root Cause:** Three recent backend test suites added in recent PRs were never added to `BUNDLES` in `.github/scripts/backend_ci.py`.
  - **Resolution:**
    - Add `tests/test_domain_activity.py` to bundle `activity-audit`
    - Add `tests/test_good_moral_assisted.py` to bundle `good-moral`
    - Add `tests/test_graduate_tracer_graduation_classification.py` to bundles `graduate-tracer` and `reports`

- **Command 2: `ruff format --check .`**
  - **Status:** **FAILED** (8 files would be reformatted)
  - **Failing Files:**
    - `compass/graduate_tracer/api.py`
    - `compass/graduate_tracer/services.py`
    - `compass/reports/graduate_tracer.py`
    - `compass/reports/graduate_tracer_xlsx.py`
    - `tests/test_graduate_tracer.py`
    - `tests/test_graduate_tracer_confidential_content_encryption.py`
    - `tests/test_graduate_tracer_graduation_classification.py`
    - `tests/test_guidance_messages.py`
  - **Root Cause:** PR #240 (`BACKLOG-GT-REPORT-1`) and subsequent commits merged unformatted Python code.
  - **Resolution:** Reformat using `ruff format`.

- **Command 3: `ruff check .`**
  - **Status:** **FAILED** (38 lint violations across 7 files)
  - **Violations by File:**
    - `compass/graduate_tracer/services.py`: Lines 517, 578, 759 (`E501` line length > 100)
    - `compass/reports/api.py`: Line 132 (`E501`)
    - `compass/reports/graduate_tracer.py`: Lines 333, 336, 355 (`E501`)
    - `compass/reports/graduate_tracer_schemas.py`: Line 3 (`I001` unsorted imports)
    - `tests/test_graduate_tracer.py`: Lines 100, 101 (`E501`)
    - `tests/test_graduate_tracer_graduation_classification.py`: 22 unused imports (`F401`), 1 unsorted imports (`I001`), 4 line length violations (`E501` lines 56, 92, 95, 263)
    - `tests/test_guidance_messages.py`: Line 908 (`F841` unused local variable `msg2`), Line 959 (`E501`)
  - **Resolution:** Remove unused imports, sort imports, wrap lines under 100 characters.

- **Command 4: `python3 manage.py check` & `makemigrations --check --dry-run`**
  - **Status:** **PASSED** (System check identified no issues; no missing migrations).

- **Command 5: `python3 manage.py export_openapi --check`**
  - **Status:** **PASSED** (Tracked `contracts/openapi.json` is byte-for-byte in sync with code).

---

### 2.2 Backend Pytest Shards (`backend-shards`) — **FAILING**
When running the full backend test suite against PostgreSQL 17, **62 tests failed** across 7 test modules. Local reproduction confirmed the exact root causes:

#### 1. `be/compass/demo_seed/` (51 test failures in `test_demo_seed.py` and `test_demo_seed_v2.py`)
- **Failure 1 (Production Seeder Regression in 49 tests):**
  - **Error Output:** `compass.graduate_tracer.errors.InvalidGraduateTracerInput: graduated_college is required before submission.`
  - **Root Cause:** ADR-112 made `graduated_college`, `graduated_program`, and `graduation_year` mandatory before calling `submit_my_response()` (`be/compass/graduate_tracer/services.py:750-756`). However, the staging demo seeder helper `_tracer_values()` in `be/compass/demo_seed/scenarios.py:911-923` (used by `SCENARIO_ALUMNI`, `SCENARIO_RECENT_GRADUATE`, and `population_workflows.py:134`) was never updated to provide `graduated_college_id`, `graduated_program_id`, and `graduation_year`.
  - **Fix:** Update `_tracer_values()` in `scenarios.py` to query or pass the valid college, program, and graduation year, ensuring all seeded responses satisfy ADR-112.
- **Failure 2 (Test Isolation Flakiness in 2 tests):**
  - `test_command_refuses_before_reading_secrets_or_touching_the_database` (line 242) and `test_missing_demo_password_fails_before_any_write` (line 271) assert `assert not AuditEvent.objects.exists()`.
  - **Root Cause:** The autouse fixture `synchronized_institutional_forms` in `be/tests/conftest.py` runs before each test and records 1 `INSTITUTIONAL_FORMS_SYNCED` `AuditEvent`.
  - **Fix:** Measure the initial audit count `baseline = AuditEvent.objects.count()` and assert `assert AuditEvent.objects.count() == baseline`.

#### 2. `be/tests/test_audit.py` (2 test failures)
- **Failing Tests:**
  - `test_success_audit_event_rolls_back_with_surrounding_transaction` (line 269)
  - `test_policy_sync_rolls_back_if_audit_recording_fails` (line 394)
- **Error Output:** `assert 1 == 0`
- **Root Cause:** Tests assert `AuditEvent.objects.count() == 0`, ignoring the 1 `AuditEvent` created by the `conftest.py` autouse fixture.
- **Fix:** Update assertions to compare against baseline count `AuditEvent.objects.count() == baseline`.

#### 3. `be/tests/test_good_moral_preparation.py` (2 test failures)
- **Failing Tests:**
  - `test_safe_corrections_preserve_sources_and_ready_requires_reconfirmation` (line 154): passes `"year_level_snapshot": "Third"`.
    - **Error Output:** `compass.good_moral.errors.InvalidGoodMoralInput: year_level_snapshot is invalid.`
    - **Root Cause:** FORM-INPUT-1A strictly enforces canonical year levels (`CANONICAL_YEAR_LEVELS = ("1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year")`). `"Third"` is rejected.
    - **Fix:** Change `"Third"` to `"3rd Year"`.
  - `test_prepare_validates_completeness_and_rejects_stale_review` (line 329): calls `update_request(..., changes={"semester_snapshot": ""})`.
    - **Error Output:** `compass.good_moral.errors.InvalidGoodMoralInput: semester_snapshot is invalid.`
    - **Root Cause:** `update_request` validates canonical semesters (`"First Semester"`, `"Second Semester"`, `"Summer"`) immediately at update time.
    - **Fix:** Test incomplete/stale review via an uncompleted field or valid target.

#### 4. `be/tests/test_accounts.py` (2 test failures)
- **Failing Tests:**
  - `test_policy_sync_is_idempotent_and_does_not_create_django_model_permissions` (lines 154, 166, 167)
  - `test_effective_capabilities_combine_role_designation_and_overrides` (line 310)
- **Error Output:**
  - `assert 79 == 78` (Capability count)
  - `assert 95 == 93` (RoleCapability count)
  - `assert missing == {'good_moral.initiate'}`
- **Root Cause:** PR #243 (`BACKLOG-GM-ASSIST-1`) added the canonical capability `good_moral.initiate` and assigned it to `COUNSELOR` and `GUIDANCE_SERVICES_STAFF`, but the hardcoded count and exact-set assertions in `test_accounts.py` were not updated.
- **Fix:** Update expected capability count from 78 to 79, role capability count from 93 to 95, and add `"good_moral.initiate"` to the counselor capability set.

#### 5. `be/tests/test_privacy_release_audit.py` (1 test failure)
- **Failing Test:** `test_graduate_tracer_xlsx_release_records_only_safe_report_context` (line 299)
- **Error Output:** Exact dictionary mismatch on `event.metadata`.
- **Root Cause:** PR #240 expanded `record_graduate_tracer_release` to record 5 filter fields (`college_id`, `college_code`, `program_id`, `program_code`, `graduation_year`), which are all `None` on unfiltered exports. The test asserted exact dict equality against the old 3-key metadata schema.
- **Fix:** Include the 5 filter keys (`None` values) in expected metadata.

#### 6. `be/tests/test_openapi_contract.py` (4 test failures)
- **Failing Tests:**
  - Line 23: `EXPECTED_OPERATION_IDS` has 351 IDs vs 355 actual.
    - **Missing IDs:** `graduateTracerListClassificationOptions`, `goodMoralListStudentOptions`, `goodMoralCreateCurrentStudentRequest`, `goodMoralCreateGraduateRequest`.
  - Line 864: `test_review_list_query_parameters_match_backend_consistency_contract` missing `college_id`, `program_id`, `graduation_year` on `graduateTracerListResponses`.
  - Line 1465: `test_core_schemas_and_realistic_error_responses_are_typed` missing `college`, `program`, `graduation_year` on `GraduateTracerReportContext`.
  - Line 1840: `test_policy_enums_and_sensitive_model_fields_are_contract_safe` missing `"good_moral.initiate"` in expected `CapabilityCode` enum list.
- **Root Cause:** Contract tests were not updated when the 4 operations, report context fields, and capability code were added in recent PRs.
- **Fix:** Update expected operation IDs, query parameters, schemas, and enum values in `test_openapi_contract.py`.

#### 7. Migration Test Shard Flakiness (`test_privacy_governance_migrations.py` & `test_ecounseling_media_v2_migration.py`)
- **Root Cause:** `test_privacy_governance_migrations.py` only migrated back to `AFTER_REMOVAL` (`0004_remove_retention_policy`) in `finally:` blocks instead of restoring to leaf nodes (`executor.loader.graph.leaf_nodes()`), leaving the database at an intermediate migration state for subsequent tests running in the same shard.
- **Fix:** Ensure all `MigrationExecutor` tests restore the database to the migration graph's leaf nodes in `finally:` blocks.

---

### 2.3 Frontend Targeted Workflow (`.github/workflows/frontend-targeted.yml`)

#### Job 1: `targeted-frontend` (Node 22.18.0)
- `pnpm lint`: **PASSED** (0 errors, 4 warnings in unregistered test file `portal-navigation-attention.browser.mjs`).
- `pnpm typecheck`: **PASSED** (0 TypeScript errors).
- `pnpm build`: **PASSED** (Production build succeeds).

#### Job 2: `frontend-tests` (Node 26.7.0, `pnpm test`) — **FAILING**
- **Test Suite:** 764 tests across 29 test files.
- **Results:** **763 passed, 1 failed.**
- **Failing Test:** `fe/tests/user-copy.test.mjs:174`
  - *Test Name:* `Raw API message reading stays confined to verified transport and bounded/controlled translators`
  - *Error Output:*
    ```
    AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
    [
      'fe/src/features/good-moral/good-moral-assisted-request.ts'
    ]
    should strictly deep equal
    []
    ```
  - *Root Cause:* PR #243 imported `readApiErrorMessage` in `fe/src/features/good-moral/good-moral-assisted-request.ts` and called `readApiErrorMessage(error.body)` on `invalid_good_moral_request`. COMPASS architectural policy strictly confines `readApiErrorMessage` to verified transport layers and prevents raw API messages from leaking into user-facing copy.
  - *Fix:* Remove `readApiErrorMessage` from `good-moral-assisted-request.ts` and return safe static user copy: `"Check the request details and try again."`

#### Job 3: `frontend-browser-regressions` (`pnpm test:ui:regressions`) — **FAILING & INCOMPLETE**
1. **Failing Test in Existing Regression Suite:**
   - `fe/tests/guidance-operations.browser.mjs` (lines 69–70):
     - Asserting link text in navigation: `assert.deepEqual(links.slice(1, 3).map((value) => value.trim()), ["My work", "Guidance operations"]);`
     - Received: `["My work31", "Guidance operations"]` (Counselor) and `["My work22", "Guidance operations"]` (Staff).
     - *Root Cause:* PR #231 (`NAV-1`) added `<span data-testid="nav-badge-expanded">{badge.display}</span>` inside the `My work` navigation link alongside the label span. Calling `nav.locator("a").allTextContents()` concatenates the label and badge count.
     - *Fix:* Query the label span `nav.locator("a > span:nth-of-type(2)").allTextContents()` (or target by accessible link name).
2. **Unregistered Browser Suites (8 Files):**
   The following 8 browser test files exist in `fe/tests/` but are **completely absent** from `fe/package.json` scripts:
   - `domain-activity.browser.mjs`
   - `ecounseling-timing.browser.mjs`
   - `form-corr-1-exit-interview.browser.mjs`
   - `form-corr-1-inventory.browser.mjs`
   - `good-moral-assisted.browser.mjs`
   - `good-moral-print.browser.mjs`
   - `portal-navigation-attention.browser.mjs` (contains 4 ESLint unused-var warnings, hardcoded artifact directory, and missing `await finish()`)
   - `security-activity.browser.mjs`
3. **Excluded Browser Suites from Regressions (3 Files):**
   The following 3 files are in `test:ui` but excluded from `test:ui:regressions`:
   - `ecounseling-call.browser.mjs`
   - `ecounseling-runtime.browser.mjs`
   - `ui-information-hierarchy.browser.mjs` (excluded due to intermittent tooltip check mentioned in workflow comment line 98).

---

## 3. Full CI Recovery Action Plan

| Priority | Component | Scope of Fix | Target PR |
|---|---|---|---|
| **P0** | `.github/scripts/backend_ci.py` | Register `test_domain_activity.py`, `test_good_moral_assisted.py`, `test_graduate_tracer_graduation_classification.py` in `BUNDLES` | CANON-1A |
| **P0** | Backend Linter & Formatter | Fix all 38 Ruff lint errors and reformat 8 files in `be/` | CANON-1A |
| **P0** | `be/compass/demo_seed/` | Fix `_tracer_values()` in `scenarios.py` to pass required college, program, and graduation year; isolate audit count in `test_demo_seed.py` | CANON-1A |
| **P0** | `be/tests/` | Fix test fixtures and assertions in `test_audit.py`, `test_good_moral_preparation.py`, `test_accounts.py`, `test_privacy_release_audit.py`, `test_openapi_contract.py` | CANON-1A |
| **P0** | Migration Tests | Restore migration leaf nodes in `finally:` blocks in `test_privacy_governance_migrations.py` and `test_ecounseling_media_v2_migration.py` | CANON-1A |
| **P0** | `fe/src/features/good-moral/` | Remove `readApiErrorMessage` from `good-moral-assisted-request.ts` to restore user-copy boundary | CANON-1A |
| **P0** | `fe/tests/` & `fe/package.json` | Fix badge selector in `guidance-operations.browser.mjs`, clean up `portal-navigation-attention.browser.mjs`, register all browser suites in `fe/package.json` and `.github/workflows/frontend-targeted.yml` | CANON-1A |
