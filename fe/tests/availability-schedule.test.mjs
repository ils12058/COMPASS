import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { MyAvailabilityPage } from "../src/features/availability/availability-pages.tsx";
import { formatUnavailabilityRange } from "../src/features/availability/availability-shared.tsx";
import { UnavailabilitySection } from "../src/features/availability/unavailability-section.tsx";
import { WeeklyScheduleCleanup, WeeklyScheduleEditor } from "../src/features/availability/weekly-schedule-editor.tsx";
import {
  draftFromWindows,
  formatClockRange,
  requestFromDraft,
  validateDraft,
  weekdayOrder,
} from "../src/features/availability/weekly-schedule.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getAvailabilityGetMyWeeklyQueryKey, getAvailabilityListMyExceptionsQueryKey } from "../src/lib/api/generated/availability/availability.ts";

const window = (weekday, start, end, mode = "ALL", id = `${weekday}-${start}`) => ({
  id, weekday, start_time: `${start}:00`, end_time: `${end}:00`, mode_scope: mode,
});
const mondayTwice = [window("MONDAY", "08:00", "12:00"), window("MONDAY", "13:00", "17:00", "ONLINE"), window("FRIDAY", "08:00", "17:00")];
const noop = async () => true;

// --- Schedule rules (unchanged semantics) -----------------------------------------------------

test("a draft keeps every weekday and saving replaces the whole schedule with exactly its windows", () => {
  assert.deepEqual(weekdayOrder, ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]);
  const draft = draftFromWindows(mondayTwice);
  assert.equal(draft[0].start_time, "08:00");
  assert.deepEqual(requestFromDraft(draft), [
    { weekday: "MONDAY", start_time: "08:00", end_time: "12:00", mode_scope: "ALL" },
    { weekday: "MONDAY", start_time: "13:00", end_time: "17:00", mode_scope: "ONLINE" },
    { weekday: "FRIDAY", start_time: "08:00", end_time: "17:00", mode_scope: "ALL" },
  ]);
  assert.deepEqual(requestFromDraft([]), []);
});

test("overlap and time order are checked per day and delivery mode, and name the day to fix", () => {
  const draft = (rows) => draftFromWindows(rows);
  assert.deepEqual(validateDraft(draft([window("MONDAY", "08:00", "12:00"), window("MONDAY", "11:00", "13:00", "ALL", "b")])), {
    weekday: "MONDAY",
    message: "Monday has overlapping hours for the same delivery mode.",
  });
  // "All delivery modes" overlaps both modes; In person and Online do not overlap each other.
  assert.equal(validateDraft(draft([window("TUESDAY", "08:00", "12:00"), window("TUESDAY", "09:00", "10:00", "ONLINE", "b")]))?.weekday, "TUESDAY");
  assert.equal(validateDraft(draft([window("TUESDAY", "08:00", "12:00", "IN_PERSON"), window("TUESDAY", "09:00", "10:00", "ONLINE", "b")])), null);
  assert.equal(validateDraft(draft([window("WEDNESDAY", "12:00", "12:00")]))?.message, "Wednesday contains a window whose start time is not earlier than its end time.");
  assert.equal(validateDraft([{ key: "x", weekday: "SUNDAY", start_time: "", end_time: "10:00", mode_scope: "ALL" }])?.weekday, "SUNDAY");
  assert.equal(validateDraft(draft(mondayTwice)), null);
});

test("hours read as clock times", () => {
  assert.equal(formatClockRange("08:00", "17:00"), "8:00 AM – 5:00 PM");
  assert.equal(formatClockRange("00:30", "12:15"), "12:30 AM – 12:15 PM");
});

// --- The weekly board ---------------------------------------------------------------------------

function board(props) {
  return renderToStaticMarkup(createElement(WeeklyScheduleEditor, { windows: mondayTwice, canMutate: true, pending: false, error: null, onSave: noop, ...props }));
}

