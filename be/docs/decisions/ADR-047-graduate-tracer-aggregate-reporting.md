# ADR-047: Graduate Tracer Aggregate Reporting

- Status: Accepted
- Date: 2026-09-19
- Scope: backend-only aggregate reporting over submitted Graduate Tracer Survey schema-v1 data

## Context

COMPASS already stores the source-faithful CHED Graduate Tracer Survey in
`compass.graduate_tracer`. The authoritative lifecycle remains `DRAFT -> SUBMITTED`, and
`graduate_tracer.view` remains the authority for identifiable/raw response review.

This decision adds a separate restricted aggregate-report surface under `compass.reports`. It does
not redesign the Graduate Tracer questionnaire or persistence model.

## Authorization

Graduate Tracer aggregate JSON and XLSX use the existing effective capability:

`reports.view`.

No new report capability is introduced. The aggregate report does not require
`graduate_tracer.view`, because raw-response review and aggregate reporting are intentionally
separate authorities. Existing per-user capability override semantics remain authoritative.

## Canonical population

The report population is exactly:

- `GraduateTracerResponse.status = SUBMITTED`;
- `instrument_schema_version = 1`; and
- `submitted_at IS NOT NULL`.

Drafts are excluded.

A submitted Graduate Tracer response is historical graduate-outcome evidence. Later account
deactivation, Student lifecycle changes, current StudentAffiliation changes, counselor assignment,
Campus, College, or Program changes do not remove a submitted response from this report.

No report table, materialized view, warehouse, snapshot table, or Redis cache is introduced.

## Submission-period filtering

The only filters are optional inclusive local calendar dates:

- `submitted_from`; and
- `submitted_to`.

They filter `GraduateTracerResponse.submitted_at` in configured Django local time. They are
collection/submission-period filters, not graduation-cohort filters. A reversed range is invalid.

No answer-value filters, Program/College/Campus filters, or graduation-year filters are introduced.

## No academic cohort inference

Graduate Tracer schema v1 has no canonical historical UCN Program/College/Campus snapshot. Its
education rows are repeatable free text and do not identify which row is the authoritative UCN degree.

Therefore the report does not:

- parse degree strings;
- classify BSIS/BSIT or other programs heuristically;
- group institution names;
- pick first/latest/earliest education rows as graduation truth;
- use current StudentAffiliation as historical truth; or
- infer Campus, College, Program, or graduation cohort.

A future authoritative cohort/program model is required before those analytics can exist.

## No response-rate claim

COMPASS has no authoritative Graduate Tracer campaign or graduate-roster denominator.

The report returns `submitted_response_count`, which is the number of matching submitted responses
available in COMPASS. It does not calculate response rate, non-response rate, cohort coverage, or
claim that the submitted-response population represents all graduates.

## Aggregate sections and denominators

Every section exposes its own respondent denominator.

All submitted-response denominator:

- Sex
- Civil Status
- Region of Origin
- Residence Location
- Current Employment State

Not-employed plus never-employed denominator:

- Unemployment Reasons

Employed-only denominator:

- Present Employment Status
- Employer Business Line
- Place of Work
- First Job After College
- First Job Duration
- First Job Source
- Time to First Job
- First Job Level
- Current Job Level
- Initial Gross Monthly Earning
- Curriculum Relevance to First Job

Employed plus `first_job_after_college = true` denominator:

- Reasons for Staying on Current/First Job
- First Job Related to Course

Employed plus `curriculum_relevant_to_first_job = true` denominator:

- Useful Competencies

`NOT_RECORDED` is a report-only defensive category for applicable submitted data that unexpectedly
lacks a required controlled value. Reporting never mutates the source response.

## Multi-select semantics

Unemployment Reasons, Reasons for Staying, and Useful Competencies are multi-select sections.

Each respondent contributes at most once to each controlled option. The denominator is respondent
count, not total selections. Percentages are respondent-selection rates and may legitimately sum above
100 percent.

`OTHER` remains the source-controlled option where present. Associated free-text “other” fields are
never aggregated or exported.

## Source-enum fidelity

Controlled keys and labels come from the existing schema-v1 Graduate Tracer `TextChoices`. Reporting
does not duplicate, modernize, merge, or replace the survey categories.

`NOT_EMPLOYED` and `NEVER_EMPLOYED` remain distinct. Existing source-faithful duration buckets,
including `THREE_TO_LT_FOUR_YEARS`, remain unchanged.

Salary brackets are reported only as source categories. No midpoint salary, average salary, inferred
peso amount, inflation adjustment, employability score, ranking, or prediction is calculated.

## Free-text and identity exclusion

The aggregate report does not expose identity/contact data, addresses, birth dates, province free text,
education-row text, professional-exam text, training text, occupation text, “other” narratives, or
curriculum suggestions.

No NLP, keyword extraction, AI summarization, sentiment analysis, or automatic taxonomy
classification is performed.

The first aggregate report also defers structured fields whose reporting interpretation has not been
authoritatively defined, including undergraduate/graduate-study reasons, advanced-study reasons,
reasons for accepting the first job, and reasons for changing jobs.

## API representations

The report adds:

- `GET /api/v1/reports/graduate-tracer`; and
- `GET /api/v1/reports/graduate-tracer/xlsx`.

Both remain under the existing `reports` OpenAPI tag.

The JSON response has explicit report context, methodology, and typed aggregate sections.

The XLSX workbook contains aggregate data only with these compact sheets:

- `Summary`
- `Respondent Profile`
- `Employment`
- `First Job`
- `Reasons & Skills`

There is no raw-response worksheet, hidden raw-data sheet, Student UUID, name, contact data, or
free-text answer. Display text is explicitly written as string cells; counts and percentages are numeric
cells. No formulas, hyperlinks, macros, or external links are introduced.

## PDF deferral

No Graduate Tracer PDF is added. Unlike Student Profiling, there is no confirmed institutional
Graduate Tracer aggregate print-template requirement. PDF can be added only when an authoritative
requirement exists.

## Privacy release auditing

Graduate Tracer XLSX is a privacy-relevant release.

A successful release appends `report.export_released` with:

- `target_type = reports.graduatetracer`;
- `target_id = 1`;
- `report_type = graduate_tracer`;
- `format = XLSX`;
- `instrument_schema_version = 1`;
- optional ISO `submitted_from`; and
- optional ISO `submitted_to`.

Audit metadata does not store respondent count, category counts, percentages, employment outcomes,
Student IDs, salaries, or raw answers.

Release is fail closed: authorization and workbook generation happen before the required AuditEvent,
and workbook bytes are returned only after that audit succeeds. Audit failure returns
`release_audit_unavailable`.

## DPO Privacy Activity

The closed DPO report-release presenter recognizes `reports.graduatetracer` only when action, target,
schema version, XLSX format, and bounded submission-date metadata are valid.

The DPO projection may show schema version and submission-period scope. It does not project report
counts, survey outcomes, salaries, Student identity, report contents, or raw AuditEvent metadata.

Student Profiling and Good Moral release presentation remain unchanged.

## Persistence and migrations

This is read-only reporting over canonical Graduate Tracer truth. No Graduate Tracer persistence
change or migration is required.

If future reporting requirements need authoritative academic cohort/program semantics, those semantics
must be modeled explicitly rather than inferred from current account state or free-text education rows.

## Explicitly deferred

This ADR does not add CSM, Customer Feedback, Exit Interview, Appointment, Counseling, Referral, or
generic dashboard analytics. It does not add AI insights, trend prediction, employability scoring,
graduate ranking, response-rate calculations, PDF output, frontend dashboards, charts, pages, or a
generic configurable analytics framework.
