# Migration, scoped cutover and recovery

## Implemented migration behavior

`accounts.0002_student_session_summary_capabilities` locks relevant policy tables, preflights all three old/new code pairs, and refuses collisions. Existing Capability IDs are updated; RoleCapability, DesignationCapability and UserCapabilityOverride rows keep their identities and fields, including explicit REVOKE and expiry. Affected users include role, designation and override holders; the normal authentication invalidation service revokes their sessions/trusted state and pending login challenges with safe audit reasons. No default grant is invented by migration. Normal identity synchronization follows migration.

`counseling.0002_student_session_summary_contract` depends on that conversion and Notification baseline. It locks the legacy resource tables and refuses remaining legacy summary/publication Notification rows. Then Django RenameModel renames the table, changes the Encounter reverse relation, and replaces the ciphertext-presence constraint. PostgreSQL retains generated names during table renames, so the migration also explicitly renames its PK, Encounter unique constraint/backing index, and Encounter FK to canonical resource names. It never decrypts, deletes, blanks or silently reinterprets old rows. Django's normal RenameModel content-type handling applies; a model-state/disk-only check is supplemented by actual PostgreSQL migration runs. Both migrations are irreversible by default; recovery must be coordinated, not an automatic reverse DDL/data rename.

New migrations are registered in `compass/common/canonical_migrations.json`; immutable baseline hashes/files remain unchanged. Pre-canonical databases remain refused by the existing history guard. Do not fake/squash the baseline.

## Local rehearsal scope

Tests explicitly create a dedicated local PostgreSQL cluster and separate randomly named disposable databases, install the canonical graph, populate the historical state, and apply the forward plan. They exercise populated refusal, scoped cleanup, draft/publication regeneration, orphan Notifications, claimed email/Push, changed plans, missing disposal approval, mixed capabilities and interrupted transactional deletion. The ordinary pytest database also installs the real final graph; no `--nomigrations` shortcut is used as migration proof. These results are **not** a staging migration.

The full synthetic dataset test removes only its four approved summary fixtures and their publication Notifications, regenerates through the new adapter, repeats safely, verifies the dataset, and proves Encounters, account passwords and existing Audit IDs survive. The normal seeder skips existing story markers, so it alone cannot repair a resource-scoped purge. The dedicated regeneration command handles that case.

## Future deployed execution — separate authorization required

1. Record approver, exact matched backend/frontend/runtime-manifest revisions, environment/database identity, maintenance window, retention/disposability decision and recovery owner. A label such as staging never proves disposability. Any retained record blocks this cleanup route and requires a separately verified original-context converter. No replacement synthetic content may be invented for retained records.
2. Provision the new independently protected keyring using the reviewed secret-file inventory. Verify parser, permissions, ordered key recovery and non-reuse without printing values. Fresh install needs only new configuration; archival old keys may be needed for backups, but are not runtime fallbacks.
3. Drain and stop **old web, workers, Beat, realtime consumers and all producers** before changing schema/policy/content. Fence browser requests and delayed summary work. Snapshot queue/claim state and preserve unrelated work. Do not blanket-purge a broker. Claimed deliveries block the command even when the claim expiry has passed; drain/reconcile them under the approved operations procedure first.
4. Verify the canonical lineage and baseline hashes. Obtain a protected consistent recovery snapshot before mutation (or documented acceptance of loss for explicitly disposable fixtures). Preserve append-only audit evidence separately.
5. Run candidate tooling under new configuration **in maintenance, before the new schema migration**. Preflight uses historical migration models, not the active content adapter, and prints only a digest. The plan contains UUIDs, publication/business timestamps and delivery status/claim-expiry metadata; no body, ciphertext, address, claim credential or key. Secure these files as operational records.

```sh
python manage.py preflight_student_session_summary_cutover --plan-file /protected/summary-scope.json
```

