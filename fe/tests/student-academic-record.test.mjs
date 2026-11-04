import assert from "node:assert/strict";
import { test } from "node:test";

import {
  academicTermLabel,
  enrollmentStatusLabel,
  lifecycleStatusLabel,
  yearLevelLabel,
} from "../src/features/student-academics/student-academic-record/academic-record-presentation.ts";

test("academic terms, enrollment, lifecycle, and year levels use readable institutional labels", () => {
  assert.equal(academicTermLabel("FIRST_SEMESTER"), "First Semester");
  assert.equal(academicTermLabel("SECOND_SEMESTER"), "Second Semester");
  assert.equal(enrollmentStatusLabel("UNKNOWN"), "Unknown");
  assert.equal(enrollmentStatusLabel("ENROLLED"), "Enrolled");
  assert.equal(enrollmentStatusLabel("NOT_ENROLLED"), "Not enrolled");
  assert.equal(lifecycleStatusLabel("CURRENT"), "Current");
  assert.equal(lifecycleStatusLabel("GRADUATED"), "Graduated");
  assert.equal(lifecycleStatusLabel("FORMER"), "Former");
  assert.equal(lifecycleStatusLabel(null), "Not set");
  assert.equal(yearLevelLabel(2), "2");
  assert.equal(yearLevelLabel(null), "—");
});
