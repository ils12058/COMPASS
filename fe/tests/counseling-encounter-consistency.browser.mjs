// CE-1 / UX-1a in a real browser: the Record encounter dialog in the E-Counseling workspace, the
// standalone and Counseling-workspace recording paths, and the correction form. Every request is
// answered with synthetic fixtures and the call uses the fake Call Object, so no account, Daily room,
// recording or institutional record is touched.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointment, appointmentId, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("counseling-encounter-consistency");
const ePath = `/portal/e-counseling/${appointmentId}`;
const SYNTH_ID = "SYNTH-2026-0203";
const STUDENT = "Synthetic Student";
const ENCOUNTER = "e0000000-0000-4000-8000-000000000001";
// The fixture Appointment runs 10:00–11:00 AM Philippine Time on Thursday, October 8, 2026.
const SCHEDULED = /Thu, Oct 8, 2026 · 10:00\sAM–11:00\sAM/;

const dialog = (page) => page.getByRole("dialog", { name: "Record encounter", exact: true });
const encounterSection = (page) => page.getByRole("region", { name: /^Counseling Encounter/ });
const studentSection = (page) => page.getByRole("region", { name: /^Student information/ });
const stage = (page) => page.getByRole("region", { name: "Video call" });
const fakeCount = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
const posts = (requests, suffix) => requests.filter((request) => request.method !== "GET" && request.pathname.endsWith(suffix));

function savedEncounter(overrides = {}) {
  return {
    id: ENCOUNTER,
    student: { id: "student", display_name: STUDENT },
    counselor: { id: "counselor", display_name: "Synthetic Counselor" },
    service: { id: "service-density-test", code: "COUNSELING", name: "Counseling" },
    appointment: { id: appointmentId, reference_code: appointment.reference_code },
    entry_mode: "APPOINTMENT",
    delivery_mode: "ONLINE",
    started_at: "2026-10-08T02:05:30Z",
    ended_at: "2026-10-08T02:55:15Z",
    created_at: "2026-10-08T03:10:00Z",
    updated_at: "2026-10-08T03:10:00Z",
    ...overrides,
  };
}

function contextOverview(student) {
  return {
    source_type: "APPOINTMENT", source_id: appointmentId, entry_mode: "APPOINTMENT", delivery_mode: "ONLINE",
    valid_from: "2026-01-01T00:00:00Z", valid_until: "2099-01-01T00:00:00Z",
    student: { ...student, campus: null, college: null, program: null, year_level: 4 },
    matching_encounter: null, routine_interview: null, available_sections: ["OVERVIEW"],
  };
}

// A Counselor's E-Counseling session whose Encounter state a check can change mid-test.
function session({ institutionalId = SYNTH_ID, post } = {}) {
  const state = { encounter: null, workspaceReads: 0, heldPosts: [] };
  const student = { id: "student", display_name: STUDENT, institutional_id: institutionalId };
  const overrides = {
    [`/api/v1/e-counseling/appointments/${appointmentId}`]: ({ reply }) => {
      state.workspaceReads += 1;
      const value = workspace();
      value.student = student;
      value.counseling_context_available = true;
      value.counseling_encounter = state.encounter;
      return reply(value);
    },
    [`/api/v1/counseling/context/APPOINTMENT/${appointmentId}`]: ({ reply }) => reply(contextOverview(student)),
    [`POST /api/v1/e-counseling/appointments/${appointmentId}/join`]: ({ reply }) => reply({
      appointment_id: appointmentId,
      workspace_id: "synthetic-workspace",
      provider: "DAILY",
      room_url: "https://synthetic.daily.co/synthetic-room",
      meeting_token: "synthetic-meeting-token",
      token_expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
    }),
    ...(post ? { "POST /api/v1/counseling/encounters": (args) => post(args, state) } : {}),
  };
  return { state, overrides };
}

// A Manila wall-clock value `days` from now, as a datetime-local input expects.
function institutionalInput(days) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Manila", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(Date.now() + days * 86_400_000)).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

async function openRecordDialog(page) {
  // Narrow layouts start the section collapsed beside the call.
  const toggle = page.getByRole("button", { name: /^Counseling Encounter/ });
  await shown(toggle);
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  await encounterSection(page).getByRole("button", { name: "Record encounter", exact: true }).click();
  await shown(dialog(page));
  return dialog(page);
}

