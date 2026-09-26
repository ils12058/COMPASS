# ADR-060: Bootstrap the system-required Counseling Service

## Context

ADR-018 deliberately omitted production Service rows while institutional offerings were unknown,
and ADR-021 kept Counseling request handling free of hidden Service creation. Subsequent
Counseling, Routine Interview, Appointment, and E-Counseling workflows all bind to the stable
`COUNSELING` code. Without that row, a migrated deployment can appear ready while core workflows
and Student booking discovery fail. Missing canonical configuration is now a deployment defect.

## Decision

`COUNSELING` is the only system-required Service in V1. After migrations and
`sync_identity_policy`, deployment runs `python manage.py sync_canonical_services`. The Role
sync must come first because provider eligibility refers to the canonical COUNSELOR Role.
The Service is not created in a data migration or during import, startup, health checks, or
ordinary requests. The command is transactional, idempotent, and reconciles an existing row
in place to preserve its primary key, references, and audit history.

Fresh configuration is active, named Counseling, appointment policy OPTIONAL, default duration
60 minutes, cancellation cutoff 30 minutes, no current Inventory prerequisite, COUNSELOR
provider eligibility, and IN_PERSON delivery only. OPTIONAL supports both scheduled and direct
Counseling. General Counseling does not inherit Routine Interview's Inventory prerequisite.
ONLINE is an explicit institution and deployment choice because Daily may be disabled or
unconfigured; the catalog does not depend on Daily.

The canonical Service must remain active and retain COUNSELOR eligibility and at least one
supported delivery mode. Normal creation cannot claim its reserved code, and normal updates
cannot remove COUNSELOR or disable the Service. Appointment policy may become NONE to stop
new appointment booking while direct Counseling continues. ONLINE may be removed while
IN_PERSON remains. Valid institution settings, including display text, policy, duration,
cutoff, Inventory prerequisite, and delivery modes, survive repeated synchronization.
Synchronization repairs required drift and records only meaningful changes through the existing
system Audit context. Other Services remain institution-configurable and disableable.

Readiness checks the required Service after PostgreSQL succeeds and returns 503 if it is
missing, inactive, or invalid. The public response reveals only pass/fail; a bounded reason
is logged for operators. Readiness does not require Daily, ONLINE, Availability, Academic Year,
or Inventory. Counseling requests continue to fail safely on invalid canonical configuration.

## Consequences

Deployment order is migrate, identity policy sync, canonical Service sync, then deployment check.
This is required operational configuration, not generic fixture seeding. ADR-018's historical
decision remains valid for arbitrary institutional offerings. ADR-021's request-time boundary
remains intact. ADR-059's `services.catalog.view`, `organization.structure.view`, and management
capabilities are unchanged; system synchronization does not grant or require human authority.
