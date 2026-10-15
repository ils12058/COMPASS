# ADR-112: Graduate Tracer Graduation Classification and Filtering

- Status: Accepted
- Date: 2026-10-15
- Scope: Academic graduation classification and report filtering across the Graduate Tracer Survey, authorized roster, aggregate reports, and XLSX export
- Refines/supersedes: Narrowly supersedes the submission-period-only filtering constraint in ADR-047; preserves ADR-035 (Foundation), ADR-072 (Operational Retention and Disposition), and ADR-084 (Confidential-Content Encryption)

## Context

The Guidance and Counseling Office (GCO) requires the ability to organize and analyze submitted Graduate Tracer Survey (GTS) responses by academic graduation dimensions:

1. **College at Graduation**
2. **Program Graduated**
3. **Graduation Year**

Prior to this decision, ADR-047 strictly restricted Graduate Tracer reporting filters to local submission-period dates (`submitted_from` and `submitted_to`). COMPASS is a Guidance and Counseling Office Management System, not an alumni management platform; academic classification must serve institutional guidance analysis without creating generalized alumni-management or academic-history subsystems.

## Graduation Classification Model

Three user-facing academic classification fields are introduced directly on `compass.graduate_tracer.GraduateTracerResponse`:

- `graduated_college`: nullable foreign key to `compass.organization.College` (`on_delete=models.SET_NULL`).
- `graduated_program`: nullable foreign key to `compass.organization.Program` (`on_delete=models.SET_NULL`).
- `graduation_year`: nullable integer representing the calendar graduation year (bounded from 1900 through current institutional civil year).

### Data Requirements and Invariants

1. **Historical Records:** Existing records remain valid with NULL classifications. Existing submissions are never backfilled with invented or inferred academic classifications.
2. **Drafts:** In-progress drafts may be saved without these values.
3. **New Submissions:** Submitting a GTS response requires all three fields (`graduated_college`, `graduated_program`, `graduation_year`).
4. **Program-College Dependency:** The selected Program must authoritatively belong to the selected College (`program.college_id == college.id`). Contradictory pairs are rejected by server-side validation.
5. **Self-Reported Provenance:** These classifications represent self-reported graduation details. They are never derived or silently overwritten from `StudentAffiliation`, `IndividualInventory`, or free-text education rows.
6. **Submission Immutability:** Once submitted, a GTS response and its classification remain immutable under existing lifecycle rules (`DRAFT -> SUBMITTED`).

## Master Data Lookup Authorization

Organization master-data endpoints require administrative capability `organization.structure.view`. Ordinary Graduated Students must not receive this management permission merely to complete their graduation classification.

A dedicated, read-only endpoint is provided:

`GET /api/v1/graduate-tracer/classification-options`

Authorized for any active user with `graduate_tracer.submit` (Graduated Students) or `graduate_tracer.view` (Counselors/Coordinators). It returns only active colleges and programs (`{ colleges: [...], programs: [...] }`), exposing no administrative metadata or student records.

## Authorized Roster Filtering

The operational roster at `/portal/graduate-tracer` (`GET /api/v1/graduate-tracer/responses`) supports optional filtering by:

- `college_id`: UUID of College.
- `program_id`: UUID of Program (authoritatively resolved to its College).
- `graduation_year`: Calendar year integer.

Supported combinations include College-only, Program-only, Year-only, and any intersection thereof. Contradictory College and Program selections are rejected with HTTP 400. Records lacking classification ("Not recorded") remain visible in unfiltered queries. The roster displays concise classification metadata (`Program Code • Year` or `Not recorded`) without table bloat.

## Aggregate Report and XLSX Export

The aggregate reporting endpoints (`GET /api/v1/reports/graduate-tracer` and `GET /api/v1/reports/graduate-tracer/xlsx`) accept `college_id`, `program_id`, and `graduation_year` alongside `submitted_from` and `submitted_to`.

- **Denominator Fidelity:** All question-level distributions, conditional logic, and multi-select denominators are calculated strictly over the population matching the applied filters.
- **Methodology Transparency:** Report metadata clearly distinguishes the submission collection period from the graduation cohort year.
- **XLSX Workbook:** The Summary sheet includes explicit rows for College, Program, and Graduation Year ("All" when unfiltered). Download filenames incorporate the filter scope (e.g., `COMPASS-Graduate-Tracer-CCS-BSCS-2024.xlsx`) using sanitized alphanumeric slugs.

## Privacy and Small-Population Protection

To prevent deanonymization and attribute disclosure in small academic cohorts:

1. **Fail-Closed Disclosure Guard:** When any academic filter (`college_id`, `program_id`, or `graduation_year`) is applied and the matching submitted population is between 1 and 4 (`0 < matching < 5`), the aggregate JSON and XLSX endpoints reject the request with:
   - HTTP 403 Forbidden
   - Error code: `small_population_disclosure_restricted`
   - User copy: *"Aggregate reporting is restricted for this population to protect respondent confidentiality."*
2. **Zero-Match Boundary:** If exactly 0 responses match the filters, standard empty-state report generation proceeds (HTTP 200).
3. **Macro Report Preservation:** Unfiltered (institution-wide) reports with < 5 responses continue to return HTTP 200 with standard disclosure advisory warnings.
4. **Information Leakage Prevention:** Suppressed population counts are never revealed in error messages, filenames, or audit releases.

## Operational Anonymization Invariant

In compliance with ADR-072 and ADR-084:

When an identifiable submitted Graduate Tracer response reaches operational retention disposition and is anonymized:
- The quasi-identifiers `graduated_college`, `graduated_program`, and `graduation_year` are **dropped (set to NULL)** alongside student identity pointers.
- The CHED survey responses (`ANALYTICAL_FIELDS`) are preserved intact for institution-level historical research.
