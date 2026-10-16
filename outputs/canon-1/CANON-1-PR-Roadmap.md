# COMPASS-CANON-1 — Sequenced Pull Request Roadmap

## 1. Overview & Branching Strategy

To maintain repository stability and allow independent, granular review, the canonicalization of COMPASS is decomposed into **7 coordinated slices (CANON-1A through CANON-7)**.

### Target Branches:
- **`staging`**: Non-breaking, staging-compatible fixes (CI infrastructure repair, linter cleanups, regression bug fixes, and backward-compatible domain cleanups).
- **`canon/compass-clean-baseline`**: Incompatible changes requiring a clean-slate database reset (consolidated `0001` migrations, removal of historical transition tombstones, and deletion of legacy database tables like `ServiceProviderRole`).
- **Live Infrastructure Policy:** **Zero merges, zero deployments, zero database resets, zero Redis flushes, and zero object storage deletions** are executed during this milestone. The live-staging cutover is documented in `CANON-1-Staging-Reset-Runbook.md` and left for separately authorized operator execution.

---

## 2. Sequenced Implementation Slices

### Slice CANON-1A: CI Infrastructure Repair & Staging Regression Baseline
- **Target Branch:** `staging` (via PR branch `fix/canon-1a-ci-and-regression-baseline`)
- **Objective:** Fix all 8 formatting and 38 linting failures, register all 3 unregistered backend tests in `.github/scripts/backend_ci.py`, fix all backend test regressions (demo seed, audit baseline, Good Moral canonical values, accounts capabilities, OpenAPI contract, migration cleanup), fix frontend unit test copy boundary, and register/stabilize all 31 browser test suites.
- **Key Files Touched:**
  - `.github/scripts/backend_ci.py`
  - `be/compass/graduate_tracer/api.py`, `services.py`
  - `be/compass/reports/api.py`, `graduate_tracer.py`, `graduate_tracer_schemas.py`, `graduate_tracer_xlsx.py`
  - `be/compass/demo_seed/scenarios.py`, `population_forms.py`
  - `be/tests/test_demo_seed.py`, `test_audit.py`, `test_good_moral_preparation.py`, `test_accounts.py`, `test_privacy_release_audit.py`, `test_openapi_contract.py`, `test_privacy_governance_migrations.py`, `test_ecounseling_media_v2_migration.py`, `test_guidance_messages.py`
  - `fe/src/features/good-moral/good-moral-assisted-request.ts`
  - `fe/tests/guidance-operations.browser.mjs`, `portal-navigation-attention.browser.mjs`
  - `fe/package.json`, `.github/workflows/frontend-targeted.yml`
- **Verification Gate:** `python3 .github/scripts/backend_ci.py verify`, `ruff format --check`, `ruff check`, backend pytest suite, `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm test:ui:regressions`.
- **Dependencies:** None. Directly reviewable and mergeable to `staging`.

---

### Slice CANON-2A: Backend Legacy Service & In-App Disposition Decommission
- **Target Branch:** `staging`
- **Objective:** Remove dead 409 service stubs in `be/compass/privacy_governance/retention.py`, remove obsolete `DOCUMENT_BRANDING_UPDATED` constant from `be/compass/audit/actions.py`, and relocate analytical verification helper in `be/compass/graduate_tracer/disposition.py`.
- **Key Files Touched:**
  - `be/compass/privacy_governance/retention.py`
  - `be/compass/audit/actions.py`
  - `be/compass/graduate_tracer/disposition.py`
  - `be/tests/legacy_disposition_fixtures.py`, `be/tests/test_operational_retention.py`
- **Verification Gate:** Pytest suite passes; confirm zero dead stubs remain.
- **Dependencies:** CANON-1A merged to `staging`.

---

### Slice CANON-2B: Encryption Domain Boundary Isolation
- **Target Branch:** `staging`
- **Objective:** Eliminate runtime imports from `migrations/_*_confidential_content_v1.py` in `inventory` and `graduate_tracer`, defining schema constants directly in each domain's `confidential_content.py`.
- **Key Files Touched:**
  - `be/compass/inventory/confidential_content.py`
  - `be/compass/graduate_tracer/confidential_content.py`
  - `be/compass/*/management/commands/rotate_*_confidential_content.py`
- **Verification Gate:** All 8 encryption test suites and key rotation commands pass without accessing `migrations/`.
- **Dependencies:** CANON-1A merged to `staging`.

---

### Slice CANON-3: Frontend Legacy Route Removal & UX Consistency
- **Target Branch:** `staging`
- **Objective:** Remove obsolete wildcard redirect page `fe/src/app/(portal)/portal/privacy/retention/[...legacy]/page.tsx`, and clean up any unused components or styling anomalies.
- **Key Files Touched:**
  - `fe/src/app/(portal)/portal/privacy/retention/[...legacy]/page.tsx` (Deleted)
  - `fe/tests/user-copy.test.mjs`
- **Verification Gate:** `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm test`.
- **Dependencies:** CANON-1A merged to `staging`.

---

### Slice CANON-4: Canonical Database Migration Consolidation
- **Target Branch:** `canon/compass-clean-baseline`
- **Objective:** Replace the 102 historical Django migrations across 27 apps with 26 canonical initial migrations (`0001_initial.py`). Remove dead `ServiceProviderRole` model and eliminate the empty `documents` app migrations. All encrypted models declare ciphertext fields directly in `0001_initial.py`.
- **Key Files Touched:**
  - `be/compass/*/migrations/*.py` (Consolidated)
  - `be/compass/service_catalog/models.py` (Delete `ServiceProviderRole`)
- **Verification Gate:** Tests A through E (Migration from empty DB, schema comparison against 102-migration DB, idempotent bootstrap, demo seeder, full pytest suite).
- **Dependencies:** CANON-2A, CANON-2B, CANON-3.

---

### Slice CANON-5: Canonical Staging Seeder Modernization
- **Target Branch:** `canon/compass-clean-baseline`
- **Objective:** Ensure `seed_demo_staging` seeds a deterministic, canonical dataset (57 accounts across all roles and campuses) exercising 100% of supported workflows against the consolidated schema without legacy workarounds.
- **Key Files Touched:**
  - `be/compass/demo_seed/`
  - `be/tests/test_demo_seed.py`, `test_demo_seed_v2.py`
- **Verification Gate:** Seeder runs cleanly from empty DB; all 57 accounts and domain scenarios are fully operational.
- **Dependencies:** CANON-4.

---

### Slice CANON-6: Full Regression Stabilization & Final CI Baseline
- **Target Branch:** `canon/compass-clean-baseline`
- **Objective:** Execute full end-to-end regression validation across all backend shards and frontend browser suites against the consolidated baseline.
- **Verification Gate:** 100% passing CI across all backend and frontend workflows.
- **Dependencies:** CANON-5.

---

### Slice CANON-7: Guarded Clean-Slate Staging Reset & Deployment Runbook
- **Target Branch:** `canon/compass-clean-baseline`
- **Objective:** Provide a step-by-step, pre-validated operator runbook (`CANON-1-Staging-Reset-Runbook.md`) detailing preflight checks, database drops, redis flushes, storage resets, deployment steps, post-cutover verification, and rollback procedures.
- **Live Action:** None by the agent; ready for authorized operator execution.
- **Dependencies:** CANON-6.
