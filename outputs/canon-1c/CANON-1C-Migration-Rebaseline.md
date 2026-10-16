# CANON-1C — Migration rebaseline

**RESET-ONLY / NOT SAFE FOR ORDINARY STAGING DEPLOYMENT.** The canonical baseline installs only
into an empty PostgreSQL database.

## Inventory recount (base `3ae47817`)

| Item | CANON-1 audit | Recounted at base | After CANON-1C |
| --- | ---: | ---: | ---: |
| Numbered COMPASS migration files | 102 | 102 | 26 |
| Apps with migrations | 27 | 27 | 26 (Documents has no models since its old 0002) |
| Frozen helper modules under `migrations/` | 8 | 8 | 0 (moved to `be/tests/encryption_oracles/`) |
| `RunPython` constructor sites | 47 in 36 files | 47 | 0 |
| `RunSQL` | 0 | 0 | 0 |
| Merge migrations | 1 (Good Moral 0005) | 1 | 0 |
| Cross-app dependency cycles needing a second migration | — | — | 0 |

## New graph

`makemigrations --name canonical_baseline` on the final models produced exactly one
`0001_canonical_baseline` per app with models, ordered by Django's autodetector (no hand-written
operations and no hand-edited dependencies):

`accounts`, `announcements`, `appointments`, `assessment_records`, `audit`, `authentication`,
`availability`, `call_slips`, `counseling`, `ecounseling`, `exit_interviews`, `feedback`,
`good_moral`, `graduate_tracer`, `guidance_messages`, `institutional_forms`, `inventory`,
`notifications`, `organization`, `platform_ops`, `privacy_governance`, `referrals`, `resources`,
`routine_interviews`, `service_catalog`, `student_support`.

Fresh `migrate` time on the local container fell from about 27 s (117 migrations) to about 8 s.
Migrations stay excluded from `ruff`, as before. `makemigrations --check --dry-run` is clean.

The distinct name is deliberate: had the baseline reused `0001_initial`, an old database's
`accounts.0001_initial` record would have made Django treat the new baseline as applied and run the
new code over the old schema.

## Fail-closed history guard

`compass/common/canonical_baseline.py` (registered from `AccountsConfig.ready`, the graph root):

- **System check `compass.E001`** (database tag): runs at the start of `migrate` and in
  `manage.py check --database default`. Any COMPASS migration recorded in `django_migrations` but
  not defined by the code is an error.
- **`pre_migrate` receiver**: raises `CommandError` for the same condition, so `migrate
  --skip-checks` cannot bypass it.

Both only read `django_migrations`. Rehearsed against Reference A: `migrate` refused with "102
pre-canonical COMPASS migrations (for example accounts.0001_initial)", also with `--skip-checks`;
nothing was applied. `tests/test_canonical_baseline.py` covers the fresh and refused cases.

## Disposition of historical custom operations

