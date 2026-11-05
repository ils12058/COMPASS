# SAR-7 — Academic roster reconciliation (Flow G)

**Status:** Implemented in the working tree; validation results recorded in
[`validation.md`](validation.md). Not committed, merged, pushed or deployed; left for explicit Git
authorization per the slice constraints.
**Branch:** `integration/ux15-modernization`.
**Base:** `8931290e` (SAR-6 merge).
**Date:** 2026-11-05.

## 1. Scope delivered

One bounded CSV import that reconciles **current Student College placement only**:

- Added the capability `student_academics.import`, granted to `IT_ADMIN` and the
  `HEAD_GUIDANCE_COUNSELOR` designation, with a dependency on `student_academics.view` only.
  Policy totals after the change: **95 capability definitions, 105 role grants, 23 designation
  grants**.
- Added `be/compass/student_academics/roster_import.py`: a bounded CSV parser (1 MiB, 1,000
  non-empty rows) and a classify/commit service that resolves identity and active Campus/College
  references, protects `VERIFIED` and anomalous placements, and applies only `SET` rows through the
  existing single writer `set_current_placement`.
- Added `POST /api/v1/student-academics/imports/csv`
  (`studentAcademicsImportRosterCsv`, `dry_run` defaults to `true`) with recent-MFA enforcement for
  both dry-run and commit. Regenerated `contracts/openapi.json` and the ignored Orval client.
- Added the gated route `/portal/organization/student-academics/import`, the roster page with a
  headers-only template, active Campus/College reference table, validation report, commit review
  dialog, step-up continuation and cache invalidation, the staff-page `Import` action, and the
  command-palette destination.
- Added backend tests (`28`), frontend node tests, and a synthetic browser suite (`6` checks)
  discovered automatically by `tests/run-browser-regressions.mjs`.

No model or migration was added. No seed file changed. No dependency was added.

## 2. Explicit non-goals

Not changed by this slice:

- Account creation, identity, email, role, designation, lifecycle or status.
- Student email matching; the CSV has no email column.
- Program assignment; `program_code` remains unsupported.
- Academic periods, enrollment status, graduation, or verification writes.
- Placement clearing, removal, withdrawal, or “missing row = no placement” semantics.
- Verified-placement verification or correction workflows.
- College-scoped academic permissions.
- Faculty or Counselor access; any grant beyond `IT_ADMIN` and `HEAD_GUIDANCE_COUNSELOR`.
- Inventory coverage, reconciliation denominators, reports or precedence.
- Models, migrations, seed files, or seed verification data.
- `docs/sar-0/**` through `docs/sar-6/**`, including every D-SAR status (all remain **Open**).
- Deployment, staging, production or Git integration.

## 3. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Per-file change table, capability definition/grants/dependency, CSV contract, classification matrix, dry-run/commit algorithm, audit behavior, API contract and error codes, frontend gate/route/actions/invalidation/step-up, generated artifacts |
| [`decisions.md`](decisions.md) | Provisional defaults applied, the D-SAR decisions they touch, and confirmation that all remain Open |
| [`validation.md`](validation.md) | Exact commands and real results, including first-run failures and fixes, per-shard and per-engine totals, disposable-database seed verification, repository hygiene, and the explicit not-run list |

## 4. Relationship to earlier slices

`docs/sar-0/` through `docs/sar-6/` remain historical and were not rewritten. SAR-6 is merged at the
base commit and supplies the canonical placement model, capability families, student self-view and
placement precedence that this slice reuses. SAR-7 consumes D-SAR-05, D-SAR-15, D-SAR-02, D-SAR-14,
D-SAR-07, D-SAR-09/10/11/12, D-SAR-16 and D-SAR-19/20 as **provisional engineering defaults**, not
institutional decisions; all remain Open.
