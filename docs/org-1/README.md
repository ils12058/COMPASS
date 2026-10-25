# ORG-1 — Database catalog authority and persisted academic policy

Implemented against integration `e7db50e0b23dd21a7ff7ec44c9d08708eb24ee12` (ORG-0 PR #326).
Branch: `feature/org-1-database-catalog-authority`. Date: 2026-10-25 (Asia/Manila).
Engineering foundation only: no deployed migration, institutional editing, policy approval or grants.

Program now persists classification, policy status and nullable Year Levels. A frozen additive
backfill preserves existing identities/history, and explicit initialization/adoption replaces the
old destructive reconciler. Live Organization, Inventory and Good Moral readers use database policy.
The initial baseline remains 6 Campuses / 10 academic units / 38 Programs; those are seed counts,
not live limits. Existing pending/unknown policy compatibility and F4 Years 1–4 stay intact.

| Document | Evidence / purpose |
|---|---|
| [Catalog authority](catalog-authority.md) | Single database authority; receipt; retired writers |
| [Program policy](program-policy.md) | Fields, allowed states, Python and PostgreSQL checks |
| [Migration/backfill](migration-and-backfill.md) | Frozen map; populated upgrade and preservation |
| [Bootstrap/seeder](bootstrap-and-seeder.md) | Commands, explicit adoption, deployment and repeats |
| [Consumer conversion](consumer-conversion.md) | All live metadata readers and remaining seed references |
| [Cross-domain compatibility](cross-domain-compatibility.md) | Routing, history and reference/selection boundaries |
| [Deployment/recovery](deployment-and-recovery.md) | Actual activation blockers and compatible rollback |
| [ORG-2 handoff](org-2-handoff.md) | Next backend slice; authority/concurrency/release boundaries |
| [Validation](validation.md) | Exact commands, distinct cases, failures/fixes and limitations |

The [new ADR](../../be/docs/decisions/ADR-ORG-1-database-owned-organization-catalog.md) supersedes
ADR-064 engineering ownership while retaining its historical text. ORG-0 remains the original audit,
not retroactively rewritten as implemented behavior.

ORG-2 can build on the persisted model/accessor/initializer after review. It must implement catalog
mutations, authority, recent MFA, Audit, versions and transactional dependency checks; none is active
here. D1/D2/D8/D19 and other institutional choices remain rollout gates. The ORG-1 migration is
intentionally not routine-deployment allowlisted. A merged PR is not cutover permission.

Implementation SHA, final PR/check state and clean-worktree status are reported in the PR/agent
handoff; this document does not embed a self-referential commit hash.
