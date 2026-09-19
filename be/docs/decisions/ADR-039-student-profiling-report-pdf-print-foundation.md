# ADR-039: Student Profiling Report PDF / Print Foundation

- Status: Accepted
- Date: 2026-09-19
- Scope: printable/downloadable representation of the canonical Student Profiling aggregate

## Context

ADR-038 established build_student_profiling_report(...) as the single Student Profiling source of
truth. The historical Students' Profile — First Year Students — 2025-2026 (CCMS) is useful as a
formal portrait report reference, but it is not authoritative for arithmetic, terminology, scope,
geography, Program identity, coverage, or current institutional branding.

The historical report is A4 portrait and uses cross-tabular Category / Program / Total / Percentage
tables. Its two-Program CCMS layout cannot be treated as an institution-wide Program limit.

## Decision

Add one read-only PDF representation:

GET /api/v1/reports/student-profile/pdf

It accepts the same optional Academic Year, Campus, College, Program, and Year Level filter
arguments as the JSON Student Profiling endpoint and reuses the same reports.view authorization.
No recent-MFA requirement is added because this remains a read-only aggregate representation.

The PDF service calls build_student_profiling_report(...) exactly once. It consumes that internal
authoritative dictionary directly and never calls the JSON endpoint or round-trips through the
public Pydantic response schema. Decimal percentage values therefore remain on the canonical
builder-to-presentation path until display formatting.

There is no second Inventory query path, demographic calculation, percentage calculation, income
calculation, age derivation, coverage calculation, report table, generated-document model, MinIO
upload, cache, or materialized report.

## Document rendering

Register code-owned template:

- key: student_profiling_report
- version: 1
- layout family: REPORT
- accreditation footer: disabled
- page numbers: enabled
- template: documents/reports/student_profile.html

Rendering uses the existing render_document_pdf(...) Playwright pipeline, including packaged
assets, disabled JavaScript, blocked service workers, blocked remote HTTP/HTTPS resources, and
prefer_css_page_size=True.

The template uses an A4 portrait @page rule local to Student Profiling. Shared print.css is not
changed to landscape or otherwise given a profiling-specific global orientation. Certificates and
other document families retain their existing page behavior.

The report uses the current DocumentBrandingProfile. University of Camarines Norte is the primary
configured institutional identity. A configured former institution name may still appear through
the shared masthead; the Student Profiling template itself owns no hardcoded CNSC branding.

The report is not a QMS FormRevision and must not print F5 identity, an invented document number, or
an invented revision. F5 remains the source questionnaire.

## Portrait Program-column chunking

A4 portrait cannot safely fit an arbitrary institution-wide Program set in one cross-tab table.
Program columns are therefore chunked deterministically in the presentation layer. Version 1 uses
at most two concise Program columns per printed table, alongside Category, Total, and Percentage.

Chunk identity uses canonical ProgramColumn.key. Every distribution row converts its canonical
program_counts list into a program_key -> count lookup, and each displayed Program count is
resolved by key. Positional array alignment is not relied upon.

Chunking never changes row totals, percentages, population, or Program identity. Continuation
chunks repeat the section heading and Category / Total / Percentage columns. Long Program names are
represented by concise codes where available, with a report legend retaining identifying context.

## Coverage and methodology

Inventory Coverage stays separate from demographic tables.

For CURRENT coverage, print:

- Eligible Students
- Submitted
- Draft
- Without Individual Inventory, meaning MISSING only

For HISTORICAL_LIMITED, print Submitted and Draft where available, but never fabricate Eligible or
Missing values. Historical Without Individual Inventory is presented as unavailable from current
COMPASS data.

The canonical inventory_coverage.scope_note is always visible. If
inventory_coverage.ignored_filters is non-empty, the PDF visibly states which selected filters do
not apply to the coverage denominator. This is especially important for Program and Year Level,
which cannot classify Students with no submitted Inventory.

Methodology is deduplicated for print: render methodology.profile_population_note once,
inventory_coverage.scope_note once, and one ignored-filter clarification when needed. The PDF does
not dump overlapping generic/historical methodology fields as repeated paragraphs.

## Historical corrections preserved

The PDF presents the corrected ADR-038 result and must not reintroduce:

- First-Year/Freshmen-only scope
- Freshman/Sophomore/Junior/Senior terminology
- Gender in place of Sex
- overlapping historical age buckets
- Nort specified
- Province-as-Municipality rows
- hardcoded BSIT/BSIS columns
- copied historical totals or percentages
- truncated percentages
- Boarding House / Dormitory as an invented normalized category
- Without Individual Inventory inside demographic tables

No named Prepared by signatory is invented. The authenticated viewer is not automatically an
institutional report preparer.

## Privacy

The presentation model selects aggregate report fields only. It does not expose Student UUIDs,
student numbers, names, email, phone, complete addresses, parent names, occupation narratives,
physical-disadvantage narratives, concerns/fears, counseling data, or referral data.

Generated filenames are deterministic, Academic-Year based, sanitized, and contain no Student PII.

## Error behavior

Document rendering failures are wrapped in one report-domain document-unavailable condition and
mapped to:

- HTTP 503
- error code report_document_unavailable

Playwright details, stack traces, local paths, template internals, and filesystem details are not
returned to API clients. Existing canonical report filter errors retain their 404 / 409 / 422
mapping.

## Persistence and audit boundary

The PDF is generated on demand and returned as application/pdf with attachment disposition. No
generated-report persistence, object-storage upload, or new database migration is introduced.

No new download audit event is introduced because the repository has no established requirement for
a simple read-only aggregate report download event.

## Validation

The new PDF test module is explicitly enumerated by backend-targeted.yml. The minimum directly
relevant regression set includes:

- tests/test_student_profiling_reports.py
- tests/test_student_profiling_report_aggregates.py
- tests/test_student_profiling_report_coverage.py
- tests/test_student_profiling_pdf.py
- tests/test_documents.py
- tests/test_accounts.py
- tests/test_openapi_contract.py

Focused tests cover authorization, filter forwarding/error parity, valid PDF response behavior,
current branding, A4 portrait locality, Program-key chunking, current/historical coverage,
methodology deduplication, empty reports, privacy boundaries, correction regressions, deterministic
filename handling, one-call canonical-builder behavior, and real Chromium multi-chunk rendering.

The shared global print CSS remains portrait-neutral for other templates, and Good Moral certificate
template behavior is unchanged.

## Consequences

The Student Profiling PDF is a presentation of the already validated aggregate, not a reporting
pipeline of its own. Institution-wide Program growth is handled without changing the aggregate API,
and a printed report remains interpretable when separated from the web application.

CSV, Excel, charts, dashboards, scheduled reports, email delivery, frontend download controls, and
other analytics remain outside this slice.
