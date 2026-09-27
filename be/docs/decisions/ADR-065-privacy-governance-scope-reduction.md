# ADR-065: Privacy Governance Scope Reduction

- Status: Accepted
- Date: 2026-09-27
- Scope: Retain only implemented COMPASS privacy governance controls and remove unsupported governance workflows

## Context

ADR-045 introduced a broad Privacy Governance foundation with Processing Activities, Privacy
Reviews/PIAs, Privacy Incidents, and a curated Privacy & Security Activity projection. ADR-061
later added versioned Privacy Notices and descriptive Retention Policies.

The implemented Guidance and Counseling Office workflows do not currently provide an institutional
source process, approved operating procedure, or authoritative data owner for a standalone
Processing Activity register, Privacy Review/PIA queue, or Privacy Incident case-management
workflow. Keeping those generic records live would make COMPASS appear to own governance processes
that have not actually been adopted by the institution.

Privacy Notices, Retention Policies, exact-revision acknowledgment, release auditing, and the
curated Privacy & Security Activity projection remain concrete system controls with clear behavior.

## Decision

COMPASS narrows the live Privacy Governance workspace to:

1. Privacy Notices and versioned Notice Revisions;
2. exact-revision acknowledgment for applicable authenticated users;
3. Retention Policies as human-approved, non-executing lifecycle guidance; and
4. curated Privacy & Security Activity over the existing append-only Audit Trail.

The following application-owned workflows are removed from the live model, API, OpenAPI contract,
frontend workspace, and Overview:

- Processing Activities;
- Privacy Reviews / PIAs;
- Privacy Incidents.

Their historical audit action constants and safe activity presenters remain readable so existing
append-only AuditEvent history, if present, is not reinterpreted or erased. No live route emits new
Processing/Review/Incident mutation events after this decision.

## Retention Policy record categories

Retention Policies now map to a closed code-owned vocabulary of implemented COMPASS record classes:

- INDIVIDUAL_INVENTORY
- COUNSELING
- ROUTINE_INTERVIEW
- REFERRAL
- CALL_SLIP
- GOOD_MORAL
- EXIT_INTERVIEW
- GRADUATE_TRACER
- CUSTOMER_FEEDBACK

The category mapping is descriptive governance metadata only. It does not create foreign keys into
domain records and does not authorize or execute deletion, archival, anonymization, notification,
backup cleanup, or other retention actions.

New Retention Policies must select at least one supported category. Legacy Retention Policy rows
created before this change remain valid with record_categories=[] until an authorized operator
deliberately classifies them; COMPASS does not infer categories from names or prose.

## Destructive migration boundary

Removing obsolete workflow tables is intentionally fail-closed.

Before deleting the ProcessingActivity, PrivacyReview, or PrivacyIncident tables, migration
0003_simplify_privacy_governance_scope counts rows in each legacy model. If any rows exist, the
migration raises and stops before table deletion. The error reports only model names and row counts.

COMPASS does not silently:

- delete populated legacy rows;
- convert them to Retention Policies or Notices;
- serialize them into opaque JSON;
- invent archival semantics; or
- infer institutional disposition.

A deployment with populated legacy rows therefore requires a separate explicit institutional
archive/migration decision before this migration can proceed.

## Overview and frontend

The Portal Overview no longer exposes open_review_count or active_incident_count, and its schema
contains no Privacy section. Privacy Governance remains discoverable through capability-based quick
access.

The Privacy Governance navigation contains only Privacy Notices, Retention Policies, and Privacy &
Security Activity. Removed workflow URLs are not kept as hidden compatibility routes.

## Authorization and audit boundaries

The existing privacy_governance.view and privacy_governance.manage capabilities remain
designation-derived for the DPO boundary established by ADR-045. Retained management mutations
continue to require recent MFA.

Notice/Retention mutations remain synchronously audited with minimized metadata. Sensitive report
and document release auditing remains unchanged. The curated activity projection continues to
exclude raw AuditEvent metadata, confidential record contents, IP addresses, user-agent values,
credentials, and arbitrary audit browsing.

## Consequences

COMPASS presents only privacy governance workflows that it can truthfully support today. The system
retains policy communication, acknowledgment provenance, human-approved retention guidance, and
privacy/security oversight without pretending to be an institutional PIA register, incident
management system, SIEM, or automated records-retention engine.

A future institutional requirement may reintroduce a Processing Activity register, PIA workflow, or
Incident workflow, but it must be backed by an explicit source process, ownership model, lifecycle,
authorization boundary, and migration decision rather than restoring these generic tables by
default.