test("the board keeps seven compact weekday rows, with several windows on one day", () => {
  const html = board();
  for (const day of ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]) {
    assert.match(html, new RegExp(`<li aria-labelledby="weekday-${day}"`));
    assert.match(html, new RegExp(`aria-label="Add time on ${day[0].toUpperCase()}${day.slice(1)}"`));
  }
  // Monday's two windows each have labelled start, end, and mode controls and a remove action.
  assert.match(html, /<label[^>]*for="weekly-monday-0-start"[^>]*>Monday hours 1 start time<\/label>/);
  assert.match(html, /<label[^>]*for="weekly-monday-1-mode"[^>]*>Monday hours 2 apply to<\/label>/);
  assert.match(html, /id="weekly-monday-1-start" type="time"[^>]*value="13:00"/);
  assert.match(html, /aria-label="Remove 1:00 PM – 5:00 PM on Monday"/);
  assert.equal((html.match(/No hours set/g) ?? []).length, 5);
  // The board is one panel of rows, not seven stacked form sections.
  assert.equal((html.match(/<section/g) ?? []).length, 1);
  assert.doesNotMatch(html, /<section[^>]*aria-labelledby="weekday-/);
});

test("Save belongs to the schedule, waits for a change, and keeps the replace consequence beside it", () => {
  const html = board();
  assert.match(html, /<button[^>]*disabled=""[^>]*>Save weekly schedule<\/button>/);
  assert.match(html, /Saving replaces all weekly hours shown above\. Existing appointments stay scheduled/);
  // No permanent success sentence; success is announced by the page.
  assert.doesNotMatch(html, /saved\./i);
});

test("a failed save stays beside Save", () => {
  const html = board({ error: "Your weekly Availability could not be saved." });
  assert.match(html, /aria-describedby="weekly-schedule-error"[^>]*>Save weekly schedule/);
  assert.match(html, /<p id="weekly-schedule-error" role="alert"[^>]*>Your weekly Availability could not be saved\.<\/p>/);
});

test("without edit access the board reads as text, with no inputs or Save", () => {
  const html = board({ canMutate: false });
  assert.match(html, /8:00 AM – 12:00 PM<span class="text-muted"> · All delivery modes<\/span>/);
  assert.match(html, /1:00 PM – 5:00 PM<span class="text-muted"> · Online<\/span>/);
  assert.doesNotMatch(html, /<input|<select|Save weekly schedule|Add time on/);
});

test("hours that can only be reviewed or cleared keep the Clear confirmation outside the keyed editor", () => {
  const html = renderToStaticMarkup(createElement(WeeklyScheduleCleanup, { windows: mondayTwice, pending: false, error: null, onClear: noop, onResetError() {} }));
  assert.match(html, /Clear weekly schedule/);
  assert.match(html, /8:00 AM – 12:00 PM/);
  assert.doesNotMatch(html, /<input/);
  const pages = readFileSync(new URL("../src/features/availability/availability-pages.tsx", import.meta.url), "utf8");
  assert.match(pages, /<WeeklyScheduleCleanup\s+windows=/);
  assert.doesNotMatch(pages, /<WeeklyScheduleCleanup\s+key=/);
});

// --- Unavailability -------------------------------------------------------------------------------

const exception = (id, startsAt, endsAt, extra = {}) => ({ id, starts_at: startsAt, ends_at: endsAt, mode_scope: "ALL", reason: "", ...extra });

function section(items, props = {}) {
  return renderToStaticMarkup(createElement(UnavailabilitySection, {
    items, canCreate: true, canRemove: true, createPending: false, removePending: false, error: null,
    onCreate: noop, onRemove: noop, onResetError() {}, ...props,
  }));
}

test("upcoming periods are listed flat, and past ones fold under their count", () => {
  const html = section([
    exception("u1", "2099-10-12T00:00:00Z", "2099-10-12T04:00:00Z", { reason: "Staff training", mode_scope: "ONLINE" }),
    exception("p1", "2020-01-02T00:00:00Z", "2020-01-02T08:00:00Z"),
    exception("p2", "2020-01-03T00:00:00Z", "2020-01-03T08:00:00Z"),
  ]);
  assert.match(html, /Upcoming/);
  assert.match(html, /Staff training/);
  assert.match(html, /aria-label="Remove unavailability Mon, Oct 12, 2099 · 8:00 AM – 12:00 PM"/);
  assert.match(html, /<details[^>]*>[\s\S]*Past · 2/);
  // No bordered list nested inside the panel.
  assert.doesNotMatch(html, /divide-y divide-border rounded-sm border/);
  assert.match(html, /Add<span class="sr-only"> unavailability<\/span>/);
});

