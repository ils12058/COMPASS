# GM-INV-1 delivery report

Branch: `feature/gm-graduation-inventory-college` · PR base: `staging` · 16 November 2026

## Changes

### A1 — Graduation Program

- Graduation CSV accepts optional `program_code`. Blank or omitted values store no Program; a supplied code must name an active Program under the row's active College. Invalid rows cannot apply.
- Preview shows the new and previously recorded Program codes. Both participate in the preview fingerprint, and apply retains the existing confirmation and stale-preview checks.
- Manual graduation accepts optional `graduated_program_id`, validates the College relationship and active state, writes the existing field, and includes Program changes in its idempotency comparison and audit metadata.
- The manual form filters Programs to the chosen College, clears the selection when the College changes, and reviews a cleared Program as “Not recorded.” Import help, template, and preview include the optional column.

### A2 — Registrar-backed graduate requests

- Self-service and GCO-assisted creation take graduation date and College from `StudentGraduationRecord`. A recorded Program supplies the degree; otherwise the degree remains typed. Major remains optional typed text.
- Date and recorded degree use the existing request snapshot fields. Creation audit metadata freezes the graduation record ID, College, Program-name degree, date, verification source, and verification time.
- Later academic-record changes do not alter the request's certificate facts or its displayed verification evidence. Registrar-backed date and degree are excluded from certificate corrections.
- Both forms prefill and lock the recorded fields. Student and staff detail views show the basis; staff also see the frozen verification source and formatted time.

### A3 — Document check

- A graduate without a record can request using typed degree, major, and date. Student copy is: “Bring your diploma or TOR when you present your Official Receipt.”
- Staff copy is: “Not in the Registrar's record. Check the diploma or TOR before preparing.” The Prepare dialog requires “I checked the diploma or TOR” for this basis.
- The backend rejects missing confirmation. A successful Prepare audits the confirming actor and time, tied to the request's preparation actor/time. Issuance requires that evidence as well.
- A legacy ready request without this evidence offers Prepare again, requires confirmation, and records a fresh preparation. Issuance stays unavailable until that check is recorded. Repeating a completed preparation preserves its actor and time.

### A4 — Basis copy

Replaced all four specified “doesn't/hasn't/can't verify” strings with the bounded Registrar or document-check presentation. Raw backend diagnoses are not rendered.

### B1 — Inventory–College check

- A changed Program is checked on save, and the saved Program is checked again on submit, including submit replay. When current College is unset, any active Program remains allowed.
- The Inventory response exposes a bounded current College summary. The editor filters active choices to that College and retains an out-of-College saved value with a correction note.
- Searched all Program assignments and Program-ID writes. The Student writer is the single editing path; there is no staff-assisted Inventory content writer. Staff reopen for correction, and the Student's save/resubmit uses the same guard. Existing staff permissions remain enforced.

### B2 — Current Student Good Moral

- Creation, Prepare, and issuance reject a submitted Inventory whose Program belongs to another current College.
- Academic context and the assisted picker expose `COLLEGE_MISMATCH`. The picker states the discrepancy and correction route rather than presenting conflicting Colleges as valid.
- Checks use the existing Student row fence. Prepare retains the request/receipt lock order and locks the staff actor and Student together in UUID order.

### Seeder

- Most seeded graduation records now include their persona's Program. `recent_graduate` retains a College/date-only record for typed-degree coverage.
- Graduated persona `bg_44` (Samuel) intentionally has no graduation record for the diploma/TOR path.
- Existing graduate issuance scenarios explicitly confirm the document check. Verification checks every saved Inventory with a current placement against its Program College, and tests cover the complete current Student dataset.
- Account counts and UAT-50 allocations are unchanged. The existing Inventory seed writer already selected each persona's College-consistent Program.

## Error codes

| HTTP | Code | Student or general message |
| --- | --- | --- |
| 409 | `inventory_program_college_mismatch` | Choose a Program from your College. If your College has changed, ask the Guidance Office. |
| 409 | `good_moral_inventory_college_mismatch` | Your Inventory's College doesn't match your current College. Ask the Guidance Office to correct it. |
| 409 | `good_moral_graduate_document_check_required` | Check the diploma or TOR and confirm it before preparing. |

Staff Good Moral mismatch message: “The Inventory's College doesn't match the Student's current College. Reopen the Inventory for correction, then have the Student choose a Program from their current College and resubmit.”

## Contract

- Added Student-only `GET /api/v1/good-moral/me/graduation-context`, operation ID `goodMoralGetMyGraduationContext`.
- Added `GraduationBasis`: `REGISTRAR_RECORD`, `DOCUMENT_CHECK`; added F4 eligibility value `COLLEGE_MISMATCH`.
- Detail adds nullable `graduation_basis` and `graduated_college`. Operational detail alone adds graduation verification source/time and document confirmer ID/time. The assisted picker adds bounded staff graduation context.
- Prepare accepts optional `diploma_tor_checked`, default `false`.
- Manual graduation accepts optional Program ID; academic responses return an optional Program summary; graduation previews return Program codes; Inventory returns a bounded current College summary.
- Regenerated `contracts/openapi.json` and the Orval frontend client. Generated client files remain uncommitted under repository policy. Contract tests assert enum values, operation identity, defaults, optionality, and staff-only evidence boundaries.