// Radix restores focus just after the dialog leaves, so wait briefly for it.
async function focused(locator, message) {
  const handle = await locator.elementHandle();
  await locator.page().waitForFunction((element) => element === document.activeElement, handle, { timeout: 3_000 }).catch(() => {
    throw new Error(message);
  });
}

async function fillTimes(target, start, end) {
  await target.getByLabel("Actual start", { exact: true }).fill(start);
  await target.getByLabel("Actual end", { exact: true }).fill(end);
}

async function errorFor(input) {
  if ((await input.getAttribute("aria-invalid")) !== "true") return null;
  const id = await input.getAttribute("aria-describedby");
  return id ? input.page().locator(`[id="${id}"]`).innerText() : null;
}

await check("ecounseling-dialog-identity-matches-overview", ePath, { overrides: session().overrides }, async (page) => {
  await shown(studentSection(page).getByText(SYNTH_ID, { exact: true }));
  const record = await openRecordDialog(page);
  const text = await record.innerText();
  assert.match(text, new RegExp(`Institutional ID: ${SYNTH_ID}`), "The dialog shows the same ID as the Student information");
  assert.match(text, /Scheduled appointment/);
  assert.match(text, SCHEDULED);
  assert.match(text, /in Philippine Time\. These times may differ from the scheduled appointment\./);
  assert.doesNotMatch(text, /undefined|null|Not provided/);
  assert.equal(await record.getByRole("heading").count(), 1, "One dialog heading, no nested panel title");
  const description = await record.getAttribute("aria-describedby");
  assert.match(await page.locator(`[id="${description}"]`).innerText(), /The Appointment sets the student, Service, and delivery mode\. You are recorded as the counselor\./);
  for (const label of ["Actual start", "Actual end"]) assert.equal(await record.getByLabel(label, { exact: true }).inputValue(), "", `${label} is not copied from the schedule`);
  await shown(record.getByRole("group", { name: "Actual counseling interaction" }));
  await shown(record.getByRole("button", { name: "Record encounter", exact: true }));
  await shown(record.getByRole("button", { name: "Cancel", exact: true }));
  await screenshot(page, "ecounseling-record-dialog");
});

await check("ecounseling-dialog-without-institutional-id", ePath, { overrides: session({ institutionalId: null }).overrides }, async (page) => {
  const record = await openRecordDialog(page);
  const text = await record.innerText();
  assert.match(text, /Institutional ID: Not provided/);
  assert.doesNotMatch(text, /undefined|null/);
});

await check("ecounseling-validation-is-specific-and-announced", ePath, { overrides: session().overrides }, async (page, { requests }) => {
  const record = await openRecordDialog(page);
  const start = record.getByLabel("Actual start", { exact: true });
  const end = record.getByLabel("Actual end", { exact: true });
  assert.equal(await errorFor(start), null, "Nothing is reported before a save attempt");
  await record.getByRole("button", { name: "Record encounter", exact: true }).click();
  await focused(start, "Focus moves to the first field to fix");
  assert.equal(await errorFor(start), "Enter the actual start time.");
  assert.equal(await errorFor(end), "Enter the actual end time.");
  await start.fill("2026-01-06T09:00");
  assert.equal(await errorFor(start), null);
  assert.equal(await errorFor(end), "Enter the actual end time.");
  for (const [value, message] of [
    ["2026-01-06T09:00", "The actual end must be later than the start."],
    ["2026-01-06T08:30", "The actual end must be later than the start."],
    [institutionalInput(2), "The actual end cannot be in the future."],
  ]) {
    await end.fill(value);
    assert.equal(await errorFor(end), message, value);
    assert.equal(await record.getByText(message, { exact: true }).count(), 1, "Each message appears once");
    assert.equal(await record.getByRole("alert").count(), 0, "Field messages are not repeated as a form alert");
  }
  await end.fill("2026-01-06T10:00");
  assert.equal(await errorFor(end), null);
  assert.equal(posts(requests, "/counseling/encounters").length, 0, "Validation never sends a request");
});

