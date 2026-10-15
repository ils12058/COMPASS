// CE-1: Institutional ID in the session's Record encounter preset, honest actual-time entry, and
// one validation and payload contract for recording and correction. Synthetic records only.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { formatAppointmentDateTime } from "../src/features/appointments/appointments-shared.tsx";
import { actualTimeIssues, firstActualTimeIssue } from "../src/features/counseling/actual-time-fields.tsx";
import { EncounterCorrectionForm, encounterCorrectionPayload, savedEncounterTimeInput } from "../src/features/counseling/encounter-correction-form.tsx";
import { RecordEncounterForm, encounterCreatePayload } from "../src/features/counseling/record-encounter-form.tsx";
import { sessionEncounterPreset } from "../src/features/ecounseling/ecounseling-shared.ts";
import { institutionalDateTimeInputToISO } from "../src/lib/institutional-time.ts";

// The browser's zone is not the institution's: every time below is still read in Philippine Time.
process.env.TZ = "America/Los_Angeles";

const NOW = Date.parse("2026-10-13T14:30:00Z"); // 10:30 PM in Manila
const SCHEDULED = { starts_at: "2026-10-13T13:00:00Z", ends_at: "2026-10-13T14:00:00Z" }; // 9–10 PM

function workspace({ id = "appointment-a", student = { id: "student-a", display_name: "Synthetic Student A", institutional_id: "SYNTH-2026-0203" } } = {}) {
  return {
    appointment: { id, reference_code: `APT-${id}`, status: "SCHEDULED", delivery_mode: "ONLINE", ...SCHEDULED },
    student,
    counseling_encounter: null,
    counseling_context_available: true,
    routine_interview: null,
  };
}

function render(element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, element)));
  client.clear();
  return html;
}

test("the test runs in a browser zone other than the institution's", () => {
  assert.notEqual(new Date(NOW).getTimezoneOffset(), -480);
});

test("actual times are checked per field with specific messages", () => {
  assert.deepEqual(actualTimeIssues("", "", NOW), { start: "Enter the actual start time.", end: "Enter the actual end time." });
  assert.deepEqual(actualTimeIssues("2026-10-13T21:05", "", NOW), { end: "Enter the actual end time." });
  assert.deepEqual(actualTimeIssues("", "2026-10-13T21:50", NOW), { start: "Enter the actual start time." });
  assert.deepEqual(actualTimeIssues("2026-02-30T21:05", "2026-10-13T21:50", NOW), { start: "Enter a valid actual start date and time." });
  assert.deepEqual(actualTimeIssues("2026-10-13T21:05", "not a time", NOW), { end: "Enter a valid actual end date and time." });
  const later = { end: "The actual end must be later than the start." };
  assert.deepEqual(actualTimeIssues("2026-10-13T21:05", "2026-10-13T21:05", NOW), later, "Equal times");
  assert.deepEqual(actualTimeIssues("2026-10-13T21:50", "2026-10-13T21:05", NOW), later, "Reversed times");
  assert.deepEqual(actualTimeIssues("2026-10-13T21:05", "2026-10-13T22:31", NOW), { end: "The actual end cannot be in the future." });
  assert.deepEqual(actualTimeIssues("2026-10-13T21:05", "2026-10-13T22:31", null), {}, "The future check needs an observed time");
  assert.equal(firstActualTimeIssue(actualTimeIssues("", "", NOW)), "start");
  assert.equal(firstActualTimeIssue(actualTimeIssues("2026-10-13T21:50", "2026-10-13T21:05", NOW)), "end");
});

test("actual times may differ from the scheduled appointment in any direction", () => {
  for (const [start, end] of [
    ["2026-10-13T21:00", "2026-10-13T22:00"], // within the scheduled window
    ["2026-10-13T21:20", "2026-10-13T22:00"], // started later than scheduled
    ["2026-10-13T21:00", "2026-10-13T22:25"], // ended later than scheduled
    ["2026-10-13T21:10", "2026-10-13T21:35"], // a different duration
    ["2026-10-13T21:10:30", "2026-10-13T21:35:45"], // seconds, as corrections keep them
  ]) {
    assert.deepEqual(actualTimeIssues(start, end, NOW), {}, `${start} – ${end}`);
  }
});

test("actual times are sent as the institutional instant whatever the browser zone", () => {
  assert.equal(institutionalDateTimeInputToISO("2026-10-13T21:05"), "2026-10-13T13:05:00.000Z");
  assert.equal(institutionalDateTimeInputToISO("2026-01-06T09:00:30"), "2026-01-06T01:00:30.000Z");
});

test("the session preset carries each Student's own Institutional ID and the schedule as reference", () => {
  const first = sessionEncounterPreset(workspace());
  const second = sessionEncounterPreset(workspace({ id: "appointment-b", student: { id: "student-b", display_name: "Synthetic Student B", institutional_id: null } }));
  assert.deepEqual(first, {
    entryMode: "APPOINTMENT",
    appointmentId: "appointment-a",
    appointmentReference: "APT-appointment-a",
    studentName: "Synthetic Student A",
    institutionalId: "SYNTH-2026-0203",
    deliveryMode: "ONLINE",
    scheduledStartsAt: SCHEDULED.starts_at,
    scheduledEndsAt: SCHEDULED.ends_at,
  });
  assert.equal(second.institutionalId, null, "Another Student never inherits an ID");
  assert.equal(second.appointmentId, "appointment-b");
});

