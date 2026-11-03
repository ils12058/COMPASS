# Migration and rollback — safe path for SAR-1

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
No migration was created or executed. Claims are labeled **Verified**, **Inferred** or **Unknown**.

## 1. Principles

1. **No destructive change in SAR-1.** **Verified.** `StudentAffiliation`, `StudentInventory`,
   `GoodMoralRequest` and `GraduateTracerResponse` remain unchanged. The proposal's retirement phase
   is explicitly deferred (proposal lines 689–696).
2. **One writer.** **Verified.** Today `set_student_affiliation` / `remove_student_affiliation` is
   the only Student placement writer (`be/compass/organization/services.py:271-325`). SAR-1 must
   not add a second independent writer.
3. **No inferred verified facts.** **Verified.** The proposal itself says not to classify migrated
   affiliations as Registrar-verified and not to infer enrollment or graduation (lines 659–672).
4. **Reversible by deactivation, not by data destruction.** Because SAR-1 adds a shadow table and
   does not move consumers, rollback can disable the mirror and leave the table in place.

## 2. Coexistence model for SAR-1

**Recommendation (not adopted policy):**

| Concern | SAR-1 behavior |
|---|---|
| Authoritative current College | `StudentAffiliation` remains authoritative |
| Profile role | Shadow/current-state projection of College |
| Profile Program | Always null in SAR-1 |
| Profile verification | `UNVERIFIED` for every backfilled and dual-written row |
| Affiliation transfer | Update affiliation row, then update the profile College in the same transaction |
| Affiliation removal | Do not delete the profile; null the College, set `UNVERIFIED`, preserve audit. Exact representation requires D-SAR-07 |
| Consumer reads | Unchanged; no consumer reads the profile |
| Provisioning | Unchanged; no academic columns |
| Period/graduation | Not created |

**Verified constraint:** `StudentAffiliation` has no effective date or end date, so a profile
“removal” cannot be historically dated from the row. The audit event timestamp is the only
transition time. Do not present it as an academic effective date without a decision.

## 3. Backfill plan

### 3.1 Preflight (read-only)

Run the aggregate checks in `data-quality.md`, especially DQ-01, DQ-02, DQ-03 and DQ-14. Record, with
no PII:

- total affiliations;
- affiliations on active Student accounts;
- affiliations on inactive accounts;
- affiliations on non-Student roles;
- affiliations to inactive College/Campus;
- current Academic Year count.

**Unknown** until executed. The inclusion rule for inactive/non-Student affiliations is D-SAR-03.

### 3.2 Backfill rule

For each included affiliation, create exactly one profile keyed by `student_id`:

```text
current_college            = affiliation.college_id
current_program            = NULL
placement_verification     = UNVERIFIED
placement_effective_at     = NULL
updated_by                 = affiliation.assigned_by if non-null, else NULL
created_at / updated_at    = migration timestamp
```

**Verified:** none of these values is an inference beyond the stored College. **Verified:** the
affiliation has no Program, so null is the only defensible Program value. **Verified:** copying
`created_at` into `placement_effective_at` would assert an academic date the row does not prove.

### 3.3 Idempotency and batching

- Key by the one-to-one Student UUID; re-running the backfill must update the same row, not create a
  duplicate.
- Process in bounded batches inside short transactions; do not hold a table-wide lock.
- Do not fire user notifications or emails.
- Emit one aggregate audit/summary event per run, not one per Student, unless the audit policy
  requires per-record events. **Unknown:** the applicable audit retention/volume policy.
- Verify counts before commit: `profiles_created + profiles_updated = eligible_affiliations`.

### 3.4 What must not be backfilled

| Fact | Why not |
|---|---|
| Current Program | The only Program is per-Academic-Year Inventory and is Student-submitted; it can disagree with the affiliation College |
| Year Level as current | Same reason; it is a per-year Inventory value |
| Placement effective date | No source; affiliation timestamps are row timestamps |
| Enrollment status | No source; lifecycle is not enrollment |
| Verification status | No verifier/source exists |
| Academic periods | No term model and no verified historical source |
| Graduation record | Tracer is self-reported and year-only; Good Moral date is request input |

## 4. Dual-write design

### 4.1 Write points

**Verified.** `set_student_affiliation` runs in one `transaction.atomic()` with row locks
(`be/compass/organization/services.py:271-303`). `remove_student_affiliation` does the same
(`:307-325`). The profile mirror should be written inside those same transactions so an affiliation
change and its projection cannot diverge on success.

**Recommendation:**

- On create/transfer: upsert the profile with the new College, `UNVERIFIED`, and an audit event.
- On removal: do not delete the profile; clear/flag it according to D-SAR-07.
- If the mirror write fails, fail the affiliation transaction. This preserves consistency at the
  cost of availability. **Inferred:** acceptable for SAR-1 because affiliation writes are
  low-volume administrative actions, but it must be an explicit decision.
- Do not notify Students or Counselors about the mirror write.

### 4.2 Activation gate

**Verified.** The repository has no feature-flag framework (`FEATURE_*` search returns no code
matches; settings are environment-driven in `be/config/settings.py`). SAR-1 therefore needs either
a new server-side setting or an approved deployment switch.

**Recommendation:** introduce a server-side setting that defaults **off** in production and is
enabled only after backfill and reconciliation. The gate must not be user-controlled and must not be
exposed through the API. Enabling it must not change any read path.

### 4.3 Reconciliation

Run after backfill and on a schedule while dual-write is active:

