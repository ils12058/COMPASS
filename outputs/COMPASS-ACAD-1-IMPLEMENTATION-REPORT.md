# COMPASS-ACAD-1 — Implementation Report

**Repository:** `ils12058/COMPASS`
**Base:** `origin/staging` at `f63b8a11`
**Branch:** `codex/compass-acad-1`
**Pull request target:** `staging`

## Summary

The code-owned Organization Program catalog now states each canonical Program's academic
classification. Bachelor's Programs have configured 1st–4th Year options. Master's and Doctoral
Programs are classified independently of College, and their Year Level policy is explicitly
`PENDING_POLICY` with no invented range. Master in Information Technology is classified as
Master's under CCMS.

The Organization Program read API returns `academic_classification`,
`year_level_policy_status`, and `applicable_year_levels`. The existing Organization Structure page
shows that information without adding runtime catalog editing.

Individual Inventory now uses the selected Program's metadata for its Year Level options. The
backend rejects an out-of-range Year Level for a configured Bachelor's Program on draft changes and
submission. Changing Programs retains a Year Level only if it applies to the newly selected Program;
otherwise the frontend clears it for resolution. An unchanged previously saved value remains
editable, including when its Program has since become inactive. Existing submitted Inventories stay
immutable.

No database migration, new model, Program editing page, StudentAffiliation change, historical data
rewrite, deployment, or merge was made.

## Compatibility and historical records

The `StudentInventory.year_level` field, database check constraint, and API's stored numeric domain
remain 1–10. This preserves accepted records and the existing compatibility behavior for Programs
whose postgraduate policy is pending. For those Programs, COMPASS continues to allow the existing
recorded range; this is not an institutional 10-year limit. The UI states that the policy is
pending, and the backend applies no unconfirmed postgraduate maximum beyond the existing storage
domain.

Counselor roster and Student Profiling filters continue to cover values 1–10. Values 5–10 appear as
“recorded value” in filter choices, roster rows, Inventory read-only views, and report filter
labels. Report populations, denominators, filter semantics, authorization, and export schema stay
the same. Tests cover historical 5th- and 10th-Year filter results.

## Active-code audit of the former universal 1–10 assumption

| Area | ACAD-1 result |
| --- | --- |
| Organization catalog | `be/compass/organization/canonical.py` is source-owned and `sync_organization_catalog` projects it into the database. Program structure has no runtime CRUD. Classification is stored on exact canonical `(Campus, College, Program)` identities, not inferred from College or name prefix. |
| Inventory API and service | `InventoryPayload.year_level` and the storage domain retain 1–10 for compatibility. `inventory/services.py` applies the selected Program's configured range when the Year Level or Program changes, and again at submission. Historical unchanged drafts remain editable, including an inactive Program reference. |
| Database and annual records | The existing positive-small-integer validators and `inventory_year_level_range` check remain 1–10. No migration or `StudentAffiliation` change was introduced. Submitted Inventories remain immutable and annual snapshots stay attached to their original Program. |
| Inventory UI | New choices for a configured Bachelor's Program are 1st–4th Year. A saved out-of-policy value is surfaced for resolution; changing Program clears an incompatible selection. Pending postgraduate Programs state that policy is unconfirmed and keep compatibility behavior. |
| Counselor roster | Filter query validation retains 1–10 for recorded rows. Choices and displayed values above 4 are labelled “recorded value.” |
| Student Profiling and exports | Backend and frontend filters retain 1–10. Report filter labels for 5–10 say “recorded value”; report populations, denominators, authorization, export schema, and PDF/XLSX structure are unchanged. The report's existing Year Level label field now explicitly qualifies values above 4. The committed OpenAPI contract is regenerated for Program metadata. |
| Other active code | `privacy_governance/activity.py` retains its 1–10 metadata bound so existing activity projections remain valid; it does not offer enrollment choices. The active staging seed's 5th-Year example belongs to Good Moral, not Inventory. |
| Good Moral and historical tests | The separate F4 `CANONICAL_YEAR_LEVELS` list and current/assisted creation and correction paths remain unchanged for GM-UX-2. Issued records, snapshots, and PDF rendering behavior are untouched. `outputs/COMPASS-FORM-INPUT-1A-Implementation-Report.md` and older 1–10 fixtures are historical evidence, not active Inventory choices. |
| Archived frontend | `fe/AGENTS.md` marks archived frontend code as reference-only. The tracked `fe/` tree has no `archive`, `archived`, `legacy`, or `deprecated` directories; search hits for old assumptions were in active Good Moral paths, tests, and historical report/evidence files. No archived frontend code was imported, changed, or revived. |

