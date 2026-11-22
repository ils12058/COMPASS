# ADR-121: Separate Solo Parent Indicator from Civil Status

- Status: Accepted
- Date: 2026-11-21
- Scope: Individual Inventory civil-status choices, supplemental Solo Parent indicator, Student
  Support Context derivation, and Student Profiling reporting (API, PDF, XLSX, and web view).
- Amends: [ADR-048](ADR-048-student-support-profile-context.md)

## Context

Previously, `StudentInventory.civil_status_category` (`CivilStatusCategory`) offered four choices:
`SINGLE`, `MARRIED`, `SOLO_PARENT`, and `OTHER`. [ADR-048](ADR-048-student-support-profile-context.md)
left Solo Parent represented solely by `StudentInventory.civil_status_category == SOLO_PARENT`
instead of adding a field to `StudentSupportProfile`.

That representation conflated two distinct facts:

1. **Being a solo parent is not a civil status.** A student who is a solo parent may be single,
   widowed, separated, annulled, or married. Recording `SOLO_PARENT` as a civil status prevented a
   widowed or separated solo parent from recording both facts accurately.
2. **Source fidelity to the controlled F5 form.** In the official Individual Inventory form
   (`CNSC-OP-GCO-01F5` Rev. 0 / `UCN-OP-GCO-01F5` Rev. 1), Civil Status is a blank line and there
   is no solo-parent item. The solo-parent indicator was added to COMPASS from Guidance and
   Counseling Office requirements interviews, just like the other supplemental support indicators
   governed by [ADR-048](ADR-048-student-support-profile-context.md).

## Decision

### 1. Civil status choices

Prospective Individual Inventory choices for `civil_status_category` are changed to:

- `SINGLE` — Single
- `MARRIED` — Married
- `WIDOWED` — Widowed
- `SEPARATED` — Separated
- `ANNULLED` — Annulled
- `OTHER` — Other (requires non-blank `civil_status` detail text, as before)

As before, choosing a non-`OTHER` category stores its canonical label in the encrypted
`civil_status` text snapshot. Spouse details remain required only when `civil_status_category` is
`MARRIED`.

`SOLO_PARENT` remains on the Django model (`CivilStatusCategory`) solely as a legacy value so
historical submitted rows remain valid. It is removed from the writable API schema
(`CivilStatusCategoryValue`), rejected by `compass.inventory.services` on draft save and
submission, and never offered in the frontend editor.

### 2. Separate Solo Parent field on `StudentSupportProfile`

Following the [ADR-048](ADR-048-student-support-profile-context.md) source-fidelity boundary (facts
not present on the controlled F5 form live on `StudentSupportProfile` under `support_profile` and
never appear on the official F5 printout), Solo Parent status is stored as its own nullable choice
field:

- Model field: `StudentSupportProfile.solo_parent_status` (`SoloParentStatus`: `YES` / `NO`),
  nullable until answered, with no default.
- API path: `support_profile.solo_parent_status` (`SoloParentStatusValue`).
- Correction target: `family.solo_parent_status` in `InventoryCorrectionTarget`.
- Inventory editor: rendered in the **Student support information** group under **Family & Student
  support** as *"Are you a solo parent?"* (Yes / No), required on submission, with neutral guidance
  referencing Republic Act No. 11861.

This amends the *"Existing normalized facts are not duplicated"* section of
[ADR-048](ADR-048-student-support-profile-context.md): Solo Parent is no longer read from
`StudentInventory.civil_status_category`.

### 3. Student Support Context

`compass.student_support.services` derives the `SOLO_PARENT` support indicator strictly from
`StudentSupportProfile.solo_parent_status == SoloParentStatus.YES`, never from
`StudentInventory.civil_status_category`.

### 4. Student Profiling report

Following [ADR-109](ADR-109-student-profiling-reporting-accuracy-and-table-first-pdf.md):

- **Civil Status** (`sections.civil_status`) prints the six active civil statuses (`Single`,
  `Married`, `Widowed`, `Separated`, `Annulled`, `Other`). When submitted rows in the population
  carry the legacy `SOLO_PARENT` civil status, they are grouped in a plainly labeled row
  *Not specified (recorded before the update)* (emitted only when non-zero). No civil status is
  ever guessed from legacy data.
- **Solo Parent Status** (`sections.solo_parent_status`, titled *Distribution of Students based on
  Solo Parent Status*) is added immediately after **PWD Status** (`physical_disadvantage`) in the
  canonical API schema, PDF report, XLSX workbook, and web report view. It prints `Yes` and `No`,
  counting legacy `SOLO_PARENT` rows as `Yes` and any pre-update submitted rows left unanswered
  (`solo_parent_status IS NULL`) in *Not specified (recorded before the update)* (emitted only when
  non-zero) so totals and Program columns reconcile without guessing.

### 5. Existing data and migrations (no guessing)

- **Historical submitted Inventories** are immutable records: neither `civil_status_category` nor
  encrypted `civil_status` text is modified. `InventoryResponse` uses
  `CivilStatusCategoryResponseValue` (which includes `SOLO_PARENT`) so historical submitted
  Inventories remain readable through student history and counselor review endpoints.
- **Drafts** with legacy `civil_status_category == SOLO_PARENT` project `civil_status_category` as
  unanswered (`null`) on read so the student must choose a real civil status before submitting,
  while `support_profile.solo_parent_status` is pre-set to `YES` by the data migration.
- **Migrations**:
  1. `inventory/0002_civil_status_categories` — choices-only `AlterField` on
     `StudentInventory.civil_status_category` (no PostgreSQL DDL).
  2. `student_support/0002_solo_parent_status` — routine additive nullable `AddField` for
     `StudentSupportProfile.solo_parent_status` with no default.
  3. `student_support/0003_backfill_solo_parent_status` — idempotent `RunPython` backfill setting
     `solo_parent_status = YES` only on rows whose `StudentInventory.civil_status_category` is
     `SOLO_PARENT`, leaving all other rows unanswered (`NULL`) and leaving `StudentInventory` rows
     untouched.

## Explicit Boundaries

- **Official F5 printout untouched:** `be/compass/documents/templates/documents/inventory/*.html`
  and `compass/inventory/documents.py` are unchanged. The form prints the stored `civil_status`
  text (so new choices and historical records print accurately) and does not print the
  supplemental solo-parent answer.
- **Graduate Tracer Survey untouched:** its *Single Parent* civil-status option reflects the CHED
  Graduate Tracer Survey instrument and stays as-is.
- **No risk scoring or extra fields:** COMPASS collects only the self-reported Yes / No indicator
  with no Solo Parent ID upload, child count, or inferred classification.

## Consequences

- Students can accurately report both their civil status (e.g., Widowed, Separated, Annulled,
  Single, Married) and whether they are a solo parent.
- Counselors receive the `SOLO_PARENT` support indicator from the explicit field, and Student
  Profiling reports expose Solo Parent Status as its own reconciled distribution alongside PWD
  Status.
- Deployment requires running `migrate`, including the two source-digest-pinned reviewed migrations
  in `be/deploy/staging/database_preflight.py`.
