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
- The backend rejects missing confirmation. A successful Prepare audits the confirming actor and time, tied to the request's preparation actor/time. Confirmation time is normalized to UTC so a Manila-offset service timestamp matches its persisted preparation evidence. Issuance requires that evidence as well.
- A legacy ready request without this evidence offers Prepare again, requires confirmation, and records a fresh preparation. Issuance stays unavailable until that check is recorded. Repeating a completed preparation preserves its actor and time.

### A4 — Basis copy

Replaced all four specified “doesn't/hasn't/can't verify” strings with the bounded Registrar or document-check presentation. Raw backend diagnoses are not rendered.

### B1 — Inventory–College check

- A changed Program is checked on save, and the saved Program is checked again on submit, including submit replay. When current College is unset, any active Program remains allowed.
- The Inventory response exposes a bounded, read-only current College summary. The editor omits it from writable payloads, filters active choices to that College, and retains an out-of-College saved value with a correction note. Its saved Year Level is preserved without calling an active Program from another College “inactive.”
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
| Inventory save/caption follow-up | 110 frontend unit tests and 28 backend correction-target tests passed; browser checks in both engines verify actual save payloads omit read-only College context |
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

The final focused run passed 178 cases. The remaining new replay assertion was corrected to compare the canonical full-precision preparation token, rather than the millisecond-formatted display timestamp. The complete new GM-INV test file then passed all 17 cases (including that case). All 179 cases in that focused set are verified passing. Academic import/record/read, Inventory, seed, and lock-scope cases outside that focused set passed in the initial affected run.

The follow-up document/preparation/verification run passed all 120 cases, including the new UTC/Manila timestamp regression. The GM-INV file now has 18 passing cases. Inventory correction-target regression passed all 28 cases after the read-only payload fix.

Final static validation passed for all 25 changed backend Python files, and OpenAPI export confirmed the committed contract is current. No whole local repository suite was run.

### Hosted CI

PR: [#376](https://github.com/ils12058/COMPASS/pull/376), targeting `staging`. Rebase immediately before PR creation completed without conflicts against `origin/staging` at `8ff40ef8`; FINAL-UI-1 had not merged at that fetch.

Completed hosted validation on `b5fe7c07c5e48dd465ac005949f19f363b89a332`:

| Workflow | Result |
| --- | --- |
| [Full backend regression](https://github.com/ils12058/COMPASS/actions/runs/43785186114) | Passed: all six shards and static/contract checks; 6,783 tests passed, four skipped |
| [Targeted backend validation](https://github.com/ils12058/COMPASS/actions/runs/43785186104) | Passed: preparation/static/contract checks, all six selected full-suite shards, and the final gate |
| [Frontend validation](https://github.com/ils12058/COMPASS/actions/runs/43785186168) | Lint, typecheck, normal production build, synthetic browser build, and all 1,331 unit tests passed. Six of eight browser shards passed; the two shard-1 failures are detailed below. |

The Inventory correction round-trip regression now passes in hosted CI: full-backend shard 4 passed all 1,169 tests. The serializer excludes read-only `current_college`; local actual-save browser checks cover that boundary too.

Remaining browser failures were left unchanged as requested:

- Chromium and WebKit shard 1: `ux15-consolidation.browser.mjs` reports the known Inventory, customer, and CSM Form reflows at 320/390 px (six checks per engine).
- Chromium shard 1 additionally reports `counseling-closure.browser.mjs`, `keyboard-close-review-input-confirmation-and-focus` (20 of 21 checks passed). The Counseling implementation and this spec are unchanged by GM-INV-1; its request paths are unaffected by the added Good Moral fixture route. WebKit passed that suite. The artifact records an equality assertion but does not retain its full expected/actual values, so no cause is claimed.
- The previously known WebKit `ux15-goa-home` failure did not recur.

Earlier hosted runs on `95e43e83ffc2277199fde85b42ae584b82137704` caught the Inventory round-trip failure, now fixed, and passed all 1,330 frontend unit tests. An earlier Exit Interview unit fixture also lacked graduation context and was fixed. Prior runs: [full backend](https://github.com/ils12058/COMPASS/actions/runs/43782463741), [targeted backend](https://github.com/ils12058/COMPASS/actions/runs/43782463748), [frontend](https://github.com/ils12058/COMPASS/actions/runs/43782463772).

The final report-only follow-up changes Markdown alone; implementation and test files are unchanged from the completed CI head above. GitHub scheduled its automatic checks after a delay. The final-head runs are tracked in [the PR checks](https://github.com/ils12058/COMPASS/pull/376/checks). No merge or deployment was performed.

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
