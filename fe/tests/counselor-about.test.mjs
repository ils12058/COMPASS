// CW-6: Counselor About presentation and the Messages Appointment summary. Pure modules only.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  ABOUT_EMPTY_COPY,
  aboutCampusRows,
  aboutError,
  assignmentBasisNote,
} from "../src/features/counselor-about/counselor-about-presentation.ts";
import {
  appointmentStatusLabel,
  appointmentSummaryLabel,
  threadAppointmentLabel,
  threadAppointmentWithheld,
  threadCounselorIdentity,
} from "../src/features/guidance-messages/guidance-messages-presentation.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

const about = (campuses) => ({
  counselor: { id: "c1", display_name: "Ana Cruz", profile_photo_url: null, profile_photo_updated_at: null },
  campuses,
  checked_at: "2026-11-14T00:00:00Z",
});
const college = (id, name, basis = "ASSIGNED", code = id.toUpperCase()) => ({ id, code, name, basis });

test("About groups Colleges by Campus and marks Head fallback, never as a direct assignment", () => {
  const rows = aboutCampusRows(about([
    { id: "m", code: "MAIN", name: "Main Campus", colleges: [college("a", "College of Arts"), college("b", "College of Business", "HEAD_FALLBACK")] },
    { id: "n", code: "NORTH", name: "", colleges: [college("c", "", "ASSIGNED", "CCMS")] },
    { id: "e", code: "EMPTY", name: "Empty Campus", colleges: [] },
  ]));
  assert.deepEqual(rows, [
    { id: "m", name: "Main Campus", colleges: [
      { id: "a", name: "College of Arts", note: null },
      { id: "b", name: "College of Business", note: "Covered while no Counselor is assigned" },
    ] },
    { id: "n", name: "NORTH", colleges: [{ id: "c", name: "CCMS", note: null }] },
  ]);
  assert.equal(assignmentBasisNote("ASSIGNED"), null);
  assert.deepEqual(aboutCampusRows(about([])), []);
  assert.match(ABOUT_EMPTY_COPY, /No current College assignment/);
});

test("About refusals are final and plain; other failures can be retried", () => {
  const failure = (status) => new CompassApiError({ status, body: { error: { code: "x", message: "backend text" } }, headers: {}, method: "GET", url: "/api/v1/organization/counselors/c1/about" });
  assert.deepEqual(aboutError(failure(404)), { message: "This Counselor's details aren't available.", retryable: false });
  assert.deepEqual(aboutError(failure(403)), { message: "Your account can't view Counselor details.", retryable: false });
  assert.equal(aboutError(failure(500)).retryable, true);
  assert.equal(aboutError(new TypeError("network")).retryable, true);
  for (const status of [403, 404, 500]) assert.doesNotMatch(aboutError(failure(status)).message, /backend text/);
});

const summary = (overrides = {}) => ({
  id: "apt", reference_code: "APT-2026-0001", service_name: "Counseling",
  starts_at: "2026-10-09T01:00:00Z", ends_at: "2026-10-09T02:00:00Z", status: "SCHEDULED", ...overrides,
});
const thread = (overrides = {}) => ({
  id: "t", kind: "COUNSELING", status: "OPEN", student: { id: "s", display_name: "Maria Santos" },
  counselor: { id: "c1", display_name: "Ana Cruz", profile_photo_url: "https://photos.example.test/a.jpg", profile_photo_updated_at: "2026-11-01T00:00:00Z" },
  relationship_appointment_id: "apt", relationship_appointment: summary(), ...overrides,
});

test("an authorized Appointment summary tells several conversations with one Counselor apart", () => {
  // The Service is always Counseling here, so it is not repeated beside the conversation kind.
  assert.match(threadAppointmentLabel(thread()), /^Appointment APT-2026-0001 · Oct 9, 2026.* · Scheduled$/);
  assert.match(threadAppointmentLabel(thread({ relationship_appointment: summary({ status: "CANCELLED", service_name: " " }) })), /^Appointment APT-2026-0001 · Oct 9, 2026.* · Cancelled$/);
  assert.match(appointmentSummaryLabel(summary({ service_name: "Career Counseling" })), /^Career Counseling · Oct 9, 2026/);
  // Same time, same Counselor: the reference still separates them.
  const same = { starts_at: "2026-10-09T01:00:00Z" };
  assert.notEqual(threadAppointmentLabel(thread({ relationship_appointment: summary(same) })), threadAppointmentLabel(thread({ relationship_appointment: summary({ ...same, reference_code: "APT-2026-0002" }) })));
  assert.equal(appointmentStatusLabel("NO_SHOW"), "No show");
  assert.match(appointmentSummaryLabel(summary({ status: "COMPLETED" })), /Completed$/);
});

test("a withheld Appointment is never reconstructed from the historical link", () => {
  const withheld = thread({ relationship_appointment: null });
  assert.equal(threadAppointmentLabel(withheld), null);
  assert.equal(threadAppointmentWithheld(withheld), true);
  assert.equal(threadAppointmentWithheld(thread()), false);
  assert.equal(threadAppointmentWithheld(thread({ kind: "OFFICE", relationship_appointment_id: null, relationship_appointment: null })), false);
});

test("the Counselor photo identity appears only where the Counselor is the conversation's identity", () => {
  assert.equal(threadCounselorIdentity(thread(), "student")?.id, "c1");
  // Staff see the Student as the conversation's identity, and Office conversations stay the office.
  assert.equal(threadCounselorIdentity(thread(), "staff"), null);
  assert.equal(threadCounselorIdentity(thread({ kind: "OFFICE", counselor: null }), "student"), null);
});

test("About is a separate button beside each choice, never inside a selecting label", () => {
  const booking = readFileSync(new URL("../src/features/appointments/booking-counselor-choice.tsx", import.meta.url), "utf8");
  const labelBlock = booking.slice(booking.indexOf("<label"), booking.indexOf("</label>"));
  assert.ok(!labelBlock.includes("CounselorAboutButton"), "About must not be inside the radio label");
  const dialog = readFileSync(new URL("../src/features/counselor-about/counselor-about-dialog.tsx", import.meta.url), "utf8");
  assert.match(dialog, /type="button"/, "About never submits the form it sits in");
  assert.match(dialog, /staleTime: 0, gcTime: 0/, "About keeps no cached copy after it closes");
  assert.ok(!/localStorage|sessionStorage|indexedDB/.test(dialog));
});
