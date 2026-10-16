# COMPASS-CANON-1 — Architecture & Technical Audit

## 1. Executive Summary & Architectural Intent

COMPASS is the Guidance and Counseling Information System for the University of Camarines Norte (UCN).
Following multiple development iterations (including the complete retirement of in-app disposition execution in PG-1A PRs #244, #245, #246), COMPASS carries accumulated legacy implementations, transition shims, migration bloat, unregistered tests, and CI regressions.

The project owner has approved **COMPASS-CANON-1**: a comprehensive milestone to establish **one canonical, clean-installable COMPASS system**, culminating in a controlled clean-slate rebuild of live-staging.

### Key Architectural Invariants:
1. **One Canonical Implementation:** One API route, one operation ID, one request/response schema, one authoritative service implementation, one domain lifecycle, one capability definition, one consistent frontend presentation, and one current database model per domain operation.
2. **Clean-Slate Staging Baseline:** No requirement to preserve disposable staging development data or carry backward-compatibility migrations for discarded test schemas.
3. **Uncompromising Security & Privacy:** All RBAC, capability enforcement, counselor boundaries, encryption at rest (Fernet bound JSON), audit trail integrity, privacy notices, and E-Counseling recording consent are strictly preserved and verified.
4. **No Fake Green CI:** Zero deleted valid tests, zero blanket xfails, zero disabled linters, and full test registration across backend and frontend CI workflows.

---

## 2. Backend Architecture Audit

### 2.1 Identity, Roles, Capabilities & Policy Bootstrap
- **Active Capabilities:** `be/compass/accounts/policy.py` defines 67 canonical capabilities, 5 roles (`IT_ADMIN`, `COUNSELOR`, `GUIDANCE_SERVICES_STAFF`, `STUDENT`, `INSTITUTIONAL_OFFICER`), and 2 institutional designations (`HEAD_GUIDANCE_COUNSELOR`, `DPO`). All active capability definitions are strictly canonical.
- **Legacy Capability Shims:**
  - `be/compass/accounts/bootstrap.py` defines `RENAMED_LEGACY_CAPABILITY_CODES = ("organization.view", "services.view")` and `RETIRED_CAPABILITY_CODES = ("institutional_forms.manage", "document_branding.view", "document_branding.manage", "privacy_governance.retention.manage", "privacy_governance.retention.approve")`.
  - `sync_identity_policy()` automatically purges any lingering role grants, designation grants, user overrides, or capability records matching `RETIRED_CAPABILITY_CODES`.
  - **Classification:** `KEEP`. The purge in `bootstrap.py` is a critical fail-closed invariant that ensures retired administrative or retention capabilities cannot linger or grant authority.

### 2.2 Privacy Governance & Retired In-App Disposition Engine (ADR-114 / ADR-115)
- **Active Canonical Surface:**
  - `be/compass/privacy_governance/retention_policy_register.py` & `retention_api.py` implement the code-owned, read-only retention policy register under `GET /api/v1/privacy/retention/policies` (`privacyGovernanceListRetentionPolicies`).
  - **Classification:** `KEEP` (Canonical).
- **Dead Fail-Closed Service Stubs (`be/compass/privacy_governance/retention.py`):**
  - Contains `create_rule()`, `update_rule()`, `transition_rule()`, `change_hold()`, `approve_case()`, and `decommissioned()`. Every function unconditionally raises HTTP 409 `retention_decommissioned`.
  - There are zero API routes and zero runtime callers in `be/compass/`. They were explicitly kept as a temporary fallback until PG-1A PR 3.
  - **Classification:** `REMOVE` (Target PR: CANON-2A).
- **Broker-Drain Celery Task Tombstones (`be/compass/privacy_governance/tasks.py`):**
  - Defines non-mutating no-op tasks for `discover_retention`, `execute_disposition`, and `recover_disposition`.
  - Beat schedules were removed in PR #244. The task names remain registered solely to acknowledge and drop any pre-ADR-114 messages in the Celery broker.
  - **Classification:** `KEEP_TEMPORARILY` (Target PR: CANON-2A / Reset Cutover).
- **Historical Ledger & Resurrection Fences:**
  - `OperationalRetentionRule`, `DispositionCase`, `DispositionHold` (`retention_models.py`): Retained as historical evidence ledgers.
  - E-Counseling media resurrection fences in `be/compass/ecounseling/` (`artifacts.py`, `reconciliation.py`, `webhooks.py`) check `artifact_disposed_at` and `DispositionCase` status to prevent late Daily webhooks from re-ingesting or exposing disposed recordings or transcripts.
  - `GraduateTracerDisposedParticipation` (`be/compass/graduate_tracer/participation.py`): Enforces one-submission-per-graduate and blocks reading historical anonymized responses.
  - **Classification:** `KEEP` (Critical security and privacy custody fences).
- **Dead Analytical Verification Helper:**
  - `be/compass/graduate_tracer/disposition.py` contains `verify_anonymized()`. Zero runtime callers in `be/compass/`; only used by test assertions.
  - **Classification:** `REMOVE` or relocate to `tests/`.

### 2.3 Confidential Content Encryption & Key Rotation
- **Zero Plaintext Fallback:** All 10 encrypted domains store data strictly in `*_ciphertext` columns with Fernet bound JSON envelopes (`be/compass/confidential_data/crypto.py`). Zero plaintext fallback exists in any runtime reader or writer.
- **Architectural Cleanup Candidates:**
  - **Migration Helper Runtime Imports:** `be/compass/inventory/confidential_content.py` and `be/compass/graduate_tracer/confidential_content.py` import schema definitions (`FIELDS`, `FAMILIES`, `BINDINGS`, `validate_payload`, `binding`) from `compass.<app>.migrations._<app>_confidential_content_v1`.
  - **Classification:** `CANONICALIZE` (Target PR: CANON-2B). Runtime domain modules must own their schema constants directly, isolating `migrations/` from runtime dependencies.
  - **Key Rotation Introspection Guards:** The 8 `rotate_*_confidential_content` management commands contain `_legacy_plaintext_exists()` introspection guards to prevent running on pre-Phase-B databases.
  - **Classification:** `KEEP`. Harmless defensive check ensuring database integrity before rotation.

### 2.4 Dead Models & Obsolete Database Artifacts
- **`ServiceProviderRole` (`be/compass/service_catalog/models.py`):** Historical table from pre-ADR-089. COMPASS has since established Counselors as the sole provider class, configured via `Service.provider_coverage` and `ServiceCounselorProvider`. `ServiceProviderRole` has zero runtime readers or writers.
  - **Classification:** `REMOVE` (Target PR: CANON-4).

---

## 3. Frontend Architecture Audit

### 3.1 Routing & Navigation
- **Routes:** 71 active page routes under `fe/src/app/`.
- **Redirect Compatibility Pages:**
  - `fe/src/app/(portal)/portal/privacy/retention/[...legacy]/page.tsx`: Redirects legacy bookmark URLs (`/portal/privacy/retention/rules/...`, `/portal/privacy/retention/cases/...`) to `/portal/privacy/retention`.
  - **Classification:** `REMOVE` (Target PR: CANON-3). Live staging rebuild eliminates old bookmark dependencies.
  - `fe/src/app/(portal)/portal/platform/page.tsx`: Redirects `/portal/platform` to `/portal/platform/health`.
  - **Classification:** `KEEP`. Standard index-to-default-tab redirect.

### 3.2 User Copy & Information Boundaries
- **Boundary Violation in Good Moral Assisted Requests:**
  - `fe/src/features/good-moral/good-moral-assisted-request.ts` imported `readApiErrorMessage` and called `readApiErrorMessage(error.body)` on `invalid_good_moral_request`.
  - COMPASS architectural rules strictly forbid exposing raw API messages in user-facing form copy.
  - **Classification:** `CANONICALIZE` (Target PR: CANON-1A). Replace with static safe copy: `"Check the request details and try again."`

### 3.3 Attention Badges & Navigation Selectors
- **Selector Fragility in Guidance Operations Browser Tests:**
  - PR #231 (`NAV-1`) added `<span data-testid="nav-badge-expanded">{badge.display}</span>` inside the `My work` navigation link. Calling `nav.locator("a").allTextContents()` returned `"My work31"` instead of `"My work"`.
  - **Classification:** `CANONICALIZE` (Target PR: CANON-1A). Target the label span directly.

---

## 4. Database & Migration Consolidation Audit

### 4.1 Migration State
- **Current State:** 102 numbered migrations across 27 apps, plus 8 frozen helper modules (`_..._v1.py`).
- **Anomalies Identified:**
  - `documents`: `0001` creates `DocumentBrandingProfile`; `0002` checks and deletes it. The app has no models left.
  - `privacy_governance`: `0001`–`0004` create and drop 4 legacy tables.
  - `good_moral`: `0005_merge_20261005_0419.py` is an empty branch merge.
  - Two-phase encryption migrations: 16 migration files across 8 apps added temporary nullable ciphertext columns, ran backfills, locked tables, and dropped plaintext.
- **Target Consolidated State (`CANON-4`):**
  - Replace the 102 migrations with 26 clean `0001_initial.py` migrations.
  - All encrypted models declare their `*_ciphertext` columns and constraints directly in `0001_initial.py`.
  - Zero data migrations in Django migration files; institutional configuration is seeded purely by authoritative `sync_*` commands.

---

## 5. API Contract & OpenAPI Audit

- **OpenAPI Schema Sync:** `python manage.py export_openapi --check` confirms `contracts/openapi.json` matches backend routers.
- **Contract Test Discrepancies (`test_openapi_contract.py`):**
  - Missing 4 recently added operations (`graduateTracerListClassificationOptions`, `goodMoralListStudentOptions`, `goodMoralCreateCurrentStudentRequest`, `goodMoralCreateGraduateRequest`).
  - Missing query filter parameters (`college_id`, `program_id`, `graduation_year`) on `graduateTracerListResponses`.
  - Missing `good_moral.initiate` capability code in expected enum list.
  - **Classification:** `CANONICALIZE` (Target PR: CANON-1A). Update contract test expectations to reflect current canonical operations.

---

## 6. Classification Summary Table

| Category | Component / Module | Classification | Target PR |
|---|---|---|---|
| **Backend** | `privacy_governance/retention.py` 409 stubs | `REMOVE` | CANON-2A |
| **Backend** | `privacy_governance/tasks.py` tombstones | `KEEP_TEMPORARILY` | CANON-2A |
| **Backend** | `audit/actions.py` `DOCUMENT_BRANDING_UPDATED` | `REMOVE` | CANON-2A |
| **Backend** | `graduate_tracer/disposition.py` verify helper | `REMOVE` | CANON-2A |
| **Backend** | `service_catalog/models.py` `ServiceProviderRole` | `REMOVE` | CANON-4 |
| **Backend** | `inventory` & `graduate_tracer` migration helper imports | `CANONICALIZE` | CANON-2B |
| **Backend** | `accounts/bootstrap.py` retired capability purge | `KEEP` | CANON-2A |
| **Backend** | `ecounseling/` media resurrection fences | `KEEP` | CANON-2B |
| **Frontend** | `portal/privacy/retention/[...legacy]/page.tsx` | `REMOVE` | CANON-3 |
| **Frontend** | `good-moral-assisted-request.ts` user copy | `CANONICALIZE` | CANON-1A |
| **Frontend** | `portal-navigation-attention.browser.mjs` cleanup | `CANONICALIZE` | CANON-1A |
| **Migrations** | 102 numbered migrations consolidated to 26 canonical | `CANONICALIZE` | CANON-4 |
| **CI** | 3 unregistered backend test files | `CANONICALIZE` | CANON-1A |
| **CI** | 8 unregistered frontend browser suites | `CANONICALIZE` | CANON-1A |
| **CI** | 38 Ruff lint errors & 8 formatting files | `CANONICALIZE` | CANON-1A |
| **CI** | Graduate Tracer demo seed ADR-112 input fields | `CANONICALIZE` | CANON-1A |
| **CI** | Backend unit test assertion drift (audit, GM, accounts, OpenAPI) | `CANONICALIZE` | CANON-1A |
