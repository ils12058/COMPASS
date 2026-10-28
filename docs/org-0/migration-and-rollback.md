# Migration, compatibility and rollback

**PROPOSED DESIGN**, grounded in the current graph and deployment sources. No new migration or
operational migration is executed by ORG-0; existing baseline migrations run only inside isolated
pytest databases. No live database is inspected.

## Additive schema and backfill sequence

Current Organization graph has only `0001_canonical_baseline`; `0002` is available at inspected SHA.
Do not edit that baseline or its hash. Add `0002_program_policy_and_catalog_initialization` (working
name) and register it in `be/compass/common/canonical_migrations.json` additive_migrations. Recheck
integration before selecting the identifier; later ORG-2 resource-version fields would normally
use `0003`, subject to then-current graph.
Sources: [be/compass/organization/migrations/0001_canonical_baseline.py:9](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/migrations/0001_canonical_baseline.py#L9);
[be/compass/common/canonical_migrations.json:30](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/common/canonical_migrations.json#L30);
[be/tests/test_canonical_baseline.py:68](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_canonical_baseline.py#L68);
[be/README.md:13](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/README.md#L13).

Smallest proposed foundation:

1. Add nullable classification, non-null status default PENDING_POLICY and nullable small-integer
   array on Program; enforce the explicit constraints in [Program policy](program-policy-design.md).
2. Add one narrow CatalogInitialization singleton (initialized_at, initialization source
   SEEDED/ADOPTED, nullable baseline_version). A fixed-key constraint and uniqueness make it a
   receipt, not an arbitrary record collection or rolling authority state machine. The receipt
   disambiguates first installation from later deliberately empty tables and serializes adoption
   evidence; it cannot stop an older binary that does not read it.
3. In the same additive migration, use historical models and a **frozen** exact-code 38-Program map
   to backfill matching existing rows' new fields only. Never import the live registry or call its
   sync. Default unresolved values on unmatched rows. Do not seed missing entities during upgrade.
4. Leave the receipt absent during schema/backfill migration. For an existing nonempty catalog,
   an explicit adoption command then writes an ADOPTED receipt and bounded Audit together, without
   claiming the catalog matches the seed. Empty catalog stays uninitialized for explicit seed or
   reviewed empty-adoption choice. Do not import runtime Audit services into historical migrations;
   schema/backfill execution is migration evidence, while seed/adoption commands own domain Audit.
5. New explicit initialization command takes the catalog advisory gate, checks receipt and table
   emptiness, then creates the frozen baseline rows **with persisted metadata**, seed receipt and
   Audit atomically. Explicit empty adoption is possible only as a reviewed operator choice, never
   fallback from failed seeding. No receipt + any existing row means refuse seed and require adoption.
6. Retain the old sync command/function name only as a documented seed-only compatibility alias or
   fail-closed retirement stub. No reachable `_repair_row`/unknown-retirement reconciler survives.
   Repeated initialization with a receipt checks/reports data and never repairs names/status/counts.
7. Convert API, Inventory, F4, degree options, seeder prerequisites/verify/report readers together.
   Freeze constants for migrations/fixtures only. No dual DB-read/Python-fallback live mode.

For very large populations ORG-1 must inspect an authorized rehearsal copy to size the transaction;
there is no production row estimate in this audit. Use bounded update batches inside the migration's
atomic boundary only if needed. Foreign keys should prevent broken references; inconsistency means
stop preflight, not reconstruct identity from names. Preserve Program updated_at if it represents
ordinary catalog edits; a migration queryset update of only new fields avoids auto_now changes.

## Before/after comparison artifact

Produce synthetic/rehearsal evidence containing UUID, code, name, parent UUID/code chain, active flag,
new classification/status/levels and resource timestamps, plus representative protected consumer
FKs and saved course/certificate text. Compare separately:

- matched canonical identities, including renamed/inactive ones;
- additional Programs, changed-code/parent identities, missing seed rows;
- configured Bachelor policy and pending postgraduate policy;
- submitted Inventory saved course/year, pending/issued F4, reported/issued F6;
- current affiliation/responsibility/supervision and Tracer history;
- inconsistent active ancestry, invalid codes and duplicates as preflight findings.

Success means no identity/name/status/parent/history changes, unchanged metadata responses for exact
matches, explicit unresolved metadata for additional rows, preserved F4/F6 behavior, and a seed that
runs only on a deliberately fresh catalog. Do not “repair” manually modified names during measurement.

## Fresh and populated database lifecycles

| State/action | Proposed outcome |
|---|---|
| Fresh canonical-lineage DB | Apply existing baseline + new additive migrations, explicit initialize → 6/10/38 baseline with metadata; later additions unrestricted by that count |
| Existing canonical-lineage DB | Additive metadata backfill/adoption only; existing UUIDs/status/names retained |
| Existing manually modified names | Retain names, backfill exact-code metadata; no approval inferred from the name |
| Existing noncanonical rows | Retain all fields and relationships; unresolved policy report, not deactivation |
| Existing inactive Programs | Remain inactive even when baseline says active |
| Empty catalog with existing receipt | No automatic reseed; recover/inspect intentional state |
| Repeated start/deploy/seed | No canonical mutation; initialization receipt is durable; seeder fixture conflicts reported without catalog repair |
| New baseline correction | Change future-install seed version only; existing catalog changes via focused approved admin/import procedure |
| Pre-canonical migration history | Current guard refuses; no fake migration, baseline rewrite, reset or data conversion under ORG |

Source for the present lineage guard:
[be/compass/common/canonical_baseline.py:44](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/common/canonical_baseline.py#L44).

## Cutover: one authority, no mixed-version editing

The reviewed deployment script stops old application containers and disables their restart policy
before migration; web, worker and Beat come up only after bootstrap/checks. It also rechecks
preflight after stopping processes. This is a useful existing maintenance boundary, not proof every
external writer is stopped. Current `.github/workflows/deploy-staging.yml` is manual and targets
staging; ORG-0 does not dispatch it.
Sources: [be/deploy/staging/deploy.sh:85](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/deploy/staging/deploy.sh#L85);
[be/deploy/staging/deploy.sh:88](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/deploy/staging/deploy.sh#L88);
[be/deploy/staging/deploy.sh:95](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/deploy/staging/deploy.sh#L95);
[.github/workflows/deploy-staging.yml:4](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/deploy-staging.yml#L4).

Recommended release boundary (ORG-1):

1. Review the replacement ADR and operator inventory of web/worker/Beat, one-off jobs, old release
   directories, host timers, deployment scripts, seeder commands and direct database writers.
2. Verify recoverable DB/Audit backup and immutable compatible image. Rehearse on synthetic or
   separately authorized scrubbed data. Catalog editor/grants remain disabled/absent.
3. Stop all old application processes and one-off reconciliation writers; disallow restarts and
   command execution from pre-ORG releases. Coordinate credential/access retirement if necessary.
4. Apply additive schema/backfill using the new migration-capable release; do not run old sync
   before/after migration “to clean up” the data. Adopt/initialize explicitly.
5. Start only the new release with all live metadata readers converted and recurring writers
   removed. Repeated bootstrap and dataset preflight must preserve approved edits/retirements.
6. Verify startup/deployment compatibility and stored facts before later ORG-2/3 activation. Record
   a minimum compatible release/schema in deployment preflight and approved rollback runbook.
7. Only a later separately approved operational action assigns catalog-editor authority. ORG-4/UAT
   approval does not follow automatically from a passing migration rehearsal.

**Rolling upgrade answer:** disallow an old/new overlap for authority migration. Even old read-only
web processes use Python F4 policy and degree options and would disagree about newly approved data.
A frontend feature flag cannot protect the DB, and a boolean/singleton checked by new code cannot
fence an old sync function. The cooperative concurrency gate in ORG-2 also cannot fence old code.

A DB-backed authority **writer fence is not required for the recommended fully stopped cutover**,
because the supported deployment already offers process exclusion and ORG-1 ships without user CRUD.
This recommendation is conditional on demonstrable old-writer retirement and enforceable image/CLI
rollback controls. If the operator cannot guarantee it (shared credentials, uncontrolled old jobs,
mandatory rolling deploy), stop activation and design a database-enforced boundary first: separate
revoked old writer credentials or a carefully reviewed DB permission/trigger boundary with bypass
controls. A marker alone is not that boundary; a trigger over all writes using an easily spoofed
session variable would be incomplete. Do not add a speculative multi-stage authority state machine.

## Rollback and recovery

| Failure point | Safe response |
|---|---|
| Preflight/schema validation failure before commit | Keep old processes stopped; inspect bounded failure, restore compatible previous deployment only if DB remains unchanged and no new admin edits exist |
| Atomic additive migration failure | Verify transaction rolled back columns/backfill/receipt consistently; test fault injection; no partial mutation or fake migration |
| After successful additive migration, before CRUD | Prefer compatible bridge/new-image rollback or roll-forward. Old binary may reject unknown additive migration history and still has destructive writers |
| After administrator edits | Roll forward or run a catalog-aware compatible rollback image against retained schema. Never restore Python reconciliation or reverse away persisted policy |
| Database/Audit damage | Restore consistent backup plus receipt and minimum compatible release, reconcile later approved edits from trustworthy evidence; no UUID regeneration |
| Bad individual name/status/policy edit | Audited corrective mutation with expected version and impact review; no source-code seed reset |

The current history guard treats applied COMPASS migrations missing from the running source as
unsupported history. Thus a pre-ORG binary running `check --database default`/`migrate` against
ORG-1's additive migration can fail even apart from policy incompatibility. It is not a complete
runtime old-process fence: an already-running process or direct ORM command could still write.
Source: [be/compass/common/canonical_baseline.py:29](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/common/canonical_baseline.py#L29).

Data backfill reverse should not erase administrator configuration or infer old policy. Recommend
forward-only policy data migration with an explicit irreversible reverse boundary; schema remains
additive during supported operational rollback. If reversible development teardown is implemented,
it must be restricted to disposable fixtures before activation, never sold as production rollback.
After catalog changes, reverting to pre-ORG runtime is unsupported. Snapshotting DB and code together
is recovery planning, not automatic permission to restore over newer official data.

## Required PostgreSQL rehearsal matrix (future ORG-1/4)

| Scenario | Required proof |
|---|---|
| Fresh DB migrate + explicit initialize | Metadata seeded; one receipt/Audit; no import/startup writes |
| Populated 0001 → 0002 | UUIDs/parents/names/status/FKs unchanged; exact backfill |
| Renamed/inactive canonical rows | Preserved after migration, deployment alias and repeat seed |
| Additional Program / missing canonical identity | Unknown pending retained, no canonical insertion/retirement |
| Changed code/parent / inconsistent chain | No name inference; explicit preflight/report; no automatic transfer |
| Duplicate code / malformed levels / raw SQL bypass | DB constraints reject invalid rows without partial change |
| Historical Inventory/Tracer/issued F4/F6 | Saved facts/reprints unchanged, authorized historical reads intact |
| Injected migration/Audit failure | Atomic rollback; retry cannot double-seed |
| Concurrent first initialization | Gate+receipt prevent duplicate baseline/partial graph |
| Deployment/CLI retry after admin edits | No restore/reactivation/deactivation |
| Old-image startup and old direct-sync attempt | Operational fence blocks unsupported execution; document negative controls |
| Recovery/compatible rollback after edited catalog | Persisted policy and approved additions survive; no old reconciliation |

These are **PROPOSED DESIGN tests, not executed results**. Existing graph/constraint/catalog tests
in [validation](validation.md) establish the baseline only. No deployed data access is needed to
implement these synthetic tests; actual operational readiness is a separate authorized evaluation.
