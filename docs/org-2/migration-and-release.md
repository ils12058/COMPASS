# Migration and release boundary

Additive [0003_catalog_resource_versions](../../be/compass/organization/migrations/0003_catalog_resource_versions.py)
depends on Organization 0002, adds default=1 positive integer versions to Campus/College/Program,
and adds three explicit >=1 CHECKs. Existing rows retain UUID/code/parent/name/status/policy/timestamps
and references. No baseline/ORG-1 migration is edited; the new migration is registered in
[canonical migration controls](../../be/compass/common/canonical_migrations.json). No live operation
or baseline reset occurs. Inconsistent recorded migration history still fails closed; the initializer
now translates Django InconsistentMigrationHistory into its existing typed incompatible-schema
refusal, preserving the command/error boundary when 0003 is recorded without its 0002 dependency. Populated upgrade tests compare every original field and SQL rejects zero.

Supported recovery retains schema/versions/Audit and uses an ORG-2-compatible image or rolls forward.
Do not reverse populated versions after edits: doing so loses concurrency evidence. Django's schema
reverse is a disposable-development mechanism, not approved operational rollback. A pre-ORG-2 image
can lack applied migration history and cooperating writers, and cannot safely maintain versions.
The migration supplies ORM default=1 rather than a promise that old unversioned writers may continue.
No release/cutover safety allowlist is weakened. ORG-1's unreviewed data-changing migration still blocks
routine deployment; adding ORG-2 source does not approve it.

Before activation, separately approve institutional Catalog ownership/delegation, rename evidence,
classification/levels and incomplete activation policy, pending-F4 treatment, open workflow
retirement/remediation and historical presentation, recovery procedure, manual UAT and rollout.
All old web/worker/Beat/CLI/seeder/external writers must be stopped/retired and compatible immutable
images/scripts/backups validated. Cooperative locks/receipt cannot fence old binaries or privileged
SQL. New user grants require explicit actual authorization; baseline role synchronization never
installs them. No real user/policy population has been inspected to infer readiness.

The protected services are source-ready for synthetic integration and ORG-3. Actual deployed
editing is not enabled. This task performs no SSH, deployment dispatch, live migration, real-data
inspection, actual grants, institutional edits or automatic merge. ORG-4 combined/browser/UAT
validation and separately approved operational cutover remain required.
