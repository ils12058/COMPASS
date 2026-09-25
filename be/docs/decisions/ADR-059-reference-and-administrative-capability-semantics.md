# ADR-059 — Clarify Reference and Administrative Capability Semantics

**Status:** Accepted
**Date:** 2026-09-25

## Context

Generic `organization.view` and `services.view` were used as frontend signals for standalone
workspaces. Their backend authority is narrower: safe Campus/College/Program structure and the
active GCO Service catalog. Students and Guidance Services Staff legitimately consume these data
through booking, selectors, and other workflows. Those reads do not confer Organization or Service
configuration authority.

Capabilities remain scope-free action classes under ADR-006 and ADR-056. Role/designation is actor
identity; resource scope, domain eligibility, and recent MFA remain separate backend checks. A
capability is not a backend menu instruction.

## Decision

- Rename `organization.view` to `organization.structure.view` for the six structural list/get
  routes. Responsibility, supervision, affiliation, people picker, and mutations continue to
  require `organization.manage`.
- Rename `services.view` to `services.catalog.view` for active catalog list/get. Inactive
  configuration remains management-gated, and writes continue to require `services.manage` and
  recent MFA. The existing independent read-revocation behavior is preserved when requesting an
  inactive-inclusive list.
- Preserve the Student, GSS, Counselor, and IT Admin baseline read grants. Head Guidance Counselor
  inherits Counselor reads and retains its management designation grants. DPO grants do not change.
- Rename persisted `Capability.code` values in place in an explicit data migration. The primary key,
  role/designation grants, and every user override including reason, expiry, and creator survive.
  If old and new rows coexist, migration fails for operator reconciliation instead of merging or
  discarding authority. The reverse migration applies the same conflict check.
- Keep `CAPABILITY_CODES` singular. Unknown and legacy rows fail closed in the effective resolver;
  runtime authorization has no permanent alias. Policy sync rejects legacy rows if it is run
  before the data migration, rather than creating new canonical rows beside them.

## Deferred and retained decisions

`availability.view` guards both effective provider lookup and Counselor self reads. A split would
require a policy for mapping each legacy GRANT/REVOKE override, since copying an override to both
new capabilities can change intended authority. It remains unchanged pending that design.

`academic_years.view` guards a read-only list of all years; `institutional_forms.view` guards
Form Family and Revision metadata lists. Their read authority and management guards remain
distinct. `accounts.view` currently has no direct route/service guard; Account Management uses
`accounts.manage`, while other person projections apply domain guards. These codes remain canonical
because a rename would not resolve a concrete backend authority ambiguity in this slice. The
[catalog audit](../capability-catalog-audit.md) records all 67 capabilities and their consumers.

## Consequences

Account Management's capability enum and access inspector, authenticated session capabilities,
and OpenAPI expose only the new codes. Existing explicit overrides keep their effects and
provenance after upgrade. A deployment must run migrations before syncing canonical policy.

The frontend must later replace the two legacy checks and compose workspace visibility from
actual operational or administrative authority: `organization.manage` for Organization management,
`services.manage` for Service configuration. Reference consumers may continue to use
`organization.structure.view` and `services.catalog.view` without gaining those workspaces.
