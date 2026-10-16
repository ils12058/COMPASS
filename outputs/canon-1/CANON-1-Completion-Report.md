# COMPASS-CANON-1 milestone status — incomplete

As of 2026-10-16 (Asia/Manila). This is a CANON-1A handoff, not milestone completion.

## Delivered implementation

Draft [PR #247](https://github.com/ils12058/COMPASS/pull/247):
`fix(ci): restore complete COMPASS test coverage (CANON-1A)`.
Exact base: `d353108d1f757386b9020c4d1297e081258d2e4e` on staging.
Branch: codex/canon-1a-ci-coverage. Managed worktree:
/Users/reynantlntno/.codex/worktrees/compass-canon-1a/COMPASS.

- Registered three backend files, repaired source-domain selection, made model changes select
  the full suite (including participation.py), matched recursive pytest discovery and tested split
  coverage. All 167 files and every planned split part are covered across six shards.
- Repaired all 38 Ruff findings and eight formatting discrepancies without weakening validation.
- Registered all 31 browser suites on Chromium and WebKit, with four shards per engine,
  attributable suite failures, continued execution after failure and discovery/shard guards.
- Adapted three feature coverage tests to the canonical discovery runner while preserving their
  engine, suite and route-compilation requirements; removed a workstation-specific evidence path.
- Enabled CI on the planned canon/compass-clean-baseline target and preserved its actual diff
  base after contract-sync dispatch. Deployment remains manual with exact-revision gating.
- Replaced stale duration metadata with actual observations for all 167 files.
- Corrected the recovered audit's unsupported counts/results; retained a repository-wide candidate
  matrix, every numbered migration dependency/custom-operation inventory, existing schema,
  contract/task inventory, classified failures and the ordered remaining PR plan.

## Validation and remaining regressions

Passing local checks: 42 CI self-tests, exact-once file/part coverage, Ruff, lock/compile checks,
fresh current-history PostgreSQL migrations, migration drift, Django checks, OpenAPI verification,
frontend generation/lint/typecheck/build and 31 focused registration/feature checks.

Completed reference CI at 8cff975e:

- Full backend: 4,648 passed, 41 failed, 22 errored, zero skipped; every shard executed and the
  aggregator failed correctly. All 4,711 JUnit case IDs are unique and agree with collected
  function/parameter counts.
- Targeted backend: 1,278 passed, seven failed, zero skipped.
- Browser CI: all 62 suite executions finished; 26/31 suites passed per engine. All unsuccessful
  cases remain visible. Frontend build/lint/typecheck passed.
- Reviewed local unit rerun: 766/767 passed; assisted Good Moral raw backend-message display
  remains an application defect.
- Five focused printing cases pass against the production build; their development-mode failures
  require query/mount lifecycle diagnosis. This is not full printing/UAT acceptance.

The final follow-up changes only CI wiring, tests, measured timings and evidence. Its remote
exact-head checks restart on push; the completed reference run is not claimed as a passing result
for that later revision. See CANON-1-Regression-Report.md for provenance and every classification.

## Review boundary and next work

CANON-1A is staging-compatible, with no changed models, migration files, API contract,
authorization, lifecycle or retention behavior. No production files are removed. It is reviewable
as CI infrastructure even though inherited application regressions remain; it is not release-ready.

Stop at the requested dependency boundary: review/merge of this foundational PR must establish
an actual repaired integration base before independent regression/removal PRs use it. No merge
is performed by this task. The roadmap separates backend fixture/contract corrections, the real
seeder classification bug, frontend fixture/safe-copy fixes, browser/runtime behavior and explicit
notification push policy coverage. Remaining canonicalization follows only after that baseline.

Reset-only PG-1A task/ledger removal, finalized canonical APIs/models, replacement migrations,
current-vs-canonical schema comparison, modernized successful seeding, complete green regression,
role-scoped end-to-end UAT and a rehearsed operator reset runbook remain unfinished. The schema
comparison and tested reset-runbook deliverables are intentionally not fabricated.

## Live safety and readiness

No merge, deployment, database reset/drop, Redis purge, object-storage deletion, key rotation or
live infrastructure change occurred. Public staging still reports build
0512e9ec3533f59b9a90038a50b2d5b122b2e5ee. Worker/broker/provider/storage readiness is unverified.
Transition tombstones, ledgers, media resurrection fences, read-only DPO oversight and capability
boundaries remain intact. Original working checkouts were preserved; the main checkout is clean.
Owned temporary local servers and services were stopped without deleting their databases.

Recommendation: review the foundational CI repair, then fix the recorded regressions from the
actual updated base. Do not promote a canonical reset release or execute a live reset yet.
