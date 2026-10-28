# Explicit bootstrap, deployment and seeder

Commands require exactly one explicit action:

```sh
python manage.py initialize_organization_catalog --seed
python manage.py initialize_organization_catalog --adopt --reference '<approved bounded reference>'
python manage.py initialize_organization_catalog --check
```

These are operator examples, not permission to run them on deployed data. Model/schema checks run
first. `--seed` requires no receipt and all Catalog tables empty. It atomically creates the frozen
6/10/38 baseline with policy, SEEDED receipt and Audit. `--adopt` requires existing rows and only
adds an ADOPTED receipt/Audit; it never fills missing entities or changes names/status/policy.
Empty adoption requires the additional explicit `--allow-empty-adoption`. No action falls back to
another after failure. References are bounded to 160 plain-text characters.

With a compatible schema and existing receipt, all actions return existing state unchanged. The
old `sync_organization_catalog` command/function is seed-only, with the same populated-data refusal.
It cannot reconcile names/statuses/policy. A receipt on empty tables prevents automatic reseeding.
The singleton plus transaction advisory lock ensures concurrent seed/seed or adopt/adopt calls
produce exactly one receipt and Audit; repeated invocations produce none.

[deploy.sh](../../be/deploy/staging/deploy.sh) no longer calls old sync in its loop. It validates
ORG_CATALOG_ACTION (check/adopt/seed, default check), invokes initializer with a deployment-reference
SHA, then checks receipt before starting applications. The workflow offers the explicit bounded
choice and [orchestrator](../../.github/scripts/run_staging_deploy.py) validates/passes it. Existing
stop/restart, migration, image, volumes and preflight guards remain. The migration is not routine
allowlisted: selecting adopt/seed does not bypass migration review or authorize cutover.

[staging_seed/seed.py](../../be/compass/staging_seed/seed.py) checks prior catalog initialization
before syncing unrelated identity/forms/service configuration. It never invokes catalog seed/sync.
Personas resolve required parent-qualified, active identities; unavailable fixtures fail clearly.
Program selection now uses the shared active-ancestry helper. Verify checks the receipt rather than
requiring all 38 seed offerings active. Persona-specific verification remains dataset consistency,
not a live catalog whitelist. Report College names resolve the persisted parent-qualified fixture
College; static narrative/codes remain explicitly synthetic scenario facts, never authority.

Tests execute the actual initializer commands extracted from deployment source against synthetic
PostgreSQL, rename/retire/change policy/add rows, repeat all actions/legacy alias and compare stored
values. Full dataset replay refuses a retired fixture and leaves the changed catalog untouched.
Seed prerequisites repeated separately also preserve edits/additions. Verify's read-only transaction
and full seeder external-boundary prohibitions remain covered. Nothing deploys or invokes real SSH.