await check("ecounseling-save-success-other-browser-zone", ePath, {
  timezoneId: "America/New_York",
  ...session({ post: ({ reply, request }, state) => {
    state.body = JSON.parse(request.postData());
    state.encounter = { id: ENCOUNTER, recorded: true };
    return reply(savedEncounter({ started_at: state.body.started_at, ended_at: state.body.ended_at }), 201);
  } }),
}, async (page, { requests }) => {
  const record = await openRecordDialog(page);
  await fillTimes(record, "2026-01-06T09:00", "2026-01-06T10:00");
  await record.getByRole("button", { name: "Record encounter", exact: true }).click();
  await hidden(record);
  const view = encounterSection(page).getByRole("link", { name: "View encounter", exact: true });
  await shown(view);
  await page.waitForFunction(() => document.activeElement?.textContent === "View encounter");
  await shown(page.getByRole("button", { name: /^Counseling Encounter\s*Recorded/ }));
  const [post] = posts(requests, "/counseling/encounters");
  assert.deepEqual(JSON.parse(post.body), {
    appointment_id: appointmentId,
    entry_mode: "APPOINTMENT",
    started_at: "2026-01-06T01:00:00.000Z",
    ended_at: "2026-01-06T02:00:00.000Z",
  }, "Philippine Time is sent whatever the browser's zone, and the schedule never is");
  assert.equal(requests.filter((request) => request.method !== "GET" && request.pathname.includes("/appointments/")).length, 0, "Recording does not complete the Appointment");
});

let releasePending;
await check("ecounseling-pending-then-unconfirmed", ePath, session({ post: async ({ reply }, state) => {
  await new Promise((resolve) => { releasePending = resolve; });
  state.released = true;
  return reply({ error: { code: "synthetic_uncertain", message: "Synthetic uncertain result" } }, 503);
} }), async (page, { requests }) => {
  const record = await openRecordDialog(page);
  await fillTimes(record, "2026-01-06T09:00", "2026-01-06T10:00");
  await record.getByRole("button", { name: "Record encounter", exact: true }).click();
  await shown(record.getByRole("button", { name: "Recording encounter…", exact: true }));
  assert.equal(await record.getByRole("button", { name: "Cancel", exact: true }).isDisabled(), true);
  assert.equal(await record.getByRole("button", { name: "Close dialog", exact: true }).count(), 0);
  await page.keyboard.press("Escape");
  await shown(record);
  releasePending();
  await shown(record.getByText(/We couldn’t confirm whether the encounter was recorded\. Check your encounters before trying again/));
  await page.keyboard.press("Escape");
  await shown(record);
  assert.equal(await record.getByLabel("Actual start", { exact: true }).inputValue(), "2026-01-06T09:00", "The unconfirmed attempt keeps its times");
  await record.getByRole("button", { name: "Close", exact: true }).click();
  await hidden(record);
  const checkAgain = encounterSection(page).getByRole("button", { name: "Check again", exact: true });
  await shown(checkAgain);
  await focused(checkAgain, "Focus lands on the section's next action");
  await shown(page.getByRole("button", { name: /^Counseling Encounter\s*Not confirmed/ }));
  assert.equal(await encounterSection(page).getByRole("button", { name: "Record encounter", exact: true }).count(), 0, "No second save from here");
  const sessionReads = () => requests.filter((request) => request.method === "GET" && request.pathname === `/api/v1/e-counseling/appointments/${appointmentId}`).length;
  const reads = sessionReads();
  await checkAgain.click();
  const deadline = Date.now() + 5_000;
  while (sessionReads() <= reads && Date.now() < deadline) await page.waitForTimeout(50);
  assert.ok(sessionReads() > reads, "Check again reloads the session");
  await shown(encounterSection(page).getByRole("button", { name: "Check again", exact: true }));
  assert.equal(posts(requests, "/counseling/encounters").length, 1);
});
releasePending?.();

await check("ecounseling-rejected-save-keeps-values", ePath, session({ post: ({ reply }) => reply({ error: { code: "counseling_invalid_time", message: "ended_at must not be in the future." } }, 422) }), async (page) => {
  const record = await openRecordDialog(page);
  await fillTimes(record, "2026-01-06T09:00", "2026-01-06T10:00");
  await record.getByRole("button", { name: "Record encounter", exact: true }).click();
  const alert = record.getByRole("alert");
  await shown(alert);
  assert.equal(await alert.innerText(), "These actual times weren’t accepted. Check that the end is later than the start and not in the future.");
  assert.equal(await record.getByLabel("Actual end", { exact: true }).inputValue(), "2026-01-06T10:00");
  assert.equal(await record.getByRole("button", { name: "Record encounter", exact: true }).isEnabled(), true, "The Counselor can correct and try again");
  await page.keyboard.press("Escape");
  await hidden(record);
});

