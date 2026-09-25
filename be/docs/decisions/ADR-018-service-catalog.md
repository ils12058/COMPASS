# ADR-018: Service Catalog foundation

## Context

COMPASS needs a stable way to describe the Guidance and Counseling Office services that exist before Availability, Appointment, or domain-specific workflows can be modeled. Appointment is shared scheduling, not the parent object for every office workflow. Some services are not normally scheduled, some may optionally use scheduling, and others may require it.

## Decision

Introduce a dedicated Service Catalog domain with three small persistent models: `Service`, `ServiceDeliveryMode`, and `ServiceProviderRole`. A Service has a stable UUID primary key, immutable-through-normal-API machine code, name, optional description, appointment policy, optional default schedulable duration, active state, and timestamps. Service codes are normalized to uppercase machine-friendly identifiers and are protected from concurrent duplicates by a database uniqueness constraint.

Appointment policy is explicit: `NONE`, `OPTIONAL`, or `REQUIRED`. This slice stores that policy but does not enforce future Appointment behavior. Delivery modes are the closed values `IN_PERSON` and `ONLINE`; there is no configurable delivery-mode registry. E-Counseling is therefore ONLINE delivery of Counseling, not a separate Service created merely because delivery occurs online.

A Service may allow the canonical operational roles `COUNSELOR` and/or `GUIDANCE_SERVICES_STAFF` as potential primary-provider roles. Provider-role eligibility checks only whether an active user has a configured primary role. It does not answer organizational responsibility, availability, student preference, resource assignment, or record-access questions. Head Guidance Counselor remains a COUNSELOR with a designation, so COUNSELOR eligibility also covers a valid Head at the role level. GSS organizational responsibility still comes dynamically from the supervising Counselor; Service Catalog does not copy that scope.

New Services are always created inactive. Active Services must have a valid name, appointment policy, at least one delivery mode, and at least one eligible provider role. OPTIONAL and REQUIRED Services also require a default duration. Default duration is bounded to 1–480 minutes when present and is a scheduling default only, not an SLA or historical duration. The full active configuration is validated atomically on enable and on updates to already-active Services. No-op updates and repeated enable/disable calls do not emit misleading audit events.

Catalog reads require `services.catalog.view` (see ADR-059). Inactive configuration additionally requires `services.manage`, so a caller with management capability but an explicit view revocation cannot use read endpoints. Catalog mutations require `services.manage` plus the existing recent-MFA step-up. Baseline grants give IT Admin both capabilities, operational roles and Student view, and the HEAD_GUIDANCE_COUNSELOR designation manage. Existing GRANT/REVOKE override semantics remain authoritative.

Service Catalog writes use PostgreSQL transactions and row locking for existing-Service mutations. Child mode/provider sets are replaced atomically when supplied. Stable audit actions are limited to `service.created`, `service.updated`, `service.enabled`, and `service.disabled`. These configuration events are not added to My Activity or Security Activity.

There is no Service delete endpoint. Disabling an ordinary Service only prevents new future workflows from offering it; it does not imply cascading deletion or cancellation. At the foundation stage, no production Service rows were seeded because institutional codes, durations, modes, and provider mappings had not been confirmed. ADR-060 now identifies one exception to that historical assumption: the system-required `COUNSELING` Service is provisioned through explicit, idempotent canonical synchronization. Other institutional Services remain unseeded and configurable.

## Consequences

Service remains more fundamental than Appointment. The catalog is intentionally institution-wide and has no Service-to-Campus or Service-to-College mapping. This slice does not introduce Availability, Appointment, ServiceDelivery, preferred-counselor persistence, routing, Counseling encounters, Good Moral processing, Exit Interview processing, Customer Feedback, dynamic forms, a generic workflow engine, or a rules DSL. Those domains may reference the stable Service catalog later while owning their own explicit workflows.
