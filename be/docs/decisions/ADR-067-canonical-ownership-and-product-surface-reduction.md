# ADR-067: Canonical ownership and product surface reduction

- Status: Accepted
- Date: 2026-09-28
- Scope: document branding ownership, Student Support discovery, Organization reference structure, and Platform operator documentation

## Context

Several COMPASS surfaces exposed implementation facts as though they were independent product
workflows. Document presentation identity was stored in PostgreSQL even though templates, assets,
and supported layouts are source-owned. Student Support exposed both contextual support facts and a
broad sensitive roster. Campus, College, and Program references were split into three portal pages
although they form one read-only hierarchy. Platform Operations exposed a browser command catalog
whose entries could not be executed and belonged in deployment documentation.

The result was unnecessary configurability, duplicated discovery surfaces, fragmented navigation,
and developer/operator documentation presented as an application workflow.

## Decision

COMPASS classifies product surfaces by ownership:

- operational workflow — user actions that change or progress real office work;
- runtime configuration — institution/deployment state that legitimately changes while the product runs;
- canonical fact — source-owned identity or compatibility facts shipped with the application;
- contextual projection — bounded information shown only inside an authorized workflow;
- operator documentation — deployment or diagnostic guidance used outside the browser product.

A database model or API endpoint does not by itself justify a portal workspace.

### Document branding is code-owned

Institution and GCO document identity is an immutable source-owned definition in the documents
domain. Confirmed values are limited to Republic of the Philippines, University of Camarines Norte,
UCN, Camarines Norte State College, and Guidance and Counseling Office. Unconfirmed address,
website, contact, parent-unit, phone, social, and office-location values remain absent.

Packaged UCN, Bagong Pilipinas, accreditation/footer assets, print CSS, and code-owned templates
remain local and deterministic. PDF rendering stays network-isolated.

The DocumentBrandingProfile runtime model, GET/PATCH API, recent-MFA mutation path, and
document_branding.view / document_branding.manage capabilities are retired. Identity policy
synchronization removes persisted grants, overrides, and retired capability rows. Existing
document_branding.updated AuditEvents remain historical facts and are not rewritten.

A new migration fails closed before deleting the old branding table if persisted branding differs
from the canonical source-owned definition. Failure reports only the profile key and differing field
names, not the stored contact values. Historical migrations remain unchanged.

### Student Support remains contextual

GET /api/v1/student-support/students/{student_id}/context remains the supported projection. It
keeps Counselor-only capability checks, organizational scope, current Academic Year resolution,
submitted-current-Inventory behavior, and the existing privacy-minimized indicator vocabulary.

The broad GET /api/v1/student-support/students roster and its search/filter/pagination machinery
are removed. Sensitive support indicators are not a Student discovery mechanism. The persisted
StudentSupportProfile remains part of the Individual Inventory data model.

### Organization structure is one reference concept

Campus, College, and Program backend read APIs remain canonical reference contracts because selectors
and other workflows use them. Their three portal pages are replaced by one read-only
/portal/organization Structure surface composed from those existing APIs.

Organization navigation is Structure, Responsibilities, and Student affiliations. Counselor
Responsibilities, Staff Supervision, and Student Affiliations remain runtime-managed because they
drive routing and authorization scope.

### Institutional Forms remain code-owned and read-only

ADR-063 remains authoritative. Form Families and supported Form Revisions are code-owned with a
historical relational projection. Runtime revision management is not reintroduced and
institutional_forms.manage remains retired.

### Operator commands belong in deployment documentation

The /api/v1/platform/commands API, source catalog, and /portal/platform/commands page are removed.
Actual Django management commands remain unchanged. Their unique invocation and safety guidance
lives in the backend README as the single operator reference.

Platform Health, Environment diagnostics, Maintenance, Email Delivery operations, Technical
Activity, and public status remain product surfaces. platform_operations.view is retained with
wording limited to those live surfaces.

This decision supersedes only the browser command-catalog portion of ADR-043 and the statement in
ADR-044 that the command-catalog API remains live; the diagnostic and runtime-operation boundaries
in those ADRs remain authoritative.

## Consequences

- document rendering no longer depends on PostgreSQL branding configuration;
- divergent historical branding cannot be silently discarded;
- Student Support cannot be enumerated through a support-indicator roster;
- Organization reference browsing has one coherent hierarchy without new backend mutations;
- deployment commands remain available without a browser documentation API;
- OpenAPI and frontend navigation are smaller and describe only current product surfaces;
- removed URLs are intentionally absent rather than hidden compatibility routes;
- unrelated workflows and retained Platform/Privacy/Institution configuration remain unchanged.
