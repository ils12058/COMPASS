# ADR-096: Source/event dates and system timestamps

## Status

Accepted. Applies across domains. It does not change the Referral back-entry chronology of
[ADR-027](ADR-027-referral-foundation.md), the actual-time rules of
[ADR-021](ADR-021-counseling.md), the live/historical Call Slip issuance modes, or the slot rules of
[ADR-020](ADR-020-appointments.md). It only states them as one policy and fills the gaps below.

## Context

COMPASS replaces paper workflows, so many records describe something that happened before anyone
typed it in: a referral slip dated last week, a counseling session recorded after the fact, a
graduation years ago. The Referral, Counseling, and Call Slip flows already kept those source dates
separate from the time the record was entered. An audit of every date and datetime field found gaps
elsewhere:

- The Individual Inventory accepted a future date of birth, both from the picker and the API.
- Good Moral accepted a future graduation date when a Graduate requested a certificate or staff
  corrected it, and a future Official Receipt date in corrections.
- Dated unavailability could be created for a period that had already ended, which removes no
  bookable time.
- The booking and reschedule date pickers offered past days, which can only return no times.
- Profile and Graduate Tracer compared dates with the runtime `TIME_ZONE` calendar day, while the
  pickers use the institutional day (`INSTITUTION_TIME_ZONE`).

## Decision

COMPASS may record legitimate historical events with their actual event or source dates, and it
keeps the real time each record and action was entered. Future-only operations do not offer past
dates. Historical facts cannot use impossible future dates. Users never set system or audit
timestamps.

Two kinds of time:

- **Source/event dates** describe the real world, for example `referred_on`, `received_at`, a
  Referral action's `occurred_at`, Counseling `started_at`/`ended_at`, Call Slip `report_at`,
  `date_of_birth`, `graduation_date`, and `official_receipt_date`. Where the domain allows, they
  may be historical.
- **System timestamps** describe COMPASS's own actions: `created_at`, `updated_at`, `submitted_at`,
  `issued_at`, `prepared_at`, `activated_at`, `voided_at`, `cancelled_at`, and audit event times.
  The server sets them, no form exposes them, and back-entry never rewrites them to match a
  source date.

Rules by field:

| Field | Rule |
| --- | --- |
| Inventory `date_of_birth` and family-member dates of birth | Any past date, or today; never after today. Checked when a draft is saved and again at submission, which catches drafts saved earlier. |
| Profile `date_of_birth` | Unchanged: never after today. |
| Good Moral `graduation_date` | Never after today, when a Graduate requests a certificate and when staff correct it. |
| Good Moral `official_receipt_date` | Optional; when given, never after today. |
| Graduate Tracer birthday, examination date, year graduated | Unchanged: never after today or the current year. |
| Dated unavailability | When created, `starts_at < ends_at` and `ends_at` after server time. The start may already have passed, so an absence in progress can be recorded. Stored past periods are not revalidated. |
| Booking and reschedule dates | The picker starts at today. Today stays selectable; the server offers only times after its current time. |
| Referral, Counseling, Call Slip source times | Unchanged. Historical and back-entered values stay valid, and future values are rejected where the fact must already have happened. Call Slip `report_at` may be past, present, or future in either issuance mode. |
| Announcement expiry | Unchanged: only a published Announcement needs a future expiry. The picker starts at the current time only while published. |
| Retention `effective_on` | Policy metadata and may be historical. The editor and activation dialog warn that a past date can make already-elapsed records eligible at once. Disposition still needs separate approval. |
| Report and history filters | No minimum or maximum; only `from <= to` where a range applies. |

Good Moral checks a date only when the correction changes it, so correcting another field never
fails because of a stored date. Good Moral issuance does not re-check the graduation date.

"Today" means the institutional calendar date (`compass.common.institutional_time.institution_today`
in the backend, `institutionalDateInputValue` in the frontend). It does not use the browser's local
date or the UTC date. Picker `min` and `max` values are only a convenience; the backend enforces
every rule and returns each domain's existing validation error (422).

## Consequences

- A Student cannot save an Inventory draft with a future birth date. The editor names the field
  before it sends anything. An old draft that already holds one must be corrected before
  submission.
- The demo seeder and tests that create unavailability on fixed calendar dates pass an explicit
  `now`, which these services now accept, as other domain services already do.
- Referral, Counseling, and Call Slip still read the institutional zone from `settings.TIME_ZONE`,
  and Retention eligibility uses `timezone.localdate()`. Both equal `INSTITUTION_TIME_ZONE` on
  staging. A deployment that runs with `TIME_ZONE=UTC` would apply their calendar-day checks on
  the UTC day. Aligning them is separate work.
