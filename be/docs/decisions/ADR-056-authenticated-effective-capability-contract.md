# ADR-056 — Authenticated Effective Capability Contract

**Status:** Accepted  
**Date:** 2026-09-20

## Context

COMPASS already evaluates scope-free account authority through the canonical
`effective_capabilities(user)` resolver. Frontend bootstrap needs a compact description of the
authenticated actor so navigation and action affordances can avoid obviously unauthorized
requests without duplicating backend policy.

The backend remains the authorization authority. Capability alone never replaces resource scope,
record/domain eligibility, or recent authentication assurance.

## Decision

`GET /api/v1/auth/session` remains the primary frontend authorization-context bootstrap surface.
The existing successful login response continues to use the same authenticated-user summary.

The authenticated user summary exposes:

- account identity fields already present;
- primary `role`;
- `student_lifecycle_status`;
- current canonical `designations`, sorted by code;
- current effective `capabilities`, sorted by code.

Capabilities come directly from `compass.accounts.services.effective_capabilities(...)`. The auth
API does not reproduce role grants, designation grants, override grant/revoke logic, override
expiry, or canonical capability filtering.

The response intentionally does **not** expose:

- role/designation grant provenance;
- override reasons, actors, or expiry;
- resource-scope identifiers or global-access flags;
- per-record/domain eligibility;
- recent-MFA state as a capability;
- backend menu, route, widget, or button configuration.

Designation remains identity/display context. Frontend authorization affordances should use
capability codes rather than infer fine-grained authority from role or designation.

Capabilities are resolved when the authenticated summary is serialized. They are not persisted
into `AuthSession`, cookies, token claims, or client-supplied headers. A later
`GET /api/v1/auth/session` therefore reflects current role/designation/override truth.

Successful MFA login completion already reuses the shared login-response serializer and therefore
inherits the same authenticated-user shape only after authentication succeeds.

## Frontend intent

A future frontend may implement an affordance helper conceptually equivalent to:

`can(code) = session.user.capabilities.includes(code)`

This is UX guidance only. Protected backend routes continue to resolve their own current
capability, resource scope, state/domain eligibility, recent MFA, and business rules.

## OpenAPI typing

The current auth schema represents `designations` and `capabilities` as arrays of strings. The
runtime serializer filters designations through canonical designation codes and obtains
capabilities from the canonical capability resolver. This avoids introducing a second hard-coded
policy list or a broader enum/code-generation refactor solely for this contract.

## Consequences

No model/schema migration and no identity-policy grant change is introduced.

The architectural split remains:

- role/designation → actor identity;
- capability → scope-free action class / frontend affordance;
- resource scope → backend record access;
- state/domain eligibility → backend action validity;
- recent MFA → backend security assurance.
