# SAR-6 implementation

## 1. Capability policy — `be/compass/accounts/policy.py`

Three `CapabilityDefinition` entries were added after the `student_session_summaries.*` block and
before `inventory.view_self`:

```python
CapabilityDefinition(
    code="student_academics.view",
    name="View Student academic records",
    description="View Student academic placement, periods and graduation records.",
),
CapabilityDefinition(
    code="student_academics.manage",
    name="Manage Student academic records",
    description=(
        "Set or clear Student academic placement and record academic periods and graduation."
    ),
),
CapabilityDefinition(
    code="student_academics.view_self",
    name="View own Student academic record",
    description="View the authenticated Student's own academic placement and record.",
),
```

Grants and dependency:

| Grant surface | Added |
|---|---|
| `ROLE_CAPABILITY_GRANTS["IT_ADMIN"]` | `student_academics.view`, `student_academics.manage` |
| `ROLE_CAPABILITY_GRANTS["STUDENT"]` | `student_academics.view_self` |
| `DESIGNATION_CAPABILITY_GRANTS["HEAD_GUIDANCE_COUNSELOR"]` | `student_academics.view`, `student_academics.manage` |
| `CAPABILITY_DEPENDENCIES` | `"student_academics.manage": frozenset({"student_academics.view"})` |

No other role or designation grant changed; `FACULTY_CAPABILITY_CEILING`, role compatibility and
existing dependencies are untouched. `CAPABILITY_CODES` is derived automatically and contains the
three new codes.

## 2. Staff API gates — `be/compass/student_academics/api.py`

| Operation ID | Endpoint | Gate |
|---|---|---|
| `studentAcademicsListPlacements` | `GET /placements` | `_require(request, "student_academics.view")` |
| `studentAcademicsGetStudentRecord` | `GET /students/{student_id}/record` | `_require(request, "student_academics.view")` |
| `studentAcademicsSetPlacement` | `PUT /students/{student_id}/placement` | `_require(request, "student_academics.manage", recent_mfa=True)` |
| `studentAcademicsClearPlacement` | `DELETE /students/{student_id}/placement` | `_require(request, "student_academics.manage", recent_mfa=True)` |
| `studentAcademicsRecordPeriod` | `PUT /students/{student_id}/periods` | `_require(request, "student_academics.manage", recent_mfa=True)` |
| `studentAcademicsRecordGraduation` | `PUT /students/{student_id}/graduation` | `_require(request, "student_academics.manage", recent_mfa=True)` |

Response shapes, `_raise` mappings, error codes, ordering and pagination are unchanged. A missing
capability raises the existing `_require` 403 `permission_denied` with
`"The <capability> capability is required."`.

## 3. Provisioning authorization — `be/compass/account_management/services.py`

`_assert_academic_placement_authorized` now checks the dedicated capability:

```python
def _assert_academic_placement_authorized(actor: User, *, requested: bool) -> None:
    if requested and not actor.has_capability("student_academics.manage"):
        raise AcademicPlacementNotAuthorized(
            "The student_academics.manage capability is required to assign an initial "
            "Student placement."
        )
```

The error class, HTTP 403 and API code `academic_placement_permission_denied` are unchanged, as
are the account create/import flows' `accounts.manage` + recent-MFA requirements, the CSV
classification matrix and the `program_code` rejection.

## 4. Student self-view — `be/compass/student_academics/api.py`

The inline record payload was extracted into `_record_payload(record)`, which builds
`student`, `lifecycle_status`, `placement`, `periods` and `graduation`. Both `student_record` and
the new endpoint use it; the staff response is byte-identical.

New operation, declared before the `students/{student_id}` routes:

```python
@router.get(
    "/me/record",
    response=response_with_errors(StudentAcademicRecordResponse, 401, 403),
    auth=session_auth,
    operation_id="studentAcademicsGetMyRecord",
)
def my_record(request):
    _require(request, "student_academics.view_self")
    if request.auth_user.role.code != "STUDENT":
        raise APIError(
            403,
            "permission_denied",
            "Academic record self-view is available only to Student accounts.",
        )
    try:
        record = get_student_academic_record(student_id=request.auth_user.pk)
    except StudentAcademicError as exc:
        _raise(exc)
    return _record_payload(record)
```

Behavior:

- A Student holding `.view_self` and having no `StudentAcademicProfile` row receives **HTTP 200**
  with `placement: null`, `periods: []`, `graduation: null` — not 404.
- A non-Student holding `.view_self` (synthetic override) receives 403 `permission_denied` with
  the message above.
- No MFA requirement; this is a read. No correction or write endpoint was added and
  `get_student_academic_record` was not changed.

## 5. Report schema — `be/compass/reports/schemas.py`

`AcademicAlignment(StrictSchema)` was added with `current_student_count`,
`current_with_placement_count`, `current_without_placement_count`,
`submitted_inventory_count`, `submitted_with_program_count`, `submitted_without_program_count`,
`placement_program_match_count`, `placement_program_mismatch_count` and `precedence_note`.
`InventoryCoverage` gains the required `academic_alignment: AcademicAlignment`; the existing
`reconciliation: PopulationReconciliation` is unchanged.

