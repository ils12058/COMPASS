import assert from "node:assert/strict";
import { test } from "node:test";

import {
  academicTermLabel,
  enrollmentStatusLabel,
  lifecycleStatusLabel,
  yearLevelLabel,
} from "../src/features/student-academics/student-academic-record/academic-record-presentation.ts";
import {
  canManageStudentAcademics,
  canViewOwnAcademicRecord,
  canViewStudentAcademics,
} from "../src/features/student-academics/student-academics-access.ts";

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

test("staff and self-view gates follow the dedicated academic capabilities", () => {
  const staff = { role: "IT_ADMIN", capabilities: ["student_academics.view", "student_academics.manage"] };
  const viewer = { role: "COUNSELOR", capabilities: ["student_academics.view"] };
  const student = { role: "STUDENT", capabilities: ["student_academics.view_self"] };
  const unprivilegedStudent = { role: "STUDENT", capabilities: [] };
  const studentWithStaffCapability = { role: "STUDENT", capabilities: ["student_academics.view"] };

  assert.equal(canViewStudentAcademics(staff), true);
  assert.equal(canManageStudentAcademics(staff), true);
  assert.equal(canViewOwnAcademicRecord(staff), false);
  assert.equal(canViewStudentAcademics(viewer), true);
  assert.equal(canManageStudentAcademics(viewer), false);
  assert.equal(canViewOwnAcademicRecord(viewer), false);
  assert.equal(canViewStudentAcademics(student), false);
  assert.equal(canManageStudentAcademics(student), false);
  assert.equal(canViewOwnAcademicRecord(student), true);
  assert.equal(canViewOwnAcademicRecord(unprivilegedStudent), false);
  assert.equal(canViewOwnAcademicRecord(studentWithStaffCapability), false);
});
