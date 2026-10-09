# ADR-069: Remove the Retention Policy Registry

- Status: Accepted
- Date: 2026-09-29
- Scope: Live Privacy Governance product boundary
- Refines: ADR-061 and ADR-065
- Refined by: [ADR-072](ADR-072-operational-retention-and-disposition.md) (operational retention and disposition for supported categories)

## Context

ADR-061 introduced descriptive Retention Policies. ADR-065 retained the registry while removing
unsupported Processing Activity, Review/PIA, and Incident workflows. Further product review found
that the registry still has no adopted institutional retention schedule, disposition process, or
operational behavior in COMPASS. Its prose and record-category mapping could imply governance that
the application does not perform.

## Decision

Remove Retention Policies from the live model, API, OpenAPI contract, frontend, and demo seeder.
Retain versioned Privacy Notices, exact-revision acknowledgment, Privacy & Security Activity, and
fail-closed auditing of privacy-sensitive document and report releases. No automatic retention,
archive, anonymization, deletion, or disposition engine is introduced.

Historical `privacy.retention.*` AuditEvents remain append-only and their legacy activity
presentations remain readable. No live route emits new retention events or links to a removed
Retention Policy page.

## Migration boundary

Migration `0004_remove_retention_policy` counts existing `RetentionPolicy` rows before dropping the
table. A nonzero count aborts with only the model identity and count. It neither deletes nor
archives rows. Deployments with existing rows, including previously seeded staging policies,
require an explicit separate institutional data-disposition decision before retrying migration.

## Consequences

Privacy Governance now presents only controls with direct operational behavior in COMPASS. A
future retention/disposition workflow needs an authoritative institutional policy source,
ownership, lifecycle, approval model, legal-hold and exception behavior, and a deliberate data
disposition design.
