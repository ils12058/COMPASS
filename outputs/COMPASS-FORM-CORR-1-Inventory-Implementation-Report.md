# COMPASS FORM-CORR-1 PR 2 — Individual Inventory Correction Targets: Implementation Report

**Slice:** PR 2 of 3. Inventory frontend only. It consumes the backend contract merged in PR 1 (#237).
**Outcome:** Counselors can name the Inventory answers to review in the existing reopen dialog. The Student sees those answers in plain language and is taken to each one in the editor. Targets stay advisory: they never mark an answer invalid and never block saving or resubmission.

---

## 1. Staging baseline

| Item | Value |
|---|---|
| `origin/staging` | `bea790e6c04a3ea6b7d69ce651e88d5ba3b724e2` (FORM-CORR-1 PR 1 squash, #237) |
| Contains | #236 FORM-INPUT-1A (`05d5e7d1`) and #237 FORM-CORR-1 backend (`bea790e6`) |
| Verified on the baseline | `be/compass/inventory/correction_targets.py` (148 codes, `MAX_CORRECTION_TARGETS = 30`); optional `targets` on `InventoryReopenRequest`; required `targets` on `InventoryCorrectionSummary` (`latest_correction.targets`); `InventoryCorrectionTarget` enum in `contracts/openapi.json` |
| Re-fetched before committing | Unchanged at `bea790e6` |

Where the audit proposal and the merged backend differ, the backend was followed. For example, the backend adds `organizations.transportation_modes` (the mode checkboxes) as its own code, and the frontend maps it.

## 2. Worktree and branch

| Item | Value |
|---|---|
| Worktree | `/Users/reynantlntno/Projects/COMPASS-FORM-CORR-1-INVENTORY` (new, from `origin/staging`) |
| Branch | `feat/form-corr-1-inventory-ui` |
| Untouched | Main checkout, audit worktree `../COMPASS-FORM-CORR-1-AUDIT`, backend worktree `../COMPASS-FORM-CORR-1-BE`, and every other agent's worktree and branch |
| Isolated resources | Own `node_modules` (`pnpm install --frozen-lockfile --offline`); locally generated client (`pnpm api:generate`, not committed); own Next dev server on port 3127 (not the shared 3000 or 3107); browser artifacts in this session's scratchpad. No backend, database or shared service was used |

## 3. Files changed

All application changes are inside `fe/src/features/inventory/**`.

| File | Change |
|---|---|
| `inventory-correction-targets.ts` | **New.** Exhaustive map from every backend code (keyed by enum value) to label, editor section, field group, scope, anchor, hint host, condition with fallback, and containing `<details>`. Also: catalog order, reading received codes, hint computation for a draft, focus order, and the focus routine |
| `inventory-correction-notice.tsx` | **New.** The Student's "Correction requested" notice with the "Answers to review" list. Buttons only when the editor passes a handler; plain text elsewhere |
| `editor/inventory-review-context.tsx` | **New.** React context that tells controls which hint to show and which hint ids to add to `aria-describedby` |
| `counselor/inventory-correction-target-chooser.tsx` | **New.** The optional "Answers to review" chooser in the reopen dialog |
| `counselor/inventory-record-detail.tsx` | Chooser in the dialog's `choices` slot; `targets` sent only when chosen; a reviewer-facing message for `inventory_invalid` |
| `editor/inventory-editor.tsx` | Notice with actionable targets; correction-target navigation beside the existing `selectIssue`; whole-section note; focusable section start as the last fallback; review provider around the sections |
| `editor/fields.tsx` | `TextField`, `TextAreaField`, `SelectField`, `CheckboxGroupField`, `BooleanField` show the review hint and add it to `aria-describedby`. `BooleanField` radios carry it too, because focus enters a radio group at one choice |
| `editor/family-section.tsx` | `inventory-parent-statuses`; `<details id="inventory-family-{member}-details">`, opened for a targeted detail as well as for the existing birth-date error; hint at "Add optional Spouse details" |
| `editor/background-section.tsx` | Sibling list hint; list fieldset and Add button described by it |
| `editor/health-section.tsx` | `inventory-boarding-exclusive`, `inventory-immunizations` |
| `editor/education-section.tsx` | `inventory-schedule-satisfied`; education rows extracted into `EducationLevelRow` (hooks per row) with a row hint; Program and Year Level hints |
| `editor/interests-section.tsx` | `inventory-course-first-choice`, `inventory-course-choice-reasons`, `inventory-interests` |
| `editor/organizations-section.tsx` | `inventory-transport-modes` group (`role="group"`); membership list hints; transportation row hints |
| `editor/plans-section.tsx` | `inventory-prior-counseling` |
| `editor/psgc-location-selector.tsx` | Location block hints; `inventory-permanent-location-add` on "Add permanent location details" |
| `inventory-shared.tsx` | `FieldGroup` accepts an optional `describedBy` |
| `inventory-home.tsx`, `student/current-inventory-page.tsx`, `student/inventory-history-detail.tsx` | Use the shared notice (plain text) |
| `fe/tests/form-corr-1-inventory.test.mjs` | **New.** 20 unit tests |
| `fe/tests/form-corr-1-inventory.browser.mjs` | **New.** 13 browser checks (Chromium and WebKit) |
| `outputs/COMPASS-FORM-CORR-1-Inventory-Implementation-Report.md` | This report |

**Not changed:** `be/**`, `contracts/openapi.json`, generated client, `fe/src/features/exit-interviews/**`, shared `components/ui/*`, authorization and notification code, Good Moral, document templates, `package.json`, CI workflows.

## 4. Reviewer selection

The existing "Reopen for correction" dialog keeps its title, consequence text, required **Correction instructions** (1000-character counter) and buttons. Below the instructions, in the dialog's `choices` slot so the dialog description stays plain text:

- **Answers to review (optional)**, with the help text "Choose the parts of the form the Student should look at again. They will see these with your instructions."
- **Eight collapsed sections** (native `<details>`, the shared `Disclosure`), one open at a time. The dialog never shows all 148 choices at once. Each summary shows "*n* selected".
- Inside a section: a **Whole section** checkbox ("Asks the Student to look at every answer in …"), then the answers under the editor's own field-group headings (Father, Mother, Spouse, Parent status, …).
- Whole-section targets are never expanded into answer codes; a reviewer may choose a section and specific answers in it.
- **"*n* of 30 selected"** (polite live region). At 30, every unchecked box is disabled and the text adds "Remove one to choose another."
- **Selected for review** lists the choices in form order before confirmation, each with **Remove** (`aria-label="Remove <label>"`), plus **Clear selection**. Focus moves to the next Remove button, or to the list heading.
- Nothing is selected by default. With no targets, the request body is exactly `{ reason }`, as before; with targets it adds `targets` in catalog order.
- While the request is pending, the whole chooser is disabled. After a failure, the selection and the instructions are kept for retry. A 422 `inventory_invalid` now reads "This correction request could not be saved. Check the instructions and the answers to review, then try again." instead of Student-facing copy.
- No second approval step.

## 5. Student correction experience

**Notice** (editor, Inventory home, current read-only view, history detail): the title "Correction requested" and the instructions are unchanged. When the request named targets, **Answers to review** follows the instructions, e.g.:

- Contact number — Personal & contact
- Father's occupation — Family & student support
- Educational history: Senior high — Educational background
- Whole section — Plans & counseling context

Then "Requested …" as before. Codes are never shown. A code this build does not know (only possible if the frontend is older than the backend) is counted as "1 more part of the form".

**Editable draft:** each item is a button ("Select an answer to go to it in the form."). Selecting it:

1. switches to the section (desktop navigation and the phone section `Select` both follow);
2. opens the `<details>` that holds the answer;
3. scrolls the control to the centre and moves focus to it;
4. falls back safely when the control is not rendered (§8).

**In context:** the targeted control shows "You were asked to review this answer." (rows and location blocks: "these answers"; lists: "this list"; whole sections: a note at the top, "You were asked to review this section."). It is linked through `aria-describedby`, styled in the info color, never `aria-invalid`, never danger, never `role="alert"`, and never says the answer is wrong.

**Other views:** Inventory home, the current read-only record and the history detail list the labels as plain text. They add no link or button, so a record that cannot be edited never looks editable. That includes a reopened draft stranded in an Academic Year that is no longer current (audit G9 / P-12).

**Pending semantics:** unchanged. The editor shows targets only while `correction_pending` is true. After resubmission the API returns `correction_pending: false` and `latest_correction: null`, so the targets disappear (browser-tested).

## 6. Mapping completeness

| Measure | Result |
|---|---|
| Codes mapped | **148 / 148**, keyed by enum value (`"personal.date_of_birth"`, never orval's dot-less keys) |
| Compile-time exhaustiveness | `satisfies Record<InventoryCorrectionTarget, …>`. Removing one entry fails `tsc` with TS1360 (checked, then restored) |
| Runtime parity | A unit test parses `be/compass/inventory/correction_targets.py`: same set, same order, same limit (30) |
| By scope | 8 sections · 124 answers · 13 rows/blocks (6 education levels, 5 transportation modes, 2 locations) · 3 lists |
| By section | Personal 19 · Family 58 · Background 9 · Health 17 · Education 11 · Interests 19 · Organizations 9 · Plans 6 |
| Conditional | 27: Spouse 15, transportation modes 5, boarding house 3, sibling list 1, two membership lists 2, permanent location 1 |
| Inside Family `<details>` | 36 (12 per member) |
| Verified against rendered controls | For every non-section code, a unit test renders its section with every condition met and checks that the anchor exists, the hint exists, and the anchor's `aria-describedby` includes it. A second render with every condition unmet checks that each fallback exists and is described. Whole-section anchors are checked in the rendered editor |
| Labels | Mirror the rendered control labels; each "label — section" string is unique; none contains `.` or `_` |

## 7. Accessibility and focus behavior

- **Focus order** (`inventoryCorrectionFocusOrder`): anchor (when its condition holds), then the condition's fallback, then `inventory-section-start`, a `tabIndex=-1` wrapper around the section heading. Every target therefore leads somewhere, including while the form is saving and its fieldset is disabled.
- **Focus target:** a form control receives focus directly. In a radio group, focus goes to the checked radio, as the Tab key would; in a checkbox group or list, it goes to the first enabled control.
- `<details>` holding the target is opened before scrolling and focusing; unrelated details are left alone (browser-checked: the father's details open, the mother's stay closed).
- **Screen readers:** the focused control is described by its hint (and by its existing help text). For fallbacks, the hint explains why the answer is not shown, e.g. "You were asked to review boarding-house details. They appear when you choose Boarding house." Lists and rows describe their container and the anchor and Add controls.
- **Keyboard:** the notice buttons work with Enter and Space; typing goes straight into the focused answer (browser-checked).
- **Mobile:** the phone section `Select` follows the navigation; no horizontal overflow at 390 px; the reviewer dialog stays inside the screen and scrolls.
- **Ids:** the nine ids reported by FORM-CORR-1 were added to the existing fieldsets/groups: `inventory-parent-statuses`, `inventory-boarding-exclusive`, `inventory-immunizations`, `inventory-schedule-satisfied`, `inventory-course-first-choice`, `inventory-course-choice-reasons`, `inventory-interests`, `inventory-transport-modes`, `inventory-prior-counseling`. Also new: `inventory-family-{father|mother|spouse}-details`, `inventory-permanent-location-add`, `inventory-section-start`, `inventory-section-review`, and `*-review` hint ids. No existing id was renamed. A unit test checks that ids are unique in every section with all targets applied. Boolean radio groups now use their id as the radio `name` (previously the legend); still one name per question.

## 8. Repeating-row safeguards

- **Siblings and organization memberships are targeted only as whole lists** (`background.siblings`, `organizations.inside_school`, `organizations.outside_school`), as the backend requires. The list hint sits at the list heading. Navigation goes to the first row's first input, or to the list's **Add** button when the list is empty. No index or row id is ever stored or sent; a test asserts no hint is attached to a row other than the first anchor.
- **Stable natural keys:**
  - Family members (`FATHER`/`MOTHER` always rendered; `SPOUSE` falls back to "Add optional Spouse details").
  - Education levels (all six rows always rendered).
  - Transportation modes (falls back to the mode checkboxes when that mode is not selected).
  - Locations (permanent falls back to "Add permanent location details").
- **Conditional fields:** boarding-house answers fall back to "Where do you live now?". A detail revealed by a category (civil status Other, PWD detail, occupation details, income amount, prior-counseling details, schedule reason, course-choice Other, immunization Other, intended-work Other) is targeted at its always-visible parent control, so it never hides.

## 9. Privacy and authorization

- No new endpoint, field, permission or capability semantics. Targets are read only from the existing `latest_correction` on the Student's own `/me/status`, `/me/current` and `/me/{id}` responses.
- The chooser appears only inside the reopen dialog, which opens only when the existing `canReopen` check passes (Counselor with `inventory.reopen`, submitted, not known historical). A view-only Counselor sees no reopen button, chooser or checkbox (browser-checked). Guidance Services Staff have no Inventory access, unchanged.
- The backend stays authoritative: it validates the codes, the limit and authorization again.
- No correction history is added; the notice appears only while a correction is pending.
- Codes never reach the URL, logs, notifications or the update payload.

## 10. Existing workflow compatibility

- `toInventoryPayload` still strips `latest_correction` (targets are nested inside it). Unit-tested on a response carrying targets; the browser save sends no `latest_correction`, `correction_pending`, `targets`, `id` or `status`.
- Draft save, **Save & continue**, review, submission validation and focus (`selectIssue`), and the unsaved-changes guard are unchanged. Following a target never saves (browser-checked).
- Targets add no save or submission issue (unit test with all 148 codes). An unchanged targeted answer does not block resubmission (browser-checked).
- FormRevision display, Academic Year handling, normalization and sensitive-data notices are unchanged.

## 11. Tests and outcomes

| Check | Result |
|---|---|
| `pnpm api:generate` | Generated from the committed contract (not committed) |
| `pnpm typecheck` | Pass |
| `pnpm lint` | 0 errors. 4 warnings, all pre-existing in `tests/portal-navigation-attention.browser.mjs` |
| `pnpm test` (all frontend unit tests) | **743 passed, 0 failed** (staging baseline: 723; +20 new) |
| `tests/form-corr-1-inventory.browser.mjs` — Chromium | **13 / 13** |
| `tests/form-corr-1-inventory.browser.mjs` — WebKit | **13 / 13** |
| `tests/form-ui-1b.browser.mjs` (Inventory review focus) | Chromium 6/6, WebKit 6/6 |
| `tests/form-input-standardization.browser.mjs` (Inventory) | Chromium 4/4, WebKit 4/4 |
| `tests/draft-and-session-safety.browser.mjs` | Chromium 24/24 |
| `tests/user-copy.browser.mjs` | Chromium 42/44. The 2 failures (`good-moral-unconfirmed-320/1440`) are **inherited**: the test calls `.fill('4')` on Good Moral "Year level", which #236 (`05d5e7d1`) made a select. This branch changes no Good Moral file |
| `pnpm build` (production) | Pass (`fe/next-env.d.ts` restored afterwards) |
| `git diff --check` | Clean |

**Browser checks:** the reviewer can choose sections and answers (sent in catalog order); a reason-only request still works; the selection stops at 30; pending and failure keep the selection; a view-only Counselor gets no controls; the dialog fits a phone. The Student can follow every kind of target on desktop and phone, by keyboard alone, through save and resubmission, and with a legacy reason-only correction. Inventory home and a stranded past-year draft list targets as plain text.

**Not run:** the backend suite (no backend change) and the full `test:ui:regressions` chain. CI's chain stops at inherited failures (§13).

## 12. Deferred work

- **Registering the new browser suite in CI.** `pnpm test:ui:regressions` lives on one shared line in `fe/package.json`, which PR 3 is likely to edit too. To avoid a conflicting edit, this PR does not register the suite. Recommendation: add `form-corr-1-inventory.browser.mjs` (both engines) together with PR 3's suite in one follow-up edit, or in this PR if reviewers prefer.
- Inventory correction history after resubmission (P-5), per-target notes (P-4), per-row sibling/organization targets, and Academic Year rollover for reopened Inventories (P-12/G9): unchanged and still deferred.
- Student and reviewer wording (P-6/P-7) follows the audit recommendations. A product owner should confirm it during review, including the variants "these answers", "this list" and "this section", and the fallback sentences.

## 13. Integration notes for PR 3 (Exit Interview)

- No shared file was changed, so PR 2 and PR 3 should not conflict. PR 2 touches only `fe/src/features/inventory/**`, two new test files and this report.
- Reusable patterns, not shared code:
  - key the map by enum value with `satisfies Record<…>`;
  - add a backend-catalog parity unit test;
  - use the dialog's `choices` slot for the chooser;
  - render plain text outside editable drafts;
  - focus the checked radio.
- The Inventory focus routine lives in the Inventory module on purpose. If PR 3 wants to share it, moving it to a shared location is a separate, reviewed change.
- **Inherited CI state on `staging`:**
  - `frontend-browser-regressions` stops at the #231 attention-badge checks ("My work31") and the WebKit Guidance Messages check.
  - `user-copy` Good Moral checks fail after #236 (above).
  - Backend `prepare` / static failures are documented in PR 1.
  - None of these comes from this PR.
- **Deployment:** the frontend needs the PR 1 backend deployed (migrations `inventory/0008` and `exit_interviews/0006`) before targets can be stored. Against an older backend, a request with `targets` would get a 422, while reason-only requests keep working. Deploy the backend first, as with every contract change.
