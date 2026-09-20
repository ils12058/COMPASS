# ADR-054 — Counselor Baseline Authority and Scoped Reporting

**Status:** Accepted  
**Date:** 2026-09-20

## Context

COMPASS authorization separates capability, resource scope, and domain/state eligibility. Final role review found that ordinary Counselors were missing several baseline capabilities even though the affected domains already had, or could authoritatively derive, Counselor organizational scope.

The correction must not turn a capability such as `reports.view` or `appointments.manage` into institution-wide authority.

## Decision

The canonical `COUNSELOR` baseline additionally grants:

- `appointments.manage`
- `academic_years.view`
- `institutional_forms.view`
- `reports.view`

Existing Head Guidance designation grants remain listed. Identity-policy synchronization is additive, so this slice does not attempt destructive reconciliation of redundant persisted grants.

### Appointments

Appointment administration continues to use the existing domain authorization boundary:

- Head Guidance Counselor: institution-wide.
- Regular Counselor: active Colleges assigned through `CounselorResponsibility`.
- Guidance Services Staff: existing supervisor-derived scope.
- Student: existing self-service behavior.

No scoped Appointment capability variant is introduced.

### Academic Year and Institutional Forms

Regular Counselors may read Academic Year configuration and controlled Form Family/Revision metadata.

They do not receive `academic_years.manage` or `institutional_forms.manage`. Existing recent-MFA and Head administrative behavior remains unchanged.

### Aggregate reports

`reports.view` means the actor may use supported aggregate-report workflows. It does not mean global population access.

The reports domain owns a narrow, non-persistent `ReportAccessScope`:

- Head Guidance Counselor: global scope.
- Regular active Counselor: current active Colleges assigned through `CounselorResponsibility`.
- Regular Counselor with no active assigned Colleges: denied.
- An unsupported role that only receives a capability override: denied because the override does not fabricate resource scope.

Student Profiling applies the resolved scope in the canonical report population/query layer before the frozen population is used by distributions and denominators. Request filters may narrow that population but cannot expand it. A College or Program outside the resolved scope is denied. A Campus filter is allowed only when that Campus contains at least one authorized College, and the population remains restricted to authorized Colleges inside it.

Current Counselor responsibility is also the authorization boundary for historical Student Profiling. COMPASS does not reconstruct historical Counselor assignments it does not store. Historical submitted/draft Inventory rows are therefore limited by their canonical Program/College against the Counselor's current authorized Colleges.

The same resolved scope is passed through JSON, PDF, and XLSX paths. Scope wording is included in the report methodology/coverage text so a Counselor-scoped artifact does not imply institution-wide coverage.

### Graduate Tracer

Graduate Tracer aggregate reporting requires global report scope. COMPASS has no authoritative historical Campus/College/Program binding for the Graduate Tracer dataset, so ordinary College-scoped Counselors are denied even though they have `reports.view`.

No College scope is inferred from current Student affiliation, survey free text, degree strings, or heuristic Program classification.

Raw `graduate_tracer.view`, Feedback/CSM raw review, and Exit Interview raw/reopen authority remain unchanged.

### Other unchanged authorization

The Counselor availability split remains:

- `availability.view`
- `availability.manage_self`

Head administrative availability remains separate through `availability.manage`.

Referral and Call Slip authorization remains on each domain's existing explicit scope boundary. Guidance Services Staff receives no new Academic Year, Institutional Form, or report capability from this correction.

### Deployment identity-policy synchronization

The staging deployment now runs:

`python manage.py sync_identity_policy`

after successful migrations and before deployment state is written and the full candidate stack is started. It runs through the same Compose `web` service and therefore the same immutable candidate image and live deployment environment.

The synchronization command remains additive. This slice does not revoke unknown or no-longer-listed database grants.

## Consequences

No schema migration is introduced and no new capability code is created.

The core rule remains:

> capability + resource scope + state/domain eligibility = authorized action

Two actors may therefore both have `appointments.manage` or `reports.view` while legitimately seeing different populations.
