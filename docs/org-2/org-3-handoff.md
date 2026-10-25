# ORG-3 — Existing Organization Structure workspace

Build on the actual [16 protected operations](api-and-contracts.md), not archived editors or guessed
CRUD. Extend `fe/src/features/organization/structure/organization-structure-page.tsx` and adjacent
bounded components; keep the existing Organization navigation and relationship tabs. Student
Affiliation remains its current operational model/workspace, without SAR migration or automatic
placement. Backend remains authoritative for every permission, status, policy and dependency.

| Concern | Required frontend behavior |
|---|---|
| Entry | Explicit catalog manage plus structure view can enter Structure without organization.manage; relationship tabs still require their existing authority; do not expose the management workspace to selector-only Students |
| Read-only viewers | Existing authorized relationship managers can browse; no fabricated editing rights from role/Head/organization.manage |
| Hierarchy | Retain Campus/College/Program identity/code/status and correct parent context; list/detail remains inactive-inclusive |
| Create | Explicit code/name/status/parent; explain immutable identity, parent conflicts and inactive draft policy |
| Rename | Focused name form, stable read-only code/parent, bounded basis, required current version |
| Policy editor | Complete nullable classification/status/level set; no inferred levels; show actual noncontiguous values rather than first–last range |
| Incomplete Program | Inactive draft; explain activation is blocked pending configured policy/institutional decisions; no fabricated approval checkbox |
| Retirement | Fetch fresh impact, show typed blockers/warnings and preserved history; explicit named consequence/confirmation; no automatic cascade or reassignment |
| Reactivation | Explicit target/version, parent and Program policy checks; do not imply children or stale relationships were restored |
| Policy conflict | Explain pending F4/institutional decision refusal without offering cancellation, override or fake approval |
| Recent MFA | Shared StepUpDialog for setup/verify; preserve safe local input; reload target/version/impact, require deliberate review/resubmission; never blindly replay |
| Stale version | Preserve input separately, load current record, compare and require a new confirmation; failed reload keeps consequential actions unavailable |
| Uncertain transport outcome | Re-read target/history before new action; no automatic arbitrary retry or claimed success |
| History | Target-specific items/page/page_size/has_next; actor UUID as returned; do not fetch global Audit/Accounts solely to enrich names |
| Success/refresh | Wait for confirmed response, refresh affected target/parents/impact/history only; report saved-but-refresh-failed accurately |

Use fe/AGENTS.md primitives: PageHeader/PageAction, Panel, shared form/error fields, ContextHelp and
ConsequentialActionDialog. No new top-level Catalog app, server-state framework, broad UI rewrite or
confidential record links from aggregate counts. Any remediation link must honor its own capability.

Browser acceptance must cover authorized synthetic managers and read-only roles, missing/revoked
capability, incomplete ancestry/policy, duplicate code, strict versions, stale preview, Audit failure,
MFA setup/verify, refresh/network failure and deliberate resubmission. Verify focus entry/return,
Escape/cancel, labels and error announcements, keyboard-only, screen reader, narrow phone layout,
long names/codes and 200% text/zoom. No ORG-2 UI has been built or manually accessibility-reviewed.
Synthetic browser success does not approve institutional policy/delegation or operational rollout.
