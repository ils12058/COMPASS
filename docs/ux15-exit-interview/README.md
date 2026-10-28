# COMPASS-UX15-PILOT-2 — Exit Interview form experience modernization

Experimental Proposal #15 slice for team review. Base and PR target:
`integration/ux15-modernization`; implementation: `feat/ux15-exit-interview`.
The fetched baseline was `f7e2e8c3b3d4fac57e294ae1452be54b93957cf0`, including merged PR #297.
The implementation branch was absent locally/remotely; a new isolated, initially clean worktree
was created from that integration HEAD. Staging and main are outside this change.

## Audit and UX rationale

| Source inspected | Existing behavior and intentional differences | Decision |
| --- | --- | --- |
| Shared `form-experience.tsx`, Panel, Button, Notice, Input, Select, Textarea and page-width conventions | Inventory has selected sections; Exit Interview is one continuous sheet. The shared save/error presentation is suitable, but step selection would misrepresent the document. | Reuse `FormSaveStatus`, extend `FormErrorSummary` with optional owner-supplied title/instruction, and add a small complementary anchor navigator. Keep the existing bounded page and visual tokens. |
| `form-safety/` | The form registers meaningful dirty state with the shared provider; the Back route is guarded. Internal routing, browser Back and native beforeunload cooperate with that guard. | Preserve registration and provider; same-page links only scroll/focus and never save or unmount sections. |
| `exit-interview-form.tsx` | Local form/saved snapshots, explicit Save draft, rating counts and missing-row links, conditional extra-terms validation, final confirmation and uncertain-outcome Refresh reconciliation already exist. | Preserve the state/mutation/validation functions. Compose clearer review and action areas around those facts. No autosave or new readiness policy. |
| `exit-interview-form-sections.tsx` and presentation utilities | Five official groups in order; native conditional controls; self ratings 1–5 and college ratings 0–5. Saved revision/item codes retain legacy Program Chair questions. A saved 0 is an answered response with no invented meaning. | Keep question text, scales, code/value mapping, native requiredness and instrument sequence. Keep semantic matrices and one radio group per original row. Improve target size, descriptions and local scrolling. |
| `exit-interview-shared.tsx`, response/detail pages and Student home | PanelSections are also used by historical/read-only responses. The parent owns eligibility, editable-versus-read-only selection, refresh failure and canonical completion. Home owns opportunity/Inventory prerequisites and entry. | Leave these sources unchanged. Scope layout adjustments to the editable form. Do not modernize staff queues, reports, opportunity management or historical responses. |
| Correction targets/context/history | Latest event supplies advisory targets, previous events remain history; hidden targets fall back to their parent choice. Focus enters a saved rating at its selected value. Hints are not field errors. | Preserve target maps, focus helper, context and history. In-page links focus headings only on explicit selection and do not track or replace correction focus. |
| Existing tests | Workflow eligibility, legacy/F9 contracts, exhaustive correction maps, reopening, keyboard/phone focus, field limits and draft-refresh retention already have focused checks. | Retain those regressions and add behavioral coverage for navigation, save failures, uncertainty and form reflow. |

The page remains a continuous institutional document. The visible section heading identifies the
current location; explicit links focus it beneath the portal header. There is no scroll observer,
visited-section model, completion percentage or compulsory progression. A footer link returns to
the section navigator. Rating counts report required ratings only, not optional-question completion.

Visual inspection caught a squeezed mobile question column after increasing touch targets. The
final matrix explicitly bounds the pinned question column by the available sheet width and keeps
horizontal scrolling inside the table region. This preserves side-by-side rating comparison without
duplicating controls or turning each question into a card.

## Changed-component inventory

| Component | Change |
| --- | --- |
| Shared `FormErrorSummary` | Optional `title` and `instruction` with the exact Inventory defaults retained. Domain validation and focus remain callbacks. |
| Shared `FormSectionLinks` | Native anchors with labels/targets supplied by the owner; optional focus destination for returning to navigation. No router, step state, persistence, observers or form-data collection. |
| Existing `FormSaveStatus` | Reused unchanged. Exit Interview supplies truthful text for saving, confirmed save and unconfirmed submission/refresh states. |
| `ExitInterviewForm` | Concise introduction, section links sourced from existing section definitions, a review PanelSection and existing PanelFooter/PanelMessage composition. Summary links cover existing missing ratings and extra-terms errors. Save/submit/refresh functions and their request bodies remain unchanged. |
| `ExitInterviewFormSections` / local `RatingMatrix` | Form-width-based field columns, less framing around delay details, keyboard-focusable named matrix regions, scrolling guidance, 44px minimum rating labels, bounded sticky question column, missing-rating error descriptions on the original radio controls, and bounded horizontal arrow-key scrolling only while the region itself has focus (radio-group arrows stay native). |
| New browser suite and synthetic fixture helper | Real local Next pages with mocked reads/writes. Covers interactions, uncertain outcomes, correction coexistence, keyboard, mobile/tablet, enlarged text and representative captures. |

No backend/API/schema, official question, option, requiredness, payload, opportunity, graduation
policy, form revision, historical record, authorization or confidentiality change. No dependency,
font, theme, workflow or deployment configuration changes.

## Branch and workflow safety

Before implementation, fetched and inspected the integration branch and confirmed PR #297's
squash commit in its ancestry. The four existing GitHub Actions files were inspected:

- `deploy-staging.yml` is `workflow_dispatch` only and verifies the staging ref and exact staging
  SHA. Feature/integration pushes and this PR do not match a deployment trigger.
- `frontend-targeted.yml` and `backend-targeted.yml` accept PRs to `staging` or
  `canon/compass-clean-baseline`, plus manual dispatch. They exclude the UX15 integration branch.
- `backend-full.yml` accepts pushes to those same two branches, filtered PRs to those branches,
  and manual dispatch. Neither UX15 branch matches.

No workflow dispatch or CI configuration edit is part of this slice. The workflow inventory has
no branch-create or workflow-completion deployment chain. Hosted CI does not automatically run
for this integration-targeted PR; the focused local results are documented below. This is an audit
of repository-controlled Actions, not uninspected hosting-account webhooks/settings.

## Visual evidence

See [before/after captures](screenshots.md). Every answer, account and correction event is synthetic.
The baseline is an archive of the exact integration SHA; after captures represent the final pilot.
Before captures use Next dev; after captures use the production build with the same pinned fonts,
fixture values and viewports. Matrix captures show the same original category/rows in both versions.

## Validation and limits

See [commands and targeted results](validation.md). Screenshots were inspected separately from test
assertions; tests passing alone is not a claim of visual or institutional acceptance.

The pre-existing top-bar overflow at 320px/200% root text remains outside this slice. Default-text
checks assert whole-page overflow; enlarged-text checks assert the modified form and navigator,
excluding intentional matrix scrollers. Nothing is clipped or hidden to satisfy these assertions.
Manual screen-reader, real-device Safari and GCO UAT have not been performed. Native HTML
conditional validation remains native; the shared summary does not duplicate those browser rules.

## Next adoption

Graduate Tracer is the next suitable candidate: its continuous sections already have anchors,
manual draft persistence and uncertain-submission recovery. It could reuse the anchor, save and
summary presentation while retaining voluntary participation, saved revisions and domain-owned
reconciliation. Routine Intake can adopt save/error presentation later without becoming a wizard.

Leave the PR ready for team review. Proposal #15 remains experimental until formally accepted.
Future slices branch from and target `integration/ux15-modernization`. No merge or deployment is
part of this delivery.
