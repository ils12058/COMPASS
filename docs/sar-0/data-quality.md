# Data quality — structural findings and reproducible checks

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
**Execution status:** no database was queried. Every population-level value below is **Unknown**.
The SQL is provided so an authorized read-only operator can reproduce the checks; it selects counts
only and must not be extended to select names, institutional IDs, emails or free text.

## 1. Structural findings

These are verified from schema and service code, independent of the current population.

### S1 — There is no single current academic placement

**Verified.** `StudentAffiliation` stores only College (`be/compass/organization/models.py:199-220`).
Program and Year Level exist only on a per-Academic-Year Inventory
(`be/compass/inventory/models.py:224-240`). No row states “this Student is currently in Program P,
Year Level Y, College C.”

**Consequence:** a Student can have an affiliation College with no Inventory, an Inventory Program
with no affiliation, or both with different Colleges.

### S2 — Inventory does not validate the affiliation College

**Verified.** `replace_current_inventory` validates an active Program and its active
College/Campus ancestry, then enforces Program year-level policy
(`be/compass/inventory/services.py:544-571,1167-1245`). It never compares
`program.college_id` with the Student's `StudentAffiliation.college_id`.

**Consequence:** invalid Program/College combinations are accepted by the domain.

### S3 — Placement history is destructive

**Verified.** Transfer updates the existing affiliation row in place; removal deletes it
(`be/compass/organization/services.py:271-325`). Audit metadata stores College IDs, not a durable
history table (`be/compass/audit/actions.py:43-45`).

**Consequence:** prior College is not reliably queryable, and prior Program/Year Level must be
reconstructed from Inventories or snapshots.

### S4 — No term, enrollment, source or verification model

**Verified.** There is no term/period model, no enrollment status field and no academic
verification field in organization, inventory, Good Moral or Tracer. The Good Moral semester is a
two-value text field (`be/compass/good_moral/models.py:42-45,121`), not a calendar FK.

**Consequence:** “enrolled”, “verified” and “term” cannot be answered from current data.

### S5 — Academic Year is a label, not a period

**Verified.** `AcademicYear` has a unique `YYYY-YYYY` label and one current flag; it has no start
date, end date, term list or enrollment window (`be/compass/organization/models.py:23-40`;
`be/compass/organization/academic_years.py:33-68`).

**Consequence:** the proposal's `term_code` cannot be derived from the existing Academic Year.

### S6 — Lifecycle can be stale

**Verified.** Role change sets `CURRENT` when entering `STUDENT` with a null value but does not clear
the value when leaving `STUDENT` (`be/compass/account_management/services.py:976-979`). Role change
away from `STUDENT` is blocked while an affiliation exists, but the lifecycle value remains stored.

**Consequence:** lifecycle anomalies are possible in the population even if every supported write
followed the intended path. Eligibility predicates use active + role + lifecycle
(`be/compass/accounts/services.py:113-122`), so the practical impact depends on population state.

### S7 — Tracer College/Program consistency is service-only

**Verified.** The Tracer service checks that the selected Program belongs to the selected College and
that the graduation year is 1900..current year (`be/compass/graduate_tracer/services.py:556-584`).
The database has no cross-field check; both FKs are nullable
(`be/compass/graduate_tracer/models.py:259-273`).

**Consequence:** rows written outside the service (imports, manual operations, future code paths)
could contain a mismatched pair. The current service path is protected.

### S8 — Program retirement is not blocked by academic references

**Verified.** Catalog impact blocks College/Campus retirement on active Student affiliations, but
Program retirement has no blocker keys (`be/compass/organization/catalog_services.py:572-590`).
Historical Inventories keep a `PROTECT` FK to the Program.

**Consequence:** an active Program can be retired while it is the Program on a Student's latest
Inventory. Historical references remain, but new selection is refused. This is an ORG-4 decision
area, not a SAR-1 blocker.

### S9 — Historical names are not effective-dated

**Verified.** Inventory and Tracer store FKs to current `Program`/`College` rows, not name
snapshots. Only Good Moral snapshots names. Reports label Year Levels above 4 as “recorded value”
(`be/compass/reports/services.py:335-344`).

**Consequence:** historical reports can show today's names for past periods. ORG decision D14
records this as unresolved (`docs/org-4/institutional-decision-register.md:24`).

### S10 — No adopted retention category for academic records

**Verified.** The code-owned retention register covers only Graduate Tracer responses and
E-Counseling recordings/transcripts; all three are `NOT_ADOPTED`
(`be/compass/privacy_governance/retention_policy_register.py:96-118`). Student affiliation,
Inventory and Good Moral are not categories in the register.

**Consequence:** SAR cannot claim an approved retention period, disposition rule or deletion
behavior. This is a DPO/Records decision.

## 2. Duplicates and orphans

**Verified.** The following are database guarantees, not population risks:

- Two current affiliations for one Student are impossible: `student` is the primary key
  (`be/compass/organization/models.py:199-206`).
- Two Inventories for one Student and Academic Year are impossible
  (`be/compass/inventory/models.py:372-375`).
