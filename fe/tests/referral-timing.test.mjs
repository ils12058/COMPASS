import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { addCivilDays, emptyTimingDraft, newTimingWindow, timingBackendErrors, timingDraftDirty, timingStatementRequest, timingWindowsRequest, validateTimingDraft } from "../src/features/referral-timing/timing-draft.ts";
import { reportedProvenance, timingStatusLabel, timingWindowExpired, timingWindowExpiry } from "../src/features/referral-timing/timing-presentation.ts";
import { TimingEditor } from "../src/features/referral-timing/timing-editor.tsx";
import { ReportedTiming, TimingWindows, VerifiedTiming } from "../src/features/referral-timing/timing-readout.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";

const now = new Date("2026-11-13T02:00:00Z");
const window = (changes = {}) => ({ ...newTimingWindow(1), date: "2026-11-13", startTime: "10:00", endTime: "11:00", ...changes });
const draft = (changes = {}) => ({ answer: "KNOWN", windows: [window()], note: "Scheduling only", ...changes });
const check = value => validateTimingDraft(value, { now });

test("Timing requires an explicit answer, and Unknown remains distinct from an untouched draft", () => {
  assert.equal(timingStatementRequest(emptyTimingDraft()), null);
  assert.ok(check(emptyTimingDraft()).answer_kind);
  assert.deepEqual(timingStatementRequest({ answer: "UNKNOWN", windows: [], note: "" }), { answer_kind: "UNKNOWN", windows: [], note: "" });
  assert.equal(timingDraftDirty(emptyTimingDraft()), false);
  assert.equal(timingDraftDirty(draft()), true);
  assert.equal(timingDraftDirty({ answer: "", windows: [newTimingWindow(1)], note: "" }), true);
});

test("Mixed information types, both patterns, and overlaps are valid", () => {
  const mixed = draft({ windows: [window(), window({ key: 2, informationType: "CLASS_RELEASE", pattern: "RECURRING_WEEKDAY", weekday: "SATURDAY", validUntil: "2026-11-20" }), window({ key: 3, startTime: "10:15", endTime: "10:45" })] });
  assert.deepEqual(check(mixed), {});
  const request = timingWindowsRequest(mixed);
  assert.equal(request[1].date, null);
  assert.equal(request[0].weekday, null);
  assert.equal(request[1].information_type, "CLASS_RELEASE");
});

test("One to five windows and duplicate normalized times are enforced", () => {
  assert.ok(check(draft({ windows: [] })).windows);
  assert.ok(check(draft({ windows: Array.from({ length: 6 }, (_, key) => window({ key, date: `2026-11-${14 + key}` })) })).windows);
  assert.deepEqual(check(draft({ windows: Array.from({ length: 5 }, (_, key) => window({ key, date: `2026-11-${14 + key}` })) })), {});
  assert.ok(check(draft({ windows: [window(), window({ key: 2, startTime: "10:00:00", endTime: "11:00:00" })] }))["windows.1.start_time"]);
});

test("Each invalid window field has its own error and rejects Sunday", () => {
  for (const [change, field] of [[{ date: "2026-11-12" }, "date"], [{ date: "2026-02-30" }, "date"], [{ date: "" }, "date"], [{ endTime: "10:00" }, "end_time"], [{ endTime: "09:59" }, "end_time"], [{ startTime: "bad" }, "start_time"], [{ startTime: "10:00+08:00" }, "start_time"], [{ pattern: "RECURRING_WEEKDAY", weekday: "SUNDAY", validUntil: "2026-11-20" }, "weekday"], [{ pattern: "RECURRING_WEEKDAY", weekday: "MONDAY", validUntil: "" }, "valid_until"]]) {
    assert.ok(check(draft({ windows: [window(change)] }))[`windows.0.${field}`], field);
  }
});

test("Philippine midnight and the inclusive 180-day validity boundary match the backend", () => {
  const value = draft({ windows: [window({ date: "2026-11-12" })] });
  assert.deepEqual(validateTimingDraft(value, { now: new Date("2026-11-12T15:59:59Z") }), {});
  assert.ok(validateTimingDraft(value, { now: new Date("2026-11-12T16:00:00Z") })["windows.0.date"]);
  const last = addCivilDays("2026-11-13", 180);
  const recurrence = { pattern: "RECURRING_WEEKDAY", weekday: "MONDAY", validUntil: last };
  assert.deepEqual(check(draft({ windows: [window(recurrence)] })), {});
  assert.ok(check(draft({ windows: [window({ ...recurrence, validUntil: addCivilDays(last, 1) })] }))["windows.0.valid_until"]);
});

test("Scheduling notes count Unicode characters and reject malformed text without truncation", () => {
  assert.deepEqual(check(draft({ note: "🌱".repeat(500) })), {});
  for (const note of ["🌱".repeat(501), "NUL\u0000text", "\ud800"]) assert.ok(check(draft({ note })).note);
});