```sql
-- R1: affiliations without a profile
SELECT count(*) AS affiliations_without_profile
FROM organization_studentaffiliation a
LEFT JOIN student_academics_studentacademicprofile p ON p.student_id = a.student_id
WHERE p.student_id IS NULL;

-- R2: profile College differs from affiliation College
SELECT count(*) AS profile_college_drift
FROM organization_studentaffiliation a
JOIN student_academics_studentacademicprofile p ON p.student_id = a.student_id
WHERE p.current_college_id IS DISTINCT FROM a.college_id;

-- R3: profiles with a Program whose College differs from current College
SELECT count(*) AS profile_program_college_mismatch
FROM student_academics_studentacademicprofile p
JOIN organization_program pr ON pr.id = p.current_program_id
WHERE p.current_college_id IS NOT NULL
  AND pr.college_id <> p.current_college_id;
```

Expected: R1/R2/R3 = 0. Any nonzero value is a rollback trigger until explained. **Unknown:** the
actual values; these are future-state checks, not executed.

## 5. Deployment ordering

**Recommended order (SAR-1):**

1. **Backup and evidence.** Confirm a restorable database backup, audit/key custody and the release
   artifact. Record the pre-migration counts from §3.1.
2. **Apply the additive migration.** Create the new app/table only. No existing table alteration.
3. **Deploy code with the activation gate off.** No reads or writes to the profile occur.
4. **Dry-run backfill.** Report eligible/excluded counts; compare with preflight.
5. **Backfill.** Idempotent, batched, count-verified. Leave the gate off.
6. **Reconcile.** R1/R2/R3 must be zero for included affiliations.
7. **Enable dual-write.** Monitor affiliation writes and reconciliation.
8. **Stop.** Do not cut over consumer reads, do not change provisioning, do not retire anything.

**Inferred:** this ordering keeps every rollback step non-destructive through step 7. After step 7,
rolling back the code leaves the shadow table; it can be ignored safely.

## 6. Observability

**Verified.** The audit infrastructure already records affiliation changes with
`previous_college_id`/`new_college_id` (`be/compass/audit/actions.py:43-45`). SAR-1 should add
profile events without duplicating the audit system (proposal lines 295–298).

Minimum signals:

- Backfill: eligible, created, skipped, failed, duration, batch count.
- Dual-write: success/failure counts, transaction rollback count, reconciliation drift.
- Migration: applied version, row count, table size, lock wait (if measured).
- Access (if read endpoints are added): authorization denials, scope denials, latency.
- No PII in logs or metrics.

**Unknown:** the production monitoring stack, alert routing and audit retention period. These are
deployment-owner inputs, not repository facts.

## 7. Rollback plan

### 7.1 Before dual-write (steps 2–6)

- Disable/stop the backfill; the affiliation table is untouched.
- If the new table contains only backfilled data, it can be truncated/dropped only with dataset-owner
  approval. **Destructive:** do not run without a backup and approval.
- Application rollback is safe because no consumer uses the profile.

### 7.2 After dual-write (step 7)

- Disable the mirror gate first; affiliation writes continue as before.
- Do **not** drop the table: it may contain writes not present elsewhere, although every value is
  derived from affiliation. Leave it as a shadow and investigate.
- Reconcile affiliations to confirm no lost updates.
- If data corruption is suspected, restore from the verified backup; this is a last resort and
  requires release-owner approval.

### 7.3 Point of no return

**Verified.** SAR-1 never reaches a point where the affiliation table can no longer reconstruct the
current College. **Inferred.** A later cutover becomes a point of no return once consumer reads or
writes depend on the profile and the affiliation table stops being maintained. That cutover needs a
separate plan, backup, reconciliation and rollback rehearsal.

## 8. Rollback triggers

| Trigger | Threshold (proposal) | Action |
|---|---|---|
| Migration failure | any | Stop; new table only; investigate |
| Backfill count mismatch | any | Stop; do not enable gate |
| R1/R2/R3 drift | any unexplained nonzero | Disable dual-write; investigate |
| Affiliation write failure rate | any sustained increase | Disable mirror gate; preserve affiliation behavior |
| Counselor routing/booking regression | any | Disable mirror gate; routing is unchanged in SAR-1 |
| Report coverage change | any | Investigate; SAR-1 should not change reports |
| Audit gap or duplicate event | any | Stop; audit integrity review |
| Migration lock/timeout | exceeds approved window | Abort; retry in a smaller window |

**Unknown:** the institution's approved thresholds and maintenance windows. The table above is a
proposal, not adopted policy.

## 9. Future cutover gates (not SAR-1)

Before any consumer reads SAR instead of `StudentAffiliation`:

1. Approved D-SAR-01 through D-SAR-08, plus the applicable FAC-D9/FAC-D10 decisions.
2. Approved conflict rule for Inventory Program vs affiliation College.
3. Dual-write stable with zero reconciliation drift over an approved observation period.
4. Read-adapter tests for routing, appointments, counseling, follow-ups, reports, Good Moral,
   referrals, call slips, student support and assessment records.
5. Approved historical access/custody matrix (FAC-D10) and transfer behavior.
6. Approved retention and privacy review.
7. Backup, restore rehearsal, UAT sign-off and release approval (ORG D19–D20).
8. A rehearsed switch-back to affiliation that does not lose new writes.

**Inferred:** without these gates, a SAR cutover would change authorization and routing behavior
for at least ten domains, not just the display of an academic field.

## 10. Non-negotiable destructive-action prohibitions for SAR-1

- Do not delete or rewrite `StudentAffiliation` rows as part of migration.
- Do not rewrite Inventory Program/Year Level or Good Moral/Tracer snapshots.
- Do not delete affiliations because a Program is missing or a College is inactive.
- Do not drop the new table as a “cleanup” after failed reconciliation.
- Do not mark backfilled data `VERIFIED`.
- Do not enable dual-write before backfill reconciliation passes.
