# SAR-2A validation

**Branch:** `codex/sar-2a-canonical-placement`
**Base:** `9109aa83b761086337826d9d1404e0ba8c8c2be3`
**Environment:** macOS arm64; Python/Django via `uv`; PostgreSQL test database; Node.js 24; pnpm.
**Date:** 2026-11-03.

No command contacted staging, production, a real mailbox, an SMS provider, a payment provider or any
other external system. Backend tests use the local test database; browser suites intercept every API
call with synthetic fixtures and run against a local Next server.

## 1. Backend

| Command | Result |
|---|---|
| `uv run ruff format --check .` | PASS — 884 files already formatted |
| `uv run ruff check .` | PASS — all checks passed |
| `uv run python manage.py check --settings=tests.settings` | PASS — no issues |
| `uv run python manage.py makemigrations --check --dry-run --settings=tests.settings` | PASS — no changes detected |
| `uv run python manage.py export_openapi --output ../contracts/openapi.json --settings=tests.settings` | PASS — exported |
| `uv run pytest -q tests/test_student_academic_records.py` | PASS — 16 passed |
| `uv run pytest -q` (full suite) | See final-gate note below |

The first complete full-suite run after the cutover reported 6393 passed and 10 failed. All ten
failures were confined to migration bookkeeping and fixtures: the canonical migration manifest was
missing the four new migrations, the handoff rehearsal read the renamed continuity column through the
ORM, and one frozen seed fingerprint included the changed review copy. The manifest entries were
added, the rehearsal now reads the state-dependent column with raw SQL, and the fingerprint reverses
the single copy change. Every affected file was then re-run in full: `test_canonical_baseline.py`
(5 passed), `test_handoff_migrations.py` (5 passed), `test_staging_deployment.py` (41 passed) and
`test_staging_seed.py` (50 passed). The final full-suite run on the merged integration branch is the
closing gate; its result is recorded in section 5.
| `python3 .github/scripts/backend_ci.py verify` | PASS — 211 test files bundled, each runs exactly once across 6 shards |

## 2. Frontend

| Command | Result |
|---|---|
| `pnpm api:generate` | PASS — Orval generated the client from the regenerated contract |
| `pnpm lint` | PASS — no output |
| `pnpm typecheck` | PASS — no output |
| `pnpm test` | PASS — 1032 tests, 0 failures |
| `pnpm build` | PASS — compiled; `/portal/organization/student-academics` is in the route table |
| `node tests/organization-catalog.browser.mjs` | PASS — 60/60 checks |
| `node tests/ux-hardening.browser.mjs` | PASS — 60/60 checks |
| `node tests/cont4-final-security.browser.mjs` | PASS — 6/6 checks |

The browser suites ran with Chromium against `pnpm exec next start -p 3107`. WebKit was not run.

## 3. Zero-reference evidence

Commands were run from the repository root.

| Check | Command | Result |
|---|---|---|
| Canonical model and reverse relation removed from runtime and tests | `rg -n "StudentAffiliation\|organization_student_affiliation" be/compass be/tests --glob '!**/migrations/**' --glob '!*.pyc'` | no matches |
| Retired operations removed from backend, frontend and contract | `rg -n "organizationListStudentAffiliations\|organizationSetStudentAffiliation\|organizationRemoveStudentAffiliation" be fe/src contracts --glob '!*.pyc'` | no matches |
| SAR-1 machinery removed | `rg -n "STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED\|sync_profile_from_affiliation\|clear_profile_for_removed_affiliation\|backfill_student_academic_profiles\|reconcile_student_academic_profiles" --glob '!docs/**' --glob '!outputs/**' --glob '!archived/**' --glob '!*.pyc'` | no matches |
| New feature contains no “affiliation” copy | `rg -in "affiliation" fe/src/features/student-academics "fe/src/app/(portal)/portal/organization/student-academics" fe/src/features/organization/components fe/src/features/portal/components/portal-command-destinations.ts` | no matches |
| No whitespace errors | `git diff --check` | clean |

`StudentAffiliation` remains only in the historical migrations
`be/compass/organization/migrations/0001_canonical_baseline.py` and
`0005_delete_studentaffiliation.py`. The new test file intentionally keeps the retired route
strings in `test_retired_affiliation_routes_are_gone` to assert that the list, set and clear routes
all return 404.

## 4. Behavioral-preservation evidence

The full suite exercises the swapped consumers. Focused suites relevant to the promised invariant:

| Invariant | Suites |
|---|---|
| Counselor routing and default resolution | `test_counseling.py`, `test_organization.py`, `test_counseling_context.py` |
| Access scopes | `test_appointments.py`, `test_appointment_management_scope.py`, `test_inventory_counselor_review.py`, `test_student_support.py`, `test_guidance_operations.py` |
| Reports and profiling | `test_student_profiling_reports.py`, `test_student_profiling_report_coverage.py`, `test_student_profiling_pdf.py` |
| Referrals and Faculty intake | `test_referrals.py`, `test_faculty_referrals.py`, `test_faculty_foundation.py`, `test_faculty_migration.py` |
| Good Moral | `test_good_moral.py`, `test_good_moral_assisted.py`, `test_good_moral_authenticated_integration.py`, `test_good_moral_receipts.py` |
| Counseling continuity and handoff | `test_continuity.py`, `test_continuity_access.py`, `test_handoff.py`, `test_continuity_release_concurrency.py` |
| Catalog impact blocking | `test_catalog_services.py`, `test_catalog_concurrency.py`, `test_catalog_final_integration.py` |
| Migration graph and policy | `test_organization_policy_migration.py`, `test_faculty_migration.py` |
| New canonical behavior | `test_student_academic_records.py` (16 tests) |

## 5. Not validated

- The closing full-suite run is executed on `integration/ux15-modernization` after the merge; its
  result is appended here when it finishes.
- No merge, push, PR, deployment, staging seed run or production contact.
- No manual browser session; only the synthetic Playwright suites above.
- WebKit browser regression was not run.
- No data migration or backfill rehearsal, because neither exists in this slice.
- The temporary `organization.manage` authorization boundary was not reviewed by IT, GCO, DPO or
  UCN; D-SAR-05 remains open.
- Institutional acceptance of the placement vocabulary, retention, verification and effective-date
  semantics was not obtained; those decisions remain open in the SAR-0 register.
