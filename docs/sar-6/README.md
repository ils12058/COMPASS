# SAR-6 — Dedicated Student academic capabilities, Student self-view, and published placement precedence

**Status:** Implemented in the working tree; validation results recorded in
[`validation.md`](validation.md). Not committed, merged, pushed or deployed; left for explicit Git
authorization per the slice constraints.
**Branch:** `integration/ux15-modernization`.
**Base:** `a3b2d99b`.
**Date:** 2026-11-04.

## 1. Scope delivered

Three workstreams:

- **A — D-SAR-05 capabilities.** Added exactly three capabilities:
  `student_academics.view` and `student_academics.manage` (IT_ADMIN and the
  HEAD_GUIDANCE_COUNSELOR designation) and `student_academics.view_self` (STUDENT). Added the
  dependency `student_academics.manage` → `student_academics.view`. Regated the six staff academic
  endpoints, moved initial-placement provisioning authorization to `.manage`, hid every write
  control from view-only users, and pointed the deep command destination at `.view`.
- **B — D-SAR-16 Student self-view.** Extracted `_record_payload`, added
  `GET /api/v1/student-academics/me/record` (`studentAcademicsGetMyRecord`), and added the
  read-only `/portal/academic-record` page behind `MyAcademicRecordGate` with the Records-group
  navigation entry. A Student with no profile receives HTTP 200 with null/empty fields; there is
  no correction workflow.
- **C — D-SAR-19/20 published precedence.** Added the verbatim `PLACEMENT_PRECEDENCE_NOTE`, a new
  required `academic_alignment` block on `InventoryCoverage` computed in both coverage modes, PDF
  section 3.4 / template version 2, the XLSX alignment block, and regression tests proving
  placement precedes Inventory Program in operational lists, Good Moral preparation and
  College-scoped coverage. The existing five-count `reconciliation` block is unchanged.

No model or migration was added.

## 2. Explicit non-goals

Not changed by this slice:

- `docs/sar-0/decisions.md` statuses. D-SAR-05, D-SAR-16, D-SAR-19 and D-SAR-20 remain **Open**.
- Student academic write behavior: audit actions, metadata, `UNVERIFIED` default, Program-null
  rule, effective-date-null rule and the no-op set behavior are untouched.
- Coverage denominators, statuses, `scope_note` strings, applied/ignored filters and the
  `reconciliation` counts. The alignment block is informational only.
- Inventory ownership of Program/Year Level statistics; no Inventory write changed.
- Account creation without placement, CSV idempotency, the CSV classification matrix and the
  `program_code` rejection.
- Existing paths, the six staff operation IDs, error codes and messages other than the two
  capability-gate messages changed deliberately.
- Seeds, seed verification, `docs/sar-3-4/**` and every historical SAR document.
- Faculty or Counselor access to Student academic records; College-scoped academic permissions;
  a correction-request workflow.

## 3. Package map

| File | Contents |
|---|---|
| [`implementation.md`](implementation.md) | Per-file change table, exact capability grants, endpoint contract, alignment fields, PDF/XLSX rendering, frontend gates and the template v1/v2 note |
| [`decisions.md`](decisions.md) | Provisional defaults applied, §2.2/§2.3 verbatim, retirement of SAR-4's `organization.manage` reuse, and the decisions that stay open |
| [`validation.md`](validation.md) | Every validation command with real results, per-shard and per-engine totals, failures and fixes, and the explicit not-run list |

## 4. Relationship to earlier slices

`docs/sar-0/` through `docs/sar-5/` remain historical and were not rewritten. This slice consumes
D-SAR-05, D-SAR-16, D-SAR-19 and D-SAR-20 as **provisional engineering defaults**, not
institutional decisions. In particular, SAR-4's temporary reuse of `organization.manage` for
Student academic authorization is retired here; `docs/sar-3-4/` still records that temporary
state as history.
