# Deployment, old-writer retirement and recovery

ORG-1 is source implementation plus disposable validation. **No operational cutover is authorized.**
D1/D2/D8/D19 and related institutional decisions remain approval-dependent. No deployed data, old
process, external job, backup or recovery image was inspected here.

The new data migration/function/constraints are deliberately absent from the routine deployment
`REVIEWED_MIGRATIONS` pins. Existing database preflight refuses unreviewed data-changing operations.
A regression proves ORG-1 is refused under that policy. A future independently reviewed cutover must
approve the exact migration/procedure; do not add a digest merely to make ordinary deployment pass.
The workflow's explicit catalog action does not bypass that guard or any initialized-storage gate.

Minimum compatible source contract is Organization migration
`0002_program_policy_and_catalog_initialization`, database-policy readers and the explicit
initializer/receipt check from ADR-ORG-1. The initializer rejects missing, unknown or unapplied
Organization migration states before bootstrap. Read-only deployment preflight also checks migration/receipt table agreement,
requires explicit seed/adopt for an uninitialized catalog, and refuses populated seeding or empty
normal-deployment adoption before schema changes. Existing migration-history preflight rejects old
images lacking applied migrations. Neither protects against an already-running old binary or an
operator directly invoking its destructive sync with shared credentials.

Before any approved actual cutover:

1. Inventory and retire old web, worker/Beat, one-off CLI, host timers and external synchronization
   scripts; prevent restarts/old command execution. Validate immutable candidate image and scripts.
2. Verify a consistent catalog/Audit backup and a compatible recovery image; rehearse using synthetic
   or separately authorized scrubbed data. No live row counts are inferred from test fixtures.
3. Use the existing coordinated application stop/restart boundary. Recheck the migration plan after
   stopping old processes; preserve volumes, keys, confidential ownership and unrelated configuration.
4. Apply the reviewed additive migration. Do not run old sync beforehand “to normalize” approved data.
5. Deliberately adopt populated data, or explicitly seed only a genuinely empty fresh installation.
   Check schema and receipt before new processes start. Default repeated bootstrap is check-only.
6. Validate policy projections, saved facts and routing; record compatible release evidence. Editor
   authority and institution policy activation remain later separately authorized decisions.

The Catalog receipt and initialization advisory lock are cooperative integrity mechanisms, not an
old-binary fence. If old writers cannot be reliably retired, activation remains blocked pending a
separately reviewed credential/DB-enforced boundary. No speculative authority state machine or
partial trigger/session-variable fence is implemented.

Rollback after successful adoption must retain additive policy columns, receipt, UUIDs, Audit and
approved names/statuses. Use an image that understands this contract or roll forward. Never restore
old reconciliation, drop populated policy, regenerate UUIDs or overwrite newer official data with
seed constants. Atomic forward failure leaves the migration unapplied and retries safely; the
historical data operation is intentionally irreversible. Disaster recovery restores DB/Audit and a
compatible image together, then reconciles later approved changes from trustworthy evidence.

No test here establishes deployed old-writer exclusion, production locale compatibility, successful
live backup recovery, institutional UAT or permission to deploy. The test database is UTF8/C locale;
matching the actual deployment's collation remains a separate rollout check.
