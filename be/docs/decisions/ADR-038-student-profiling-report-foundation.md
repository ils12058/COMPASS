# ADR-038: Student Profiling Report Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: read-only Student Profiling aggregate reporting

## Context

The Guidance and Counseling Office historical reference is titled *Students' Profile — First Year
Students — 2025-2026 (CCMS)*. It reflects the previous manual practice in which freshmen and
transferees were the primary Individual Inventory population. COMPASS deliberately expands that
practice into annual Student Profiling over submitted Individual Inventories for any configured
Academic Year, Campus, College, Program, and valid numeric Year Level.

The historical report is therefore a structural and presentation reference, not the scope boundary
of the new feature and not a trusted source for arithmetic, percentages, geography, age boundaries,
or enrollment truth.

The source Individual Inventory remains CNSC-OP-GCO-01F5 Revision 0. Program + Inventory Academic
Context (ADR-036) and Inventory Profiling + Controlled Data Normalization (ADR-037) provide the
normalized data used by this report.

## Decision

Create a focused read-only \`compass.reports\` package. The first report is Student Profiling and is
exposed through one aggregate GET endpoint:

\`GET /api/v1/reports/student-profile\`

Supported optional filters are Academic Year, Campus, College, Program, and Year Level. If Academic
Year is omitted, the canonical current Academic Year is resolved once and reused throughout the
request. Historical Academic Years remain selectable.

The report is calculated directly from PostgreSQL using existing domain truth. There is no report
table, snapshot table, analytics fact table, materialized view, Redis report cache, or generic
report-definition engine.

### Profile population

The demographic/profile population is:

- \`StudentInventory.academic_year == selected Academic Year\`
- \`submitted_at IS NOT NULL\`
- plus applicable Inventory academic filters

Current Student lifecycle is not a profile-population condition. A Student who later becomes
GRADUATED or FORMER remains represented in a historical submitted Inventory snapshot.

Campus, College, and Program profile filters use the annual Inventory Program chain:

\`StudentInventory.program -> Program -> College -> Campus\`

They do not use \`StudentAffiliation\` as academic truth. Historical inactive Campus, College, and
Program records remain valid filter targets.

Contradictory hierarchy filters are rejected rather than silently returning an empty report.

### Year Level terminology

Year Level remains the controlled numeric Inventory value. Display metadata uses ordinal labels:

- 1 -> 1st Year
- 2 -> 2nd Year
- 3 -> 3rd Year
- 4 -> 4th Year
- higher valid values continue the ordinal pattern

Freshman, Sophomore, Junior, and Senior are not canonical COMPASS report terminology, and Programs
are not assumed to last exactly four years.

### Dynamic Program columns and legacy Program

Program columns are derived dynamically from Program identities represented in the selected
submitted Inventory population. They are ordered deterministically by Campus code, College code,
and Program code.

\`Program.id\`, not \`course_currently_enrolled\` free text, is the grouping identity.

Legacy submitted Inventories with \`program = NULL\` are not dropped from an unfiltered report.
They appear as an explicit *Not recorded / legacy* Program column. Applying an explicit Program
filter naturally excludes those rows.

### Distributions and arithmetic

Each profiling section returns typed category rows containing:

- key and label
- total count
- overall percentage
- count for each dynamic Program column

Percentages use the section denominator and are calculated with Decimal arithmetic using
\`ROUND_HALF_UP\` to exactly two decimal places. A zero denominator yields 0.00. Independently
rounded rows are not forced to sum to exactly 100.00.

No historical percentage or total is copied.

### Sections

The Student Profiling response includes:

- Sex
- exact Age
- Civil Status
- Physical Disadvantage
- Current Religion
- Mother Life Status
- Father Life Status
- Parent Family Status
- Current City / Municipality
- Parent Annual Income
- Mother Occupation
- Father Occupation
- Living Condition

Sex uses the F5/model term *Sex*, not *Gender*.

Age is dynamically derived from Date of Birth at \`submitted_at.date()\` using the canonical
ADR-037 helper. The backend returns observed exact integer ages and does not reproduce the
historical overlapping "20" / "20 & Above" buckets.

Civil Status, Current Religion, Physical Disadvantage, Parent Family Status, parent life status,
occupation categories, and Living Condition use the normalized ADR-037 controlled values.

*Not specified* means the Student explicitly selected that normalized response. *Not recorded /
legacy* means the normalized field is null/missing because an older submitted Inventory predates
structured capture. These states remain distinct.

### Geographic residence

Student Profiling uses the CURRENT structured Inventory geographic snapshot. City/Municipality is
grouped by \`city_municipality_psgc_code\`; the saved display-name snapshot, Province context where
present, and Region context are returned for historical display.

A structured \`not_specified = true\` row maps to *Not specified*. A legacy submitted Inventory
with no CURRENT structured location maps to *Not recorded / legacy*.

The report does not parse \`current_address\`, does not make an external PSGC network call, and
does not mirror Philippine geographic master data.

### Parent annual income

The report reuses the canonical ADR-037 helpers for Father + Mother annual income combination and
income-band classification. Spouse income is excluded. Explicit NONE contributes zero.
NOT_SPECIFIED preserves unknown semantics. If legacy normalized parent-income status is not
deterministically available, the report uses *Not recorded / legacy*.

Income thresholds are not duplicated inside the report domain.

### Inventory Coverage is separate

Historical reports embedded "Without Individual Inventory" inside demographic tables. COMPASS
keeps coverage separate because a Student without an Inventory has no trustworthy Inventory
answers for Program, Year Level, Religion, parent data, and other profile fields.

For the current Academic Year, coverage uses the canonical current-Student semantics: active
account, primary STUDENT role, and lifecycle CURRENT. States are SUBMITTED, DRAFT, and MISSING.
DRAFT is not MISSING.

Campus and College coverage filters, when present, may use current Guidance
\`StudentAffiliation\` solely to scope the current eligible-account denominator. This does not make
StudentAffiliation Inventory Program truth and never mutates routing.

Program and Year Level never classify MISSING Students. Coverage metadata explicitly reports which
filters apply and which are ignored.

For a historical Academic Year, COMPASS may accurately count existing SUBMITTED and DRAFT
Inventories but cannot reconstruct authoritative MISSING coverage because there is no historical
enrollment/eligibility roster or Registrar feed. The response therefore uses
\`HISTORICAL_LIMITED\`, with no fabricated missing denominator.

### Methodology disclosure

The response contains methodology text explaining that profile statistics come from submitted
Individual Inventories for the selected Academic Year and applied profile filters. Students without
a submitted Inventory may lack trustworthy Inventory-based Program or Year Level classification, so
"Without Individual Inventory" is a separate coverage indicator and cannot be interpreted as
Program- or Year-Level-specific without another authoritative source.

Historical reports additionally disclose that authoritative missing-Inventory coverage cannot be
reconstructed from today's current Student accounts.

### Authorization and privacy

Add the scope-free capability \`reports.view\`.

The initial default grant is HEAD_GUIDANCE_COUNSELOR designation only. It is not granted by default
to ordinary Counselors, Guidance Services Staff, Students, IT Admin, or DPO. Existing explicit
per-user capability override behavior continues to apply.

The endpoint is aggregate-only. It returns no Student/User identifier, student number, name, email,
phone, complete address, parent name, occupation narrative, Physical Disadvantage narrative,
concerns/fears, counseling data, referral data, or other private narrative content.

No public sharing or export surface is introduced.

## Historical corrections deliberately applied by COMPASS

| Historical reference | COMPASS decision |
| --- | --- |
| First Year / Freshmen scope | Annual, filterable Student Profiling across valid Year Levels |
| Freshman/Sophomore/Junior/Senior terminology | 1st Year, 2nd Year, 3rd Year, 4th Year, etc. |
| Gender | Sex |
| Age rows include both 20 and 20 & Above | Dynamic exact age derived at submission date |
| Civil Status contains "Nort specified" | Canonical "Not specified" |
| Evangelical Christian percentage missing percent formatting | Typed calculated percentage |
| Parent section called Marital Status despite OFW/partner states | Parent Family Status |
| Municipality table includes Camarines Sur, a Province | PSGC City/Municipality identity with Region/Province context |
| BSIT / BSIS hardcoded columns | Dynamic Program columns |
| Parent-income total shows 145 / 84 / 217 | All totals calculated from selected query data |
| Father Farmer 39 / 217 shown as 17.74% | Standard calculation rounds to 17.97% |
| Truncated/inconsistent spreadsheet percentages | Decimal ROUND_HALF_UP to 2 decimals |
| Boarding house/Dormitory | Controlled F5 value Boarding House |
| Without Individual Inventory embedded in demographic rows | Separate transparent Inventory Coverage section |

## Boundaries

This slice adds no first-year-only mode, hardcoded Program catalog, report persistence, generic
reporting framework, data warehouse, materialized view, cache, PDF, HTML print template, chart API,
CSV/Excel export, broader Feedback/CSM/Exit/Graduate-Tracer analytics, Registrar/SIS integration,
historical roster, Program/Year inference for MISSING Students, fuzzy legacy classification,
address parsing, external PSGC dependency, or StudentAffiliation mutation.

No new database migration is required because the report is read-only and \`reports.view\` is
synchronized through the existing code-defined Accounts identity-policy mechanism.

The immediate follow-up slice is Student Profiling Report PDF / Print Foundation, which must consume
this validated aggregate service rather than duplicate its calculations.