test("Switching to Unknown preserves partial local windows but sends no hidden timing", () => {
  const original = draft();
  const unknown = { ...original, answer: "UNKNOWN" };
  assert.deepEqual(timingStatementRequest(unknown), { answer_kind: "UNKNOWN", windows: [], note: "" });
  assert.deepEqual(unknown.windows, original.windows);
  assert.equal(timingDraftDirty(unknown), true);
});

test("Verification supports no suitable time and a scheduling note", () => {
  assert.deepEqual(validateTimingDraft({ answer: "NO_SUITABLE_TIME", windows: [], note: "Student will confirm later" }, { verification: true, now }), {});
  assert.ok(check({ answer: "NO_SUITABLE_TIME", windows: [], note: "" }).answer_kind);
});

test("Specific times expire at their end; recurring validity includes its whole Philippine date", () => {
  const specific = timingWindowsRequest(draft())[0];
  assert.equal(timingWindowExpired(specific, now), false);
  assert.equal(timingWindowExpired(specific, new Date("2026-11-13T03:00:00Z")), true);
  const recurring = timingWindowsRequest(draft({ windows: [window({ pattern: "RECURRING_WEEKDAY", weekday: "SATURDAY", validUntil: "2026-11-20" })] }))[0];
  assert.equal(timingWindowExpired(recurring, new Date("2026-11-20T15:59:59Z")), false);
  assert.equal(timingWindowExpired(recurring, new Date("2026-11-20T16:00:00Z")), true);
  assert.equal(timingWindowExpiry(recurring), "2026-11-20T16:00:00.000Z");
});

test("GCO provenance identifies the encoder, never the staff member as the referrer", () => {
  const base = { author_name: "Synthetic Staff", created_at: "2026-11-13T02:00:00Z" };
  assert.match(reportedProvenance({ ...base, submission_channel: "GCO_RECORDED" }), /^Reported by the referrer, recorded by Synthetic Staff on/);
  assert.match(reportedProvenance({ ...base, submission_channel: "FACULTY_PORTAL" }), /^Reported by Synthetic Staff on/);
  assert.equal(timingStatusLabel(undefined), "Timing: Not provided");
  assert.equal(timingStatusLabel("UNKNOWN"), "Timing: Unknown");
  assert.equal(timingStatusLabel("KNOWN"), "Timing: Known");
});

test("Backend validation maps nested statement/window fields without displaying unrelated fields", () => {
  const error = new CompassApiError({ status: 422, body: { error: { details: [{ loc: ["body", "scheduling_statement", "windows", "1", "end_time"], message: "End time must be after start time." }, { loc: ["body", "reason"], message: "Reason" }] } }, headers: {}, method: "POST", url: "/api/v1/faculty/referrals" });
  assert.deepEqual(timingBackendErrors(error), { "windows.1.end_time": "End time must be after start time." });
});

test("Editor rows are named and every field error is attached to a real control", () => {
  const value = draft({ windows: [window(), window({ key: 2 })] });
  const html = renderToStaticMarkup(createElement(TimingEditor, { prefix: "test", draft: value, onChange() {}, errors: { "windows.1.end_time": "End after start" } }));
  assert.match(html, /Window 2 of 2/);
  assert.match(html, /id="test-window-2-end_time"[^>]*aria-invalid="true"[^>]*aria-describedby="test-window-2-end_time-error"/);
  assert.match(html, /Philippine Time/);
  const statement = { id: "s", answer_kind: "KNOWN", windows: [{ ...timingWindowsRequest(draft())[0], expired: true }], note: "Reported scheduling note", submission_channel: "FACULTY_PORTAL", author_name: "Faculty", created_at: "2026-11-13T02:00:00Z", author_id: "f" };
  const own = renderToStaticMarkup(createElement(ReportedTiming, { statement }));
  assert.match(own, /This time has passed/);
  assert.doesNotMatch(own, /Student confirmed|Verified availability/);
  const verified = renderToStaticMarkup(createElement(VerifiedTiming, { records: [{ ...statement, confirmation_source: "STUDENT_CONFIRMED" }] }));
  assert.match(verified, /Student confirmed/);
});

test("A valid sub-minute window keeps its distinct start and end in the readout", () => {
  const value = draft({ windows: [window({ startTime: "10:00:01.100", endTime: "10:00:01.200" })] });
  assert.deepEqual(check(value), {});
  const html = renderToStaticMarkup(createElement(TimingWindows, {
    windows: timingWindowsRequest(value).map(window => ({ ...window, expired: false })),
  }));
  assert.ok(html.includes("10:00:01.100–10:00:01.200"), "An allowed interval must not display as 10:00–10:00");
});
