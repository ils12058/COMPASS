# Decisions consumed by SAR-6

**Source register:** `docs/sar-0/decisions.md`, D-SAR-01 through D-SAR-20. All entries remain
recorded there as **Open**, with institutional owners; no status was edited.
**Status of this file:** SAR-6 applies **provisional engineering defaults** for four open
decisions. They reproduce today's effective access and are not institutional decisions.

## 1. Applied provisional choices

| Decision | Provisional choice | Where enforced |
|---|---|---|
| D-SAR-05 | Exactly three capabilities: `student_academics.view`, `student_academics.manage`, `student_academics.view_self`; institution-wide scope; no College-scoped permission; same MFA policy as today (writes require recent MFA, reads do not) | `be/compass/accounts/policy.py`; `be/compass/student_academics/api.py`; `be/compass/account_management/services.py` |
| D-SAR-16 | Student may read their own aggregate record (placement, periods, graduation) and nothing else; the page is read-only | `GET /api/v1/student-academics/me/record`; `fe/src/features/student-academics/my-academic-record/` |
| D-SAR-19 | Published rule: placement governs current College affiliation; the Inventory Program never infers it | `PLACEMENT_PRECEDENCE_NOTE` in `be/compass/reports/services.py`, reused verbatim in the API, PDF and XLSX |
| D-SAR-20 | Reconciliation is additive: the existing `reconciliation` block is byte-identical; a new informational `academic_alignment` block reports placement-vs-Inventory agreement | `be/compass/reports/schemas.py`; `be/compass/reports/services.py::_coverage`; PDF section 3.4; XLSX alignment block |

Grants reproduce today's effective access. IT_ADMIN and the HEAD_GUIDANCE_COUNSELOR designation
were the only holders of `organization.manage`; they receive `.view` and `.manage`. The STUDENT
role receives only `.view_self`. COUNSELOR, GUIDANCE_SERVICES_STAFF, FACULTY and
INSTITUTIONAL_OFFICER receive none.

## 2. D-SAR-16 — visibility only (slice §2.2, verbatim)

- A Student may read their own aggregate academic record: placement, periods and graduation.
- The view is read-only. There is **no correction-request workflow, no edit, no approval path**.
  D-SAR-14 (who approves corrections) and D-SAR-16's correction process remain open.
- The Student page states that placement is unverified and does not confirm enrollment, and tells
  the Student to contact the Registrar or Guidance office if the record is incorrect.
- No change to the staff Student Academic Records workspace beyond the new capability gates.

## 3. D-SAR-19/20 — published precedence and additive reconciliation (slice §2.3, verbatim)

Publish this rule verbatim as a single constant and reuse it in the API, PDF and XLSX:

```
PLACEMENT_PRECEDENCE_NOTE = (
    "Student College affiliation is taken from the Student's current academic placement. The "
    "Program recorded on an Individual Inventory describes what the Student reported on that "
    "form and is never used to infer current College affiliation. Differences are reported here "
    "and are not reconciled automatically."
)
```

- Placement governs routing, eligibility, operational Student lists, report scope and coverage
  filters. The Inventory `program` governs only Inventory profile statistics.
- Reconciliation is additive: the existing five-count `reconciliation` block and every existing
  denominator, formula, filter and status stay byte-identical. A new informational
  `academic_alignment` block exposes placement-vs-Inventory agreement counts. Nothing is
  auto-corrected, backfilled or reassigned.

## 4. SAR-4's temporary `organization.manage` reuse is retired

SAR-3/4 used `organization.manage` as a temporary gate for Student academic reads, writes and
initial-placement provisioning because no dedicated capability existed. This slice retires that
reuse on every Student academic surface:

- all six staff endpoints now require `student_academics.view` or `.manage`;
- initial placement in single-account creation and CSV import requires
  `student_academics.manage`;
- the frontend gates and the command-palette destination use the new helpers.

`docs/sar-3-4/` is not rewritten; it remains the historical record of the temporary state. No
other use of `organization.manage` changed.

## 5. Resolver behavior recorded as implemented

The slice text (A4.4) says a synthetic `.manage`-only grant "resolves `.view` through
`resolve_capability_dependencies`". The implemented resolver is fail-closed: it returns the
largest dependency-coherent subset, so a `.manage`-only set resolves to the empty set rather than
manufacturing `.view`. `be/tests/test_capability_dependencies.py` asserts the actual behavior:

- `resolve_capability_dependencies({"student_academics.manage"}) == frozenset()`;
- `resolve_capability_dependencies({"student_academics.manage", "student_academics.view"})`
  resolves both;
- a `.manage`-only `UserCapabilityOverride` is ineffective and grants neither capability.

The dependency itself is declared as required by the slice
(`required_capabilities("student_academics.manage") == {"student_academics.view"}`). This is a
documentation discrepancy in the slice text, not an access expansion.

## 6. What remains open

- `student_academics.verify` and `student_academics.import` (and `.reopen` / `.export`).
- College-scoped or Campus-scoped academic permissions; the `.view` / `.manage` scope stays
  institution-wide.
- Counselor, Guidance Services Staff, Faculty and Institutional Officer access to Student academic
  records.
- MFA policy for academic writes beyond "recent MFA as today".
- D-SAR-14 / D-SAR-16 correction-request, approval, dispute and notification workflows.
- Historical placement reconstruction; no historical placement data is inferred or backfilled.
- Inventory-vs-placement precedence for Inventory-owned statistics beyond the published rule.
- D-SAR-20 reconciliation approvals across reports, profiling and operational lists. The new
  alignment block is informational and does not settle denominators or cross-surface
  reconciliation.
