# ADR-109: Student Profiling Reporting Accuracy and Table-First PDF

- Status: Accepted
- Date: 2026-10-11
- Scope: Student Profiling canonical report contract, PDF presentation, XLSX polish, and web
  wording. Graduate Tracer, Inventory capture, authorization, storage and audit are unchanged.
- Amends: [ADR-038](ADR-038-student-profiling-report-foundation.md),
  [ADR-039](ADR-039-student-profiling-report-pdf-print-foundation.md),
  [ADR-040](ADR-040-report-xlsx-export-and-student-profiling-foundation.md)

## Context

The Guidance and Counseling Office reference, *Students' Profile — First Year Students, 2025–2026
(CCMS)*, remains a structural and domain reference only. Its income totals, several percentages,
overlapping age groups, Province-as-Municipality row, repeated missing-Inventory categories and
manual pagination are not reproduced (ADR-038).

An audit of `build_student_profiling_report(...)` before this change found that the arithmetic was
already sound:

- Membership is the frozen set of submitted Inventories (ADR-051). `(student, academic_year)`,
  `(inventory, kind)` family and geography rows, and the one-to-one Student Support Profile are all
  unique, so no join can count an Inventory twice. Every one of the 13 sections is single-response:
  each Inventory lands in exactly one row, and missing child rows fall into *Not recorded /
  legacy*.
- Percentages use Decimal `ROUND_HALF_UP` to two places. A zero denominator returns `None`
  (printed and exported as N/A). ADR-038's "a zero denominator yields 0.00" sentence was stale and
  is superseded here.
- Age uses the institutional calendar date of `submitted_at` (ADR-097), never today.

The defects were in presentation and disclosure, not in counting:

1. The PDF split Program columns into two-Program chunks and repeated the institution-wide Total
   and Percentage beside each partial chunk, under "(continued)" headings. A reader could take a
   partial table's Total as the sum of the Programs beside it.
2. The access-scope sentence was appended to both the population note and the coverage note, so
   the PDF and the XLSX Summary printed it twice.
3. The two populations were described in prose only. A Student currently affiliated with one
   College whose submitted Inventory records another College's Program is counted as Submitted in
   coverage but not in that College's profile, and nothing showed this.
4. The PDF printed "Generated" in the runtime timezone instead of institutional time.
5. The web methodology panel showed the current-year coverage note on historical reports.

## Decision

### Two named populations

Reports name the populations explicitly and never treat them as interchangeable:

- **Submitted Inventory Profile Population** — submitted Individual Inventories for the selected
  Academic Year. Campus, College, Program and Year Level use the Program and Year Level recorded on
  each Inventory. This is the denominator of every distribution.
- **Current Student Inventory Coverage** — active Student accounts with a Current lifecycle status,
  scoped by current Guidance College affiliation, and their Submitted / Draft / no-Inventory state
  for the current Academic Year. Program and Year Level never classify Students without an
  Inventory.

`HISTORICAL_LIMITED` coverage is unchanged: existing submitted and draft Inventories within the
reporting scope, with no eligible or missing count, because there is no historical roster.
Today's Current Students are never a historical denominator. Historical coverage keeps ignoring the
Campus and College filters, as before. The report discloses this instead of changing the policy.

No submission rate is calculated from the two populations.

### Exact population reconciliation

`inventory_coverage.reconciliation` is new. It compares the two populations by the identity each
one actually counts, so every number comes from set arithmetic:

| Field | Meaning |
| --- | --- |
| `profile_submitted_count` | Inventories in the profile population |
| `coverage_submitted_count` | Coverage Submitted count (Students for CURRENT, Inventories for historical) |
| `in_both_count` | counted in both |
| `profile_only_count` | profile Inventories whose Student is not counted as Submitted in coverage (no longer Current, inactive, or affiliated outside the coverage scope) |
| `coverage_only_count` | coverage Submitted whose Inventory is outside the profile filters (other recorded Program, College, Campus or Year Level, or no Program) |

The invariants are `in_both + profile_only = profile_submitted` and
`in_both + coverage_only = coverage_submitted`. Reconciliation counts are released aggregate values
and feed the existing disclosure advisory. No enrollment roster or historical affiliation snapshot is
invented.

### Additional canonical fields

- `program_columns[].submitted_inventory_count` — the canonical Program population, so
  presentations verify Program columns instead of re-deriving totals.
- `report_context.reporting_scope` — the same `{is_global, colleges}` projection as
  `GET /api/v1/reports/scope`, for metadata that separates selected filters from effective scope.
- `methodology.access_scope_note` — the scope sentence, stated once. `profile_population_note`
  no longer repeats it. `inventory_coverage.scope_note` keeps its complete standalone wording for
  API consumers.

Existing endpoints, filters, authorization, filenames and release auditing are unchanged. The
additions are new required response fields in the generated contract.

### Parent annual income

`compass.inventory.services.PARENT_INCOME_BRACKETS` is now the single ordered threshold table, and
`classify_parent_annual_income` iterates it. The thresholds and boundary behavior are unchanged
and remain covered by the existing boundary tests. Reports print the bracket legend through
`parent_income_bracket_legend()`, which reads that table, so the report module states no threshold.
The legend says the brackets follow the existing Guidance and Counseling Office profiling reference.
It makes no claim that they are current national poverty thresholds; any future revision of them is
a separate institutional policy decision.

