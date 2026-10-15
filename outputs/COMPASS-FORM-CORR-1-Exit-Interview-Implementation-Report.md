# COMPASS FORM-CORR-1 PR 3 — Exit Interview Correction Targets: Implementation Report

**Slice:** PR 3 of 3. Exit Interview frontend only. It consumes the backend contract merged in PR 1 (#237).
**Outcome:** An authorized reviewer can name the Exit Interview answers to review in the existing two-step reopen flow. The choices are limited to the record's saved Form Revision. The Student sees those answers in plain language and is taken to each one, landing on the saved rating where there is one. Targets stay advisory: no answer is changed, interpreted, marked invalid, or required to change.

---

## 1. Staging baseline

| Item | Value |
|---|---|
| `origin/staging` | `bea790e6c04a3ea6b7d69ce651e88d5ba3b724e2` (FORM-CORR-1 PR 1 squash, #237) |
| Contains | #236 FORM-INPUT-1A (`05d5e7d1`) and #237 FORM-CORR-1 backend (`bea790e6`) |
| Verified on the baseline | `be/compass/exit_interviews/correction_targets.py` (68 codes, `MAX_CORRECTION_TARGETS = 30`, `allowed_correction_targets`); optional `targets` on `ReopenRequest` (≤ 30, reason 1–1000); required `reopen_events[].targets`; `ExitInterviewCorrectionTarget` enum in `contracts/openapi.json`; `college_feedback_item_codes` on the detail response (26 codes for a null revision, 23 for UCN F9) |
| Re-fetched before committing | Unchanged at `bea790e6` |

## 2. Worktree and branch

| Item | Value |
|---|---|
| Worktree | `/Users/reynantlntno/Projects/COMPASS-FORM-CORR-1-EXIT-INTERVIEW` (new, from `origin/staging`, no upstream tracking) |
| Branch | `feat/form-corr-1-exit-interview-ui`. It is not based on the Inventory PR 2 branch (#238) |
| Untouched | The main checkout, the Inventory worktree `../COMPASS-FORM-CORR-1-INVENTORY` and its branch, the audit and backend worktrees, and every other agent's worktree |
| Isolated resources | Own `node_modules` (`pnpm install --frozen-lockfile --offline`); a locally generated client (`pnpm api:generate`, not committed); an own Next dev server on port 3137 (separate from 3000, 3107 and PR 2's 3127); browser artifacts in the session scratchpad. No backend, database or shared service was used |

## 3. Files changed

All application changes are inside `fe/src/features/exit-interviews/**`.

| File | Change |
|---|---|
| `exit-interview-correction-targets.ts` | **New.** An exhaustive map from all 68 backend codes, keyed by enum value, to section, group, label, plain title, anchor, condition and fallback, and saved-contract metadata. It also provides `allowedExitInterviewCorrectionTargets`, reading received codes, hint computation, focus order, and the focus routine |
| `exit-interview-correction-target-chooser.tsx` | **New.** The optional "Answers to review" chooser |
| `exit-interview-review-context.tsx` | **New.** The context that tells controls and rating rows which hint to show. It also renders the whole-section note |
| `exit-interview-reopen-dialog.tsx` | Chooser in step 1; the reason gets the contract's `maxLength` 1000 and a counter (roadmap T-7); step 2 lists "Answers to review"; `targets` are sent only when chosen and only if allowed; a reviewer-facing message for a 422 `invalid_exit_interview_request` |
| `exit-interview-detail-page.tsx` | Passes the record's `college_feedback_item_codes` to the reopen action |
| `exit-interview-correction-history.tsx` | Adds "Answers to review" to the pending notice (buttons only when the editable form passes a handler) and lists each history event's targets as plain text |
| `exit-interview-form.tsx` | Hints come from the latest (pending) request; review provider; direct scroll-and-focus navigation |
| `exit-interview-form-sections.tsx` | Review hints on fields, comments and rating rows; new fieldset ids; whole-section notes; re-exports `exitRatingRowId` |
| `exit-interview-presentation.ts` | `exitRatingRowId` and `ExitRatingMatrixId` moved here unchanged. The map and the form share one definition without an import cycle |
| `fe/tests/form-corr-1-exit-interview.test.mjs` | **New.** 14 unit tests |
| `fe/tests/form-corr-1-exit-interview.browser.mjs` | **New.** 13 browser checks (Chromium and WebKit) |
| `outputs/COMPASS-FORM-CORR-1-Exit-Interview-Implementation-Report.md` | This report |

**Not changed:**

- `be/**`, `contracts/openapi.json` and the generated client.
- `fe/src/features/inventory/**` and every PR 2 file.
- Shared `components/ui/*`, permissions and notifications.
- Good Moral, PDF and form templates.
- `package.json` and the CI workflows.

## 4. Reviewer selection

The existing two-step flow is kept: **Reopen for correction**, then a form dialog, then **Review reopening**, then a confirmation dialog, then **Reopen for correction**.

**Step 1** keeps the required **Reason for correction**. It is now limited to 1000 characters with a "*n* / 1000 characters" counter, matching the backend's new `maxLength` (T-7). Below it:

- **Answers to review (optional)**, with the help text "Choose the parts of the form the Student should look at again. They will see these with your instructions."
- The form's sections as collapsed `<details>`, one open at a time, each summary showing "*n* selected":
  - General information
  - Section I — Program completion and plans
  - Section II — Self-Assessment
  - Section III — College Feedback
  - Suggestions / Recommendations
- In each section: **Whole section**, then the questions grouped as on the form:
  - Section I: Program completion, Significant learning experiences, Career plans.
  - Section II: the 15 items.
  - Section III: one group per category, holding its rating rows and its comment.
- A whole section is never expanded into answer codes.
- **"*n* of 30 selected"** (polite live region). At 30, every unchecked box is disabled.
- **Selected for review** with **Remove** per item and **Clear selection**; focus moves to the next Remove button or to the list heading.
- Nothing is preselected. **Review reopening** stays disabled until there is a reason.

**Step 2** (the existing confirmation) shows the reason and **Answers to review** in form order, or "None. The Student will see only the reason."

**Sending:**

- The request is `{ reason }` exactly as before, plus `targets` (catalog order) only when some were chosen.
- Targets not allowed on the record are filtered out before sending.

**Pending and failure:**

- While the request runs, step 1's chooser is disabled. Step 2 keeps its existing pending and error behavior.
- If the backend refuses the targets, step 2 shows "This correction request could not be saved. Check the reason and the answers to review, then try again." The reason and selection are kept for a retry (browser-checked).

## 5. F9 and historical revision handling

- **Source of truth:** the record's own `college_feedback_item_codes`, never the active revision, the Academic Year or a global setting.
- `allowedExitInterviewCorrectionTargets` mirrors the backend's `allowed_correction_targets`:
  - a rating code is offered only if its item is in the record's codes;
  - a comment code is offered only if its category has at least one of those items;
  - every other code is always offered.

| Record | Ratings offered | Comments offered | Total | Program Chair |
|---|---|---|---|---|
| UCN F9 (`college_feedback_item_codes` = 23) | 23 | 6 | **64** | None (no ratings, no comment, no group) |
| Legacy null revision (26) | 26 | 7 | **68** | 3 ratings and the comment |

- The Student form renders only the record's categories (unchanged). A Program Chair target therefore can never point at a missing row on F9 (unit-checked).
- Historical answers are never converted or filled in.
- **Backend authority:**
  - The backend still rejects codes outside the saved contract (422) and unsupported revisions (409).
  - Both are handled: the 422 with the new reviewer message above; the 409 with the existing `exit_interview_conflict` message.

## 6. Student correction experience

- **Pending notice** (`ExitInterviewCorrectionHistory` with `emphasizeLatest`): unchanged title "Correction requested", reviewer attribution ("… reopened this Exit Interview for correction.") and **Reason:**. When the request named targets, **Answers to review** follows the reason, then "Requested …". Example labels (real titles):
  - Program completion
  - Self-Assessment — Self Esteem
  - College Feedback — Guidance Counselor — Efficiency
  - College Feedback — Comments about the Guidance Counselor
  - Section II — Self-Assessment (whole section)
- **Codes are never shown.** A code this build does not know (only possible if the frontend is older than the backend) appears as "1 more part of the form".
- **Editable draft:** each label is a button ("Select an answer to go to it in the form."). The whole form is on one page, so selecting an answer scrolls to it and moves focus straight away. There is no section switch, delay, or state change.
- **Correction history:** each event lists its targets as plain text, keeping its reason and its reviewer and time line. Earlier and completed requests are never buttons.
- **Read-only views:** the reviewer's response view, and a Student draft that cannot be edited, show plain text.
- **After resubmission:** the record is `SUBMITTED`, so no request is shown as pending. The requests stay readable in history, as before (browser-checked).
- No history visibility is added: history comes from the same `reopen_events` the same audiences already receive.

## 7. Target mapping completeness

| Measure | Result |
|---|---|
| Codes mapped | **68 / 68**, keyed by enum value (`"self_assessment.SELF_ESTEEM"`) |
| Compile-time exhaustiveness | `satisfies Record<ExitInterviewCorrectionTarget, …>`. Removing one entry fails `tsc` with TS1360 (checked, then restored) |
| Runtime parity | A unit test parses `be/compass/exit_interviews/correction_targets.py`: same set, same order, same limit (30) |
| By kind | 5 sections · 8 general · 6 Section I (program completion, extra terms, delay reasons, learning, career Work, career Study) · 15 self-assessment rows · 26 college-feedback rows · 7 comments · 1 suggestions |
| Labels | Reuse the form's own labels (`SELF_ASSESSMENT_ITEMS`, `COLLEGE_FEEDBACK_CATEGORIES`, field labels); titles are unique and contain no codes |
| Verified against rendered controls | For every allowed code on both a legacy and an F9 record, a unit test renders the form and checks three things: the anchor exists, it is described by its hint, and ids are unique. Section headings and section ids match the form |
| Rating rows | Use the same `exitRatingRowId` as the form (one definition, moved to `exit-interview-presentation.ts`) |
| New ids | `exit-program-completion` (the audit's missing id) plus `exit-delay-reasons`, `exit-learning-experiences`, `exit-career-work-plans`, `exit-career-study-plans` on the existing fieldsets, and `*-review` hint and section-note ids. No existing id was renamed |

## 8. Rating navigation and accessibility

- **Focus order:**
  1. the anchor;
  2. for delay details hidden by "According to schedule", Program completion instead;
  3. the section heading as a last resort, given `tabindex="-1"` only when it is used.

  A target therefore always leads somewhere, including while the draft is saving and the controls are disabled.
- **Rating rows and radio groups:** focus goes to the **checked** radio, so the Student lands on their saved answer. With no answer, focus goes to the first enabled radio. The value is never changed (browser-checked for 4 and for 0, with no unsaved-changes notice).
- **One hint per rating row**, shown once in the row header, instead of on every choice. Each choice in the row is described by that hint, so whichever radio has focus announces it once. The row itself is described too.
- **Fieldsets** (Program completion, Reason for delay, Significant learning experiences, Work, Study): the hint follows the legend, and the fieldset is described by it. Program completion radios carry it as well.
- **Conditional fields:** "You were asked to review the delay details. They appear when you choose With some delay." appears at Program completion; nothing is revealed by changing an answer.
- **No error semantics:** never `aria-invalid`, never danger-styled, never `role="alert"`, and the hint text never calls an answer wrong.
- **Keyboard:** the notice buttons work with Enter and Space; typing goes straight into a focused field.
- **Mobile:** no horizontal overflow at 390 px; the reviewer dialog stays inside the screen and scrolls (browser-checked in both engines).

## 9. Rating 0 non-regression

- The College Feedback scale, its sr-only values and the "does not specify its meaning" note are unchanged.
  - The 0 column header stays "0", and its accessible value stays "Efficiency: 0".
  - No label such as "Not applicable" is introduced (unit-checked).
- Targeting a row whose saved rating is 0 shows the review hint once and keeps 0 checked.
  - Focus lands on the checked 0 radio.
  - Saving sends `{ item_code, rating: 0 }` unchanged (unit- and browser-checked).
- 0 is never treated as missing or invalid.
- The F9 and legacy answer contracts stay distinct: 23 vs 26 rating codes in the form state and payload.

## 10. Privacy and authorization invariants

- **No new capability, endpoint, field or notification.**
  - The chooser exists only inside the existing reopen action. That action renders only for `exit_interviews.reopen`, on the existing Head-designation reviewer path.
  - A reviewer with only `exit_interviews.view` sees no reopen action and no checkboxes (browser-checked).
  - Guidance Services Staff and ordinary Counselors cannot read responses, which is unchanged.
- **Targets are read only from existing authorized responses:** `reopen_events[].targets` on the reviewer detail and on the Student's own detail.
- **Codes stay out of everything else:** URLs, logs, notifications, Student Actions, payloads (unit- and browser-checked: no `targets` or `reopen_events` in saves) and PDFs.
- **The repository copy guard** (no "Head Guidance" wording in Exit Interview sources) still passes.

## 11. Tests and results

| Check | Result |
|---|---|
| `pnpm api:generate` | Generated from the committed contract (not committed) |
| `pnpm typecheck` | Pass |
| `pnpm lint` | 0 errors. 4 warnings, all pre-existing in `tests/portal-navigation-attention.browser.mjs` |
| `pnpm test` (all frontend unit tests) | **737 passed, 0 failed** (staging baseline 723; +14 new) |
| `tests/form-corr-1-exit-interview.browser.mjs` | Chromium **13 / 13**, WebKit **13 / 13** (including phone width) |
| `tests/form-ui-1b.browser.mjs` (Exit Interview limits, save, submit, legacy chair content) | Chromium 6/6, WebKit 6/6 |
| `tests/ux-hardening.browser.mjs` | Chromium 60/60 |
| `tests/draft-and-session-safety.browser.mjs` (unsaved-navigation safety) | Chromium 24/24 |
| `tests/user-copy.browser.mjs` (includes the Exit Interview correction reviewer copy) | Chromium 42/44. The 2 failures (`good-moral-unconfirmed-320/1440`) are **inherited**: the test calls `.fill('4')` on Good Moral "Year level", which #236 (`05d5e7d1`) made a select. This branch changes no Good Moral file |
| `pnpm build` (production) | Pass (`fe/next-env.d.ts` restored) |
| `git diff --check` | Clean |

**Browser checks:**

- **Reviewer:**
  - F9 choices are sent in catalog order after the review step.
  - Legacy Program Chair targets are offered and sent.
  - A reason-only request is unchanged.
  - The 30 limit holds, and removing one frees a place.
  - After a 422, the reason and selection are kept.
  - A reviewer without the reopen capability gets no controls.
  - The dialog fits a phone.
- **Student:**
  - Every kind of target works on desktop and phone: scalar, program completion, a hidden delay detail, career, a self-assessment row, the whole section, the College Feedback row with 0, and a comment. Earlier requests stay plain text.
  - Legacy Program Chair targets work.
  - Keyboard-only use works.
  - Save and resubmission work, with 0 unchanged and no pending notice afterwards.
  - A legacy reason-only correction is unchanged.

**Not run:** the backend suite (no backend change) and the full `test:ui:regressions` chain. The CI chain stops at inherited failures (§13).

## 12. Deferred work

- **Registering the browser suites in CI.** `test:ui:regressions` is one shared line in `fe/package.json`. Neither PR 2 (#238) nor this PR edits it, to avoid conflicting edits. Recommendation: one small follow-up adds both `form-corr-1-inventory.browser.mjs` and `form-corr-1-exit-interview.browser.mjs` (Chromium and WebKit).
- **Per-target notes (P-4)** and any wording change (P-6/P-7): wording follows the audit recommendations and should be confirmed in review. That includes the whole-section suffix "(whole section)" and the delay-details sentence.
- **Rating 0 meaning (P-10):** remains undefined and is not interpreted.

## 13. Integration considerations for Inventory PR 2 (#238)

- **No shared file was changed.** This PR touches only `fe/src/features/exit-interviews/**`, two new test files and this report, so it merges independently of #238 in either order.
- **The two slices follow the same contract:**
  - keyed by enum value with `satisfies Record<…>`;
  - backend parity test;
  - optional chooser with one section open at a time, the 30 limit, and Remove / Clear;
  - plain-language labels;
  - buttons only in the editable draft;
  - "You were asked to review this answer." via `aria-describedby`;
  - checked-radio focus;
  - no `aria-invalid`.

  The code is intentionally duplicated per feature (no shared-component edits). A later consolidation into a shared module would need its own review.
- **Small intended differences:**
  - Inventory switches editor sections; the Exit Interview form is a single page, so it scrolls and focuses directly.
  - The Exit Interview chooser is filtered by the saved revision.
  - Exit Interview titles read "Area — item", following the form's existing missing-rating list.
- **Inherited CI on `staging`:**
  - `frontend-browser-regressions` stops at the #231 attention-badge checks and the WebKit Guidance Messages check.
  - `user-copy` Good Moral checks fail after #236.
  - Backend `prepare` / static failures are documented in PR 1.
  - None of these comes from this PR.
- **Deployment:** deploy after the PR 1 backend (migrations `inventory/0008` and `exit_interviews/0006`). An older backend would reject a request that includes `targets`; reason-only reopens keep working.
