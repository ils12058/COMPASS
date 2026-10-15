# FORM-INPUT-1A — Good Moral Year Level & Semester Standardization

## 1. Baseline and Context

- **Repository:** `ils12058/COMPASS`; target: `staging`.
- **Baseline commit SHA:** `fea0f3c483d5fade22457efba6b73aed8d1893ce`.
- **Merged PRs verified on staging:**
  - PR #232 (`180759f0b79b8a3d2b418ad0fd38101196f18942`): FORM-ID-1 (UCN Controlled Form Cutover).
  - PR #233 (`b7f365b5828ab5db8fc541d90321558a5183f7f2`): FORM-INPUT-1C (Input validation hardening).
  - PR #234 (`c39d91f868ad931a196155986423528b7e2c0e86`): FORM-UI-1A (Call Slip permission-aware lifecycle actions).
  - PR #235 (`fea0f3c483d5fade22457efba6b73aed8d1893ce`): FORM-UI-1B (Call Slip guidance notice).
- **Source Audits:** FORM-INPUT-0 and FORM-FIDELITY-0 (discrepancy findings on uncontrolled Year Level and Semester inputs for UCN-OP-GCO-01F4).
- **Scope Boundary:** Applies strictly to Undergraduate / Current Student Good Moral Character certificate requests (`UCN-OP-GCO-01F4`). The Graduate variant (`UCN-OP-GCO-01F6`) remains strictly unchanged.

---

## 2. Controlled Implementation Scope

### A. Year Level Control
- **Choices (10 options):** `1st Year`, `2nd Year`, `3rd Year`, `4th Year`, `5th Year`, `6th Year`, `7th Year`, `8th Year`, `9th Year`, `10th Year`.
- Follows the existing Individual Inventory numeric Year Level domain (1–10) with standard ordinal formatting.
- Select element defaults to an empty unselected state (`Select your Year Level`) to prevent accidental submissions.
- Free-text fallback is completely removed for new student requests.

### B. Semester Control
- **Choices (exactly 2 options):** `First Semester`, `Second Semester`.
- Excludes: `Summer`, `Midyear`, `Summer/Midyear`, `Third Semester`, or custom free text, matching the fixed certificate wording of approved form F4.
- Select element defaults to an empty unselected state (`Select your Semester`).

### C. Evaluation of Inventory Preselection
- Inventory preselection was evaluated against Condition 7 ("No unnecessary confidential payload retrieval may be introduced merely to populate the dropdown").
- Current Student status endpoint `/api/v1/good-moral/me/status` indicates only whether a valid submitted inventory exists; it does not contain the `year_level` field.
- Accessing the numeric year level would require retrieving and decrypting the student's full confidential Individual Inventory record (`/api/v1/inventory/me/current` containing family background, health, finances, and sensitive personal histories).
- In accordance with Condition 7, frontend inventory preselection was intentionally omitted to prevent unnecessary transmission and decryption of sensitive confidential data. The backend already strictly enforces inventory prerequisites upon submission.

---

## 3. Preservation of Text-Based Persistence

- **Data schema intact:** `year_level_snapshot` remains `CharField(max_length=64)` and `semester_snapshot` remains `CharField(max_length=80)`.
- **No DB migration:** No schema changes, no database enum columns, no numeric IDs, and no FormRevision registry alterations were made.
- **Canonical strings stored:** The exact visible text values are persisted:
  - Year Level: `"1st Year"`, `"2nd Year"`, ..., `"10th Year"`.
  - Semester: `"First Semester"`, `"Second Semester"`.
- **Zero silent mutation:** Historical records are not migrated or backfilled; existing text values are preserved as-is.

---

## 4. Staff and Counselor Operational Correction Workflow

- **Shared selection choices:** Authorized Guidance Counselors and Guidance Services Staff use the same canonical choices when correcting F4 records before issuance.
- **Handling of canonical records:** When editing a canonical record, the dropdown selects the stored value and allows selecting another valid choice.
- **Handling of legacy records:**
  - Historical non-canonical values (e.g. `"Fourth"`, `"1st"`, `"Second Sem"`) are rendered in the dropdown as `{item.year_level} (Current value as entered)` or `{item.semester} (Current value as entered)`.
  - An informational notice is displayed: `"This record contains a historical value that is no longer offered for new requests. It will be preserved as-is unless you choose a replacement above."`
  - Untouched legacy values are retained and preserved verbatim on unrelated corrections.
  - Authorized personnel can intentionally choose a canonical replacement value.
- **Immutability of issued and cancelled records:** Requests in `ISSUED` or `CANCELLED` status remain strictly locked against modification.

---

## 5. Backend Validation & Idempotency Safety

- **Canonical constants:** Defined in `be/compass/good_moral/models.py`:
  - `CANONICAL_YEAR_LEVELS`: 10 ordinal strings (`"1st Year"` through `"10th Year"`).
  - `CANONICAL_SEMESTERS`: `"First Semester"` and `"Second Semester"`.
- **Creation validation:** In `create_my_current_student`, new F4 submissions with non-canonical Year Level or Semester raise `InvalidGoodMoralInput` (HTTP 422 `invalid_good_moral_request`).
- **Idempotency replay preservation:** Validation is placed *after* the idempotency lock check (`_existing_creation_locked`). If a previously accepted request created prior to this standardization is retried with its original `Idempotency-Key`, it resolves idempotently without validation failure.
- **Correction validation:** In `update_request`, validation is only enforced when `year_level_snapshot` or `semester_snapshot` is explicitly in `changed`. Historical snapshots remain valid and untouched during edits of unrelated fields.

---

## 6. Official Certificate PDF Rendering