test("with nothing recorded the region stays compact; with no upcoming period it says so", () => {
  assert.match(section([]), /data-density="compact"[^>]*><p[^>]*>No unavailability has been recorded\./);
  assert.match(section([exception("p1", "2020-01-02T00:00:00Z", "2020-01-02T08:00:00Z")]), /No upcoming unavailability\./);
});

test("a failure is shown inside the Add dialog, never in the list behind it", () => {
  const html = section([], { error: "Your unavailability could not be added." });
  assert.doesNotMatch(html, /could not be added/);
  const source = readFileSync(new URL("../src/features/availability/unavailability-section.tsx", import.meta.url), "utf8");
  assert.match(source, /<form className="mt-6 space-y-5" onSubmit=\{submitCreate\}>[\s\S]*\{localError \?\? error\}[\s\S]*<\/form>/);
  // Removal confirms, then completes in the same dialog.
  assert.match(source, /completed=\{removed \? \{\s*title: "Unavailability removed"/);
});

test("periods read in the institution's time, shortened within one day", () => {
  assert.equal(formatUnavailabilityRange("2026-10-12T00:00:00Z", "2026-10-12T04:00:00Z"), "Mon, Oct 12, 2026 · 8:00 AM – 12:00 PM");
  assert.equal(formatUnavailabilityRange("2026-10-20T00:00:00Z", "2026-10-21T09:00:00Z"), "Oct 20, 2026, 8:00 AM – Oct 21, 2026, 5:00 PM");
});

// --- Page composition and feedback ------------------------------------------------------------

function myAvailability() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const ok = (data) => ({ data, status: 200, headers: {} });
  client.setQueryData(getAvailabilityGetMyWeeklyQueryKey(), ok({ provider_id: "p", windows: mondayTwice }));
  client.setQueryData(getAvailabilityListMyExceptionsQueryKey(), ok({ provider_id: "p", items: [] }));
  const user = { id: "p", role: "COUNSELOR", capabilities: ["availability.view", "availability.manage_self"] };
  return renderToStaticMarkup(withNextRouter(createElement(QueryClientProvider, { client },
    createElement(PortalSessionProvider, { value: { user } }, createElement(MyAvailabilityPage)))));
}

test("the schedule leads, its exceptions sit beside it on wide pages, and the preview spans below", () => {
  const html = myAvailability();
  assert.match(html, /@container\/availability/);
  assert.match(html, /grid items-start gap-5 @\[68rem\]\/availability:grid-cols-\[minmax\(0,2fr\)_minmax\(20rem,1fr\)\]/);
  const schedule = html.indexOf('id="weekly-schedule-heading"');
  const exceptions = html.indexOf('id="unavailability-heading"');
  assert.ok(schedule > 0 && exceptions > schedule, "the schedule comes first, so narrow pages stack it above");
  assert.match(html, /data-action-status=""/);
});

test("routine saves are announced only after the server confirms them; removal completes in its dialog", () => {
  const source = readFileSync(new URL("../src/features/availability/availability-pages.tsx", import.meta.url), "utf8");
  for (const message of ["Weekly schedule saved.", "Unavailability added.", "Office weekly schedule saved.", "Office unavailability added."]) {
    const at = source.indexOf(`status.show("${message}")`);
    assert.ok(at > 0, `${message} is announced`);
    const before = source.lastIndexOf(".run(", at);
    assert.ok(source.slice(before, at).includes("if (!response) return false;"), `${message} follows a confirmed response`);
  }
  assert.doesNotMatch(source, /status\.show\("[^"]*removed/i);
  // A new attempt clears an earlier confirmation, so it never sits beside a new failure.
  assert.equal((source.match(/status\.dismiss\(\);\n\s+const response = await/g) ?? []).length, 9);
  // Preview refreshes after each change that affects it.
  assert.ok((source.match(/setPreviewRefresh\(\(value\) => value \+ 1\)/g) ?? []).length >= 6);
});
