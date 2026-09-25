# ADR-058 — Portal Overview Summary Projection

**Status:** Accepted  
**Date:** 2026-09-25

## Context

The authenticated COMPASS Portal needs a useful home Overview for Students, Guidance operational
users, IT Administrators, and the Data Protection Officer. Existing operational list APIs are
intentionally paginated and expose `items`, `page`, `page_size`, and `has_next` rather than an
authoritative total count. A page length is therefore not a valid source for dashboard totals.

The Overview also crosses several bounded domains. It must not become a second authorization
engine or a universal feed of record details.

## Decision

COMPASS exposes a read-only `GET /api/v1/overview` projection whose exact operational counts are
computed in the backend.

The Overview package is a composition layer only. Appointments, Routine Interviews, Good Moral,
Call Slips, Platform Operations, and Privacy Governance continue to own their eligibility, resource
scope, lifecycle semantics, and count queries. Overview calls those domain-owned helpers rather than
reconstructing Counselor responsibilities, Staff supervision, Student affiliation, or domain state
from serialized list responses.

### Zero and null

A numeric zero means the metric applies to the actor, the actor is authorized to know it, and the
authoritative current count is zero.

A null metric or null section means the metric is not applicable to the actor or the actor lacks the
relevant authority. Unauthorized or inapplicable metrics are never disguised as zero.

### Role and designation composition

Student metrics are available only to the canonical STUDENT role and remain capability- and
lifecycle-aware.

Guidance metrics are composed only for COUNSELOR and GUIDANCE_SERVICES_STAFF. Head Guidance
Counselor remains a COUNSELOR whose designation augments existing capabilities and organizational
scope; it does not create a replacement role. Personal Appointment and assigned Routine Interview
metrics therefore remain personal/assigned, while domain scopes such as Call Slips may become
institution-wide through the canonical organizational resolver.

Platform metrics are limited to the compatible IT_ADMIN platform-operations identity and reuse the
existing EmailDelivery summary service.

Privacy metrics require the compatible INSTITUTIONAL_OFFICER + DPO designation and effective
privacy-governance view authority. A capability override alone does not fabricate DPO identity.

### Deliberate exclusions

Overview does not expose confidential Counseling-case counts, support-indicator counts, invented
Referral pending states, Report analytics, Graduate Tracer analytics, Exit Interview obligations,
or unread Notification counts. It returns counts only and no record identities or details.

Notifications remain owned by the global Portal notification surface. Report analytics remain owned
by Reports. Cross-domain mutations remain in their owning domains.

Future record previews on the Overview must continue to use the existing authorized domain APIs
rather than turning Overview into a universal cross-domain record feed.

## Consequences

The Overview is non-persistent: no models, migrations, cache, or new capability are introduced.

The frontend receives one generated timestamp and strictly typed role/designation-aware sections,
while domain authorization remains authoritative and paginated list lengths are never treated as
totals.
