# COMPASS-UX15-PILOT-1 — Unified Form Experience Foundation

Reversible Individual Inventory pilot for team review. Base: `staging` at
`0a843dae20c01984d0fb9aa46d5eef34102ab386`, fetched October 21, 2026.
The supplied Development Proposal Notes, especially #15, are design references;
the explicit pilot request defines implementation scope. This is not institutional sign-off.

## Focused current-state audit

| Area inspected | Existing foundation and justified differences | Pilot decision |
| --- | --- | --- |
| `src/components/ui/` | Panel/Header/Section/Footer/Message, Button, Notice, Select, Label, Input, Textarea and ConsequentialActionDialog already supply surfaces, controls and confirmation. ActionStatus supplies transient routine success feedback. | Reuse these. Keep long-form save state persistent beside actions rather than introducing a second toast system or universal form shell. |
| `src/features/form-safety/` | The provider registers dirty forms, intercepts guarded links, protects browser traversal and beforeunload; the hook carries only dirty state and warning text. | Preserve it and Inventory's existing registration. Do not implement the prospective save-and-leave adapter from #11 or collect answers centrally. |
| Inventory editor | Eight answer sections plus review, free section jumping, native mobile selector, dirty/saved payload comparison, manual Save progress and Save & continue, draft versus submission validation, field focus, correction targets and explicit final confirmation already exist. | Extract presentation only: navigation, persistent save state and an error summary. Retain all mutation bodies, validators, correction mapping and route ownership. |
| Exit Interview | Long grouped PanelSections, rating summaries, draft save, confirmation and correction context. Its instrument grouping differs legitimately from Inventory. | Candidate for error-summary presentation; a future navigation adapter must target its existing groups rather than copying Inventory's step state. |
| Graduate Tracer | Anchor section links over a continuous form, replace-draft save, separate final confirmation and uncertain-submission reconciliation. | Candidate for common navigation appearance/error summary; retain continuous layout, voluntary participation and reconciliation. |
| Routine Student Intake | Focused question groups, contextual fields, Save progress, review and separate submission inside the encounter workflow. | Candidate for save-state presentation. Keep appointment/encounter and intake ownership. |
| Feedback / CSM | Short one-session forms with grouped questions, review/submit confirmation, idempotent recovery and dirty protection. No durable draft operation. | Candidate for error summary only. Do not add Save progress or section steps. |
| Typography / theme / layout | Existing Outfit/Plus Jakarta fonts, semantic colors, near-square panels, `pageSheetWidth`, focus rings and accessibility preferences. Existing fields retain institutional grouping and labels. | No new fonts, palette, dependencies or component library. Use the existing page width and responsive sheet. |

The genuine divergence is presentation: Inventory's section navigator was feature-local;
its error-summary buttons were embedded in a framed message; its Save confirmation and dirty
status were separated; action groups could overflow at enlarged text sizes. None requires
an engine, registry, metadata schema or a new source of workflow truth.

### Proposal compatibility

- **#11:** existing shared form safety remains authoritative; no local/browser draft storage,
  guard replacement or autosave.
- **#12:** keep official questions, wording, options, requiredness, addresses, institutional
  identity, form revision and historical representation. Address consolidation is deferred.
- **#13:** keep role/capability/resource checks and Student eligibility unchanged. No terminology
  or grant migration, additional access, backend API or schema changes.
- **#15:** calm framing, free section choice, position rather than completion percentage,
  domain-owned state, explicit manual save and final confirmation. The other proposed forms
  and broader portal redesign remain outside this pilot.

## Changed-component inventory

| Component(s) | Change |
| --- | --- |
| `src/components/ui/form-experience.tsx` — `FormSectionNavigation` | Source-supplied section labels/order, current-step semantics, named desktop navigation, native mobile selector, optional domain error counts. No completion calculation, persistence or router logic. |
| Same file — `FormSaveStatus` | One persistent polite status: saved draft, unsaved changes, saving, or a confirmed owner-supplied save message. Failures keep the owner's dirty state and error message. |
| Same file — `FormErrorSummary` | Named section with question links rendered as Buttons. The owner navigates/focuses the original field. No duplicate validation or field model. |
| `inventory-editor.tsx` | Plain introductory text, unframed section rail beside one Panel, reused PanelFooter/PanelMessage, Back/Continue/Review answers and existing explicit save actions. Section buttons focus the new heading; the native selector retains focus. Error/correction targets retain their own focus path. |
| `review-section.tsx` | Shared error summary, concise validation guidance, section buttons returning to the original answers. Final submit and its confirmation are unchanged. |
| `personal`, `family`, `background`, `health`, `education`, `interests`, `organizations`, `plans`, `review` sections; `fields.tsx`; `psgc-location-selector.tsx` | Field columns follow a named Inventory sheet container instead of viewport width, so a narrow sheet or larger text stacks fields. Action groups wrap. Only layout classes change in the answer sections and field helpers. |
| `tests/ux15-inventory.browser.mjs` | Synthetic local regression suite, automatically discovered by the existing browser-suite runner. No live account or record is used. |

No backend, contract, payload adapter, validation rules, correction map, read-only snapshot,
query ownership, authorization, persistence or navigation-provider source changes.

## Visual evidence

Synthetic Student data only. Baseline screenshots use the original fetched editor;
after screenshots use the pilot. Desktop: 1440×1000; phone: 390×844. Full-page captures
include the existing portal shell. No production service was contacted.

| Screen | Before | After |
| --- | --- | --- |
| Desktop — Personal | [Before](screenshots/before-desktop-personal.png) | [After](screenshots/after-desktop-personal.png) |
| Phone — Personal | [Before](screenshots/before-phone-personal.png) | [After](screenshots/after-phone-personal.png) |
| Desktop — Review | [Before](screenshots/before-desktop-review.png) | [After](screenshots/after-desktop-review.png) |
| Phone — Review | [Before](screenshots/before-phone-review.png) | [After](screenshots/after-phone-review.png) |

## Validation

See [targeted validation results](validation.md) for commands and outcomes.
Screenshots and browser fixtures assess presentation and client behavior. They are not
GCO UAT, a manual screen-reader audit, or approval to roll out the design.

At 320px with 200% root text size, the existing global top-bar controls extend beyond the
viewport. This pilot leaves that shell source unchanged. Enlarged-text tests therefore check
the Inventory form's own reflow; default-text tests still require no whole-page horizontal
overflow at desktop, 390px and 320px. Treat the top bar as a separate accessibility follow-up.

## Later adoption candidates

1. **Exit Interview:** error summary first; consider section navigation only after a focused
   instrument and correction-path audit.
2. **Graduate Tracer:** navigation presentation, error summary and persistent manual-save
   feedback, preserving anchor navigation and uncertain-outcome recovery.
3. **Routine Student Intake:** persistent save feedback and clearer review actions without
   adding a mandatory wizard.
4. **Counselor Evaluation / Assessment Records:** focused professional save/error presentation;
   preserve confidential ownership and distinct finalization.
5. **Feedback / CSM:** error-summary presentation where useful, keeping short survey layout and
   final idempotent submission; no invented persistent drafts.

Adoption requires a separate scoped change and team review. Keep this PR draft; do not merge
or deploy it as part of the pilot.
