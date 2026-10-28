# Catalog authority

The persisted Campus → College → Program hierarchy is the only live definition source. Ordinary
names/statuses and Program policy no longer reconcile with Python. Existing UUIDs, protected FKs
and operational relationships stay intact. No code/parent transfer or catalog editor is introduced.

[canonical.py](../../be/compass/organization/canonical.py) is frozen installation baseline
`ucn-2026-09-27-v1`. Its tuples, identity indexes, expected counts and legacy metadata lookup are
seed/fixture input only. [bootstrap.py](../../be/compass/organization/bootstrap.py) uses it solely
inside an explicitly requested empty seed; it contains no name repair or unknown-row retirement.
The migration owns an independent frozen policy map and imports no live registry/policy definitions.

[CatalogInitialization](../../be/compass/organization/models.py) is one fixed-key receipt, not a
CODE/DB toggle. It records SEEDED/ADOPTED, timestamp, nullable baseline version and bounded reference.
SQL constrains the key/source shape. Supported application save/update/delete paths refuse receipt
replacement/removal. No HTTP mutation or Django Admin editor exposes it. Privileged SQL remains
outside this application immutability boundary; it is not a database-security writer fence.

The initializer verifies applied/known Organization migrations, takes a PostgreSQL transaction-level
advisory lock, rechecks the singleton and commits seed/adoption plus synchronous Audit atomically.
A repeated call returns the existing receipt without touching catalog rows or creating another
Audit event. A previously initialized empty catalog is not automatically repopulated.

New system Audit actions are `organization.catalog_initialized` and `organization.catalog_adopted`.
Old `organization.catalog_synced` events remain historical evidence; no new reconciliation emits it.
No-op initialization creates no event. Audit failure rolls back all initialization changes.

The legacy function/command remains a documented seed-only compatibility alias. With no receipt it
can seed only three empty tables; a populated catalog requires explicit adoption. With a receipt it
returns unchanged state. The old private reconciler is removed rather than hidden behind a flag.

Old deployment calls are replaced with explicit action/check; the seeder checks the receipt and
fixture prerequisites. Startup, requests, migrations and Beat do not secretly initialize the catalog.
No installed-state receipt can prevent an old process from running old code; actual writer retirement
and a compatible release floor remain operator/approval obligations.
