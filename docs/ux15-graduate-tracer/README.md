# COMPASS-UX15-PILOT-3 — Graduate Tracer form experience modernization

Experimental Proposal #15 slice for team review. Feature: `feat/ux15-graduate-tracer`.
Base and PR target: `integration/ux15-modernization` at
`132be02d69316d8456b0a244704c0a9f263d1e13`. The fetched integration history includes
PR #297 (`f7e2e8c3`) and PR #298 (`132be02d`). The requested feature branch was absent
locally and remotely; a new isolated worktree was created without resetting any branch.
The two existing open PRs target the separate Follow-Up stack; neither changes these shared
form components. The earlier pilot worktrees were clean when inspected.

## Focused audit and decisions

| Owning source | Existing behavior and legitimate domain differences | Smallest useful change |
| --- | --- | --- |
| `graduate-tracer-form.tsx` | Canonical saved draft plus local edits; explicit replacement; separate draft/email/row and submission checks; saved-draft submission; confirmation; no automatic mutation retry; canonical checks after uncertain submission; shared dirty guard. | Keep all save, submit, confirmation-opening and reconciliation handler bodies unchanged. Reuse persistent save status, a linked summary of existing issues, a compact review area and shared PanelFooter/PanelMessage. Review does not write data. |
| `graduate-tracer-form-sections.tsx` | Official A/B/C groups, College → Program filtering, institutional year bounds, dynamic degrees/exams/training with stable `formKey`, degree-reason checkbox comparison. | Preserve labels, callbacks, row identities, IDs and options. Remove redundant record frames, wrap long actions and use available form width for columns. |
| `graduate-tracer-form-fields.tsx` | Native Input/Select/Textarea, field error descriptions, fieldsets for choices. Final requiredness uses `aria-required`; it does not prevent saving partial drafts. | Retain that distinction. Give radio/checkbox labels 44px minimum height and describe focused inputs with their existing group errors. Add one feature-local scroll wrapper used by the two comparison tables. |
| `graduate-tracer-employment-section.tsx` | Employed, not-employed and never-employed paths; self-employment skills; first-job conditions; Other explanations; job-level radio comparison; curriculum competencies. | Keep every conditional expression and callback. Reduce nested framing around first-job answers and improve matrix target sizes/local scrolling. No alternate active controls. |
| `graduate-tracer-presentation.ts` | Five official sections; historical summary-to-ID fallback; row-to-payload mapping; normalization clears inactive employment/Other branches; authoritative existing domain validation. | Unchanged. No second validator, completion model, policy, classification or payload mapping. |
| `graduate-tracer-shared.tsx` | PanelSection composition shared by editable and historical responses. | Retain all IDs/order; improve explicit anchor focus outline and scroll offset under the portal header. Read-only answer rendering and status/error mappings stay unchanged. |
| Student workspace, response, access and detail/operational components | Parent owns GRADUATED eligibility and capabilities, voluntary start, draft/submitted/read-only selection, confidential reviewer access, disposed-response handling and canonical query data. Operational/reporting workflows differ from Student editing. | Unchanged. No six-month gate, academic verification/dependency, Good Moral prerequisite, reminder, new collection or reporting behavior. |
| Shared `form-experience.tsx`, Panel/Button/Notice/Input/Select/Textarea, `form-safety/` | Inventory uses selected sections; Exit Interview uses a continuous instrument. Shared links/save status/error summary are presentation-only. The existing provider owns route, browser Back and native unload protection. | Reuse `FormSectionLinks`, `FormSaveStatus`, configurable `FormErrorSummary`, PanelHeader/Section/Footer/Message. No shared-source change, wizard, observer, new guard or form engine. |
| Earlier pilot documentation and tests | PR #297 established default Inventory summary behavior; #298 added continuous links and a configurable summary, 44px rating labels and bounded keyboard scrolling. Existing tracer regressions already check pinned-column reachability and confidentiality. | Reuse those focused regressions; add synthetic domain/UX tests rather than duplicating broad suites. |

The survey stays continuously mounted, in the same five-section order, with natural scrolling.
The horizontal/sticky section rail becomes a wrapped in-sheet link group: all destinations are
visible on phones without a competing sidebar. Explicit selection focuses the original named
section; Back to sections returns focus to navigation. No completion percentage, visited state,
forced sequence, autosave or data-bearing navigation is introduced.

