import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CompassApiError } from "../src/lib/api/errors.ts";
import {
  RoutineContextSummary,
  routineAcademicYearLabel,
  routineErrorMessage,
  routineInventoryNote,
  routineProgramLabel,
} from "../src/features/routine-interviews/routine-interviews-shared.tsx";

const year = { id: "year", label: "2026-2027" };
const submitted = { id: "inventory", academic_year: year, available: true, full_name: "Student Example", course: "BS Information Systems", major: "Data" };
const correcting = { ...submitted, available: false, full_name: null, course: null, major: null };

function summary(overrides) {
  return renderToStaticMarkup(h(RoutineContextSummary, {
    personName: "Student Example",
    academicYear: year,
    inventoryContext: submitted,
    appointment: null,
    encounter: null,
    entryMode: "WALK_IN",
    deliveryMode: "IN_PERSON",
    intakeStatus: "DRAFT",
    intakeSubmittedAt: null,
    createdAt: "2026-10-07T00:00:00Z",
    formRevision: null,
    ...overrides,
  }));
}

test("a Routine Interview with submitted Inventory context shows course and major", () => {
  const html = summary({});
  assert.match(html, /BS Information Systems · Data/);
  assert.match(html, /2026-2027/);
  assert.doesNotMatch(html, /Individual Inventory/);
});

test("a Routine Interview that began without an Inventory still shows its own Academic Year", () => {
  const html = summary({ inventoryContext: null });
  assert.match(html, /2026-2027/);
  assert.match(html, /Not available at initiation/);
  assert.doesNotMatch(html, /Course and major/);
});

test("an Inventory reopened for correction shows no draft values", () => {
  const html = summary({ inventoryContext: correcting });
  assert.match(html, /Being corrected/);
  assert.doesNotMatch(html, /Course and major/);
  assert.equal(routineProgramLabel(correcting), null);
});

test("presentation helpers never invent missing context", () => {
  assert.equal(routineAcademicYearLabel(null), "Not recorded");
  assert.equal(routineInventoryNote(null), "Not available at initiation");
  assert.equal(routineInventoryNote(submitted), null);
  assert.equal(routineProgramLabel({ ...submitted, major: " " }), "BS Information Systems");
  assert.match(summary({ academicYear: null, inventoryContext: null }), /Not recorded/);
});

test("Routine Interviews no longer explain an Inventory prerequisite", () => {
  const error = new CompassApiError({ status: 409, body: { error: { code: "routine_interview_inventory_required", message: "raw" } }, headers: {}, method: "POST", url: "/api/v1/routine-interviews/me" });
  assert.equal(routineErrorMessage(error, "fallback"), "fallback");
});
