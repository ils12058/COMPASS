# ADR-117: Reset-only release migration baseline

- Status: Accepted by owner for Phase D; Phase E reset/deployment remains separate.
- Date: 2026-11-09
- Scope: the final code cleanup before Evaluation, based on integration `f9581adb`.
- Supersedes in part: ADR-116's migration graph and routine deployment lineage assumption.
- Preserves: every current model, API, policy, feature and database guard; Dataset v1 configuration
  and explicit synchronizers. No contract, frontend or runtime behavior change.

## Decision

Replace 72 COMPASS migrations with 36 immutable files across the 29 apps with models. Every app
starts at `0001_release_baseline`, generated from the current Django model state. Baselines and
link files contain only schema operations; no `RunPython`, `RunSQL` or state/database separation.
No migration performs data backfills, row renames, policy synchronization or catalog seeding.

| App | Immutable release files |
| --- | --- |
| accounts | `0001_release_baseline.py` |
| announcements | `0001_release_baseline.py` |
| appointments | `0001_release_baseline.py`, `0002_release_baseline_links.py` |
| assessment_records | `0001_release_baseline.py` |
| audit | `0001_release_baseline.py` |
| authentication | `0001_release_baseline.py` |
| availability | `0001_release_baseline.py` |
| call_slips | `0001_release_baseline.py` |
| counseling | `0001_release_baseline.py`, `0002_database_guards.py` |
| ecounseling | `0001_release_baseline.py` |
| exit_interviews | `0001_release_baseline.py` |
| feedback | `0001_release_baseline.py` |
| good_moral | `0001_release_baseline.py`, `0002_database_guards.py` |
| graduate_tracer | `0001_release_baseline.py` |
| group_sessions | `0001_release_baseline.py`, `0002_database_guards.py` |
| guidance_followups | `0001_release_baseline.py` |
| guidance_messages | `0001_release_baseline.py` |
| institutional_forms | `0001_release_baseline.py` |
| inventory | `0001_release_baseline.py` |
| notifications | `0001_release_baseline.py` |
| organization | `0001_release_baseline.py`, `0002_database_guards.py` |
| platform_ops | `0001_release_baseline.py` |
| privacy_governance | `0001_release_baseline.py` |
| referrals | `0001_release_baseline.py`, `0002_database_guards.py` |
| resources | `0001_release_baseline.py` |
| routine_interviews | `0001_release_baseline.py` |
| service_catalog | `0001_release_baseline.py`, `0002_database_guards.py` |
| student_academics | `0001_release_baseline.py` |
| student_support | `0001_release_baseline.py` |

Documents has neither models nor migrations. Appointments' Service foreign key references Service
Catalog, whose Fixed Slot and booking-history foreign keys reference Appointment. Django breaks
this cycle by creating Appointment first, creating Service Catalog next, and adding Appointment's
remaining links/constraints/indexes in `0002_release_baseline_links`. Keep the generated split.

## PostgreSQL guards

Five SQL-only `0002_database_guards` migrations install the final functions/triggers from the
fully migrated reference database. Good Moral keeps P3's unconditional function bodies, never
its superseded ledger-gated definitions. Group Sessions keeps deletion refusal and facilitator
removal preservation. Service Catalog keeps slot/history deletion refusal and booking-history
recording. Referrals keeps submission-origin and administrative-history immutability. Organization
creates `organization_valid_year_levels_v1(smallint[])` before adding the model-owned
`organization_program_policy_consistent` CHECK, moved intact from its baseline. Django's final
state still includes the constraint and `makemigrations --check` reports no drift.

A sixth SQL-only guard migration in Counseling preserves the PK, encounter uniqueness and
encounter FK names produced by the previous Student Session Summary rename. The old
`rename_resource_constraints` RunPython changed schema even on an empty database; dropping its
effect would violate schema equality. SQL renames preserve both constraint and backing-index
identities without changing models or behavior. Reverse SQL explicitly undoes these renames.
Other guard reversals drop their triggers first, then functions; the Organization constraint is
removed before its function. Reversal is provided for disposable schema tooling, never an old
history upgrade or a production rollback plan.

`tests/test_canonical_baseline.py` owns a literal list of all 19 public functions and 20 non-internal
triggers (including deferred constraint triggers). The test queries the database independently
of migration source. It also checks all model constraints/indexes, SHA-256 immutability, allowed
operation types, no RunPython anywhere, and one graph leaf per app. Both immutable manifests
include baselines, links and guards; `additive_migrations` becomes empty. Future additions extend
this graph and are registered separately; do not regenerate the immutable files.

## Reset-only history and deployment refusal

The owner chose a complete staging reset with no compatibility. A database built with the old
migrations is never upgraded, faked forward, imported or restored. The new baseline name makes
old canonical records unknown to the current graph. The existing `compass.E001` database check
and `pre_migrate` receiver refuse all unknown COMPASS migration records, including when command
checks are skipped. The public guard callable names remain stable for AppConfig registration.

`deploy-staging.yml` refuses every revision containing release baseline files before deployment.
It retains staging-tooling unit tests. Phase E's separately approved reset lifts that refusal and
pins the new lineage commit. Database/host preflights expect all release files, including guards,
already applied, reject unknown history and check the new CatalogInitialization migration/table
contract. Prior source-pinned migration exceptions are retired; even a digest pin cannot admit
the reset-only graph through routine deployment. Phase D never connects to live staging.

## Evidence and consequences

Phase D compares sorted public-schema catalog snapshots from separate empty PostgreSQL databases
built by the old and release graphs. The comparison includes tables, columns as sets (physical
column order excluded), types/defaults/nullability, constraints and deferral, indexes, functions,
non-internal triggers, sequences and extensions. The final diff must be empty; the reference and
new databases and external evidence remain available for review. Migration-history rows and
sequence values are excluded. The comparison requires all current guards plus P11's appointment
link mode CHECK and P10a's Referral submission-channel CHECK unchanged.

Fresh bootstrap remains: `migrate`, `sync_identity_policy`, `sync_canonical_services`,
`sync_institutional_forms`, `initialize_organization_catalog --seed`, then database checks.
A second migrate is a no-op. The old-history copy must refuse migrate. Migration-history replay
tests are retired after reading them; current schema/runtime assertions move to normal domain
tests wherever existing coverage is insufficient. Targeted tests and deployment-tooling checks
run in Phase D; full backend regression, browser specs, staging reset and freeze belong to Phase E.
