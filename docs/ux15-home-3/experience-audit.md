# Experience and source audit

## Baseline

The fetched integration baseline is `217e1677bd78dc53640b6fb5c49e892e3ec1f734`, the HOME-2 merge. Before this slice, `PortalHome` selected Student Home for Students and Counselor Home for Counselors; Guidance Services Staff and other roles used the shared Overview. HOME-2's synthetic GSS screenshot records that former shared composition in `../ux15-home-2/screenshots/non-regression/chromium/gss-existing-overview.png`.

The shared Overview combined task rows, overview metrics, announcements, and email status. It was a broad fallback rather than a GSS operational view. Guidance staff already had canonical My Work, Guidance Operations, and domain workspaces, so a second task assembler or an Overview count dashboard was not justified.

## Verified workflow sources

- `be/compass/work_queue/services.py` composes items from Follow-Ups, Guidance Messages, Routine Interview evaluations, Good Moral preparation/issuance, and Call Slips. Each source owns its scope; the service globally orders and paginates the bounded projection. The Home displays the first page in that returned order and links back to `/portal/work`.
- `be/compass/guidance_operations/services.py` composes domain-owned, actor-scoped backlog and schedule metrics. It resolves unavailable facts as `null`; its generated timestamp belongs to the response. For GSS, the managed Appointment count is distinct from Counselor self-Appointment counts.
- `be/compass/appointments/access.py` and `be/compass/appointments/services.py` require `appointments.manage` and apply the managed-list resource scope before filters. Organizational visibility follows the actor's operational responsibility scope and excludes Counseling service records from the College-scoped path.
- The OpenAPI `appointmentsListManaged` operation supports status, date bounds, ordering, page, and page size. The Home uses only those contract parameters and the generated React Query hook.
- `portalWorkspaceGroups(user)` already presents destinations based on the current user's workspace access. The new Home selects a small subset from that list rather than adding its own role or capability policy.

## Findings that shaped the design

1. **My Work is the task source.** A task row has source identity, backend priority, waiting/due context, and its owning destination. The Home does not create separate Good Moral, Message, or Call Slip task lists.
2. **Guidance Operations is contextual.** Its returned non-null facts are presented under “Office workload”; counts do not imply individual assignment or transaction authority. `null` is omitted, while `0` remains visible.
3. **The managed schedule is separate from Counselor self appointments.** It uses the managed API, a scheduled status filter, today's institutional date range, earliest-start ordering, and a page size of five.
4. **The same count should not become three cards.** Guidance Operations is the sole summary panel for GSS; the overlapping Overview summary is disabled for this role. The managed Appointment count is omitted from the workload panel because its record preview appears in the schedule.
5. **The Sidebar remains the complete navigation system.** Home adds only a concise set of currently available office destinations, with descriptions tied to existing workspaces.

## Read-model and role limits

The shared Work Queue and Guidance Operations schemas contain work kinds and metrics that are not inherently available to every staff role. The presentation checks existing domain helpers before exposing Counselor evaluations, Good Moral preparation, or workspace links. A Good Moral issuance item, if returned to an operational viewer, is described as awaiting Counselor issuance and links to view the request; it does not become an issuance action. Routine evaluation aggregates are not shown to GSS because the existing Routine Interview access helper is Counselor-only.

No read-model gap required a backend contract change. The UI does not use the managed Appointment summary count as a substitute for the day list, does not infer booked sessions from Fixed-Date Slots, and does not fetch any separate resource query to reconstruct My Work.
