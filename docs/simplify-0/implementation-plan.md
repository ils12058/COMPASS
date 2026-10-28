# Bounded implementation plan

Implement safe presentation changes first. Keep backend/policy-dependent options separate, so reducing bureaucracy does not require a new approval framework. All slices target `integration/ux15-modernization` through independently reviewable PRs; none authorizes deployment, grants, activation or merge.

## SIMPLIFY-1 — Organization Catalog

Prefer two small frontend PRs rather than one broad Catalog redesign.

| PR | Boundary and likely source ownership | Acceptance evidence |
| --- | --- | --- |
| 1A — Copy and information hierarchy | `fe/src/features/organization/structure/catalog/{catalog-editor.tsx,catalog-model.ts,catalog-errors.ts,catalog-review.tsx,catalog-history.tsx,catalog-impact.tsx,catalog-policy-fields.tsx}`. Change note label/helper, human success/recovery text, de-emphasized versions/UUIDs, current/proposed values first, clearer Program configuration. | Required basis and exact mutation payload unchanged. History still has action, date, before/after, note, pagination and safe missing-identity treatment. Blockers, warnings and access consequences remain at decision. No false success on unknown outcome. |
| 1B — Routine Save and contextual editing | `catalog-editor.tsx`, `catalog-query.ts`, `catalog-actions.tsx`, `organization-structure-page.tsx` and existing shared dialog/menu/step-up primitives only where needed. Routine rename uses direct deliberate Save with inline comparison; improve selected-record action proximity and reduce repeated context. | Existing authority, session, CSRF, MFA, expected-version and no-retry behavior retained. Create/status/policy keep consequential review. Fresh data never silently changes an expected version and sends a write. Focus returns to real opener or heading; one active editor, no competing mutation. |

### Smallest safe routine rename sequence

1. Open Rename; keep current/proposed name and linked-label consequence readable. Keep required Change note at first.
2. Person presses **Save**. Refresh current session/authority and target; validate the draft against the version the person reviewed. Build an explicit command only after those checks pass. A fresh record differing from the reviewed version stops submission and presents a comparison for deliberate review; it does not silently rebase the write.
3. Send one existing rename mutation. The server remains the authority for authorization, recent MFA, version and transaction/Audit integrity.
4. If recent MFA is required, preserve input and open the existing StepUpDialog. Verify, re-read authority/target (and impact for any future applicable flow), then return to an unsent proposal. **Wait for another explicit Save.** The verification callback cannot submit or retain an executable command for replay.
5. If MFA setup is required, keep the existing Account Security setup/return route. If authority/account/session changes, disable or clear the protected draft as today. If refresh fails, saving remains unavailable.
6. Confirm success from the authoritative response or conservative detail/history reconciliation. On uncertainty, block another write and offer read-only status checking. Refresh failure after confirmed save is a distinct read failure.

No new API preflight, feature flag, session cache, persistent draft or MFA policy is needed. The existing `authGetMfaStatus`/session hints may help presentation but never authorize a mutation and are not required for this sequence. This replaces redundant interaction around MFA; it preserves the MFA control. For creation with immutable code/parent, activation/deactivation and eligibility-affecting Program settings, retain one meaningful current-state review and explicit action-specific confirmation, refreshed again after security transitions.

### Optional backend-dependent work: outside 1A/1B

| Option | Actual ownership/dependency | Required boundary |
| --- | --- | --- |
| Relax universal note requiredness | `be/compass/organization/{api.py,catalog_services.py}`, Catalog Audit/history serialization, `contracts/openapi.json`, generated FE models/operations, `catalog-model.ts`, `catalog-query.ts` and relevant tests. | Catalog owner decides whether automatic Audit alone, optional routine notes, or selected required reasons are appropriate. Preserve historical basis text and actor/time/change evidence. Design old-client compatibility and canonical blank/null handling; reconciliation currently matches basis exactly. No synthetic note or silent backend bypass. |
| Resolve actor display names safely | Catalog history response/service projection, account privacy/scope policy and generated contract. Current response supplies only `actor_id`. | A Catalog-only manager must not acquire Accounts/global Audit access. Define allowed current/historical name behavior and unavailable/deactivated identity fallback. Until then, omit the raw UUID in ordinary presentation without claiming a person's name or role. |

Neither option is necessary for the core simplification. This audit does not prescribe a migration or create additional management processes. Changes to MFA requirements, Catalog blockers, identity/parent immutability, pending Program handling or Good Moral eligibility are excluded from SIMPLIFY-1.

## SIMPLIFY-2 — Layout, role focus and illustration

Start with one Home composition pilot and compare current desktop/phone rendering. Likely owners: `fe/src/features/portal/home/{student-home.tsx,student-home-attention.tsx,counselor-home.tsx,gss-home.tsx,overview-summary.tsx,overview-announcements.tsx}` and their presentation helpers. Keep canonical work order and authorization-derived shortcuts; HGC oversight remains a designation/capability composition, not a new privileged role.

