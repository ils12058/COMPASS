import assert from "node:assert/strict";
import test from "node:test";

import {
  batchCommitReady,
  batchRowActionLabel,
  graduationConsequence,
  graduationsTemplate,
  termFacts,
  termRecordsTemplate,
  typedCountMatches,
} from "../src/features/student-academics/roster-import/batch-import-presentation.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";

const file = { name: "a.csv" };
const valid = { valid: true, committed: false };

test("templates carry exactly the backend headers", () => {
  assert.equal(termRecordsTemplate, "institutional_id,campus_code,college_code,year_level,enrollment_status\n");
  assert.equal(graduationsTemplate, "institutional_id,campus_code,college_code,graduation_date\n");
});

test("apply is offered only for the same file and choices the preview checked", () => {
  const reviewed = { file, scope: "year|FIRST_SEMESTER" };
  const base = { file, reviewed, scope: "year|FIRST_SEMESTER", report: valid, conflict: false, writes: 2 };
  assert.equal(batchCommitReady(base), true);
  assert.equal(batchCommitReady({ ...base, scope: "year|SECOND_SEMESTER" }), false, "changing the term needs a new preview");
  assert.equal(batchCommitReady({ ...base, file: { name: "b.csv" } }), false);
  assert.equal(batchCommitReady({ ...base, writes: 0 }), false);
  assert.equal(batchCommitReady({ ...base, conflict: true }), false);
  assert.equal(batchCommitReady({ ...base, report: { valid: false, committed: false } }), false);
  assert.equal(batchCommitReady({ ...base, report: { valid: true, committed: true } }), false);
});

test("the typed graduation confirmation must equal the count exactly", () => {
  assert.equal(typedCountMatches("126", 126), true);
  assert.equal(typedCountMatches(" 126 ", 126), true);
  assert.equal(typedCountMatches("125", 126), false);
  assert.equal(typedCountMatches("126.0", 126), false);
  assert.equal(typedCountMatches("", 0), false);
});

test("labels and consequences use plain words", () => {
  assert.equal(batchRowActionLabel("GRADUATE"), "Will graduate");
  assert.equal(batchRowActionLabel("INVALID"), "Problem");
  assert.equal(termFacts(2, "ENROLLED"), "Year 2 · Enrolled");
  assert.equal(termFacts(null, "UNKNOWN"), "No year level · Unknown");
  assert.equal(termFacts(null, null), "—");
  assert.equal(
    graduationConsequence({ graduate_count: 126, update_count: 1, placement_cleared_count: 120 }),
    "126 Students will become Graduated; 1 Student will have their graduation record updated; 120 Students will leave their current College placement.",
  );
});

test("the two new imports are reachable from the command menu only for importers", () => {
  const account = (capabilities) => ({
    id: "00000000-0000-4000-8000-000000000001",
    email: "fixture@example.test",
    first_name: "Fixture",
    last_name: "User",
    role: "IT_ADMIN",
    capabilities,
    designations: [],
    student_lifecycle_status: null,
  });
  const importer = portalCommandDestinations(account(["organization.structure.view", "student_academics.view", "student_academics.import"]));
  for (const href of ["/portal/organization/student-academics/import/terms", "/portal/organization/student-academics/import/graduations"]) {
    assert.ok(importer.some((item) => item.href === href), href);
    assert.equal(portalCommandDestinations(account(["organization.structure.view", "student_academics.view"])).some((item) => item.href === href), false);
  }
});
