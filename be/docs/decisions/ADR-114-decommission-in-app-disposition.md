# ADR-114: Decommission in-app records disposition

- Status: Proposed (PG-1A PR 1). Becomes Accepted on owner approval.
- Date: 2026-10-16
- Supersedes, for future operation: [ADR-072](ADR-072-operational-retention-and-disposition.md) in
  full, and the "Versioned retention and verified disposition" section of
  [ADR-092](ADR-092-ecounseling-media-governance-v2.md)
- Preserves: ADR-011 append-only Audit Trail; ADR-045/ADR-061 Privacy Notices and DPO boundary;
  ADR-069 history; ADR-084 Graduate Tracer encryption; ADR-092 consent, custody, provider cleanup
  and assigned access; ADR-112's anonymous-contribution invariant for existing rows
- Follow-up: PG-1A PR 2, implemented by [ADR-115](ADR-115-code-owned-retention-oversight.md)
  (code-owned register, capability retirement, read-only UI); PG-1A PR 3, tombstone removal and a
  database read-only guard on the legacy ledger

## Context

ADR-072 and ADR-092 introduced an in-app engine:

- DPO-editable retention rules;
- periodic eligibility discovery;
- single-record cases;
- holds;
- recent-MFA approval;
- Celery executors that anonymize Graduate Tracer responses or delete E-Counseling media.

The engine is implemented and present in deployed live-staging builds. Both ADRs stayed "Proposed".
No institutionally adopted retention schedule, period or rule was ever seeded.

The project owner decided that COMPASS must not act as an institutional records-disposition approval
or execution platform (PG-1 decision D1). The University of Camarines Norte is a state university
(RA 11399). Its records are public records under RA 9470:

- disposal requires the prior written authority of the National Archives (§18);
- disposal requires notice before it happens (§19);
- disposal follows an approved Records Disposition Schedule (§16-17).

A DPO's technical approval inside COMPASS was never that authority. Formal authorization, disposal
and destruction belong to the University's external records process.

## Decision

1. **No in-app disposition.**
   - COMPASS no longer discovers retention eligibility, places holds, approves or retries disposition,
     or executes it.
   - The Beat entries `retention-eligibility-discovery` and `retention-approved-dispatch-recovery`
     are removed.
   - The Graduate Tracer anonymization executor is deleted, as are the version-1 provider-artifact
     executor, the version-2 private-media executor, and dispatch and recovery.
2. **Fail-closed mutations.**
   - `create_rule`, `update_rule`, `transition_rule`, `change_hold` and `approve_case` raise
     HTTP 409 `retention_decommissioned` as their first statement. That happens before any query,
     lock, write, audit event, provider call or task dispatch.
   - The refusal is unconditional, so neither the DPO baseline grant nor an exceptional capability
     override can make an operation succeed.
   - Route-level capability and recent-MFA checks stay unchanged until PR 2 removes the routes.
   - The OpenAPI contract is unchanged; every affected route already declares 409.
3. **Temporary tombstones.** `compass.privacy_governance.discover_retention`, `execute_disposition`
   and `recover_disposition` stay registered for one release as non-mutating tombstones. A
   broker-resident or redelivered message from the previous build is then acknowledged and dropped,
   instead of failing as an unregistered task.
   - A tombstone never reads its arguments or the database.
   - It never calls Daily or object storage, and never enqueues work.
   - It logs only the task name and `outcome_code=DECOMMISSIONED`.
   - It never moves a QUEUED case to any other state.
   - PR 3 removes the names after a verified deploy cycle shows the broker drained.
4. **Historical evidence is retained, not operated.**
   - Preserved unchanged:
     - `OperationalRetentionRule`, `DispositionCase` and `DispositionHold`;
     - historical AuditEvents and their activity presentations;
     - anonymous Graduate Tracer contributions and disposed-participation markers;
     - disposed E-Counseling markers.
   - No migration drops or rewrites them, and unresolved legacy case states are not rewritten.
   - `DispositionCase.source_id` is the only link between a destroyed original and its outcome. A
     backup restore needs it so disposed data is not resurrected.
   - E-Counseling webhook, reconciliation and ingestion code reads the table as a resurrection fence.
   - The existing GET routes stay readable until PR 2 replaces them.
   - `verify_anonymized` and `ANALYTICAL_FIELDS` remain the integrity rule for existing anonymous
     contributions.
5. **Custody-transfer cleanup is preserved.** After verified private COMPASS custody, deleting the
   Daily provider copy is operational minimization of a processor copy, not retention-triggered
   disposition.
   - This covers `ecounseling.artifacts.ingest_artifact`, `delete_v2_provider` and
     `recover_media_artifacts`.
   - It continues unchanged, with its existing verification.
   - The sensitive-storage policy that rejects age-based expiry also stays.
6. **Deployment gate.** `manage.py retention_decommission_status` is a read-only, counts-only
   database preflight. It exits 3 when a database release gate is blocked:
   - G1: a case is PROCESSING;
   - G2: a case is APPROVED or QUEUED;
   - G3: a case is FAILED or RECONCILIATION_REQUIRED;
   - G4: a rule is ACTIVE;
   - G5: completed-case evidence is inconsistent.

   Broker, worker, custody-cleanup health and deployed-build checks are separate operator steps. A
   pass does not certify deployment safety.

   Pending APPROVED or QUEUED cases are a release blocker until authorized institutional personnel
   review them. A prior DPO approval is not treated as sufficient. Live queues, rules and case states
   are not changed from implementation work.
7. **Code-owned retention follows in PR 2.** PR 2 adds a version-controlled, read-only policy
   register. Every entry starts as not adopted and nothing is enforced. PR 2 also retires
   `privacy_governance.retention.manage` and `.approve` through `RETIRED_CAPABILITY_CODES`, removes
   the mutation routes and the rule, hold and approval UI, and rewrites Student-facing retention copy.
   PR 1 changes no capability, contract or frontend.

## Unresolved external dependencies

Decommissioning does not satisfy retention or disposal obligations; it removes an in-app capability
that was never institutionally authorized. Still required from the University or infrastructure owners:

- adopted retention periods for Graduate Tracer responses and E-Counseling recordings and transcripts
  (RA 10173 §11(e)-(f); IRR §19(d) forbids retention "in perpetuity");
- whether a National Archives-approved Records Disposition Schedule covers these records;
- an external disposal procedure for data COMPASS holds in its database and private storage, and
  how COMPASS state stays consistent with it;
- disposal of legacy version-1 media that remains provider-held;
- backup retention and restore handling;
- the retention status of the legacy disposition ledger itself.

Until then, identifiable tracer responses and stored or provider-held media are retained. That is a
policy gap, not a compliance claim.

## Consequences

- The previous frontend still shows retention actions until PR 2. After deployment they return the
  409 refusal.
- Operators follow the "Decommission verification" section of the
  [retention runbook](../retention-disposition-runbook.md) before and after deploying. That runbook's
  historical restoration boundary remains mandatory.
- New in-app disposition requires a new ADR and institutional authority. Re-enabling the retired
  schedules or executors is not a configuration change.
