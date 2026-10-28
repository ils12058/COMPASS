# Resource versions and cooperative PostgreSQL integrity

[integrity.py](../../be/compass/organization/integrity.py) owns the signed-bigint advisory key
`477580715032`. Exclusive `pg_advisory_xact_lock` protects catalog create/rename/status/policy;
shared `pg_advisory_xact_lock_shared` protects dependent writes. ORG-1 initialization keeps its
separate key `477580715031`. Both are cooperative transaction locks, not an old-binary or SQL fence.
Nested service calls retain the gate until the outermost transaction commits/rolls back. Never
upgrade a shared gate to exclusive; dependent writers must not call catalog mutation services.

Acquisition order:

1. Shared/exclusive gate, before existing user, management mutex or domain-row locks.
2. Catalog path: authenticated actor (NO KEY UPDATE), active factor, session. Factor-before-session
   matches existing session verification. No arbitrary dependent Student/User locks follow ancestry.
3. Catalog ancestry: Campus → College → Program; single target paths lock each level explicitly.
   Future operations locking multiple same-level rows must sort UUIDs; no bulk/move path exists here.
4. Domain writes retain their existing user/domain ordering after the shared gate.

Every existing catalog row receives resource_version=1 through additive Organization 0003. Each
supported real mutation increments once under a row lock in the same transaction as Audit. No-op
retains version/timestamp; creation starts at 1. PositiveIntegerField plus explicit per-model CHECK
`organization_{campus|college|program}_version_positive` reject zero/negative stored values.
Expected versions are mandatory genuine positive integers; stale versions yield 409. Database
uniqueness remains the final code constraint. No automatic stale-command replay occurs.

| Shared participant | Reason |
|---|---|
| Organization affiliation/responsibility set/remove | Stable active hierarchy, dependency insert/removal, no absent-row race |
| Account Management `_admin_mutation` | Reactivation, role/delegation/revocation must precede user/mutex locks |
| Low-level capability override and identity policy sync | Supported authority changes cannot commit midway through a catalog mutation |
| CSV account management entry | Avoid nesting participant calls after pre-existing management/user locks |
| Inventory ensure/replace/submit | Program selection/policy and submission facts remain coherent |
| F4 `_create_current_student`, assisted entry, Good Moral update_request | Academic context/year correction and pending F4 barrier; assisted entry takes gate before actor lock |
| Student appointment creation | Default routing decision/recheck before scheduling user locks |
| Office thread creation/status change | Open work insertion/reopening cannot evade retirement blocker |
| Follow-Up create/lifecycle/reassignment/activity | Current operational scope and pending-work projection; gate wraps durable replay before user locks |
| Dataset seed outer entry | Nested synthetic domain services cannot acquire the gate after seed row locks; the synthetic seed run holds one outer shared transaction, with existing unit savepoints inside it |

F6 self-service reported-text creation, issuance, certificate rendering and historical-only reads
acquire no new catalog gate. Assisted F6 shares its existing common assisted entry (which also creates
F4); update_request shares the correction entry because year correction is conditional on the row.
Impact GET takes a shared gate against catalog changes but stays advisory: shared dependent writers
can commit while it is being observed. Actual mutation recounts under exclusive coordination.
Future SAR current-placement writers MUST join before taking user/placement locks; SAR is not added.

Independent-connection tests use real services under an outer transaction, controlled Events and
`pg_locks` ungranted advisory-lock observations before releasing the first writer. Scenarios include
normalized duplicates for all entities; same-row rename/status; both parent/child creation orders;
College/Program activation; affiliation/responsibility; account reactivation; Inventory selection
and submission; F4 creation in both policy orders; correction versus policy; stale preview; revoked
capability; expired MFA; Audit failure and rollback after version increment. A real lock timeout and
a deliberately injected TEST-ONLY external lock inversion exercise actual PostgreSQL deadlock
translation (`40P01`, `55P03`, `57014` → `catalog_busy`) and rollback. See [validation](validation.md)
for final distinct results. Sequential mocks are not counted as race proof.

Supported operations produce a coherent commit or safe conflict. Shared dependent writers still
concur with each other; the gate globally serializes infrequent catalog administration. It neither
retrofits arbitrary `.save()`/QuerySet/raw SQL writers nor retires deployed old binaries. Full old
process exclusion and compatible rollout remain separate approval gates. External database errors
outside the translated contention states propagate and roll back; no fake success is returned.