test("recording sends the entered actual times, never the scheduled ones", () => {
  const preset = sessionEncounterPreset(workspace());
  const payload = encounterCreatePayload(preset, institutionalDateTimeInputToISO("2026-10-13T21:20"), institutionalDateTimeInputToISO("2026-10-13T22:25"));
  assert.deepEqual(payload, {
    appointment_id: "appointment-a",
    entry_mode: "APPOINTMENT",
    started_at: "2026-10-13T13:20:00.000Z",
    ended_at: "2026-10-13T14:25:00.000Z",
  });
  assert.doesNotMatch(JSON.stringify(payload), /13:00:00|14:00:00|scheduled/);
});

test("the record form shows the Student's ID and the schedule, with blank actual times", () => {
  const preset = sessionEncounterPreset(workspace());
  const html = render(h(RecordEncounterForm, { preset, framed: false, onCancel() {} }));
  assert.match(html, /Synthetic Student A/);
  assert.match(html, /Institutional ID: SYNTH-2026-0203/);
  assert.match(html, /Scheduled appointment/);
  assert.ok(html.includes(formatAppointmentDateTime(SCHEDULED.starts_at, SCHEDULED.ends_at)), "Scheduled time uses the institutional appointment format");
  assert.match(html, /<legend[^>]*>Actual counseling interaction<\/legend>/);
  assert.match(html, /actually started and ended, in Philippine Time\. These times may differ from the scheduled appointment\./);
  for (const id of ["counseling-started-at", "counseling-ended-at"]) {
    const input = html.match(new RegExp(`<input[^>]*id="${id}"[^>]*>`))?.[0] ?? "";
    assert.match(input, /type="datetime-local"/);
    assert.match(input, /value=""/, `${id} starts blank instead of copying the schedule`);
    assert.match(input, /required/);
    assert.doesNotMatch(input, /aria-invalid/, "Nothing is reported before the Counselor tries to save");
  }
  assert.match(html, /<form novalidate=""/i);
  assert.match(html, /<button[^>]*type="submit"[^>]*>Record encounter<\/button>/);
  assert.match(html, /<button[^>]*>Cancel<\/button>/);
  // The dialog supplies its own title and provenance note.
  assert.doesNotMatch(html, /Record counseling encounter|You are recorded as the counselor/);
  assert.doesNotMatch(html, /undefined|null/);
});

test("a Student without an Institutional ID is shown honestly", () => {
  const preset = sessionEncounterPreset(workspace({ student: { id: "student-c", display_name: "Synthetic Student C", institutional_id: null } }));
  const html = render(h(RecordEncounterForm, { preset, framed: false }));
  assert.match(html, /Institutional ID: Not provided/);
  assert.doesNotMatch(html, /Institutional ID: (?:undefined|null|<)/);
});

test("a direct origin has no scheduled appointment to compare against", () => {
  const html = render(h(RecordEncounterForm, {
    preset: { entryMode: "WALK_IN", studentId: "student-d", studentName: "Synthetic Student D", institutionalId: "SYNTH-0001", deliveryMode: "IN_PERSON" },
  }));
  assert.doesNotMatch(html, /Scheduled appointment|differ from the scheduled appointment/);
  assert.match(html, /You are recorded as the counselor for this encounter\./);
});

const savedEncounter = {
  id: "encounter-1",
  student: { id: "student-a", display_name: "Synthetic Student A" },
  counselor: { id: "counselor-1", display_name: "Synthetic Counselor" },
  service: { id: "service-1", code: "COUNSELING", name: "Counseling" },
  appointment: { id: "appointment-a", reference_code: "APT-appointment-a" },
  entry_mode: "APPOINTMENT",
  delivery_mode: "ONLINE",
  started_at: "2026-01-06T01:00:30.123456Z",
  ended_at: "2026-01-06T01:45:15Z",
  created_at: "2026-01-06T02:00:00Z",
  updated_at: "2026-01-06T02:00:00Z",
};

test("corrections send only changed facts and keep untouched timestamps intact", () => {
  const values = {
    appointmentId: "appointment-a",
    entryMode: "APPOINTMENT",
    deliveryMode: "ONLINE",
    startedAt: savedEncounterTimeInput(savedEncounter.started_at),
    endedAt: savedEncounterTimeInput(savedEncounter.ended_at),
  };
  assert.equal(values.startedAt, "2026-01-06T09:00:30", "Saved seconds open in the form");
  assert.equal(values.endedAt, "2026-01-06T09:45:15");
  assert.deepEqual(encounterCorrectionPayload(savedEncounter, values), {}, "Nothing changed");
  assert.deepEqual(
    encounterCorrectionPayload(savedEncounter, { ...values, endedAt: "2026-01-06T09:50:15" }),
    { ended_at: "2026-01-06T01:50:15.000Z" },
    "The untouched start keeps its stored sub-second precision by not being sent",
  );
  assert.deepEqual(
    encounterCorrectionPayload(savedEncounter, { ...values, appointmentId: "", entryMode: "WALK_IN" }),
    { appointment_id: null, entry_mode: "WALK_IN" },
  );
  assert.equal(encounterCorrectionPayload(savedEncounter, { ...values, startedAt: "2026-02-30T09:00" }), null);
});

test("the correction form opens with the saved times and the shared time contract", () => {
  const html = render(h(EncounterCorrectionForm, { encounter: savedEncounter, onClose() {} }));
  const start = html.match(/<input[^>]*id="correction-started-at"[^>]*>/)?.[0] ?? "";
  assert.match(start, /value="2026-01-06T09:00:30"/);
  assert.match(start, /step="1"/);
  assert.match(html, /<legend[^>]*>Actual counseling interaction<\/legend>/);
  assert.match(html, /in Philippine Time\. These times may differ from the scheduled appointment\./);
  assert.match(html, /<button[^>]*type="submit"[^>]*disabled=""[^>]*>Save corrections<\/button>/, "Nothing to save until a fact changes");
  assert.match(html, /<button[^>]*>Cancel<\/button>/);
  assert.match(html, /<form novalidate=""/i);
});
