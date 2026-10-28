# Information architecture

## Final hierarchy

1. Compact time-of-day greeting, Counselor name, Philippine institutional date, and existing role/designation context.
2. A two-column first work area at wide content widths: Today's appointments and My work. It collapses into one readable column at narrower widths.
3. Continue in your workspace, capped at four routes found in the existing role-visible workspace groups.
4. Supporting column with Authorized oversight when the account is Head-designated and has matching capabilities, followed by the existing Overview summary.
5. Existing announcements after the work areas.

The page does not add a full calendar, duplicate action cards, or a new global navigation system.

## Today's appointments

`CounselorAgenda` calls the generated `useAppointmentsListMy` hook only when `getAppointmentAccess(user).canViewSelf` is true. It requests `status=SCHEDULED`, the same `from_date` and `to_date` in `Asia/Manila`, `EARLIEST_START`, page 1, and page size 5. The current institutional date is recalculated once per minute while the Counselor Home is open. The preview keeps API order and does not infer that an Encounter exists or that an appointment is in progress.

Each row uses semantic `<time>` values for start and end, the existing Appointment status badge, the authorized student display name, service, delivery mode, and a direct link to the owning Appointment. The complete-day link passes the exact scheduled status and Manila date to the existing self Appointments workspace. When `has_next` is true, the preview says that more appointments are scheduled today. When the authorized query succeeds empty, it says no scheduled appointments are available today.

## My work

The existing `OverviewAttentionData` is rendered as a dedicated My work list. The first five backend-ordered items retain their source-specific label, context, and route. Only a server-provided `TIME_SENSITIVE` priority gets the existing “Time sensitive” label. `has_next` becomes an explicit “first 5” notice, and “View all work” opens `/portal/work`. A retry action is offered on a work query error. No due-date ranking is recomputed by Home.

## Continuation and oversight

The ordinary Counselor links are drawn from the existing `portalWorkspaceGroups(user)` route list and capped at four. Links currently include role-visible destinations such as Routine Interviews, Follow-Ups, Counseling, Messages, Assessment Records, Guidance operations, Referrals, Call Slips, and Good Moral.

The separate Authorized oversight list appears only for an actual Counselor with the Head designation and only for links still present in their workspace groups. Availability also checks `canManageAvailability`; managed Appointments also checks `getAppointmentAccess(user).canManage`. Reports, Organization, and Services similarly rely on the existing route visibility. No aggregate count is inferred from the designation.

## Supporting summary and announcements

The existing Overview summary component, data, links, null behavior, and count semantics are passed through unchanged. It remains supporting context and is not relabeled as today's work. Announcements continue to use their existing component and behavior, lower in the reading order.

## Query states and revalidation

- Pending: skeletons and accessible loading regions.
- Confirmed empty: an explicit agenda empty state; an empty work queue does not claim all professional responsibilities are complete.
- Transient failure with confirmed data: last confirmed rows remain visible with a stale notice and retry.
- Initial failure: an error and retry, not an empty-state message.
- Access denial: `safeQueryData` does not expose data after 401/403; an unauthorized agenda is not shown as empty.
- Projection refresh: periodic refresh plus focus/reconnect handling through query settings and the existing projection invalidation hook.

Agenda and work data remain independent so one section can stay useful while the other fails.

## Responsive composition

The first row uses CSS container breakpoints; agenda and work panels reflow to one column in constrained widths. Continuations and summary also stack. Long synthetic names and labels wrap. Tests measure page and panel overflow, link collisions/focusability, and primary action target heights at 320, 360, 390, 768, 1024, and 1440 CSS pixels with normal and 200% root text size. This is root-font enlargement testing, not browser zoom certification.