Use a dominant work list with quieter supporting links/metrics/announcements. Preserve headings, data and useful entry points. Change feature composition first; shared `Panel`, `PanelSection`, `PageHeader`, `FloatingListTools` and navigation tokens stay intact unless the pilot demonstrates a shared defect. Do not globally remove containers or duplicate navigation into a new hub.

A separate bounded asset PR can integrate the owner's actual 3D conversions after they are available to that branch. Owners: `fe/public/illustrations/`, `fe/src/features/public/home/public-hero.tsx`, `fe/src/features/public/shared/public-page-header.tsx`, selected Home/empty-state consumers. Preserve proportions/alpha, review visible quality at actual sizes, optimize delivery, use width/height to avoid layout shift and check mobile/text wrapping. Keep Lucide for operational controls and all sensitive records free of decorative characters. Update the narrow illustration-placement guidance in `fe/AGENTS.md` / `fe/docs/ui-guidelines.md` to express this brief's selected Home/empty-state direction; do not treat historical public-only restrictions as evidence that conversions are already integrated.

No backend, eligibility, scope or policy change is needed for those presentation choices. Do not add images to every module, generate new artwork, redesign branding or introduce an illustration/component subsystem.

## SIMPLIFY-3 — Copy and selected interaction cleanup

Use one small booking/service PR first: `fe/src/features/appointments/appointment-booking-page.tsx` and `fe/src/features/services/services-list-page.tsx` plus feature presentation helpers/tests. Remove the duplicate booking roadmap and unsent Inventory acknowledgment checkbox. Keep prerequisite explanation, server eligibility, final appointment details, slot recheck and same-intent idempotent recovery. Merge service booking metadata while preserving supported-versus-enabled pathways and duration.

Then apply the high-impact copy register to demonstrated producers only. `fe/docs/user-copy-guide.md`, feature error maps and existing shared presentation helpers own vocabulary; avoid a parallel string registry or hundreds of incidental replacements. Follow-Up, privacy, account access and institutional instruments showed meaningful consequences in the sample, so they are not default candidates for fewer confirmations.

Do not rewrite consent, Privacy Notices, controlled Inventory/Exit/Tracer/Routine/Feedback questions, certificate/receipt language, saved snapshots, user-authored content or technical operator diagnostics whose detail is useful. A generic shorter message must never collapse denied, stale, uncertain, rejected and confirmed states.

## Focused validation

| Change | Checks to run when implemented |
| --- | --- |
| Catalog wording/presentation | Existing Catalog component/source checks adjusted for meaning; targeted browser cases for create/rename/policy/status/history, long names and unavailable identities. Preserve role/capability negative cases and target-specific history. |
| Routine Save/MFA | Assert request counts and state transitions: one attempt per deliberate Save; no write from MFA callback; stale-before-save stops; stale-on-write preserves input; account/session/capability change clears/disables draft; failed refresh blocks; double click cannot duplicate; setup/verify paths remain distinct. Exercise interrupted committed rename/create and unmatched history without replay, plus success with failed refresh. |
| Program and impact | Exact noncontiguous levels, pending/null semantics, active incomplete refusal, pending F4 refusal, inactive ancestry, fresh preview and changed blockers at commit. Preserve aggregate-only counts and authorized remediation links. Backend policy checks change only if a separately scoped contract PR exists. |
| Home/artwork | Fresh Student/Counselor/HGC/GSS/IT-capability renders at 1440/1024 and 320/390 px, headings/reading order, icon names, touch targets, keyboard/focus, images/alt/layout shift. Compare before/after task prominence; no hidden authorized destinations. |
| Booking/service cleanup | Book without checkbox; server still refuses missing current Inventory; preserve unavailable-Inventory/configuration error path, taken slot, flexible/fixed/group distinctions, same-intent idempotency, uncertain retry and final confirmed schedule. |

Use existing synthetic fixtures with no real student/counseling data. Run affected tests and repository-required checks for each future runtime PR, not the whole product suite by habit. Native zoom, screen reader and physical-device review remain human verification work; enlarged root text is not native zoom. No fixture result supplies institutional acceptance or deployment authority.

## Order, risks and exclusions

Suggested order: **1A → 1B → 2 Home pilot → 3 booking/service cleanup**. The later 3D asset PR and optional note/actor contract work can proceed independently when their real dependencies are ready. Keep the three slice names for tracking; use smaller PRs where state-machine changes warrant separate review.

Main risks are accidental MFA replay, a silently substituted version, loss of uncertain-save lockout, treating missing identity as a known role/name, confusing configured with active booking pathways, and hiding material consequences while shortening copy. Retain boundary tests and independently review those transitions.

ORG-4 D4/D7–D11 and other existing operational decisions remain unresolved where applicable; do not create new approval gates for ordinary cosmetic work. Catalog ownership/grants, migration/deployment readiness and UCN UAT are separate from this roadmap. No SAR, ERP/SIS/Registrar expansion, permission changes, new approvals, database migration, OpenAPI change, security-policy change, runtime feature flag, deployment or automatic merge is part of SIMPLIFY-0.
