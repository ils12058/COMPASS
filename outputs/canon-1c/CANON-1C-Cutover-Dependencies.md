# CANON-1C — Cutover dependencies and CANON-1D handoff

**RESET-ONLY / NOT SAFE FOR ORDINARY STAGING DEPLOYMENT.** Nothing in CANON-1C was deployed, and
no live database, Redis, worker, object store, Daily resource, backup or secret was touched. The
reset itself is a separately authorized operation.

## What is incompatible with the current live staging

| Change | Why it cannot meet the live database |
| --- | --- |
| Migration graph replaced by `0001_canonical_baseline` per app | The live database records the 102 historical migrations; the history guard (`compass.E001`, `pre_migrate`) refuses to migrate or check it. `--fake`/`--fake-initial` must never be used to bypass this. |
| Ledger tables, tombstone tasks, fallback services and preflight command removed | Old workers or queued `compass.privacy_governance.*` messages would have no task; old restored captures would lose the ledger fence. |
| `compass.demo_seed` → `compass.staging_seed`; `DEMO_*` → `STAGING_SEED_*` | Old operator procedures and variables no longer exist. |
| Runtime-secret check rejects a long-running `STAGING_SEED_ENABLED` | Harmless for live staging, but the checker version must match the image. |
| Frontend/API | **No contract change.** OpenAPI and generated clients are unchanged; the only frontend change (the browser-test harness, [#249](https://github.com/ils12058/COMPASS/pull/249)) is staging-compatible. |

`.github/workflows/deploy-staging.yml` must **not** be used for this branch: it runs `migrate` and
synchronization while the old web/worker/Beat still run, and gates on a `staging` full-regression
SHA. The reset needs its own reviewed, non-standard procedure.

## Gates that must be evidenced before the canonical runtime is activated

These come from the PG-1A handoff and are prerequisites for the clean-reset strategy. Record
evidence for the exact environment and image; passing tests do not certify them.

1. **Freeze and inventory.** Freeze competing deploys. Inventory every web, worker, Beat, one-off
   process, host, Vercel/Droplet project and rollback path that can reach the old PostgreSQL,
   Redis or provider configuration.
2. **Old-runtime evidence while its schema exists.** Run `retention_decommission_status` (G1–G5)
   and the broker, worker and build checks in `be/docs/retention-disposition-runbook.md` on the
   **old** runtime. Preserve the output outside the repository. Account explicitly for any
   PROCESSING, QUEUED/APPROVED, FAILED or RECONCILIATION_REQUIRED case and their external effects.
3. **Stop old producers.** Stop old web, worker and Beat before activating the canonical image; do
   not force-kill a task whose provider operation may already have happened without recorded
   handling.
4. **Broker isolation.** Give the canonical runtime a separate, verified Redis namespace/instance.
   Inventory old queues, reserved/scheduled/ETA work, retries, unacked messages and persistence
   snapshots. No blind shared purge; old work is never restored into the new broker.
5. **Image and rollback fencing.** Old images, `.deploy.env` / `.deploy.previous.env`, manual
   rollback commands and schedules must not reach the new database or broker, and the canonical
   image must not run against the old database (the history guard enforces the latter at
   `migrate`/`check`).
6. **No historical data.** No old capture, room, receipt, recovery, rule, case or hold row and no
   pre-reset backup is imported or restored into the canonical database, including data-only
   imports, which the application cannot detect. Old backups stay retained and protected under
   their own policy; their restoration needs a separate compatibility plan.
7. **Provider and storage classification.** Inventory Daily rooms, recordings, transcripts and
   webhooks, and private object-storage objects and versions referenced by the old database.
   Classify them and obtain separate authority for any cleanup. Database recreation deletes none
   of them. New rooms get fresh UUID4 identities; confirm webhook signing configuration.
8. **Secrets.** Preserve or provision runtime secrets deliberately, including all nine domain
   keyrings. A database reset rotates nothing.

If any gate cannot be met, do not activate this branch; the handoff's protected deny-store
alternative would be required first.

## Proposed clean-rebuild sequence (for CANON-1D rehearsal, not executed)

1. Gates 1–3 complete; old runtime stopped; its database retained, not dropped.
2. New, empty PostgreSQL database and isolated Redis provisioned (gate 4).
3. Reset-only image built from the reviewed `canon/compass-clean-baseline` head; deployed with a
   dedicated procedure; build identity verified (`/api/v1/meta` `build_id`).
4. `migrate`, `sync_identity_policy`, `sync_canonical_services`, `sync_institutional_forms`,
   `sync_organization_catalog`, `check --deploy`, `check --database default`, `compass_doctor`.
5. Verify actual web/worker/Beat identities, the Beat schedule (no `compass.privacy_governance.*`
   entry), registered tasks, read-only retention oversight, consent and custody recovery.
6. `seed_staging_dataset seed` with `STAGING_SEED_ENABLED=true` and an operator-controlled
   `STAGING_SEED_EMAIL_DOMAIN`, one-off; then `verify` and `report`.
7. `issue-credentials` into a mounted `0700` operator directory; private delivery; delete the file.
8. Lift the deployment freeze only after the evidence above is recorded.

## What CANON-1D must verify

- The complete backend suite and both browser engines at the final reviewed revision of the
  reset-only branch, on CI configured for that branch (targeting `canon/compass-clean-baseline`).
- A disposable rebuild rehearsal following the sequence above, including history-guard refusal of
  a copy of an old-schema database and of `migrate --skip-checks`.
- Seeded-database browser walkthroughs of representative scenarios for every stakeholder role
  (the scenario matrix's initial states are database-verified; UI walkthroughs are not yet done).
- Role-scoped UAT, privacy, encryption, PDF and media regressions on the rebuilt environment.
- Non-destructive resource inventory and typed environment/revision gates; rollback fencing.
- Whether the three approved pre-defense features have merged; if so, their `0002_…` migrations on
  the baseline, and promotion of their `PENDING_IMPLEMENTATION` scenarios to executable with
  predicates.

## Requires later operator authorization

- Executing the live-staging reset, stopping services, provisioning databases/Redis, and any
  deployment of the reset-only image.
- Any deletion, expiry or cleanup of Daily resources, object-storage objects, Redis data or
  backups.
- Secret provisioning or rotation; enabling Daily for E-Counseling UAT.
- Seeding live staging, choosing the dataset email domain, issuing and delivering credentials, and
  the UAT email/provider testing plan.
- Merging the reset-only PR into `canon/compass-clean-baseline` (not into `staging`).

## Can be reviewed now

- [#249](https://github.com/ils12058/COMPASS/pull/249): the staging-compatible browser-test fix.
- The CANON-1C reset-only PR into `canon/compass-clean-baseline`: schema baseline, history guard,
  PG-1A removal, Staging Dataset v1, generated UAT documents and these reports.
