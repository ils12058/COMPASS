# Migration, initialization and recovery rehearsal

Result: PARTIAL operational readiness. Synthetic PostgreSQL migration/preservation and actual
dump/restore checks passed; no live database, actual backup system, deployed old-writer inventory,
production locale or compatible built deployment image was inspected.

Organization migrations remain unchanged:

1. `0001_canonical_baseline`: original identity/reference schema.
2. `0002_program_policy_and_catalog_initialization`: additive receipt/policy, frozen 38-entry exact
   identity backfill, versioned immutable array function and SQL checks; forward data step irreversible.
3. `0003_catalog_resource_versions`: additive version=1 and positive CHECKs for all three entities.

Existing migration tests run disposable PostgreSQL upgrades with renamed/inactive entities,
additional and changed identities, unknown policy and historical FK fixtures. The two 0002 cases
cover normal upgrade and injected atomic failure/retry; one 0003 case compares all original fields,
positive versions and repeat migration. Backfill does not top up missing rows, create a receipt,
normalize adopted values or change timestamps/UUIDs/parents/history. Historical migration fixtures
include ciphertext sentinels; real encrypted Inventory and actual PDF preservation are separate tests.

Fresh current-schema migrate, seed and check also ran on `compass_org4`: seed changed=True, repeat
check changed=False. The real integration fixture separately exercised deliberate empty adoption
and persisted an ADOPTED receipt. Existing Catalog tests cover populated adoption, repeated
seed/adopt/check/legacy alias, initialized-empty receipt, populated-without-receipt refusal, invalid
migration history, Audit rollback and two independent-connection seed/adopt races.

Supported new-runtime paths contain no destructive canonical reconciliation. The frozen registry
is used for explicit empty installation seed only; an additional database Program is not retired
because it lacks a Python entry. Seeder/deployment regressions pass repeat-preservation/preflight
and refuse unavailable synthetic prerequisites rather than silently reactivating them.

## Actual post-edit backup/restore

After the complete authenticated run, the task-owned Django server stopped. A PostgreSQL custom
dump of `compass_org4_browser` captured the already-confirmed Catalog edits and Audit together.
It was restored into fresh `compass_org4_recovery` on the same isolated cluster. The test helper's
backup-manifest action canonicalizes and hashes every row of every introspected application table,
without printing row contents. **All 117 tables / 514 rows matched exactly.** This includes Catalog
UUID/code/name/parent/status/policy/version, initialization receipt, capability assignments, Audit,
authentication fixtures and submitted encrypted Inventory/relationship references.

Using the compatible current source against the restored DB, Inventory snapshot comparison passed
and initialization check recognized ADOPTED unchanged. Repeating seed/adopt and the legacy sync
alias produced no Catalog or Audit changes: the entire all-table manifest still matched.

A later protected synthetic Program rename committed on the original source DB after the backup.
The manifest then differed in Program and related actor/Audit/session fixture tables. This
demonstrates that restoring a consistent backup is insufficient to preserve later institutional
edits: its recovery point must be reconciled against trustworthy later commits before reopening
mutation access. No automatic reconciliation or production recovery gate was invented. The test
did not replay those later events into the restored DB or claim that doing so was already approved.

Executed native tools (loopback cluster only):

```sh
pg_dump -h 127.0.0.1 -p 56649 -U compass -Fc -f /private/tmp/compass-org4.I9H5cI/confirmed-edits.dump compass_org4_browser
createdb -h 127.0.0.1 -p 56649 -U compass compass_org4_recovery
pg_restore -h 127.0.0.1 -p 56649 -U compass -d compass_org4_recovery --exit-on-error /private/tmp/compass-org4.I9H5cI/confirmed-edits.dump
```

`backup-before.json`, `backup-restored.json`, `backup-after-repeats.json`, `backup-later.json` and
`recovery-results.json` hold local hashes/results, not production rows. The private test state
retains fixture keyrings for encrypted-value checks. This rehearsal does not establish external
key-backup handling, RPO/RTO, storage restoration or real institutional backup responsibility.

## Deployment and rollback limits

The 26 canonical baseline hashes and additive registration remain intact. ORG-1 0002 is still
absent from routine `REVIEWED_MIGRATIONS`; its explicit data migration is deliberately refused by
ordinary deployment preflight. Tests do not add a digest to authorize it. Existing bootstrap,
staging seeder, legacy alias and deployment validation suites ran synthetically; no script was
executed against a deployed host and no workflow was dispatched.

Supported operational recovery retains the additive schema, all versions/receipts/policies,
historical FKs and consistent Audit, using an ORG-aware compatible image or roll-forward. A pre-
ORG-1/2 binary is unsafe after edits: it can lack applied migration history, database policy readers,
version semantics and cooperative writers, and may restore destructive synchronization. Do not
reverse populated columns or use old sync to repair definitions. Cooperative locks/receipts cannot
stop old processes or privileged SQL. Retire web/worker/Beat/CLI/seeder/external writers and verify
immutable compatible artifacts under separately approved cutover authority.
