# ADR-088: Individual Inventory as optional Routine Interview provenance

## Status

Accepted. Supersedes only the Individual Inventory prerequisite in
[ADR-023](ADR-023-routine-interview.md) ("The record binds the submitted current-year
`StudentInventory` that governed creation"). The rest of ADR-023, the Encounter lifecycle in
[ADR-087](ADR-087-deterministic-routine-encounter-linking.md), the Inventory reopen workflow in
[ADR-055](ADR-055-inventory-counselor-review-navigation.md), and the canonical COUNSELING Service
in [ADR-060](ADR-060-canonical-counseling-service-bootstrap.md) are unchanged.

## Context

ADR-023 drew a conservative boundary. A Routine Interview required a submitted Individual
Inventory for the current Academic Year at creation, and bound it as the Routine's historical
context. Experience with the surrounding domains shows that coupling is now stronger than the
Routine Interview needs:

- The Student Intake and Counselor Evaluation do not use Inventory answers.
- Counseling is valid without an Inventory. ADR-060 already keeps the canonical COUNSELING
  Service free of the Routine prerequisite, and Counseling Encounters never needed one.
- ADR-087 made the Routine Interview a first-class record of a counseling interaction. Its
  Appointment or workspace provenance, not the Inventory, ties it to the interaction.
- Inventory has a controlled correction workflow. ADR-055's reopen sets `submitted_at` back to
  NULL on the same record. A Routine Interview bound to that record could still be edited, but
  Intake submission was refused, while an already submitted Intake could still be evaluated and
  finalized. The outcome depended on timing rather than on a Routine rule.
- Routine responses read the bound Inventory's live course, major, and name. After a reopen those
  are draft values, which other surfaces already treat as private until resubmission.
- The Academic Year existed only through the Inventory, so Routine history and filtering assumed
  an Inventory was always present. Direct Student discovery began from submitted Inventories, so
  Students with a missing, draft, or reopened Inventory could not be selected at all.

## Decision

### Invariant

A Routine Interview is an interaction-specific counseling record. It may be created, progressed,
and finalized independently of Individual Inventory. Individual Inventory remains a separate
annual domain.

### Initiation-time provenance

At creation, through the Appointment ensure or direct creation, COMPASS resolves optional
context:

| Current Academic Year | Current Inventory | `academic_year` | `inventory` |
| --- | --- | --- | --- |
| configured | submitted | that year | that Inventory |
| configured | missing, draft, or reopened | that year | NULL |
| not configured | n/a | NULL | NULL |

- The submitted Inventory row is locked while it is bound, so a concurrent reopen cannot make
  the binding untrue.
- A draft or reopened Inventory is never bound.
- No Inventory is created to satisfy the Routine Interview.
- Creation no longer requires an Academic Year to be configured.

`inventory` identifies the annual source record that was submitted at initiation. It is
provenance, not a frozen copy of the record's fields. NULL records the fact that no submitted
Inventory was available at initiation.

### No retroactive binding

A Routine Interview that began without an Inventory stays unbound. A later submission is bound
only by later Routine Interviews. No Inventory event writes Routine rows.

### Independent lifecycle

Intake submission depends only on Routine-owned rules: the Student relationship, current Student
lifecycle, an actionable parent Appointment, Intake state, and Intake content.

The following never block or reopen an existing Routine Interview, and never change its Intake,
Evaluation, Encounter link, Academic Year, ownership, or provenance:

- reopening or resubmitting the bound Inventory;
- a missing Inventory;
- a switch of the current Academic Year.

### Academic Year

`RoutineInterview.academic_year` is the configured current Academic Year at initiation.

- When an Inventory is bound, it equals that Inventory's year.
- A later Academic Year switch never rewrites it.
- It is never inferred from timestamps or labels.
- The Counselor queue's Academic Year filter uses it. Records without a year match no year filter
  but stay visible unfiltered.
- Audit metadata for creation, Intake submission, and finalization reports this year (or null).
  Creation also reports a structural `inventory_bound` flag. No Inventory content is logged.

### Candidates

- **Direct creation:** candidates are active Students in the CURRENT lifecycle, as the existing
  direct-create authority already allows. Each candidate carries Inventory context only when a
  submitted current-year Inventory exists. Program or course is never derived from
  StudentAffiliation (ADR-036).
- **Appointment candidates:** Students list their eligible Counseling Appointments without an
  Inventory or a configured Academic Year.

`routine_interview_inventory_required` no longer exists.

### API and privacy

Routine responses carry:

- `academic_year`: a nullable year summary.
- `inventory_context`: nullable. Null means no submitted Inventory was bound at initiation.

When `inventory_context` is present, it has `available`:

- `available: true`: course, major, and Inventory full name come from the bound record's
  current submitted values.
- `available: false`: the bound record is reopened for correction. Its draft values are withheld
  (null) until it is resubmitted.

Student identity otherwise comes from the Routine Interview's Student, not from the Inventory.

### Counseling Context

A context with a bound Routine Interview Inventory shows that record under its current
submitted or draft state, as before.

Without a bound Inventory, the Inventory section uses the general current-Inventory enrichment:
the same resolver a context without a Routine Interview uses. It reports MISSING, DRAFT, or
SUBMITTED, and without a configured Academic Year the endpoint keeps its existing error. That
enrichment describes the Student today. It never becomes the Routine Interview's provenance and
never writes `RoutineInterview.inventory`.

### Unchanged

The following are unchanged:

- `Service.requires_current_inventory` and its Appointment booking prerequisite, including the
  canonical COUNSELING default of not requiring it. A Routine Interview does not re-enforce it
  once an Appointment exists.
- Inventory submission, reopen authority, and correction semantics.
- Student Support.
- ADR-087 Encounter linking, which works the same with or without a bound Inventory.

### Migration

`0004_optional_inventory_and_academic_year`:

- Makes `inventory` nullable (PROTECT when present).
- Adds a nullable `academic_year` (PROTECT).
- Under a table lock, backfills each existing row's year from its bound Inventory.

Existing links, content, statuses, Encounter links, and audit history are untouched. Reversal is
refused once any unbound Routine Interview exists, because the previous schema cannot represent
it.

## Consequences

- Students and Counselors can complete Routine Interviews for Students who have not submitted
  their Inventory, or whose Inventory is being corrected.
- Inventory, when present, remains initiation-time provenance.
- Clients must treat Routine Inventory context as optional, and read the Routine's own Academic
  Year.