Review answers exposes existing draft and submission issues, deduplicated by original field ID.
Save alone exposes only existing draft constraints. Summary actions focus the original field or
first native choice in its group; hidden employment branches remain governed by existing
normalization and validation. Failures remain contextual and retain dirty input. The one persistent
save status reports dirty, pending or confirmed persistence beside the actions.

The two matrices retain captions, column/row headers, native groups, official names/values and
local horizontal scrolling. Their scroll areas are named and keyboard focusable; only unmodified
Left/Right with focus on the region scroll it, leaving native checkbox/radio keys intact. Narrow
fixed table layout bounds the pinned label and each answer column; wide forms retain automatic
table layout. Existing 320/390px regressions verify both columns can be fully reached.

## Changed-component inventory

- `GraduateTracerForm`: shared navigation/save/error presentation; review controls; deduplicated
  visible issue list; one action area. Existing mutation and reconciliation bodies are unchanged.
- `GraduateTracerGeneralSection`, `GraduateTracerEducationSection`, `GraduateTracerTrainingSection`:
  container-based columns, flatter dynamic rows and wrapping record actions; accessible degree matrix.
- `GraduateTracerEmploymentSection`: container-based columns, flatter first-job group, accessible
  job comparison; branching and question wording unchanged.
- Local field helpers and `GraduateTracerChoiceMatrix`: 44px choice labels, original error
  descriptions on focused choices, one bounded feature-specific scroll wrapper.
- `GraduateTracerSection`: focus/scroll presentation only, including when reused by read-only responses.
- Dedicated browser/unit tests and fixture helper; audit, validation and 12 paired screenshots.

No backend, contract, schema, API generation policy, institutionally controlled question, option,
requiredness, payload mapper, draft persistence semantics, lifecycle, retention, capability or
notification change. No new dependency, font, palette, storage, workflow or deployment configuration.
This preserves Proposals #11 (form safety), #12 (instrument fidelity), #13 (authorization boundaries)
and #15 (shared presentation with domain-owned behavior). The proposal notes are design context;
the explicit Pilot 3 request defines this implementation scope.

## Branch and deployment audit

Before implementation and before push, inspected the four repository-controlled Actions workflows:

- `deploy-staging.yml` is manual `workflow_dispatch` only. It checks the staging ref, exact current
  staging SHA and explicitly supplied expected SHA. Neither the feature push nor integration PR is
  a deployment trigger. The default main branch also retains this manual trigger.
- `frontend-targeted.yml` and `backend-targeted.yml` accept PRs to `staging` or
  `canon/compass-clean-baseline`, plus manual dispatch. This integration PR is excluded.
- `backend-full.yml` accepts pushes and filtered PRs to those same two branches, plus manual
  dispatch. Both UX15 branches are excluded. There is no create/workflow_run/repository_dispatch
  deployment chain in the workflow inventory.

No workflow is dispatched and CI configuration is unchanged. Hosted Actions checks are not
expected for this integration-targeted PR, so [validation](validation.md) records local evidence.
This audit covers repository Actions; external hosting-account webhooks/settings were not inspected.
Staging and main are not modified; no deployment or automatic merge is part of this delivery.

## Visual evidence and limits

See [12 before/after pairs](screenshots.md) and [focused results](validation.md). All fixtures and
captures are synthetic. Screenshots were inspected visually; this found adjacent review/navigation
links without spacing, which were placed in a wrapping action row before final capture.

The known portal top-bar overflow at 320px with 200% root text remains a separate shell issue.
Default-text checks assert whole-page overflow; enlarged-text checks assert the form, excluding
intentional local matrix scrollers. Nothing is clipped or hidden to make the checks pass.
Automated Chromium/WebKit viewport emulation is not manual screen-reader testing, real-device
Safari or Guidance Office UAT; those have not been performed.

## Next adoption

Routine Student Intake can reuse persistent save/error presentation inside its existing encounter
workflow. Keep appointment/intake ownership and its own review/submission rules. Feedback/CSM may
later reuse error summaries; its short, non-durable-draft workflow should not acquire Save draft.
Future UX15 slices branch from and target the integration branch until formally accepted.
