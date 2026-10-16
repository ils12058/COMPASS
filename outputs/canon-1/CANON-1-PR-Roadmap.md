# CANON-1 PR roadmap

Base verified 2026-10-16: `d353108d1f757386b9020c4d1297e081258d2e4e`.
No merge, deployment, live reset, Redis purge, storage deletion or live infrastructure change is authorized.

| Slice | Target | Concrete scope | Prerequisites and acceptance |
| --- | --- | --- | --- |
| CANON-1A — test discovery and CI coverage | staging | Register three backend files; include My Activity dependencies; select full suite on model edits; match pytest discovery; verify split-node coverage; repair Ruff; discover all browser suites on Chromium/WebKit with attributable failures and four shards per engine; remove workstation-only evidence path; enable validation on the reset integration target while preserving manual deployment | CI self-tests, exact-once coverage, lint, static/contract/migration checks, frontend generation/typecheck/build, classified regression evidence. Application green is a later checkpoint; no valid tests are deleted/skipped. |
| CANON-1B — inherited regressions | staging | Fix independently reproduced seed, fixture, contract, migration isolation and user-copy/browser failures by root cause | Review/merge 1A first so ordinary validation uses the repaired planner and all browser suites. Production bugs and fixture updates need separate justification. No blanket assertion rewrites. Full six-shard run and registered browser results required. |
| CANON-2 — compatible backend cleanup | staging | Review dead stubs/action vocabulary and Routine wrappers; domain-by-domain service/route/validation consumer tracing; capability drift handling | 1A trusted CI, 1B green baseline for attribution. Matrix evidence for each deletion; current policy/encryption/authorization/lifecycle invariants preserved. Retention tombstones and ledger changes excluded. |
| CANON-3 — frontend/API consumers | staging where compatible, otherwise reset integration | Retired retention redirect; duplicated utilities/presentations; source-owned generated contract; supported deep links and strict error semantics | Domain/API consumer map, regenerated clients, unit/browser/build checks. Removal of currently served API contracts is reset-only if deployed frontend consumers would break. No visual redesign. |
| CANON-2R — final PG-1A decommission | canon/compass-clean-baseline | Remove retired task registrations, 409 services, ledger models and legacy fixture machinery where proved obsolete; replace ledger-dependent E-Counseling queries with surviving custody rules | Reviewed compatible prerequisites; stopped/isolated old runtime and broker as cutover prerequisite; external callbacks/storage review; privacy absence/security tests. Never ordinary deploy to old staging. |
| CANON-4 — canonical schema | canon/compass-clean-baseline | Final models, minimal valid migration graph, no dead schema/transition backfills; explicit config bootstrap | 2/3/2R reviewed. Existing-vs-canonical schema comparison with explained differences; fresh PostgreSQL tests A–E; constraints, indexes, defaults, key rotation, provenance and source ownership verified. Number of initial files is determined by the actual graph. |
| CANON-5 — one deterministic synthetic dataset | canon/compass-clean-baseline | Modernize existing seeder, retire additive staging-only upgrades, cover assisted GM/notifications/printing/form corrections/Activity/DPO/E-Counseling; retain 57-Student population unless expansion separately approved | Canonical schema and sync order validated; actual count/coverage report, idempotent rerun, concurrent-run exclusion, environment/credential/synthetic-domain safety; no email/provider side effects. |
| CANON-6 — complete canonical regression | canon/compass-clean-baseline | Full backend/shards, privacy, encryption, concurrency, reports/PDF, frontend unit/build, Chromium/WebKit/responsive/printing, representative role-scoped UAT | 4/5 and current APIs finalized. Exact revision, zero skipped required shards, all registered checks execute and pass. Record unsuccessful checks too. |
| CANON-7 — operator rebuild preparation | canon/compass-clean-baseline | Resource inventory/classification, non-destructive preflight, typed environment/scope/revision gate, local rehearsal and rollback/failure procedure | No live destructive action. Disposable local full rehearsal, schema/seed/health/transcript/CI evidence, explicit operator approvals, secret preservation and incompatible-image rollback fencing. Normal CI/deploy must never invoke reset. |

## Review boundaries

CANON-1A intentionally does not bundle application fixes with discovery repair. Its expanded checks
can expose real inherited failures. After its review/merge, start CANON-1B from the new actual
origin/staging; do not emulate a merge with a long stack of unpublished application changes.
This is the first dependency boundary because subsequent slices rely on the amended selection and
browser registration being part of their base. The full milestone is not complete after 1A.

Create the dedicated integration branch only when incompatible work begins, with the reviewed
compatible base recorded. PRs into that branch must state reset-only safety and exact dependencies.
Do not merge it into staging or deploy it until separately approved controlled cutover.

Each implementation PR records base SHA, scope, architectural reason, removed/replaced files,
compatibility/security effects, focused/full relevant test results, known regressions, migration
effects and deployment safety. Regression fixes must explain why the old expectation/fixture or
production behavior violates the current approved contract.

## Later deliverables

The existing audit, matrix, CI baseline, migration inventory, regression report and this roadmap
have source/command evidence. Do not create a claimed canonical schema comparison, successful
seeder validation, completed reset runbook/rehearsal or milestone completion report until their
implementation/evidence exists. A CANON-1A handoff report may explicitly record partial progress.

## Concrete regression PR boundaries after CANON-1A review/merge

1. **CANON-1B-A — backend fixture and contract alignment.** Accounts canonical grants;
   audit pre-operation baselines; verified OpenAPI operations/query/context/enums; safe release
   metadata; migration-test restoration. Require exact ownership/authorization/privacy assertions
   to remain. Diagnose the migration failures from the completed full-shard JUnit reports before
   choosing their fix; do not rewrite migration history in this compatible PR.
2. **CANON-1B-B — current seeder input regression.** If the full run confirms missing Graduate
   Tracer academic classification, supply actual canonical college/program/year data in existing
   scenarios and preserve synthetic safety and deterministic reruns. This is distinct from the
   later reset-only retirement of Dataset v1 upgrade machinery. Require focused seeder reports
   and domain validation; no population expansion is implicitly approved.
3. **CANON-1B-C — frontend current-contract fixtures and safe copy.** Controlled assisted Good
   Moral error copy, select-based Good Moral fixtures, badge-aware navigation assertions and
   request-observed synchronization. Preserve uncertain-result/idempotency and exact payload tests.
4. **CANON-1B-D — browser/runtime behavior.** Investigate development PDF query lifecycle versus
   production (five production cases already pass), WebKit popup/device/download/draft behavior,
   the 320px E-Counseling control row and same-tab freshness timing. Keep these as separate small
   fixes when their causes differ; no arbitrary waits, timeout inflation or deleted assertions.

These can be independent PRs from the actual repaired staging base when their files/contracts do
not overlap. A full green baseline remains required before attributing broad canonicalization
regressions. None are to be implemented on an assumed merge of unreviewed CANON-1A.

5. **CANON-1B-E — explicit notification push decision.** The complete suite found the new
   GOOD_MORAL_REQUEST_INITIATED event missing from PUSH_POLICY. Its fallback suppresses push.
   Add an explicit decision consistent with approved current channels; preserve the complete
   registry assertion, safe lock-screen copy and existing in-app/email behavior. No new push
   channel is implicitly approved.
