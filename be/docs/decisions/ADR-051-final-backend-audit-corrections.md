# ADR-051: Final Backend Audit Corrections

- **Status:** Accepted
- **Date:** 2026-09-20

## Context

Two independent static reviews of the backend at staging commit
`5542474f1bd6afc9b014227e31c59a0d2f514517` identified a bounded set of
correctness, concurrency, deployment, and recovery defects after the final planned
functional slice.

This ADR records only corrections to existing behavior. It does not reopen backend
functional scope.

## Decision A — Authentication security-state serialization

Primary password verification and issuance of reusable authentication state are
serialized on the User row used by password change/reset security transitions.

Password-only sessions, trusted-browser sessions, ordinary MFA LoginChallenges, and
mandatory-MFA enrollment challenges therefore cannot be issued from a stale primary
password after a completed password transition.

Mandatory TOTP roles without an active factor receive a short-lived LoginChallenge
whose only allowed method is `totp_enroll`. That challenge may start and confirm TOTP
enrollment only. It is not an AuthSession and cannot authenticate ordinary APIs.
Successful confirmation consumes the challenge and still requires a normal login.

## Decision B — E-Counseling transcript-storage withdrawal wins

A transcription start revalidates effective LIVE_TRANSCRIPTION and, when requested,
TRANSCRIPT_STORAGE consent on the same locked room/capture boundary immediately
before the provider start command.

TRANSCRIPT_STORAGE withdrawal treats a pending START_REQUESTED transcription as
storage work in flight. Withdrawal remains committed before provider cleanup.
If withdrawal supersedes a pending start after provider storage was enabled, COMPASS
attempts compensating provider disablement and never restores consent because cleanup
failed.

## Decision C — Exit Interview historical correction authority

First-time Exit Interview initiation remains bound to the current submitted Inventory.

After creation, the Exit Interview ID, Inventory, and Academic Year are historical
authority. A CURRENT Student may update and resubmit a specifically owned reopened
draft by Exit Interview ID without re-resolving the institution-current Academic
Year. Cross-student IDs remain concealed as not found.

ADR-032 remains authoritative for lifecycle eligibility: Student edit/resubmission
and Head reopen-for-Student-correction still require CURRENT lifecycle. The audit
suggestion to remove that prerequisite is therefore rejected.

Each `ExitInterviewReopenEvent` is the logical Notification source. Retries of the
same event deduplicate, while distinct reopen events create distinct notifications.

## Decision D — Narrow persistence and idempotency corrections

Routine Interview direct creation contains the potentially conflicting insert inside
a nested transaction savepoint. A uniqueness race is recovered outside the failed
savepoint while preserving request-fingerprint conflict semantics.

Inventory sibling draft payloads normalize nullable `sex` from API `null` to the
model's existing blank-string representation before persistence. No Inventory schema
redesign is introduced.

## Decision E — Previous-address email security-alert recovery

The immutable `EmailChangeRequest.current_email_snapshot` remains the alert
destination.

Confirmed requests with no `old_email_alert_sent_at` are periodically republished by
a bounded recovery task. Delivery holds the EmailChangeRequest row lock through the
mail transport call and sent-state stamp so duplicate recovery publications converge
without two tasks sending concurrently for the same durable row.

## Decision F — Coherent report populations

Graduate Tracer and Student Profiling reports materialize the matching immutable
submitted-record IDs once per generated report. Denominators, grouped counts, program
totals, and missing-value calculations are then constrained to that fixed membership.

This avoids relying on ordinary READ COMMITTED transaction wrapping as a snapshot
mechanism.

## Decision G — Appointment provider eligibility

ADR-050's operational rule is canonical: `COUNSELOR` is the Appointment provider
role; Guidance Services Staff remain scoped Appointment administrators, not providers.

New Service Catalog provider-role configuration accepts COUNSELOR only. Historical
ServiceProviderRole rows that contain GUIDANCE_SERVICES_STAFF remain readable for
source compatibility, but they do not confer live provider eligibility.

A role transition from COUNSELOR to GUIDANCE_SERVICES_STAFF therefore removes
provider eligibility and is blocked while active/future provider Appointments remain.

## Decision H — Live-staging internal health probes

Public HTTP-to-HTTPS enforcement remains enabled.

Docker and Caddy internal health probes identify themselves through the configured
health Host and the existing trusted `X-Forwarded-Proto: https` mechanism so Django
can serve readiness directly to the internal probe without requiring TLS at Gunicorn.

No public transport-security setting is weakened.

## Consequences

- No database migration is required.
- Existing capability, resource-scope, privacy, and historical-record boundaries are
  retained.
- The canonical GitHub Actions workflow is not changed by this correction package.
- Backend functional scope remains frozen; unresolved Routine Interview versus later
  Counseling-correction semantics remain a stakeholder clarification rather than an
  implementation change.
