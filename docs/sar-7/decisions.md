# SAR-7 provisional decisions

Every decision below is an **engineering default for this slice**, not an institutional decision.
All D-SAR items referenced remain **Open** in `docs/sar-0/decisions.md`; that document and all
historical SAR documents were not modified.

## 1. Defaults applied

1. **Dedicated import capability (D-SAR-05).**
   `student_academics.import` is granted only to `IT_ADMIN` and the
   `HEAD_GUIDANCE_COUNSELOR` designation. It requires `student_academics.view` only: it does not
   require or imply `.manage`, and it grants no single-record period, graduation or verification
   authority. Scope is institution-wide, matching the provisional SAR-6 academic grants. An
   import-only override without `.view` is ineffective.
2. **Placement only (D-SAR-02, D-SAR-15).**
   The CSV changes `current_college` only. It never writes Program, verification, periods,
   enrollment, graduation, names, roles, lifecycle or account state. Imported placements remain
   `UNVERIFIED`, `current_program` stays null and `placement_effective_at` stays null. The import
   does not confirm enrollment and is not a verification act.
3. **College-only profile (D-SAR-15).**
   `program_code` is an unsupported header. The CSV has no email column and does not match on
   email.
4. **Missing rows never clear (D-SAR-07).**
   A Student absent from the CSV keeps the current placement. There is no bulk removal,
   withdrawal, graduation or “no current placement” row semantic. Blank `campus_code` or
   `college_code` is an `INVALID` row, not a clear.
5. **Verified and anomalous placements are protected (D-SAR-02, D-SAR-14).**
   A `VERIFIED` placement with a different target College is a `CONFLICT`; with the same target it
   is a `NOOP` and verification is unchanged. An unverified profile carrying a non-null
   `current_program` or `placement_effective_at` is a `CONFLICT`, because the import cannot safely
   replace those facts.
6. **No account creation or identity edits (D-SAR-15, D-SAR-10).**
   An unresolved institutional ID, a non-Student account and an inactive Student are conflicts; no
   account is created. `student_lifecycle_status` is not an import gate because
   lifecycle/enrollment semantics remain Open under D-SAR-10.
7. **Approved references only.**
   `campus_code` and `college_code` must resolve to an active Campus and an active College beneath
   that Campus. Unknown, inactive or mismatched references are conflicts.
8. **All-or-nothing (D-SAR-09/11/12).**
   Any conflict or invalid row aborts the commit with no write. Application uses the existing
   single writer `set_current_placement`; a mid-commit failure rolls back every row.
9. **Bounded input and recent MFA.**
   The limit is 1 MiB and 1,000 non-empty rows, matching the account CSV import. Recent MFA is
   required for both validation and commit.
10. **Counts-only summary audit.**
    One `student_academics.roster.imported` event is written only when `set_count > 0`, inside the
    same transaction, with `{total_rows, set_count, noop_count}` and no target, institutional IDs,
    names or codes. Per-row `student_academics.placement.set` events remain unchanged.
11. **Frontend authority display.**
    The staff-page action, route gate and command destination all read the `.import` capability
    directly. View-only and `.manage`-only accounts do not see the import entry.

## 2. Decisions that stay Open

| Decision | Why this slice does not settle it |
|---|---|
| **D-SAR-05** — capability grants and scope | SAR-7 applies one provisional grant pair and an institution-wide scope; role/designation/override matrix and College-scoped authority remain open |
| **D-SAR-15** — mandatory vs optional provisioning fields | The roster import adds no new provisioning field; it reconciles an existing placement only |
| **D-SAR-02** — meaning and authority of `VERIFIED` | The import refuses to overwrite verified placements but does not define verification authority or reliance |
| **D-SAR-14** — correction workflow for verified facts | Conflicts require manual resolution; no correction workflow, evidence or notification rule is added |
| **D-SAR-07** — removal/withdrawal/no placement | Missing rows never clear; there is no state model for removal or former placement |
| **D-SAR-09** — term/period calendar | No period or term is read or written |
| **D-SAR-10** — enrollment classification and lifecycle | Lifecycle is deliberately not an import gate |
| **D-SAR-11** — graduation confirmation | Graduation is never imported or changed |
| **D-SAR-12** — multiple programs/degrees | Program is never imported; `program_code` is rejected |
| **D-SAR-16** — Student visibility and correction requests | The import is a staff operation; student-facing visibility is unchanged |
| **D-SAR-19/20** — precedence and reconciliation definitions | The import writes the canonical placement but does not change Inventory precedence, report denominators or alignment rules |

## 3. Explicitly recorded for reviewers

- `.import` is institution-wide and separate from `.manage`.
- The exact CSV headers are `institutional_id,campus_code,college_code`; there are no email,
  Program, period, enrollment or graduation columns.
- Verified placements and profiles with non-null Program/effective date are conflicts.
- Missing rows never clear placements.
- The import never creates accounts.
- Commit is all-or-nothing and writes a counts-only summary event only when at least one placement
  is set.
