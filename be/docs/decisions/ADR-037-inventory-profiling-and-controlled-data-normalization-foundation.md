# ADR-037: Inventory Profiling and Controlled Data Normalization Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: `compass.inventory`

## Context

The Guidance and Counseling Office historically prepares a Students' Profile for first-year
students. The supplied 2025-2026 CCMS profile demonstrates the reporting dimensions the office
needs to aggregate, while the three-page Individual Inventory
`CNSC-OP-GCO-01F5`, Revision 0, remains the source questionnaire for the annual Student
Inventory.

The historical profile is a structural reporting target, not a source of trusted arithmetic,
spelling, percentage formulas, geographic hierarchy, or a complete current Program roster.
COMPASS remains a Guidance and Counseling platform rather than a Registrar, SIS, enrollment
ledger, or roster mirror.

PR #20 already established configurable Organization `Program`, annual
`StudentInventory.program`, controlled numeric `year_level`, the frozen
`course_currently_enrolled` Program-name snapshot, and the separation between Inventory Program
and Guidance `StudentAffiliation`.

## Decision

Normalize only the categorical facts needed for deterministic future profiling while preserving
the readable F5 snapshots and legacy submitted records. Small stable vocabularies use explicit
choices; large/evolving external reference data uses stable identifiers plus display snapshots;
genuinely narrative answers stay text.

No existing submitted Inventory is backfilled or reclassified from legacy free text. New fields
are nullable for migration compatibility. The final submission boundary, rather than a destructive
migration, establishes prospective completeness.

### Printed F5 fields and COMPASS digital extensions

The printed F5 explicitly contains Sex, Date of Birth, Civil Status, Current Religion, Physical
Disadvantage, parent Occupation, separate Father/Mother/Spouse annual income, parent marital-status
choices, Current/Permanent Address, Living Condition, transportation Mode/Frequency/Fare, Course
currently enrolled, and Major.

Year Level remains the COMPASS digital academic-context metadata introduced by PR #20; it is not
represented as a newly invented printed F5 field. Mother/Father living-or-deceased status is also
a COMPASS digital profiling extension because the historical Students' Profile reports it but the
printed F5 does not ask it explicitly. These digital extensions do not change the official
controlled-document identity: `CNSC-OP-GCO-01F5`, Revision 0 remains unchanged.

### Controlled personal categories

`civil_status_category` uses Single, Married, Solo Parent, Other, and Not specified while the
legacy/readable `civil_status` text remains. Fixed selections normalize the text snapshot to the
canonical label; Other requires explicit detail; Not specified does not invent text.

`current_religion_category` uses the report-oriented small vocabulary represented by the
historical profile, plus None, Other, and Not specified. Current Religion, rather than Religion
from Birth, is the profiling category. Fixed selections may normalize the readable
`current_religion` snapshot; Other requires detail. None and Not specified are deliberately
different states. No Religion catalog is introduced and no historical religion string is
classified automatically.

`physical_disadvantage_status` distinguishes None, Has physical disadvantage, and Not specified.
The F5 `physical_disadvantage` text remains descriptive detail. Has physical disadvantage
requires detail; None clears contradictory detail. COMPASS does not infer a medical or legal
diagnosis from narrative text.

The legacy grouped `parent_statuses` values remain readable because the printed F5 instructs the
respondent to check and underline grouped choices. A new single `parent_status_category`
preserves the atomic reporting categories required by the historical profile without guessing
which legacy sub-choice was underlined.

### Family profiling normalization

Father and Mother family rows gain explicit `life_status` values Living, Deceased, or Not
specified. These are digital profiling extensions and are never inferred from blank names,
addresses, occupations, income, or other family details. Spouse rows are not forced to carry
parent-specific profiling semantics.

The descriptive `occupation` field remains. A separate `occupation_category` captures
Government Employee, Private Employee, Laborer, Farmer, Self Employed, OFW, None, Other, or Not
specified. Other requires narrative detail; no keyword classifier maps strings such as "Farmer"
or "Teacher at DepEd" into categories.

The existing decimal `annual_income_previous_year` remains the numeric amount.
`annual_income_status` distinguishes Reported, None, and Not specified. Reported requires a
positive amount, None is explicit zero, and Not specified requires no numeric assumption.

For future profiling, combined parent annual income is a pure rule: Father plus Mother, excluding
Spouse. None contributes zero. If either relevant parent is Not specified, the combined result is
Not specified rather than silently treating unknown as zero. Income bands are derived, not stored:

