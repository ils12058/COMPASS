# ORG-3 — Organization Catalog management

Implemented on fetched integration `f9e6fb4a99ed3bdc72f7b594752a141d6ac48edd`, in an isolated
`feature/org-3-catalog-management-ux` worktree. PR target: `integration/ux15-modernization`.
Date: 2026-10-26 (Asia/Manila). The final implementation SHA and hosted-check state belong in the
PR/handoff rather than a self-referential commit hash here.

The existing Organization Structure workspace now supports official Campus, College and Program
creation, rename, status, full academic policy, deactivation impact and restricted change history.
All sixteen ORG-2 operations use generated clients. Campus panels, College rows and indented Program
rows remain; there is no second Catalog application or new top-level entity destination.

Catalog management requires an eligible staff identity, `organization.structure.view` and explicit
`organization.catalog.manage`. Operational tabs and their routes separately require the existing
`organization.manage`. Eligible staff reference readers can browse Structure without editing;
Students' selector reads never expose this standalone workspace. Backend checks remain final.

This is frontend source delivery and synthetic verification. No actual capability grant or policy
activation occurred. Deployment, real catalog state, approved delegates, institutional policy and
old-writer retirement remain unverified. ORG-1 migration/cutover restrictions are intact.

| Document | Scope |
|---|---|
| [Workspace](catalog-workspace.md) | Hierarchy, search, filters, navigation and reference viewers |
| [Forms](catalog-forms.md) | Fixed identities, policy sets and deliberate review |
| [Deactivation/history](deactivation-and-history.md) | Actual aggregate impact, blockers and safe target history |
| [Authority/MFA](authorization-and-step-up.md) | Independent access and shared authenticator flows |
| [State/recovery](frontend-state-and-recovery.md) | Versions, uncertain outcomes, cache and draft ownership |
| [Accessibility](accessibility-and-responsive.md) | Keyboard, focus, layout evidence and limits |
| [ORG-4 handoff](org-4-handoff.md) | Combined authenticated verification and release gates |
| [Validation](validation.md) | Commands, distinct results, corrections and environment |

ORG-4 can now validate the combined source with real authenticated local browser/API/PostgreSQL
workflows. Synthetic browser evidence does not establish institutional UAT or operational readiness.
Stop after opening one focused PR; no automatic merge or deployment.
