# Migration and recovery

The actual graph is recorded in [manifest](integration-manifest.md). Fresh empty migrate, canonical populated upgrade, GM-OR-1→GM-OR-2, registry/hash/drift checks, idempotent/chunked interrupted import and guard tests all run on disposable PostgreSQL. Frozen migration files are unchanged. 0002/0003 reverse guards are tested with nonempty retained history: reversal raises atomically, leaves migrations applied and retains evidence. Empty verification tables can reverse/reapply independently; receipt identities/claims/operations/batches prevent destructive 0002 reversal.

## Legacy fixture inventory

| Categories | Newly executed coverage / limitation |
| --- | --- |
| F4/F6; REQUESTED, READY, ISSUED, CANCELLED | Core/receipt/migration/legacy READY suites |
| Blank, complete unique, incomplete unique; missing date/amount | Receipt/verification and migration suites |
| Zero, non-80, future date, invalid numeric legacy anomalies | Receipt and both-variant verification matrix; preserve actual fact, block new eligibility |
| Cross-Student and cross-variant duplicates; issued involvement; case/outer-space collision | Receipt and new historical issued-PDF suites; one ambiguous identity, no owner |
| Unsupported characters | Exact quarantine observation, no guessed alias; cutover refuses unresolved unsupported formats |
| Corrections, cleared/replaced identities | Immutable revision/replay/non-reuse tests |
| Historically overwritten, unrecoverable prior number | PARTIAL: unknown former values cannot be reconstructed from changed-field-only Audit; never invented |

Observation is not payment/inspection/fee authority. Import preserves request projection, form/template/applicant/issuer/date/status and historical null inspection references. It never creates reissuance or retroactive revocation. Duplicate quarantine is not a rightful-owner decision. Amount anomalies are not proof of an approved waiver or payment failure.

DORMANT compatibility is deliberately weaker than active permanent reservation: no assurance of complete historical non-reuse is made before a reconciled cutover. FENCED drains shared-lock writers and denies source mutations during chunked observations. ACTIVE requires complete source/claim/projection reconciliation and no unresolved unsupported-format blocker. Synthetic import is explicitly restricted to local test-named databases. It is not production migration tooling or authorization.

## Actual backup/restore rehearsal

`test_disposable_backup_restore_preserves_evidence_but_loses_later_claims` uses an opt-in loopback database named `test_*`, real `pg_dump -Fc` and `pg_restore` into a generated `_synthetic` clone. It captures full rows for source requests, identities, assignments, mutation operations, import batches, writer-control state, inspection, Audit, notifications and feedback. A later committed receipt is then created on the source. The clone must exactly match the earlier snapshot and retain enabled guards, yet omit the later request and reservation. It is never attached to a server or opened for new application writes and is dropped in `finally`. No trigger is disabled by this rehearsal.

A restored snapshot can retain ACTIVE while missing post-backup claims. Its uniqueness constraint cannot reject an identifier that is absent from the backup. Thus restore success is not operational recovery readiness. Before restored writes reopen, authorized operators must account for later receipt reservations/revisions/attestations and issuance outcomes using approved protected sources/WAL/consistent backups, restore compatible backend/frontend/workers/contracts and prevent a second issuance or OR reuse. Unknown gaps require continued mutation pause. The test demonstrates the gap; it does not solve arbitrary lost history.

There is no ordinary ACTIVE→FENCED/downgrade command. For an activated database, a future approved incident runbook must stop/drain mutation clients/workers or revoke the narrowly scoped writer path at the service/infrastructure boundary, retaining compatible read-only certificate access where feasible. Do not defeat monotonic database guards to obtain a pause. Do not return an old weak writer to service.

Production volume, backup retention/RPO, WAL/archive completeness, restoration with real keys, post-backup claim reconciliation, actual old-binary retirement and institutionally governed exception/duplicate disposition remain BLOCKED pending separate authority/evidence. No staging backup, reset or restore occurred.
