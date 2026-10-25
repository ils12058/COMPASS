# ORG-2 — Protected catalog mutations

Engineering implementation on integration `077d98a29855f9822599c938d81cb6b5d7102684`, verified
against the fetched remote before creating the isolated worktree. Branch:
`feature/org-2-catalog-crud-integrity`. Date: 2026-10-25 (Asia/Manila).

Database-owned Campus, College and Program definitions now have focused creation, official rename,
active-state and complete Program-policy operations, positive resource versions, restricted change
history and aggregate retirement impact. Protected services enforce current delegated authority,
server-established recent MFA, synchronous Audit and a cooperative PostgreSQL integrity gate.
No code/parent edit, delete, transfer, merger, SAR, affiliation migration or management UI is added.

No role or designation receives `organization.catalog.manage` automatically. The technical eligible
role fence is IT_ADMIN / COUNSELOR / GUIDANCE_SERVICES_STAFF; it does not approve institutional
appointment or delegation. Existing `organization.manage` keeps its operational relationship meaning.

| Document | Purpose |
|---|---|
| [Domain/services](catalog-domain-and-services.md) | Explicit operations and immutable identity |
| [Authorization/MFA](authorization-and-mfa.md) | Current authority, sessions, role fence and grants |
| [Integrity/concurrency](integrity-and-concurrency.md) | Gate, lock order, versions and race evidence |
| [Impact/deactivation](deactivation-and-impact.md) | Counts, blockers, warnings and recheck |
| [Academic policy](academic-policy-changes.md) | Inventory, F4/F6 and unresolved decisions |
| [Audit/history](audit-and-history.md) | Same-transaction evidence and safe projection |
| [API/contracts](api-and-contracts.md) | Routes, operation IDs, inputs and errors |
| [Migration/release](migration-and-release.md) | Additive migration and compatible recovery |
| [ORG-3 handoff](org-3-handoff.md) | Existing Structure workspace implementation contract |
| [Validation](validation.md) | Executed checks, distinct cases and limits |

The ORG-1 actual cutover remains pending. No deployment, SSH, live migration, real institutional data
inspection, actual Catalog grant, institutional policy edit or editing activation is authorized or
performed. Source and synthetic tests can be complete while operational editing remains unavailable.
The PR targets integration; stop after opening it. Merge requires a new explicit user instruction.
