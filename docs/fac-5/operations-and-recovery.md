# Operational rollout and recovery checklist — no deployment performed

FAC-5 changes no schema, migration history, runtime secret or deployment environment variable.
The existing migration manifest still owns FAC-1 Organization 0004, FAC-2 Referral 0002 and
FAC-4 Referral 0003. The supported recovery model retains immutable Faculty history.

## Before any separately authorized deployment

- Obtain an exact implementation SHA and matching frontend/backend artifacts. Check all
  required hosted jobs for that SHA, including every browser shard; pending/cancelled jobs
  are not passes. Review this package's technical, policy, UAT and deployment verdicts separately.
- Confirm the actual starting schema/record counts on an authorized controlled staging clone;
  FAC-5 uses disposable synthetic PostgreSQL only. No sanitized or live staging clone is assumed
  available and no staging data or host is accessed by this work.
- Verify backup/restore rehearsal and encrypted key custody. Preserve the complete required
  ordered Referral/other domain keyrings for retained records and backups. A DB backup without
  its independently protected keys cannot prove historical content recovery.
- Review all web, worker, scheduler, CLI and import writers. Inspect current deployment scripts,
  migration-before-service-replacement ordering, readiness and failure behavior. Do not assume
  an old binary understands Faculty provenance/administrative guards because additive columns
  exist. Stop/drain incompatible writers before transition and test a compatible image explicitly.
- Confirm actual CSRF/session/trusted origins, authenticated deep links, proxy transport, Redis
  privacy limiter availability, private storage, existing Notification currentness/deduplication,
  monitoring and incident responsibility. FAC-5 changes none of their live settings.
- Confirm approved Faculty identity provisioning/home management independently of unavailable
  digital intake. Do not seed real Student narratives or convert existing identities implicitly.

## Backend/frontend order

1. Rehearse all registered migrations on the controlled clone and compare identifiers, original
   receipt dates, ciphertext, saved provenance/form revisions and Audit; retain a recovery point.
2. Deploy the matching backend schema/domain/API version under approved operational change
   control. Run the existing explicit identity-policy synchronization, not raw GRANT scripts.
3. Verify default provider denial, historical GCO reads/PDF, current authorization and API contract.
4. Release the matching generated frontend against that backend. FAC-4 source-origin metadata
   is the prerequisite for mounting its GCO intake query; no frontend state activates a provider.
5. Validate availability, owned-cache/session changes, default denial and ordinary GCO operations.
   A release can remain intentionally unavailable for Faculty intake; technical health is distinct
   from institutional activation. No automatic Student Referral notice is introduced.
6. Perform any institutional activation only as a separate approved, reviewed adapter/release
   after FAC-D1–D10 decisions and appropriate UAT. This checklist grants no activation permission.

## Compatible-code and forward recovery

- On failed application rollout, stop unsafe/consequential writers and preserve committed data,
  schema, Audit and complete keyrings. Establish actual transaction/result status before retries.
- Restore a verified schema-compatible application version or roll forward with a reviewed fix.
  Compatibility must include new facts/guards, not just the ability to query historical columns.
- Do not reverse Organization 0002's irreversible policy backfill, the Student Session Summary
  cutover, or Faculty provenance/administrative migrations after digital history exists. Do not
  remove records, edit migration history, fake applied migrations or bypass guards to downgrade.
- A failed uncommitted business transaction should roll back as one unit. For committed requests,
  use canonical reads and the defined idempotent/versioned contracts; never blindly replay.
- Reapply the supported forward migration plan idempotently and compare all retained facts.
  Restore backups only under the institution's authorized recovery procedure, with keys and a
  verified consistent application/schema pair. A restore is not a substitute for row provenance.
- Check no duplicate reference, Audit, transition, Notification intent or delivery was created.
  Record incident/recovery evidence and obtain actual operational approval before resuming.

The new postbaseline test creates a uniquely named owned database, installs the prior supported
floor, upgrades forward, compares every original column of its synthetic users/service/appointment,
rolls back a simulated failed data transaction, reruns forward migrations and checks compatible
historical-column reads. It never reverses the shared test database. FAC-1/2/4 tests separately
exercise their own populated migrations and irreversible Faculty history guards.

These are technical synthetic rehearsals. Deployment readiness still requires actual controlled
staging compatibility, backup/key custody, monitoring/incident review, institutional approval and
UAT evidence. None is silently inferred from local or hosted test success.
