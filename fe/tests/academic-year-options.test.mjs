import assert from "node:assert/strict";
import { test } from "node:test";

import {
  academicYearLabel,
  academicYearOptions,
  currentInstitutionCalendarYear,
  suggestedAcademicYearStart,
} from "../src/features/institution-configuration/academic-year-options.ts";

test("a starting year produces a canonical consecutive label", () => {
  assert.equal(academicYearLabel(2026), "2026-2027");
});

test("choices update with the institutional calendar year and include historical and future years", () => {
  const in2026 = academicYearOptions(2026, []);
  const in2027 = academicYearOptions(2027, []);

  assert.equal(in2026[0].startYear, 1900);
  assert.ok(in2026.some((option) => option.startYear === 2036));
  assert.ok(in2027.some((option) => option.startYear === 2037));
  assert.equal(in2027.length, in2026.length + 1);
});

test("year defaults use the institution-local date and skip existing canonical years", () => {
  assert.equal(currentInstitutionCalendarYear(new Date("2026-12-31T16:30:00.000Z")), 2027);

  const options = academicYearOptions(2026, ["2026-2027", "AY 2023"]);
  assert.equal(options.find((option) => option.startYear === 2026)?.exists, true);
  assert.equal(suggestedAcademicYearStart(2026, options), 2027);
});

test("an existing canonical year extends future options and legacy labels are preserved", () => {
  const options = academicYearOptions(2026, ["1899-1900", "legacy AY", "2040-2041"]);

  assert.equal(options[0].startYear, 1899);
  assert.ok(options.some((option) => option.startYear === 2041));
  assert.ok(!options.some((option) => option.label === "legacy AY"));
});
