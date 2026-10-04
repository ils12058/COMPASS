import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  BOOKING_UNCONFIRMED,
  bookedAppointmentFromResponse,
  classifyBookingFailure,
} from "../src/features/appointments/appointment-booking-outcome.ts";
import { SLOT_JUST_TAKEN } from "../src/features/appointments/appointment-slot-freshness.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

const apiError = (status, code, message = code) =>
  new CompassApiError({ status, body: { error: { code, message } }, headers: {}, method: "POST", url: "/api/v1/appointments" });

const source = readFileSync(new URL("../src/features/appointments/appointment-booking-page.tsx", import.meta.url), "utf8");

test("each booking failure is shown at the step that can resolve it", () => {
  assert.deepEqual(classifyBookingFailure(apiError(409, "appointment_time_unavailable")), { step: "time", message: SLOT_JUST_TAKEN });
  assert.equal(classifyBookingFailure(apiError(409, "appointment_time_conflict")).step, "time");

  const service = classifyBookingFailure(apiError(409, "appointment_not_schedulable"));
  assert.equal(service.step, "service");
  assert.match(service.message, /Choose from the current Services\.$/);

  const conflict = classifyBookingFailure(apiError(409, "idempotency_key_conflict"));
  assert.equal(conflict.step, "review");
  assert.equal(conflict.keepIntent, false);
  assert.equal(conflict.uncertain, false);

  const refused = classifyBookingFailure(apiError(400, "validation_error"));
  assert.deepEqual({ step: refused.step, uncertain: refused.uncertain, keepIntent: refused.keepIntent }, { step: "review", uncertain: false, keepIntent: true });
});

test("an unread response stays persistent beside Book and keeps the retry-safe booking key", () => {
  const unknown = classifyBookingFailure(new TypeError("Failed to fetch"));
  assert.deepEqual(unknown, { step: "review", message: BOOKING_UNCONFIRMED, uncertain: true, keepIntent: true });
  // The key is reused for the exact same details, so a retry returns the booking already made.
  assert.match(source, /intentRef\.current\?\.fingerprint === fingerprint\s*\?\s*intentRef\.current\.key/);
  assert.match(source, /if \(!failure\.keepIntent\) intentRef\.current = null;/);
  assert.match(source, /bookingError\?\.uncertain \? "Retry booking" : "Book appointment"/);
});

test("errors render inside their own steps, never below the whole sheet", () => {
  const at = (marker) => source.indexOf(marker);
  const service = at('title="1. Choose a Service"');
  const delivery = at('title="2. Choose delivery mode"');
  const time = at('title="4. Choose date and time"');
  const review = at('title="5. Review appointment"');
  const footer = at("<PanelFooter>");
  const serviceError = at("{serviceError ? (");
  const timeError = at("{timeError ? (");
  const bookingError = at("{bookingError ? (");
  assert.ok(service < serviceError && serviceError < delivery, "Service errors stay with the Service step");
  assert.ok(time < timeError && timeError < review, "time errors stay with the time step");
  assert.ok(review < bookingError && bookingError < footer, "final errors sit with the review and Book");
  // Nothing after the sheet but the completion dialog.
  const afterSheet = source.slice(source.indexOf("</Panel>", footer));
  assert.doesNotMatch(afterSheet.slice(0, afterSheet.indexOf("function BookingCompletion")), /<Notice/);
});

test("the review is the confirmation: Book submits directly, with no extra 'are you sure' step", () => {
  assert.doesNotMatch(source, /ConsequentialActionDialog|AlertDialog|Are you sure/);
  assert.match(source, /onClick=\{\(\) => void bookAppointment\(\)\}/);
  // The time is still rechecked before the request, and the slot freshness policy is unchanged.
  assert.ok(source.indexOf("await slots.refetch()") < source.indexOf("create.mutateAsync("));
  assert.match(source, /\.\.\.appointmentSlotFreshness/);
});

test("a confirmed booking opens one completion dialog and cannot be submitted twice", () => {
  const success = source.slice(source.indexOf("const response = await create.mutateAsync("), source.indexOf("} catch (caught) {", source.indexOf("const response = await create.mutateAsync(")));
  assert.ok(success.indexOf("setBooked(") > success.indexOf("response.data"), "the dialog follows the server's answer");
  assert.match(success, /getAppointmentsListMyQueryKey\(\)/);
  assert.match(success, /getAppointmentsListBookableSlotsQueryKey\(\)/);
  assert.match(source, /disabled=\{submitting \|\| booked !== null \|\|/);
  // Done starts a new booking instead of leaving a spent review behind.
  assert.match(source, /function finishBooking\(\) \{\s*setBooked\(null\);\s*changeService\(null\);/);
  assert.match(source, /<DialogTitle>Appointment scheduled<\/DialogTitle>/);
  assert.match(source, /href=\{`\/portal\/appointments\/\$\{booked\.id\}`\}[^>]*>\s*View appointment/);
  assert.match(source, /onOpenAutoFocus=\{\(event\) => \{\s*event\.preventDefault\(\);\s*viewLink\.current\?\.focus\(\);/);
});

test("the completion states only the safe facts the review showed", () => {
  const booked = bookedAppointmentFromResponse({
    id: "a1",
    reference_code: "APT-7K2Q",
    service: { id: "s1", code: "COUNS", name: "Counseling" },
    provider: { id: "p1", display_name: "Maria Santos" },
    student: { id: "u1", display_name: "Ana Cruz", institutional_id: "2023-0001" },
    student_id: "u1",
    delivery_mode: "IN_PERSON",
    starts_at: "2026-10-06T06:00:00Z",
    ends_at: "2026-10-06T07:00:00Z",
    status: "SCHEDULED",
    created_at: "2026-10-05T00:00:00Z",
    cancellation_cutoff_minutes: 120,
    cancelled_at: null,
    completed_at: null,
    no_show_at: null,
  }, { assignedCounselor: true, timeZone: "Asia/Manila" });

  assert.equal(booked.referenceCode, "APT-7K2Q");
  assert.deepEqual(booked.facts.map((fact) => fact.label), ["Reference", "Service", "Counselor", "Schedule", "Delivery", "Duration"]);
  const values = booked.facts.map((fact) => fact.value).join(" | ");
  assert.match(values, /Maria Santos · Assigned counselor/);
  assert.match(values, /2:00/);
  assert.match(values, /In person/);
  assert.match(values, /60 minutes/);
  assert.doesNotMatch(values, /Ana Cruz|2023-0001|u1|SCHEDULED/);
});
