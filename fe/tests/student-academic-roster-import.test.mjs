import assert from "node:assert/strict";
import { test } from "node:test";

import { portalCommandDestinations, searchPortalCommands } from "../src/features/portal/components/portal-command-destinations.ts";
import { canImportStudentAcademics } from "../src/features/student-academics/student-academics-access.ts";
import {
  rosterCommitReady,
  rosterError,
  rosterIssues,
  rosterRowActionLabel,
  rosterTemplate,
} from "../src/features/student-academics/roster-import/roster-import-presentation.ts";

const account = (capabilities, role = "COUNSELOR") => ({
  id: "00000000-0000-4000-8000-000000000001",
  email: "fixture@example.test",
  first_name: "Fixture",
  last_name: "User",
  role,
  capabilities,
  designations: [],
  student_lifecycle_status: role === "STUDENT" ? "CURRENT" : null,
});

const report = (overrides = {}) => ({
  valid: true,
  committed: false,
  total_rows: 1,
  set_count: 1,
  noop_count: 0,
  conflict_count: 0,
  invalid_count: 0,
  rows: [],
  ...overrides,
});

test("academic roster import requires the dedicated import capability", () => {
  assert.equal(
    canImportStudentAcademics(account(["student_academics.view", "student_academics.import"])),
    true,
  );
  assert.equal(
    canImportStudentAcademics(account(["student_academics.view", "student_academics.manage"])),
    false,
  );
  assert.equal(canImportStudentAcademics(account([], "STUDENT")), false);
});

test("roster template and row action labels are stable", () => {
  assert.equal(rosterTemplate, "institutional_id,campus_code,college_code\n");
  assert.equal(rosterRowActionLabel("SET"), "Set");
  assert.equal(rosterRowActionLabel("NOOP"), "No change");
  assert.equal(rosterRowActionLabel("CONFLICT"), "Conflict");
  assert.equal(rosterRowActionLabel("INVALID"), "Invalid");
  assert.equal(rosterRowActionLabel("FUTURE_ACTION"), "FUTURE_ACTION");
});

test("commit readiness requires the validated file identity, a clean uncommitted report, and at least one set", () => {
  const file = new File(["institutional_id,campus_code,college_code\n"], "roster.csv");
  const other = new File(["institutional_id,campus_code,college_code\n"], "other.csv");
  assert.equal(rosterCommitReady({ file: null, reviewedFile: null, report: report(), conflict: false }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: other, report: report(), conflict: false }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: file, report: null, conflict: false }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: file, report: report({ valid: false }), conflict: false }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: file, report: report({ committed: true }), conflict: false }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: file, report: report(), conflict: true }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: file, report: report({ set_count: 0 }), conflict: false }), false);
  assert.equal(rosterCommitReady({ file, reviewedFile: file, report: report(), conflict: false }), true);
});

test("roster issues are read from API error details without trusting other fields", () => {
  const error = {
    body: {
      error: {
        code: "csv_import_invalid_rows",
        message: "one or more CSV rows are invalid",
        details: [
          { row_number: 3, institutional_id: "UCN-3", message: "campus_code is required" },
          { message: "message without row identity" },
          { row_number: "4", institutional_id: 7, message: "coerced values are ignored" },
          "not an object",
        ],
      },
    },
  };
  assert.deepEqual(rosterIssues(error), [
    { row: 3, institutionalId: "UCN-3", message: "campus_code is required" },
    { row: null, institutionalId: "", message: "message without row identity" },
    { row: null, institutionalId: "", message: "coerced values are ignored" },
  ]);
  assert.deepEqual(rosterIssues({ body: { error: { details: "not a list" } } }), []);
  assert.deepEqual(rosterIssues(new Error("network failure")), []);
  assert.deepEqual(rosterIssues(null), []);
});

test("roster errors map known codes and otherwise keep the server message or fallback", () => {
  const withBody = (code, message) => ({ body: { error: { code, message } } });
  assert.equal(
    rosterError(withBody("permission_denied", "The student_academics.import capability is required."), "fallback"),
    "The student_academics.import capability is required to import an academic roster.",
  );
  assert.equal(
    rosterError(withBody("identity_policy_unavailable", "Unavailable."), "fallback"),
    "Academic policy is temporarily unavailable. Try again later.",
  );
  assert.equal(
    rosterError(withBody("csv_import_conflict", "one or more CSV rows conflict"), "fallback"),
    "one or more CSV rows conflict",
  );
  assert.equal(rosterError(withBody("csv_import_malformed", ""), "fallback"), "fallback");
  assert.equal(rosterError(new Error("network failure"), "fallback"), "fallback");
  assert.equal(rosterError(null, "fallback"), "fallback");
});

test("the academic roster import destination appears only for accounts with the import capability", () => {
  const path = "/portal/organization/student-academics/import";
  const importer = account([
    "organization.structure.view",
    "student_academics.view",
    "student_academics.import",
  ]);
  const viewer = account(["organization.structure.view", "student_academics.view"]);

  const destination = portalCommandDestinations(importer).find((item) => item.href === path);
  assert.equal(destination?.label, "Import academic roster");
  assert.equal(destination?.group, "Institution");
  assert.equal(destination?.breadcrumb, "Organization › Import academic roster");
  assert.ok(searchPortalCommands(portalCommandDestinations(importer), "csv").some((item) => item.href === path));
  assert.equal(
    portalCommandDestinations(viewer).some((item) => item.href === path),
    false,
  );
  assert.equal(
    portalCommandDestinations(account(["organization.structure.view", "student_academics.import"])).some(
      (item) => item.href === path,
    ),
    true,
  );
});
