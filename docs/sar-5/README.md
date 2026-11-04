# SAR-5 — Legacy retirement and end-to-end validation

**Status:** Implemented in the working tree; validation results recorded in
[`validation.md`](validation.md). Not committed, merged, pushed or deployed; left for explicit Git
authorization per the slice constraints.
**Branch:** `integration/ux15-modernization`.
**Base:** `c65b66a8`.
**Date:** 2026-11-04.

## 1. Scope delivered

Two workstreams:

- **A — Legacy residue retirement.** Removed the two deliberate SAR-2A Student "affiliation"
  naming residues from live backend code and report output:
  - the counselor-resolution reason code `NO_AFFILIATION` became `NO_PLACEMENT`;
  - the PDF coverage label `Applied — Student's current Guidance affiliation` became
    `Applied — Student's current academic placement`;
  - the methodology coverage note now says "current academic College placement" instead of
    "current Guidance College affiliation".
- **B — End-to-end validation.** Ran the evidence SAR-1 through SAR-4 explicitly skipped: static
  and contract checks, all six backend regression shards, frontend lint/typecheck/unit/build, the
  complete 84-suite browser inventory on chromium and webkit, the reset-only baseline seed, and
  the zero-reference checks. Results are recorded in [`validation.md`](validation.md).

No model, migration, capability, role, designation, endpoint or API field was added or changed.

## 2. Explicit non-goals

Not changed by this slice:

- Report semantics: coverage denominators, inclusion rules, applied/ignored filters,
  reconciliation counts, `HISTORICAL_COVERAGE_NOTE`, `PROFILE_METHODOLOGY` and XLSX/PDF table
  structure are untouched. Only two Student-affiliation strings changed.
- `FacultyAffiliation`, `faculty_affiliation` API fields, `ManagedFacultyAffiliation` and all
  Faculty wording. "Affiliation" remains correct for Faculty.
- Historical documents `docs/org-0/**`, `docs/sar-0/**` through `docs/sar-4/**` and
  `be/docs/decisions/ADR-*`.
- Any D-SAR-12..20 policy, including D-SAR-20 report reconciliation definitions.
- New UI, roster reconciliation, academic CSV updates or account-detail placement display. The
  changed report strings are backend-generated and rendered as returned.
- Test deletion or skipping to obtain a green result.

## 3. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Exact residue changes with before/after, affected tests, report-wording boundary and what remains intentionally historical |
| [`decisions.md`](decisions.md) | No institutional decision consumed; terminology-only change; open decisions |
| [`validation.md`](validation.md) | Every validation command with real results, per-shard and per-engine totals, failures and fixes, and the explicit not-run list |

## 4. Relationship to earlier slices

`docs/sar-0/` through `docs/sar-4/` remain historical and were not rewritten. SAR-2A recorded the
two naming residues as deliberate deferrals ("a later terminology slice can change them
deliberately rather than accidentally"). This slice performs exactly that change; it is the last
named SAR slice.

SAR-1 through SAR-4 skipped full-suite, full-browser and reset/seed evidence. This slice supplies
it against the same branch and records the results without claiming anything it did not run.