### Table-first PDF (template `student_profiling_report` v1, A4 portrait)

1. **Report Overview** — Academic Year (current/historical), the Campus, College, Program and Year
   Level *filters*, Reporting Scope (institution-wide or the assigned Colleges), profile population
   n, and Generated At in institutional time.
2. **Populations in This Report** — definitions of both populations, the profile population by
   College, the coverage table (CURRENT: Submitted + Draft + Without = Eligible; historical: "Not
   available — no historical eligibility roster"), the reconciliation table, and a filter-application
   table showing how each selected filter applies to each population.
3. **Methodology and Data Notes** — one concise statement each for population, coverage,
   denominators and rounding, age, Not specified vs legacy, residence, Program breakdown and
   confidentiality. Empty reports print only the statements that apply.
4–6. **Demographics, Family and Household, Geographic Distribution** — Tables 1–13. Each shows
   Category | Frequency | Percentage with its denominator ("Population: submitted Individual
   Inventories (n = N)") and a Total row of N and 100.00%. Every controlled response category is
   printed, including zeros. *Not recorded / legacy* is not a response option and is printed only
   when it occurs. Geography adds Province and Region context columns. The income bracket legend
   follows the income table.

**Appendix A. Program Breakdown** replaces the two-Program chunks:

- Table A lists every Program with its College, n and share, with College subtotals and an
  Unclassified / Legacy row reconciling to N.
- Each College is one group, and each group after the first starts on a new page. Its tables use
  the College's own submitted Inventories as denominator. No institution-wide total appears beside
  a partial College table.
- A College with 1–5 Programs prints a cross-tab: Category | each Program | College Total |
  % of College, with a Total row of Program n's, the College n and 100.00%. A single-Program College
  omits the redundant College Total column.
- A College with more than `MAX_CROSS_TAB_PROGRAMS` (5) Programs prints, per section, a College
  total table plus a long-form table: Program | Category | Frequency | Program n | % of Program.
  Each Program's rows and its Total row form one unbreakable block.
- Inventories without a recorded Program form an *Unclassified / Legacy* group. They are never
  attributed to a College.
- Categories with no responses in a group are omitted from that group's tables, with a note.
- A single-Program report omits the appendix, because Sections 4–6 already are its breakdown.
- Programs are matched by canonical Program key, never by array position. Inactive historical
  Programs keep their identity.

Before printing, the presentation verifies that every row's Program counts sum to the row total,
rows sum to N, each Program column sums to its canonical Program population, every percentage
equals `calculate_percentage(count, N)`, coverage states sum to Eligible, and the reconciliation
holds. Any failure raises the existing `report_document_unavailable` boundary. A PDF whose numbers
disagree is never produced. College subtotals and College or Program percentages are sums of
canonical counts with percentages from the same `calculate_percentage`.

Pagination: headings and table captions avoid page breaks after them; tables of up to 18 rows are
kept on one page; longer tables break only between rows (or Program blocks) and repeat their
column headers. No "(continued)" text is printed. The masthead appears once and the recognition
strip on every page. The page footer reads "Student Profile Report · Academic Year … · Generated …"
with "Page X of Y" (`document_pdf_footer_label`, a small optional extension of the shared footer
template). No signatory, certification, approving official or QMS form identity is printed.

### XLSX

The fourteen-sheet structure, full horizontal Program columns, formula and hyperlink safety,
filenames and the zero-submission header-only sheets are preserved. Targeted polish:

- Summary prints the reporting scope once, uses the population names, adds the reconciliation, and
  gives long merged notes explicit row heights. Its Program legend adds Submitted Inventories (n).
- Every category sheet ends with a "Total (profile population)" row, outside the auto-filter
  range, giving each Program's n, N and 100.00, followed by a denominator note.
- The Parent Income sheet carries the same bracket legend as the PDF.
- Generated At stays ISO-8601 text with its offset, now expressed in institutional time (the same
  instant, matching the PDF).

### PDF and XLSX parity

The two formats differ in layout only. Built from one frozen canonical report, they show identical
overall counts and percentages, identical Program counts, and College subtotals equal to the sum of
the XLSX Program columns. The only rows the PDF leaves out are zero-count *Not recorded / legacy*
rows and, in appendix groups, zero-count categories. `tests/test_student_profiling_xlsx.py`
asserts this parity against a database-built report.

### Disclosure

The advisory policy is unchanged (`reports/policy.py`): one general warning when the population or
any released count, including reconciliation counts, is between 1 and 4. Exact values are never
suppressed, and the PDF now says so beside the warning. The methodology states that aggregate
tables are not guaranteed to be anonymous and that narrow filters or comparing reports generated
with different filters (differencing) can reveal individuals.

Cell suppression is not introduced. A sound policy would need institutional approval and
complementary suppression across totals, College subtotals, Program columns, the reconciliation,
and the XLSX. Hiding one cell while its totals remain would not protect it. No row-level or
identifiable data is added to any format.

## Consequences

- The printed report states what was counted, how each total was obtained, and how the two
  populations relate.
- Appendix length grows with the number of Colleges and Programs. That is the cost of
  self-contained College tables, and it replaces misleading chunks.
- The generated contract gains required fields. The web report shows the reporting scope, the
  population names, the reconciliation, Program n, and the mode-appropriate coverage note. It does
  not recalculate any total.