6. Review every selected summary, legacy publication Notification and dependent EmailDelivery/PushDelivery, including orphan legacy references. Create a separate approval JSON. `scope_digest` must match the generated plan. The approver is attesting to **that exact database and disposable scope**, not authorizing a general reset:

```json
{"scope_digest":"DIGEST_FROM_PLAN","approved_by":"AUTHORIZED_OWNER","disposable_synthetic":true,"consumers_stopped":true,"regenerate_known_fixtures":true}
```

7. Only after separate authorization, execute:

```sh
python manage.py preflight_student_session_summary_cutover --plan-file /protected/summary-scope.json --approval-file /protected/approval.json --execute
```

The command requires PostgreSQL, locks summary/Notification/delivery tables, recomputes and matches the entire plan, refuses processing delivery rows, and deletes only reviewed legacy summary/publication Notification scope in one transaction. FK cascades remove dependent delivery rows. Encounters, Routine Interviews, users, credentials, unrelated notifications and Audit are not selected. An exception/interruption rolls the whole purge back. A stale plan must be regenerated and reapproved; it is not silently broadened. If purge commits and later migration fails, stay in maintenance and resume from the recorded recovery state; do not run old producers.

8. Apply `python manage.py migrate --noinput`, followed by normal `sync_identity_policy` and other documented bootstrap checks. Accounts conversion can commit before Counseling's retained-row refusal; the operation is resumable after the blocker is reviewed, but mixed code must remain stopped. Confirm one model/table, new constraint, migration registration/one leaf per app, and no legacy resource rows or old active contracts.
9. If and only if **known synthetic fixture regeneration** is approved, run with the existing staging seed environment opt-in:

```sh
python manage.py regenerate_student_session_summaries --plan-file /protected/summary-scope.json --approval-file /protected/approval.json
python manage.py seed_staging_dataset verify
```

The dedicated command accepts only four current catalog recipes: academic adjustment, referred follow-up, walk-in draft, and the action-ready published fixture. It verifies database/digest/approval and known Student/author/entry identities, preserves approved UUID/Encounter/timestamps, and encrypts the source-controlled synthetic recipe with the new binding. Unknown fixtures refuse; existing differing content/publication refuses; repeated matching execution creates nothing. It does not reconstruct retained real text. The existing seed advisory lock and transaction bound writes. Publication uses the normal service, then the existing seed settlement removes unattempted delivery intents before commit; any on-commit delivery kick refers to a removed row and cannot send. Keep consumers stopped during the procedure and verify no summary email/Push deliveries remain before restart. A failure rolls regeneration back; retry only after diagnosing it.
10. Run the updated seed/verification workflow for a fresh installation; it must not change credentials or expand the population. On existing datasets, do not reset unrelated scenario markers to force summary regeneration. Verify counts, new encrypted reads/rotation, publication idempotency, Notification destinations, Student/author and cross-Counselor denials, Context windows, and exact runtime versions/config/mounts. Restart only the new matched consumers after these gates.
11. Old backend endpoints, old frontend detail routes and old email deep links intentionally fail; no redirect/alias exists. Refresh existing frontend clients and invalidate stale authority/session state during release. Already delivered emails or previously viewed content cannot be retracted. New code against old schema, or old code against the renamed schema/binding, is unsupported and must stay behind maintenance; database failures are not permission to fall back.

## Recovery unit and unresolved operational gates

A compatible **backend + frontend + schema/data + persisted policy + runtime configuration + complete protected keyrings/mounts + queue/delivery state** is the recovery unit. Code-only rollback is insufficient. Scoped disposable deletion is recoverable only from the approved recovery copy or accepted synthetic regeneration. Never rewrite old Audit names to make a rollback or old-name search appear clean. Unknown data classification, missing key recovery, unresolved delivery claims, old consumers still running, failed graph/seed verification or mixed application versions block deployment.

No live cutover, key provisioning, broker/worker change, recovery or rollback is executed by this PR.
