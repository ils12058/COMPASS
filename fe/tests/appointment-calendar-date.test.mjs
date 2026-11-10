import assert from "node:assert/strict";
import { test } from "node:test";
import { calendarDate, calendarDateValue } from "../src/features/appointments/appointment-calendar-date.ts";
import { institutionalDateInputValue } from "../src/lib/institutional-time.ts";

test("calendar values stay civil dates across leap days and year boundaries", () => {
  for (const value of ["0001-01-01", "2026-12-31", "2027-01-01", "2028-02-29", "9999-12-31"]) {
    assert.equal(calendarDateValue(calendarDate(value)), value);
  }
  for (const value of ["0000-01-01", "2027-02-29", "2028-02-30", "2026-13-01", "2026-01-00", "2026-1-01", "", "2026-11-11T00:00:00Z"]) {
    assert.equal(calendarDate(value), undefined, value);
  }
});

test("institutional today crosses midnight in Manila while selected dates round-trip unchanged", () => {
  const now = new Date("2026-12-31T16:05:00Z");
  assert.equal(institutionalDateInputValue(now), "2027-01-01");
  assert.equal(calendarDateValue(calendarDate(institutionalDateInputValue(now))), "2027-01-01");
});
