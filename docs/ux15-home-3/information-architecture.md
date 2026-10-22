# Information architecture

## Page order

The GSS page follows the requested operational sequence:

1. **My work** — first five items from the authorized Work Queue response, in server order, with source title, Student reference, source priority where time-sensitive, due/waiting context, and destination-specific link.
2. **Today's managed Appointments** — when `getAppointmentAccess(user).canManage` is true, show up to five scheduled Appointments from today in `Asia/Manila`, in earliest-start order. Show time, Student name, Service, assigned Counselor, delivery mode, status, and a detail link. The full schedule link preserves the date and scheduled-status filters.
3. **Office workload** — the available Messages, Good Moral preparation/issuance, and Call Slip due aggregates. Good Moral issuance is explicitly awaiting Counselor action. Routine Evaluation counts remain absent for GSS.
4. **Continue in your workspaces** — at most six destinations selected from `portalWorkspaceGroups(user)` in operational priority order. Referrals is included ahead of the Follow-Up workspace when both are available because task-level Follow-Ups already appear in canonical My Work; the full Sidebar remains available for every authorized workspace.
5. **Announcements** — retained as secondary supporting context.

On wider containers, task and schedule regions use the primary column, while operational context and destinations use the secondary column. At narrower widths the regions stack in the same reading and DOM order. The layout uses the existing Panel, PageHeader, design-token, and focus styles.

## Data states

Each source remains independent:

- Initial pending states show local loading placeholders.
- A confirmed empty queue, schedule, or zero-count workload is stated within its own region.
- A transient refresh error keeps last-confirmed data with an explicit stale notice and Retry.
- An initial failure is an alert with Retry, not an empty state.
- A 401/403 result does not reuse protected cached data. A missing `appointments.manage` capability omits the schedule region and makes no managed-list request.
- Work Queue pagination is unchanged. If the backend reports a next page, the preview says it is incomplete and links to the full queue.
- Guidance Operations' `generated_at` and Work Queue's `generated_at` are shown as their source timestamps.

No new cache was added. The managed schedule uses the generated managed-list query, focus/reconnect refresh, the existing Appointment query family, and a bounded one-minute refresh interval consistent with the existing Home agenda freshness convention. Work Queue and Guidance Operations keep their existing refresh/invalidation behavior.

## Labels and links

“Managed Appointments” identifies office coordination scope; it does not call them the GSS user's counseling sessions. Appointment times identify Philippine Time. Service, provider, status, and Student display identity come from the managed Appointment response. The Home never renders Appointment purpose or Counseling narrative.

Work actions are source-owned navigation only. The Home adds no direct issuance, preparation, reassignment, reminder, Call Slip, Referral, Message, Follow-Up, or evaluation mutation.