## Decisions and defaults

- Conflicting submitted date/degree values are ignored in favor of the Registrar's recorded values. The corresponding UI fields are locked.
- The existing database constraint requires a graduate request's `college_snapshot` to remain empty. College is therefore frozen in creation audit metadata and exposed as `graduated_college`; no migration or constraint change was made.
- A record without Program confirms the recorded date/College; typed degree remains correctable. A recorded Program degree and recorded date remain fixed on the request.
- Legacy requests lacking frozen creation evidence default to `DOCUMENT_CHECK`. A later-added Registrar record does not retroactively verify an earlier request.
- Legacy ready requests can record the missing check by preparing again; a completed documented preparation remains idempotent.
- Inventory changes do not mutate academic placement. The existing correction/reopen workflow resolves discrepancies.
- No document uploads, new organization filter, new staff Inventory editor, migrations, staging reset, merge, or deployment were introduced.

## Verification

All database tests used local synthetic test data with `tests.settings`; no staging or live database was accessed.

| Check | Result |
| --- | --- |
| Affected backend regressions, including academic imports/records/reads, Inventory, seed, Good Moral, contract and lock scope | Initial run identified fixtures requiring the new document confirmation and consistent College. Updated those fixtures. Final results recorded below. |
| Receipt, authenticated workflow, and verification/concurrency regressions | 435 passed, 2 opt-in proxy tests skipped; one legacy-date fixture failure subsequently corrected. Final focused rerun recorded below. |
| Ruff check and format check on changed backend files | Passed |
| OpenAPI export `--settings=tests.settings --check` | Passed |
| Backend CI manifest `verify` | Passed: 241 files, each exactly once across six full-regression shards |
| Frontend affected unit tests | Initial affected set: 160 passed. Final affected set after review fix: 154 passed. |
| Frontend lint | Passed with five existing unused-variable warnings in counseling browser specs |
| Frontend typecheck | Passed |
| Normal production build | Passed |
| Production UI-test build | Passed; rebuilt after the manual-review fix |
| Affected browser suites | All ten suites passed on Chromium and WebKit: 122 checks per engine, 244 total |
| Final request/manual-record and document-gate browser reruns | Passed on both engines, including cleared Program review |
| `fe/next-env.d.ts` | Restored after builds |

Browser suites: `gm-inventory-academic-basis`, `good-moral-request`, `good-moral-assisted`, `good-moral-receipt`, `good-moral-print`, `student-academic-record`, `student-academic-batch-import`, `student-academic-roster-import`, `ux15-inventory`, and `form-corr-1-inventory`. These browser runs intercepted synthetic APIs on the production test server on port 3107. They establish UI behavior, not staging/live UAT or physical-device assurance.

### Final backend results

The receipt/authenticated/verification regression rerun passed 435 tests and skipped two opt-in loopback Next proxy tests. Its one legacy-date fixture failure was corrected and passed in the final focused run.

The final focused run passed 178 cases. The remaining new replay assertion was corrected to compare the canonical full-precision preparation token, rather than the millisecond-formatted display timestamp. The complete new GM-INV test file then passed all 17 cases (including that case). All 179 cases in the final focused set are now verified passing. Academic import/record/read, Inventory, seed, and lock-scope cases outside that focused set passed in the initial affected run.

Final static validation passed for all 24 changed backend Python files, and OpenAPI export confirmed the committed contract is current. No whole local repository suite was run.

### Hosted CI

Pending PR creation and hosted validation. Known prior failures to distinguish if observed: `ux15-consolidation` Form reflows at 320/390 px, and WebKit `ux15-goa-home`.

## Screenshots

Selected screenshots are retained for both engines under [gm-inv-screenshots](gm-inv-screenshots/); each suite's `results.json` retains its check outcomes. Stale failed-locator images and unrelated screenshots were removed.

- [Registrar-backed request with locked fields](gm-inv-screenshots/chromium/good-moral-student/registrar-graduate-locked-fields.png)
- [No-record request with bring-documents copy](gm-inv-screenshots/chromium/good-moral-student/student-former-external-postgraduate-f6-request.png)
- [Assisted Registrar request review](gm-inv-screenshots/chromium/good-moral-assisted-chromium/assisted-registrar-graduate-review.png)
- [Document-check Prepare confirmation](gm-inv-screenshots/chromium/gm-inventory-academic-basis/document-check-prepare.png)
- [Registrar Prepare without document checkbox](gm-inv-screenshots/chromium/gm-inventory-academic-basis/registrar-prepare.png)
- [Inventory choices filtered by College](gm-inv-screenshots/chromium/gm-inventory-academic-basis/inventory-college-options-desktop.png)
- [Saved mismatch on phone](gm-inv-screenshots/webkit/gm-inventory-academic-basis/inventory-college-options-saved-mismatch-phone.png)
- [Manual graduation Program](gm-inv-screenshots/chromium/student-academic-record/manual-graduation-program.png)
- [Graduation CSV preview](gm-inv-screenshots/chromium/student-academic-batch-import/graduations-preview.png)

The selected screens were visually reviewed for legible copy, date formatting, controls, and desktop/phone layout.
