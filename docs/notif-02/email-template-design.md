# Appointment email presentation

The five existing Appointment template pairs cover seven events: Scheduled,
Rescheduled, Reassigned, Cancelled and a shared Reminder pair for the three
occurrence types. Subjects, headings, preheaders, help/footer copy and template
selection remain code-owned. An absent approved detail tuple retains existing
generic copy; the Scheduled template retains its qualified NOTIF-01 link branch.
Event-code-only previews remain generic and require no source context.

## Controlled detail adapter

Appointments resolves frozen `AppointmentEmailFacts` and `AppointmentEmailDetail`
rows using the closed `AppointmentEmailField` vocabulary. Notifications filters
rows through its Student/current-Counselor field sets before creating the plan.
The renderer verifies policy version, event/target/class binding, typed rows,
allowed fields, duplicate fields and the rebuilt trusted link. Only the approved
tuple and code-rebuilt `action_url` enter the existing Django rendering engine.
No source model, arbitrary payload or template dictionary from a caller is used.

The HTML partial renders a semantic table with an accessible name and row header
cells (`scope=row`). Inline styles provide readable spacing, fixed table layout
and wrapping for long values; label width is 36%. The shared shell supplies its
existing responsive maximum width, typography, branding and footer. No script,
image, tracker, external stylesheet, font or embedded resource is introduced.

The text partial prints the identical ordered label/value pairs. HTML autoescape
stays on. Text-only values preserve literal ampersands/angle brackets with
autoescape disabled only inside the typed plain-text detail partial; strings
cannot execute HTML in a text body. Plain-string validation rejects SafeString
objects, controls, oversized values and URI/address-like labels. Unsafe optional
Service/provider labels are omitted; required invalid provenance falls back.

## Fact semantics and time

- Reference is the canonical source reference; Service uses the stored immutable
  Service-name snapshot, never a fresh catalog label or description.
- Scheduled uses unchanged initial facts only. Rescheduled shows the exact source
  previous and new intervals, with distinct previous/updated labels.
- Reassigned shows the new provider's current name to the Student. Previous names
  are omitted. Current Counselor names are labeled as current, not historical.
- Cancellation shows the retained cancelled interval and no provider name, Join
  action, private reason, new booking promise or active-session wording.
- Reminder details describe the verified occurrence revision and current source.
- Institution time uses the existing timezone helper. Asia/Manila displays
  Philippine Time, weekday/month/day/year and 12-hour start/end times. Cross-date
  intervals show both dates. Naive, zero-length and negative intervals are rejected.

All rich actions say “View Appointment in COMPASS”. The destination comes from
the NOTIF-01 HTTPS-origin validator and closed UUID route. The text version prints
the same URL; no credentials/query parameters/meeting links are included. Missing
or invalid origin prevents rich details and gives the safe minimal presentation.
The record endpoint and existing login/MFA continuation remain authoritative.

See [preview evidence](screenshots.md) for twelve HTML/text pairs, an explicit
suppression record, desktop/mobile screenshots and long/missing optional labels.
Local Chromium rendering is layout evidence only; Gmail/Outlook testing is pending.
