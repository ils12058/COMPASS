# CANON-1C — Canonical schema comparison

Date: 2026-10-16 (Asia/Manila). Base: `origin/staging` `3ae47817923849eef6cd3fd1ad15e0a43bd79568`.
Both references were built on empty, disposable PostgreSQL 17.11 databases in a local container
(`127.0.0.1:55432`). No live, shared or user database was touched.

## Method

| Reference | Source | Database | Applied migrations |
| --- | --- | --- | --- |
| A — current supported history | `origin/staging` @ `3ae47817` (unchanged backend) | `canon_ref_a` | 117 (102 COMPASS + 15 Django contrib) |
| B — canonical baseline | `codex/canon-1c-schema-uat-dataset` | `canon_ref_b`, re-checked on `canon_rehearsal` | 41 (26 COMPASS + 15 contrib) |

Both snapshots were taken with [`tools/schema_snapshot.py`](tools/schema_snapshot.py), which reads
`pg_catalog` in a read-only transaction: tables, every column's `format_type`, nullability, default
expression, identity and generated status, every constraint's `pg_get_constraintdef` with
deferrability, every index's `pg_get_indexdef` (with a name-independent signature), triggers,
functions, extensions and sequences. Constraints and indexes are matched by definition first, so a
different generated name is reported as *renamed*, not as a removal plus an addition.

Evidence: [schema-reference-a.json](evidence/schema-reference-a.json),
[schema-reference-b.json](evidence/schema-reference-b.json),
[schema-diff-a-b.json](evidence/schema-diff-a-b.json). After all later commits, a snapshot of the
final rehearsal database compared to Reference B with **zero** differences.

`makemigrations --check --dry-run` reported no changes on both A (before) and B (after).

## Totals

| Object | A | B | Difference |
| --- | ---: | ---: | --- |
| Tables | 98 | 95 | −3 (retired ledger) |
| Columns on the 95 shared tables | 933 | 933 | none |
| Constraints (PK, FK, unique, check) | 557 | 531 | −26, all on the 3 retired tables |
| Indexes | 429 | 411 | −18, all on the 3 retired tables |
| Triggers / functions / extensions / sequences | 0 / 0 / `plpgsql` / 0 | identical | none |

## Classified differences

| # | Difference | Classification | Notes |
| --- | --- | --- | --- |
| 1 | Tables `privacy_governance_operationalretentionrule`, `privacy_governance_dispositioncase`, `privacy_governance_dispositionhold` (48 columns, 26 constraints, 18 indexes) absent | **Intentional legacy removal** | Final PG-1A decommission under the clean-reset strategy; see [PG-1A verification](CANON-1C-PG-1A-Decommission-Verification.md). |
| 2 | `service_catalog_service`: check `CHECK (default_appointment_duration_minutes >= 0)` named `service_catalog_service_default_duration_minutes_check` in A, `service_catalog_service_default_appointment_duration_minu_check` in B | **Equivalent implementation** | Identical definition. Django names `PositiveIntegerField` checks after the column; A kept the name from before migration 0004 renamed the column. No code references constraint names of this kind. |

No difference was classified as **unexpected regression**. There are no column type, nullability,
default, foreign-key action, uniqueness, check, partial-index, index-column or deferrability
differences on any of the 95 shared tables.

## Invariants confirmed present in B

Because every shared table matches A exactly, all of the following historical invariants survive:

- Primary and foreign keys, including PROTECT-equivalent `NO ACTION` FKs and nullable ownership.
- Ciphertext-only confidential storage: every `*_cipher_present` / `*_ciphertext_present` check
  (Inventory and its six child tables, Exit Interview and opportunity notes and reopen events,
  Referral and actions, Routine Interview, Shared Summary, Feedback/CSM, Graduate Tracer families,
  account profile, Guidance Messages) and the absence of every removed plaintext column.
- Lifecycle shape checks: Appointment status/timestamps, Good Moral issuance, preparation,
  cancellation, variant provenance and initiation shape, Exit Interview opportunity shape, Call
  Slip issuance provenance, Inventory year-level and fare ranges, Guidance Message sequences.
- Database defaults that encode current semantics, e.g. Good Moral `initiation_origin`
  `db_default='LEGACY_UNSPECIFIED'` (model-owned; see "Retained model semantics").
- Partial unique indexes such as institutional form official identity and one-active-revision
  rules, and every ordering/listing index.
- E-Counseling consent, capture, artifact, reconciliation and webhook receipt tables with their
  claim, provider-binding, quarantine, disposal and custody columns and checks.
- Audit Trail tables and the action-code check introduced historically by `audit.0003`.

`tests/test_canonical_baseline.py::test_every_declared_constraint_and_index_exists_in_postgresql`
also asserts, for every COMPASS model, that each `Meta.constraints` and `Meta.indexes` entry exists
in the migrated database.

## Retained model semantics (not schema regressions)

These are part of current models and API contracts, so the baseline reproduces them unchanged:

- Good Moral `initiation_origin = LEGACY_UNSPECIFIED` and Call Slip `issuance_mode =
  LEGACY_UNKNOWN`. On an empty database nothing carries them, but removing them changes the model,
  OpenAPI enum and frontend presentation. Recorded as a later, separately reviewed contract change.
- Graduate Tracer anonymous-contribution columns (`student` nullable, `anonymized_at`) and
  `GraduateTracerDisposedParticipation`, read by reports and eligibility. Nothing writes them in the
  canonical system; their removal needs its own consumer review.

## Not covered by this comparison

- Row data: both references are empty apart from Django contrib bookkeeping. Data migration
  behavior is intentionally absent from B (see [migration rebaseline](CANON-1C-Migration-Rebaseline.md)).
- Live staging's actual schema, which may differ from A if it has unapplied or out-of-band changes.
  CANON-1D/operator work must not assume live staging equals A.
