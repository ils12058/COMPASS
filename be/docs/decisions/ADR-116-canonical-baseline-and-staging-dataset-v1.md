# ADR-116: Reset-only canonical baseline and COMPASS Staging Dataset v1

- Status: Proposed (CANON-1C). Becomes Accepted on owner approval of the reset-only branch.
- Date: 2026-10-16
- Scope: the `canon/compass-clean-baseline` integration branch only. Not for ordinary `staging`
  deployment.
- Supersedes, on the canonical baseline: the historical migration graph; the ADR-072 ledger and
  the ADR-114 transition safeguards (tombstones, fallback services, preflight command);
  [ADR-068](ADR-068-staging-demo-dataset-seeder.md) and
  [ADR-095](ADR-095-staging-demo-dataset-v2-and-pre-deployment-validation-baseline.md) (kept as
  history).
- Preserves: ADR-011 append-only Audit Trail and historical action vocabulary; ADR-045/061
  Privacy Notices; ADR-115 code-owned retention oversight; ADR-092 custody transfer; every
  encryption envelope, keyring and rotation contract; all authorization, consent and lifecycle
  rules.

## Context

The owner approved a clean-slate rebuild of disposable staging. The historical graph had 102
migrations across 27 apps, including encryption backfills, plaintext removal, legacy capability
renames, frozen helper modules and retired tables. PG-1A left the disposition ledger in place only
as a resurrection fence and transition safeguard for a runtime whose history was unknown. The
demonstration seeder carried v1-to-v2 upgrade paths, a shared password and an 11-persona cast
that did not support independent stakeholder UAT.

## Decision

1. **Canonical schema.** Each app has one Django-generated, schema-only
   `0001_canonical_baseline` migration (26 apps; Documents has no models). No `RunPython` or
   `RunSQL`: institutional forms and all configuration come from the explicit synchronizers. An
   empty-database comparison with the historical graph shows identical tables, columns, defaults,
   indexes and constraints except the three removed ledger tables and one auto-named check
   constraint that now follows its renamed column.
2. **Fail-closed history guard.** A database system check (`compass.E001`) and a `pre_migrate`
   receiver refuse `migrate` on any database that records a pre-canonical COMPASS migration. The
   distinct baseline name also prevents an old `0001_initial` record from being mistaken for the
   new baseline.
3. **Final PG-1A removal.** `OperationalRetentionRule`, `DispositionCase` and `DispositionHold`,
   the three tombstone tasks, the 409 fallback services and `retention_decommission_status` are
   removed. E-Counseling removes only the ledger query arms; capture/artifact disposal markers,
   terminal-state, quarantine, consent, claim, custody and unknown-room protections remain. This
   is the reviewed *clean-reset* strategy: it is valid only because no historical capture, room,
   broker message, worker, callback or backup may reach the canonical database (cutover gates).
   Retired capabilities stay in `RETIRED_CAPABILITY_CODES`; historical audit presenters stay.
4. **Encryption oracles.** The frozen v1 codecs move from migrations to
   `tests/encryption_oracles/`, so envelope-format and rotation compatibility stay tested.
5. **COMPASS Staging Dataset v1.** `compass.staging_seed` and `seed_staging_dataset` replace
   `compass.demo_seed` and `seed_demo_staging` as a new lineage with dataset version 1 (independent
   of the application version). It refuses retired `DEMO-2026-` accounts. It keeps the reviewed
   domain-service seeding, seed-only write allowlist, timeline and fail-closed guard, and adds:
   a manifest of 113 accounts (100 Students in rich, action-ready and background groups; 13 staff
   and negative-test accounts) and 91 scenarios with verifiable initial-state predicates;
   read-only `verify` and `report` modes; generated UAT documentation; and
   `STAGING_SEED_*` configuration.
6. **Credentials.** Seeding never sets a password. `issue-credentials` is a separate explicit
   operator action that issues distinct `secrets`-generated, policy-valid passwords (hash only in
   the database) into a new mode-0600 handoff file outside the repository, skips accounts that
   already have a credential, and reissues only named accounts with confirmation (revoking their
   sessions). MFA, verification and authorization policy are unchanged.

## Consequences

- The branch is **RESET-ONLY / NOT SAFE FOR ORDINARY STAGING DEPLOYMENT**. The current deployed
  runtime keeps ADR-114's tombstones and ledger until its operator cutover.
- Restoring a pre-reset backup into the canonical runtime is unsupported; the history guard
  refuses its migration records, and data-only imports are prohibited by the cutover plan.
- Tests that replayed historical migrations are retired; canonical-baseline, decommission and
  dataset tests replace them.
- Later features (Appointment Reminders, Service Catalog Expansion, Shared Guidance Follow-Up)
  add ordinary `0002_…` migrations; the baseline is not regenerated for them. Their UAT scenarios
  are `PENDING_IMPLEMENTATION` until merged.

## Unresolved

- Owner acceptance of the reset-only strategy and of the 100-Student design target.
- Live clean-rebuild execution, provider/object-storage/backup classification and broker
  isolation (CANON-1D and separately authorized operator work).
- Good Moral `LEGACY_UNSPECIFIED` initiation and Call Slip `LEGACY_UNKNOWN` issuance values remain
  model-owned enum members; removing them is a separate contract change.
