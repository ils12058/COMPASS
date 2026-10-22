# Privacy and access

## Counselor and Head scope

The Home uses the current authenticated `UserSummary` and existing portal session. An ordinary Counselor sees their own self-Appointment agenda only when `getAppointmentAccess(user).canViewSelf` allows it. The Home calls the existing `/api/v1/appointments/me` endpoint; it never switches to the managed Appointment population to fill gaps.

A Head Guidance Counselor is still a Counselor for their own agenda and My work. The `HEAD_GUIDANCE_COUNSELOR` designation can reveal a separate destination area, but it does not grant a new API permission or widen the resource scope. Each candidate oversight link must remain present in `portalWorkspaceGroups(user)`; availability and managed Appointments additionally call the existing capability/access helpers.

## Data shown and excluded

The agenda shows only fields required to identify and open an authorized self-Appointment: time, status, student display name, service name, and delivery mode. Work rows use the canonical server projection's task title, authorized subject label, due/waiting context, source priority, and existing owning-workspace destination.

Home does not include Appointment purpose, counseling notes, Counselor Evaluation narratives, assessment findings, referral reasons, private Message bodies, or handoff summaries. The same exclusion applies to accessible labels and hidden descriptions; tests include a synthetic confidential purpose field and assert that it is absent from rendered text.

## Access failure and freshness

The agenda is not requested when self-view access is absent. `safeQueryData` retains data only for transient failures; on 401/403 it hides confirmed private data. Initial errors and confirmed empty results have separate user-facing states. The canonical Work Queue keeps its existing authorization and query behavior, with retry state surfaced in the Home. No write is issued by Home rendering or revalidation.

Query keys remain account-scoped through the existing API client/session infrastructure, and destination visibility is recalculated from the current user. The Counselor browser suite switches a synthetic Head Counselor session to a Student session and verifies that the former student's self-Appointment, canonical work, and Head-only destination content disappear. Student Home account-switch/session-expiry regressions also continue to pass. The Counselor suite additionally verifies restricted capabilities, no self-agenda request without self-view, and stale data hiding after 403.

## Negative checks

- A Head designation by itself produces no oversight destinations.
- Removing `appointments.view_self` suppresses the self agenda and request.
- Removing optional management capabilities suppresses corresponding Home links.
- The Head scenario makes no resource-level Appointment detail reads while Home renders.
- Synthetic private purpose text does not appear visually or in accessible page text.
- Home sends no non-GET request.

The owning APIs remain responsible for resource-level authorization when a user opens a linked record. This Home does not bypass those checks. Automated negative tests do not replace a live security review or institutional privacy assessment.
