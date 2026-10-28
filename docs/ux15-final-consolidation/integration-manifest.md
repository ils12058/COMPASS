# UX15 Integration Manifest

## Verified refs and topology

Fetched on 2026-10-22. The audit worktree was created from the exact current integration ref.

| Ref | SHA |
| --- | --- |
| `origin/integration/ux15-modernization` | `f200e106d46474508c9efb69826e2e1948949d90` |
| `origin/staging` | `0a843dae20c01984d0fb9aa46d5eef34102ab386` |
| `origin/main` | `1a9933535a0b8c0cbd7764c35f301e8402f48375` |
| `merge-base(staging, integration)` | `0a843dae20c01984d0fb9aa46d5eef34102ab386` |

`git rev-list --left-right --count origin/staging...origin/integration/ux15-modernization`
returned `0 18`: staging has no unique commits relative to the integration branch's merge base;
integration is 18 commits ahead. No merge conflict or independent staging divergence was found.
The final consolidation source branch was created at `f200e106`; the fetched integration ref was
not modified during the audit.

## Merged UX15 PR inventory

GitHub PR metadata and the local first-parent topology were both checked. Each PR is merged to the
dedicated integration branch.

| PR | Slice and owning area | GitHub merged commit | Implementation, tests, and audit record |
| --- | --- | --- | --- |
| [#297](https://github.com/ils12058/COMPASS/pull/297) | Individual Inventory pilot / form foundation | `f7e2e8c3b3d4fac57e294ae1452be54b93957cf0` | `fe/src/features/inventory/editor/`, `fe/src/components/ui/form-experience.tsx`; `ux15-inventory.browser.mjs`; `docs/ux15-pilot/` |
| [#298](https://github.com/ils12058/COMPASS/pull/298) | Exit Interview | `132be02d69316d8456b0a244704c0a9f263d1e13` | `fe/src/features/exit-interviews/`; `ux15-exit-interview.browser.mjs`; `docs/ux15-exit-interview/` |
| [#299](https://github.com/ils12058/COMPASS/pull/299) | Graduate Tracer | `c5f1bb2bdd37fd98eb640d563553b425771cd140` | `fe/src/features/graduate-tracer/`; `ux15-graduate-tracer.browser.mjs`; `docs/ux15-graduate-tracer/` |
| [#300](https://github.com/ils12058/COMPASS/pull/300) | Counselor Evaluation | `f74ee48da7191e1a2a3f0e7ba5bc4e0127655870` | `fe/src/features/routine-interviews/routine-counselor-evaluation.tsx`; `ux15-counselor-evaluation.browser.mjs`; `docs/ux15-counselor-evaluation/` |
| [#301](https://github.com/ils12058/COMPASS/pull/301) | Routine Student Intake | `a4c8bed349e0a7e774f8a6bde3bb805fb0168543` | `fe/src/features/routine-interviews/routine-student-intake.tsx`; `ux15-routine-intake.browser.mjs`; `docs/ux15-routine-intake/` |
| [#302](https://github.com/ils12058/COMPASS/pull/302) | Customer Feedback and CSM | `757eb933786b8067724394c365d3a760279a1627` | `fe/src/features/feedback/`; `ux15-feedback-csm.browser.mjs`; `docs/ux15-feedback-csm/` |
| [#303](https://github.com/ils12058/COMPASS/pull/303) | Unified forms consistency and selective hardening | `af171d2a41fb1dab4d83b04fc9c285cec6365ce8` | `form-experience.tsx`, Inventory/Exit/Evaluation presentations; `ux15-consolidation.browser.mjs`; `docs/ux15-consolidation-1/` |
| [#304](https://github.com/ils12058/COMPASS/pull/304) | Portal Shell accessibility and reflow | `613525bf9c7ed41dca8869fd717b5baf360f2f70` | Portal Shell, Account Menu, Accessibility Control, Command Palette; `portal-shell-accessibility.browser.mjs`; `docs/ux15-accessibility-1/` |
| [#305](https://github.com/ils12058/COMPASS/pull/305) | Student Home | `0aa6de7ff8f26c8afd6531a8b2d7d87e52869ef4` | `fe/src/features/portal/home/student-home*` and Overview presentation; `ux15-student-home.browser.mjs`; `docs/ux15-home-1/` |
| [#306](https://github.com/ils12058/COMPASS/pull/306) | Intake/Feedback submission recovery and Inventory reflow | `1d8dcd3eb413955718904c1acb8e0b87d8766053` | `routine-student-intake.tsx`, Feedback forms, Inventory editor; form browser suites; `docs/ux15-hardening-1/` |
| [#307](https://github.com/ils12058/COMPASS/pull/307) | Counselor and Head Guidance Counselor Home | `217e1677bd78dc53640b6fb5c49e892e3ec1f734` | `counselor-home*`, `portal-home.tsx`, `overview-work.ts`; Counselor and Student Home suites; `docs/ux15-home-2/` |
| [#308](https://github.com/ils12058/COMPASS/pull/308) | Guidance Services Staff Home | `f200e106d46474508c9efb69826e2e1948949d90` | `gss-home*`, `portal-home.tsx`, `overview-work.ts`; GSS/Work Queue/Guidance Operations suites; `docs/ux15-home-3/` |

## Integrated ownership and shared dependencies

| Domain | Production locations | Canonical contracts and shared dependencies |
| --- | --- | --- |
| Form presentation | `fe/src/components/ui/form-experience.tsx`; form-specific feature files above | Shared Panel, Button, Input, Select, Textarea, `form-safety/`, generated OpenAPI clients. The shared form component owns presentation only. |
| Portal shell | `fe/src/features/portal/components/portal-shell.tsx`, `portal-command-palette.tsx`, `fe/src/features/accessibility/accessibility-control.tsx`, `fe/src/features/account/components/account-menu.tsx` | Existing dialog/menu primitives, current `PortalSession`, route and capability helpers. |
| Student Home | `student-home.tsx`, `student-home-attention.tsx`, `student-home-presentation.ts` | Canonical Student Actions, existing Overview summary and announcements, role/lifecycle access helpers. |
| Counselor Home | `counselor-home.tsx`, `counselor-home-presentation.ts` | Canonical Work Queue, authorized self Appointment list, current workspace projection, Overview summary and announcements. |
| GSS Home | `gss-home.tsx`, `gss-home-presentation.ts` | Canonical Work Queue, existing scoped Guidance Operations response, managed Appointment projection and `portalWorkspaceGroups`. |
| Other roles | `portal-home.tsx`, existing Overview components | Existing summary, queue, role context, announcements, and no UX15-specific override for IT Admin or Institutional Officer. |

## Complete staging-to-integration change inventory

The authoritative local `git diff origin/staging...origin/integration/ux15-modernization` includes
385 paths:

- **40 frontend source/config:** form experience and six form areas; Portal Shell, account and
  accessibility controls; Student/Counselor/GSS Home compositions and presentation; one
  `fe/package.json` script change.
- **24 tests/support files:** seven form browser suites, form/home unit tests, three Home browser
  suites, shared Portal Shell suite, fixture helpers, and an existing Routine Interview test
  update.
- **57 Markdown files, 26 JSON evidence files, and 238 screenshot/visual evidence files** under
  the twelve slice documentation directories.
- **No backend, contract, generated API, migration, workflow, deployment, or environment-example
  changes.** The API contract is identical between staging and integration.

The consolidation PR itself adds the audit documents in this directory and changes only
`fe/tests/ux15-gss-home.browser.mjs`. No generated client output is committed.

## Merge integrity

All twelve merge commits are reachable from the current integration HEAD in PR order. The local
tree on the audit branch began clean and at the fetched integration SHA; test/build-generated
`fe/next-env.d.ts` changes are discarded before handoff. The source checkout's untracked files are
outside this worktree and were left untouched.
