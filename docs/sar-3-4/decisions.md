# Decisions consumed by SAR-3 + SAR-4

**Source register:** `docs/sar-0/decisions.md`, D-SAR-01 through D-SAR-20. All entries remain
recorded there as **Open**, with institutional owners.
**Status of this file:** this slice applies the task's locked choices and one **provisional
engineering default** for D-SAR-15. They are not UCN, GCO, Registrar, DPO, Records or IT approvals.
The implementation was merged into `integration/ux15-modernization` and pushed to `origin` without
a PR; it was not deployed or run against a shared environment.

## 1. Applied choices

| ID | Applied choice | Where enforced |
|---|---|---|
| D-SAR-01 | **College-only.** No Program reader, writer, API field, CSV column or Inventory copy. `program_code` remains an unsupported CSV header. | Reads facts carry only College; writer never sets Program; CSV header set; frontend copy |
| D-SAR-02 | Placement is `UNVERIFIED` only. Provisioning never verifies. | `set_current_placement`; create-account and CSV UI copy |
| D-SAR-04 | `placement_effective_at` stays null. | Writer remains unchanged on effective date |
| D-SAR-05 | **Reuse `organization.manage`.** No new capability. Account creation and CSV already require `accounts.manage` + recent MFA. | `_assert_academic_placement_authorized`; API error mapping |
| D-SAR-06/07 | Clearing keeps the profile row. Provisioning never deletes. | Writer unchanged; no delete path added |
| D-SAR-08 | `compass.student_academics.services` remains the only writer. | Only the provisioning flows call the service; no direct writes added |
| D-SAR-15 | **Provisional default:** initial placement is optional. Omitting it creates no `StudentAcademicProfile` row. | `validate_initial_student_placement`, `resolve_csv_student_placement`, create and CSV flows |
| D-SAR-19/20 | Untouched. No Inventory-vs-placement precedence or report reconciliation change. | No consumer, report or Inventory change |

## 2. D-SAR-15 — provisional default, not an institutional decision

The task fixes the engineering behavior needed to ship provisioning without waiting for a mandatory
or optional academic-field decision:

- An account may be created with no Student placement at all. No profile row is created.
- A placement may be supplied only as a Campus + College pair.
- Supplying a placement records it as `UNVERIFIED`; it never confirms enrollment and never changes
  the Student lifecycle.
- The Student Academic Records workspace remains the place to inspect and change placement later.

This is a provisional default. It does not settle whether future provisioning must collect an
academic placement, whether the institution will require a College, or what verification workflow
will replace `UNVERIFIED`.

## 3. `organization.manage` reuse — D-SAR-05 remains open

Assigning an initial placement is an academic write performed from an account-provisioning screen.
No `student_academics.*` capability, role grant or designation grant was introduced. The capability
used is the existing `organization.manage`, consistent with SAR-2A.

Consequences:

- A user may hold `accounts.manage` and create accounts without placement.
- A user may hold `accounts.manage` but not `organization.manage`; the UI hides the placement
  section and the API rejects any supplied placement with
  `academic_placement_permission_denied` (HTTP 403).
- D-SAR-05 remains open. A later dedicated authorization model must revisit the read/write split,
  MFA policy, scope and grants.

## 4. `faculty-colleges` naming residue

The choices endpoint keeps its path `/api/v1/accounts/faculty-colleges` and its operation ID
`accountsFacultyCollegeChoices` so generated clients and existing callers do not break. The summary
now reads "List active catalog Colleges for account provisioning", and the same response is reused
for Student placement choices. The path name remains a documented naming residue, not a statement
that only Faculty may use it.

## 5. `program_code` rejection

`program_code` is not in `REQUIRED_HEADERS` or `OPTIONAL_HEADERS`. An import that supplies it is
rejected as an unsupported header before any row is classified or committed. No code path reads it.
The frontend names it only to tell operators that it is not supported.

## 6. D-SAR-05 and D-SAR-19/20 remain open

- **D-SAR-05** — dedicated Student academic capabilities and the final read/write authorization
  split are not decided.
- **D-SAR-19** — Inventory Program College vs placement College precedence is untouched.
- **D-SAR-20** — reconciliation definitions for reports, profiling and operational Student lists are
  untouched.

No other deferred decision is consumed by this slice.
