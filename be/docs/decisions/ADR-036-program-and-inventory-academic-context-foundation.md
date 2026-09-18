# ADR-036: Program and Inventory Academic Context Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: `compass.organization` Program catalog and `compass.inventory` academic context

## Context

COMPASS needs normalized Program and Year Level data for Guidance workflows and future profiling,
but it is not the institution's Registrar, SIS, enrollment system, curriculum system, or academic
progression engine.

A prior design proposed a separate annual `StudentAcademicClassification` record. That approach
was rejected because COMPASS has no authoritative CAPS/Registrar integration that can establish
official annual enrollment, shifting dates, semester registration, progression, block/section
membership, or transfer history. Maintaining that state independently would overstate what
COMPASS actually knows.

The controlled Individual Inventory (CNSC-OP-GCO-01F5 Rev.0) visibly contains
`Course currently enrolled` and `Major`. It does not visibly provide a canonical Program
identifier, and Year Level is not treated here as a printed F5 field. The historical profiling
report demonstrates why normalized Program context is useful, but it does not establish a complete
current institutional Program catalog or an authoritative non-responder roster.

## Decision

Add configurable `Program` master/reference data to `compass.organization`:

- Program belongs to exactly one College.
- Code is normalized using existing Organization conventions.
- Code is unique within College.
- Name is trimmed.
- Program can be enabled/disabled.
- College ownership is immutable through ordinary update operations.
- No production BSIT, BSIS, or other Program rows are seeded from historical reports.

An active Program requires an active parent College and Campus. Program create/enable enforces that
hierarchy. A College cannot be disabled while it owns an active Program, in addition to the
existing StudentAffiliation and CounselorResponsibility protections. Inactive Programs remain
historically referenceable and are never cascade-deleted through this workflow.

Reuse existing `organization.view` for Program read and `organization.manage` plus recent MFA
for Program mutations. No new capabilities are added.

## Inventory academic context

The annual `StudentInventory` remains the place where COMPASS legitimately obtains the
Student-provided academic context for that Academic Year. Add nullable migration-compatible fields:

- `program -> Program` using `PROTECT`
- `year_level` as a nullable positive small integer constrained to 1 through 10 when present

Keep the existing `major` text field as optional Inventory-local data. Do not introduce Major,
ProgramMajor, Block, Section, Semester, Curriculum, enrollment-history, roster, or academic
classification models.

`year_level` is COMPASS digital academic-context metadata attached to the annual Inventory for
normalization and future reporting. It must not be described as a printed field on the supplied F5
when the source does not visibly show one.

## Course snapshot compatibility

Keep `course_currently_enrolled` because it is part of the controlled F5 response and historical
snapshot. During an editable Inventory, when a Program is selected, the server derives
`course_currently_enrolled` from `Program.name`. Client-supplied course text cannot override a
selected Program.

The current request schema temporarily continues accepting `course_currently_enrolled` for
backward compatibility. Structured `program_id` and numeric `year_level` are added. Once a
Program is selected, the server-owned Program name wins.

An empty DRAFT may exist without Program or Year Level. Current Inventory submission requires:

- selected Program
- Year Level
- active Program
- active parent College
- active parent Campus

At final submission, `course_currently_enrolled` is refreshed from the current Program name and
then frozen with the rest of the submitted Inventory.

A later Program rename or deactivation does not rewrite submitted Inventory text. Legacy submitted
Inventories with null Program/Year Level remain readable and immutable. There is no data migration
that guesses Program from historical free-text course strings.

## StudentAffiliation separation

`StudentAffiliation` remains Guidance-managed organizational routing and responsibility state.
`Inventory.program` is the Student-provided annual academic context.

Inventory update or submission does not mutate StudentAffiliation. A Program/College mismatch is
allowed and does not block submission because silently changing Guidance scope from a Student's
self-reported Inventory would be unsafe. No reconciliation engine is introduced.

Academic Year switching retains its existing narrow behavior. It does not move affiliations,
create Programs, create Inventories, advance Year Level, or perform annual academic transitions.

## Future reporting boundary

Without an authoritative CAPS/Registrar roster, COMPASS can truthfully observe current eligible
Student accounts and their current-Academic-Year Inventory status: MISSING, DRAFT, or SUBMITTED.
It can profile Program and Year Level only where structured Inventory context exists.

COMPASS must not fabricate Program- or Year-Level-specific counts for Students with no Inventory
when those facts are unknown. The final mapping of MISSING/DRAFT/SUBMITTED into a presentation
label such as "Without Individual Inventory" belongs to the later Reports/Profiling slice.

If a future CAPS/Registrar integration becomes available, it may become an authoritative source
for enrollment, Program, and Year Level validation or prefill. No such integration is implemented
here.

## Out of scope

This foundation adds no StudentAcademicClassification, Registrar/SIS subsystem, enrollment or
transfer ledger, academic-year synchronization engine, Major catalog, Block/Section model,
semester/curriculum model, roster/denominator table, CAPS integration, profiling endpoint,
analytics dashboard, percentages, or report/PDF generation.
