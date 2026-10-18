# COMPASS-CAL-1 — Appointment Calendar Views

## Baseline audit

1. **Pages:** `My Appointments` is the self-scoped collection for Students and authorized staff. `Manage Appointments` is the staff-managed collection. Both already link to the existing Appointment Details route.
2. **API sufficiency:** the existing `/api/v1/appointments/me` and `/api/v1/appointments` list endpoints accept `from_date` and `to_date` and return the appointment data needed for calendar entries. Responses are paginated with a maximum page size of 50, so the calendar follows all returned pages for the selected period.
3. **Backend support:** no backend change or calendar endpoint was needed. Existing server authorization scopes remain authoritative.
4. **Statuses and roles:** the calendar honors the current page status/search/service/delivery/date filters and supports Scheduled, Cancelled, Completed, and No-show appointments. The list’s Scheduled default remains intact. My Appointments remains self-scoped; Manage Appointments uses the same managed endpoint and server scope as before.
5. **Privacy and time:** Student tiles show service, time, and status without counselor, student, or reference identifiers. Staff tiles show student name, service, time, and status without institutional ID or reference. Visible dates and times use the browser’s local timezone; query boundaries are derived from the visible local period and converted to institution-local dates expected by the API. The appointment instant remains canonical.

## Implementation

- Added List/Calendar controls to My Appointments and Manage Appointments while retaining both existing list workflows.
- Added desktop Month and Week views with Today, previous/next period navigation, a highlighted current day, status-aware event labels, and links to the existing details page.
- Dense month cells display up to three appointments and provide a “more” action that opens the relevant week.
- On narrow screens, calendar views use a scrollable date agenda rather than a compressed seven-column grid.
- Existing search and filters stay applied when switching views. The floating filter bar is hidden while the calendar is active to keep it from covering events; switch to List to edit filters.
- Empty periods show a clear message while keeping the calendar navigation and date grid available.

## Screenshots

All captures use synthetic appointments and local browser fixtures. No real student, counseling, or live backend data was used.

| Evidence | Screenshot |
| --- | --- |
| Before — My Appointments list | [before-my-list.png](fe/docs/evidence/compass-cal-1/appointments-calendar/before-my-list.png) |
| Before — Manage Appointments list | [before-manage-list.png](fe/docs/evidence/compass-cal-1/appointments-calendar/before-manage-list.png) |
| After — My Appointments list | [after-my-list.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-my-list.png) |
| After — My Appointments calendar | [after-my-calendar-month.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-my-calendar-month.png) |
| After — Manage Appointments list | [after-manage-list.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-manage-list.png) |
| After — Manage Appointments calendar | [after-manage-calendar-month.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-manage-calendar-month.png) |
| Desktop month | [after-desktop-month.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-desktop-month.png) |
| Desktop week | [after-desktop-week.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-desktop-week.png) |
| Mobile agenda | [after-mobile-calendar-agenda.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-mobile-calendar-agenda.png) |
| Empty calendar | [after-calendar-empty.png](fe/docs/evidence/compass-cal-1/appointments-calendar/after-calendar-empty.png) |

Browser case results are recorded in [results.json](fe/docs/evidence/compass-cal-1/appointments-calendar/results.json).

## Validation

- `pnpm lint` — passed
- `pnpm typecheck` — passed
- `pnpm test` — passed, 818 tests
- `pnpm build` — passed
- Synthetic browser suite — passed, 7/7 scenarios (role-safe labels, list/calendar switching, month navigation, Today, browser-local time, pagination, dense-day week navigation, detail link, mobile agenda, and empty state)

## Responsive and accessibility notes

- The List/Calendar, Month/Week, Today, and period-navigation controls are labeled buttons with visible focus styles; toggle state is exposed through `aria-pressed`.
- Event links have a screen-reader label that includes the local date/time, role-appropriate title, status, and details action.
- Current dates are marked with `aria-current="date"`; period headings announce changes politely.
- Mobile uses an agenda list and the 320px browser scenario verified that no horizontal page overflow occurs.

## Known limitations and possible follow-up

- The operational view is Week; there is no separate single-day mode. Month and Week satisfy the current role needs without adding another view state.
- Recurrence, availability editing, drag-to-reschedule, calendar sync, and booking from the grid remain out of scope.
- Users edit current search and filter criteria in List view; active criteria continue to constrain the calendar.
- A future enhancement could add compact date and filter controls directly to the calendar if users need to refine criteria without returning to List.
