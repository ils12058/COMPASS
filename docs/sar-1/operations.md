# SAR-1 operations runbook

**Applies to:** `be/compass/student_academics/` on `codex/sar-1-academic-profile`.
**Gate:** `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED` — default `false`; **not activated** by this
branch.
**Hard rule:** the profile is a shadow projection. Do not point any consumer at it and do not make
it authoritative in this phase.

## 1. Preconditions for any run

1. D-SAR-08 activation policy approved by IT + GCO (the SAR-0 register records it as Open).
2. Named operator, approved environment, change record and observation window.
3. Database backup/restore evidence for the target environment.
4. The deployed build contains migration `student_academics.0001_initial` and the gate is
   confirmed `false` before the first backfill.
5. A read-only preflight copy of the aggregate counts is retained as evidence.

Until all five are true, do not run the write steps below.

## 2. Deploy schema with the gate off

```text
python manage.py migrate --noinput
python manage.py check
```

Expected: `student_academics.0001_initial` applies; check reports no issues. With the gate off, no
profile is read or written by any request.

Confirm the gate is false in the running process before proceeding (environment inspection or the
deployment configuration). Do not set it to true.

## 3. Preflight (read-only)

```text
python manage.py backfill_student_academic_profiles --dry-run --batch-size 200
python manage.py reconcile_student_academic_profiles
```

Record the full aggregate output. Before the first backfill, `affiliations_without_profile` is
expected to equal the eligible affiliation count; `created` must be `0` in a dry run. Review:

- `non_student_role_rows` — excluded rows; confirm the D-SAR-03 inclusion matrix.
- `inactive_student_accounts` — included by the approved default.
- `inactive_college_rows` — copied as recorded; decide whether they need a separate data-quality
  action before activation.

No command prints Student names, emails or IDs.

## 4. Backfill

Run in short batches. The command itself commits one short transaction per batch.

```text
python manage.py backfill_student_academic_profiles --batch-size 200
```

Why batches: limits transaction size and lock duration on large affiliation tables. Use a smaller
`--batch-size` if lock contention appears; the valid range is 1–1000. Re-running is safe and creates
only still-missing profiles.

Expected output: `created=<missing_profiles from the dry run>`, `dry_run=false`. Existing profiles
(including any created by earlier gate-on activity) are left untouched.

If the process is interrupted, re-run the same command. The pagination key is the Student UUID, so
completed batches are not recreated.

## 5. Reconcile before activation

```text
python manage.py reconcile_student_academic_profiles --fail-on-mismatch
```

Required result: exit code 0 and `blocking_total=0`.

- `non_student_profiles` and `inactive_student_profiles` are informational warnings, not blockers.
- Any blocking mismatch must be explained and corrected under an approved procedure before
  activation. This slice provides detection, not automated repair:
  - `affiliations_without_profile` — re-run the backfill after confirming the missing Student has
    role `STUDENT`.
  - `profile_college_drift` / `profiles_without_affiliation` — these usually mean an affiliation
    change happened while the gate was off. There is no replay command in this slice. Do not hand-
    edit rows; escalate for an approved remediation or a controlled window.
  - `profile_program_present`, `profile_effective_at_present`, `profile_verified` — must never be
    non-zero for SAR-1 data; treat as a defect and stop.

Keep the gate **off** if any blocker remains.

## 6. Activation (separate approval, not performed here)

Only after step 5 is clean and D-SAR-08 is approved:

1. Set `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=true` for the application process in the approved
   environment.
2. Restart/redeploy so every worker and web process reads the new value.
3. Verify the process configuration actually reports `true`; do not infer it from the file alone.
4. Exercise one authorized affiliation set/transfer and one removal in a controlled test Student
   account, then confirm the shadow row changed as specified and the affiliation audit event
   remains single.
5. Keep the gate on only while reconciliation remains at zero blocking mismatches.

Do not enable the gate in local, test, staging or production as part of this PR. No activation was
performed.

## 7. Monitoring while active

- Run `reconcile_student_academic_profiles --fail-on-mismatch` on an approved schedule and after
  any affiliation batch job.
- Alert on any blocking token becoming non-zero; the affiliation transaction is designed to roll
  back on profile write failure, so a nonzero drift indicates an out-of-band write or a prior
  gate-off change.
- Watch application errors for profile write failures; they surface as affiliation request
  failures, not silent divergence.
- Retain aggregate command output as operational evidence. Do not export profile contents.

## 8. Rollback

Rollback is **deactivation**, not data destruction.

1. Set `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED=false` and restart all processes. Affiliation behavior
   returns to the pre-SAR-1 path immediately.
2. Leave the `student_academics_studentacademicprofile` table in place. It is shadow data with no
   consumer; dropping it is unnecessary and destroys the only current projection and any audit
   value.
3. Do not delete profile rows after any gate-on period. In particular, rows with a null College
   represent a recorded removal; deleting them would erase that fact and interfere with
   reconciliation.
4. If the table must be removed for an approved emergency reason, take a backup first and follow
   the DBA/Records procedure. Never drop the table as cleanup after a failed reconciliation.
5. To reactivate later, repeat steps 3–6. Backfill is idempotent and will fill new affiliations
   without overwriting existing rows.

## 9. Failure modes and responses

| Symptom | Likely cause | Response |
|---|---|---|
| `--batch-size must be between 1 and 1000` | Invalid operator input | Re-run within range |
| `CommandError: N blocking profile mismatch(es) remain` | Backfill not run, gate-off drift, or a real defect | Do not activate; investigate per step 5 |
| Non-Student-role warning | Affiliations attached to non-Student accounts | Review D-SAR-03 inclusion matrix; leave excluded |
| Inactive College warning | Affiliation references inactive catalog rows | Data-quality review; do not mutate catalog in this runbook |
| Affiliation request error after gate-on | Profile write failed and rolled back | Treat as an availability incident; gate off to restore prior behavior |
| Drift after a batch job | A writer bypassed `set_student_affiliation` or gate was off | Stop, reconcile, escalate; do not hand-edit |

## 10. Data handling

Commands print aggregate counts only. Do not add ad-hoc queries that export Student identifiers,
names, emails or program histories. Population counts and DQ evidence belong in the approved
operational record, not in this repository.