- Two case-insensitive identical emails or institutional IDs are impossible
  (`be/compass/accounts/models.py:218-226`).
- Affiliations, Inventories and Tracers cannot reference a missing User/College/Program through
  the ORM while FKs are enforced (`PROTECT` on the relevant relations).

**Inferred.** “Semantic orphans” remain possible: an affiliation to an inactive College/Campus, a
submitted Inventory whose Program is inactive/retired, or a Student with no Counselor
responsibility for their College. These are reported by the catalog impact and routing resolution,
not by referential integrity.

## 3. Reproducible aggregate checks

Run as a read-only role. Each query returns a count only. Do not add identifying columns.

### DQ-01 — Active current Students with no affiliation

```sql
SELECT count(*) AS active_current_students_without_affiliation
FROM accounts_user u
JOIN accounts_role r ON r.id = u.role_id
LEFT JOIN organization_studentaffiliation a ON a.student_id = u.id
WHERE u.is_active
  AND r.code = 'STUDENT'
  AND u.student_lifecycle_status = 'CURRENT'
  AND a.student_id IS NULL;
```

Expected if > 0: Students who cannot route, appear in operational scope, or request current-student
Good Moral. **Observed: Unknown (not executed).**

### DQ-02 — Affiliations on non-Student or inactive accounts

```sql
SELECT
  count(*) FILTER (WHERE NOT u.is_active) AS inactive_account_affiliations,
  count(*) FILTER (WHERE u.is_active AND r.code <> 'STUDENT') AS non_student_affiliations,
  count(*) FILTER (WHERE r.id IS NULL) AS missing_role_affiliations
FROM organization_studentaffiliation a
JOIN accounts_user u ON u.id = a.student_id
LEFT JOIN accounts_role r ON r.id = u.role_id;
```

Expected if > 0: legacy/stale placement records that need a backfill inclusion rule. **Unknown.**

### DQ-03 — Affiliations to inactive College or Campus

```sql
SELECT count(*) AS affiliations_to_inactive_organization
FROM organization_studentaffiliation a
JOIN organization_college c ON c.id = a.college_id
JOIN organization_campus cp ON cp.id = c.campus_id
WHERE NOT c.is_active OR NOT cp.is_active;
```

Expected if > 0: operational denial (`INACTIVE_ORGANIZATION`) or invisibility. **Unknown.**

### DQ-04 — Current-year submitted Inventory College disagrees with affiliation

```sql
SELECT count(*) AS current_inventory_affiliation_college_mismatch
FROM inventory_studentinventory i
JOIN organization_academicyear ay
  ON ay.id = i.academic_year_id AND ay.is_current
JOIN organization_program p ON p.id = i.program_id
JOIN organization_studentaffiliation a ON a.student_id = i.student_id
WHERE i.submitted_at IS NOT NULL
  AND p.college_id <> a.college_id;
```

Expected if > 0: the Student's Good Moral College snapshot and course snapshot can come from
different Colleges; reports can classify the Student differently by mode. **Unknown.**

### DQ-05 — Submitted Inventories missing Program or Year Level

```sql
SELECT
  count(*) FILTER (WHERE i.program_id IS NULL) AS submitted_without_program,
  count(*) FILTER (WHERE i.year_level IS NULL) AS submitted_without_year_level
FROM inventory_studentinventory i
WHERE i.submitted_at IS NOT NULL;
```

Expected if > 0: should be impossible through the service; indicates a legacy/import path.
**Unknown.**

### DQ-06 — Year Level outside the Program's configured policy

```sql
SELECT count(*) AS submitted_year_level_outside_policy
FROM inventory_studentinventory i
JOIN organization_program p ON p.id = i.program_id
WHERE i.submitted_at IS NOT NULL
  AND i.year_level IS NOT NULL
  AND p.year_level_policy_status = 'CONFIGURED'
  AND NOT (i.year_level = ANY (p.applicable_year_levels));
```

Expected if > 0: historical data predates policy activation or bypassed validation. **Unknown.**

### DQ-07 — Denormalized course text drifts from the Program name

```sql
SELECT count(*) AS course_text_program_name_mismatch
FROM inventory_studentinventory i
JOIN organization_program p ON p.id = i.program_id
WHERE i.program_id IS NOT NULL
  AND i.course_currently_enrolled <> p.name;
```

Expected if > 0: a name-only historical record or a bypassed save path. The service rewrites the
field on save (`be/compass/inventory/services.py:1207-1212`). **Unknown.**

### DQ-08 — Tracer Program/College mismatch

```sql
SELECT count(*) AS tracer_program_college_mismatch
FROM graduate_tracer_graduatetracerresponse t
JOIN organization_program p ON p.id = t.graduated_program_id
WHERE t.graduated_program_id IS NOT NULL
  AND t.graduated_college_id IS NOT NULL
  AND p.college_id <> t.graduated_college_id;
```

Expected if > 0: a row bypassed the service check. **Unknown.**

### DQ-09 — Tracer graduation year out of supported range

```sql
SELECT count(*) AS tracer_graduation_year_out_of_range
FROM graduate_tracer_graduatetracerresponse t
WHERE t.graduation_year IS NOT NULL
  AND (t.graduation_year < 1900 OR t.graduation_year > EXTRACT(YEAR FROM CURRENT_DATE));
```