- Poor: below 131,484
- Low Income: 131,484 to below 262,968
- Lower Middle Income: 262,968 to below 525,936
- Middle Middle Income: 525,936 to below 920,388
- Upper Middle Income: 920,388 to below 1,577,808
- Upper Income: 1,577,808 through 2,626,680
- Rich: above 2,626,680
- None: combined known income equals zero
- Not specified: combined income cannot be determined

No income-band model, rules engine, or formula DSL is introduced.

### Geographic identity and PSGC trust boundary

Current and Permanent full address text remain annual descriptive snapshots. Structured geography
is stored separately in `InventoryGeographicLocation`, with one CURRENT and one PERMANENT row at
most. Each row stores bounded Philippine Standard Geographic Code identifiers and the selected
display-name snapshots for Region, optional Province, City/Municipality, and optional Barangay.

Province is nullable because valid Philippine locations need not fit a mandatory province
relationship. Required and optional code/name pairs must be complete together. Display names are
trimmed. An explicit `not_specified` state represents an unknown structured location without
inventing a fake PSGC code.

COMPASS does not mirror Region, Province, City/Municipality, or Barangay master tables, does not
hardcode Camarines Norte municipalities, does not parse address strings, and does not call an
external PSGC service during Inventory mutation. A future frontend may use PSA PSGC, PSGC Cloud,
or another approved PSGC-compatible provider for dependent selection, but the backend remains
provider-agnostic and stores only identifiers plus display snapshots. Historical rendering never
depends on a future external lookup.

### Living and transportation

The existing F5 `LivingArrangement` choices Own House, With Relatives, and Boarding House are
reused and are required at new/current submission. No parallel residence catalog is created.

Transportation Mode remains the existing F5-controlled vocabulary. The legacy `frequency` text
is retained, while `frequency_category` provides Daily, Several times a week, Weekly,
Occasional, Other, and Not specified. Fixed categories normalize the text snapshot; Other requires
detail. Historical free-text frequency is not auto-classified.

Transportation fare remains Decimal and gains database-level non-negative protection. Fare is a
numeric quantity, not a hardcoded peso enum or tariff-management domain.

### Submission and legacy compatibility

Draft creation remains lightweight and incomplete drafts remain editable. A new/current submitted
Inventory requires the PR #20 Program and Year Level requirements plus Sex, Date of Birth, Civil
Status category, Current Religion category, Physical Disadvantage status, atomic Parent Family
Status, Living Arrangement, a deliberate CURRENT structured geographic response, and Father and
Mother rows with life, occupation, and annual-income statuses. Not specified is an explicit
structured response where offered.

Transportation modes are not required merely to submit. When a transportation row exists, its
frequency category must be explicit and its fare, when supplied, must be non-negative.

Existing submitted Inventories may have null normalized fields, grouped parent statuses, free-text
occupation/frequency, no geographic snapshot, and pre-PR20 null Program/Year Level. They remain
readable and immutable. No migration fuzzy-classifies Civil Status, Religion, Physical
Disadvantage, parent underlining, addresses, occupations, or transportation frequency.

Historical age is derived from Date of Birth and `submitted_at.date()`, not today's date, so
later reports do not silently age historical respondents. Future age buckets must be
non-overlapping; the historical report's separate "20" and "20 & Above" rows must not be copied
literally.

## Historical-profile corrections reserved for the reporting slice

The next reporting implementation must calculate counts and percentages from live query results,
not copy spreadsheet totals or percentages. In particular, the historical profile contains the
overlapping age labels above, the typo "Nort specified", an inconsistent parent-income total
showing 145 and 84 against 217, percentage/formatting inconsistencies, and a table titled
Municipality that includes Camarines Sur, which is a Province.

Program columns must be dynamic from normalized Program/Inventory data and must not hardcode the
sample BSIT/BSIS columns. A Student with no current Inventory has no trustworthy Inventory Program
or Year Level, so future reporting must not fabricate Program-specific missing-Inventory counts.

## Boundaries

This foundation adds no StudentAcademicClassification, enrollment history, Registrar/SIS or
roster subsystem, CAPS integration, automatic Academic-Year synchronization, Major catalog,
Block/Section/Semester/Curriculum model, Religion catalog, PSGC database mirror, GIS engine,
transport tariff administration, User/Profile ownership of annual Inventory context, or
StudentAffiliation mutation.

No profiling endpoint, report model, PDF, percentages, dashboard, chart, materialized view, or
generic report engine is implemented here. The next focused slice is the Students' Profile /
First-Year Profiling Report consuming this normalized Inventory foundation.
