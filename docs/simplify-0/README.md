# COMPASS-SIMPLIFY-0

COMPASS is the Guidance and Counseling Management System for the **University of Camarines Norte (UCN)**. This audit recommends smaller interactions and clearer presentation while preserving accountability. It adds documentation only; implementation belongs to subsequent, bounded PRs.

## Verified baseline

| Item | Verified value |
| --- | --- |
| Repository | `ils12058/COMPASS` |
| Fetched base and PR target | `integration/ux15-modernization` |
| Exact audited commit | `0101a5d03c69c6f46fdf6b961a0a2de0ea73a122` — fixed-slot contract/integration validation, PR #334 |
| Audit branch | `audit/simplify-0-product-experience` |
| Isolation | Clean managed worktree created from that exact commit; unrelated primary-checkout changes left untouched |
| Review date | 28 October 2026, Asia/Manila |
| Review method | Three GPT-6 Luna sub-agents, followed by primary-agent source verification and focused synthetic browser inspection |

## Most important findings

1. **Routine Catalog editing carries disproportionate ceremony.** Rename requires a manually written basis, a review dialog, confirmation, and another review/confirmation if recent MFA has expired. Retain MFA and the required wire field initially; simplify a routine rename to an explicit Save, followed by MFA and another deliberate Save only when required.
2. **Required implementation is being mistaken for required policy.** Every Catalog mutation requires `basis`, but acceptable change-basis policy remains explicitly open in ORG-4. Relabel it **Change note** now; evaluate optional notes for routine changes separately from frontend work. Automatic Audit must remain.
3. **Technical facts dominate ordinary Catalog feedback.** Versions appear in editors, review, success, impact and history; history shows actor UUIDs. Keep integrity checks internally and prioritize action, values, time and note. A human actor name requires an authorized backend projection; do not invent one or add Accounts lookups.
4. **Some complexity is already well contained.** Catalog dependency counts and filters are already disclosed; Program level inputs are already conditional; history already maps actions into readable labels. Preserve these patterns. Deactivation blockers, explicit consequential review and uncertain-save reconciliation serve real purposes.
5. **Cross-product cleanup can stay small.** Booking has a duplicated progress cue and an unsent Inventory acknowledgment checkbox despite independent server eligibility checks. Service rows repeat flexible-booking information. Other inspected security, privacy and instrument workflows do not justify blanket removal of review or explanatory text.
6. **The strongest visual opportunity is hierarchy, especially Home on phones.** Historical Student/Counselor renders show many equally framed sections. Catalog uses one Campus panel with divided children, rather than a card for every nested item. Test quieter secondary Home sections and more compact contextual Catalog actions; avoid replacing shared panels indiscriminately.
7. **Converted 3D artwork is not in this baseline.** Four original transparent 2D/chibi PNGs are committed. The primary checkout contains local replacement/untracked 3D files, excluded from this audit's baseline and PR. Plan a restrained asset integration later; keep Lucide for controls.

## Recommendation

Proceed with **SIMPLIFY-1 frontend-only Catalog refinement first**: Change note wording, routine rename Save/MFA continuity, human-readable feedback/history, and clearer Program/impact presentation. Keep required notes, all authorization and MFA checks, versions, Audit, dependency enforcement, deliberate post-security submission and conservative reconciliation.

Treat note-requiredness and safe actor-name enrichment as independent backend-dependent options. They must not delay safe cosmetic work or quietly enter its scope. Follow with bounded SIMPLIFY-2 layout/artwork work and SIMPLIFY-3 booking/copy cleanup. [The plan](implementation-plan.md) gives ownership and acceptance checks; [the findings](experience-audit.md) distinguish essential protection, exposed complexity, interaction friction and policy questions; [design direction](design-direction.md) defines presentation choices.

COMPASS should help students and Guidance Office staff complete their work. Catalog settings record the academic context needed by Inventory, Good Moral, routing and reporting; they do not authorize an ERP, SIS, Registrar platform, SAR implementation or institutional approval subsystem.

## Evidence, validation and limits

- Read active source and the UI/copy/density guides, ADR-090/091 and relevant later frontend/security/privacy decisions, ORG-0–4, UX15 Home/final consolidation and recent service UX evidence. Historical design intent is distinguished from current source and unresolved policy.
- Ran **10/10 selected existing Chromium Catalog checks**: 23, 25, 28–30, 34–37 and 49. They cover raw history identity, stale edits, explicit post-MFA submission, interrupted-save reconciliation, saved-but-refresh-failed recovery, dialog focus, 320px form containment, enlarged root text, relationship navigation and 1024px impact containment.
- Ran **2/2 additional synthetic capture checks** for current 1440px desktop hierarchy/rename and 390px phone hierarchy. Inspected these PNGs plus the 320px form, expanded impact and enlarged-text confirmation. Artifacts are local under `/tmp/compass-simplify-0-browser/`; they are temporary and not part of the PR. Historical UX15 Home screenshots are separately linked in the design document.
- Reproduce the selected checks against a local fixture-only frontend with `COMPASS_UI_BASE_URL=http://127.0.0.1:3128 COMPASS_UI_ARTIFACTS=/tmp/compass-simplify-0-browser COMPASS_UI_CHECK='^(23 |25 |28 |29 |30 |34 |35 |36 |37 |49 )' node tests/organization-catalog.browser.mjs` from `fe/`. The test harness intercepts API traffic and blocks external destinations; no backend was connected. Local client generation from the unchanged OpenAPI was a disposable browser prerequisite, excluded from the diff.
- Checked Markdown links/source anchors, institution-name consistency, whitespace and the exact four-file documentation diff. No full test suite, build, backend integration test or new institutional requirement was needed for this audit.
- Browser checks establish fixture behavior and rendered containment, not real backend correctness, task-completion usability, native browser zoom, screen-reader acceptance, physical-device behavior or UCN UAT. Current renders outside Catalog and large real-world Catalog scale remain unverified. Home density recommendations remain proposals informed by historical renders and current source.
- ORG-4's [final assessment](../org-4/final-assessment.md) records synthetic assurance separately from blocked staging readiness, unexecuted UAT and unauthorized activation. That historical assessment is not a fresh operational-status check or authorization.

No runtime source, assets, migrations, OpenAPI, grants, security policy or feature flags changed. No deployment, SSH, live database access, real student/counseling data inspection, merge, or change to `staging` or `main` occurred.
