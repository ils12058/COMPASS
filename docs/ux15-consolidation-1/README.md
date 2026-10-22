# UX15 consolidation 1

Experimental Proposal #15 consistency, accessibility and architecture review, October 22, 2026.
This is a selective hardening slice for review, not production or institutional acceptance.

Result: 85 focused Node/component tests and 332 distinct browser cases passed (166 each in
Chromium/WebKit), plus lint, typecheck, API generation, production build and whitespace checks.
The source correction is eight class-name changes across five files. Three synthetic screenshot
pairs and the deferred header-overflow capture accompany the audit.

## Source verification

Fetched `origin` with pruning before any implementation. Latest fetched
`integration/ux15-modernization`: **`757eb933786b8067724394c365d3a760279a1627`**.
Created the isolated `ux15-forms-consolidation/COMPASS` worktree at that exact commit, then
`feat/ux15-forms-consolidation`. The original `staging` checkout and its local files were left alone.

GitHub PR metadata confirms all six pilots merged to the integration branch; all their merge
commits are in the fetched integration history:

| Experience | PR | Merge commit |
| --- | --- | --- |
| Individual Inventory | [297](https://github.com/ils12058/COMPASS/pull/297) | `f7e2e8c3b3d4fac57e294ae1452be54b93957cf0` |
| Exit Interview | [298](https://github.com/ils12058/COMPASS/pull/298) | `132be02d69316d8456b0a244704c0a9f263d1e13` |
| Graduate Tracer | [299](https://github.com/ils12058/COMPASS/pull/299) | `c5f1bb2bdd37fd98eb640d563553b425771cd140` |
| Counselor Evaluation | [300](https://github.com/ils12058/COMPASS/pull/300) | `f74ee48da7191e1a2a3f0e7ba5bc4e0127655870` |
| Routine Student Intake | [301](https://github.com/ils12058/COMPASS/pull/301) | `a4c8bed349e0a7e774f8a6bde3bb805fb0168543` |
| Customer Feedback and CSM | [302](https://github.com/ils12058/COMPASS/pull/302) | `757eb933786b8067724394c365d3a760279a1627` |

Reviewed each pilot's README, validation and screenshot index (Inventory embeds its index in its
README), plus Inventory's integration-safety document. These are historical baseline evidence;
this slice's executed checks are recorded separately in [validation.md](validation.md).

## Architecture assessment

All seven actual editors and their parent editability/read-only boundaries were inspected:
Inventory's editor/field helpers and section composition; Exit Interview's form/sections and
correction paths; Tracer's form, field helpers, repeating and conditional sections; both Routine
Interview editors; and the separate Customer Feedback and CSM forms.

The shared presentation surface is appropriately small:

- `fe/src/components/ui/form-experience.tsx`: `FormSectionNavigation`, `FormSectionLinks`,
  `FormSaveStatus`, `FormErrorSummary`.
- `fe/src/components/ui/panel.tsx`, `page-header.tsx`, `button.tsx`, `notice.tsx`,
  shared native inputs and `consequential-action-dialog.tsx`, including the dialog return-focus hook.
- `fe/src/features/feedback/feedback-shared.tsx`: `FeedbackSection`, `FeedbackRadioGroup`,
  field labels, known-code errors and opportunity handling.
- `fe/src/features/form-safety/`: dirty registration, guarded links, provider-owned history and
  unload protection. Existing query/transport ownership remains authoritative.

Navigation, save-status and error-summary components do not own values, persistence, validation,
eligibility or submission. `FeedbackSection` adapts stable institutional group headings to
`PanelSection`; `FeedbackRadioGroup` shares native choice presentation within that domain.
Neither is a universal questionnaire engine.

The similar focus callbacks have different destinations: Inventory may mount another selected
section; continuous forms focus a heading, named section, field or matrix choice. Combining these
would obscure meaningful behavior for little maintenance benefit. The two feedback submission
handlers also retain separate request bodies, conditional branches and intent state. They were
assessed, not extracted merely because they look similar.

## Plan recorded before production-source changes

1. Keep all shared infrastructure and workflow functions unchanged.
2. Increase Inventory checkbox/Boolean and localized sibling/transport choice-label minimums
   from 32–40px to 44px. Increase Exit Interview's 36px checkbox labels to 44px. These are
   inconsistent with the other pilots' choice targets and can be corrected without new controls.
3. Add inherited emergency word wrapping to the existing Evaluation panel. At 320px/200% text,
   the baseline panel has 254px client width but 267px scroll width; viewport-only checks miss it.
4. Reproduce those cases first, then validate the corrected cases and every affected Inventory
   section, followed by existing pilot suites and the final cross-form audit in Chromium/WebKit.
5. Capture only representative new before/after pairs. Track shell and domain-recovery work in
   separate follow-ups. Do not change CI or deployment configuration.

## Intentional differences retained

Inventory already uses unrestricted selected sections, a native mobile selector and explicit
Save & continue. It is not converted to another architecture, nor are progression locks added.
Exit Interview, Tracer, Intake, Customer Feedback and CSM remain continuous documents; the short
Evaluation stays grouped without a section navigator. CSM retains its four groups without a rail.

Persisted drafts and explicit saves remain in their five existing domains. Evaluation's professional
finalization remains separate from saving and from Student submission. The two one-time feedback
forms acquire no draft status or Save Progress. Native feedback validation remains native; summaries
remain only where the domains already supply their own issues. Saved state is backed by loaded
canonical data or a successful canonical save, not navigation or a click.

All official questions, labels, option order/values, conditional requiredness and payload mapping
remain unchanged. Optional feedback identity remains blank; CSM zero remains a valid answer;
Evaluation keeps null and exact 1–10 values. No backend, contract, model, generated-client,
authorization, encryption, visibility, lifecycle, revision, notification or persistence change.

## Assessment and review material

Changed-file inventory:

| Paths | Purpose |
| --- | --- |
| `fe/src/features/inventory/editor/fields.tsx`, `background-section.tsx`, `organizations-section.tsx` | Larger existing checkbox/Boolean/sibling/transport labels. |
| `fe/src/features/exit-interviews/exit-interview-form-sections.tsx` | Larger existing checkbox labels. |
| `fe/src/features/routine-interviews/routine-counselor-evaluation.tsx` | Editable/finalized panel and read-only answer wrapping. |
| `fe/tests/ux15-consolidation.browser.mjs` | Reusable synthetic cross-form audit and focused regressions. |
| `docs/ux15-consolidation-1/` | Six documents, seven PNGs, result inventory and baseline/final metrics. |

The pilots are intentionally related and can retain their domain-specific behavior. The practical
consolidation is a bounded presentation correction and a reusable comparison/verification record,
not another form framework. See [matrix](consistency-matrix.md), [accessibility audit](accessibility-audit.md),
[validation](validation.md), [screenshots](screenshots.md) and [follow-ups](followups.md).

Repository Actions were inspected: targeted frontend/backend PR workflows only match `staging`
and `canon/compass-clean-baseline`; backend-full uses those same push/filtered PR branches.
`deploy-staging.yml` is manual-only and verifies the exact current staging SHA. This PR targets
`integration/ux15-modernization`; local results must not be described as hosted CI approval.
No workflow dispatch, merge, staging/main mutation or deployment is part of this delivery.
External hosting-account webhooks/settings were not inspected.