## 6. Precedence constant and computation — `be/compass/reports/services.py`

Exact constant (reused verbatim in the API response, PDF and XLSX):

```
PLACEMENT_PRECEDENCE_NOTE = (
    "Student College affiliation is taken from the Student's current academic placement. The "
    "Program recorded on an Individual Inventory describes what the Student reported on that "
    "form and is never used to infer current College affiliation. Differences are reported here "
    "and are not reconciled automatically."
)
```

`HISTORICAL_ALIGNMENT_NOTE` adds: `"Historical coverage counts Inventory records; today's
placement is not used to classify a historical Academic Year."`

`_coverage()` returns `academic_alignment` in both branches:

- **CURRENT:** current Student count from the existing `eligible_count`; placement presence from
  `StudentAcademicProfile.current_college_id` for exactly those eligible Students; submitted
  Inventory/Program-presence counts from the existing `inventory_queryset.filter(
  submitted_at__isnull=False)`; match/mismatch from the placement map versus
  `program__college_id`. The scope is never widened.
- **HISTORICAL_LIMITED:** the five placement-dependent counts are `None`; the three Program
  presence counts are computed from the same submitted Inventory IDs as before;
  `precedence_note` is still populated.

`CURRENT_COVERAGE_NOTE`, `HISTORICAL_COVERAGE_NOTE`, every coverage filter, status, denominator,
`profile_ids` and `_reconciliation()` are untouched.

## 7. PDF — `be/compass/reports/pdf.py` and the template

- `TEMPLATE_VERSION = 2`; `ALIGNMENT_TITLE = "Academic Placement and Inventory Alignment"`.
- `_alignment_table(coverage, mode)` fails closed: a missing or negative count raises
  `_unavailable(...)`, the Program presence counts must reconcile to the submitted Inventory
  count, and CURRENT placement/match counts must reconcile. `None` is accepted only for the five
  historical-unavailable fields.
- `_coverage_tables` adds the `alignment` table after the existing coverage/reconciliation
  tables. Rows and labels are identical to the schema block. CURRENT notes are
  `[PLACEMENT_PRECEDENCE_NOTE]`; HISTORICAL notes append `HISTORICAL_ALIGNMENT_NOTE`.
- `student_profile.html` inserts after section 3.3:

```html
<h3 class="sp-subsection">3.4 {{ student_profile.coverage.alignment.title }}</h3>
{% include "documents/reports/_student_profile_table.html" with table=student_profile.coverage.alignment show_heading=False %}
```

  The previous filters section is renumbered to 3.5.
- `template_specs.py` adds `("student_profiling_report", 2)` with the same template name, layout
  family, footer and page-number settings as version 1. **Both versions resolve to the same
  template file** because no environment retains version-1 PDFs; the product is not deployed and
  every database is rebuilt from `0001_canonical_baseline`.

## 8. XLSX — `be/compass/reports/xlsx.py`

`_alignment_rows(coverage)` returns the same eight labels, using the existing
`NOT_AVAILABLE_HISTORICAL` literal for `None`, with the same fail-closed validation. The block is
written after the reconciliation block and before "Program Legend", under the heading
"Academic Placement and Inventory Alignment", followed by `PLACEMENT_PRECEDENCE_NOTE` and, for
historical mode, `HISTORICAL_ALIGNMENT_NOTE`.

## 9. Frontend

| File | Change |
|---|---|
| `fe/src/features/student-academics/student-academics-access.ts` (new) | `canViewStudentAcademics`, `canManageStudentAcademics`, `canViewOwnAcademicRecord` capability helpers |
| `fe/src/features/organization/components/organization-gate.tsx` | `StudentAcademicRecordsGate` uses `canViewStudentAcademics`; new `MyAcademicRecordGate` uses `canViewOwnAcademicRecord` and renders `WorkspaceUnavailable` title "Academic record unavailable" |
| `fe/src/app/(portal)/portal/academic-record/page.tsx` (new) | Metadata title "Academic Record"; `MyAcademicRecordGate`; `Suspense` fallback `TableSkeleton` |
| `fe/src/features/student-academics/my-academic-record/my-academic-record-page.tsx` (new) | Read-only Student page: heading "Academic record" plus lifecycle badge and account status; placement panel "Academic placement" showing `"<Campus> · <College>"`, Verified/Unverified badge and the recorded-placement note; periods table (Academic year, Term, College, Year level, Enrollment status); graduation facts (Graduated college, Graduation date, Verification source, Verified by, Verified at); empty states "No academic placement recorded.", "No academic periods recorded.", "No graduation recorded."; always-visible "If this information is incorrect, contact the Registrar or Guidance office." |
| `fe/src/features/student-academics/student-academic-record/student-academic-record-page.tsx` | `canManageStudentAcademics(user)` hides Record period, row Update action, Record graduation, the Action column and the structure/years notices; reads stay visible |
| `fe/src/features/student-academics/student-academic-records/student-academic-records-page.tsx` | `canManageStudentAcademics(user)` hides Assign, Update placement, Clear placement and the Action column |
| `fe/src/features/portal/components/portal-workspaces.ts` | Records group gains `/portal/academic-record`, label "Academic Record", icon `GraduationCap`, after Individual Inventory; visible only through `canViewOwnAcademicRecord` |
| `fe/src/features/portal/components/portal-command-destinations.ts` | Student Academic Records deep destination uses `canViewStudentAcademics` |
| `fe/src/features/accounts/create/create-account.tsx` | `canAssignPlacement` checks `student_academics.manage` |
| `fe/src/features/accounts/components/account-action.tsx` | `academic_placement_permission_denied` copy names `student_academics.manage` |