await check("ecounseling-already-recorded", ePath, session({ post: ({ reply }, state) => {
  state.encounter = { id: ENCOUNTER, recorded: true };
  return reply({ error: { code: "counseling_appointment_already_used", message: "Already used" } }, 409);
} }), async (page) => {
  const record = await openRecordDialog(page);
  await fillTimes(record, "2026-01-06T09:00", "2026-01-06T10:00");
  await record.getByRole("button", { name: "Record encounter", exact: true }).click();
  await hidden(record);
  await shown(encounterSection(page).getByText("An encounter was already recorded for this Appointment. The latest details are now shown.", { exact: true }));
  await shown(encounterSection(page).getByRole("link", { name: "View encounter", exact: true }));
});

await check("ecounseling-dialog-keeps-times-and-call", ePath, { fakeDaily: true, ...session() }, async (page) => {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for ${STUDENT}…`, { exact: true }).first());
  const record = await openRecordDialog(page);
  await fillTimes(record, "2026-01-06T09:00", "2026-01-06T10:00");
  await page.keyboard.press("Escape");
  await hidden(record);
  const trigger = encounterSection(page).getByRole("button", { name: "Record encounter", exact: true });
  await focused(trigger, "Focus returns to Record encounter");
  await trigger.click();
  assert.equal(await record.getByLabel("Actual start", { exact: true }).inputValue(), "2026-01-06T09:00", "Times survive dismissal");
  await record.getByRole("button", { name: "Cancel", exact: true }).click();
  await hidden(record);
  assert.equal(await fakeCount(page, "createCallObject"), 1, "The call object is never recreated");
  assert.equal(await fakeCount(page, "destroy"), 0, "Opening and closing the dialog never ends the call");
  await shown(stage(page).getByRole("button", { name: "Leave session", exact: true }));
});

for (const device of ["narrowPhone", "phone", "tablet"]) {
  await check(`ecounseling-dialog-${device}`, ePath, { device, ...session() }, async (page) => {
    const record = await openRecordDialog(page);
    await fillTimes(record, "2026-01-06T09:00", "2026-01-06T10:00");
    await noHorizontalOverflow(page);
    const overflow = await record.evaluate((element) => element.scrollWidth - element.clientWidth);
    assert.ok(overflow <= 1, `Dialog content overflows by ${overflow}px`);
    const box = await record.boundingBox();
    for (const control of [record.getByLabel("Actual start", { exact: true }), record.getByLabel("Actual end", { exact: true }), record.getByRole("button", { name: "Record encounter", exact: true }), record.getByRole("button", { name: "Cancel", exact: true })]) {
      await control.scrollIntoViewIfNeeded();
      const rect = await control.boundingBox();
      assert.ok(rect.x >= box.x - 1 && rect.x + rect.width <= box.x + box.width + 1, "Controls stay inside the dialog");
      assert.ok(rect.height >= 40, "Controls keep a usable target");
    }
    assert.match(await record.innerText(), new RegExp(`Institutional ID: ${SYNTH_ID}`));
    await screenshot(page, `ecounseling-record-dialog-${device}`);
  });
}

const correctionOverrides = (state) => ({
  [`/api/v1/counseling/encounters/${ENCOUNTER}`]: async ({ reply, request }) => {
    if (request.method() === "PATCH") {
      state.patch = JSON.parse(request.postData());
      if (state.hold) await new Promise((resolve) => { state.release = resolve; state.started?.(); });
      return reply(savedEncounter(state.patch));
    }
    return reply(savedEncounter());
  },
  [`/api/v1/counseling/encounters/${ENCOUNTER}/appointment-candidates`]: {
    items: [{ id: appointmentId, reference_code: appointment.reference_code, delivery_mode: "ONLINE", starts_at: appointment.starts_at, ends_at: appointment.ends_at, status: "COMPLETED" }],
    page: 1, page_size: 20, has_next: false,
  },
});

const correction = { hold: true };
const correctionStarted = new Promise(resolve => { correction.started = resolve; });
await check("correction-form-consistency", `/portal/counseling/encounters/${ENCOUNTER}`, { overrides: correctionOverrides(correction) }, async (page) => {
  await page.getByRole("button", { name: "Correct encounter details", exact: true }).click();
  const form = page.getByRole("form", { name: "Correct encounter details" });
  await shown(form);
  const start = form.getByLabel("Actual start", { exact: true });
  const end = form.getByLabel("Actual end", { exact: true });
  assert.equal(await start.inputValue(), "2026-10-08T10:05:30", "Saved seconds are shown");
  assert.equal(await start.getAttribute("step"), "1");
  await shown(form.getByRole("group", { name: "Actual counseling interaction" }));
  assert.match(await form.innerText(), /in Philippine Time\. These times may differ from the scheduled appointment\./);
  assert.match(await form.innerText(), /Selected: APT-TEST-1024 · Scheduled Thu, Oct 8, 2026 · 10:00\sAM–11:00\sAM/);
  const save = form.getByRole("button", { name: "Save corrections", exact: true });
  assert.equal(await save.isDisabled(), true, "Nothing to save yet");
  await end.fill("2026-10-08T10:05");
  assert.equal(await errorFor(end), "The actual end must be later than the start.", "The same message as recording");
  await end.fill("2026-10-08T10:50");
  assert.equal(await errorFor(end), null);
  await screenshot(page, "encounter-correction-form");
  await save.click();
  await shown(form.getByRole("button", { name: "Saving corrections…", exact: true }));
  assert.equal(await form.getByRole("button", { name: "Cancel", exact: true }).isDisabled(), true);
  await correctionStarted;
  assert.deepEqual(correction.patch, { ended_at: "2026-10-08T02:50:00.000Z" }, "Only the changed time is sent; the start keeps its stored seconds");
  correction.release();
  await hidden(form);
});

await check("standalone-appointment-recording", "/portal/counseling", { overrides: {
  "/api/v1/counseling/me/encounters": { items: [], page: 1, page_size: 20, has_next: false, ordering: "LATEST_ENCOUNTER" },
  "/api/v1/counseling/appointment-candidates": {
    items: [{ id: appointmentId, reference_code: appointment.reference_code, student: { id: "student", display_name: STUDENT, institutional_id: SYNTH_ID }, delivery_mode: "ONLINE", starts_at: appointment.starts_at, ends_at: appointment.ends_at, status: "SCHEDULED" }],
    page: 1, page_size: 20, has_next: false,
  },
} }, async (page) => {
  await page.getByRole("button", { name: "Record counseling encounter" }).click();
  await page.getByRole("button", { name: "From Counseling appointment", exact: true }).click();
  await page.getByRole("button", { name: new RegExp(`${appointment.reference_code} · ${STUDENT}`) }).click();
  const summary = page.locator("form").filter({ has: page.getByRole("group", { name: "Actual counseling interaction" }) });
  const text = await summary.innerText();
  assert.match(text, new RegExp(`Institutional ID: ${SYNTH_ID}`));
  assert.match(text, SCHEDULED);
  assert.match(text, /The Appointment sets the student, Service, and delivery mode\. You are recorded as the counselor\./);
  assert.match(text, /Recording this encounter does not complete the Appointment\./);
  assert.equal(await summary.getByLabel("Actual start", { exact: true }).inputValue(), "");
  await shown(summary.getByRole("button", { name: "Record encounter", exact: true }));
  await shown(summary.getByRole("button", { name: "Cancel", exact: true }));
});

await check("counseling-workspace-dialog-identity", `/portal/counseling/workspace/appointment/${appointmentId}`, { overrides: {
  [`/api/v1/counseling/context/APPOINTMENT/${appointmentId}`]: contextOverview({ id: "student", display_name: STUDENT, institutional_id: SYNTH_ID }),
} }, async (page) => {
  await page.getByRole("button", { name: "Record encounter", exact: true }).click();
  const record = dialog(page);
  await shown(record);
  assert.match(await record.innerText(), new RegExp(`Institutional ID: ${SYNTH_ID}`));
  assert.doesNotMatch(await record.innerText(), /Scheduled appointment/, "No schedule is invented where the context has none");
  assert.match(await record.innerText(), /These times may differ from the scheduled appointment\./);
});

await finish();