The audit covered the Organization catalog, Inventory models/API/services, reporting services and
filters, Good Moral dependencies, frontend forms/roster/report filters, ADR-036, ADR-038, ADR-064,
ADR-109, and the prior FORM-INPUT-1A report. The exact source-owned classification is included in
the API contract; new metadata is not derived from encrypted/confidential Inventory content.

## Pending institutional policy

The remaining institutional-policy questions are:

1. For each Master's and Doctoral Program, what academic standing or Year Level choices are
   officially supported? Confirm whether each uses year levels or another standing model.
2. Until those rules are confirmed, is retaining the existing 1–10 storage compatibility domain for
   postgraduate submissions acceptable? This implementation does not describe 10 as an academic
   maximum.
3. Are there any canonical Program classification exceptions or Program-specific standing rules
   beyond the current Bachelor's, Master's, and Doctoral assignments?
4. For GM-UX-2, what authoritative evidence or verification process proves an undergraduate degree
   for F6 when account lifecycle is only `GRADUATED` and the submitted degree is free text?
5. For GM-UX-2 F4, should the Year Level match the linked submitted Inventory, and how should
   inactive or pending-classification Programs and pre-issuance corrections be handled?

No two-year Master's or three-year Doctoral defaults were added. Once policy is approved, its values
belong in the code-owned Program catalog and API metadata; no runtime catalog editor is needed.

## GM-UX-2 integration handoff

See [GM-UX-2 Academic Classification Integration Handoff](../docs/handoffs/GM-UX-2-ACADEMIC-CLASSIFICATION-INTEGRATION.md).
The handoff identifies the F4 self-service, assisted, and correction paths; their linked Inventory
source; the F6 self-service, assisted, and correction paths; the missing degree-proof source; and
the historical issuance/access boundary. Good Moral eligibility is not changed here.

## Validation

Focused validation completed:

- Backend focused classification/catalog/Inventory/report/OpenAPI selection: **18 passed, 80
  deselected**. This included exact classification, CCMS MIT and Graduate School Programs, the
  Bachelor's 1st–4th policy, no progression from a long collegiate education span, pending
  postgraduate compatibility, historical 5th/10th-Year report populations, report labels, and
  OpenAPI stability.
- Backend Inventory draft/submission follow-up: **3 passed, 14 deselected** for Bachelor's options
  and enforcement, pending postgraduate compatibility, submission rejection of a previously stored
  unsupported value, and inactive/unmodified draft compatibility. The existing student-self-service
  authorization test also passed when run sequentially (**1 passed, 16 deselected**).
- Frontend focused form/structure tests: **21 passed**. These cover the Bachelor's option list,
  explicit saved-value resolution, pending MIT compatibility messaging, Organization Structure
  classification display, and the Year Level control's accessible ID.
- Ruff checks and formatting checks passed for changed Python files. `pnpm typecheck` and `pnpm lint`
  passed.
- OpenAPI export check passed with no contract drift. `makemigrations --check --dry-run` reported
  **No changes detected**; Django emitted a local connection warning because the configured
  `compass_test` database is absent, so the migration-history consistency check could not connect.
- `git diff --check` passed. Full backend, browser, and PDF/XLSX render suites were not run.
