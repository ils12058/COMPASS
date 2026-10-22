# Experience audit

## Existing Counselor path

At the verified integration baseline `1d8dcd3eb413955718904c1acb8e0b87d8766053`, `PortalHome` had a dedicated Student composition. Other roles shared the Overview layout: `OverviewAttention`, announcements, and a supporting summary panel. The professional attention projection already combined authorized canonical Work Queue items with role-applicable actions. The work queue itself came from `useWorkQueue`; `OverviewSummary` represented counts returned by the Overview API.

Counselor pages already provided the full professional destinations: `/portal/work`, `/portal/appointments/my`, the managed Appointment routes where permitted, and source workspaces such as Routine Interviews, Follow-Ups, Counseling, Messages, Assessment Records, Referrals, Call Slips, and Good Moral. The Home did not show a compact list of the Counselor's appointments for today. The general attention list mixed action types in the established canonical projection but did not orient the day around a schedule. Users had to open a separate workspace to see that schedule.

## Head designation and limits

`HEAD_GUIDANCE_COUNSELOR` is a designation carried by a Counselor account. Review of the established access policy (including ADR-099) confirmed that Head designation does not itself provide all-Counselor Appointment access or broad access to Counseling records. Self-provider Appointment access and operational-management capabilities are separate. Reports, Organization, availability, service management, and managed Appointments each remain governed by the existing destination visibility or capability helper.

No Head-specific aggregate queue or Head-only count was present in the audited source projections that could safely be added here. The new section therefore provides checked navigation only; it does not manufacture workload or oversight statistics.

## Authoritative projections and helpers

| Need | Existing source used | Boundary |
| --- | --- | --- |
| Today's schedule | `useAppointmentsListMy` / `/api/v1/appointments/me` | enabled only by `getAppointmentAccess(user).canViewSelf`; no managed list fallback |
| Professional tasks | `useOverviewAttention` → `useWorkQueue` / `/api/v1/work` | backend owns item scope, ordering, priority, page size, and source links |
| Supporting counts | Existing Overview summary and `getOverviewMetrics` | backend definitions retained; missing/null values are not changed into zero |
| Common continuations | `portalWorkspaceGroups(user)` | only destinations already visible to the user; limited to four |
| Head oversight | `portalWorkspaceGroups`, `canManageAvailability`, `getAppointmentAccess` | designation gates presentation only; each destination needs its existing permission |
| Announcements | `OverviewAnnouncements` | existing audience filter, order, pinned treatment, and route behavior |

## UX opportunities addressed

- Make the day's self-appointments visible beside the primary professional queue.
- Keep each projection independent so a failed agenda does not hide work, and vice versa.
- Keep one canonical queue while making the existing five-item boundary explicit when another page exists.
- Offer a small set of contextual workspace links rather than duplicating the full navigation.
- Give capability-authorized Heads a separate, clearly named route group without implying broader record access.
- Put announcements after schedule, work, and supporting context so they do not displace daily responsibilities.

The implementation deliberately does not create student case continuity, merge unrelated records by student, or recalculate a competing priority order.