- Validated with official PDF generation in `documents/templates/documents/good_moral/ucn_current_student.html` and `compass/documents/templates.py`:
  - Template helper `_certificate_fragment` strips trailing `\s+year$` and `\s+semester$` before embedding into the certificate phrasing:
    `"a <year_level> student"` and `"during the <semester> semester of Academic Year"`.
  - With canonical inputs (`"1st Year"`, `"4th Year"`, `"First Semester"`), rendering outputs clean natural text:
    `"a 1st year student"` and `"during the First semester of Academic Year"`.
  - Tested against 7 rendering scenarios:
    1. Canonical 1st Year + First Semester
    2. Canonical 4th Year + Second Semester
    3. Canonical 10th Year boundary
    4. Historical Year Level with trailing "Year"
    5. Historical Semester with trailing "Semester"
    6. Legacy CNSC renderer version 1
    7. Current UCN F4 renderer version 2
  - **No duplicate word repetitions:** Eliminates potential stuttering such as `"year year"` or `"semester semester"`.

---

## 7. Graduate Request (F6) Non-Regression

- Student Graduate request form (`UCN-OP-GCO-01F6`), operational detail, correction, and PDF rendering paths are completely untouched.
- Unit and regression tests confirm zero changes or side-effects on the `GRADUATE` variant.

---

## 8. Changed Files

1. `be/compass/good_moral/models.py`:
   - Defined `CANONICAL_YEAR_LEVELS` and `CANONICAL_SEMESTERS`.
2. `be/compass/good_moral/services.py`:
   - Added canonical input validation on creation (post-idempotency lock) and on targeted field update.
3. `be/compass/demo_seed/narratives.py`:
   - Updated seed narratives to use canonical `"3rd Year"` and `"5th Year"`.
4. `be/compass/demo_seed/timeline.py`:
   - Updated `academic_semester()` to return `"First Semester"` / `"Second Semester"`.
5. `be/tests/test_demo_seed.py`:
   - Updated calendar semester assertion to canonical values.
6. `be/tests/test_exit_interview_opportunities.py`:
   - Updated F4 test fixtures to use canonical values.
7. `be/tests/test_good_moral.py`:
   - Updated existing fixtures/tests to canonical values; preserved legacy rows via direct model creation.
   - Added full FORM-INPUT-1A regression test suite (10 year levels, 2 semesters, invalid inputs, idempotent replay, Counselor/GSS operational corrections, legacy preservation, locked state enforcement, 7 PDF rendering scenarios, and Graduate non-regression).
8. `fe/src/features/good-moral/good-moral-shared.tsx`:
   - Exported `GOOD_MORAL_YEAR_LEVELS`, `GOOD_MORAL_SEMESTERS`, `isCanonicalYearLevel`, `isCanonicalSemester`.
9. `fe/src/features/good-moral/good-moral-request-page.tsx`:
   - Replaced free-text Year Level and Semester inputs with accessible `<Select>` controls and empty unselected placeholders.
10. `fe/src/features/good-moral/good-moral-correction-form.tsx`:
    - Replaced free-text inputs with `<Select>` controls; added legacy non-canonical preservation and guidance callout.
11. `fe/tests/good-moral-request-standardization.test.mjs`:
    - Created comprehensive unit and component test suite (5 passing test cases).
12. `outputs/COMPASS-FORM-INPUT-1A-Implementation-Report.md`:
    - This implementation and verification report.

---

## 9. Verification Commands and Outcomes

| Directory | Command | Outcome |
|---|---|---|
| `be` | `.venv/bin/ruff check compass/good_moral/ compass/demo_seed/ tests/test_good_moral.py tests/test_demo_seed.py tests/test_exit_interview_opportunities.py` | **Passed** (All checks passed) |
| `be` | `.venv/bin/ruff format --check compass/good_moral/ compass/demo_seed/ tests/test_good_moral.py tests/test_demo_seed.py tests/test_exit_interview_opportunities.py` | **Passed** (38 files already formatted) |
| `be` | `.venv/bin/pytest tests/test_good_moral.py` | **85 passed** in 72.20s |
| `be` | `.venv/bin/pytest tests/test_exit_interview_opportunities.py` | **28 passed** in 43.64s |
| `be` | `.venv/bin/pytest tests/test_demo_seed.py -k "test_semester_follows_the_dataset_academic_calendar"` | **1 passed** (49 deselected) |
| `fe` | `pnpm typecheck` | **Passed** (`tsc --noEmit`, 0 errors) |
| `fe` | `pnpm lint` | **Passed** (`eslint .`, 0 errors) |
| `fe` | `node --import ./tests/support/register-tsx.mjs --test tests/good-moral-request-standardization.test.mjs` | **5 passed**, 0 failed |
| `fe` | `pnpm test` | **723 passed**, 0 failed |
| Repo | `git diff --check` | **Passed** (clean, no whitespace issues) |

---

## 10. Outstanding GCO/QMS Signoff Notice

> [!IMPORTANT]
> **Owner-Directed Requirement / Pending Institutional Signoff:**
> These Year Level and Semester selections are owner-directed application requirements derived from the FORM-INPUT-0 and FORM-FIDELITY-0 audits. They standardize system data entry without altering approved document revision registries.
>
> Formal institutional GCO/QMS signoff is required prior to production activation per institutional discrepancy items G-16 and FF-12.

---

## 11. Compatibility Declaration

- No database schema migrations or enum column migrations were performed.
- Text persistence is strictly preserved (`CharField(64)` and `CharField(80)`).
- Idempotent request replays for previously accepted requests remain fully compatible.
- Historical records with non-canonical text remain viewable, correctable on other fields, and issuable without data loss.
- No deployment or staging merge was executed.
