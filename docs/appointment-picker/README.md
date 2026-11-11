# Appointment-picker improvements

Implemented and validated on `codex/appointment-picker`, based on `origin/staging`
at `879f0c646473abd47978d19c1ec38386f8e459a9`. After local verification, the owner
authorized a direct push to `staging` and `vercel --prod --yes` on 2026-11-11,
without waiting for hosted CI.

## What changed

- Flexible appointment booking and the rescheduling dialog share an inline calendar
  built on `react-day-picker` 10.0.2 with COMPASS styling. It scrolls with the form,
  offers named month navigation, month/year jumps, and Go to today, and distinguishes
  today, selected date, and selected time. Keyboard interactions include arrows,
  Page Up/Down, Home/End, and Enter.
- Dates remain civil `YYYY-MM-DD` values. Calendar arithmetic uses UTC as its
  representation; the minimum and today use Philippine institutional time. Only
  backend-returned slots supply appointment instants.
- The calendar and available times share a row in sufficiently wide booking
  containers and stack on narrow containers. At extreme text enlargement the
  calendar alone can scroll horizontally, keeping the page within its width.
- Counselor choices are compact native radio rows with shared photo/initials
  identity, full names, an assigned flag, and visible focus. They use two columns
  when the container is wide enough. One eligible counselor is chosen automatically
  and shown directly, including when they are not marked as assigned.
- Shared available-time presentation preserves the existing canonical queries,
  15-second visible-page freshness checks, refresh/retry, failed refresh warnings,
  lost-selection invalidation, submission rechecks, and conflict recovery. Inputs
  cannot change while submission rechecks are running. Unconfirmed booking retries
  retain the original idempotency key. Rescheduling retains its reason, review,
  dismissal, and focus restoration.
- Service details, supported delivery modes, Inventory requirements, booking review,
  fixed-slot booking, and Group Session registration remain covered by regressions.
  Calendar navigation makes no requests for decorative availability indicators.
- Go to today remains a navigation action. It now brings the Philippine current
  day into view and gives its button visible focus, even when the current month is
  already displayed. It preserves the selected date and time; activating the
  focused day separately changes the date and clears the incompatible time.

## Verified contract gaps

`EligibleCounselorResponse` in `contracts/openapi.json` and
`be/compass/appointments/api.py` exposes only `id`, `display_name`,
`profile_photo_url`, `profile_photo_updated_at`, and `is_default`. The booking user
has no authorized biography, credentials, specialties, or other useful professional
profile information in this contract. No About action or empty information dialog
is shipped. Adding useful counselor information requires an approved backend
projection for the booking user.

The counselor endpoint has no search or pagination parameters; the service caps its
result at 50. No client-invented search/pagination is added. Bookable slots are queried
for one selected date; there is no month-availability endpoint. Unknown dates are
not marked unavailable or disabled for availability reasons.

## Validation

All browser checks used local synthetic API fixtures against a production frontend
build. They do not establish live-backend readiness or institutional approval.

| Check | Result |
| --- | --- |
| `pnpm api:generate` | Passed; no handwritten generated API edits |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm build` | Passed |
| Full Node test suite, initial picker implementation | 1169/1169 passed |
| Calendar/date semantics, today-navigation follow-up | 11/11 passed |
| Appointment picker, including today navigation | 26/26 Chromium; 26/26 WebKit |
| Existing appointment dialogs | 2/2 Chromium; 2/2 WebKit |
| Unconfirmed booking/same-request retry | 2/2 Chromium; 2/2 WebKit |
| Fixed-slot and Group Session flows | 40/40 Chromium; 40/40 WebKit |
| Compact booking entry at five widths | 5/5 Chromium; 5/5 WebKit |

Picker coverage includes 1440, 1024, 390, and 320px widths, 200% text size, long names,
photos and initials fallback, visible focus, keyboard selection, counselor loading/
empty/error states, time loading/empty/error states, failed refresh and recovery,
service/delivery/counselor/date resets, polling and submission conflicts, leap days,
year boundaries, and browser zones in Los Angeles, Manila, and Kiritimati. Tests use
the new calendar interaction instead of filling a native date input.
Today-navigation checks cover mouse and keyboard activation, repeated use in the
same month, returning from another month, a 390 × 500 viewport, preserved time
selection, and focus within the rescheduling dialog.

The browser suite is automatically discovered by `tests/run-browser-regressions.mjs`
and the frontend browser CI inventory. Hosted CI is not being awaited for this
owner-authorized staging promotion and Vercel deployment.

### Actual macOS Safari

Safari **27.0.1** was exercised through the native app against the local synthetic
preview. Date clicking, arrow/Enter selection, and visible keyboard focus worked.
In Safari Responsive Design Mode at **1280 × 500**, the page was scrolled to the
bottom of the calendar; November 29 remained selectable and available-time choices
appeared. Safari's thin native month-select rendering was corrected locally with
an explicit control appearance and chevron; automated checks assert its 44px height.

This was real desktop Safari, distinct from the automated WebKit checks. An ordinary
short-window resize and physical iPhone Safari were not verified. Screen-reader
interaction and human UAT remain unverified; the calendar uses DayPicker's semantic
grid and keyboard behavior. The saved screenshots below come from automated
Chromium/WebKit, not native Safari.
The subsequent today-navigation focus and scroll refinement was verified in
Chromium and WebKit; the native Safari observations above cover the initial picker.

## Screenshots and result records

- [Desktop booking, Chromium](evidence/chromium/appointment-picker/booking-1440.png)
- [Narrow booking, WebKit](evidence/webkit/appointment-picker/booking-390.png)
- [320px booking with 200% text, WebKit](evidence/webkit/appointment-picker/booking-320-enlarged.png)
- [Rescheduling after a conflict, WebKit](evidence/webkit/appointment-picker/reschedule-conflict.png)
- [Picker results, Chromium](evidence/chromium/appointment-picker/results.json)
- [Picker results, WebKit](evidence/webkit/appointment-picker/results.json)

Other result records and screenshots are grouped by engine and suite under
`evidence/`. Superseded failure screenshots have been removed.

## Reproduce locally

From `fe/`:

```sh
pnpm install --frozen-lockfile
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
pnpm test
pnpm start --port 3107
```

With that production server running, use another terminal in `fe/`:

```sh
COMPASS_UI_ARTIFACTS=../docs/appointment-picker/evidence pnpm test:ui:regressions --suite appointment-picker.browser.mjs
COMPASS_UI_ARTIFACTS=../docs/appointment-picker/evidence pnpm test:ui:regressions --suite svc-ux-1.browser.mjs
COMPASS_UI_ARTIFACTS=../docs/appointment-picker/evidence pnpm test:ui:regressions --suite simplify-3c-booking.browser.mjs
```

For the focused existing-dialog and uncertain-retry checks, run each engine with
`COMPASS_UI_BROWSER=chromium` or `COMPASS_UI_BROWSER=webkit`:

```sh
COMPASS_UI_CHECK='appointment-dialogs|mobile-sort-and-dialog' node tests/ui-information-hierarchy.browser.mjs
COMPASS_UI_CHECK='booking-server-error-same-intent' node tests/user-copy.browser.mjs
```

For an optional native Safari preview, run
`node tests/support/appointment-picker-preview.mjs` while the frontend runs on 3107,
then open `http://127.0.0.1:3112/portal/appointments/book` in Safari. The preview
terminates every `/api/` request locally and refuses mutations.