## 10. Tests

Backend: `test_student_academic_records.py` (view/manage negative matrix, write-audit stability,
`organization.manage`-only denial, self-view 200/403), `test_account_csv_import.py` (dry-run and
commit denial plus rollback), `test_account_management.py` (single-create denial message),
`test_capability_dependencies.py` (grants, resolver, manage-only override),
`test_student_profiling_report_coverage.py` (alignment counts, unplaced Student, historical
`None`s, existing reconciliation untouched), `test_student_profiling_pdf.py` and
`test_student_profiling_xlsx.py` (section title, labels, match/mismatch, precedence note,
template version 2), `test_operational_students.py` and `test_good_moral.py` (placement College A
wins over Inventory Program College B), `test_openapi_contract.py` (frozen capability codes and
operation ID), `test_documents.py` (template provenance), and `test_accounts.py` (frozen grant
counts updated from 101 to 104 role grants and 20 to 22 designation grants; the
HEAD_GUIDANCE_COUNSELOR effective set gains the two new capabilities).

Frontend: `student-academic-record.test.mjs` (access-helper unit coverage),
`academic-record-self-view.browser.mjs` (four cases: populated read-only, empty states,
non-Student gate, zero write requests), `student-academic-record.browser.mjs` (view-only case),
`student-placement-provisioning.browser.mjs` (new capability message and fixture),
`portal-command-palette.test.mjs`, `organization-catalog.test.mjs`,
`support/catalog-fixtures.mjs`.

## 11. Contract and generated client

`contracts/openapi.json` was regenerated with the exporter, not hand-edited. The diff adds the
three `CapabilityCode` enum values (in every enum location), the
`studentAcademicsGetMyRecord` operation at `GET /api/v1/student-academics/me/record` with
200/401/403, the `AcademicAlignment` schema and the required
`InventoryCoverage.academic_alignment` property. Nothing else moved.
`fe/src/lib/api/generated/` was regenerated with `pnpm api:generate` (gitignored).

## 12. Files changed

| Area | File |
|---|---|
| Capabilities | `be/compass/accounts/policy.py` |
| API gates + self-view | `be/compass/student_academics/api.py` |
| Provisioning | `be/compass/account_management/services.py` |
| Report schema | `be/compass/reports/schemas.py` |
| Report computation | `be/compass/reports/services.py` |
| PDF | `be/compass/reports/pdf.py`, `be/compass/documents/templates/documents/reports/student_profile.html`, `be/compass/documents/template_specs.py` |
| XLSX | `be/compass/reports/xlsx.py` |
| Backend tests | `be/tests/test_student_academic_records.py`, `test_account_csv_import.py`, `test_account_management.py`, `test_capability_dependencies.py`, `test_student_profiling_report_coverage.py`, `test_student_profiling_pdf.py`, `test_student_profiling_xlsx.py`, `test_operational_students.py`, `test_good_moral.py`, `test_openapi_contract.py`, `test_accounts.py` |
| Contract | `contracts/openapi.json` (regenerated); `fe/src/lib/api/generated/**` (regenerated, gitignored) |
| Frontend gates/UI | `fe/src/features/student-academics/student-academics-access.ts`, `fe/src/features/organization/components/organization-gate.tsx`, `fe/src/app/(portal)/portal/academic-record/page.tsx`, `fe/src/features/student-academics/my-academic-record/my-academic-record-page.tsx`, `fe/src/features/student-academics/student-academic-record/student-academic-record-page.tsx`, `fe/src/features/student-academics/student-academic-records/student-academic-records-page.tsx`, `fe/src/features/portal/components/portal-workspaces.ts`, `fe/src/features/portal/components/portal-command-destinations.ts`, `fe/src/features/accounts/create/create-account.tsx`, `fe/src/features/accounts/components/account-action.tsx` |
| Frontend tests | `fe/tests/academic-record-self-view.browser.mjs` (new), `student-academic-record.browser.mjs`, `student-academic-record.test.mjs`, `student-placement-provisioning.browser.mjs`, `portal-command-palette.test.mjs`, `organization-catalog.test.mjs`, `support/catalog-fixtures.mjs`, `support/ux-hardening-fixtures.mjs` |
| Docs | `docs/sar-6/**` |

No model, migration, seed or unrelated behavior changed.
