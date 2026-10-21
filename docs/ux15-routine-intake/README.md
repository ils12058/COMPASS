# COMPASS-UX15-PILOT-4 — Routine Student Intake

This pilot modernizes the Student Intake editor as a continuous, question-oriented form. It adds clearer section navigation, calmer spacing, persistent save feedback, linked submission guidance, and a responsive review/action area while preserving the existing Routine Interview workflow.

**Source baseline:** `integration/ux15-modernization` at `f74ee48da7191e1a2a3f0e7ba5bc4e0127655870`
**Merged baseline pilots:** #297 Individual Inventory, #298 Exit Interview, #299 Graduate Tracer, and #300 Counselor Evaluation
**Implementation branch:** `feat/ux15-routine-intake`
**PR target:** `integration/ux15-modernization`

## Focused audit

The Student Intake already had all seven question groups mounted in one document, separate controlled text answers, optional questions, multiple concern selections, a conditional Other specification, explicit Save Progress, server-confirmed draft state, dirty-navigation protection, a submission confirmation, and a read-only state after submission. Submission already requires at least one written answer or one selected concern; choosing Other also requires its specification. Save Progress and Submit Intake are separate actions.

The Student-facing detail page remains the authority for editability: only a current Student with the existing self-management capability can edit an active draft. Other Student states remain read-only. Counselor draft content remains unavailable through the existing server-owned access boundary until the Intake is submitted. Appointment creation/lookup, historical records, Counselor Evaluation prerequisites, and Counseling Encounter relationships are outside this editor and unchanged.

The interface now reuses `FormSectionLinks`, `FormSaveStatus`, and `FormErrorSummary` from `src/components/ui/form-experience.tsx`, plus `Panel`, `PanelBody`, `PanelHeader`, `PanelSection`, `PanelFooter`, and `PanelMessage`. It continues to use the shared `Button`, `Label`, `Textarea`, submission dialog, and unsaved-navigation guard. No additional shared framework or form engine was needed.

## Experience changes

- The form keeps all seven question groups available at once. Section links work as in-page navigation and move keyboard focus to the selected group; there is no forced step order or completion percentage.
- Each question group has a clearer heading and spacing. Narrative fields keep their original labels and payload keys. The full concern option set stays intact, with larger aligned checkbox targets and responsive wrapping.
- The Other specification remains conditional and keeps its existing clearing behavior. If missing at submission, the error summary links to the field, the field receives `aria-invalid`, and focus moves to that field.
- Save Progress remains explicit. `FormSaveStatus` reports unsaved, saving, and confirmed saved states; a failed save preserves the Student's answer and the dirty-navigation guard remains active.
- The review copy explains the private draft, editable save, read-only submitted state, and Counselor access boundary. Save Progress and Submit Intake remain separate, with wrapped actions on narrow screens.
- A failed or uncertain submission is not replayed automatically. The message now asks the Student to refresh and check the Intake status before trying again. The current editor does not automatically reconcile an uncertain result through its existing detail read; that recovery gap is documented and left for a future domain review.

## Changed-component inventory

| File | Change |
| --- | --- |
| `fe/src/features/routine-interviews/routine-student-intake.tsx` | Reuses shared form presentation primitives; adds section destinations, linked validation state, responsive concern controls, truthful save status, and clearer review copy. Submission and save mutation flow remains explicit and domain-owned. |
| `fe/tests/support/ux15-routine-intake-fixtures.mjs` | Adds isolated synthetic Student, Counselor, draft, submitted, and mutation fixtures. |
| `fe/tests/ux15-routine-intake.browser.mjs` | Covers section links, optional answers, explicit saving, errors, concern behavior, confirmation, read-only and confidentiality states, keyboard use, and responsive layout. |
| `docs/ux15-routine-intake/` | Adds this audit, validation results, and paired synthetic screenshots. |

No API client, contract, generated source, backend, database, official question, response mapping, permission, lifecycle, or institutional requirement changed.

## Visual evidence

The paired captures use synthetic answers and the same viewport for each comparison. No sensitive concern category is selected in the screenshots. See [screenshots.md](./screenshots.md).

## Limits and future adoption

The browser checks confirm the form itself stays within its 320px viewport at 200% root text. The portal shell has a separate existing top-bar overflow at that size: its page width measured 417px for a 320px viewport both before and after this pilot. The form panel's own horizontal overflow measured 334px before and 254px after, matching its 254px available width after the change.

Manual screen-reader and real-device testing remain pending. Proposal #15 is experimental until formally accepted. The next suitable adoption is a short Feedback/CSM form where the existing workflow fits; these shared pieces should be adopted selectively rather than imposing a draft or wizard flow.

## Integration safety

GitHub Actions on the integration baseline were inspected before implementation. Existing CI branch filters target `staging` or `canon/compass-clean-baseline`; the staging deployment workflow is `workflow_dispatch` only. This PR targets `integration/ux15-modernization`. No workflow was dispatched, and no staging/main update or deployment occurred.
