# SVC-UX-2

This slice clarifies the three supported Service booking pathways and adds a scoped staff entry
point for fixed-date appointment slots.

## Implementation

- Services list and detail copy now distinguish flexible appointment configuration, scheduled
  slots, and Group Sessions from actual availability.
- The flexible appointment filter is named for `appointment_booking_enabled`; no frontend-only
  pathway filter or unbounded catalog fetch was added.
- Counselors and directly supervised Guidance Services Staff with `appointments.manage` can reach
  `/portal/appointments/slots` without `services.manage`.
- The operational page uses the existing catalog, provider-candidate, slot, publication, and
  withdrawal APIs. Backend scope remains authoritative.
- Fixed-slot mutations now open the shared recent-MFA dialog when the backend requests step-up.
  Verification refreshes state and requires a fresh explicit confirmation rather than replaying
  the mutation.

The verified starting checkout was the repository's current `staging` checkout; it was not
repointed or merged automatically. No deployment, live-data operation, or institutional policy
change was performed.

## Limitations

The current generated contract does not expose a general fixed-pathway catalog filter or a
historical inactive-Service projection for scoped operators. The operational selector therefore
uses bounded catalog pages and reports page-local results honestly. The fixed-slot Inventory
exception mapping and the four Feedback/CSM browser failures remain validation debt and are
carried to SVC-UX-3.