Expected if > 0: historical import or a time-dependent edge case. **Unknown.**

### DQ-10 — Lifecycle anomalies

```sql
SELECT
  count(*) FILTER (
    WHERE r.code <> 'STUDENT' AND u.student_lifecycle_status IS NOT NULL
  ) AS non_student_with_lifecycle,
  count(*) FILTER (
    WHERE r.code = 'STUDENT' AND u.student_lifecycle_status IS NULL
  ) AS student_without_lifecycle,
  count(*) FILTER (
    WHERE NOT u.is_active AND u.student_lifecycle_status = 'CURRENT'
  ) AS inactive_current
FROM accounts_user u
JOIN accounts_role r ON r.id = u.role_id;
```

Expected if > 0: role/lifecycle drift; the non-student cases are expected to be possible because
role changes do not clear the value. **Unknown.**

### DQ-11 — Current-student Good Moral snapshots with empty academic fields

```sql
SELECT count(*) AS current_good_moral_missing_snapshot
FROM good_moral_goodmoralrequest g
WHERE g.variant = 'CURRENT_STUDENT'
  AND g.status <> 'CANCELLED'
  AND (
    g.college_snapshot = ''
    OR g.course_snapshot = ''
    OR g.year_level_snapshot = ''
  );
```

Expected if > 0: a legacy or corrected record that cannot be re-derived after a transfer.
**Unknown.**

### DQ-12 — Current-student Good Moral snapshot College differs from current affiliation name

```sql
SELECT count(*) AS good_moral_college_snapshot_drift
FROM good_moral_goodmoralrequest g
JOIN organization_studentaffiliation a ON a.student_id = g.student_id
JOIN organization_college c ON c.id = a.college_id
WHERE g.variant = 'CURRENT_STUDENT'
  AND g.college_snapshot <> c.name;
```

Expected if > 0: either a legitimate transfer after the request or a College rename; both are
historical facts, not necessarily defects. Requires a reason breakdown before any remediation.
**Unknown.**

### DQ-13 — Current-year coverage: current Students without a submitted Inventory

```sql
SELECT count(*) AS current_students_without_submitted_inventory
FROM accounts_user u
JOIN accounts_role r ON r.id = u.role_id
JOIN organization_academicyear ay ON ay.is_current
WHERE u.is_active
  AND r.code = 'STUDENT'
  AND u.student_lifecycle_status = 'CURRENT'
  AND NOT EXISTS (
    SELECT 1
    FROM inventory_studentinventory i
    WHERE i.student_id = u.id
      AND i.academic_year_id = ay.id
      AND i.submitted_at IS NOT NULL
  );
```

Expected if > 0: this is the report coverage gap and a Good Moral F4 prerequisite gap. **Unknown.**

### DQ-14 — Academic Year configuration

```sql
SELECT
  count(*) AS total_years,
  count(*) FILTER (WHERE is_current) AS current_years
FROM organization_academicyear;
```

Expected: `current_years` should be 1; 0 is database-permitted and causes explicit service
conflicts. **Unknown.**

### DQ-15 — Submitted Inventory with a retired Program

```sql
SELECT count(*) AS submitted_inventory_with_inactive_program
FROM inventory_studentinventory i
JOIN organization_program p ON p.id = i.program_id
WHERE i.submitted_at IS NOT NULL AND NOT p.is_active;
```

Expected if > 0: historical facts referencing a retired Program. This is expected over time and
must not be “fixed” by rewriting history. **Unknown.**

### DQ-16 — Students with an affiliation but no Counselor responsibility for that College

```sql
SELECT count(*) AS students_without_college_counselor
FROM organization_studentaffiliation a
JOIN accounts_user u ON u.id = a.student_id AND u.is_active
JOIN accounts_role r ON r.id = u.role_id AND r.code = 'STUDENT'
WHERE NOT EXISTS (
  SELECT 1
  FROM organization_counselorresponsibility cr
  JOIN accounts_user c ON c.id = cr.counselor_id
  WHERE cr.college_id = a.college_id
    AND c.is_active
);
```

Expected if > 0: booking may fall back to unique Head Guidance or fail unresolved; not necessarily a
data defect. **Unknown.**

## 4. Aggregate-only evidence rules

- Do not export institutional IDs, names, emails, free-text majors or counseling content for this
  audit.
- A mismatch count is not a remediation list. Any case-level review requires a separately approved
  data-handling procedure and least-privilege access.
- Do not correct historical snapshots to match current affiliation or Program names. The Good Moral
  and Inventory records are evidence of what was recorded at the time.
- Do not deduplicate Students by name; identity uniqueness is by email/institutional ID, and name
  collisions are not duplicates.

## 5. Population conclusions

**Unknown.** This audit cannot state how many Students lack affiliations, how many Inventories
disagree with affiliations, how many snapshots have drifted, or whether any lifecycle anomaly
exists. Those answers require the authorized read-only queries above. Every remediation cost and
backfill exclusion should be sized only after those counts are available.
