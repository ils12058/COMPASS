# CANON-1B implementation report

Date: 2026-10-16 (Asia/Manila). Verified fetched base:
`0d7fbd0a5fd0ee6d38aba091a27ffa4ed3ac4691` (`origin/staging`, merged PR #247).
No open PRs existed when work began. Existing worktrees were inspected and preserved. Work is
isolated in the managed `compass-canon-1b/COMPASS` checkout on
`codex/canon-1b-fullstack-cleanup`.

The exact base backend full run
[38888769644](https://github.com/ils12058/COMPASS/actions/runs/38888769644) completed successfully
with all six shards. The inherited browser run
[38886458758](https://github.com/ils12058/COMPASS/actions/runs/38886458758) failed on both engines;
that failure was investigated, not labeled universally flaky.

## Removed and canonicalized

| Area | Change | Caller evidence and canonical replacement |
| --- | --- | --- |
| Routine crypto | Remove `parse_keyring` and `keyring_reuses_secret` forwarding exports | No production caller used these exports; startup already uses common crypto. Routine owner now calls the common parser with its explicit setting name. Domain encryption/binding/error/rotation behavior remains covered. Duplicate parser tests reside in common crypto coverage. |
| Audit context | Remove unused `actor_user` constructor argument and property alias | No caller passed the argument. Three property readers in Assessment Records, Availability and Organization now use `AuditContext.actor`. Actor-type validation and attribution remain. |
| Activity | Remove `ACTIVITY_PRESENTERS` alias | Zero callers; `MY_ACTIVITY_PRESENTERS` remains the canonical projection registry. |
| Retention frontend | Delete `fe/src/app/(portal)/portal/privacy/retention/[...legacy]/page.tsx` | No active application links use it. Canonical `/portal/privacy/retention` remains. Old rule/case bookmarks return 404. Browser and unit assertions now verify absence rather than redirects. |
| Frontend dead exports | Remove 22 symbols across 16 modules | Source/test caller search and App Router import tracing proved the symbols unused. No other whole handwritten module was proven dead. Exact list below. |
| Reports | Share `reportProgramName` in `reports-shared.tsx` | Student profile and geography sections previously duplicated the same formatter. Historical legacy/coded/uncoded labels are preserved. |
| Browser runtime | Replace development-server warming with a separately built synthetic production application | Compile once and share only within eight required browser jobs. No route inventory can go stale. Ordinary production build remains separately required. |

Unused frontend symbols removed: `AlertDialogTrigger`; privacy `primaryLinkClass`, `CategoryList`,
`lifecycleParams`, `LifecycleFilter`, `lifecycleFilterFrom`, `LifecycleFilterValue`, `isNotFound`;
`AppointmentsWorkspaceGate`; `ReferralNotice`; `diagnosticStatusLabel`; `contentPrimaryLinkClass`;
`GoodMoralYearLevel`, `GoodMoralSemester`; `CallSlipNotice`; `InventorySectionHeading`,
`isInventorySubmitted`, `INVENTORY_FORM_CODE`; `ecounselingErrorCode`; `servicesErrorCode`;
`InlineHelp`; Organization `SearchField`. The lifecycle family referenced only its own dead members.
Active API error mappings, input validation, layout conventions and generated schemas remain.

## APIs, authorization and deployment compatibility

No operation, endpoint, response schema, generated operation ID, database model or migration changed.
Generated Orval code was regenerated locally from the committed OpenAPI source and stays ignored.
Active handwritten API consumers use generated clients and the shared transport/CSRF boundary.
No retired retention mutation consumer was found. No deployed API alias was removed.

These changes support ordinary staging deployment against the current schema. The intentional
compatibility effect is retiring redirects for old external retention descendants. This does not
change the current frontend's canonical links or expose mutation routes.

No business/privacy policy, assignment/ownership authorization, encryption secret, key-rotation
support or supported capability override was removed. Historical audit actions, capability-name
guards, authority-invalidation policy, provider-role persisted models, PG tombstones and ledger
consumers remain. Their names alone do not prove obsolescence.

The synthetic build's explicit `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1` permits existing provider mocks
only on loopback pages; realtime test sockets must also be loopback. Normal builds bake `0` into
that guard. The browser artifact is separate from the ordinary build and has no deployment consumer.
Browser harness requests to external hosts are blocked. No real provider is used in regression tests.

## Browser stabilization

See [browser evidence and limits](CANON-1B-Browser-Stabilization.md). Navigation now has a bounded
30-second budget, while interactions retain 12 seconds. Initial navigation failures retain their
fixture for screenshot/URL/readiness/request diagnostics and cleanup. Failures omit API bodies,
query strings and credentials from diagnostics. All 31 suites remain discoverable, both engines
required, with four non-optional shards each. No suite or safety assertion was skipped.

## Validation recorded before final CI

- Django system check: passed.
- Migration drift (`makemigrations --check --dry-run`): no changes.
- Committed OpenAPI consistency: passed; 38 OpenAPI contract tests passed.
- Changed backend Ruff lint and format: passed.
- Focused backend domain regression: 248 passed, including Routine encryption/rotation/migration,
  Activity, Audit, Assessment Records, Availability and Organization.
- Shared crypto/Routine compatibility: 85 passed.
- Frontend generation, lint and typecheck: passed. Complete unit run: 773 passed, zero skipped.
  Focused cleanup tests: 29 passed; provider seam tests: 43 passed.
- Frontend normal production build and synthetic production build: passed locally.
- Local production browser representatives: consent/transcription, fresh download, scheduled-end
  timing, dock navigation and context-denial checks passed on both engines; Notification realtime
  recovery passed on Chromium. Complete engine/shard results belong to the PR CI checks.
- Initial unit pass exposed four stale source/CI assertions (legacy redirect plus three development
  route-warmup checks). These were updated to verify route absence and compiled production testing;
  they did not represent new product defects. Final frontend unit/lint/type results are recorded by CI.

This document records local evidence, not a claim of exact-head CI success. The implementation PR's
attached checks are the authoritative final revision record: all eight browser jobs, frontend lint,
unit/type/build and full backend regression must complete successfully before readiness is claimed.
No earlier revision's result is substituted for the PR head. Any remaining CI failure must be
reported explicitly in the handoff.

## Remaining work and boundaries

[PG-1A reset handoff](CANON-1B-PG-1A-Reset-Handoff.md) identifies exact task names, ledger readers,
resurrection risks and stop/isolation/rollback prerequisites. CANON-1C owns incompatible ledger and
provider-role removal, renamed-capability baseline cleanup, migration consolidation and deterministic
seeder work. CANON-1D owns final regression and rebuild preparation. The reset is separately authorized.

No merge, deployment, live infrastructure access/modification, live migration, reset, Redis purge,
provider/object deletion, secret change, migration-history rewrite, dataset expansion or seeder
redesign occurred. The only database setup was task-specific disposable local test databases.
