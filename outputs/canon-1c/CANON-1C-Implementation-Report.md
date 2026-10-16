# CANON-1C — Implementation report

**RESET-ONLY / NOT SAFE FOR ORDINARY STAGING DEPLOYMENT.** Nothing was merged or deployed. No live
database, Redis, worker, object store, Daily resource, backup or secret was touched, and the
live-staging reset was not executed.

## Starting state

- Fetched `origin/staging` = `3ae47817923849eef6cd3fd1ad15e0a43bd79568` (CANON-1B, #248) on
  2026-10-16; unchanged at PR time. No open PRs; existing worktrees were left untouched; no
  branch, PR or approved schema contract existed for the three pre-defense features (ADR-046
  defers reminders; ADR-104/105/106 exclude follow-up models).
- Isolated worktrees: `../COMPASS-CANON-1C` (implementation) and `../COMPASS-CANON-1C-WEBKIT`
  (staging-compatible browser fix). Disposable PostgreSQL 17.11 and Redis 8.10.1 containers on
  `127.0.0.1:55432` / `:56379`, separate from the user's compose stack.

## Branches and PRs

| Item | Value |
| --- | --- |
| Staging-compatible browser fix | [#249](https://github.com/ils12058/COMPASS/pull/249) `fix/canon-1c-webkit-contextual-messages` → `staging`, head `27336d87`, CI success (run 38902560551) |
| Reset-only integration branch | `canon/compass-clean-baseline`, created on origin at `3ae47817` |
| Reset-only PR | [#250](https://github.com/ils12058/COMPASS/pull/250) `codex/canon-1c-schema-uat-dataset` → `canon/compass-clean-baseline` |
| Commits | `703909b8` browser fix (cherry-pick of #249) · `80c80d75` canonical baseline and PG-1A · `c50b53e4` Staging Dataset v1 · `261119e7` reports and UAT documents · this report |

## Implementation

**Schema** ([details](CANON-1C-Migration-Rebaseline.md), [comparison](CANON-1C-Canonical-Schema-Comparison.md)):
102 historical migration files and 8 frozen helpers replaced by 26 schema-only
`0001_canonical_baseline` migrations (no `RunPython`/`RunSQL`, no cycles). Against an empty
database the old and new graphs produce identical tables, columns, defaults, constraints and
indexes except the 3 retired ledger tables and one renamed auto-generated check constraint. A
history guard (`compass.E001` check and `pre_migrate` receiver) refuses databases with
pre-canonical migration records; `deploy-staging.yml` refuses revisions containing the baseline.

**PG-1A** ([verification](CANON-1C-PG-1A-Decommission-Verification.md)): models removed —
`OperationalRetentionRule`, `DispositionCase`, `DispositionHold`; also removed: the three tombstone
tasks, five 409 fallback services, `retention_decommission_status`, and the E-Counseling ledger
query arms. All remaining disposal, terminal, quarantine, consent, claim, custody and unknown-room
fences are preserved and tested.

**Seeder** ([design](CANON-1C-Staging-Dataset-v1-Design.md)): `compass/demo_seed` (26 modules,
`seed_demo_staging`, Dataset v2 and its upgrade path) replaced by `compass/staging_seed`
(`seed_staging_dataset` with `seed`, `verify`, `report`, `issue-credentials`), Dataset version 1,
`STAGING_SEED_*` configuration, ADR-116 and `be/docs/staging-dataset-v1.md`.

## Dataset

| Measure | Value |
| --- | --- |
| Synthetic Students | **100** (11 rich scenario, 24 action-ready, 65 background) |
| Staff accounts | **13** (10 UAT-ready, 3 restricted) |
| UAT-ready accounts | **45**: 35 Students; IT Administrator 2, Head Guidance Counselor 1, Guidance Counselor 3, Guidance Services Staff 2, DPO 2 |
| Background / restricted | 64 / 4 (disabled former staff, disabled Student, unassigned Counselor, undesignated officer) |
| Lifecycle | 86 CURRENT, 10 GRADUATED, 4 FORMER |
| Campuses / Colleges / Programs | 6 / 9 / 30, all canonical |
| Scenarios | 91: 88 executable, 3 pending implementation |

Executable scenarios by role (88): Student 39, Guidance Counselor 20, Head Guidance Counselor 7,
Guidance Services Staff 6, IT Administrator 5, DPO 5, plus 6 negative-authorization scenarios
(Student 2, Guidance Counselor 2, Guidance Services Staff 1, Institutional Officer 1); 3 pending. Sample recommendations from the
[selection guide](uat/UAT-ACCOUNT-SELECTION-GUIDE.md): one evaluator per Counselor
(`counselor_a`, `counselor_b`, `counselor_c` own disjoint caseloads); Student evaluators take an
`ar_…` account each (one pending action apiece); `head_guidance` is shared, so its mutating
scenarios are serialized; restricted accounts only for `NEG-…` scenarios.

Idempotency and reconciliation: first seed 32 s; rerun 0 created / 399 reused; evaluator
cancellations, requests and password changes survive reruns; strict verification fails visibly
on changed states while `--allow-uat-changes` reports them as warnings.

## Validation

| Check | Result |
| --- | --- |
| Fresh migration (empty database) | 41 applied; `check --database default` clean; old-history database refused (also with `--skip-checks`) |
| Schema verification | 95 shared tables identical; differences classified ([evidence](evidence/)) |
| Seeder verification | `verify` PASSED, 1,447 checks, 0 failures ([verification](CANON-1C-Staging-Dataset-v1-Verification.md)) |
| Documentation consistency | Catalog, CSV, guide, matrix, template and summary generated from manifest plus passing verification; counts agree (113 / 100 / 88 / 3); secret scan clean |
| Backend tests | Local full suite 4,452 passed, 0 failed ([regression report](CANON-1C-Regression-Report.md)) |
| Frontend / browser | #249 full browser matrix success; no application or contract change |
| Remaining failures | None observed |

## Cutover

- **Reviewable now:** #249 (staging-compatible) and #250 (reset-only).
- **Incompatible with live staging:** the migration graph, removed ledger and tasks, seeder package
  and variables (see [cutover dependencies](CANON-1C-Cutover-Dependencies.md)). No API change.
- **CANON-1D must verify:** complete backend and browser matrix at the final reset-only revision;
  a disposable rebuild rehearsal including history-guard refusal; seeded-database browser
  walkthroughs per role; privacy/encryption/PDF/media regressions; resource inventory, revision
  gates and rollback fencing; the state of the three pre-defense features.
- **Needs operator authorization:** the live reset itself, service stops, database/Redis
  provisioning, any provider/storage/backup cleanup, secrets, enabling Daily, live seeding,
  credential issuance and delivery, and merging #250.

No live-staging rebuild or UAT execution is claimed.
