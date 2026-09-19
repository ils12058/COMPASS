# ADR-040: Report XLSX Export and Student Profiling Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: small reusable XLSX plumbing and Student Profiling XLSX export

## Context

COMPASS analytical reports need a tabular export that remains useful outside the web application.
XLSX is the standard tabular export format. CSV is not supported by this decision. PDF remains
optional and report-specific; it is not implied by the reporting architecture.

Student Profiling is the first XLSX consumer because ADR-038 already established
build_student_profiling_report(...) as its canonical aggregate source, and ADR-039 added an
independent presentation-only PDF representation.

## Decision

Add:

GET /api/v1/reports/student-profile/xlsx

The endpoint accepts the same optional Academic Year, Campus, College, Program, and Year Level
filters as the JSON and PDF representations and reuses reports.view authorization. No new
reports.export/download capability and no recent-MFA requirement are introduced.

The service calls build_student_profiling_report(...) exactly once. The internal authoritative
result is consumed directly. It is not queried again, passed through the JSON endpoint, serialized
through the public Pydantic response schema, or reconstructed from response JSON.

Canonical report values remain authoritative for counts, ages, income classifications, coverage,
geography, totals, and percentages.

## XLSX library and dependency boundary

Use openpyxl 3.1.5, pinned through normal uv dependency management. It is a focused maintained
Python XLSX library and does not require pandas, numpy, LibreOffice, Java, or a second spreadsheet
stack.

Only small reusable mechanics are shared:

- explicit safe text-cell writing
- restrained header/table formatting
- capped column widths
- workbook serialization
- deterministic report filename sanitization

There is no ExportDefinition, ReportDefinition, metric/column registry, plugin framework,
database-backed template, schema DSL, or generic reporting engine. Each report owns its explicit
workbook mapping.

## Workbook structure

Student Profiling always produces one workbook with fourteen deterministic visible worksheets:

1. Summary
2. Sex
3. Age
4. Civil Status
5. Physical Disadv.
6. Religion
7. Mother Life
8. Father Life
9. Parent Family
10. City Municipality
11. Parent Income
12. Mother Occupation
13. Father Occupation
14. Living Condition

A valid report with zero submitted Inventories retains all fourteen worksheets. Summary still
contains context, coverage, methodology, and the empty-report message. Section sheets retain their
headers but intentionally suppress category rows in the zero-submission state. This avoids mixing
canonical scalar zero buckets with naturally empty sections while keeping the export structure
stable for office users.

## Summary semantics

Summary contains:

- Students' Profile
- Academic Year
- Campus
- College
- Program
- Year Level
- Generated At
- Submitted Inventory Count
- Inventory Coverage
- canonical profile-population methodology note
- canonical mode-specific coverage scope note
- ignored-filter clarification when applicable
- Program Legend / Program Columns

Generated At comes from the canonical report_context.generated_at value. Because XLSX date cells do
not preserve timezone offsets reliably, the timestamp is exported as ISO-8601 text with its
timezone offset instead of converting it to a naive Excel datetime.

CURRENT coverage exports Coverage Mode, Eligible Students, Submitted, Draft, and Without Individual
Inventory. Without Individual Inventory means MISSING only.

HISTORICAL_LIMITED exports Coverage Mode, Submitted, Draft, and an explicit statement that Without
Individual Inventory is unavailable from current COMPASS data. Historical eligible or missing
counts are not fabricated.

Methodology is deduplicated: profile_population_note once, inventory_coverage.scope_note once, and
one ignored-filter clarification when needed.

## Program columns and identity

Every section worksheet uses all dynamic Program columns horizontally. XLSX does not reuse the PDF
two-Program portrait chunking.

Program counts are resolved by canonical identity:

program_counts -> program_key -> count

and then matched against each ProgramColumn.key. Positional alignment is not trusted.

Concise Program codes are used as headers when available. Duplicate Program codes are
deterministically disambiguated with College/Campus context. Summary retains a Program Legend with
displayed label, Program code, Program name, College, Campus, and legacy indicator.

The canonical Not recorded / legacy Program column is retained when present.

If the required worksheet width would exceed Excel's real column limit, generation fails safely
with the stable workbook-unavailable boundary. Program columns are never silently truncated,
split, or PDF-chunked.

## Section values

Normal section sheets contain:

Category | dynamic Program columns | Total | Percentage (%)

Age uses the canonical exact observed age categories.

City Municipality contains:

City / Municipality | Province | Region | dynamic Program columns | Total | Percentage (%)

Province and Region are context from canonical geography metadata. The exporter does not parse
addresses, call PSGC APIs, or regroup locations independently.

Percentages are canonical report percentage values. They are written as numeric workbook values
with 0.00 formatting. No count/denominator recalculation occurs in the XLSX layer.

No Excel formulas are used for totals, percentages, age, income, coverage, category counts, or
other report math.

## Formula-injection and workbook safety

Every display/untrusted string is explicitly written as a text cell. Values beginning with formula
prefixes such as =, +, -, or @ therefore remain text rather than executable formulas.

Before serialization, the workbook is checked to reject:

- formula cells
- hyperlinks
- hidden worksheets

No macros, external workbook references, external data connections, or hidden raw-data sheets are
created.

## Privacy

The XLSX is aggregate-only. The mapper selects only canonical aggregate report fields. It does not
include Student UUIDs, student numbers, names, email, phone, full addresses, parent names,
occupation narratives, physical-disadvantage narratives, concerns/fears, counseling data, referral
data, respondent rows, or hidden source sheets.

Generated filenames are deterministic, Academic-Year based, sanitized, and contain no Student PII.

## Error boundary

Canonical report selection/filter errors remain outside the workbook-generation exception boundary
and preserve their existing 404 / 409 / 422 behavior.

Actual workbook construction or serialization failures map to:

- HTTP 503
- error code report_workbook_unavailable

Internal openpyxl/ZIP/XML/path details are not returned to clients.

## Persistence and audit boundary

The XLSX is generated on demand and returned as an HTTP attachment. No database model, migration,
MinIO object, export history, background job, Celery task, or cached generated workbook is added.

No download audit event is introduced because current repository policy does not require one for a
simple read-only aggregate representation.

## Existing PDF boundary

The Student Profiling PDF remains report-specific and keeps its portrait layout, page-number
behavior, Program chunking, coverage wording, and print semantics. Only the small filename
sanitizer is shared so PDF and XLSX filenames cannot drift.

No new PDF reports are introduced by this slice.

## OpenAPI contract

The XLSX endpoint is part of the normal generated OpenAPI surface. `contracts/openapi.json` is
produced by the repository export tooling / CI sync and is not maintained by hand.

## Consequences

Student Profiling now has:

- canonical JSON/in-app aggregate
- optional report-specific PDF/Print representation
- standard XLSX tabular export

Future analytical reports may reuse the low-level XLSX safety helpers while defining their own
explicit workbook mappings. XLSX does not imply PDF, and CSV remains explicitly unsupported by this
decision.
