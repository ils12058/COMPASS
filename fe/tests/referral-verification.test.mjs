import assert from "node:assert/strict";
import { test } from "node:test";
import {
  detectCourseYearBlockMismatch,
  extractTypedYearLevel,
  formatAcademicUnit,
  formatStudentPlacementSummary,
} from "../src/features/referrals/student-verification.ts";

const bsisThirdYear = {
  college: { code: "CCMS", name: "College of Computing and Multimedia Studies" },
  program: { code: "BSIS", name: "Bachelor of Science in Information Systems" },
  year_level: 3,
};

test("formatAcademicUnit and formatStudentPlacementSummary handle present and missing fields", () => {
  assert.equal(
    formatAcademicUnit({ code: "CCMS", name: "College of Computing and Multimedia Studies" }),
    "CCMS — College of Computing and Multimedia Studies",
  );
  assert.equal(formatAcademicUnit({ code: "ENTIENZA", name: "ENTIENZA" }), "ENTIENZA");
  assert.equal(formatAcademicUnit(null), null);
  assert.equal(
    formatStudentPlacementSummary(bsisThirdYear),
    "BSIS — Bachelor of Science in Information Systems · 3rd Year",
  );
  assert.equal(
    formatStudentPlacementSummary({ college: bsisThirdYear.college, program: null, year_level: null }),
    "",
  );
});

test("extractTypedYearLevel recognizes common Philippine Course/Year/Block formats without misreading numbers", () => {
  assert.equal(extractTypedYearLevel("BSIS 3A"), 3);
  assert.equal(extractTypedYearLevel("BSIS-3A"), 3);
  assert.equal(extractTypedYearLevel("BSIS 3-A"), 3);
  assert.equal(extractTypedYearLevel("BSIS / 4 / B"), 4);
  assert.equal(extractTypedYearLevel("BSIS 2nd Year Block A"), 2);
  assert.equal(extractTypedYearLevel("BSIS Year 4 - Block 2"), 4);
  assert.equal(extractTypedYearLevel("BSIS 3rd Year - Block 2"), 3);
  assert.equal(extractTypedYearLevel("First Year Block C"), 1);
  assert.equal(extractTypedYearLevel("BSIS III-A"), 3);
  assert.equal(extractTypedYearLevel("2-B"), 2);

  // Non-year numbers must not produce false year levels.
  assert.equal(extractTypedYearLevel("BSIS Block 2"), null);
  assert.equal(extractTypedYearLevel("BSIS Section 1"), null);
  assert.equal(extractTypedYearLevel("BSIS 2026"), null);
  assert.equal(extractTypedYearLevel("BSIS 101"), null);
  assert.equal(extractTypedYearLevel("Synthetic course"), null);
});

test("detectCourseYearBlockMismatch stays quiet on matching or non-conflicting free-form text", () => {
  for (const typed of [
    "BSIS 3A",
    "BSIS 3-A",
    "BSIS-3A",
    "BS Information Systems 3rd Year Block A",
    "Bachelor of Science in Information Systems 3A",
    "BSIS Block A",
    "3A",
    "3rd Year - Block 2",
    "CCMS 3A",
    "CCMS course declared by CAS Faculty",
    "Synthetic course",
  ]) {
    assert.equal(
      detectCourseYearBlockMismatch(typed, bsisThirdYear),
      null,
      `Expected no mismatch for "${typed}"`,
    );
  }

  // Hyphenated program code allows writing just the base program code.
  const bsbaFm = {
    college: { code: "CBPA", name: "College of Business and Public Administration" },
    program: { code: "BSBA-FM", name: "Bachelor of Science in Business Administration Major in Financial Management" },
    year_level: 2,
  };
  assert.equal(detectCourseYearBlockMismatch("BSBA 2A", bsbaFm), null);
  assert.equal(detectCourseYearBlockMismatch("BSBA-FM 2A", bsbaFm), null);
  assert.equal(detectCourseYearBlockMismatch("BSBA FM 2A", bsbaFm), null);
});

test("detectCourseYearBlockMismatch warns clearly on Program, Year level, or combined disagreements", () => {
  const programOnly = detectCourseYearBlockMismatch("BSIT 3A", bsisThirdYear);
  assert.ok(programOnly);
  assert.equal(programOnly.programMismatch, true);
  assert.equal(programOnly.yearLevelMismatch, false);
  assert.match(programOnly.message, /BSIS — Bachelor of Science in Information Systems/);
  assert.match(programOnly.message, /still submit if this is intentional/);

  const yearOnly = detectCourseYearBlockMismatch("BSIS 2A", bsisThirdYear);
  assert.ok(yearOnly);
  assert.equal(yearOnly.programMismatch, false);
  assert.equal(yearOnly.yearLevelMismatch, true);
  assert.equal(yearOnly.detectedYearLevel, 2);
  assert.match(yearOnly.message, /3rd Year/);

  const both = detectCourseYearBlockMismatch("BSN 1st Year Block B", bsisThirdYear, { action: "record" });
  assert.ok(both);
  assert.equal(both.programMismatch, true);
  assert.equal(both.yearLevelMismatch, true);
  assert.match(both.message, /Program .* and Year level \(3rd Year\)/);
  assert.match(both.message, /still record this Referral if this is intentional/);

  // Full degree name disagreement.
  const fullPhrase = detectCourseYearBlockMismatch(
    "Bachelor of Science in Civil Engineering 3A",
    bsisThirdYear,
  );
  assert.ok(fullPhrase?.programMismatch);

  // Different hyphenated major disagrees.
  const bsbaFm = {
    college: { code: "CBPA", name: "College of Business and Public Administration" },
    program: { code: "BSBA-FM", name: "Bachelor of Science in Business Administration Major in Financial Management" },
    year_level: 2,
  };
  assert.equal(detectCourseYearBlockMismatch("BSBA-MM 2A", bsbaFm)?.programMismatch, true);

  // Missing actual program or year level never invents a mismatch for that field.
  assert.equal(
    detectCourseYearBlockMismatch("BSIT 2A", {
      college: bsisThirdYear.college,
      program: null,
      year_level: null,
    }),
    null,
  );
});
