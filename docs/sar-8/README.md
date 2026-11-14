# SAR-8: Batch import of term records and graduations

**Status:** draft PR into `staging`. Not merged or deployed.
**Base:** `501aa47d` (`staging` after #372).
**Date:** 2026-11-14.
**Decision:** the owner approved the academic batch import proposal on 14 November 2026, with defaults D1–D6 accepted. It goes before passkeys.

## 1. Why

The Guidance Office asked whether academic information can be updated in a batch. Only current College placement could be: through the SAR-7 roster import and the account import. Term records (year level and enrollment per academic year and term) and graduation records had to be entered one Student at a time.

## 2. Scope delivered

### Backend

**`be/compass/student_academics/batch_import.py`** provides two imports. Both follow SAR-7:
- one UTF-8 CSV, up to 1 MiB and 1,000 non-empty rows;
- a dry-run preview;
- an all-or-nothing apply.

**Term records** (`import_student_academic_periods`):
- Covers one academic year and term, chosen on the screen (D1).
- Columns: `institutional_id`, `campus_code`, `college_code`, and optionally `year_level` (1–8 or blank) and `enrollment_status` (`ENROLLED`, `NOT_ENROLLED`, `UNKNOWN`, or blank for `UNKNOWN`).
- Each row is classified as `CREATE`, `UPDATE`, `NOOP`, `CONFLICT` or `INVALID`.
- Writes go through `record_academic_period`.
- Current placement is never changed (D2).

**Graduations** (`import_student_graduations`):
- Columns: `institutional_id`, `campus_code`, `college_code`, `graduation_date` (`YYYY-MM-DD` only, D3).
- One verification source is entered for the whole file, up to 200 characters.
- Each row is classified as `GRADUATE`, `UPDATE`, `NOOP`, `CONFLICT` or `INVALID`.
- The report states `write_count` and `placement_cleared_count`.
- Writes go through `record_graduation`, so lifecycle, placement clearing and per-record audit match the single-record form.

**Shared rules:**
- Single-record parity: inactive Student accounts are allowed, and the account must have the STUDENT role.
- Campus and College must both be active.
- A repeated `institutional_id` is an invalid row.

**Stale-preview protection:**
- The preview returns `preview_fingerprint`, a SHA-256 over every row's action, target and current state, plus the year and term or the verification source.
- Apply requires it, re-classifies under row locks, and refuses with `409 csv_import_stale` if anything changed.

**Typed confirmation:**
- Graduation apply also requires `confirmed_count` equal to `write_count`. Otherwise it returns `422 csv_import_confirmation_mismatch`.
- There is no batch undo (D4).

**Endpoints:**
- `POST /api/v1/student-academics/imports/periods/csv` (`studentAcademicsImportPeriodsCsv`).
- `POST /api/v1/student-academics/imports/graduations/csv` (`studentAcademicsImportGraduationsCsv`).
- Both are multipart, with `dry_run` defaulting to `true`.
- Both require `student_academics.import` with recent MFA, so only IT Admin and the Head can use them (D5). No new capability.
- Errors reuse the SAR-7 codes, plus `csv_import_preview_required`, `csv_import_stale` and `csv_import_confirmation_mismatch`.

**Audit:**
- New actions `student_academics.periods.imported` and `student_academics.graduations.imported`. Each records one summary per apply that writes, with counts only.
- The existing per-record events are unchanged.
- Uploaded files are not stored.

**Contract:** `contracts/openapi.json` was regenerated, and both operation IDs are registered in `test_openapi_contract.py`.

**CI:** `test_student_academic_batch_import.py` was added to the `student-academics` bundle.

### Frontend

**Routes:**
- `/portal/organization/student-academics/import/terms`
- `/portal/organization/student-academics/import/graduations`
- Both use the existing import gate.
- **Academic import navigation** tabs (College placement · Term records · Graduations) join all three imports, including the existing roster page.

**Term records screen:**
- Academic year (the current year is preselected) and term.
- CSV template, College code reference, preview with "Now" and "From CSV" facts, and a confirmation dialog.

**Graduations screen:**
- The verification source is required before validating.
- The preview states the consequences, for example "N Students will become Graduated; N will leave their current College placement".
- A danger-styled import whose dialog needs the exact count typed.

**Shared behaviour:**
- Changing the file, year, term or source drops the preview, so apply always matches what was shown.
- A stale or conflicting apply asks for a new preview.

**Command menu:** destinations for both imports.

## 3. Verification

| Check | Result |
|---|---|
| `test_student_academic_batch_import.py` | 9 passed |
| `student-academics` bundle + `test_openapi_contract.py` | 128 passed (after registering the two operation IDs) |
| `test_audit.py`, `test_activity.py`, `test_activity_retrieval.py` | 120 passed |
| `export_openapi --check`, `ruff check`, `ruff format --check`, `backend_ci.py verify` | clean |
| Frontend `typecheck`, `lint` (0 errors), `pnpm test` | 1,322 / 1,322 |
| `student-academic-batch-import.browser.mjs` (new) | 7/7 Chromium, 7/7 WebKit |
| `student-academic-roster-import.browser.mjs` | 6/6 Chromium, 6/6 WebKit |

CI on the pull request is the full run.

## 4. Not included

- Reverse graduation (D4). A mistake is corrected through the single-record form.
- Program or section per Student.
- Importing directly from a Registrar system.
- Any change to who may edit academic information.
