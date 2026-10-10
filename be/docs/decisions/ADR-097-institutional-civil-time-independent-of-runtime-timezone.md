# ADR-097: Institutional civil time independent of the runtime timezone

## Status

Accepted. Follows [ADR-096](ADR-096-source-event-dates-and-system-timestamps.md). Where
[ADR-019](ADR-019-availability.md), [ADR-020](ADR-020-appointments.md), or
[ADR-021](ADR-021-counseling.md) say UCN civil time is interpreted in `settings.TIME_ZONE`, read it
as `INSTITUTION_TIME_ZONE`.

## Context

The documented configuration is `TIME_ZONE=UTC` for Django and Celery and
`INSTITUTION_TIME_ZONE=Asia/Manila` for UCN civil time. `compass.common.institutional_time` already
existed, and Appointments, Availability, and activity retrieval used it. Several other places still
took UCN dates from the runtime zone:

- Referral, Counseling, and Call Slip each defined a private zone from `settings.TIME_ZONE`.
- Retention eligibility, privacy notice publication, and Graduate Tracer disposition used
  `timezone.localdate()`.
- Feedback and Graduate Tracer review/report filters built day boundaries in the current zone.
- Documents and labels took dates from `timezone.localtime(...)` or from `.date()` of a UTC
  instant: the Referral and Call Slip slips, the Good Moral `issued_on`, the Inventory submission
  date and age, profiling-report ages, the Exit Interview age, and E-Counseling artifact filenames.
- Email operations counted "sent today" from the runtime midnight.
- The demo seeder placed business-hours activity in the runtime zone.

Under the documented UTC runtime, all of these switch days at 08:00 Manila. Midnight-to-08:00
records got the previous day's date, filters, and checks. Referral reference years rolled over at
08:00 on 1 January. The Call Slip template also converted an aware interview-end time back to UTC.

## Decision

Every UCN civil date or time comes from `compass.common.institutional_time`. That covers "today"
rules, calendar-date filters, business-day placement, reference years, and controlled-form or
label dates. Two small helpers were added:

- `institution_date(instant)`: the Manila calendar day of an aware instant.
- `institution_day_start(day)`: the aware instant at which a Manila day begins. Date filters use
  `[institution_day_start(from), institution_day_start(to + 1))`.

Instants stay aware and are stored and compared as instants. Retention durations stay exact instant
arithmetic. Templates receive civil `date` and `time` objects, not aware datetimes, because Django
template filters convert aware values to the runtime zone. Counseling API timestamps now carry the
institutional offset, as Appointment timestamps already did. They denote the same instants.

Good Moral preparation and final issuance refuse a certificate whose `graduation_date` or
`official_receipt_date` is after the institutional date of that action. This covers rows saved
before ADR-096, imported rows, and anything that bypassed write validation. The stored date is
never changed. The error code is `good_moral_certificate_date_in_future` (409), and the message
names the date to correct.

## Retained runtime-zone uses

- Naive datetimes accepted by the capability-override expiry and maintenance-window inputs are
  read as runtime time. The frontend always sends offset-qualified values, so changing this would
  only reinterpret malformed input.
- Appointment interval checks widen the availability query by UTC calendar dates. The window is a
  superset of the Manila day, and scheduling behavior is unchanged.
- Report "generated at" stamps print with an explicit offset or zone label.
- Celery beat runs fixed intervals, not wall-clock schedules.

## Consequences

`TIME_ZONE=UTC` with `INSTITUTION_TIME_ZONE=Asia/Manila` is correct at Manila midnight and at New
Year without relying on a runtime override. Tests that built boundary times in the current zone now
build them in the institutional zone. Boundary tests run with an explicit UTC runtime.