| Family (CANON-1 inventory) | Historical purpose | Canonical treatment |
| --- | --- | --- |
| Identity lifecycle / capability rename (`accounts` 0003, 0006) | Backfill lifecycle; rename capability codes and migrate grants/overrides | Dropped. Fresh rows are created with current codes by `sync_identity_policy`; `RETIRED_CAPABILITY_CODES` still removes retired codes if ever present. |
| Institutional Forms seeding (`institutional_forms` 0001, 0002, 0004–0007) | Seed CNSC-era form families and revisions | Dropped. `sync_institutional_forms` creates every canonical family and revision (CNSC inactive, UCN active). Tests already synchronized forms in `conftest.py`. |
| Confidential-content encryption (accounts, counseling, referrals, inventory, exit interviews, feedback, graduate tracer, routine interviews) | Add ciphertext, backfill, verify, fence writers, drop plaintext, reversible | Dropped. The baseline declares ciphertext-only columns and the same `*_present` checks. Envelope versions, bindings and key rotation are unchanged and tested against the relocated frozen v1 oracles. |
| Student Support / Inventory split (`inventory` 0004, `student_support` 0001) | Copy legacy PWD and parent-life status | Dropped; fresh `StudentSupportProfile` schema only. |
| Routine Interview academic year / optional Inventory (`routine_interviews` 0004) | Backfill year; refuse unbound rows on reverse | Dropped; optional Inventory and explicit academic year are model-declared. |
| Appointment/Counseling service name snapshots (0003) | Backfill snapshots | Dropped; snapshots are required fields written at creation. |
| Service booking capability / Counselor coverage (`service_catalog` 0004) | Map old policy | Dropped; `sync_canonical_services` creates the canonical Counseling Service. |
| E-Counseling media v2, reconciliation, webhook provenance (0002–0006) | Move provider artifacts/consent into custody model | Dropped as migrations; every resulting table, column, check and index is in the baseline (schema comparison: identical). |
| Documents branding profile (0001 seed, 0002 removal with refusal) | Seed then remove a profile | Dropped; no Documents model exists. |
| Privacy Governance scope/table removals (0003, 0004) and ledger (0005, 0006) | Remove retired tables with refusal; create/alter ledger | Dropped; retired tables never exist; the ledger is removed (PG-1A). |
| Call Slip issuance classification (0003) | Classify historical rows as LEGACY_UNKNOWN | Dropped; `issuance_mode` is set at creation. The enum value remains model-owned. |
| Good Moral merge (0005) and initiation provenance (0006) | Merge parallel 0004s; `db_default` LEGACY_UNSPECIFIED | Merge gone; the `db_default` is model-declared and reproduced identically. |

Nothing that defines a current invariant was dropped: every such invariant is a model field,
constraint, index or default and is present in the baseline (see the schema comparison).

## Retired migration tests

Tests that replayed historical migrations cannot run against a graph that no longer contains those
migrations. They were retired, and only those:

- Whole files removed: `test_capability_rename_migration.py`, `test_documents_migrations.py`,
  `test_ecounseling_media_v2_migration.py`, `test_ecounseling_reconciliation_migration.py`,
  `test_ecounseling_webhook_migration.py`, `test_privacy_governance_migrations.py`,
  `test_student_support_migrations.py` (12 test functions).
- From 17 mixed files, 62 test functions that used the `legacy` migration fixture, a historical
  migration module or `MigrationExecutor`, chosen from the actual failure set of a run against the
  canonical schema (1,324 runtime tests in those files passed). Orphaned migration targets and
  legacy row builders were pruned with them; `residual_encryption_helpers.py` keeps only its
  envelope helpers.
- Runtime behavior in the same files (encryption round trips, rotation, fail-closed decryption,
  authorization, API projections, frozen-oracle compatibility) is unchanged.

Replacement coverage: `tests/test_canonical_baseline.py` (one schema-only baseline per app, one
leaf per app, no drift, every declared constraint/index present, history guard).

## Bootstrap rehearsal on the fresh baseline

```
migrate                       41 migrations applied
check --database default      no issues
sync_identity_policy          roles 5, designations 2, capabilities 78; 95 role + 20 designation grants
sync_canonical_services       canonical Counseling Service created
sync_institutional_forms      families 8, revisions 13 (8 activated)
sync_organization_catalog     campuses 6, colleges 10, programs 38
rerun of all four             unchanged / already synchronized
```

Full transcript: [evidence/rehearsal-clean.txt](evidence/rehearsal-clean.txt).

## Future feature migrations

No active branch, PR or approved schema contract exists for Appointment Reminders, Service Catalog
Expansion or Shared Guidance Follow-Up Management. ADR-046 explicitly defers Appointment reminders,
and ADR-104/105/106 explicitly exclude follow-up, task and case models; the only catalog branch,
`feat/service-catalog-consolidation`, is the merged #185. No tables were invented for them. When they land on the reset-only branch they add ordinary
`0002_<name>` migrations on top of `0001_canonical_baseline`; the baseline is not regenerated.
This baseline is therefore **not** claimed to be the final defense-release schema.
