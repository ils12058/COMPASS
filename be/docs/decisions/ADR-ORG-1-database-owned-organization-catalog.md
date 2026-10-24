# ADR-ORG-1: Database-owned Organization catalog and persisted Program policy

- Date: 2026-10-25
- Status: Accepted engineering foundation for ORG-1; institutional adoption and deployment remain unapproved.
- Supersedes: ADR-064's recurring code authority and Python-owned academic metadata. Preserves its stable identity, base Program/major distinction, protected history and operational relationships.
- Baseline: integration `e7db50e0b23dd21a7ff7ec44c9d08708eb24ee12`; ORG-0 PR #326.

## Decision

Campus, College and Program rows are the single live catalog. Program stores nullable classification,
explicit configured/pending status and nullable PostgreSQL small-integer Year Levels. One validator
and persisted accessor serve the current consumers. There is no runtime seed lookup or name-based
classification fallback. Additional Programs require no Python registration.

The original registry is frozen installation baseline `ucn-2026-09-27-v1`, not a recurrent reconciler.
The additive Organization 0002 embeds its own frozen 38-policy exact-code map, uses historical models,
and changes only new columns. Names, statuses, parent UUIDs, timestamps and consumer facts survive.
Unknown/changed identities remain null/PENDING_POLICY/null. Missing baseline rows are not inserted.

Explicit `initialize_organization_catalog --seed` requires all three tables empty and no receipt.
`--adopt` records an existing catalog without seeding or repairing it. `--check` requires a compatible
schema and a receipt. A singleton SEEDED/ADOPTED receipt and synchronous Audit append are atomic;
PostgreSQL transaction advisory locking serializes concurrent installers. Repeated calls return the
receipt without reconciliation or duplicate events. Empty adopted catalogs are not reseed triggers.
The old function/command is a deprecated seed-only alias and refuses populated unadopted data.

The seeder checks initialization and fixture availability; it cannot repair catalog prerequisites.
Deployment defaults to a catalog check. Explicit seed/adopt choices are passed through the controlled
workflow/orchestrator, but do not authorize the migration: it is deliberately **not** in the routine
live migration allowlist. Future coordinated migration review is still required.

## Compatibility and consequences

Inventory retains configured membership validation and pending/unknown recorded 1–10 compatibility.
F4 still requires a Bachelor policy and the intersection with fixed template-supported Years 1–4.
F6 degree-name suggestions come from active database Bachelor Programs, remain advisory, and do not
validate historical qualifications. Saved certificate/course facts and existing routing/scope remain.
Generic historical reference reads remain inactive-inclusive.

The immutable V1 SQL helper is narrowly scoped to array validity. Its CHECK handles empty/null,
shape/lower bounds, null elements, range, uniqueness and order; Python rejects booleans/floats before
field coercion. Policy backfill is forward-only: supported operational rollback retains schema and
requires a compatible DB-authority image or roll-forward. Do not reverse/drop populated policy.

No catalog CRUD endpoints, editor, capability/grants, transfers, SAR or institutional policy workflow
are added. ORG-2 must provide protected mutations, resource versions, transactional impact checks,
recent MFA, Audit and cross-domain concurrency before any editor is enabled.

A receipt or cooperative initialization lock cannot fence an unmodified old binary or direct SQL.
Actual cutover requires verified backups, all old web/worker/Beat/CLI/external writers stopped, an
approved compatible image/scripts floor, and separate institutional approval (ORG-0 D1/D2/D8/D19).
No live writer inventory, data inspection or operational cutover was performed to accept this ADR.
