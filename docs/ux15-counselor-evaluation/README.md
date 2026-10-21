# COMPASS-UX15-PILOT-5 — Counselor Evaluation experience modernization

Experimental Proposal #15 slice for team review. Baseline and PR target: `integration/ux15-modernization`; implementation branch: `feat/ux15-counselor-evaluation`. The fetched baseline was `c5f1bb2bdd37fd98eb640d563553b425771cd140`, including merged Pilots #1–#3 (PRs #297–#299). Pilot #4 was not present as an open PR or integration commit at audit time. This pilot edits only the Counselor Evaluation workspace and its focused tests; it leaves the Student Intake, detail page, and shared Routine Interview logic untouched.

## Focused audit and decisions

| Area inspected | Existing behavior and differences | Decision |
| --- | --- | --- |
| Counselor Evaluation workspace | Six native radio groups, each with Not rated and 1–10; three Counselor narrative fields; explicit replacement save; direct Encounter recovery selection; Appointment resolution and linked-Encounter paths; separate consequential finalization. | Keep the instrument, payload mapping, saved/draft snapshots, and mutation behavior. Improve the presentation within the existing workspace. |
| Shared form experience and UI | FormSaveStatus, PanelSection, PanelFooter, PanelMessage, Button, Label, Textarea, ConsequentialActionDialog, and CanonicalPagination already cover the needed presentation. | Reuse these primitives. Do not add a universal form shell, new rating abstraction, or duplicate error summary. |
| Form safety | The shared UnsavedChangesProvider and useUnsavedChangesGuard already protect meaningful dirty forms across app navigation, browser history, and unload. Counselor Evaluation had no registration. | Register only while the evaluation differs from the last server-confirmed save. Do not save automatically. |
| Finalization and error recovery | Finalization links a completed eligible Counseling Encounter and makes the Evaluation read-only. Direct Encounter choices are never inferred; candidate selection, retry, and pagination are already domain-owned. | Preserve each path. After an uncertain finalization response, require a fresh authorized record read and refreshed candidate list before another deliberate confirmation. A failed status read must not replace the open detail query with an error. |
| Backend contract and privacy | Ratings accept integers 1–10 or null; narratives retain exact strings. The backend validates/decrypts the existing section, enforces assigned-Counselor and submitted-Intake access, links Encounters under existing matching rules, encrypts content, and records content-free audit metadata. | Read-only audit only. No backend, schema, API, encryption, validation, authorization, or visibility changes. |
| Earlier UX15 pilots | Pilots #1–#3 established shared save status, concise presentation, native controls, focused navigation, dirty guards, and domain-owned validation across distinct continuous and sectioned forms. | Follow their component reuse and preserve this professional record's separate ownership and lifecycle. |

FormErrorSummary is intentionally not used: this Evaluation has no structured field-level required-answer issues, and adding a completion checklist would create a new rule. FormSectionNavigation is also unnecessary: all Evaluation fields remain available in one continuous form, without a forced wizard or a new progress model.

## User-visible changes

- Adjustment ratings are grouped in a bounded responsive layout with one shared scale explanation, explicit screen-reader descriptions, visible selection and focus, and 44px controls.
- The original six labels, 1–10 values, Not rated null state, and three narrative labels remain intact. Narrative text is sent unchanged.
- Narrative fields have clearer hierarchy and more comfortable writing height and width.
- Save Evaluation uses the shared persistent save state. A save remains a separate action from finalization; success appears only after the canonical response confirms persistence, and a failed save keeps the edited text and dirty warning.
- Dirty drafts use the existing navigation guard.
- Encounter prerequisites and finalization consequences are stated clearly. Direct choices remain explicit, Appointment-backed records remain server-resolved, and linked records need no choice.
- Uncertain finalization is never automatically replayed. The current record is fetched without poisoning the active detail query; a confirmed draft refreshes the clean local Evaluation snapshot and Encounter candidates before another attempt is enabled. A confirmed finalized record becomes read-only.

## Changed-component inventory

- `fe/src/features/routine-interviews/routine-counselor-evaluation.tsx` — Evaluation layout, shared save state, dirty guard, responsive rating controls, clearer Encounter context, and safe finalization reconciliation.
- `fe/tests/routine-encounter-linking.test.mjs` — supplies the app's unsaved-navigation provider for the rendered workspace and asserts the original nullable ratings and narrative fields.
- `fe/tests/support/ux15-counselor-evaluation-fixtures.mjs` and `fe/tests/ux15-counselor-evaluation.browser.mjs` — synthetic API fixture and focused Chromium/WebKit interaction, safety, and viewport regressions.
- This directory — focused audit, validation results, and paired synthetic screenshots.

No other form, backend source, generated API client, workflow, dependency, theme, or deployment configuration changes are included. The experimental pattern may be considered for Routine Student Intake after its own Pilot #4 work is reconciled, then for other longer forms where durable draft state already exists. Short Feedback/CSM forms may reuse concise error presentation only; this pilot does not add draft persistence or navigation steps to them.

## Visual evidence and limits

See the [before/after screenshot index](screenshots.md) and [focused validation](validation.md). Every record and narrative is synthetic. Screenshots were reviewed visually at desktop and phone widths. Browser emulation does not replace manual screen-reader testing, real-device Safari, or Guidance Office UAT; those remain for team review. The known portal-shell overflow at 320px with 200% root text remains outside this component change; the modified form itself is checked for horizontal reflow.

Proposal #15 remains experimental until formally accepted. The PR targets only `integration/ux15-modernization`; this work is not a rollout, merge, or deployment authorization.
