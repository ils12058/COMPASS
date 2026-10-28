# SIMPLIFY-3A — audit register (in progress)

Baseline: `integration/ux15-modernization` at `4bfc1b4185c46cff2a40598f071bad1f2e40168e`, fetched 29 October 2026. This is a starting register, **not a completed application audit or closure matrix**. The SIMPLIFY-2A and UX15 reports are useful prior evidence but do not establish complete route, role, state or device coverage.

## Inventory and how to use it

- [Route inventory](routes.csv) enumerates every current `fe/src/app/**/page.tsx`, including route groups and dynamic segments, and links each entry to the feature modules imported directly by the route. `workspace` is the Next route group, not an authorization claim. `pageSheetWidth` is only an entry-file hint; a feature or nested layout can impose other geometry. Routes that redirect are marked as such. Roles, tasks, states and final dispositions are deliberately unassessed until verified against the owning feature, capability rules and rendered behavior. A dynamic pattern is one entry, not evidence for every record or role variant.
- [Shared UI inventory](components.csv) lists all source-owned files immediately under `src/components/ui`, with their direct source consumers. It does not enumerate every feature-local component, transitive consumer, re-export, or dynamically referenced component. Each remains pending inspection in context.
- Reproduce the source inventory with `python3 docs/simplify-3a/inventory.py`. It overwrites the CSVs; record reviewed findings separately instead of treating the script as a visual or authorization audit. The inventory excludes non-page entry points such as `not-found.tsx`, `error.tsx`, route handlers and layouts, which need a separate review.

The initial scan found 130 page entry files and 35 shared UI files. It does not prove every user-visible state is represented. An audit is complete only after each route's actual role/capability variants, primary task, relevant states and evidence are recorded, each shared and feature-level component is examined in its consumers, and uninspectable items remain explicitly open.

## Starting findings and ownership

| ID | Evidence | Finding and root cause | Treatment / disposition |
| --- | --- | --- | --- |
| S3-001 | [Prior synthetic booking render, 1440px](../simplify-2c/screenshots/after-booking-1440.png); current `student-booking-pathways.tsx` and `appointment-booking-page.tsx` | A full-width panel with three vertically stacked explanations places service selection below substantial secondary orientation. The existing illustration sits within that panel. This is a rendered observation at one synthetic viewport and a current source inspection, not proof of other viewports or users. | High priority; Student booking slice. Recompose pathways around the active task and validate all three access/availability states, keyboard and booking recovery. Pending. |
| S3-002 | `fe/AGENTS.md` §15, `src/styles/public-fonts.ts`, public route layout | Caveat is loaded only for public routes and explicitly restricted to the landing hero. Extending it requires a deliberate pattern and changed font-loading boundary, not a class on authenticated pages. | Design-system slice: prototype a restrained, readable accent and seek design review through its PR; retain Outfit for functional headings. Pending; no broader typography approval inferred from a screenshot. |
| S3-003 | [SIMPLIFY-2A product assessment](../simplify-2a/product-experience-assessment.md), [UX15 final audit](../ux15-final-consolidation/README.md) | Prior synthetic visual sampling does not cover every route, role or state. The current source inventory exposes the missing evidence rather than assuming previous completion. | Audit slice: obtain synthetic rendered and interaction evidence per route and distinct access/state variant; explicitly mark unavailable fixtures. Pending. |

No other route or component has been declared visually verified by this initial scan. The prior image uses synthetic data; it is not authenticated production, physical-device, screen-reader, or institutional UAT evidence. Do not infer actual availability of fixed slots or group activities from the presence of their navigation.

## Proposed slices and gates

1. Complete this audit: map route access to actual capability checks and task/state variants; inspect all shared UI files in real consumers; add a prioritized issue register and screenshot/interaction evidence. Keep inaccessible and untested entries visible with blockers.
2. Shared foundation: address repeated verified root causes and review the typography prototype. Keep collection, form, detail, queue, configuration and live-workspace archetypes distinct.
3. Student journeys: start with booking composition while preserving the existing slot, eligibility, idempotency and recovery flows.
4. Guidance and Counseling workspaces: preserve confidentiality, consent, live-call continuity and lifecycle safeguards.
5. Administrative workspaces: preserve capability and recent-MFA boundaries and dense records.
6. Final cross-role pass: recheck every route and relevant state at the requested responsive/accessibility settings, reconcile each issue and document UAT limitations.

Each implementation slice must fetch and revalidate the latest integration base, own bounded files, carry focused tests and before/after evidence, and disclose any unverified behavior. This initial register is not authorization to change backend contracts or to deploy, merge into staging, or modify main.
