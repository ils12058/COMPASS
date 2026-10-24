# ORG-0 — Catalog authority and migration architecture

Status: **audit and proposed design; no runtime implementation**. Source review began 2026-10-24; report completed 2026-10-25 (Asia/Manila).
Repository: `ils12058/COMPASS`. Fetched and inspected integration SHA:
`7522e55c94193a28e2e8c6773c634426be48856c`.
Branch: `audit/org-0-catalog-authority`; PR base: `integration/ux15-modernization`.

The catalog is still owned by Python. Adding CRUD now would let deployment or the dataset seeder
restore old names, reactivate retired canonical entities, and deactivate approved new Programs.
ORG-1 must replace that authority before any catalog editor is enabled.

## Evidence vocabulary

- **VERIFIED CODE FACT**: inspected at the SHA above; links below pin that revision.
- **TESTED BEHAVIOR**: exercised in the disposable PostgreSQL environment in [validation](validation.md).
- **PROPOSED DESIGN**: an implementation recommendation, with no claim of delivery or approval.
- **INSTITUTIONAL DECISION REQUIRED**: a policy/authority choice the code audit cannot approve.
- **UNVERIFIED DEPLOYED STATE**: actual deployment versions, catalog populations, grants, jobs and policy approvals were not inspected.

A test proves only its named scenario. No synthetic result establishes institutional UAT or deployment readiness.

## Verified findings

1. Campus/College/Program UUIDs and protected relationships already support ordinary renames.
   Program has no persisted academic policy. Registry baseline: 6 Campuses, 10 academic units,
   38 base Programs (30 Bachelor's, 5 Master's, 3 Doctoral), not permanent catalog limits.
2. Explicit management command, staging deployment loop, and staging dataset seed mode can invoke
   reconciliation. Organization startup, migrations, requests and scheduled tasks contain no
   additional recurring catalog synchronizer in this revision. Test fixtures also call it.
3. Metadata depends on exact `(campus.code, college.code, program.code)`; a new Program row can
   be selectable in Inventory while F4 rejects it as unclassified. Good Moral degree suggestions
   also enumerate the Python registry directly.
4. Inventory stores course text and a Program FK; API reference labels are live. Good Moral
   F4/F6 save certificate-local text and render provenance. Graduate Tracer has live College/Program
   labels without catalog-name snapshots. Reports combine historical facts with current labels/scope.
5. Inactive College/Campus stops default routing before Head fallback. Current affiliation and
   responsibility rows therefore need explicit remediation before deactivation.
6. `organization.manage` authorizes operational relationships and is granted to IT Admin and the
   Head designation. It must not become catalog authority by accident. Structure API reads and
   Organization workspace access currently have different capability gates.

Sources: [be/compass/organization/models.py:41](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L41);
[be/compass/organization/bootstrap.py:95](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L95);
[be/compass/organization/canonical.py:82](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L82);
[be/compass/organization/services.py:103](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L103);
[be/compass/good_moral/api.py:685](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/api.py#L685).

## Recommended architecture

**PROPOSED DESIGN:** Option B: retain the existing relational catalog as the sole live authority;
freeze today's Python definitions as a versioned initial seed/backfill input. Persist the three
academic-policy values on Program using nullable classification, explicit policy status and a
nullable PostgreSQL small-integer array. Use one narrow initialization receipt, not a second
catalog or a multi-mode authority state machine. Never reconcile ordinary administrator edits
against baseline names/status/counts.

Use a coordinated cutover that stops all old writers and readers. The existing deployment script
already stops old application containers; ORG-1 must strengthen the version/rollback boundary and
retire the seeder's direct reconciliation call. A database marker alone cannot stop an older
binary that ignores it. If complete old-process retirement cannot be proved, activation is blocked;
a separately reviewed database-enforced writer fence would then be necessary.

ORG-1 preserves existing Inventory pending-policy compatibility and F4 Years 1–4 limits. Catalog
management is a later capability (`organization.catalog.manage`), recent-MFA and audit boundary,
with no automatic role/designation grants. Transfers, mergers, code changes, SAR, affiliation
migration, confidential ownership and institution-wide imports remain outside ordinary CRUD.

## Deliverables and release boundaries

| Document | Purpose |
|---|---|
| [Current state](current-state-audit.md) | Models, API, permissions and workspace facts |
| [Authority/bootstrap](canonical-authority-and-bootstrap.md) | Writer/read inventory, alternatives and seed rules |
| [Program policy](program-policy-design.md) | Representation, backfill, Inventory/F4/F6 and pending transactions |
| [Dependencies/history](dependency-and-history-matrix.md) | Direct/indirect consumers, routing and snapshots |
| [Integrity/authorization](integrity-and-authorization.md) | Blockers, impact, grants, auditing and locking |
| [Migration/rollback](migration-and-rollback.md) | Additive schema, rehearsal, cutover and recovery |
| [UX/workspace](ux-and-workspace-design.md) | Existing surface and proposed interactions |
| [Implementation plan](implementation-plan.md) | ORG-1 → ORG-4 paths, contracts, tests and gates |
| [Open decisions](open-decisions.md) | Institutional and release choices |
| [Validation](validation.md) | Exact executed commands, distinct counts and limitations |

**ORG-1 readiness:** implementation-ready design with explicit release gates; not permission to
activate editors, deploy, grant authority or resolve institutional policy. Resolve the decisions
identified as ORG-1 gates before selecting rollout behavior. ORG-2/3 must wait for authority and
consumer conversion. ORG-4 must demonstrate the combined result, including migration/concurrency
and authenticated-browser tests not performed in this audit.

## Proposal provenance and exclusions

Proposal #2 in **COMPASS Development Proposal Notes — Fifteen Proposals** was read from the saved
publication source, section beginning `# COMPASS — Organization Catalog CRUD`. Its original
current-state baseline is `staging` `0a843dae`, reviewed October 20, 2026. This audit re-inspects the
newer integration revision; the proposal's older findings are not substituted for source evidence.
Local source: `Downloads/COMPASS_Development_Proposal_Booklet_2026-10-21/sources/COMPASS Development Proposal Notes - Fifteen Proposals.txt`.
The substantive boundaries remain: Organization owns institutional definitions and operational
responsibilities; proposed SAR owns individual academic placement/history; Accounts owns identity;
Inventory owns Guidance submissions. No source document is copied into this PR.

This PR changes only `docs/org-0/`. It adds no runtime fields, migrations, routes, UI, capabilities
or grants. No SSH, Droplet access, live database access, operational data mutation, deployment or
merge is authorized or performed. Local pytest creates synthetic schema/data only.
